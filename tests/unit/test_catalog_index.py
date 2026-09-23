"""Real local LanceDB with fixture vectors, not measured Qwen retrieval quality."""

import json
import math
from pathlib import Path

import pytest
from lancedb.db import LanceDBConnection
from pydantic import ValidationError

from kkb_agent.catalog.lance_index import (
    MANIFEST,
    CatalogIndexError,
    LocalCatalogIndex,
    build_catalog_index,
)
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.normalization import normalize_index_text
from kkb_agent.catalog.vectors import (
    DIMENSION,
    CatalogVectors,
    QueryVector,
    SeriesVector,
    VectorProfile,
    catalog_documents,
)

ROOT = Path(__file__).parents[2]


@pytest.fixture
def snapshot():
    return load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v2.json").read_bytes())


@pytest.fixture
def profile():
    return VectorProfile(
        model="kkbhackathon2026/Qwen3-Embedding-8B",
        dimension=4096,
        input_policy_id="test-fixture-no-model-call-v1",
        origin="offline_fixture",
    )


def direction(x=1.0, y=0.0):
    return (x, y, *([0.0] * (DIMENSION - 2)))


@pytest.fixture
def vectors(snapshot, profile):
    return CatalogVectors(
        snapshot_sha256=snapshot.content_sha256,
        profile=profile,
        vectors=tuple(
            SeriesVector(
                series_id=d.series_id, text_sha256=d.text_sha256, values=direction(1, i / 10)
            )
            for i, d in enumerate(catalog_documents(snapshot))
        ),
    )


@pytest.fixture
def built(tmp_path, snapshot, profile, vectors):
    root = tmp_path / "catalog-generation"
    build_catalog_index(root, snapshot, vectors)
    return root, LocalCatalogIndex.open(root, snapshot, profile)


def test_documents_are_reproducible_and_exclude_observation_payloads(snapshot):
    docs = catalog_documents(snapshot)
    assert docs == catalog_documents(snapshot)
    assert tuple(d.series_id for d in docs) == tuple(sorted(d.series_id for d in docs))
    assert len(docs) == 15
    for doc in docs:
        assert normalize_index_text(doc.text) == doc.text
        assert len(doc.text.encode()) <= 8192
        assert doc.text_sha256 and doc.concept_ids
        assert "276785" not in doc.text  # Real prepared value must not enter catalog text.
    unresolved = {"enflasyon orani", "yeni konut kredisi kullandirimi"}
    assert not any(alias in doc.text for alias in unresolved for doc in docs)


def test_persistent_search_matches_independent_cosine_oracle(built, snapshot, profile, vectors):
    root, _ = built
    reopened = LocalCatalogIndex.open(root, snapshot, profile)
    q = direction(1, 0.96)
    expected = sorted(
        (
            (
                v.series_id,
                1
                - sum(a * b for a, b in zip(q, v.values, strict=True))
                / math.hypot(*q)
                / math.hypot(*v.values),
            )
            for v in vectors.vectors
        ),
        key=lambda item: (item[1], item[0]),
    )[:10]
    actual = reopened.search(
        QueryVector(profile=profile, values=q),
        eligible_ids=frozenset(v.series_id for v in vectors.vectors),
    )
    assert [h.series_id for h in actual] == [sid for sid, _ in expected]
    assert [h.rank for h in actual] == list(range(1, 11))
    assert [h.cosine_distance for h in actual] == pytest.approx([d for _, d in expected], abs=2e-7)
    manifest = json.loads((root / MANIFEST).read_text())
    assert manifest["profile"]["origin"] == "offline_fixture"
    assert not manifest.keys() & {"values", "observations", "api_key", "url"}


