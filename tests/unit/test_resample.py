"""resample: a weekly column of a published table, onto months by its declaration."""

from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

import pytest

from kkb_agent.analytics.resample import ResampleRefused, resample_column
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Period,
    ResultValue,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.alignment import WeekAssignment
from kkb_agent.lakehouse.semantics import SeriesSemantics

RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.WEEKLY,
    anchor=WeeklyAnchor.FRIDAY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)


def fridays(first, count):
    return [first + timedelta(days=7 * i) for i in range(count)]


def column(values, first=date(2026, 1, 2), label="EVDS:TP.RATE"):
    return [
        ResultValue(
            label=label,
            value=value,
            unit="percent",
            scale=Scale.ONE,
            measure=StockFlow.RATE,
            period=Period(
                start=end - timedelta(days=6),
                end=end,
                frequency=Frequency.WEEKLY,
                weekly_anchor=WeeklyAnchor.FRIDAY,
            ),
        )
        for end, value in zip(fridays(first, len(values)), values, strict=True)
    ]


def test_weeks_become_months_by_the_declared_average_with_coverage():
    # Fridays of Jan 2026: 2, 9, 16, 23, 30; February: 6, 13, 20, 27.
    reduced = resample_column(
        column([10, 12, 14, 16, 18, 20, 22, 24, 26]),
        RATE,
        column_label="EVDS:TP.RATE",
        assignment=WeekAssignment.BY_END,
    )
    by_month = {v.period.end: v.value for v in reduced.values}
    assert by_month == {date(2026, 1, 31): 14.0, date(2026, 2, 28): 23.0}
    assert all(v.period.frequency is Frequency.MONTHLY for v in reduced.values)
    assert reduced.label == "EVDS:TP.RATE monthly average (by_end)"
    coverage = reduced.transformation.parameters["coverage"]
    assert coverage["2026-01-31"] == {"expected": 5, "observed": 5}
    assert reduced.incomplete == ()


def test_a_month_with_a_missing_week_is_kept_and_marked():
    values = column([10, 12, 14, 16, 18])
    del values[2]  # 16 January was not published
    reduced = resample_column(
        values, RATE, column_label="EVDS:TP.RATE", assignment=WeekAssignment.BY_END
    )
    assert reduced.incomplete == (date(2026, 1, 31),)
    assert reduced.values[0].value == pytest.approx((10 + 12 + 16 + 18) / 4)


@pytest.mark.parametrize(
    ("semantics", "needle"),
    [
        (replace(RATE, aggregation=Aggregation.UNKNOWN), "declares no aggregation"),
        (
            replace(RATE, frequency=Frequency.MONTHLY, anchor=None),
            "only a weekly or a daily column",
        ),
    ],
)
def test_no_declared_way_means_no_reduction(semantics, needle):
    with pytest.raises(ResampleRefused, match=needle):
        resample_column(
            column([1, 2, 3]),
            semantics,
            column_label="EVDS:TP.RATE",
            assignment=WeekAssignment.BY_END,
        )


def test_the_planner_states_the_week_assignment():
    from kkb_agent.tools.table_transform import TableTransformArguments

    ok = TableTransformArguments.model_validate(
        {"operation": "resample", "source": "analiz_1", "column": "x", "week_assignment": "by_end"}
    )
    assert ok.root.operation == "resample"
    # A daily column needs none, so the schema allows its absence; a weekly column is then
    # refused rather than given a default.
    bare = TableTransformArguments.model_validate(
        {"operation": "resample", "source": "analiz_1", "column": "x"}
    )
    assert bare.root.week_assignment is None
    with pytest.raises(ResampleRefused, match="never defaulted"):
        resample_column(column([1, 2, 3]), RATE, column_label="EVDS:TP.RATE", assignment=None)


DAILY_RATE = SeriesSemantics(
    unit="TRY",
    scale=Scale.ONE,
    frequency=Frequency.DAILY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)


def daily_column(first, last, label="EVDS:TP.DK.USD.A.YTL"):
    """Every weekday with a value, as a typed read returns a daily series (DEC-177)."""
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return [
        ResultValue(
            label=label,
            value=float(day.day),
            unit="TRY",
            scale=Scale.ONE,
            measure=StockFlow.STOCK,
            period=Period(start=day, end=day, frequency=Frequency.DAILY),
        )
        for day in days
        if day.weekday() < 5
    ]


