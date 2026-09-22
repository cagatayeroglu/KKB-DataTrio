"""M5-21: gate decisions and publication failures preserve trusted state."""

import json

import duckdb
import pytest
from pydantic import BaseModel

import kkb_agent.agent.loop as loop
from kkb_agent.agent import Session, ToolRegistry, ToolResult, ToolSpec, ToolStatus
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.agent.workspace import ArtifactKind, Workspace, WorkspaceError
from kkb_agent.core import (
    AnalyticalResult,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
)
from kkb_agent.database import apply_schema
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ProviderError

TABLES = ("workspace_results", "workspace_artifacts", "workspace_bindings", "workspace_history")


def snapshot(space):
    return {
        table: space.connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
        for table in TABLES
    }


def result(value=999.0, *, broken=False):
    return AnalyticalResult(
        result_id=f"fixture-{value}",
        kind=ResultKind.LEVEL,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=[ResultValue(label="amount", value=value, unit="TRY", scale=Scale.ONE)],
        evidence=ResultEvidence(
            input_refs=["missing-reference" if broken else "silver_observations"]
        ),
    )


@pytest.fixture
def space(monkeypatch):
    with duckdb.connect(":memory:") as connection:
        apply_schema(connection)
        from kkb_agent.agent import ExecutionContext
        from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool

        connection.execute(
            "INSERT INTO bronze_artifacts VALUES ('fixture','synthetic','memory','opaque:fixture',"
            "NULL,'application/json',2,'memory','2026-09-10')"
        )
        produced = {}
        for value in (100, 200, 300, 500, 600, 700, 999):
            series_id = f"amount_{value}"
            connection.execute(
                "INSERT INTO silver_series VALUES (?,?,'fixture','TRY','one','monthly',"
                "NULL,'stock','none','last',NULL)",
                [series_id, series_id],
            )
            connection.execute(
                "INSERT INTO silver_observations VALUES (?,'2026-06-01','2026-06-30',?)",
                [series_id, value],
            )
            produced[value] = (
                make_lakehouse_tool(connection)
                .run(
                    LakehouseArguments(
                        sql=(
                            "SELECT o.series_id, o.period_start, o.period_end, o.value,"
                            " s.unit, s.scale,"
                            " s.frequency, s.anchor, s.observation FROM silver_observations o"
                            " JOIN silver_series s ON s.series_id=o.series_id "
                            f"WHERE o.series_id='{series_id}'"
                        )
                    ),
                    ExecutionContext(question="publication fixture"),
                )
                .output.result
            )

        def supplied(value=999.0, *, broken=False):
            candidate = produced[value].model_copy(deep=True)
            if broken:
                candidate.evidence.input_refs = ["missing-reference"]
            return candidate

        monkeypatch.setattr(__name__ + ".result", supplied)
        workspace = Workspace.open(connection, "publication")
        workspace.record("table", ArtifactKind.VALUE, result(100.0))
        workspace.record("derived", ArtifactKind.VALUE, result(200.0), inputs=["table"])
        workspace.define("chart", ArtifactKind.CHART, inputs=["derived"])
        workspace.record("other", ArtifactKind.VALUE, result(500.0))
        yield workspace


class Args(BaseModel):
    pass


def session(candidate, draft="table: 999 TL.", *, later=None):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "lakehouse",
            "fixture",
            Args,
            lambda a, c: ToolResult(
                ToolStatus.SUCCESS,
                "s1",
                "lakehouse",
                output=candidate,
            ),
        )
    )
    steps = [{"step_id": "s1", "tool": "lakehouse", "arguments": {}}]
    if later is not None:

        def later_run(a, c):
            # The second fixture step really reads the first result; an order-
            # only edge would be two independent finals under the product gate.
            assert c.outputs["s1"] is candidate
            return ToolResult(
                later,
                "s2",
                "anomaly",
                error_category="fixture-failure" if later is ToolStatus.FAILURE else None,
            )

        registry.register(
            ToolSpec(
                "anomaly",
                "fixture",
                Args,
                later_run,
                required_steps=lambda a: ("s1",),
            )
        )
        steps.append({"step_id": "s2", "tool": "anomaly", "arguments": {}, "depends_on": ["s1"]})
    provider = scripted(json.dumps({"question": "fixture", "steps": steps}), draft)
    return Session(provider, registry)