def test_filter_precedes_top_k_and_empty_filter_performs_no_search(
    built, profile, vectors, monkeypatch
):
    _, index = built
    wanted = vectors.vectors[0].series_id
    q = QueryVector(profile=profile, values=direction(1, 1.4))
    hits = index.search(q, eligible_ids=frozenset({wanted}), limit=1)
    assert len(hits) == 1 and hits[0].series_id == wanted
    assert hits[0].cosine_distance > 0.4  # Globally distant but eligible, not lost after top-k.

    def fail(*args, **kwargs):
        raise AssertionError("empty selection must not query LanceDB")

    monkeypatch.setattr(type(index._table), "search", fail)
    assert index.search(q, eligible_ids=frozenset()) == ()


def test_equal_vectors_have_stable_id_ties_and_do_not_auto_select(
    tmp_path, snapshot, profile, vectors
):
    data = vectors.model_dump()
    for item in data["vectors"]:
        item["values"] = direction()
    same = CatalogVectors.model_validate(data)
    root = tmp_path / "equal"
    build_catalog_index(root, snapshot, same)
    index = LocalCatalogIndex.open(root, snapshot, profile)
    ids = frozenset(v.series_id for v in vectors.vectors)
    hits = index.search(
        QueryVector(profile=profile, values=direction()), eligible_ids=ids, limit=10
    )
    assert [h.series_id for h in hits] == sorted(ids)[:10]
    assert all(abs(h.cosine_distance) < 1e-6 for h in hits)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "0.1"])
def test_invalid_components_are_rejected_before_native_code(profile, bad):
    values = list(direction())
    values[5] = bad
    with pytest.raises((ValueError, ValidationError)):
        QueryVector(profile=profile, values=values)


@pytest.mark.parametrize("size", [0, 2, 4095, 4097])
def test_wrong_dimension_is_not_padded_or_truncated(profile, size):
    with pytest.raises(ValidationError):
        QueryVector(profile=profile, values=[1.0] * size)


def test_zero_vector_is_not_assigned_arbitrary_cosine(profile):
    with pytest.raises(ValidationError, match="zero vector"):
        QueryVector(profile=profile, values=[0.0] * 4096)


@pytest.mark.parametrize("field", ["missing", "extra", "duplicate", "snapshot", "text"])
def test_inconsistent_batch_never_creates_directory(tmp_path, snapshot, profile, vectors, field):
    data = vectors.model_dump(mode="json")
    if field == "missing":
        data["vectors"].pop()
    elif field == "extra":
        data["vectors"][0]["series_id"] = "EVDS:UNKNOWN; DROP TABLE catalog"
    elif field == "duplicate":
        data["vectors"][0] = data["vectors"][1]
    elif field == "snapshot":
        data["snapshot_sha256"] = "0" * 64
    else:
        data["vectors"][0]["text_sha256"] = "0" * 64
    root = tmp_path / "invalid"
    with pytest.raises((CatalogIndexError, ValidationError)):
        build_catalog_index(root, snapshot, CatalogVectors.model_validate(data))
    assert not root.exists()


def test_a_build_killed_before_its_manifest_does_not_block_the_next_one(
    tmp_path, snapshot, profile, vectors
):
    """The generation's path is its catalogue digest, so debris blocked it forever.

    A build that is killed between the directory and the manifest leaves
    something that can never be opened; every later build of that catalogue then
    refused the existing directory and an operator had to delete it by hand
    (finding F4-bt-9). The leftovers are renamed, never removed.
    """
    root = tmp_path / "generation"
    root.mkdir()
    (root / "half-written.lance").write_bytes(b"debris")

    build_catalog_index(root, snapshot, vectors)
    assert LocalCatalogIndex.open(root, snapshot, profile).snapshot_sha256 == (
        snapshot.content_sha256
    )
    kept = [path for path in tmp_path.iterdir() if path.name.startswith("generation.incomplete-")]
    assert len(kept) == 1 and (kept[0] / "half-written.lance").read_bytes() == b"debris"

    # A complete generation is still never overwritten.
    with pytest.raises(CatalogIndexError, match="NEW_LOCAL_DIRECTORY"):
        build_catalog_index(root, snapshot, vectors)


