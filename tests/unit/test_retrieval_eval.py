"""M13-09 evaluation cases/metrics and M13-05 embedding policies; offline only."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from kkb_agent.catalog import embedding
from kkb_agent.catalog import retrieval_eval as evaluation
from kkb_agent.catalog.hybrid import CatalogDenseStage
from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ProviderError

ROOT = Path(__file__).parents[2]
CATALOG = ROOT / "docs/catalog/prepared_v3.json"
CASES = ROOT / "docs/catalog/retrieval_cases_v3.json"


@pytest.fixture(scope="module")
def snapshot():
    return load_reviewed_snapshot(CATALOG.read_bytes())


def raw_cases():
    return json.loads(CASES.read_text(encoding="utf-8"))


def test_reviewed_case_file_matches_the_catalog(snapshot):
    cases = evaluation.load_cases(CASES.read_bytes(), snapshot)
    splits = [case.split for case in cases.cases]
    assert len(cases.cases) == 44 and splits.count("holdout") == 18
    assert {case.category for case in cases.cases} >= {
        "alias_exact",
        "paraphrase_tr",
        "english",
        "unresolved",
        "out_of_scope",
        "archived",
    }


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["cases"][0].update(relevant_series_ids=["EVDS:TP.UNKNOWN"]),
        lambda d: d["cases"][2].update(primary_series_id="EVDS:TP.KFE.TR"),
        lambda d: d["cases"][0].update(expected_statuses=["NO_MATCH"]),
        lambda d: d["cases"][20].update(expected_statuses=[]),
        lambda d: d["cases"][1].update(case_id=d["cases"][0]["case_id"]),
        lambda d: d.update(cases=[c for c in d["cases"] if c["split"] == "development"]),
        lambda d: d.update(snapshot_sha256="0" * 64),
        lambda d: d["cases"][0].update(unexpected=True),
    ],
)
def test_inconsistent_or_unreviewed_cases_are_refused(snapshot, change):
    data = raw_cases()
    change(data)
    with pytest.raises((ValueError, ValidationError)):
        evaluation.load_cases(json.dumps(data).encode(), snapshot)


def test_metrics_follow_the_reviewed_relevance(snapshot):
    case = evaluation.RetrievalCase(
        case_id="X",
        split="development",
        category="alias_exact",
        query="q",
        relevant_series_ids=("a", "b"),
        primary_series_id="a",
    )
    metrics = evaluation._metrics(["x", "b", "y", "z", "q", "a"], case)
    assert metrics["hit_at_1"] is False and metrics["hit_at_5"] is True
    assert metrics["recall_at_5"] == 0.5 and metrics["recall_at_10"] == 1.0
    assert metrics["reciprocal_rank"] == 0.5 and metrics["primary_at_1"] is False
    assert evaluation._metrics([], case)["reciprocal_rank"] == 0.0


def test_lexical_evaluation_is_deterministic_and_leak_free(snapshot):
    cases = evaluation.load_cases(CASES.read_bytes(), snapshot)
    first = evaluation.evaluate(cases, snapshot, ["lexical"])
    second = evaluation.evaluate(cases, snapshot, ["lexical"])
    assert [o["ranked"] for o in first["cases"]] == [o["ranked"] for o in second["cases"]]
    summary = first["summary"]["all/lexical"]
    assert summary["cases"] == 44 and summary["scored"] == 39 and summary["archived_leaks"] == 0
    assert first["input_policy_id"] is None
    with pytest.raises(ValueError):
        evaluation.evaluate(cases, snapshot, ["dense"])


class Counting:
    def __init__(self, inner, *, count=None, dimension=None):
        self.inner, self.count, self.dimension = inner, count, dimension
        self.requests: list[tuple[str, list[str]]] = []

    def embed(self, texts, *, kind):
        self.requests.append((kind, list(texts)))
        vectors = self.inner.embed(texts, kind=kind)
        if self.count is not None:
            vectors = vectors[: self.count]
        if self.dimension is not None:
            vectors = [v[: self.dimension] for v in vectors]
        return vectors


def fixture_provider(**kwargs):
    return Counting(scripted(embedding_dimension=4096), **kwargs)


def test_catalog_embedding_batches_and_keeps_stable_identity(snapshot):
    provider = fixture_provider()
    stats = embedding.EmbeddingStats()
    vectors = embedding.embed_catalog(
        provider, snapshot, "qwen3-plain-v1", origin="offline_fixture", batch_size=16, stats=stats
    )
    assert [len(texts) for _, texts in provider.requests] == [16, 16, 5]
    assert {kind for kind, _ in provider.requests} == {"passage"}
    assert stats.requests == 3 and stats.texts == 37
    assert [v.series_id for v in vectors.vectors] == sorted(
        s.record.series_id for s in snapshot.series
    )
    assert vectors.profile.origin == "offline_fixture"


@pytest.mark.parametrize("change", [{"count": 15}, {"dimension": 1024}])
def test_short_or_wrong_dimension_responses_fail(snapshot, change):
    with pytest.raises(ProviderError):
        embedding.embed_catalog(
            fixture_provider(**change), snapshot, "qwen3-plain-v1", origin="offline_fixture"
        )


def test_policy_and_batch_bounds_are_explicit(snapshot):
    with pytest.raises(ValueError):
        embedding.policy("e5-query-prefix")
    for size in (0, 65, True):
        with pytest.raises(ValueError):
            embedding.embed_catalog(
                fixture_provider(),
                snapshot,
                "qwen3-plain-v1",
                origin="offline_fixture",
                batch_size=size,
            )


def test_instruct_policy_changes_queries_only(snapshot):
    provider = fixture_provider()
    embedding.embed_catalog(provider, snapshot, "qwen3-instruct-query-v1", origin="offline_fixture")
    assert not any(text.startswith("Instruct:") for _, texts in provider.requests for text in texts)
    embed = embedding.query_embedder(provider, "qwen3-instruct-query-v1", origin="offline_fixture")
    embed("konut kredisi faizi")
    embed("konut kredisi faizi")
    queries = [texts for kind, texts in provider.requests if kind == "query"]
    assert queries == [[f"Instruct: {embedding.TASK}\nQuery:konut kredisi faizi"]]


def test_fixture_index_supports_dense_and_hybrid_evaluation(snapshot, tmp_path):
    provider = fixture_provider()
    vectors = embedding.embed_catalog(
        provider, snapshot, "qwen3-plain-v1", origin="offline_fixture"
    )
    root = tmp_path.resolve() / "index"
    build_catalog_index(root, snapshot, vectors)
    profile = embedding.profile_for("qwen3-plain-v1", "offline_fixture")
    stats = embedding.EmbeddingStats()
    dense = CatalogDenseStage(
        LocalCatalogIndex.open(root, snapshot, profile),
        embedding.query_embedder(provider, "qwen3-plain-v1", origin="offline_fixture", stats=stats),
    )
    cases = evaluation.load_cases(CASES.read_bytes(), snapshot)
    report = evaluation.evaluate(cases, snapshot, ["lexical", "dense", "hybrid"], dense=dense)
    assert {o["mode"] for o in report["cases"]} == {"lexical", "dense", "hybrid"}
    assert report["embedding_origin"] == "offline_fixture"
    assert report["summary"]["all/hybrid"]["dense_failures"] == 0
    # Dense and hybrid share one cached embedding per distinct normalized query.
    assert stats.requests <= 44
    assert all(o["archived_leak"] is False for o in report["cases"])


def test_dense_cli_needs_explicit_enablement_before_any_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "kkb_agent.llm.KloudeksProvider", lambda *a: pytest.fail("no provider without enablement")
    )
    with pytest.raises(SystemExit):
        evaluation.main(
            [
                "--catalog",
                str(CATALOG),
                "--cases",
                str(CASES),
                "--index",
                str(tmp_path),
                "--out",
                str(tmp_path / "r.json"),
            ]
        )
    with pytest.raises(SystemExit):
        embedding.main(
            ["--catalog", str(CATALOG), "--root", str(tmp_path / "i"), "--policy", "qwen3-plain-v1"]
        )
