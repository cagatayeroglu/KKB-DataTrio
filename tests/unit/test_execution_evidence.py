"""M8-21: only actual producer execution can support a numeric result."""

from datetime import date

import duckdb
import pytest

from kkb_agent.agent import AnswerStatus, ExecutionContext, gate_answer
from kkb_agent.core import (
    AnalyticalResult,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
)
from kkb_agent.database import apply_schema
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.tools import ChangeDetectionArguments, make_change_detection_tool


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as db:
        apply_schema(db)
        yield db


def unproven(reference="silver_observations", *, period=None):
    return AnalyticalResult(
        result_id="manual",
        kind=ResultKind.LEVEL,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=[
            ResultValue(
                label="invented", value=987654.0, unit="TRY", scale=Scale.ONE, period=period
            )
        ],
        evidence=ResultEvidence(input_refs=[reference]),
    )


@pytest.mark.parametrize("reference", ["silver_observations", "lineage_nodes", "missing", "node"])
@pytest.mark.parametrize("period", [None, Period(start=date(2026, 6, 1), end=date(2026, 6, 30))])
def test_reference_existence_never_proves_a_number(connection, reference, period):
    if reference == "node":
        reference = Lineage(connection).record(NodeKind.SOURCE_FILE, "unrelated source")
    result = unproven(reference, period=period)
    answer = gate_answer("Değer 987654 TL.", result, connection)
    assert answer.status is AnswerStatus.ABSTAINED
    assert not answer.presentable


@pytest.fixture
def comparison(connection):
    connection.execute(
        "INSERT INTO bronze_artifacts VALUES ('fixture','synthetic','memory','opaque:fixture',NULL,"
        "'application/json',2,'memory','2026-09-10')"
    )
    connection.execute(
        "INSERT INTO silver_series VALUES ('housing','Synthetic housing','fixture','TRY','million',"
        "'monthly',NULL,'stock','none','last',NULL)"
    )
    connection.execute(
        "INSERT INTO silver_observations VALUES ('housing','2026-05-01','2026-05-31',782918),"
        "('housing','2026-06-01','2026-06-30',801438)"
    )
    return (
        make_change_detection_tool(connection, lineage=Lineage(connection))
        .run(
            ChangeDetectionArguments(
                operation="compare",
                series_id="housing",
                start=date(2026, 5, 31),
                end=date(2026, 6, 30),
            ),
            ExecutionContext(question="synthetic comparison"),
        )
        .output
    )


def test_real_comparison_remains_accepted(connection, comparison):
    assert (
        gate_answer("Değişim 18.520 milyon TL.", comparison, connection).status
        is AnswerStatus.ACCEPTED
    )


def test_modified_comparison_cannot_reuse_lineage(connection, comparison):
    payload = comparison.model_dump()
    next(v for v in payload["values"] if v["value"] == 18520.0)["value"] = 987654.0
    changed = AnalyticalResult.model_validate(payload)
    assert changed.digest() != comparison.digest()
    assert changed.evidence.lineage_node == comparison.evidence.lineage_node
    assert (
        gate_answer("Değişim 987654 milyon TL.", changed, connection).status
        is AnswerStatus.ABSTAINED
    )


@pytest.mark.parametrize(
    "field",
    [
        "value",
        "label",
        "period",
        "unit",
        "scale",
        "method",
        "parameters",
        "input_refs",
        "tool",
        "run_id",
        "step_id",
        "result_id",
        "claim_kind",
        "samples",
    ],
)
def test_evidence_binds_the_complete_computation(connection, comparison, field):
    payload = comparison.model_dump(mode="json")
    value = payload["values"][2]
    if field in {"value", "label", "period", "unit", "scale"}:
        changes = {
            "value": 987654.0,
            "label": "different",
            "period": None,
            "unit": "USD",
            "scale": "one",
        }
        value[field] = changes[field]
    elif field == "input_refs":
        payload["evidence"][field] = ["lineage_nodes"]
    elif field == "parameters":
        payload[field]["series"] = "other"
    elif field == "claim_kind":
        payload[field] = "literal_source_value"
    elif field == "samples":
        payload[field]["used"] = 3
    else:
        payload[field] = "forged"
    changed = AnalyticalResult.model_validate(payload)
    assert (
        gate_answer("Değişim 18.520 milyon TL.", changed, connection).status
        is AnswerStatus.ABSTAINED
    )