@pytest.mark.parametrize(
    "case",
    [
        "bad_evidence",
        "wrong_number",
        "verifier_error",
        "failed_step",
        "partial_step",
        "uncited_bad_candidate",
        "planner_error",
        "noncomputed",
    ],
)
def test_unsuccessful_turn_leaves_all_workspace_tables_unchanged(space, monkeypatch, case):
    candidate = result(broken=case in ("bad_evidence", "uncited_bad_candidate"))
    draft = "table: 999 TL."
    expected = AnswerStatus.ABSTAINED
    later = None
    if case == "wrong_number":
        draft = "table: 777 TL."
    elif case == "uncited_bad_candidate":
        draft = "other: 500 TL."
        # Invalid current execution stops before synthesis. The writer no longer
        # spends a call answering from an unrelated old table instead.
    elif case in ("failed_step", "partial_step"):
        later = ToolStatus.FAILURE if case == "failed_step" else ToolStatus.PARTIAL
        # DEC-165: every figure binds, but a plan that did not run whole is QUALIFIED,
        # with the missing step named; publication stays refused as before.
        expected = AnswerStatus.QUALIFIED
    elif case == "noncomputed":
        candidate = AnalyticalResult(
            result_id="abstention",
            kind=ResultKind.LEVEL,
            status=ResultStatus.ABSTAINED,
            tool="lakehouse",
            reason="fixture",
        )
    turn = session(candidate, draft, later=later)
    if case == "verifier_error":

        def fail(*args, **kwargs):
            raise RuntimeError("fixture verifier failure")

        monkeypatch.setattr(loop, "gate_answer", fail)
    if case == "planner_error":
        turn.provider.responses[0] = ProviderError("fixture planner failure")
    before = snapshot(space)
    if case in ("planner_error", "verifier_error"):
        with pytest.raises((ProviderError, RuntimeError)):
            turn.answer("fixture", space.connection, workspace=space, remember="table")
    else:
        answer = turn.answer("fixture", space.connection, workspace=space, remember="table")
        assert answer.answer.status is expected
        if case == "uncited_bad_candidate":
            assert len(turn.provider.seen) == 1
    assert snapshot(space) == before
    assert space.value_of("table").values[0].value == 100.0
    assert space.stale() == set()


def test_verified_scalar_survives_writer_failure_without_changing_prior_tables(space):
    previous = {name: space.value_of(name).digest() for name in ("table", "derived", "other")}
    turn = session(result(), ProviderError("fixture provider failure"))
    answer = turn.answer("fixture", space.connection, workspace=space, remember="new")
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert space.value_of("new").values[0].value == 999.0
    assert "yazılı değerlendirme üretilemedi" in answer.answer.text
    assert "tablosu" not in answer.answer.text
    assert {name: space.value_of(name).digest() for name in previous} == previous
    assert space.stale() == set()


def test_a_writer_that_returns_nothing_does_not_cost_the_reader_the_verified_table(space):
    # An empty draft used to abstain and unpublish. Live 2026-09-21 the writer spent all its
    # tokens thinking; the table was computed and verified all the same. It is published,
    # and the prose says plainly that it is missing (DEC-186: the table is the tools').
    turn = session(result(), "   ")
    answer = turn.answer("fixture", space.connection, workspace=space, remember="table")
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert "yazılı değerlendirme üretilemedi" in answer.answer.text
    assert space.value_of("table").values[0].value == 999.0


def test_a_qualified_turn_still_publishes_the_verified_table(space):
    # The table is what the tools computed and the verifier re-read. A sentence withheld
    # from the prose about it (here an amount nothing computed) no longer unpublishes it.
    turn = session(result(), "table: 999 TL. Extra amount: 777 TL.")
    answer = turn.answer("fixture", space.connection, workspace=space, remember="table")
    assert answer.answer.status is AnswerStatus.QUALIFIED
    assert "777" not in answer.answer.text
    assert space.value_of("table").values[0].value == 999.0


def test_writer_and_verifier_get_preview_but_real_workspace_changes_only_after_gate(
    space, monkeypatch
):
    before = snapshot(space)
    original_gate = loop.gate_answer
    phases = []

    def draft(self, question, available, **_):
        phases.append("writer")
        assert snapshot(space) == before
        assert set(available) == {"table", "other"}
        assert available["table"].values[0].value == 999.0
        assert available["other"].values[0].value == 500.0
        return "table: 999 TL. other: 500 TL."

    def gate(text, available, *args, **kwargs):
        phases.append("gate")
        assert snapshot(space) == before
        assert set(available) == {"table", "other"}
        return original_gate(text, available, *args, **kwargs)

    original_publish = Workspace.publish

    def publish(self, preview):
        phases.append("publish")
        return original_publish(self, preview)

    monkeypatch.setattr(Session, "draft", draft)
    monkeypatch.setattr(loop, "gate_answer", gate)
    monkeypatch.setattr(Workspace, "publish", publish)
    old = space.resolve("table")
    answer = session(result()).answer(
        "fixture", space.connection, workspace=space, remember="table"
    )
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert phases == ["writer", "gate", "publish"]
    assert space.value_of("table").values[0].value == 999.0
    assert space.stale() == {"derived", "chart"}
    assert len(space.history("table")) == 2
    assert space.history("table")[0] == old
    assert space.read_result(old.value_ref).values[0].value == 100.0
    assert space.value_of("other").values[0].value == 500.0


