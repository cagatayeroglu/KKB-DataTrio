"""Actual prepared Session + HTTP integration, independent copies, zero live calls."""

import json
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, QUESTION, TOTAL, discover, proposal, seed_prepared

from kkb_agent.agent import Workspace
from kkb_agent.api import __main__ as cli
from kkb_agent.api import prepared as module
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import (
    PreparedError,
    PreparedRunner,
    inspect_pool,
    manifest,
)
from kkb_agent.api.service import AnalysisService
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import SourceRef
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role

BASE = "http://127.0.0.1:8000"


def calculate(operation="compare"):
    return {
        "step_id": "a",
        "tool": "change_detection",
        "arguments": {
            "operation": operation,
            "series_id": TOTAL,
            "start": "2026-04-30",
            "end": "2026-06-30",
        },
    }


def responses():
    return [
        proposal(discover()),
        proposal(calculate()),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    ]


@pytest.fixture
def pool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def runner(root, tmp_path, provider):
    return PreparedRunner(provider, root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes())


def wait_http(client, path, headers):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = client.get(path, headers=headers)
        assert result.status_code == 200, result.text
        if result.json()["state"] in ("completed", "failed"):
            return result.json()
        time.sleep(0.005)
    pytest.fail("prepared turn did not finish")


def test_readiness_is_read_only_and_distinguishes_catalog_from_observations(pool):
    before = manifest(pool)
    status = inspect_pool(pool, load_reviewed_snapshot(CATALOG.read_bytes()))
    assert status.prepared_identities == 1 and status.catalog_identities == 15
    assert "toplam (TP ve YP birlikte)" in status.series[0].title
    assert status.observation_rows == status.series[0].nonnull_observations == 3
    assert str(status.series[0].first_period) == "2026-04-01"
    assert status.pool_bytes == sum(size for size, _ in before.values())
    assert status.live_model_checked is False and manifest(pool) == before
    assert str(pool) not in status.model_dump_json()


def test_http_runtime_uses_real_gate_and_isolates_two_sessions(pool, tmp_path):
    before = manifest(pool)
    provider = scripted(*responses(), *responses())
    prepared = runner(pool, tmp_path, provider)
    seed_before = manifest(prepared.seed)
    service = AnalysisService(prepared, mode="scripted")
    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        assert not provider.seen
        status = client.get("/v1/dataset").json()
        assert status["prepared_identities"] == 1 and status["observation_rows"] == 3
        outputs = []
        sessions = []
        for _ in range(2):
            session = client.post("/v1/sessions", json={}).json()
            sessions.append(session)
            headers = {"X-KKB-Session-Token": session["token"]}
            path = f"/v1/sessions/{session['session_id']}/turns"
            request = {"request_id": uuid4().hex, "question": QUESTION}
            admitted = client.post(path, json=request, headers=headers).json()
            done = wait_http(client, path + "/" + admitted["turn_id"], headers)
            assert done["state"] == "completed", done
            assert done["answer"]["status"] == "accepted" and done["answer"]["result"]["published"]
            assert "50" in done["answer"]["text"]
            assert (
                client.post(path, json=request, headers=headers).json()["turn_id"]
                == admitted["turn_id"]
            )
            outputs.append(done)
        assert (
            outputs[0]["answer"]["result"]["result_ref"]
            != outputs[1]["answer"]["result"]["result_ref"]
        )
        assert len(provider.seen) == 6
    for session in sessions:
        target = prepared.run_root / session["session_id"] / "lake"
        with open_lakehouse(target) as lake:
            assert Workspace.open(lake.connection, session["session_id"]).names() == ["analiz_1"]
            assert (
                Workspace.open(
                    lake.connection,
                    sessions[1]["session_id"]
                    if session == sessions[0]
                    else sessions[0]["session_id"],
                ).names()
                == []
            )
    assert manifest(pool) == before and manifest(prepared.seed) == seed_before


