"""Finite rehearsal budgets and actual prepared hybrid wiring; no live network."""

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import BaseModel
from test_catalog_continuation import CATALOG, QUESTION, seed_prepared
from test_prepared_api import responses, set_config
from test_prepared_dense import build_index, discovery

from kkb_agent.agent import loop
from kkb_agent.catalog import embedding
from kkb_agent.catalog.hybrid import CatalogDenseStage, search_hybrid_catalog
from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments
from kkb_agent.llm import KloudeksProvider, scripted
from kkb_agent.llm.provider import CapabilityUnavailable, Completion, ProviderError, TransportError

spec = importlib.util.spec_from_file_location(
    "manual_live_client", Path(__file__).parents[1] / "manual/live_client.py"
)
assert spec and spec.loader
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        httpx.HTTPTransport, "handle_request", lambda *a: pytest.fail("live network forbidden")
    )


class Fake:
    def __init__(self, error=None):
        self.chat = self.embeddings = 0
        self.error = error

    def complete(self, *args, **kwargs):
        self.chat += 1
        if self.error:
            raise self.error
        return Completion("PRIVATE answer", "model", finish_reason="PRIVATE finish")

    def embed(self, texts, *, kind):
        self.embeddings += 1
        if self.error:
            raise self.error
        return [[1.0] + [0.0] * 4095]

    def vision(self, *args):
        pytest.fail("vision must not reach provider")


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("chat,embed", [(0, 0), (16, 0), (True, 0), (1, -1), (1, 16), (1, True)])
def test_invalid_limits(chat, embed, tmp_path):
    with pytest.raises(ValueError):
        cli.RequestBudget(Fake(), chat, tmp_path / "ledger", embedding_limit=embed)


def test_chat_and_embedding_are_independent_and_content_free(tmp_path):
    path = tmp_path / "ledger"
    provider = Fake()
    budget = cli.RequestBudget(provider, 2, path, embedding_limit=1)
    budget.complete([], schema=BaseModel)
    budget.embed(["PRIVATE query"], kind="query")
    with pytest.raises(ProviderError):
        budget.embed(["PRIVATE query"], kind="query")
    budget.complete([])
    with pytest.raises(ProviderError):
        budget.complete([])
    assert (provider.chat, provider.embeddings, budget.used, budget.embedding_used) == (2, 1, 2, 1)
    logged = entries(path)
    assert [e["kind"] for e in logged if e["outcome"] == "started"] == [
        "structured",
        "embedding",
        "text",
    ]
    assert "PRIVATE" not in path.read_text()
    assert all(e["finish"] == "other" for e in logged if "finish" in e)


@pytest.mark.parametrize("kind", ["chat", "embedding"])
@pytest.mark.parametrize("error", [TransportError("PRIVATE"), RuntimeError("PRIVATE")])
def test_failed_dispatch_consumes_budget_and_records_safe_error(kind, error, tmp_path):
    path = tmp_path / "ledger"
    provider = Fake(error)
    budget = cli.RequestBudget(provider, 1, path, embedding_limit=1)
    call = budget.complete if kind == "chat" else lambda _: budget.embed(["x"], kind="query")
    with pytest.raises(type(error)):
        call([])
    with pytest.raises(ProviderError, match="budget exhausted"):
        call([])
    assert provider.chat + provider.embeddings == 1
    assert [e["outcome"] for e in entries(path)] == [
        "started",
        "provider_error" if isinstance(error, ProviderError) else "unexpected_error",
        "budget_refused",
    ]
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "texts,kind",
    [([], "query"), ([""], "query"), ([" "], "query"), (["a", "b"], "query"), (["a"], "passage")],
)
def test_only_single_nonempty_query_is_authorized(texts, kind, tmp_path):
    provider = Fake()
    budget = cli.RequestBudget(provider, 1, tmp_path / "ledger", embedding_limit=1)
    with pytest.raises(CapabilityUnavailable):
        budget.embed(texts, kind=kind)
    with pytest.raises(CapabilityUnavailable):
        budget.vision(b"PRIVATE", "PRIVATE")
    assert provider.embeddings == budget.embedding_used == 0


def test_embedding_disabled_by_default(tmp_path):
    provider = Fake()
    budget = cli.RequestBudget(provider, 1, tmp_path / "ledger")
    with pytest.raises(ProviderError):
        budget.embed(["query"], kind="query")
    assert provider.embeddings == 0