def test_preview_and_repeat_publication_preserve_no_op(space):
    before = snapshot(space)
    preview = space.preview("table", result(100.0))
    assert set(preview.values()) == {"table", "derived", "other"}
    assert snapshot(space) == before
    space.publish(preview)
    space.publish(preview)
    assert snapshot(space) == before


def test_preview_is_an_immutable_snapshot_of_mutable_results(space):
    candidate = result()
    preview = space.preview("table", candidate)
    candidate.values[0].value = 777.0
    preview.values()["table"].values[0].value = 666.0
    assert preview.values()["table"].values[0].value == 999.0
    space.publish(preview)
    assert space.value_of("table").values[0].value == 999.0


@pytest.mark.parametrize("change", ["target", "other", "add", "stale", "change_back", "payload"])
def test_changed_workspace_rejects_old_preview_without_overwriting_new_state(space, change):
    preview = space.preview("table", result())
    if change == "target":
        space.record("table", ArtifactKind.VALUE, result(300.0))
    elif change == "other":
        space.record("other", ArtifactKind.VALUE, result(600.0))
    elif change == "add":
        space.record("new", ArtifactKind.VALUE, result(700.0))
    elif change == "stale":
        space._mark_stale({"other"})
    elif change == "change_back":
        space.record("other", ArtifactKind.VALUE, result(600.0))
        space.record("other", ArtifactKind.VALUE, result(500.0))
    else:
        space.connection.execute("UPDATE workspace_results SET result_id = 'changed'")
    newer = snapshot(space)
    with pytest.raises(WorkspaceError, match="changed since"):
        space.publish(preview)
    assert snapshot(space) == newer


def test_writer_side_workspace_change_is_not_overwritten(space, monkeypatch):
    def draft(self, question, available, **_):
        space.record("table", ArtifactKind.VALUE, result(300.0))
        return "table: 999 TL."

    monkeypatch.setattr(Session, "draft", draft)
    with pytest.raises(WorkspaceError, match="changed since"):
        session(result()).answer("fixture", space.connection, workspace=space, remember="table")
    assert space.value_of("table").values[0].value == 300.0
    assert len(space.history("table")) == 2


@pytest.mark.parametrize(
    "target", ["results", "artifacts", "bindings", "history", "stale", "commit"]
)
def test_sql_failure_rolls_back_entire_publication(space, target):
    statements = {
        "results": "INSERT OR IGNORE INTO workspace_results",
        "artifacts": "INSERT OR IGNORE INTO workspace_artifacts",
        "bindings": "INSERT OR REPLACE INTO workspace_bindings",
        "history": "INSERT OR REPLACE INTO workspace_history",
        "stale": "UPDATE workspace_bindings SET stale",
        "commit": "COMMIT",
    }
    before = snapshot(space)
    preview = space.preview("table", result())
    original = space.connection
    calls = []

    class FailingCursor:
        def __init__(self):
            self.inner = original.cursor()

        def execute(self, sql, *args):
            calls.append(sql)
            # Fail COMMIT before committing, all other writes after they happen.
            if sql == "COMMIT" and target == "commit":
                raise RuntimeError("fixture SQL failure")
            returned = self.inner.execute(sql, *args)
            if sql.startswith(statements[target]):
                raise RuntimeError("fixture SQL failure")
            return returned

        def close(self):
            self.inner.close()

    class Connection:
        def cursor(self):
            return FailingCursor()

    space.connection = Connection()
    try:
        with pytest.raises(RuntimeError, match="fixture SQL failure"):
            space.publish(preview)
    finally:
        space.connection = original
    assert "ROLLBACK" in calls
    assert snapshot(space) == before