def test_days_become_months_by_the_declared_aggregation_with_coverage():
    values = daily_column(date(2026, 6, 1), date(2026, 8, 18))
    reduced = resample_column(
        values, DAILY_RATE, column_label="EVDS:TP.DK.USD.A.YTL", assignment=None
    )
    assert [v.period.end for v in reduced.values] == [
        date(2026, 6, 30),
        date(2026, 7, 31),
        date(2026, 8, 31),
    ]
    june = [v.value for v in values if v.period.end.month == 6]
    assert reduced.values[0].value == pytest.approx(sum(june) / len(june))
    assert reduced.values[0].period.frequency is Frequency.MONTHLY
    assert reduced.label == "EVDS:TP.DK.USD.A.YTL monthly average"
    # Only the month the column ends inside is reported as resting on part of a month.
    assert reduced.incomplete == (date(2026, 8, 31),)
    coverage = reduced.transformation.parameters["coverage"]
    assert coverage["2026-06-30"] == {"expected": 22, "observed": 22}
    assert coverage["2026-08-31"] == {"expected": 21, "observed": 12}
    assert reduced.transformation.parameters["method"] == "daily-to-monthly-v1"
    last = resample_column(
        values,
        replace(DAILY_RATE, aggregation=Aggregation.LAST),
        column_label="EVDS:TP.DK.USD.A.YTL",
        assignment=None,
    )
    assert [v.value for v in last.values] == [30.0, 31.0, 18.0]


def test_a_monthly_column_is_never_spread_onto_days():
    monthly = replace(DAILY_RATE, frequency=Frequency.MONTHLY)
    with pytest.raises(ResampleRefused, match="never spread onto finer periods"):
        resample_column(
            daily_column(date(2026, 6, 1), date(2026, 6, 5)),
            monthly,
            column_label="x",
            assignment=None,
        )


def test_a_served_weekly_rate_table_is_turned_monthly(tmp_path):
    """Turn 1 publishes the reviewed weekly housing-loan rate; turn 2 makes it monthly."""
    from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
    from test_evds_load import FakeSource
    from test_series_inspection import SQL

    from kkb_agent.api.prepared import PreparedRunner
    from kkb_agent.ingest.evds_load import ingest_series
    from kkb_agent.ingest.evds_request import EvdsWindow
    from kkb_agent.lakehouse import open_lakehouse
    from kkb_agent.llm import scripted

    weekly = "EVDS:TP.KTF12"
    root = tmp_path / "prepared"
    seed_prepared(root)
    with open_lakehouse(root) as lake:
        ingest_series(
            lake,
            "TP.KTF12",
            EvdsWindow(start=date(2026, 1, 1), end=date(2026, 3, 31)),
            retrieve=FakeSource(),
        )
    # A weekly period keeps its calendar only when the query selects its anchor.
    weekly_sql = SQL.replace(TOTAL, weekly).replace("s.observation ", "s.observation,s.anchor ")
    assert "s.anchor" in weekly_sql
    table = {"step_id": "a", "tool": "lakehouse", "arguments": {"sql": weekly_sql}}
    resample = {
        "step_id": "b",
        "tool": "table_transform",
        "arguments": {
            "operation": "resample",
            "source": "analiz_1",
            "column": weekly,
            "week_assignment": "by_end",
        },
    }
    runner = PreparedRunner(
        scripted(proposal(table), "Tablo hazır.", proposal(resample), "Aylık hale getirildi."),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
    )
    sid = uuid4().hex

    first = runner(sid, uuid4().hex, "Haftalık konut kredisi faizini getir.")
    second = runner(sid, uuid4().hex, "Bu haftalık faizi aylığa çevir.")

    assert first.status.value == "accepted", first
    assert second.status.value == "accepted", second
    monthly = [c for c in second.result.cells if c.period.frequency == "monthly"]
    assert monthly and {c.period.end.month for c in monthly} <= {1, 2, 3}
    weekly_cells = [c for c in second.result.cells if c.period.frequency == "weekly"]
    assert len(weekly_cells) == len(first.result.cells)  # the weekly column is unchanged


def test_a_period_gold_cannot_hold_is_skipped_not_raised():
    """Regression: an unknown-frequency table used to raise while being written to gold.

    A served query now takes its calendar from the series declaration, so the
    unknown calendar is built here directly.
    """
    from kkb_agent.core import AnalyticalResult, ResultEvidence, ResultKind, ResultStatus
    from kkb_agent.lakehouse.gold import gold_from_result

    unknown = [
        value.model_copy(
            update={
                "period": Period(
                    start=value.period.start, end=value.period.end, frequency=Frequency.UNKNOWN
                )
            }
        )
        for value in column([1.0, 2.0])
    ]
    result = AnalyticalResult(
        result_id="r",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        method="sql",
        values=unknown,
        evidence=ResultEvidence(input_refs=["silver_observations"], lineage_node="n"),
    )
    assert gold_from_result(result, table_id="analiz_1", lineage=None) is None
