"""Synthetic arithmetic and real tool/workspace regression for cumulative conversion."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from kkb_agent.agent import ArtifactKind, ExecutionContext, Session, ToolRegistry, Workspace
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics.accumulation import AccumulationRefused, to_flow_column
from kkb_agent.analytics.table_relationship import TableComparisonRefused, _column
from kkb_agent.core import (
    CumulativeKind,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.tools import make_lakehouse_tool, make_table_transform_tool
from kkb_agent.tools.lakehouse import LakehouseArguments
from kkb_agent.tools.table_transform import TableTransformArguments

SERIES = "fixture:net_profit"
SEMANTICS = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.FLOW,
    cumulative=CumulativeKind.YEARLY_RESET,
)
ENDS = [date(2025, 11, 30), date(2025, 12, 31), date(2026, 1, 31), date(2026, 2, 28)]


def column(values=(90.0, 120.0, 8.0, 20.0), ends=ENDS):
    return [
        ResultValue(
            label=SERIES,
            value=value,
            unit="TRY",
            scale=Scale.MILLION,
            measure=StockFlow.FLOW,
            period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
        )
        for end, value in zip(ends, values, strict=True)
    ]


def convert(values=None, semantics=SEMANTICS, **kwargs):
    return to_flow_column(
        column() if values is None else values, semantics, column_label=SERIES, **kwargs
    )


def test_year_boundary_is_reset_not_a_negative_flow_and_input_is_immutable():
    original = column()
    before = [v.model_dump() for v in original]
    result = convert(list(reversed(original)))
    assert [v.value for v in result.values] == [30.0, 8.0, 12.0]
    assert result.empty_periods == (ENDS[0],)
    assert result.transformation.parameters["declared_cumulative"] == "yearly_reset"
    assert [v.model_dump() for v in original] == before
    assert {(v.unit, v.scale, v.measure) for v in result.values} == {
        ("TRY", Scale.MILLION, StockFlow.FLOW)
    }


@pytest.mark.parametrize(
    "baseline, expected", [(None, [30.0, -112.0, 12.0]), (80.0, [10.0, 30.0, -112.0, 12.0])]
)
def test_since_inception_uses_only_an_explicit_baseline(baseline, expected):
    result = convert(
        semantics=replace(SEMANTICS, cumulative=CumulativeKind.SINCE_INCEPTION), baseline=baseline
    )
    assert [v.value for v in result.values] == expected


def test_missing_month_is_neither_zero_nor_a_multimonth_flow():
    values = column()[::2] + column()[3:]
    result = convert(values)
    assert [v.value for v in result.values] == [8.0, 12.0]
    midyear = column((10.0, 50.0, 80.0), [date(2026, 2, 28), date(2026, 4, 30), date(2026, 5, 31)])
    result = convert(midyear)
    assert [v.value for v in result.values] == [30.0]
    assert result.empty_periods == (date(2026, 2, 28), date(2026, 4, 30))


@pytest.mark.parametrize("kind", [CumulativeKind.NONE, CumulativeKind.UNKNOWN])
def test_rising_values_cannot_authorize_conversion(kind):
    with pytest.raises(AccumulationRefused):
        convert(semantics=replace(SEMANTICS, cumulative=kind))


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "duplicate",
        "no_period",
        "bad_start",
        "bad_end",
        "unit",
        "scale",
        "measure",
        "label",
        "infinite",
    ],
)
def test_bad_column_refused_before_any_numbers_are_published(case):
    values = column()
    if case == "empty":
        values = []
    elif case == "duplicate":
        values.append(values[0])
    else:
        updates = {
            "no_period": {"period": None},
            "unit": {"unit": "USD"},
            "scale": {"scale": Scale.ONE},
            "measure": {"measure": StockFlow.STOCK},
            "label": {"label": "another_series"},
            "infinite": {"value": float("inf")},
        }
        if case in ("bad_start", "bad_end"):
            field = "start" if case == "bad_start" else "end"
            updates[case] = {
                "period": values[0].period.model_copy(update={field: date(2025, 11, 15)})
            }
        values[0] = values[0].model_copy(update=updates[case])
    with pytest.raises(AccumulationRefused):
        convert(values)


def test_unsupported_frequency_and_nonfinite_baseline_refused():
    with pytest.raises(AccumulationRefused):
        convert(semantics=replace(SEMANTICS, frequency=Frequency.QUARTERLY))
    with pytest.raises(AccumulationRefused):
        convert(baseline=float("nan"))


@pytest.fixture
def rig(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"synthetic net profit",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=datetime(2026, 9, 18, tzinfo=UTC),
        )
        lake.register_series(
            SERIES,
            title="Synthetic net profit",
            artifact_id=artifact.artifact_id,
            semantics=SEMANTICS,
        )
        lake.append_observations(
            SERIES, [Observation(v.period.start, v.period.end, v.value) for v in column()]
        )
        workspace = Workspace.open(lake.connection, "flow-test")
        sql = (
            "SELECT o.series_id,o.period_start,o.period_end,o.value,"
            "s.unit,s.scale,s.frequency,s.observation "
            "FROM silver_observations o JOIN silver_series s ON o.series_id=s.series_id "
            f"WHERE o.series_id='{SERIES}' ORDER BY o.period_end"
        )
        output = (
            make_lakehouse_tool(lake.connection, lineage=lake.lineage)
            .run(LakehouseArguments(sql=sql), ExecutionContext("read synthetic table"))
            .output
        )
        output = output.result
        assert output.status is ResultStatus.COMPUTED
        workspace.record("original", ArtifactKind.VALUE, output)
        tool = make_table_transform_tool(lake.connection, workspace, lineage=lake.lineage)
        yield lake, workspace, tool


def args(source="original", **updates):
    return TableTransformArguments.model_validate(
        {"operation": "to_flow", "source": source, "column": SERIES, **updates}
    )


def test_real_tool_preserves_source_and_binds_result_to_execution_evidence(rig):
    lake, workspace, tool = rig
    source = workspace.value_of("original")
    before = source.digest()
    result = tool.run(args(), ExecutionContext("convert to monthly flow")).output
    assert result.status is ResultStatus.COMPUTED
    assert result.values[: len(source.values)] == source.values
    assert [v.value for v in result.values[len(source.values) :]] == [30.0, 8.0, 12.0]
    assert result_faults({"flow": result}, lake.connection) == {}
    assert workspace.value_of("original").digest() == before
    altered = result.model_copy(
        update={
            "values": [*result.values[:-1], result.values[-1].model_copy(update={"value": 999.0})]
        }
    )
    assert result_faults({"tampered": altered}, lake.connection)
    workspace.record("flow", ArtifactKind.VALUE, result, inputs=("original",))
    retry = tool.run(args("flow"), ExecutionContext("convert the same column again")).output
    assert retry.status is ResultStatus.ABSTAINED and not retry.values
    assert workspace.value_of("flow").digest() == result.digest()


def test_converted_column_is_usable_without_inferring_cumulative_shape(rig):
    _, _, tool = rig
    result = tool.run(args(), ExecutionContext("convert")).output
    label = result.values[-1].label
    notes = []
    assert list(_column(result, label, notes).values()) == [30.0, 8.0, 12.0]
    assert any("to_flow" in note for note in notes)
    # A suffix alone must not turn unconverted values into declared period flows.
    with pytest.raises(TableComparisonRefused):
        _column(result.model_copy(update={"evidence": None}), label, [])
    with pytest.raises(TableComparisonRefused):
        _column(result, SERIES, [])


def test_no_usable_predecessor_abstains_instead_of_publishing_unchanged_table(rig):
    _, workspace, tool = rig
    filtered = tool.run(
        TableTransformArguments.model_validate(
            {
                "operation": "filter",
                "source": "original",
                "start_period": "2025-11-30",
                "end_period": "2025-11-30",
            }
        ),
        ExecutionContext("filter"),
    ).output
    workspace.record("single", ArtifactKind.VALUE, filtered, inputs=("original",))
    result = tool.run(args("single"), ExecutionContext("convert")).output
    assert result.status is ResultStatus.ABSTAINED and not result.values


def test_planner_schema_does_not_accept_invented_cumulative_kind_or_baseline():
    for update in ({"cumulative": "yearly_reset"}, {"baseline": 0.0}):
        with pytest.raises(ValidationError):
            args(**update)


def test_scripted_plan_runs_real_tool_and_records_observed_trace(rig):
    import json

    lake, workspace, tool = rig
    registry = ToolRegistry()
    registry.register(tool)
    tracer = Tracer()
    provider = scripted(
        json.dumps(
            {
                "question": "convert",
                "steps": [
                    {
                        "step_id": "flow",
                        "tool": "table_transform",
                        "arguments": args().model_dump(mode="json"),
                    }
                ],
            }
        )
    )
    plan, outcome = Session(provider, registry, tracer=tracer).run("convert", workspace)
    assert plan.plan.steps[0].arguments.root.operation == "to_flow"
    assert outcome.by_step("flow").output.status is ResultStatus.COMPUTED
    assert result_faults({"flow": outcome.by_step("flow").output}, lake.connection) == {}
    assert any(event.name == "table_transform" and event.stage == "tool" for event in tracer.events)


def test_flow_then_add_series_then_compare_uses_real_tools_and_survives_reopen(rig):
    from kkb_agent.tools import make_change_detection_tool
    from kkb_agent.tools.change_detection import ChangeDetectionArguments

    lake, workspace, tool = rig
    artifact = lake.record_artifact(
        b"synthetic monthly driver",
        source=SourceRef(source_id="driver", source_type="fixture", locator="opaque:driver"),
        media_type="text/plain",
        recorded_at=datetime(2026, 9, 18, tzinfo=UTC),
    )
    lake.register_series(
        "fixture:rate",
        title="Synthetic rate",
        artifact_id=artifact.artifact_id,
        semantics=replace(
            SEMANTICS,
            unit="percent",
            scale=Scale.ONE,
            observation=StockFlow.RATE,
            cumulative=CumulativeKind.NONE,
        ),
    )
    lake.append_observations(
        "fixture:rate",
        [
            Observation(end.replace(day=1), end, value)
            for end, value in zip(ENDS, (10.0, 9.0, 8.0, 9.0), strict=True)
        ],
    )
    source = workspace.value_of("original")
    flowed = tool.run(args(), ExecutionContext("convert")).output
    workspace.record("flow", ArtifactKind.VALUE, flowed, inputs=("original",))
    augmented = tool.run(
        TableTransformArguments.model_validate(
            {"operation": "add_series", "source": "flow", "series_id": "fixture:rate"}
        ),
        ExecutionContext("add driver"),
    ).output
    assert augmented.status is ResultStatus.COMPUTED
    workspace.record("augmented", ArtifactKind.VALUE, augmented, inputs=("flow",))
    # Reopen the durable workspace object: the conversion semantics come from
    # stored evidence, not the planner's memory or a transient variable.
    reopened = Workspace.open(lake.connection, "flow-test")
    comparison = (
        make_change_detection_tool(lake.connection, workspace=reopened, lineage=lake.lineage)
        .run(
            ChangeDetectionArguments.model_validate(
                {
                    "operation": "table_co_movement",
                    "source": "augmented",
                    "driver_column": "fixture:rate",
                    "target_column": flowed.values[-1].label,
                    "driver_direction": "up",
                    "target_direction": "up",
                }
            ),
            ExecutionContext("compare monthly directions"),
        )
        .output
    )
    assert comparison.status is ResultStatus.COMPUTED
    count = next(
        v.value
        for v in comparison.values
        if v.label.endswith("eligible transitions matching both directions")
    )
    assert count == 1.0  # February: rate 8 -> 9, monthly profit 8 -> 12.
    assert comparison.values[: len(augmented.values)] == augmented.values
    assert reopened.value_of("original").digest() == source.digest()
    assert result_faults({"comparison": comparison}, lake.connection) == {}


def test_registered_noncumulative_series_is_refused_at_tool_boundary(rig):
    lake, _, tool = rig
    # A new declaration cannot authorize guessing from increasing values.
    lake.connection.execute(
        "UPDATE silver_series SET cumulative = 'none' WHERE series_id = ?", [SERIES]
    )
    result = tool.run(args(), ExecutionContext("convert")).output
    assert result.status is ResultStatus.ABSTAINED and not result.values