@pytest.mark.parametrize("reference", ["missing", "wrong_kind", "self_digest", "empty", "copy"])
def test_only_the_matching_execution_reference_works(connection, comparison, reference):
    payload = comparison.model_dump(mode="json")
    if reference == "wrong_kind":
        node = Lineage(connection).record(NodeKind.SOURCE_FILE, "unrelated")
        ids = ["execution:" + node]
    elif reference == "self_digest":
        ids = ["execution:" + comparison.digest()]
    elif reference == "empty":
        ids = []
    elif reference == "copy":
        # Copy real evidence onto an arbitrary new result, not just a dangling id.
        payload = unproven().model_dump(mode="json")
        ids = comparison.evidence.evidence_ids
    else:
        ids = ["execution:missing"]
    payload["evidence"]["evidence_ids"] = ids
    result = AnalyticalResult.model_validate(payload)
    assert gate_answer("Değer 987654 TL.", result, connection).status is AnswerStatus.ABSTAINED
    from kkb_agent.agent.verifier import result_faults

    assert result_faults({"candidate": result}, connection)


@pytest.mark.parametrize("broken", ["none", "closed", "node", "input", "edge", "snapshot"])
def test_missing_or_broken_resolver_fails_closed(connection, comparison, broken):
    import json

    graph = Lineage(connection)
    node = comparison.evidence.evidence_ids[0].removeprefix("execution:")
    parent = graph.parents(node)[0][0]
    if broken == "none":
        connection = None
    elif broken == "closed":
        connection.close()
    elif broken == "node":
        connection.execute("UPDATE lineage_nodes SET attributes='{}' WHERE node_id=?", [node])
    elif broken == "input":
        connection.execute("DELETE FROM lineage_nodes WHERE node_id=?", [parent])
    elif broken == "edge":
        connection.execute("DELETE FROM lineage_edges WHERE downstream_id=?", [node])
    else:
        attributes = dict(graph.node(parent).attributes)
        attributes["snapshot"] = '{"forged":true}'
        connection.execute(
            "UPDATE lineage_nodes SET attributes=? WHERE node_id=?",
            [json.dumps(attributes), parent],
        )
    assert (
        gate_answer("Değişim 18.520 milyon TL.", comparison, connection).status
        is AnswerStatus.ABSTAINED
    )


def test_input_snapshot_preserves_actual_rows_and_source(connection, comparison):
    import json

    graph = Lineage(connection)
    node = graph.node(comparison.evidence.evidence_ids[0].removeprefix("execution:"))
    args = json.loads(node.attributes["arguments"])
    assert args["series_id"] == "housing"
    assert args["start"] == "2026-05-31"
    parents = graph.parents(node.node_id)
    snapshot = json.loads(graph.node(parents[0][0]).attributes["snapshot"])
    assert snapshot["artifact_id"] == "fixture"
    assert snapshot["series_id"] == "housing"
    assert [row[2] for row in snapshot["observations"]] == [782918, 801438]
    output = json.loads(node.attributes["output"])
    assert output["values"][2]["value"] == 18520.0
    # The event binds the actual computation, not whatever a later reread sees.
    connection.execute("UPDATE silver_observations SET value=1")
    assert graph.node(parents[0][0]).attributes["snapshot"] == json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def test_unproven_candidate_cannot_change_workspace(connection, comparison):
    import json

    from pydantic import BaseModel

    from kkb_agent.agent import Session, ToolRegistry, ToolResult, ToolSpec, ToolStatus
    from kkb_agent.agent.workspace import ArtifactKind, Workspace
    from kkb_agent.llm import scripted

    class Args(BaseModel):
        pass

    workspace = Workspace.open(connection, "proof-audit")
    workspace.record("table", ArtifactKind.VALUE, comparison)
    workspace.record("dependent", ArtifactKind.VALUE, comparison, inputs=["table"])
    tables = ("workspace_results", "workspace_artifacts", "workspace_bindings", "workspace_history")

    def snapshot():
        return [
            connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall() for table in tables
        ]

    before = snapshot()
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "lakehouse",
            "untrusted result double",
            Args,
            lambda a, c: ToolResult(ToolStatus.SUCCESS, "s1", "lakehouse", output=unproven()),
        )
    )
    provider = scripted(
        json.dumps(
            {
                "question": "audit",
                "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {}}],
            }
        ),
        "Değer 987654 TL.",
    )
    answer = Session(provider, registry).answer(
        "audit", connection, workspace=workspace, remember="table"
    )
    assert answer.answer.status is AnswerStatus.ABSTAINED
    assert snapshot() == before


