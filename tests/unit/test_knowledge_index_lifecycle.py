"""Offline USER catalog generation lifecycle and fail-closed rebuild diagnostics."""

import json
import threading
from dataclasses import replace

import pytest
from test_knowledge_base import REVIEWED, dataset, monthly
from test_prepared_dense import Recording

from kkb_agent.api.knowledge_service import KnowledgeService
from kkb_agent.api.store import DATABASE_NAME, ConversationStore
from kkb_agent.catalog import embedding
from kkb_agent.catalog.hybrid import CatalogDenseStage
from kkb_agent.catalog.lance_index import (
    MANIFEST,
    CatalogIndexError,
    LocalCatalogIndex,
    build_catalog_index,
)
from kkb_agent.knowledge import KnowledgeStore
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ConfigurationError, TransportError


@pytest.fixture
def lifecycle(tmp_path):
    conversations = ConversationStore(tmp_path / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path / "knowledge.sqlite")
    _, token = conversations.create_owner()
    provider = Recording(scripted(embedding_dimension=4096))
    profile = embedding.profile_for(embedding.RUNTIME_QUERY_POLICY, "offline_fixture")
    generations = tmp_path / "catalog-index"
    installed = []

    def open_stage(catalog):
        root = generations / catalog.content_sha256
        if not (root / "catalog-manifest.json").exists():
            return None
        return CatalogDenseStage(
            LocalCatalogIndex.open(root, catalog, profile),
            embedding.query_embedder(
                provider, embedding.RUNTIME_QUERY_POLICY, origin="offline_fixture"
            ),
        )

    def build_stage(catalog, previous=None):
        existing = open_stage(catalog)
        if existing is not None:
            return existing
        vectors = embedding.embed_catalog(
            provider,
            catalog,
            embedding.RUNTIME_QUERY_POLICY,
            origin="offline_fixture",
            reuse=previous,
        )
        build_catalog_index(generations / catalog.content_sha256, catalog, vectors)
        return open_stage(catalog)

    old = build_stage(REVIEWED)
    service = KnowledgeService(
        knowledge,
        conversations,
        REVIEWED,
        prepared=frozenset(),
        dense=old,
        rebuild_index=build_stage,
        reopen_index=open_stage,
        install_index=installed.append,
    )
    yield service, knowledge, token, provider, old, build_stage, installed
    service.close()
    knowledge.close()
    conversations.close()


def _stage_of(trial, series_id: str) -> str | None:
    """Which stage found one identity in a trial's hits."""
    return next((hit.stage for hit in trial.hits if hit.series_id == series_id), None)