def test_followup_reads_prior_workspace_in_same_session(pool, tmp_path):
    provider = scripted(
        *responses(),
        proposal(calculate()),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex
    first = prepared(sid, uuid4().hex, QUESTION)
    first_json = first.model_dump_json()
    first_call_count = len(provider.seen)
    # A genuine reference to the prior table must see its published identity;
    # repeating the original independent question does not request that context.
    second = prepared(
        sid,
        uuid4().hex,
        "Bu tablodaki konut kredisi stoğu Nisan-Haziran 2026 arasında ne kadar değişti?",
    )
    assert first_json == first.model_dump_json()
    published_contexts = [
        message.content
        for call in provider.seen[first_call_count:]
        for message in call
        if message.role is Role.SYSTEM
        and message.content.startswith("Results published in earlier turns")
    ]
    assert len(published_contexts) == 1
    assert "analiz_1: produced by" in published_contexts[0]
    assert "coverage 2026-04-01..2026-06-30" in published_contexts[0]
    assert "column labels:" in published_contexts[0]
    assert QUESTION not in published_contexts[0]
    assert len(published_contexts[0]) < 1200
    # The same unqualified numeric claim now matches two distinct result
    # identities. Preserve the existing gate's refusal, not a weaker API matcher.
    assert second.status.value == "abstained" and second.result is None
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        assert workspace.value_of("analiz_1").digest() == first.result.version


def test_real_table_followup_adds_index_and_preserves_every_original_cell(pool, tmp_path):
    from test_catalog_continuation import NOW
    from test_series_inspection import CPI, SQL

    record = next(
        s.record
        for s in load_reviewed_snapshot(CATALOG.read_bytes()).series
        if s.record.series_id == CPI
    )
    with open_lakehouse(pool) as lake:
        artifact = lake.record_artifact(
            b"synthetic cpi 100 110 120",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=NOW,
        )
        lake.register_series(
            CPI,
            title="Synthetic CPI",
            artifact_id=artifact.artifact_id,
            semantics=SeriesSemantics(
                unit=record.unit,
                scale=record.scale,
                frequency=record.frequency,
                observation=record.stock_flow,
                cumulative=record.cumulative,
                aggregation=record.aggregation.default,
                base_year=record.base_year,
            ),
        )
        lake.append_observations(
            CPI,
            [
                Observation(date(2026, m, 1), date(2026, m, last), value)
                for m, last, value in [(4, 30, 100.0), (5, 31, 110.0), (6, 30, 120.0)]
            ],
        )
    provider = scripted(
        proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}),
        "Tablo hazır.",
        proposal(
            {
                "step_id": "b",
                "tool": "table_transform",
                "arguments": {
                    "operation": "add_series",
                    "source": "analiz_1",
                    "series_id": CPI,
                },
            }
        ),
        "Tabloya endeks eklendi.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex
    first = prepared(sid, uuid4().hex, "Konut kredisi tablosunu getir.")
    assert first.status.value == "accepted", first
    second = prepared(sid, uuid4().hex, "Önceki tabloyu koruyup TÜFE ekle.")
    assert second.status.value == "accepted", second
    assert len(first.result.cells) == 3 and len(second.result.cells) == 6
    assert [c.value for c in second.result.cells[:3]] == [100.0, 120.0, 150.0]
    assert [c.value for c in second.result.cells[3:]] == [100.0, 110.0, 120.0]
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        assert workspace.names() == ["analiz_1", "analiz_2"]
        assert workspace.value_of("analiz_1").digest() == first.result.version


def test_unprepared_catalog_candidate_refuses_without_fetching(pool, tmp_path):
    bad = calculate()
    bad["arguments"]["series_id"] = "EVDS:TP.KFE.TR"
    provider = scripted(proposal(bad))
    prepared = runner(pool, tmp_path, provider)
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "abstained" and answer.result is None
    # DEC-167: the tool's refusal is fed back once. The exhausted script stands in for a
    # provider that cannot answer the repair, and the refusal stands - still nothing fetched.
    assert len(provider.seen) == 2


def test_source_changes_after_startup_do_not_change_immutable_runtime_seed(pool, tmp_path):
    provider = scripted(*responses())
    prepared = runner(pool, tmp_path, provider)
    with open_lakehouse(pool) as lake:
        lake.connection.execute("UPDATE silver_observations SET value=999")
    answer = prepared(uuid4().hex, uuid4().hex, QUESTION)
    assert answer.status.value == "accepted" and "50" in answer.text
    assert (
        prepared.status.snapshot_id
        != inspect_pool(pool, load_reviewed_snapshot(CATALOG.read_bytes())).snapshot_id
    )


def test_changed_seed_and_failed_copy_cannot_create_empty_database_on_retry(pool, tmp_path):
    provider = scripted()
    prepared = runner(pool, tmp_path, provider)
    with open_lakehouse(prepared.seed) as lake:
        lake.connection.execute("UPDATE silver_observations SET value=999")
    sid = uuid4().hex
    for _ in range(2):
        with pytest.raises(PreparedError, match="prepared_copy_refused"):
            prepared(sid, uuid4().hex, QUESTION)
    assert not provider.seen
    assert not (prepared.run_root / sid / "lake" / "kkb.duckdb").exists()


