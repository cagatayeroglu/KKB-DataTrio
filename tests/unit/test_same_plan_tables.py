"""E1 (2026-09-19): one turn may fetch a table and transform it in the same plan.

The accepted live run planned lakehouse -> table_transform.deflate(source="fetch_housing")
and failed at run time because `source` resolved published tables only; validation had
passed. The validator now checks every table name against the published tables and the
plan's own steps, and the tool reads a same-plan step's result when the edge is declared.
"""

import json
from types import SimpleNamespace

import pytest
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_turn_two import CPI_ID, transform
from test_turn_two import pool as pool  # noqa: F401
from test_turn_two import tool as transform_tool

from kkb_agent.agent import (
    AnalyticalPlan,
    AnswerStatus,
    ExecutionContext,
    PlanRejected,
    Session,
    ToolRegistry,
    ToolStatus,
    validate_plan,
)
from kkb_agent.core import ResultStatus
from kkb_agent.llm import scripted
from kkb_agent.tools import make_lakehouse_tool

FETCH_SQL = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    f" WHERE o.series_id = '{CPI_ID}'"
)
PUBLISHED = "konut_kredisi_ve_faiz"
QUESTION = "TÜFE genel endeksini Haziran 2021 = 100 olacak şekilde yeniden bazla."


def registry_for(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(lake.connection, lineage=lake.lineage))
    registry.register(transform_tool(lake, workspace))
    return registry


def fetch():
    return {"step_id": "fetch", "tool": "lakehouse", "arguments": {"sql": FETCH_SQL}}


def rebase(source, depends_on=()):
    return {
        "step_id": "rebased",
        "tool": "table_transform",
        "arguments": {
            "operation": "rebase",
            "source": source,
            "column": CPI_ID,
            "reference_period": "2021-06-30",
            "new_base": 100.0,
        },
        "depends_on": list(depends_on),
    }


def plan(*steps, question=QUESTION):
    return AnalyticalPlan.model_validate({"question": question, "steps": list(steps)})


def test_the_validator_accepts_published_tables_and_declared_same_plan_steps(pool):
    registry = registry_for(pool)
    known = pool[1].names()
    assert known == [PUBLISHED]
    validate_plan(plan(fetch(), rebase("fetch", ["fetch"])), registry, known_tables=known)
    validate_plan(plan(rebase(PUBLISHED)), registry, known_tables=known)
    # A caller without a workspace keeps the earlier behaviour: names are not checked here.
    validate_plan(plan(rebase("fetch_housing")), registry)


def test_the_validator_names_the_repair_for_a_missing_edge_or_an_unknown_table(pool):
    registry = registry_for(pool)
    known = pool[1].names()
    with pytest.raises(PlanRejected, match="declare 'fetch' in depends_on"):
        validate_plan(plan(fetch(), rebase("fetch")), registry, known_tables=known)
    with pytest.raises(PlanRejected, match="neither a published result nor an earlier step"):
        validate_plan(plan(rebase("fetch_housing")), registry, known_tables=known)
    with pytest.raises(PlanRejected, match=PUBLISHED):
        validate_plan(plan(rebase("fetch_housing")), registry, known_tables=known)
    with pytest.raises(PlanRejected, match="cannot use itself"):
        validate_plan(plan(rebase("rebased")), registry, known_tables=known)


def test_scalar_and_independent_table_are_not_implicitly_published_as_one(pool):
    registry = registry_for(pool)
    second = {**fetch(), "step_id": "other"}
    scalar = {
        "step_id": "summary",
        "tool": "table_transform",
        "arguments": {
            "operation": "summarize",
            "source": "fetch",
            "column": CPI_ID,
            "aggregation": "mean",
        },
        "depends_on": ["fetch"],
    }
    # A table nobody consumes beside a summary of another used to refuse the plan. The
    # last step's result is published; the other reaches the writer (`Session.answer`).
    validated = validate_plan(plan(fetch(), second, scalar), registry, known_tables=pool[1].names())
    assert [item.step.step_id for item in validated.steps][-1] == "summary"


def test_same_plan_step_cannot_shadow_a_published_table_name(pool):
    registry = registry_for(pool)
    shadowed = {**fetch(), "step_id": PUBLISHED}
    with pytest.raises(PlanRejected, match="collides with a published table"):
        validate_plan(
            plan(shadowed, rebase(PUBLISHED, [PUBLISHED])),
            registry,
            known_tables=pool[1].names(),
        )


