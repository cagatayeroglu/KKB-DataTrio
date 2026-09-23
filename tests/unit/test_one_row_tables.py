"""QA-36: a table of one month is a table; a lone cell beside several rows is not.

Two tables of one month each were refused as having "at least two rows" too few, so a
same-month join or a filter of a one-month table could not be made at all. The rule
every table operation now reads (`table_columns`) keeps what the old one protected: a
single-period metric beside real columns adds no row, cells on different months make no
row, and an operation that needs an earlier observation still needs one.
"""

from datetime import date

import pytest
from test_compute_contracts import FEB, JAN, MAR, cell, table

from kkb_agent.analytics.table_series import SeriesAdditionRefused, join_monthly_table
from kkb_agent.analytics.table_shape import (
    TableShapeRefused,
    filter_periods,
    period_change,
    table_columns,
)
from kkb_agent.core import StockFlow


def test_the_rule_itself():
    several = {"a": {JAN, FEB}, "total": {MAR}}
    assert table_columns(several) == {"a"}  # the lone cell is a metric about the table
    assert table_columns({"a": {JAN}, "b": {JAN}}) == {"a", "b"}  # one row, two columns
    assert table_columns({"a": {JAN}, "b": {FEB}}) == set()  # no row is said


def test_two_one_month_tables_join_keeping_each_columns_own_unit():
    rate = cell("oran", JAN, 42.0, measure=StockFlow.RATE)
    joined = join_monthly_table(table(cell("tutar", JAN, 10.0)), table(rate), other_name="a2")
    (added,) = joined.values
    assert (added.label, added.value, added.unit) == ("oran", 42.0, "percent")
    assert joined.transformation.parameters["matched_rows"] == {"oran": 1}


def test_a_month_the_one_row_table_lacks_is_not_joined_onto_it():
    with pytest.raises(SeriesAdditionRefused, match="does not hold"):
        join_monthly_table(table(cell("a", JAN, 10.0)), table(cell("b", FEB, 20.0)), other_name="x")


def test_one_shared_month_is_still_not_a_column_of_a_table_of_several():
    source = table(cell("a", JAN, 1.0), cell("a", FEB, 2.0), cell("a", MAR, 3.0))
    with pytest.raises(SeriesAdditionRefused, match="fewer than two months"):
        join_monthly_table(source, table(cell("b", JAN, 9.0)), other_name="x")


def test_a_one_month_table_can_be_filtered():
    shaped = filter_periods(
        table(cell("a", JAN, 10.0), cell("b", JAN, 20.0)), start_period=JAN, end_period=JAN
    )
    assert {(v.label, v.value) for v in shaped.values} == {("a", 10.0), ("b", 20.0)}


def test_cells_on_different_months_are_still_no_table():
    with pytest.raises(TableShapeRefused, match="no period table"):
        filter_periods(
            table(cell("a", JAN, 1.0), cell("b", FEB, 2.0)), start_period=JAN, end_period=None
        )


def test_a_change_still_needs_the_month_before():
    with pytest.raises(TableShapeRefused):
        period_change(table(cell("a", JAN, 10.0)), column_label="a", kind="difference", lag=1)


def test_a_lone_metric_beside_months_adds_no_row():
    source = table(
        cell("a", JAN, 1.0), cell("a", FEB, 2.0), cell("yıl sonu", date(2021, 12, 31), 9.0)
    )
    shaped = filter_periods(source, start_period=JAN, end_period=None)
    assert {v.label for v in shaped.values} == {"a"}
