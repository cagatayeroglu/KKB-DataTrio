"""Independent arithmetic and shape oracles for bounded table transforms."""

from datetime import date

import pytest

from kkb_agent.analytics.table_shape import (
    REBASE_FORMULA,
    TableShapeRefused,
    align_periods,
    filter_periods,
    period_change,
    rebase_index,
)
from kkb_agent.core import (
    DIMENSIONLESS,
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

MONTHS = (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31))


def cell(label: str, end: date, value: float, *, index: bool = False) -> ResultValue:
    return ResultValue(
        label=label,
        value=value,
        unit="index" if index else "TRY",
        scale=Scale.ONE if index else Scale.MILLION,
        measure=StockFlow.INDEX if index else StockFlow.STOCK,
        period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
    )


def source() -> AnalyticalResult:
    values = [
        ResultValue(
            label="old summary",
            value=3.0,
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            measure=StockFlow.STOCK,
        ),
        *(
            cell("index", end, value, index=True)
            for end, value in zip(MONTHS, (80.0, 100.0, 120.0), strict=True)
        ),
        cell("amount", MONTHS[0], 10.0),
        cell("amount", MONTHS[2], 30.0),
        *(
            cell("untouched", end, value)
            for end, value in zip(MONTHS, (1.0, 2.0, 3.0), strict=True)
        ),
    ]
    return AnalyticalResult(
        result_id="fixture-table",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="fixture",
        values=values,
        coverage=Period(start=date(2024, 1, 1), end=MONTHS[-1], frequency=Frequency.MONTHLY),
        evidence=ResultEvidence(input_refs=["synthetic-independent-fixture"]),
    )


def test_rebase_uses_hand_calculated_reference_ratio_and_keeps_source_immutable():
    original = source()
    before = original.model_dump_json()
    result = rebase_index(
        original,
        column_label="index",
        reference_period=MONTHS[1],
        new_base=200.0,
    )
    assert [value.value for value in result.values] == [160.0, 200.0, 240.0]
    assert [value.period.end for value in result.values] == list(MONTHS)
    assert all(
        value.unit == "index" and value.measure is StockFlow.INDEX for value in result.values
    )
    assert result.transformation.parameters == {
        "formula": REBASE_FORMULA,
        "column": "index",
        "reference_period": "2024-02-29",
        "reference_value": 100.0,
        "new_base": 200.0,
        "fill": "none",
    }
    assert original.model_dump_json() == before


def test_inner_and_left_alignment_preserve_order_values_and_missingness():
    original = source()
    inner = align_periods(
        original,
        columns=("index", "amount"),
        join="inner",
        anchor_column=None,
    )
    assert {value.period.end for value in inner.values} == {MONTHS[0], MONTHS[2]}
    assert inner.values == tuple(
        value
        for value in original.values
        if value.period is not None and value.period.end in {MONTHS[0], MONTHS[2]}
    )
    assert inner.transformation.parameters["join"] == "inner_exact_period"
    assert inner.transformation.parameters["fill"] == "none"

    left = align_periods(
        original,
        columns=("index", "amount"),
        join="left",
        anchor_column="index",
    )
    assert {value.period.end for value in left.values} == set(MONTHS)
    assert not any(
        value.label == "amount" and value.period.end == MONTHS[1] for value in left.values
    )
    assert left.transformation.parameters["missing_selected_cells"] == 1


def test_period_filter_is_inclusive_and_drops_stale_summaries_without_fabrication():
    original = source()
    result = filter_periods(
        original,
        start_period=MONTHS[1],
        end_period=MONTHS[2],
    )
    assert result.values == tuple(
        value
        for value in original.values
        if value.period is not None and value.period.end in {MONTHS[1], MONTHS[2]}
    )
    assert result.coverage.start == date(2024, 2, 1)
    assert result.coverage.end == MONTHS[2]
    assert result.dropped_non_period_values == 1
    assert result.transformation.parameters["predicate"] == "period_end_inclusive"


@pytest.mark.parametrize("case", ["not_index", "missing_reference", "zero", "duplicate"])
def test_rebase_rejects_incompatible_inputs(case):
    original = source()
    if case == "not_index":
        column = next(value for value in original.values if value.label == "amount")
        original = original.model_copy(update={"values": [column, *original.values]})
        label = "amount"
    elif case == "missing_reference":
        label = "index"
    elif case == "zero":
        label = "index"
        original = original.model_copy(
            update={
                "values": [
                    value.model_copy(update={"value": 0.0})
                    if value.label == label and value.period.end == MONTHS[0]
                    else value
                    for value in original.values
                ]
            }
        )
    else:
        label = "index"
        duplicate = next(value for value in original.values if value.label == label)
        original = original.model_copy(update={"values": [*original.values, duplicate]})
    reference = date(2023, 12, 31) if case == "missing_reference" else MONTHS[1]
    with pytest.raises(TableShapeRefused):
        rebase_index(original, column_label=label, reference_period=reference, new_base=100.0)