def test_user_save_rebuild_reopen_archive_and_version_are_digest_bound(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    first = knowledge.save_dataset(dataset())
    stale = service.index_status(token)
    assert not stale.covers_catalog and stale.missing == (first.series_id,)
    # This question's own alias maps only to the entry that was just saved, and that one
    # entry has no vector yet, so the meaning stage has nothing it can rank.
    lexical = service.search(token, "kart harcaması")
    assert lexical.retrieval_mode == "lexical_degraded"
    assert first.series_id in {hit.series_id for hit in lexical.hits}
    # Every other entry is covered exactly as it was, so a question about one of them is
    # still answered by meaning. One saved record used to turn the whole stage off (N27).
    reviewed_question = service.search(token, "konut kredisi stok")
    assert reviewed_question.retrieval_mode == "hybrid"
    assert {"dense", "both"} & {hit.stage for hit in reviewed_question.hits}

    service.rebuild(token)
    service.close()
    covered = service.index_status(token)
    assert covered.covers_catalog and covered.missing == () and covered.last_error is None
    assert service.search(token, "kart harcaması").retrieval_mode == "hybrid"
    embedded = len(provider.embedded)
    assert service.rebuild(token).covers_catalog  # same exact generation is a no-op
    assert len(provider.embedded) == embedded

    restarted = KnowledgeService(
        knowledge,
        service._conversations,
        REVIEWED,
        prepared=frozenset(),
        dense=old,
        reopen_index=lambda catalog: build_stage(catalog),
        install_index=installed.append,
    )
    assert restarted.restore_generation()
    assert restarted.index_status(token).covers_catalog
    assert len(provider.embedded) == embedded  # exact generation reopened, not re-embedded

    second = knowledge.save_dataset(dataset(observations=monthly([101.0, 110.0, 125.0])))
    assert second.series_id != first.series_id
    assert not service.index_status(token).covers_catalog
    assert service.index_status(token).missing == (second.series_id,)
    knowledge.set_dataset_status(first.slug, "archived", author="test")
    assert service.index_status(token).catalog_sha256 == REVIEWED.content_sha256
    knowledge.set_dataset_status(first.slug, "active", author="test")
    assert service.index_status(token).catalog_sha256 not in {
        REVIEWED.content_sha256,
        covered.catalog_sha256,
    }


def test_catalog_change_during_build_never_installs_stale_stage(lifecycle):
    service, knowledge, token, _, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())

    def changed_during_build(catalog, previous):
        stage = build_stage(catalog, previous)
        knowledge.save_dataset(dataset(observations=monthly([101.0, 110.0, 125.0])))
        return stage

    service._rebuild = changed_during_build
    service.rebuild(token)
    service.close()
    status = service.index_status(token)
    assert status.last_error == "concurrent_catalog_change"
    assert not status.covers_catalog and installed == [] and service._dense is old
    # The stage that was kept is the reviewed one: it covers no entry this question is
    # about, and still covers every reviewed series.
    assert service.search(token, "kart harcaması").retrieval_mode == "lexical_degraded"
    assert service.search(token, "konut kredisi stok").retrieval_mode == "hybrid"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ConfigurationError("secret=do-not-echo"), "provider_auth_or_configuration"),
        (TransportError("secret=do-not-echo"), "provider_transient_failure"),
        (CatalogIndexError("INDEX_CATALOG_DIGEST_MISMATCH"), "catalog_digest_mismatch"),
        (CatalogIndexError("INDEX_PROFILE_MISMATCH"), "profile_mismatch"),
        (CatalogIndexError("INDEX_VECTOR_DIMENSION_MISMATCH"), "vector_dimension_mismatch"),
        (CatalogIndexError("INDEX_MANIFEST_INVALID"), "generation_corrupt_or_incomplete"),
        (OSError("/private/secret/path"), "state_filesystem_failure"),
    ],
)
def test_failed_rebuild_keeps_valid_generation_and_sanitizes_status(lifecycle, error, category):
    service, knowledge, token, _, old, build_stage, installed = lifecycle
    old_manifest = knowledge._path.parent / "catalog-index" / REVIEWED.content_sha256 / MANIFEST
    unchanged = old_manifest.read_bytes()
    knowledge.save_dataset(dataset())

    def fail(_catalog, _previous):
        raise error

    service._rebuild = fail
    service.rebuild(token)
    service.close()
    status = service.index_status(token)
    assert status.last_error == category and "secret" not in status.last_error
    assert service._dense is old and installed == []
    assert old_manifest.read_bytes() == unchanged
    assert not status.covers_catalog
    service._rebuild = build_stage
    service.rebuild(token)
    service.close()
    assert service.index_status(token).covers_catalog
    assert service.index_status(token).last_error is None


@pytest.mark.parametrize("failure", ["digest", "profile", "install"])
def test_wrong_generation_or_install_failure_preserves_active_stage(lifecycle, failure):
    service, knowledge, token, _, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())

    def build(catalog, previous):
        stage = build_stage(catalog, previous)
        if failure == "digest":
            return old
        if failure == "profile":
            wrong = embedding.profile_for("qwen3-plain-v1", "offline_fixture")
            return replace(stage, index=replace(stage.index, _profile=wrong))
        return stage

    service._rebuild = build
    if failure == "install":

        def fail_install(_stage):
            raise OSError("/private/secret/path")

        service._install = fail_install
    service.rebuild(token)
    service.close()
    assert service._dense is old and installed == []
    assert (
        service.index_status(token).last_error
        == {
            "digest": "catalog_digest_mismatch",
            "profile": "profile_mismatch",
            "install": "state_filesystem_failure",
        }[failure]
    )


@pytest.mark.parametrize(
    ("change", "category"),
    [
        ("manifest", "generation_corrupt_or_incomplete"),
        ("profile", "profile_mismatch"),
    ],
)
def test_corrupt_or_wrong_profile_generation_never_reopens(lifecycle, change, category):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())
    catalog = service._effective()
    build_stage(catalog)
    path = knowledge._path.parent / "catalog-index" / catalog.content_sha256 / MANIFEST
    if change == "manifest":
        path.write_text("{broken", encoding="utf-8")
    else:
        body = json.loads(path.read_text(encoding="utf-8"))
        body["profile"]["input_policy_id"] = "qwen3-plain-v1"
        path.write_text(json.dumps(body), encoding="utf-8")
    embedded = len(provider.embedded)
    assert not service.restore_generation()
    assert len(provider.embedded) == embedded
    assert service._dense is old and installed == []
    assert service.index_status(token).last_error == category


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ([[1.0] * 4096], "INDEX_EMBEDDING_COUNT_MISMATCH"),
        ([[1.0] * 4095] * len(REVIEWED.series), "INDEX_VECTOR_DIMENSION_MISMATCH"),
    ],
)
def test_partial_or_wrong_dimension_fake_embedding_is_refused(monkeypatch, supplied, expected):
    provider = scripted(embedding_dimension=4096)
    monkeypatch.setattr(provider, "embed", lambda _texts, *, kind: supplied)
    with pytest.raises(CatalogIndexError, match=expected):
        embedding.embed_catalog(
            provider, REVIEWED, embedding.RUNTIME_QUERY_POLICY, origin="offline_fixture"
        )