@pytest.mark.parametrize("kind", ["chat", "embedding"])
def test_concurrent_requests_cannot_overspend(kind, tmp_path):
    path = tmp_path / "ledger"
    provider = Fake()
    budget = cli.RequestBudget(provider, 3, path, embedding_limit=3)

    def attempt(_):
        try:
            if kind == "chat":
                budget.complete([])
            else:
                budget.embed(["query"], kind="query")
            return True
        except ProviderError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(20))) == 3
    assert provider.chat + provider.embeddings == 3
    assert len(entries(path)) == 23  # 3 starts + 3 outcomes + 17 refusals


def test_unwritable_ledger_prevents_dispatch(tmp_path):
    provider = Fake()
    budget = cli.RequestBudget(provider, 1, tmp_path)  # directory, not writable as a file
    with pytest.raises(OSError):
        budget.complete([])
    assert provider.chat == 0


def test_cached_query_does_not_consume_another_request(tmp_path):
    provider = Fake()
    budget = cli.RequestBudget(provider, 1, tmp_path / "ledger", embedding_limit=1)
    embed = embedding.query_embedder(budget, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks")
    assert embed("same") == embed("same")
    with pytest.raises(ProviderError):
        embed("different")
    assert provider.embeddings == budget.embedding_used == 1


def test_exhausted_embedding_budget_degrades_explicitly_without_another_dispatch(tmp_path):
    root = build_index(tmp_path / "index", CATALOG)
    snapshot = load_reviewed_snapshot(CATALOG.read_bytes())
    index = LocalCatalogIndex.open(
        root, snapshot, embedding.profile_for(embedding.RUNTIME_QUERY_POLICY, "kloudeks")
    )
    provider = Fake()
    budget = cli.RequestBudget(provider, 1, tmp_path / "ledger", embedding_limit=1)
    stage = CatalogDenseStage(
        index, embedding.query_embedder(budget, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks")
    )
    first = search_hybrid_catalog(snapshot, CatalogSearchArguments(query="konut"), stage)
    second = search_hybrid_catalog(snapshot, CatalogSearchArguments(query="konut kredisi"), stage)
    assert first.retrieval_mode == "hybrid"
    assert second.retrieval_mode == "lexical_degraded"
    assert second.dense_failure == "embedding_failed" and second.candidates
    assert provider.embeddings == 1
    assert entries(tmp_path / "ledger")[-1]["outcome"] == "budget_refused"


def test_gate_observer_restored_on_exception(tmp_path):
    original = loop.gate_answer
    with pytest.raises(RuntimeError), cli.record_gate_outcomes(tmp_path / "ledger"):
        assert loop.gate_answer is not original
        raise RuntimeError("stop")
    assert loop.gate_answer is original


def setup_cli(tmp_path, monkeypatch):
    set_config(monkeypatch)
    monkeypatch.setenv("KLOUDEKS_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("KLOUDEKS_EMBEDDING_MODEL", embedding.MODEL)
    root = tmp_path / "prepared"
    seed_prepared(root)
    return [
        "--prepared-root",
        str(root),
        "--catalog",
        str(CATALOG),
        "--state-root",
        str(tmp_path / "state"),
        "--max-model-requests",
        "3",
        "--enable-model-requests",
        "--ledger",
        str(tmp_path / "ledger"),
    ]


@pytest.mark.parametrize(
    "extra",
    [
        ["--max-model-requests", "0"],
        ["--max-embedding-requests", "16"],
        ["--max-embedding-requests", "1"],
        ["--enable-embedding-requests"],
        ["--catalog-index", "missing"],
        ["--catalog-index", "missing", "--max-embedding-requests", "1"],
        ["--enable-embedding-requests", "--max-embedding-requests", "1"],
        ["--port", "0"],
    ],
)
def test_invalid_cli_refuses_before_provider_or_ledger(tmp_path, monkeypatch, extra):
    args = setup_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider"))
    with pytest.raises(SystemExit) as exc:
        cli.main(args + extra)
    assert exc.value.code == 2
    assert not (tmp_path / "ledger").exists()


@pytest.mark.parametrize(
    "setting,value",
    [
        ("KLOUDEKS_MAX_ATTEMPTS", "2"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "901"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "nan"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "inf"),
    ],
)
def test_retry_and_timeout_settings_refuse_before_provider(tmp_path, monkeypatch, setting, value):
    args = setup_cli(tmp_path, monkeypatch)
    monkeypatch.setenv(setting, value)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider"))
    assert cli.main(args) == 2
    assert not (tmp_path / "ledger").exists()


@pytest.mark.parametrize("problem", ["missing", "fixture", "snapshot", "policy", "model"])
def test_wrong_index_refuses_before_provider_and_preserves_ledger(tmp_path, monkeypatch, problem):
    args = setup_cli(tmp_path, monkeypatch)
    path = tmp_path / "ledger"
    path.write_text("prior evidence")
    index = tmp_path / "index"
    if problem != "missing":
        catalog = (
            CATALOG
            if problem != "snapshot"
            else CATALOG.parents[2] / "docs/catalog/prepared_v3.json"
        )
        build_index(
            index,
            catalog,
            origin="offline_fixture" if problem == "fixture" else "kloudeks",
            policy="qwen3-plain-v1" if problem == "policy" else embedding.RUNTIME_QUERY_POLICY,
        )
    if problem == "model":
        monkeypatch.setenv("KLOUDEKS_EMBEDDING_MODEL", "wrong-model")
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider"))
    assert (
        cli.main(
            args
            + [
                "--catalog-index",
                str(index),
                "--max-embedding-requests",
                "1",
                "--enable-embedding-requests",
            ]
        )
        == 2
    )
    assert path.read_text() == "prior evidence"


def test_existing_ledger_is_not_truncated(tmp_path, monkeypatch):
    args = setup_cli(tmp_path, monkeypatch)
    path = tmp_path / "ledger"
    path.write_text("prior evidence")
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: pytest.fail("no provider"))
    assert cli.main(args) == 2
    assert path.read_text() == "prior evidence"


@pytest.mark.parametrize("hybrid", [False, True])
def test_launcher_runs_real_prepared_turn_and_restores_gate(tmp_path, monkeypatch, capsys, hybrid):
    args = setup_cli(tmp_path, monkeypatch)
    if hybrid:
        index = build_index(tmp_path / "index", CATALOG)
        args += [
            "--catalog-index",
            str(index),
            "--max-embedding-requests",
            "1",
            "--enable-embedding-requests",
        ]
    provider = scripted(*responses(), embedding_dimension=4096)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: nullcontext(provider))
    actual_runner = cli.PreparedRunner
    captured = {}

    def prepare(*a, **kw):
        runner = actual_runner(*a, **kw)
        captured["runner"] = runner
        return runner

    def serve(app, **kw):
        assert kw["host"] == "127.0.0.1" and kw["workers"] == 1
        assert kw["proxy_headers"] is False
        runner = captured["runner"]
        answer = runner(uuid4().hex, uuid4().hex, QUESTION)
        assert answer.status.value == "accepted" and answer.result is not None

    monkeypatch.setattr(cli, "PreparedRunner", prepare)
    monkeypatch.setattr(cli.uvicorn, "run", serve)
    original_gate = loop.gate_answer
    assert cli.main(args) == 0
    assert loop.gate_answer is original_gate
    report = json.loads(capsys.readouterr().out)
    assert report["catalog_retrieval"] == ("hybrid" if hybrid else "lexical")
    logged = entries(tmp_path / "ledger")
    assert logged[-1] == {"run": "stopped", "chat_used": 3, "embedding_used": int(hybrid)}
    assert any("gate" in e for e in logged)
    if hybrid:
        assert discovery(provider)["retrieval_mode"] == "hybrid"


@pytest.mark.parametrize("kind", ["chat", "embedding"])
def test_actual_transport_error_is_one_http_attempt(tmp_path, monkeypatch, kind):
    setup_cli(tmp_path, monkeypatch)
    sent = []

    def respond(request):
        sent.append(request.url.path)
        return httpx.Response(503, text="PRIVATE body")

    with KloudeksProvider(
        cli.literal_config(None), transport=httpx.MockTransport(respond)
    ) as inner:
        budget = cli.RequestBudget(inner, 1, tmp_path / "ledger", embedding_limit=1)
        for _ in range(2):
            with pytest.raises(ProviderError):
                if kind == "chat":
                    budget.complete([], schema=BaseModel)
                else:
                    budget.embed(["PRIVATE query"], kind="query")
    assert len(sent) == 1
    assert "PRIVATE" not in (tmp_path / "ledger").read_text()