def test_publication_does_not_commit_or_abort_callers_transaction(space):
    before = snapshot(space)
    space.connection.execute("BEGIN TRANSACTION")
    space.record("table", ArtifactKind.VALUE, result(300.0))
    pending = snapshot(space)
    preview = space.preview("table", result())
    with pytest.raises(WorkspaceError, match="changed since"):
        space.publish(preview)
    assert snapshot(space) == pending  # Caller transaction remains usable and uncommitted.
    observer = space.connection.cursor()
    try:
        assert observer.execute(
            "SELECT revision FROM workspace_bindings WHERE name='table'"
        ).fetchone() == (1,)
    finally:
        observer.close()
    space.connection.execute("ROLLBACK")
    assert snapshot(space) == before


def test_other_workspace_changes_do_not_invalidate_preview(space):
    preview = space.preview("table", result())
    other = Workspace(space.connection, "separate")
    other.record("table", ArtifactKind.VALUE, result(700.0))
    space.publish(preview)
    assert other.value_of("table").values[0].value == 700.0


@pytest.mark.parametrize("mode", ["no_workspace", "no_remember"])
def test_nonpublishing_session_modes_stay_unchanged(space, mode):
    before = snapshot(space)
    kwargs = (
        {"workspace": None, "remember": "table"} if mode == "no_workspace" else {"workspace": space}
    )
    draft = "table: 999 TL." if mode == "no_workspace" else "result: 999 TL."
    answer = session(result(), draft).answer("fixture", space.connection, **kwargs)
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert snapshot(space) == before


def test_same_value_with_changed_definition_still_invalidates_dependents(space):
    # Session historically records VALUE with no parameters/inputs. Same digest
    # does not imply a no-op when the old definition had parameters or inputs.
    space.define("selection", ArtifactKind.SOURCE)
    space.record(
        "table", ArtifactKind.VALUE, result(100.0), parameters={"mode": "old"}, inputs=["selection"]
    )
    space.refresh("derived", lambda artifact, inputs: result(200.0))
    space.refresh("chart")
    preview = space.preview("table", result(100.0))
    assert "derived" not in preview.values()
    space.publish(preview)
    assert space.stale() == {"derived", "chart"}
    assert space.resolve("table").parameters == {}
    assert space.resolve("table").inputs == ()


def test_same_stale_artifact_is_rebound_using_existing_define_semantics(space):
    space._mark_stale({"table", "derived", "chart"})
    preview = space.preview("table", result(100.0))
    assert set(preview.values()) == {"table", "other"}
    space.publish(preview)
    assert not space.is_stale("table")
    assert len(space.history("table")) == 2
    assert space.stale() == {"derived", "chart"}
    with pytest.raises(WorkspaceError, match="recomput"):
        space.refresh("derived")
    space.refresh("derived", lambda artifact, inputs: result(200.0))
    space.refresh("chart")
    assert not space.stale()


def test_new_name_adds_one_binding_and_preserves_existing_columns(space):
    before = space.resolve("table")
    preview = space.preview("new", result())
    assert set(preview.values()) == {"table", "derived", "other", "new"}
    space.publish(preview)
    assert len(space.history("new")) == 1
    assert space.resolve("table") == before
    assert not space.stale()


def test_candidate_verification_exception_after_gate_does_not_publish(space, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("candidate verification failed")

    monkeypatch.setattr(loop, "result_faults", fail)
    before = snapshot(space)
    with pytest.raises(RuntimeError, match="candidate verification failed"):
        session(result()).answer("fixture", space.connection, workspace=space, remember="table")
    assert snapshot(space) == before


def test_another_committed_change_during_publication_rolls_back_candidate(space, monkeypatch):
    preview = space.preview("table", result())
    original = Workspace.record

    def record(self, *args, **kwargs):
        artifact = original(self, *args, **kwargs)
        if self.connection is not space.connection:
            original(space, "other", ArtifactKind.VALUE, result(600.0))
        return artifact

    monkeypatch.setattr(Workspace, "record", record)
    with pytest.raises(WorkspaceError, match="changed during"):
        space.publish(preview)
    assert space.value_of("table").values[0].value == 100.0
    assert len(space.history("table")) == 1
    assert not space.stale()
    assert space.value_of("other").values[0].value == 600.0
    assert space.connection.execute(
        "SELECT count(*) FROM workspace_results WHERE result_digest = ?", [result().digest()]
    ).fetchone() == (0,)


def test_preview_cannot_publish_into_another_workspace(space):
    preview = space.preview("table", result())
    before = snapshot(space)
    with pytest.raises(WorkspaceError, match="another workspace"):
        Workspace(space.connection, "other").publish(preview)
    assert snapshot(space) == before
