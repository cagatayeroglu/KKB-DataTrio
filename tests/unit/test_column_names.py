"""A column named by the series it holds is found in every table operation.

Live 2026-09-21 (reference turn 1): the planner read a weekly rate, reduced it to months
and joined it to the balance with `columns=["EVDS:TP.KTF12"]`, as the prompt tells it to
name a column a step of its own plan adds. The reduction had renamed the column
"EVDS:TP.KTF12 monthly average (by_end)"; the join was refused, the next step found an
empty table, and the turn paid a second planner call (250 s) for a simpler plan.
"""

from __future__ import annotations

import pytest
from test_turn_two import credit_column

from kkb_agent.analytics.table_series import join_monthly_table
from kkb_agent.core import AnalyticalResult, ResultEvidence, ResultKind, ResultStatus, StockFlow
from kkb_agent.tools.table_transform import ColumnUnknown, _column_of, _named

RATE = "EVDS:TP.KTF12"
REDUCED = f"{RATE} monthly average (by_end)"


def table(*columns):
    return AnalyticalResult(
        result_id="fixture:table",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method="synthetic",
        evidence=ResultEvidence(input_refs=["synthetic fixture"]),
        values=[value for column in columns for value in column],
    )


def rate(label, levels=(8, 7, 7, 6, 5, 6)):
    return credit_column(list(levels), label=label, unit="percent", measure=StockFlow.RATE)


def test_the_series_id_finds_the_column_a_reduction_renamed():
    reduced = table(credit_column([10, 9, 10, 10, 8, 9]), rate(REDUCED))
    label, note = _column_of(reduced, RATE)
    assert label == REDUCED and note is not None and RATE in note
    # The exact label is still the exact label, and says nothing about itself.
    assert _column_of(reduced, REDUCED) == (REDUCED, None)


def test_a_column_derived_from_it_does_not_make_the_name_ambiguous():
    derived = table(
        rate(REDUCED), rate(f"{REDUCED} month-over-month change", (0, -1, 0, -1, -1, 1))
    )
    assert _column_of(derived, RATE)[0] == REDUCED


def test_two_different_columns_of_one_series_are_still_refused_by_name():
    both = table(rate(REDUCED), rate(f"{RATE} monthly last (by_end)"))
    with pytest.raises(ColumnUnknown) as refused:
        _column_of(both, RATE)
    assert REDUCED in str(refused.value)  # the refusal lists what the table holds
    assert _named(both, RATE) == RATE  # an operation with its own refusal keeps the name


def test_a_join_that_names_the_reduced_rate_by_its_series_id_joins_it():
    balance = table(credit_column([10, 9, 10, 10, 8, 9]))
    reduced = table(rate(REDUCED))
    joined = join_monthly_table(
        balance, reduced, other_name="rate_monthly", columns=(_named(reduced, RATE),)
    )
    # What a join returns is what it added: the six months of the rate, under its own label.
    assert [value.label for value in joined.values] == [REDUCED] * 6
    # Named as the planner named it, the same join is refused - which is what happened.
    from kkb_agent.analytics.table_series import SeriesAdditionRefused

    with pytest.raises(SeriesAdditionRefused):
        join_monthly_table(balance, reduced, other_name="rate_monthly", columns=(RATE,))
