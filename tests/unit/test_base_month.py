"""B1's base month: every change has its own predecessor, and none becomes a row.

The deposit question asks for the monthly net change over 2021-2025, whose first month
needs December 2020. The acquisition window now starts there; a change on a stored
series completes a missing predecessor from the store; a table of chosen months compares
each with its own previous calendar month, never with the row above; and a grouped
column is in no store: its base month travels through its chain (test_compute_contracts).
A balance's difference is its net change, never new deposits.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import ExecutionContext, Workspace
from kkb_agent.analytics.table_shape import TableShapeRefused, period_change
from kkb_agent.core import (
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.ingest.acquisition import bddk_window
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import make_lakehouse_tool, make_table_transform_tool
from kkb_agent.tools.lakehouse import LakehouseArguments


def month(end: date) -> Period:
    return Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY)


def cell(end: date, value: float, *, label: str = "bakiye", unit: str = "TRY") -> ResultValue:
    return ResultValue(
        label=label,
        value=value,
        unit=unit,
        scale=Scale.MILLION,
        measure=StockFlow.STOCK,
        period=month(end),
    )


def table(*values: ResultValue) -> AnalyticalResult:
    ends = [value.period.end for value in values if value.period is not None]
    return AnalyticalResult(
        result_id="t",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=list(values),
        coverage=Period(start=min(ends).replace(day=1), end=max(ends), frequency=Frequency.MONTHLY),
        evidence=ResultEvidence(input_refs=["x"]),
    )


JAN, FEB, MAR = date(2021, 1, 31), date(2021, 2, 28), date(2021, 3, 31)
DEC = date(2020, 12, 31)


def test_the_bddk_window_opens_on_the_month_before_the_prepared_period():
    window = bddk_window(date(2026, 9, 19))
    assert (window.start.year, window.start.month) == (2020, 12)


class TestAPredecessorOutsideTheTable:
    def test_the_first_month_is_completed_and_the_base_is_no_row(self):
        changed = period_change(
            table(cell(JAN, 110.0), cell(FEB, 115.0), cell(MAR, 112.0)),
            column_label="bakiye",
            kind="difference",
            preceding=(cell(DEC, 100.0),),
        )
        assert [(v.period.end, v.value) for v in changed.values] == [
            (JAN, 10.0),
            (FEB, 5.0),
            (MAR, -3.0),
        ]
        assert changed.transformation.parameters["predecessors_read_from_store"] == 1
        assert changed.transformation.parameters["periods_without_predecessor"] == 0

    def test_chosen_months_are_each_compared_with_their_own_previous_month(self):
        chosen = table(cell(date(2021, 3, 31), 130.0), cell(date(2022, 6, 30), 160.0))
        with pytest.raises(TableShapeRefused):
            # Without the store: never one chosen month minus another.
            period_change(chosen, column_label="bakiye", kind="difference")
        changed = period_change(
            chosen,
            column_label="bakiye",
            kind="difference",
            preceding=(cell(date(2021, 2, 28), 125.0), cell(date(2022, 5, 31), 158.0)),
        )
        assert [v.value for v in changed.values] == [5.0, 2.0]

    def test_a_value_in_another_unit_is_not_a_predecessor(self):
        changed = period_change(
            table(cell(JAN, 110.0), cell(FEB, 115.0)),
            column_label="bakiye",
            kind="difference",
            preceding=(cell(DEC, 100.0, unit="USD"),),
        )
        assert [v.period.end for v in changed.values] == [FEB]


SERIES = ("fixture:deposit_short", "fixture:deposit_long")
SEMANTICS = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
)
LEVELS = {
    SERIES[0]: {DEC: 100.0, JAN: 110.0, FEB: 115.0, MAR: 112.0},
    SERIES[1]: {DEC: 50.0, JAN: 52.0, FEB: 55.0, MAR: 60.0},
}


@pytest.fixture
def rig(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"synthetic deposits",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=datetime(2026, 9, 23, tzinfo=UTC),
        )
        for series in SERIES:
            lake.register_series(
                series, title=series, artifact_id=artifact.artifact_id, semantics=SEMANTICS
            )
            lake.append_observations(
                series,
                [
                    Observation(end.replace(day=1), end, value)
                    for end, value in LEVELS[series].items()
                ],
            )
        workspace = Workspace.open(lake.connection, "base")
        yield lake, workspace


def read(lake, *, since: date) -> AnalyticalResult:
    ids = ", ".join(f"'{series}'" for series in SERIES)
    sql = (
        "SELECT o.series_id,o.period_start,o.period_end,o.value,"
        "s.unit,s.scale,s.frequency,s.observation "
        "FROM silver_observations o JOIN silver_series s ON o.series_id=s.series_id "
        f"WHERE o.series_id IN ({ids}) AND o.period_end >= DATE '{since.isoformat()}' "
        "ORDER BY o.period_end"
    )
    output = (
        make_lakehouse_tool(lake.connection, lineage=lake.lineage)
        .run(LakehouseArguments(sql=sql), ExecutionContext("read"))
        .output
    )
    return output.result


def transform(lake, workspace, context, **arguments):
    tool = make_table_transform_tool(lake.connection, workspace, lineage=lake.lineage)
    return tool.run(tool.parse(arguments), context)


class TestTheStoreAndTheChain:
    def test_a_stored_series_window_takes_its_base_from_the_store(self, rig):
        lake, workspace = rig
        window = read(lake, since=JAN)
        assert all(v.period.end >= JAN for v in window.values)
        context = ExecutionContext("soru", outputs={"a1": window})
        done = transform(
            lake,
            workspace,
            context,
            operation="change",
            source="a1",
            column=SERIES[0],
            kind="difference",
        ).output
        assert done.status is ResultStatus.COMPUTED
        new = [v for v in done.values if v.label.endswith("change (lag 1)")]
        assert [(v.period.end, v.value) for v in new] == [(JAN, 10.0), (FEB, 5.0), (MAR, -3.0)]
        # The base month completed a change and is no row of the table.
        assert DEC not in {v.period.end for v in done.values}
        assert any("net change of a balance" in item for item in done.limitations)
