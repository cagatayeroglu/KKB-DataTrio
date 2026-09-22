"""A running total is never taken for each period's own amount.

The organizer's brief warns that some BDDK figures accumulate from their first publication
and some within each year, and that ignoring it makes the calculations wrong. The store
declares which series do, and the tools that read a stored series refuse them; but a table
cell carries no cumulative kind, so every table operation summed, averaged, differenced
and deflated a year-to-date column as if each value were the month's own, and the answer
gate accepted the result because every figure was one the harness had computed (audit of
2026-09-21: twelve running totals summed to 7,800 where the year earned 1,200).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from test_accumulation_runtime import SEMANTICS, SERIES
from test_accumulation_runtime import rig as rig  # noqa: F401 - one stored year-to-date series
from test_association import ECHO, MONTHLY_RATE, WAVES, lagged, pair
from test_granger import FOLLOWER, LEADER, MONTHLY
from test_granger import monthly as granger_months

from kkb_agent.agent import ArtifactKind, ExecutionContext, Workspace
from kkb_agent.analytics.granger import granger_precedence
from kkb_agent.core import CumulativeKind, Frequency, ResultStatus, Scale, SourceRef, StockFlow
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import make_lakehouse_tool
from kkb_agent.tools.lakehouse import SeriesRead
from kkb_agent.tools.table_relationship import TableRelationshipArguments, run_table_relationship
from kkb_agent.tools.table_transform import TableTransformArguments


def transform(tool, **arguments):
    return tool.run(
        TableTransformArguments.model_validate({"source": "original", **arguments}),
        ExecutionContext("synthetic"),
    ).output


@pytest.mark.parametrize("aggregation", ["sum", "mean", "min", "max"])
def test_a_running_total_is_not_summed_or_averaged_as_if_it_were_monthly(rig, aggregation):  # noqa: F811
    _, _, tool = rig
    result = transform(
        tool,
        operation="summarize",
        column=SERIES,
        aggregation=aggregation,
        requested_aggregation=aggregation,
    )

    assert result.status is ResultStatus.ABSTAINED and not result.values
    # The reason is what the planner gets for its one run-time re-plan (DEC-167).
    assert "yearly_reset" in result.reason and "to_flow" in result.reason


@pytest.mark.parametrize("aggregation", ["first", "last", "count"])
def test_quoting_or_counting_its_cells_is_not_arithmetic_across_periods(rig, aggregation):  # noqa: F811
    _, _, tool = rig
    result = transform(
        tool,
        operation="summarize",
        column=SERIES,
        aggregation=aggregation,
        requested_aggregation=aggregation,
    )

    assert result.status is ResultStatus.COMPUTED


def test_its_month_over_month_change_is_refused_and_its_year_over_year_one_is_not(rig):  # noqa: F811
    _, _, tool = rig
    monthly = transform(tool, operation="change", column=SERIES, kind="difference")
    yearly = transform(tool, operation="change", column=SERIES, kind="difference", lag=12)

    assert monthly.status is ResultStatus.ABSTAINED and "to_flow" in monthly.reason
    # Twelve months apart one running total meets last year's; whatever this short
    # fixture then yields, it is not refused for accumulating.
    assert "running total" not in (yearly.reason or "")


def test_it_is_not_deflated_by_one_months_index(rig):  # noqa: F811
    _, _, tool = rig
    result = transform(
        tool,
        operation="deflate",
        column=SERIES,
        index_series_id="fixture:cpi",
        reference_period="2026-02-28",
    )

    assert result.status is ResultStatus.ABSTAINED and "to_flow" in result.reason


def test_the_flow_column_to_flow_adds_is_summed_like_any_other(rig):  # noqa: F811
    _, workspace, tool = rig
    flow = transform(tool, operation="to_flow", column=SERIES)
    workspace.record("flow", ArtifactKind.VALUE, flow, inputs=("original",))
    label = flow.values[-1].label

    total = tool.run(
        TableTransformArguments.model_validate(
            {
                "operation": "summarize",
                "source": "flow",
                "column": label,
                "aggregation": "sum",
                "requested_aggregation": "sum",
            }
        ),
        ExecutionContext("synthetic"),
    ).output
    assert total.status is ResultStatus.COMPUTED
    assert [value.value for value in total.values] == [50.0]  # 30 + 8 + 12
    # The raw column rides along in the same table, and is still what it was.
    raw = tool.run(
        TableTransformArguments.model_validate(
            {
                "operation": "summarize",
                "source": "flow",
                "column": SERIES,
                "aggregation": "sum",
                "requested_aggregation": "sum",
            }
        ),
        ExecutionContext("synthetic"),
    ).output
    assert raw.status is ResultStatus.ABSTAINED


def test_a_read_of_a_running_total_says_what_its_values_are(rig):  # noqa: F811
    _, workspace, _ = rig
    read = workspace.value_of("original")

    assert read.status is ResultStatus.COMPUTED
    assert any(SERIES in item and "yearly_reset" in item for item in read.limitations)


class TestAnAssociationIsNotMeasuredOnARunningTotal:
    YEAR_TO_DATE = replace(
        MONTHLY_RATE,
        unit="TRY",
        scale=Scale.MILLION,
        observation=StockFlow.FLOW,
        cumulative=CumulativeKind.YEARLY_RESET,
    )

    def test_association_and_lag_refuse_it_on_either_side(self):
        for result in (
            pair(right_sem=self.YEAR_TO_DATE),
            pair(left=ECHO, right=WAVES, left_sem=self.YEAR_TO_DATE, right_sem=MONTHLY_RATE),
            lagged(right_sem=self.YEAR_TO_DATE),
        ):
            assert result.status is ResultStatus.ABSTAINED
            assert "accumulates (yearly_reset)" in result.reason

    def test_granger_refuses_it_too(self):
        result = granger_precedence(
            granger_months(LEADER),
            MONTHLY,
            granger_months(FOLLOWER),
            self.YEAR_TO_DATE,
            left_id="a",
            right_id="b",
            max_order=4,
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "accumulates (yearly_reset)" in result.reason


def test_the_stores_declaration_outranks_what_the_values_look_like(tmp_path):
    """A year-to-date profit with a loss month stops looking cumulative; it still is one."""
    months = [date(2025, month, 28) for month in range(1, 13)]
    ends = [
        date(day.year, day.month, 31 if day.month in (1, 3, 5, 7, 8, 10, 12) else 30)
        if day.month != 2
        else day
        for day in months
    ]
    running = [50.0, 100.0, 150.0, 120.0, 170.0, 220.0, 270.0, 320.0, 370.0, 420.0, 470.0, 520.0]
    rate = [20.0 + step for step in range(12)]
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"synthetic",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=datetime(2026, 9, 21, tzinfo=UTC),
        )
        for series_id, semantics, values in (
            (SERIES, SEMANTICS, running),
            (
                "fixture:rate",
                SeriesSemantics(
                    unit="percent",
                    scale=Scale.ONE,
                    frequency=Frequency.MONTHLY,
                    observation=StockFlow.RATE,
                    cumulative=CumulativeKind.NONE,
                ),
                rate,
            ),
        ):
            lake.register_series(
                series_id, title=series_id, artifact_id=artifact.artifact_id, semantics=semantics
            )
            lake.append_observations(
                series_id,
                [
                    Observation(end.replace(day=1), end, value)
                    for end, value in zip(ends, values, strict=True)
                ],
            )
        workspace = Workspace.open(lake.connection, "running-totals")
        table = (
            make_lakehouse_tool(lake.connection, lineage=lake.lineage)
            .run(
                SeriesRead(
                    series=[SERIES, "fixture:rate"], start=ends[0].replace(day=1), end=ends[-1]
                ),
                ExecutionContext("read both"),
            )
            .output.result
        )
        assert table.status is ResultStatus.COMPUTED
        workspace.record("both", ArtifactKind.VALUE, table)

        compared = run_table_relationship(
            TableRelationshipArguments(
                operation="table_co_movement",
                source="both",
                driver_column="fixture:rate",
                target_column=SERIES,
                driver_direction="up",
                target_direction="up",
            ),
            ExecutionContext("compare"),
            lake.connection,
            workspace=workspace,
            lineage=lake.lineage,
        ).output

    assert compared.status is ResultStatus.ABSTAINED
    assert "yearly_reset" in compared.reason and "to_flow" in compared.reason
