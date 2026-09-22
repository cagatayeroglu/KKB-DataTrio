"""Independent arithmetic and shape oracles for bounded table transforms."""

from datetime import date

import pytest

from kkb_agent.analytics.table_shape import (
    REBASE_FORMULA,
    TableShapeRefused,
    align_periods,
    combine_columns,
    filter_periods,
    names_only_excluded_months,
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


def test_a_warning_about_months_outside_the_range_does_not_apply_to_it():
    """A table filtered to 2025 kept warning about a month in 2026 (finding L2-4)."""
    year = Period(start=date(2025, 1, 1), end=date(2025, 12, 31), frequency=Frequency.MONTHLY)
    left_out = "1 month(s) not yet ended at retrieval were left out of the monthly rows (2026-09)"
    assert names_only_excluded_months(left_out, year) is True
    # One named month inside the range keeps the whole warning.
    assert names_only_excluded_months("2 month(s) were left out (2025-12, 2026-09)", year) is False
    # A warning about the table itself names no month and always travels.
    assert (
        names_only_excluded_months(
            "Column 'clval' has 3 empty month(s); those cells are empty", year
        )
        is False
    )


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
    assert percent.largest_increase == (MONTHS[1],) and percent.largest_decrease == ()
    # A tie is several answers: both months rose by exactly 1.
    assert difference.largest_increase == (MONTHS[1], MONTHS[2])
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


def grouped(label="second", values=(4.0, 5.0, 6.0), **update):
    """The fixture table plus one more million-TRY stock column, as a maturity bucket is."""
    table = source()
    added = [
        cell(label, end, value).model_copy(update=update)
        for end, value in zip(MONTHS, values, strict=True)
    ]
    return table.model_copy(update={"values": [*table.values, *added]})


def test_combine_sums_the_named_columns_cell_by_cell_and_leaves_the_source_alone():
    """untouched = 1, 2, 3 and second = 4, 5, 6: the group totals are 5, 7 and 9."""
    original = grouped()
    before = original.model_dump_json()
    result = combine_columns(original, columns=("untouched", "second"))
    assert by_end(result.values) == {MONTHS[0]: 5.0, MONTHS[1]: 7.0, MONTHS[2]: 9.0}
    assert {(v.unit, v.scale, v.measure) for v in result.values} == {
        ("TRY", Scale.MILLION, StockFlow.STOCK)
    }
    assert result.empty_periods == ()
    record = result.transformation
    assert record.operation == "combine"
    assert record.parameters["columns"] == ["untouched", "second"]
    assert record.parameters["period_rows"] == 3
    assert record.parameters["periods_missing_a_column"] == 0
    assert record.parameters["fill"] == "none"
    assert original.model_dump_json() == before


def test_a_period_one_column_lacks_is_left_empty_rather_than_counted_as_zero():
    """amount has January and March only: February's group is not 2 on its own."""
    result = combine_columns(source(), columns=("amount", "untouched"))
    assert by_end(result.values) == {MONTHS[0]: 11.0, MONTHS[2]: 33.0}
    assert result.empty_periods == (MONTHS[1],)
    assert result.transformation.parameters["periods_missing_a_column"] == 1
    assert result.transformation.parameters["period_rows"] == 2


def test_the_reader_names_the_group_or_the_summed_labels_do():
    """Live 2026-09-22: the reader asked for "3 aya kadar TP mevduat", not for "a + b"."""
    named = combine_columns(
        grouped(), columns=("untouched", "second"), label="3 aya kadar TP mevduat"
    )
    assert named.label == "3 aya kadar TP mevduat"
    assert {value.label for value in named.values} == {"3 aya kadar TP mevduat"}
    assert named.transformation.output_ref == "3 aya kadar TP mevduat"
    # No label: the summed labels joined in the order the reader gave them, not sorted.
    assert combine_columns(grouped(), columns=("second", "untouched")).label == (
        "second + untouched"
    )
    assert combine_columns(grouped(), columns=("untouched", "second")).label == (
        "untouched + second"
    )


def quarterly(label="second", values=(4.0, 5.0, 6.0)):
    table = source()
    added = [
        cell(label, end, value).model_copy(
            update={
                "period": Period(start=end.replace(day=1), end=end, frequency=Frequency.QUARTERLY)
            }
        )
        for end, value in zip(MONTHS, values, strict=True)
    ]
    return table.model_copy(update={"values": [*table.values, *added]})


@pytest.mark.parametrize(
    ("case", "match"),
    [
        ("unknown_column", "No values are labelled"),
        ("other_unit", "do not share one unit"),
        ("other_scale", "do not share one unit"),
        ("other_measure", "do not share one unit"),
        ("rate", "not summable"),
        ("mixed_frequency", "mix period frequencies"),
        ("one_column", "at least two column labels"),
        ("duplicate_column", "not summed twice"),
        ("label_exists", "already holds a column labelled"),
    ],
)
def test_combine_refuses_what_it_cannot_add_up(case, match):
    table = grouped()
    columns = ("untouched", "second")
    label = None
    if case == "unknown_column":
        columns = ("untouched", "absent")
    elif case == "other_unit":
        table = grouped(unit="USD")
    elif case == "other_scale":
        table = grouped(scale=Scale.THOUSAND)
    elif case == "other_measure":
        table = grouped(measure=StockFlow.FLOW)
    elif case == "rate":
        # Both columns are rates, so they share their semantics; a total of two rates
        # is still not a quantity (StockFlow says so outright).
        table = grouped(unit="percent", scale=Scale.ONE, measure=StockFlow.RATE)
        table = table.model_copy(
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
    elif case == "mixed_frequency":
        table = quarterly()
    elif case == "one_column":
        columns = ("untouched",)
    elif case == "duplicate_column":
        columns = ("untouched", "untouched")
    else:
        label = "amount"
    with pytest.raises(TableShapeRefused, match=match):
        combine_columns(table, columns=columns, label=label)


def test_a_column_without_a_stated_unit_still_has_a_percent_change():
    """Live J3 (2026-09-19): the BIST endpoint's `clval` states no unit; percent needs none."""
    table = source()
    unitless = table.model_copy(
        update={
            "values": [
                value.model_copy(update={"unit": None, "scale": None, "measure": None})
                if value.label == "untouched"
                else value
                for value in table.values
            ]
        }
    )
    percent = period_change(unitless, column_label="untouched", kind="percent")
    assert by_end(percent.values) == {MONTHS[1]: 100.0, MONTHS[2]: 50.0}
    assert {(v.unit, v.scale) for v in percent.values} == {("percent", Scale.ONE)}
    difference = period_change(unitless, column_label="untouched", kind="difference")
    assert by_end(difference.values) == {MONTHS[1]: 1.0, MONTHS[2]: 1.0}
    assert {(v.unit, v.scale) for v in difference.values} == {(None, None)}
