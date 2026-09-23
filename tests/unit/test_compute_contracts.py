"""`table_compute`: what a computed column means, held by the tool, not by the model.

A group of maturities is a sum of columns, and B1 is built from such groups. These are
the tool's contracts — not rules about how the model works — so a sum is never a
column counted twice, a month quietly overwritten, a quarter paired with a month, a gap
read as zero, or a name that merges two columns; and a grouped column is a verifiable
table the next step can read.
"""

from __future__ import annotations

from datetime import date

import pytest
from test_base_month import DEC, FEB, JAN, MAR, SERIES, read, rig, transform  # noqa: F401

from kkb_agent.agent import ExecutionContext
from kkb_agent.agent.executor import ToolStatus
from kkb_agent.agent.verifier import result_faults
from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
)
from kkb_agent.tools.table_compute import make_table_compute_tool


def cell(
    label: str,
    end: date,
    value: float,
    *,
    start: date | None = None,
    frequency: Frequency = Frequency.MONTHLY,
    measure: StockFlow = StockFlow.STOCK,
) -> ResultValue:
    return ResultValue(
        label=label,
        value=value,
        unit="TRY" if measure is StockFlow.STOCK else "percent",
        scale=Scale.MILLION if measure is StockFlow.STOCK else Scale.ONE,
        measure=measure,
        period=Period(start=start or end.replace(day=1), end=end, frequency=frequency),
    )


def table(*values: ResultValue) -> AnalyticalResult:
    return AnalyticalResult(
        result_id="t",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=list(values),
        coverage=Period(start=date(2021, 1, 1), end=MAR, frequency=Frequency.MONTHLY),
        evidence=ResultEvidence(input_refs=["x"]),
    )


def compute(held: AnalyticalResult, **arguments):
    tool = make_table_compute_tool()
    return tool.run(
        tool.parse({"source": "a1", **arguments}), ExecutionContext("s", outputs={"a1": held})
    )


BANDS = table(
    cell("vadesiz", JAN, 10.0),
    cell("vadesiz", FEB, 11.0),
    cell("vadesiz", MAR, 12.0),
    cell("bir ay", JAN, 20.0),
    cell("bir ay", MAR, 22.0),
)


def refused(result, words: str) -> bool:
    return result.status is ToolStatus.FAILURE and words in result.warnings[0]


def test_a_column_named_twice_is_not_summed_twice():
    assert refused(
        compute(BANDS, label="g", operation="sum", columns=["vadesiz", "vadesiz"]),
        "birden çok kez",
    )


def test_a_period_held_twice_is_refused_not_overwritten():
    twice = table(*BANDS.values, cell("vadesiz", JAN, 99.0))
    assert refused(
        compute(twice, label="g", operation="sum", columns=["vadesiz", "bir ay"]),
        "aynı dönem iki kez",
    )


def test_a_quarter_is_not_paired_with_the_month_it_ends_in():
    mixed = table(
        cell("aylık", MAR, 5.0),
        cell("çeyreklik", MAR, 7.0, start=date(2021, 1, 1), frequency=Frequency.QUARTERLY),
    )
    assert refused(
        compute(mixed, label="g", operation="sum", columns=["aylık", "çeyreklik"]),
        "ortak bir dönemi yok",
    )


def test_a_missing_component_leaves_its_period_empty_and_says_which():
    done = compute(BANDS, label="kısa vade", operation="sum", columns=["vadesiz", "bir ay"])
    assert done.status is ToolStatus.SUCCESS
    made = [v for v in done.output.values if v.label == "kısa vade"]
    assert [(v.period.end, v.value) for v in made] == [(JAN, 30.0), (MAR, 34.0)]
    [note] = done.warnings
    assert "2021-02-28" in note and "sıfır sayılmadı" in note


def test_a_new_name_may_not_be_an_old_column():
    assert refused(
        compute(BANDS, label="vadesiz", operation="sum", columns=["vadesiz", "bir ay"]),
        "zaten bir sütunun adı",
    )


def test_rates_are_averaged_not_summed():
    rates = table(
        cell("oran a", JAN, 40.0, measure=StockFlow.RATE),
        cell("oran b", JAN, 44.0, measure=StockFlow.RATE),
    )
    assert refused(
        compute(rates, label="g", operation="sum", columns=["oran a", "oran b"]), "toplanmaz"
    )
    mean = compute(rates, label="ortalama", operation="mean", columns=["oran a", "oran b"])
    assert [v.value for v in mean.output.values if v.label == "ortalama"] == [42.0]


def test_an_arithmetic_period_without_its_other_side_is_named():
    done = compute(BANDS, label="fark", operation="subtract", left="vadesiz", right="bir ay")
    assert [v.period.end for v in done.output.values if v.label == "fark"] == [JAN, MAR]
    assert any("2021-02-28" in note for note in done.warnings)


def test_a_grouped_column_is_verifiable_and_keeps_its_base_through_the_chain(rig):  # noqa: F811
    """B1's chain: read with the base month, group, change, then show the asked months."""
    lake, workspace = rig
    window = read(lake, since=DEC)
    compute_tool = make_table_compute_tool(lake.connection)
    grouped = compute_tool.run(
        compute_tool.parse(
            {"source": "a1", "label": "toplam", "operation": "sum", "columns": list(SERIES)}
        ),
        ExecutionContext("soru", outputs={"a1": window}),
    )
    assert grouped.status is ToolStatus.SUCCESS
    assert grouped.output.tool == "table_compute"
    assert result_faults({"a2": grouped.output}, lake.connection) == {}
    context = ExecutionContext("soru", outputs={"a2": grouped.output})
    changed = transform(
        lake,
        workspace,
        context,
        operation="change",
        source="a2",
        column="toplam",
        kind="difference",
    )
    assert changed.status is ToolStatus.SUCCESS, changed.warnings
    context = ExecutionContext("soru", outputs={"a3": changed.output})
    shown = transform(
        lake,
        workspace,
        context,
        operation="filter",
        source="a3",
        start_period="2021-01-31",
        end_period="2021-03-31",
    ).output
    new = [v for v in shown.values if v.label == "toplam change (lag 1)"]
    assert [(v.period.end, v.value) for v in new] == [(JAN, 12.0), (FEB, 8.0), (MAR, 2.0)]
    assert DEC not in {v.period.end for v in shown.values}


def test_without_the_store_a_computed_column_is_still_computed():
    """The connection records trust; the arithmetic does not depend on it."""
    done = compute(BANDS, label="g", operation="sum", columns=["vadesiz", "bir ay"])
    assert done.status is ToolStatus.SUCCESS and done.output.run_id is None


@pytest.mark.parametrize("operation", ["min", "max"])
def test_min_and_max_of_like_columns(operation):
    done = compute(BANDS, label="uç", operation=operation, columns=["vadesiz", "bir ay"])
    expected = {"min": [10.0, 12.0], "max": [20.0, 22.0]}[operation]
    assert [v.value for v in done.output.values if v.label == "uç"] == expected