@pytest.mark.parametrize("change", ["unit", "base", "unknown", "workspace"])
def test_wrong_or_contaminated_prepared_pool_fails_before_provider(pool, tmp_path, change):
    with open_lakehouse(pool) as lake:
        if change == "unit":
            lake.connection.execute("UPDATE silver_series SET unit='USD'")
        elif change == "base":
            lake.connection.execute("UPDATE silver_series SET frequency='weekly'")
        elif change == "unknown":
            lake.connection.execute("DELETE FROM silver_observations")
            lake.connection.execute("UPDATE silver_series SET series_id='unknown'")
        else:
            workspace = Workspace.open(lake.connection, "other-user")
            from kkb_agent.agent.workspace import ArtifactKind

            workspace.define("other", ArtifactKind.VALUE, value_ref="not-private-data")
    provider = scripted()
    with pytest.raises(PreparedError):
        runner(pool, tmp_path, provider)
    assert not provider.seen


@pytest.mark.parametrize("name", [".env", "kkb.duckdb.wal", "private.txt"])
def test_unexpected_root_files_refused(pool, name):
    (pool / name).write_text("private-canary", encoding="utf-8")
    with pytest.raises(PreparedError, match="unexpected_prepared_file"):
        manifest(pool)


def test_file_and_byte_caps_are_enforced_before_copy(pool, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "MAX_POOL_BYTES", 1)
    with pytest.raises(PreparedError, match="prepared_pool_limit"):
        runner(pool, tmp_path, scripted())
    monkeypatch.setattr(module, "MAX_POOL_BYTES", 1024**3)
    monkeypatch.setattr(module, "MAX_POOL_FILES", 1)
    with pytest.raises(PreparedError, match="prepared_pool_limit"):
        manifest(pool)


def test_relative_network_and_overlapping_roots_refused(pool, tmp_path):
    with pytest.raises(PreparedError):
        manifest(Path("relative"))
    with pytest.raises(PreparedError):
        manifest(Path("//server/share"))
    with pytest.raises(PreparedError, match="overlapping_roots_refused"):
        PreparedRunner(scripted(), pool, pool / "runtime", catalog_bytes=CATALOG.read_bytes())
    with pytest.raises(PreparedError, match="overlapping_roots_refused"):
        PreparedRunner(scripted(), pool, tmp_path, catalog_bytes=CATALOG.read_bytes())


def test_linked_prepared_file_is_rejected(pool, tmp_path):
    target = tmp_path / "outside"
    target.write_text("outside", encoding="utf-8")
    link = pool / "bronze" / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(PreparedError, match="linked_path_refused"):
        manifest(pool)


@pytest.mark.parametrize("sid", ["../outside", "a" * 31, "a" * 33, "g" * 32])
def test_runtime_ids_do_not_become_caller_paths(pool, tmp_path, sid):
    provider = scripted()
    prepared = runner(pool, tmp_path, provider)
    with pytest.raises(PreparedError, match="invalid_runtime_identity"):
        prepared(sid, uuid4().hex, QUESTION)
    assert not provider.seen


def set_config(monkeypatch):
    for key, value in {
        "KLOUDEKS_BASE_URL": "https://mia.csp.kloudeks.com/v1",
        "KLOUDEKS_API_KEY": "test-only-canary-not-a-real-key",
        "KLOUDEKS_PLANNER_MODEL": "approved-test-model",
        "KLOUDEKS_ROUTER_MODEL": "approved-test-model",
        "KLOUDEKS_REQUEST_TIMEOUT": "120",
        "KLOUDEKS_MAX_ATTEMPTS": "3",
    }.items():
        monkeypatch.setenv(key, value)


