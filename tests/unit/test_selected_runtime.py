"""Selected-table HTTP/runtime integration with real tools and publication gates."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, NOW, proposal, seed_prepared
from test_prepared_api import BASE, wait_http
from test_series_inspection import CPI, SQL

from kkb_agent.agent import Session, Workspace
from kkb_agent.agent.loop import PlanningFailed
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService, SelectedResult, ServiceError
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import SourceRef
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm import scripted


def table():
    return {"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}


def add(source="analiz_1", series=CPI):
    return {
        "step_id": "b",
        "tool": "table_transform",
        "arguments": {
            "operation": "add_series",
            "source": source,
            "series_id": series,
        },
    }


def identity(tid, answer):
    assert answer.result is not None
    return SelectedResult(tid, answer.result.result_ref, answer.result.version)


def runtime(tmp_path, *responses):
    root = tmp_path / "prepared"
    seed_prepared(root)
    record = next(
        s.record
        for s in load_reviewed_snapshot(CATALOG.read_bytes()).series
        if s.record.series_id == CPI
    )
    with open_lakehouse(root) as lake:
        artifact = lake.record_artifact(
            b"synthetic cpi",
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
    provider = scripted(*responses)
    return PreparedRunner(
        provider, root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    ), provider


def first_turn(runner):
    sid, tid = uuid4().hex, uuid4().hex
    answer = runner(sid, tid, "Konut kredisi tablosunu getir.")
    return sid, identity(tid, answer), answer


def test_older_selection_repairs_wrong_source_and_records_dependency(tmp_path):
    runner, provider = runtime(
        tmp_path,
        proposal(table()),
        "Tablo hazır.",
        proposal(table()),
        "Yeni tablo hazır.",
        proposal(add("analiz_2")),
        proposal(add()),
        "Endeks eklendi.",
    )
    sid, selected, first = first_turn(runner)
    runner(sid, uuid4().hex, "Başka tablo getir.")
    answer = runner.selected(sid, uuid4().hex, "Seçili tabloya TÜFE ekle.", selected)
    assert answer.status.value == "accepted" and answer.result is not None
    assert [v.value for v in answer.result.cells[:3]] == [v.value for v in first.result.cells]
    assert [v.value for v in answer.result.cells[3:]] == [100.0, 110.0, 120.0]
    assert any(
        "selected_workspace_source" in m.content and "analiz_1" in m.content
        for m in provider.seen[4]
    )
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        ws = Workspace.open(lake.connection, sid)
        source = ws.resolve("analiz_1")
        assert ws.resolve("analiz_3").inputs == (source.artifact_id,)
        assert ws.value_of("analiz_1").digest() == selected.version
        # Real DAG invalidation, not a synthetic stale flag.
        ws.define(
            "analiz_1", source.kind, parameters={"changed": "yes"}, value_ref=source.value_ref
        )
        assert ws.is_stale("analiz_3") and not ws.is_stale("analiz_2")


def test_selected_discovery_continuation_preserves_source(tmp_path):
    discovery = {
        "step_id": "discover",
        "tool": "catalog_search",
        "arguments": {"query": "TÜFE tüketici fiyat endeksi"},
    }
    runner, provider = runtime(
        tmp_path,
        proposal(table()),
        "Tablo hazır.",
        proposal(discovery),
        proposal(add()),
        "Endeks eklendi.",
    )
    sid, selected, _ = first_turn(runner)
    answer = runner.selected(sid, uuid4().hex, "Seçili tabloya TÜFE ekle.", selected)
    assert answer.status.value == "accepted" and len(answer.result.cells) == 6
    assert all(
        any("selected_workspace_source" in m.content for m in provider.seen[i]) for i in (2, 3)
    )


@pytest.mark.parametrize("bad", [table(), add("analiz_2")])
def test_repeated_ungrounded_plan_never_publishes(tmp_path, bad):
    runner, provider = runtime(
        tmp_path, proposal(table()), "Tablo hazır.", proposal(bad), proposal(bad)
    )
    sid, selected, _ = first_turn(runner)
    with pytest.raises(PlanningFailed):
        runner.selected(sid, uuid4().hex, "Bu tabloyu kullan.", selected)
    assert len(provider.seen) == 4
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == ["analiz_1"]


def test_stale_selection_fails_before_model_and_failed_transform_preserves_source(tmp_path):
    runner, provider = runtime(
        tmp_path, proposal(table()), "Tablo hazır.", proposal(add(series="EVDS:TP.KFE.TR"))
    )
    sid, selected, first = first_turn(runner)
    answer = runner.selected(sid, uuid4().hex, "Seçili tabloya seri ekle.", selected)
    assert answer.result is None
    assert runner.resolve_selection(sid, selected).value.digest() == first.result.version
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        lake.connection.execute("UPDATE workspace_bindings SET stale=TRUE")
    calls = len(provider.seen)
    with pytest.raises(ServiceError) as failure:
        runner.selected(sid, uuid4().hex, "Seçili tabloyu kullan.", selected)
    assert failure.value.code == "invalid_result" and len(provider.seen) == calls


def test_source_change_during_writer_cannot_publish(tmp_path, monkeypatch):
    runner, _ = runtime(
        tmp_path, proposal(table()), "Tablo hazır.", proposal(add()), "Endeks eklendi."
    )
    sid, selected, _ = first_turn(runner)
    original = Session.draft

    def changed(self, question, available):
        source = self.selection.workspace.resolve(self.selection.name)
        self.selection.workspace.define(
            source.name, source.kind, parameters={"changed": "yes"}, value_ref=source.value_ref
        )
        return original(self, question, available)

    monkeypatch.setattr(Session, "draft", changed)
    with pytest.raises(ServiceError) as failure:
        runner.selected(sid, uuid4().hex, "Seçili tabloya TÜFE ekle.", selected)
    assert failure.value.code == "invalid_result"
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == ["analiz_1"]


def test_http_selected_followup_and_retry_use_actual_prepared_runner(tmp_path):
    runner, provider = runtime(
        tmp_path, proposal(table()), "Tablo hazır.", proposal(add()), "Endeks eklendi."
    )
    service = AnalysisService(runner, mode="scripted", selected_runner=runner.selected)
    with TestClient(create_app(service), base_url=BASE) as client:
        session = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": session["token"]}
        path = f"/v1/sessions/{session['session_id']}/turns"
        first = client.post(
            path, headers=headers, json={"request_id": uuid4().hex, "question": "Tabloyu getir."}
        ).json()
        done = wait_http(client, path + "/" + first["turn_id"], headers)
        payload = {
            "request_id": uuid4().hex,
            "question": "Seçili tabloya TÜFE ekle.",
            "selected_result_id": done["answer"]["result"]["result_ref"],
        }
        accepted = client.post(path, headers=headers, json=payload)
        assert accepted.status_code == 202
        follow = wait_http(client, path + "/" + accepted.json()["turn_id"], headers)
        assert follow["state"] == "completed" and len(follow["answer"]["result"]["cells"]) == 6
        assert (
            client.post(path, headers=headers, json=payload).json()["turn_id"] == follow["turn_id"]
        )
        assert len(provider.seen) == 4


def test_selected_add_then_relationship_binds_step_output_and_publishes_counts(tmp_path):
    from test_catalog_continuation import TOTAL

    relationship = {
        "step_id": "c",
        "tool": "change_detection",
        "depends_on": ["b"],
        "arguments": {
            "operation": "table_co_movement",
            "input_step": "b",
            "driver_column": CPI,
            "target_column": TOTAL,
            "driver_direction": "up",
            "target_direction": "up",
        },
    }
    runner, _ = runtime(
        tmp_path,
        proposal(table()),
        "Tablo hazır.",
        proposal(add(), relationship),
        "Karşılaştırma hazır.",
    )
    sid, selected, first = first_turn(runner)
    answer = runner.selected(sid, uuid4().hex, "TÜFE ekle ve artışları karşılaştır.", selected)
    assert answer.status.value == "accepted" and answer.result is not None
    assert [c.value for c in answer.result.cells[:3]] == [c.value for c in first.result.cells]
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        value = workspace.value_of("analiz_2")
        assert [v.value for v in value.values if v.label.startswith("table comparison ")] == [
            2,
            0,
            2,
            2,
            2,
            2,
        ]
        assert workspace.resolve("analiz_2").inputs == (workspace.resolve("analiz_1").artifact_id,)