def test_old_snapshot_cannot_open_new_index(built, profile):
    root, _ = built
    old = load_reviewed_snapshot((ROOT / "docs/catalog/demo_v1.json").read_bytes())
    with pytest.raises(CatalogIndexError, match="CATALOG_DIGEST_MISMATCH"):
        LocalCatalogIndex.open(root, old, profile)


@pytest.mark.parametrize(
    "change", [{"input_policy_id": "different-policy"}, {"origin": "kloudeks"}]
)
def test_input_policy_and_fixture_origin_cannot_be_mixed(built, snapshot, profile, change):
    root, index = built
    changed = VectorProfile.model_validate({**profile.model_dump(), **change})
    with pytest.raises(CatalogIndexError, match="PROFILE_MISMATCH"):
        LocalCatalogIndex.open(root, snapshot, changed)
    with pytest.raises(CatalogIndexError, match="QUERY_PROFILE"):
        index.search(QueryVector(profile=changed, values=direction()), eligible_ids=frozenset())


@pytest.mark.parametrize(
    "policy", ["", "guess with spaces", "https://external.invalid", "x\nexecute"]
)
def test_policy_must_be_an_explicit_bounded_identifier(profile, policy):
    with pytest.raises(ValidationError):
        VectorProfile.model_validate({**profile.model_dump(), "input_policy_id": policy})


def test_existing_generation_is_never_overwritten(built, snapshot, vectors):
    root, _ = built
    original = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(CatalogIndexError, match="NEW_LOCAL_DIRECTORY"):
        build_catalog_index(root, snapshot, vectors)
    assert original == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_incomplete_native_write_does_not_publish_manifest(
    tmp_path, snapshot, profile, vectors, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("private native detail")

    monkeypatch.setattr(LanceDBConnection, "create_table", fail)
    root = tmp_path / "incomplete"
    with pytest.raises(CatalogIndexError, match="^INDEX_BUILD_INCOMPLETE$"):
        build_catalog_index(root, snapshot, vectors)
    assert not (root / MANIFEST).exists()
    with pytest.raises(CatalogIndexError, match="MANIFEST_INVALID"):
        LocalCatalogIndex.open(root, snapshot, profile)


@pytest.mark.parametrize("payload", ["{", "{}", "x" * 17000])
def test_missing_partial_or_oversized_manifest_is_refused(tmp_path, snapshot, profile, payload):
    (tmp_path / MANIFEST).write_text(payload)
    with pytest.raises(CatalogIndexError, match="MANIFEST_INVALID"):
        LocalCatalogIndex.open(tmp_path, snapshot, profile)


def test_changed_content_digest_is_refused(built, snapshot, profile):
    root, _ = built
    path = root / MANIFEST
    manifest = json.loads(path.read_text())
    manifest["rows_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(CatalogIndexError, match="CONTENT_INVALID"):
        LocalCatalogIndex.open(root, snapshot, profile)


@pytest.mark.parametrize(
    "root", ["db://remote/catalog", Path("relative"), Path("//server/share/catalog")]
)
def test_remote_or_nonlocal_roots_never_reach_connection(snapshot, vectors, root, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("connection must not be constructed")

    monkeypatch.setattr(LanceDBConnection, "__init__", fail)
    with pytest.raises(CatalogIndexError, match="LOCAL_ABSOLUTE_PATH"):
        build_catalog_index(root, snapshot, vectors)


@pytest.mark.parametrize("limit", [0, 11, True, 1.0])
def test_invalid_limits_are_refused(built, profile, limit):
    _, index = built
    with pytest.raises(CatalogIndexError, match="RESULT_LIMIT"):
        index.search(
            QueryVector(profile=profile, values=direction()), eligible_ids=frozenset(), limit=limit
        )


def test_unknown_identity_or_sql_text_is_not_interpolated(built, profile):
    _, index = built
    with pytest.raises(CatalogIndexError, match="ELIGIBILITY_INVALID"):
        index.search(
            QueryVector(profile=profile, values=direction()),
            eligible_ids=frozenset({"' OR 1=1 --"}),
        )
