"""Prepared publication identities resolve through real persisted workspace reads."""

from dataclasses import replace
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, proposal, seed_prepared
from test_series_inspection import SQL

from kkb_agent.agent import Workspace
from kkb_agent.api import prepared as module
from kkb_agent.api.prepared import PreparedError, PreparedRunner
from kkb_agent.api.projection import OutputRefused
from kkb_agent.api.service import SelectedResult
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted


def table_responses():
    return (
        proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}),
        "Tablo hazır.",
    )


@pytest.fixture
def published(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    provider = scripted(*table_responses(), *table_responses())
    runner = PreparedRunner(
        provider, root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid, tid = uuid4().hex, uuid4().hex
    answer = runner(sid, tid, "Konut kredisi tablosunu getir.")
    assert answer.result is not None
    selection = SelectedResult(tid, answer.result.result_ref, answer.result.version)
    return runner, provider, sid, selection


def test_latest_and_older_publications_resolve_without_model_calls(published):
    runner, provider, sid, first = published
    initial = runner.resolve_selection(sid, first)
    second_tid = uuid4().hex
    answer = runner(sid, second_tid, "Konut kredisi tablosunu tekrar getir.")
    assert answer.result is not None
    second = SelectedResult(second_tid, answer.result.result_ref, answer.result.version)
    calls = len(provider.seen)
    assert runner.resolve_selection(sid, second).name == "analiz_2"
    old = runner.resolve_selection(sid, first)
    assert old.name == "analiz_1" and old.artifact_id == initial.artifact_id
    assert old.value.model_dump_json() == initial.value.model_dump_json()
    assert old.value.digest() == first.version
    assert len(provider.seen) == calls
    # Returned values are independent snapshots, never cached mutable state.
    old.value.values[0].value = 999.0
    assert runner.resolve_selection(sid, first).value.digest() == first.version


@pytest.mark.parametrize("field", ["turn_id", "result_ref", "version"])
def test_forged_identity_is_refused(published, field):
    runner, provider, sid, selection = published
    forged = replace(selection, **{field: "0" * (64 if field == "version" else 32)})
    calls = len(provider.seen)
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(sid, forged)
    assert len(provider.seen) == calls
    assert runner.resolve_selection(sid, selection).name == "analiz_1"


@pytest.mark.parametrize("sid", ["../outside", "0" * 32])
def test_unknown_or_invalid_session_never_creates_storage(published, sid):
    runner, _, _, selection = published
    before = sorted(runner.run_root.iterdir())
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(sid, selection)
    assert sorted(runner.run_root.iterdir()) == before


def test_foreign_publication_with_identical_values_is_refused(published):
    runner, _, sid, selection = published
    foreign_sid, foreign_tid = uuid4().hex, uuid4().hex
    answer = runner(foreign_sid, foreign_tid, "Konut kredisi tablosunu getir.")
    assert answer.result is not None
    foreign = SelectedResult(foreign_tid, answer.result.result_ref, answer.result.version)
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(sid, foreign)
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(foreign_sid, selection)


@pytest.mark.parametrize(
    "change", ["stale", "rebound", "missing", "binding", "artifact", "payload", "malformed"]
)
def test_persisted_stale_changed_or_missing_result_is_refused(published, change):
    runner, provider, sid, selection = published
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        artifact = workspace.resolve("analiz_1")
        if change == "stale":
            # Publication dependency invalidation is a later slice; emulate its
            # persisted stale marker here to test mandatory read-side rejection.
            lake.connection.execute("UPDATE workspace_bindings SET stale = TRUE")
        elif change == "rebound":
            workspace.define(
                "analiz_1",
                artifact.kind,
                parameters={"changed": "yes"},
                value_ref=artifact.value_ref,
            )
        elif change == "binding":
            lake.connection.execute("DELETE FROM workspace_bindings")
        elif change == "artifact":
            lake.connection.execute(
                "UPDATE workspace_artifacts SET parameters = ?", ['{"changed":"yes"}']
            )
        elif change == "missing":
            lake.connection.execute("DELETE FROM workspace_results")
        else:
            value = workspace.value_of("analiz_1")
            value.values[0].value = 999.0
            payload = value.model_dump_json() if change == "payload" else "{}"
            lake.connection.execute("UPDATE workspace_results SET payload = ?", [payload])
    calls = len(provider.seen)
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(sid, selection)
    assert len(provider.seen) == calls


def test_failed_projection_cannot_create_selectable_receipt(published, monkeypatch):
    runner, _, sid, first = published
    tid = uuid4().hex

    def refuse(*args, **kwargs):
        raise OutputRefused("output_limit")

    monkeypatch.setattr(module, "project_answer", refuse)
    with pytest.raises(OutputRefused):
        runner(sid, tid, "Konut kredisi tablosunu tekrar getir.")
    with pytest.raises(PreparedError, match="^invalid_result$"):
        runner.resolve_selection(sid, replace(first, turn_id=tid))
    assert runner.resolve_selection(sid, first).value.digest() == first.version


def test_duplicate_published_turn_and_concurrent_read_are_refused(published):
    runner, provider, sid, selection = published
    calls = len(provider.seen)
    with pytest.raises(PreparedError, match="^duplicate_publication_turn$"):
        runner(sid, selection.turn_id, "Tekrar çalıştır.")
    assert runner._lock.acquire(blocking=False)
    try:
        with pytest.raises(PreparedError, match="^concurrent_runtime_refused$"):
            runner.resolve_selection(sid, selection)
    finally:
        runner._lock.release()
    assert len(provider.seen) == calls
    assert runner.resolve_selection(sid, selection).name == "analiz_1"
