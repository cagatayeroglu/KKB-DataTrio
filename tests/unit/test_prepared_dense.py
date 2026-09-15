"""DEC-142 dense catalog stage in the prepared runtime; offline vectors, zero live calls."""

import json
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, QUESTION, seed_prepared
from test_prepared_api import responses, set_config

from kkb_agent.api import __main__ as cli
from kkb_agent.api.prepared import PreparedError, PreparedRunner, manifest
from kkb_agent.catalog import embedding
from kkb_agent.catalog.hybrid import CatalogDenseStage
from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.llm import scripted

ROOT = CATALOG.parents[2]
POLICY = embedding.RUNTIME_QUERY_POLICY


class Recording:
    """Embedding double that records exact wire texts; completions pass through."""

    def __init__(self, inner, *, fail=False):
        self.inner, self.fail = inner, fail
        self.embedded: list[tuple[str, list[str]]] = []

    def complete(self, *args, **kwargs):
        return self.inner.complete(*args, **kwargs)

    def embed(self, texts, *, kind):
        self.embedded.append((kind, list(texts)))
        if self.fail:
            raise RuntimeError("private endpoint detail must not be copied")
        return self.inner.embed(texts, kind=kind)

    @property
    def seen(self):
        return self.inner.seen


def build_index(root, catalog, policy=POLICY, origin="kloudeks"):
    snapshot = load_reviewed_snapshot(catalog.read_bytes())
    fixture = scripted(embedding_dimension=4096)
    vectors = embedding.embed_catalog(fixture, snapshot, policy, origin="offline_fixture")
    # Test-only relabel: the CLI refuses any index whose profile is not the runtime one.
    relabelled = vectors.model_copy(update={"profile": embedding.profile_for(policy, origin)})
    build_catalog_index(root, snapshot, relabelled)
    return root


@pytest.fixture
def pool(tmp_path):
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    return root


@pytest.fixture
def index(tmp_path):
    return build_index(tmp_path.resolve() / "index", CATALOG)


def check(pool, *extra):
    return cli.main(["--check", "--prepared-root", str(pool), "--catalog", str(CATALOG), *extra])


def test_check_opens_the_runtime_index_without_any_provider(pool, index, monkeypatch, capsys):
    set_config(monkeypatch)
    monkeypatch.setenv("KLOUDEKS_EMBEDDING_MODEL", embedding.MODEL)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider in check"))
    before = manifest(pool)
    assert check(pool, "--catalog-index", str(index)) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["catalog_retrieval"] == "hybrid" and report["model_checked"] is False
    assert str(index) not in json.dumps(report) and manifest(pool) == before
    assert check(pool) == 0
    assert json.loads(capsys.readouterr().out)["catalog_retrieval"] == "lexical"


@pytest.mark.parametrize("problem", ["no_model", "other_model", "plain_policy", "fixture", "other"])
def test_mismatched_index_or_embedding_model_refuses_startup(
    pool, tmp_path, monkeypatch, capsys, problem
):
    set_config(monkeypatch)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider"))
    if problem != "no_model":
        model = "another/embedding-model" if problem == "other_model" else embedding.MODEL
        monkeypatch.setenv("KLOUDEKS_EMBEDDING_MODEL", model)
    root = tmp_path.resolve() / "wrong"
    if problem == "plain_policy":
        build_index(root, CATALOG, policy="qwen3-plain-v1")
    elif problem == "fixture":
        build_index(root, CATALOG, origin="offline_fixture")
    elif problem == "other":
        build_index(root, ROOT / "docs/catalog/prepared_v3.json")
    else:
        build_index(root, CATALOG)
    assert check(pool, "--catalog-index", str(root)) == 2
    out = capsys.readouterr().out
    assert json.loads(out) == {"ready": False, "error": "configuration_or_runtime_unavailable"}
    assert str(root) not in out and "canary" not in out