def test_the_tool_reads_a_same_plan_step_when_the_plan_declared_it(pool):
    lake, workspace = pool
    source = workspace.value_of(PUBLISHED)
    tool = transform_tool(lake, workspace)
    # A step's output is either the typed result itself or a tool output carrying it.
    for produced in (source, SimpleNamespace(result=source)):
        context = ExecutionContext("turn", outputs={"fetch": produced})
        result = tool.run(transform(source="fetch"), context)
        assert result.status is ToolStatus.SUCCESS, result.warnings
        assert result.output.status is ResultStatus.COMPUTED
        assert result.output.values[: len(source.values)] == source.values
    missing = tool.run(transform(source="fetch_housing"), ExecutionContext("turn"))
    assert missing.error_category == "workspace_reference"
    assert "earlier step of this plan" in missing.warnings[0]


def test_a_turn_fetches_and_transforms_in_one_plan_and_publishes_the_result(pool):
    lake, workspace = pool
    steps = [fetch(), rebase("fetch", ["fetch"])]
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), "Tablo hazırlandı.")
    answered = Session(provider, registry_for(pool)).answer(
        QUESTION, lake.connection, workspace=workspace, remember="tufe_haziran_bazli"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert answered.outcome.completed
    assert [r.status for r in answered.outcome.results] == [ToolStatus.SUCCESS] * 2
    published = workspace.value_of("tufe_haziran_bazli")
    assert published.evidence.transformations[-1].operation == "rebase"
    assert workspace.names() == [PUBLISHED, "tufe_haziran_bazli"]


def test_a_one_column_fetched_table_is_used_when_the_planner_names_a_column_it_could_not_see(
    pool,
):
    """Live E1 (2026-09-19): the planner wrote column="value" for a lakehouse step's table."""
    lake, workspace = pool
    steps = [
        fetch(),
        {
            **rebase("fetch", ["fetch"]),
            "arguments": {**rebase("fetch")["arguments"], "column": "value"},
        },
    ]
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), "Tablo hazırlandı.")
    answered = Session(provider, registry_for(pool)).answer(
        QUESTION, lake.connection, workspace=workspace, remember="tufe_bazli_value"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    published = workspace.value_of("tufe_bazli_value")
    assert published.parameters["column_resolution"] == {"requested": "value", "used": CPI_ID}
    assert any("its only column" in warning for warning in published.warnings)
    assert published.evidence.transformations[-1].operation == "rebase"


def test_a_wrong_label_on_a_table_with_several_columns_names_them(pool):
    lake, workspace = pool
    result = transform_tool(lake, workspace).run(transform(column="value"), ExecutionContext("t"))
    assert result.status is ToolStatus.SUCCESS and result.output.status is ResultStatus.ABSTAINED
    assert "the table's columns are:" in result.output.reason
    assert "EVDS:TP.KTF12" in result.output.reason and "BDDK:selector" in result.output.reason


def test_change_adds_a_month_over_month_column_and_marks_the_largest_moves(pool):
    """Live U2 (2026-09-19): "Harcama en çok hangi ayda arttı?" had no tool to answer it."""
    from test_co_movement import CREDIT, MONTHS, TOTAL_ID

    from kkb_agent.agent.verifier import result_faults
    from kkb_agent.tools.table_transform import TableTransformArguments

    lake, workspace = pool
    arguments = TableTransformArguments.model_validate(
        {"operation": "change", "source": PUBLISHED, "column": TOTAL_ID, "kind": "percent"}
    )
    result = transform_tool(lake, workspace).run(arguments, ExecutionContext("turn")).output
    assert result.status is ResultStatus.COMPUTED, result.reason
    label = f"{TOTAL_ID} % change (lag 1)"
    added = {v.period.end: v.value for v in result.values if v.label == label}
    expected = {
        end: (now / before - 1) * 100
        for end, now, before in zip(MONTHS[1:], CREDIT[1:], CREDIT[:-1], strict=True)
    }
    assert added == pytest.approx(expected)
    source = workspace.value_of(PUBLISHED)
    assert result.values[: len(source.values)] == source.values
    highlighted = result.parameters["highlighted_periods"]
    assert highlighted[f"{label} is largest"] == [MONTHS[2].isoformat()]  # 990 -> 1010
    assert highlighted[f"{label} is smallest"] == [MONTHS[1].isoformat()]  # 1000 -> 990
    assert result.evidence.transformations[-1].operation == "change"
    assert result_faults({"change": result}, lake.connection) == {}


def test_a_change_turn_needs_no_discovery_and_publishes(pool):
    from test_co_movement import TOTAL_ID

    lake, workspace = pool
    step = {
        "step_id": "aylik_degisim",
        "tool": "table_transform",
        "arguments": {
            "operation": "change",
            "source": PUBLISHED,
            "column": TOTAL_ID,
            "kind": "difference",
        },
    }
    question = "Konut kredisi bakiyesi en çok hangi ayda arttı?"
    provider = scripted(json.dumps({"question": question, "steps": [step]}), "Tablo hazırlandı.")
    session = Session(provider, registry_for(pool), require_series_discovery=True)
    answered = session.answer(question, lake.connection, workspace=workspace, remember="degisim")
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert workspace.names() == ["degisim", PUBLISHED]