@pytest.mark.parametrize("case", ["unknown_column", "no_overlap", "bad_anchor", "empty_range"])
def test_shape_changes_fail_closed(case):
    original = source()
    if case == "unknown_column":
        call = lambda: align_periods(  # noqa: E731
            original, columns=("index", "absent"), join="inner", anchor_column=None
        )
    elif case == "no_overlap":
        shifted = [
            cell("later", date(2025, 1, 31), 1.0),
            cell("later", date(2025, 2, 28), 2.0),
        ]
        original = original.model_copy(update={"values": [*original.values, *shifted]})
        call = lambda: align_periods(  # noqa: E731
            original, columns=("index", "later"), join="inner", anchor_column=None
        )
    elif case == "bad_anchor":
        call = lambda: align_periods(  # noqa: E731
            original, columns=("index", "amount"), join="left", anchor_column=None
        )
    else:
        call = lambda: filter_periods(  # noqa: E731
            original, start_period=date(2025, 1, 1), end_period=None
        )
    with pytest.raises(TableShapeRefused):
        call()


def by_end(values):
    return {value.period.end: value.value for value in values}


def test_change_adds_differences_and_percentages_by_hand():
    """untouched = 1, 2, 3: differences 1 and 1; percentages 100 and 50."""
    difference = period_change(source(), column_label="untouched", kind="difference")
    assert by_end(difference.values) == {MONTHS[1]: 1.0, MONTHS[2]: 1.0}
    assert difference.label == "untouched change (lag 1)"
    assert {(v.unit, v.scale, v.measure) for v in difference.values} == {
        ("TRY", Scale.MILLION, StockFlow.STOCK)
    }
    percent = period_change(source(), column_label="untouched", kind="percent")
    assert by_end(percent.values) == {MONTHS[1]: 100.0, MONTHS[2]: 50.0}
    assert percent.label == "untouched % change (lag 1)"
    assert {(v.unit, v.scale, v.measure) for v in percent.values} == {
        ("percent", Scale.ONE, StockFlow.RATE)
    }
    assert percent.largest_increase == MONTHS[1] and percent.largest_decrease is None
    record = percent.transformation
    assert record.operation == "change" and record.parameters["fill"] == "none"
    assert record.parameters["periods_without_predecessor"] == 1


def test_an_index_changes_in_index_points_and_a_gap_is_never_bridged():
    index = period_change(source(), column_label="index", kind="difference")
    assert by_end(index.values) == {MONTHS[1]: 20.0, MONTHS[2]: 20.0}
    assert {(v.unit, v.scale) for v in index.values} == {("index point", Scale.ONE)}
    # "amount" has January and March only: March's predecessor is two months away.
    with pytest.raises(TableShapeRefused, match="no period with a usable predecessor"):
        period_change(source(), column_label="amount", kind="difference")


def test_change_refuses_what_it_cannot_state():
    table = source()
    rate = table.model_copy(
        update={
            "values": [
                value.model_copy(
                    update={"unit": "percent", "scale": Scale.ONE, "measure": StockFlow.RATE}
                )
                if value.label == "untouched"
                else value
                for value in table.values
            ]
        }
    )
    with pytest.raises(TableShapeRefused, match="use kind=difference"):
        period_change(rate, column_label="untouched", kind="percent")
    points = period_change(rate, column_label="untouched", kind="difference")
    assert {v.unit for v in points.values} == {"percentage point"}
    with pytest.raises(TableShapeRefused, match="No values are labelled"):
        period_change(table, column_label="absent", kind="difference")
    with pytest.raises(TableShapeRefused, match="too few rows"):
        period_change(table, column_label="untouched", kind="difference", lag=3)
    with pytest.raises(TableShapeRefused, match="lag must be"):
        period_change(table, column_label="untouched", kind="difference", lag=13)
    once = table.model_copy(
        update={
            "values": [
                *table.values,
                *period_change(table, column_label="untouched", kind="percent").values,
            ]
        }
    )
    with pytest.raises(TableShapeRefused, match="already holds that change column"):
        period_change(once, column_label="untouched", kind="percent")


def test_a_nonpositive_predecessor_leaves_the_percentage_empty():
    table = source()
    zeroed = table.model_copy(
        update={
            "values": [
                value.model_copy(update={"value": 0.0})
                if value.label == "untouched" and value.period.end == MONTHS[0]
                else value
                for value in table.values
            ]
        }
    )
    percent = period_change(zeroed, column_label="untouched", kind="percent")
    assert by_end(percent.values) == {MONTHS[2]: 50.0}
    assert percent.transformation.parameters["periods_with_nonpositive_predecessor"] == 1