def _passages(provider, since=0):
    return sum(len(texts) for kind, texts in provider.embedded[since:] if kind == "passage")


def test_one_saved_entry_embeds_one_text_and_keeps_every_other_vector(lifecycle):
    # Measured 2026-09-22 on the served catalogue: one saved dataset sent all 8,375 texts to
    # the embedding model again, in 524 requests, although 8,374 of them had not changed.
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())
    before = len(provider.embedded)
    service.rebuild(token)
    service.close()
    assert _passages(provider, before) == 1
    status = service.index_status(token)
    assert status.covers_catalog and status.last_error is None
    assert installed and installed[-1] is service._dense
    new = service._dense.index
    assert new.snapshot_sha256 == status.catalog_sha256
    # The entries that did not change carry the vectors of the generation that was in use.
    kept = old.index.held_vectors(old.index.profile)
    moved = new.held_vectors(new.profile)
    assert set(kept) < set(moved)
    for series_id, (text, values) in kept.items():
        assert moved[series_id][0] == text
        assert max(abs(a - b) for a, b in zip(values, moved[series_id][1], strict=True)) < 1e-6


def test_a_changed_description_embeds_only_that_entry(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    target = REVIEWED.series[0].record.series_id
    knowledge.annotate(target, archived=False, aliases=(), note="Yeni açıklama.", author="test")
    before = len(provider.embedded)
    service.rebuild(token)
    service.close()
    assert _passages(provider, before) == 1
    assert "yeni aciklama" in provider.embedded[-1][1][0]  # the normalized index text
    assert service.index_status(token).covers_catalog


def test_reuse_counts_what_it_kept_and_embeds_the_rest(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())
    stats = embedding.EmbeddingStats()
    vectors = embedding.embed_catalog(
        provider,
        service._effective(),
        embedding.RUNTIME_QUERY_POLICY,
        origin="offline_fixture",
        stats=stats,
        reuse=old.index,
    )
    assert (stats.texts, stats.requests, stats.reused) == (1, 1, len(REVIEWED.series))
    assert len(vectors.vectors) == len(REVIEWED.series) + 1


@pytest.mark.parametrize(
    ("policy", "origin"),
    [("qwen3-plain-v1", "offline_fixture"), (embedding.RUNTIME_QUERY_POLICY, "kloudeks")],
)
def test_another_profile_reuses_no_vector(lifecycle, policy, origin):
    # A vector stands for its text under the profile it was made with, and nothing else.
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    assert old.index.held_vectors(embedding.profile_for(policy, origin)) == {}
    stats = embedding.EmbeddingStats()
    embedding.embed_catalog(provider, REVIEWED, policy, origin=origin, stats=stats, reuse=old.index)
    assert stats.reused == 0 and stats.texts == len(REVIEWED.series)


def test_a_vector_that_no_longer_matches_its_digest_is_embedded_again(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    target = REVIEWED.series[0].record.series_id
    tampered = replace(old.index, _vector_digests={**old.index._vector_digests, target: "0" * 64})
    stats = embedding.EmbeddingStats()
    embedding.embed_catalog(
        provider,
        REVIEWED,
        embedding.RUNTIME_QUERY_POLICY,
        origin="offline_fixture",
        stats=stats,
        reuse=tampered,
    )
    assert (stats.texts, stats.reused) == (1, len(REVIEWED.series) - 1)


def test_the_generation_in_use_answers_until_its_successor_is_installed(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    knowledge.save_dataset(dataset())
    started, release = threading.Event(), threading.Event()

    def slow(catalog, previous):
        started.set()
        assert release.wait(10)
        return build_stage(catalog, previous)

    service._rebuild = slow
    service.rebuild(token)
    assert started.wait(10)
    try:
        during = service.index_status(token)
        assert during.rebuilding and not during.covers_catalog
        assert service._dense is old and installed == []
        assert service.search(token, "konut kredisi stok").retrieval_mode == "hybrid"
    finally:
        release.set()
    service.close()
    after = service.index_status(token)
    assert not after.rebuilding and after.covers_catalog
    assert installed[-1] is service._dense and service._dense is not old