def test_missing_or_empty_index_generation_refuses_startup(pool, tmp_path, monkeypatch, capsys):
    set_config(monkeypatch)
    monkeypatch.setenv("KLOUDEKS_EMBEDDING_MODEL", embedding.MODEL)
    empty = tmp_path.resolve() / "empty-generation"
    empty.mkdir()
    for path in (tmp_path.resolve() / "missing-generation", empty):
        assert check(pool, "--catalog-index", str(path)) == 2
    assert "generation" not in capsys.readouterr().out


def runner_with(pool, tmp_path, index, provider):
    snapshot = load_reviewed_snapshot(CATALOG.read_bytes())
    stage = CatalogDenseStage(
        LocalCatalogIndex.open(index, snapshot, embedding.profile_for(POLICY, "kloudeks")),
        embedding.query_embedder(provider, POLICY, origin="kloudeks"),
    )
    return PreparedRunner(
        provider,
        pool,
        tmp_path.resolve() / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        catalog_dense=stage,
    )


def discovery(provider):
    """The planner continuation's untrusted discovery data, parsed rather than grepped."""
    data = next(
        json.loads(m.content)
        for m in provider.seen[1]
        if m.content.startswith('{"kind":"untrusted_catalog_discovery"')
    )
    (result,) = data["results"]
    return result


def test_prepared_turn_embeds_the_instructed_query_and_still_publishes(pool, tmp_path, index):
    provider = Recording(scripted(*responses(), embedding_dimension=4096))
    prepared = runner_with(pool, tmp_path, index, provider)
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "accepted" and answer.result is not None
    assert provider.embedded == [
        ("query", [f"Instruct: {embedding.TASK}\nQuery:toplam konut kredisi"])
    ]
    found = discovery(provider)
    assert found["retrieval_mode"] == "hybrid" and found["dense_status"] == "success"
    assert found["combination_policy"] == "reviewed-match-order-v1"
    assert found["input_policy_id"] == POLICY and found["clarification_required"]


def test_prepared_hybrid_refuses_planner_bypass_before_discovery(pool, tmp_path, index):
    initial, calculation, writer = responses()
    provider = Recording(
        scripted(calculation, initial, calculation, writer, embedding_dimension=4096)
    )
    prepared = runner_with(pool, tmp_path, index, provider)
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "accepted" and answer.result is not None
    assert len(provider.embedded) == 1 and len(provider.seen) == 4
    assert "catalog_search phase" in provider.seen[1][-1].content


def test_embedding_failure_degrades_to_lexical_without_leaking(pool, tmp_path, index):
    provider = Recording(scripted(*responses(), embedding_dimension=4096), fail=True)
    prepared = runner_with(pool, tmp_path, index, provider)
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "accepted" and len(provider.embedded) == 1
    assert "private endpoint detail" not in answer.model_dump_json()
    found = discovery(provider)
    assert found["retrieval_mode"] == "lexical_degraded"
    assert found["dense_failure"] == "embedding_failed"
    assert "private endpoint detail" not in json.dumps(found)


def test_runner_refuses_an_index_for_another_catalog(pool, tmp_path):
    other = build_index(tmp_path.resolve() / "v3", ROOT / "docs/catalog/prepared_v3.json")
    snapshot = load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v3.json").read_bytes())
    stage = CatalogDenseStage(
        LocalCatalogIndex.open(other, snapshot, embedding.profile_for(POLICY, "kloudeks")),
        lambda text: pytest.fail("never embedded"),
    )
    with pytest.raises(PreparedError, match="catalog_index_mismatch"):
        PreparedRunner(
            scripted(),
            pool,
            tmp_path.resolve() / "runtime",
            catalog_bytes=CATALOG.read_bytes(),
            catalog_dense=stage,
        )


def test_query_cache_is_bounded_and_evicts_the_oldest_text(monkeypatch):
    monkeypatch.setattr(embedding, "MAX_CACHED_QUERIES", 2)
    provider = Recording(scripted(embedding_dimension=4096))
    embed = embedding.query_embedder(provider, POLICY, origin="offline_fixture")
    for text in ("a", "b", "a", "c", "b", "a"):
        embed(text)
    assert [texts[0].rsplit(":", 1)[1] for _, texts in provider.embedded] == ["a", "b", "c", "a"]
