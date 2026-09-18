"""to_flow: a declared cumulative column becomes per-period flow, and nothing else does."""

from dataclasses import replace
from datetime import date

import pytest
from test_breakpoint import SEMANTICS, months

from kkb_agent.analytics.accumulation import AccumulationRefused, to_flow_column
from kkb_agent.core import CumulativeKind, Frequency, Period, ResultValue, StockFlow

FLOW = replace(SEMANTICS, observation=StockFlow.FLOW, cumulative=CumulativeKind.YEARLY_RESET)


def column(values, semantics=FLOW, start=date(2025, 10, 31), label="TEST:issued"):
    return [
        ResultValue(
            label=label,
            value=value,
            unit=semantics.unit,
            scale=semantics.scale,
            measure=semantics.observation,
            period=Period(start=date(end.year, end.month, 1), end=end, frequency=Frequency.MONTHLY),
        )
        for end, value in zip(months(len(values), start), values, strict=True)
    ]


def test_a_yearly_reset_column_is_differenced_and_january_is_the_month_itself():
    # Oct..Mar: running totals that restart in January.
    flowed = to_flow_column(
        column([10.0, 25.0, 45.0, 7.0, 15.0, 30.0]), FLOW, column_label="TEST:issued"
    )
    by_end = {value.period.end: value.value for value in flowed.values}
    # October has no predecessor in the table, so it stays empty rather than 10.
    assert flowed.empty_periods == (date(2025, 10, 31),)
    assert by_end == {
        date(2025, 11, 30): 15.0,
        date(2025, 12, 31): 20.0,
        date(2026, 1, 31): 7.0,  # the year restarted: January is its own month
        date(2026, 2, 28): 8.0,
        date(2026, 3, 31): 15.0,
    }
    assert all(value.measure is StockFlow.FLOW for value in flowed.values)
    assert flowed.label == "TEST:issued flow (yearly_reset)"
    assert flowed.transformation.parameters["declared_cumulative"] == "yearly_reset"


def test_since_inception_needs_the_level_before_the_first_month():
    semantics = replace(FLOW, cumulative=CumulativeKind.SINCE_INCEPTION)
    values = column([100.0, 130.0, 170.0], semantics, start=date(2026, 1, 31))

    without = to_flow_column(values, semantics, column_label="TEST:issued")
    with_baseline = to_flow_column(values, semantics, column_label="TEST:issued", baseline=90.0)

    assert [v.value for v in without.values] == [30.0, 40.0]
    assert without.empty_periods == (date(2026, 1, 31),)
    assert [v.value for v in with_baseline.values] == [10.0, 30.0, 40.0]


@pytest.mark.parametrize(
    ("semantics", "needle"),
    [
        (SEMANTICS, "declared none"),  # a stock is not differenced because it could be
        (replace(FLOW, cumulative=CumulativeKind.UNKNOWN), "declared unknown"),
    ],
)
def test_only_the_declaration_decides(semantics, needle):
    with pytest.raises(AccumulationRefused, match=needle):
        to_flow_column(column([1.0, 2.0, 3.0], semantics), semantics, column_label="TEST:issued")


def test_a_column_that_disagrees_with_its_stored_meaning_is_refused():
    wrong_unit = [value.model_copy(update={"unit": "USD"}) for value in column([1.0, 2.0, 3.0])]
    with pytest.raises(AccumulationRefused, match="disagrees"):
        to_flow_column(wrong_unit, FLOW, column_label="TEST:issued")


def test_a_gap_is_not_bridged():
    values = column([10.0, 25.0, 45.0, 7.0])
    del values[1]  # November missing: December's predecessor is not adjacent
    flowed = to_flow_column(values, FLOW, column_label="TEST:issued")
    assert date(2025, 12, 31) in flowed.empty_periods
    assert [v.period.end for v in flowed.values] == [date(2026, 1, 31)]


def test_the_planner_can_ask_for_it_and_its_description_says_when():
    from kkb_agent.tools.table_transform import TableTransformArguments

    parsed = TableTransformArguments.model_validate(
        {"operation": "to_flow", "source": "analiz_1", "column": "TEST:issued"}
    )
    assert parsed.root.operation == "to_flow"
    with pytest.raises(ValueError):
        TableTransformArguments.model_validate(
            {"operation": "to_flow", "source": "analiz_1", "column": "x", "baseline": 1}
        )


def test_a_served_turn_refuses_a_series_the_catalog_does_not_declare_cumulative(tmp_path):
    """Every reviewed series today is declared `none` or `unknown`.

    So in the served runtime the correct outcome of "make this monthly flow" on the
    credit balance is a refusal with its reason, and the published table stays
    exactly as it was: a balance that only looks cumulative is not differenced.
    """
    from uuid import uuid4

    from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
    from test_series_inspection import SQL

    from kkb_agent.api.prepared import PreparedRunner
    from kkb_agent.llm import scripted

    root = tmp_path / "prepared"
    seed_prepared(root)
    table = {"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}
    flow = {
        "step_id": "b",
        "tool": "table_transform",
        "arguments": {"operation": "to_flow", "source": "analiz_1", "column": TOTAL},
    }
    provider = scripted(proposal(table), "Tablo hazır.", proposal(flow), "Aylık akım eklendi.")
    runner = PreparedRunner(
        provider, root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex

    first = runner(sid, uuid4().hex, "Konut kredisi tablosunu getir.")
    second = runner(sid, uuid4().hex, "Bu seriyi aylık akıma çevir.")

    assert first.status.value == "accepted"
    assert second.status.value == "abstained" and second.result is None
    # The drafted "flow added" sentence never reaches the person.
    assert "Aylık akım eklendi." not in second.text
    assert first.result.cells and [c.value for c in first.result.cells] == [100.0, 120.0, 150.0]
