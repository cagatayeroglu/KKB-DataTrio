"""Offline USER catalog generation lifecycle and fail-closed rebuild diagnostics."""

import json
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

    def build_stage(catalog):
        existing = open_stage(catalog)
        if existing is not None:
            return existing
        vectors = embedding.embed_catalog(
            provider, catalog, embedding.RUNTIME_QUERY_POLICY, origin="offline_fixture"
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


def test_user_save_rebuild_reopen_archive_and_version_are_digest_bound(lifecycle):
    service, knowledge, token, provider, old, build_stage, installed = lifecycle
    first = knowledge.save_dataset(dataset())
    stale = service.index_status(token)
    assert not stale.covers_catalog and stale.missing == (first.series_id,)
    lexical = service.search(token, "kart harcaması")
    assert lexical.retrieval_mode == "lexical_degraded"
    assert first.series_id in {hit.series_id for hit in lexical.hits}

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

    def changed_during_build(catalog):
        stage = build_stage(catalog)
        knowledge.save_dataset(dataset(observations=monthly([101.0, 110.0, 125.0])))
        return stage

    service._rebuild = changed_during_build
    service.rebuild(token)
    service.close()
    status = service.index_status(token)
    assert status.last_error == "concurrent_catalog_change"
    assert not status.covers_catalog and installed == [] and service._dense is old
    assert service.search(token, "kart harcaması").retrieval_mode == "lexical_degraded"


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

    def fail(_catalog):
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

    def build(catalog):
        stage = build_stage(catalog)
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