def test_valid_neighbor_never_launders_unproven_claim(connection, comparison):
    answer = gate_answer(
        "Değişim 18.520 milyon TL. Başka değer 987654 TL.",
        {"valid": comparison, "invalid": unproven()},
        connection,
    )
    assert answer.status is AnswerStatus.QUALIFIED
    assert answer.text == "Değişim 18.520 milyon TL."
    assert "987654" not in answer.text


def test_legacy_result_stays_inspectable_without_becoming_proven(connection):
    from kkb_agent.agent.workspace import ArtifactKind, Workspace

    space = Workspace.open(connection, "legacy")
    result = unproven()
    before = result.digest()
    space.record("old", ArtifactKind.VALUE, result)
    loaded = space.value_of("old")
    assert loaded.digest() == before
    assert loaded.evidence.evidence_ids == []
    assert gate_answer("Değer 987654 TL.", loaded, connection).status is AnswerStatus.ABSTAINED
    assert space.value_of("old").digest() == before


def test_caller_uncommitted_evidence_cannot_authorize_publication(connection, comparison):
    from kkb_agent.agent.verifier import result_faults

    connection.execute("BEGIN")
    # Use a valid separate event: same comparison, without optional lineage.
    result = (
        make_change_detection_tool(connection)
        .run(
            ChangeDetectionArguments(
                operation="compare",
                series_id="housing",
                start=date(2026, 5, 31),
                end=date(2026, 6, 30),
            ),
            ExecutionContext(question="comparison without query lineage"),
        )
        .output
    )
    assert result.status is ResultStatus.COMPUTED
    assert result_faults({"candidate": result}, connection)
    connection.execute("ROLLBACK")
    assert result_faults({"candidate": result}, connection)
    assert not result_faults({"old": comparison}, connection)


@pytest.mark.parametrize("label", ["analytical_input_v1", "analytical_execution_v1"])
def test_failed_evidence_write_cannot_publish(connection, comparison, monkeypatch, label):
    import json

    from kkb_agent.agent import Session, ToolRegistry, ToolStatus
    from kkb_agent.agent.workspace import ArtifactKind, Workspace
    from kkb_agent.llm import scripted

    graph_record = Lineage.record

    def fail(self, kind, name, **kwargs):
        if name == label:
            raise RuntimeError("synthetic evidence write failure")
        return graph_record(self, kind, name, **kwargs)

    monkeypatch.setattr(Lineage, "record", fail)
    space = Workspace.open(connection, "write-failure")
    space.record("table", ArtifactKind.VALUE, comparison)
    before = space.history("table")
    registry = ToolRegistry()
    registry.register(make_change_detection_tool(connection))
    provider = scripted(
        json.dumps(
            {
                "question": "audit",
                "steps": [
                    {
                        "step_id": "s1",
                        "tool": "change_detection",
                        "arguments": {
                            "operation": "compare",
                            "series_id": "housing",
                            "start": "2026-05-31",
                            "end": "2026-06-30",
                        },
                    }
                ],
            }
        )
    )
    answered = Session(provider, registry).answer(
        "audit", connection, workspace=space, remember="table"
    )
    assert answered.outcome.results[0].status is ToolStatus.FAILURE
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert space.history("table") == before
    assert space.value_of("table").digest() == comparison.digest()
    assert len(provider.seen) == 1  # No writer called after the tool failed.