def test_check_command_never_constructs_provider_or_listener(pool, monkeypatch, capsys):
    set_config(monkeypatch)
    monkeypatch.setattr(
        cli, "KloudeksProvider", lambda *a: pytest.fail("provider should not be built")
    )
    monkeypatch.setattr(
        cli.uvicorn, "run", lambda *a, **k: pytest.fail("listener should not start")
    )
    before = manifest(pool)
    assert cli.main(["--check", "--prepared-root", str(pool), "--catalog", str(CATALOG)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] and not report["model_checked"]
    assert "canary" not in json.dumps(report) and str(pool) not in json.dumps(report)
    assert manifest(pool) == before


@pytest.mark.parametrize(
    "setting,value",
    [
        ("KLOUDEKS_BASE_URL", "https://api.openai.com/v1"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "nan"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "99999"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "1801"),
        ("KLOUDEKS_REQUEST_TIMEOUT", "0"),
        ("KLOUDEKS_MAX_ATTEMPTS", "99"),
        ("KLOUDEKS_API_KEY", ""),
    ],
)
def test_bad_settings_are_redacted_and_never_start_service(
    pool, monkeypatch, capsys, setting, value
):
    set_config(monkeypatch)
    monkeypatch.setenv(setting, value)
    assert cli.main(["--check", "--prepared-root", str(pool), "--catalog", str(CATALOG)]) == 2
    report = capsys.readouterr().out
    assert json.loads(report) == {"ready": False, "error": "configuration_or_runtime_unavailable"}
    assert str(pool) not in report and "canary" not in report


@pytest.mark.parametrize("seconds", ["600", "1800"])
def test_measured_slow_completion_timeout_is_accepted_without_a_model_call(
    pool, monkeypatch, capsys, seconds
):
    set_config(monkeypatch)
    monkeypatch.setenv("KLOUDEKS_REQUEST_TIMEOUT", seconds)
    monkeypatch.setattr(
        cli, "KloudeksProvider", lambda *a: pytest.fail("provider should not be built")
    )
    assert cli.main(["--check", "--prepared-root", str(pool), "--catalog", str(CATALOG)]) == 0
    assert json.loads(capsys.readouterr().out)["model_checked"] is False


def test_serving_requires_explicit_enablement_before_reading_configuration(pool):
    with pytest.raises(SystemExit):
        cli.main(["--serve", "--prepared-root", str(pool), "--catalog", str(CATALOG)])


def test_launcher_is_loopback_only_and_closes_before_provider(pool, tmp_path, monkeypatch, capsys):
    set_config(monkeypatch)
    entered = []

    class Provider:
        def __enter__(self):
            entered.append("provider_open")
            return scripted()

        def __exit__(self, *args):
            entered.append("provider_closed")

    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: Provider())

    def serve(app, **kwargs):
        assert kwargs["host"] == "127.0.0.1" and kwargs["workers"] == 1
        assert kwargs["access_log"] is False and kwargs["proxy_headers"] is False
        with TestClient(app, base_url=BASE) as client:
            assert client.get("/v1/dataset").json()["observation_rows"] == 3
        entered.append("server_closed")

    monkeypatch.setattr(cli.uvicorn, "run", serve)
    assert (
        cli.main(
            [
                "--serve",
                "--enable-model-requests",
                "--prepared-root",
                str(pool),
                "--catalog",
                str(CATALOG),
                "--state-root",
                str(tmp_path / "runtime"),
            ]
        )
        == 0
    )
    assert entered == ["provider_open", "server_closed", "provider_closed"]
    assert "canary" not in capsys.readouterr().out


def test_missing_dataset_contract_is_explicit():
    service = AnalysisService(
        lambda sid, tid, text, *, is_continuation: pytest.fail("not run"),
        mode="scripted",
    )
    with TestClient(create_app(service), base_url=BASE) as client:
        response = client.get("/v1/dataset")
        assert response.status_code == 503 and response.json()["error"] == "unavailable"


def test_runner_rejects_concurrent_connection_ownership(pool, tmp_path):
    provider = scripted()
    prepared = runner(pool, tmp_path, provider)
    prepared._lock.acquire()
    try:
        with pytest.raises(PreparedError, match="concurrent_runtime_refused"):
            prepared(uuid4().hex, uuid4().hex, QUESTION)
    finally:
        prepared._lock.release()
    assert not provider.seen


def test_empty_directory_nesting_is_bounded(pool):
    (pool / "silver" / Path(*(["nested"] * 13))).mkdir(parents=True)
    with pytest.raises(PreparedError, match="prepared_pool_limit"):
        manifest(pool)


def test_dataset_endpoint_returns_frozen_startup_metadata(pool, tmp_path):
    prepared = runner(pool, tmp_path, scripted())
    service = AnalysisService(prepared, mode="scripted")
    app = create_app(service, prepared=prepared.status)
    prepared.status.observation_rows = 999
    with TestClient(app, base_url=BASE) as client:
        assert client.get("/v1/dataset").json()["observation_rows"] == 3


def test_literal_env_file_never_executes_or_mutates_process_environment(tmp_path, monkeypatch):
    import os

    set_config(monkeypatch)
    path = tmp_path / ".env"
    marker = tmp_path / "must-not-exist"
    literal = '$(touch "' + str(marker) + '")'
    path.write_text(
        "KLOUDEKS_API_KEY='" + literal + "'\nKLOUDEKS_REQUEST_TIMEOUT=60 # seconds\n",
        encoding="utf-8",
    )
    before = dict(os.environ)
    config = cli.literal_config(path)
    assert config.credential.get_secret_value() == literal and config.request_timeout == 60
    assert not marker.exists() and dict(os.environ) == before


@pytest.mark.parametrize(
    "content",
    [
        "KLOUDEKS_API_KEY=a\nKLOUDEKS_API_KEY=b",
        "KLOUDEKS_API_KEY='unclosed",
        "KLOUDEKS_BAD_SETTING missing_equals",
        "x" * (64 * 1024 + 1),
    ],
    ids=["duplicate", "quote", "malformed", "oversize"],
)
def test_bad_env_file_is_refused_without_exposing_values(tmp_path, monkeypatch, content):
    set_config(monkeypatch)
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        cli.literal_config(path)
    assert content not in str(error.value)