def test_repeated_production_reuses_evidence_but_changed_input_does_not(connection, comparison):
    from kkb_agent.agent.verifier import result_faults

    arguments = ChangeDetectionArguments(
        operation="compare", series_id="housing", start=date(2026, 5, 31), end=date(2026, 6, 30)
    )
    tool = make_change_detection_tool(connection, lineage=Lineage(connection))
    repeat = tool.run(arguments, ExecutionContext(question="repeat")).output
    assert repeat.evidence.evidence_ids == comparison.evidence.evidence_ids
    before = comparison.digest()
    connection.execute("UPDATE silver_observations SET value=801439 WHERE period_end='2026-06-30'")
    changed = tool.run(arguments, ExecutionContext(question="changed")).output
    assert changed.evidence.evidence_ids != comparison.evidence.evidence_ids
    assert comparison.digest() == before
    assert not result_faults({"changed": changed}, connection)


def test_snapshots_are_the_inputs_used_not_a_postcomputation_reread(
    connection, comparison, monkeypatch
):
    import json

    import kkb_agent.tools.change_detection as producer

    calculate = producer.compare_periods

    def change_after_computation(*args, **kwargs):
        result = calculate(*args, **kwargs)
        connection.execute("UPDATE silver_observations SET value=7")
        return result

    monkeypatch.setattr(producer, "compare_periods", change_after_computation)
    result = (
        make_change_detection_tool(connection)
        .run(
            ChangeDetectionArguments(
                operation="compare",
                series_id="housing",
                start=date(2026, 5, 31),
                end=date(2026, 6, 30),
            ),
            ExecutionContext(question="audit"),
        )
        .output
    )
    graph = Lineage(connection)
    node = result.evidence.evidence_ids[0].removeprefix("execution:")
    parent = graph.parents(node)[0][0]
    snapshot = json.loads(graph.node(parent).attributes["snapshot"])
    assert [row[2] for row in snapshot["observations"]] == [782918, 801438]
    assert result.values[2].value == 18520.0


def test_equal_outputs_from_different_input_snapshots_cannot_swap_receipts(connection, comparison):
    # Equal measurements do not make two source identities the same production event.
    connection.execute(
        "INSERT INTO bronze_artifacts SELECT 'other', 'other-source', source_type, locator, "
        "retrieved_at, media_type, byte_count, payload_path, recorded_at FROM bronze_artifacts"
    )
    rows = connection.execute("SELECT * FROM silver_observations").fetchall()
    # DuckDB disallows updating even a non-key parent column while referenced.
    connection.execute("DELETE FROM silver_observations")
    connection.execute("UPDATE silver_series SET artifact_id='other'")
    connection.executemany("INSERT INTO silver_observations VALUES (?,?,?,?)", rows)
    other = (
        make_change_detection_tool(connection, lineage=Lineage(connection))
        .run(
            ChangeDetectionArguments(
                operation="compare",
                series_id="housing",
                start=date(2026, 5, 31),
                end=date(2026, 6, 30),
            ),
            ExecutionContext(question="other source"),
        )
        .output
    )
    assert comparison.values == other.values
    assert comparison.evidence.evidence_ids != other.evidence.evidence_ids
    copied = comparison.model_copy(
        update={
            "evidence": comparison.evidence.model_copy(
                update={"evidence_ids": other.evidence.evidence_ids}
            )
        }
    )
    from kkb_agent.agent.verifier import result_faults

    assert result_faults({"copied": copied}, connection)
