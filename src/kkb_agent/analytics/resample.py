"""A weekly or daily column of a published table, reduced onto months (M12-08 at runtime).

A weekly rate and a monthly balance cannot sit in one table, or be compared,
until one of them is reduced. `lakehouse.alignment.to_monthly` has always done
that reduction; this module applies it to a column of a published table so the
result can be joined with monthly tables. A daily column (an exchange rate, DEC-177) is
reduced the same way, with nothing to decide: a day lies in exactly one month.

Two things stay decisions, never defaults. How weeks become a month is the
series' **declared** aggregation (a rate is averaged, a flow summed, a stock
taken at its last week) — a series whose aggregation is unknown is refused.
Which month a straddling week belongs to is the **caller's** stated policy. And
each month says how many of its weeks were observed: a month averaged from one
Friday is not the claim a month averaged from five is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from pydantic import JsonValue

from kkb_agent.core import Aggregation, Frequency, Period, ResultValue, TransformationRecord
from kkb_agent.lakehouse.alignment import (
    AlignmentError,
    WeekAssignment,
    reducer_for,
    to_monthly,
)
from kkb_agent.lakehouse.periods import expected_periods, month_end
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD: Final = "weekly-to-monthly-v1"
DAILY_METHOD: Final = "daily-to-monthly-v1"
_DAILY: Final = (Frequency.DAILY, Frequency.BUSINESS_DAY)


class ResampleRefused(ValueError):
    """The column cannot be reduced as asked. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Resampled:
    values: tuple[ResultValue, ...]
    incomplete: tuple[date, ...]
    transformation: TransformationRecord
    label: str


def _weekdays(start: date, end: date) -> int:
    return sum(
        (start + timedelta(days=offset)).weekday() < 5 for offset in range((end - start).days + 1)
    )


def _days_to_months(
    column: Sequence[ResultValue], semantics: SeriesSemantics, column_label: str
) -> Resampled:
    """Monthly values for a daily column: each day counts in the month it lies in.

    Coverage says how many weekdays a month has and how many days carried a value (a source
    lists a holiday without one). A month is reported incomplete only when the column itself
    begins or ends inside it, which is what makes its value rest on part of a month.
    """
    reducer = reducer_for(semantics.aggregation)
    if reducer is None:
        raise ResampleRefused(
            f"{column_label} declares no aggregation, so there is no stated way to turn its "
            "days into a month"
        )
    template = column[0]
    months: dict[date, list[tuple[date, float]]] = {}
    for value in column:
        if value.period is None or value.period.frequency not in _DAILY:
            raise ResampleRefused(f"{column_label} is not a daily column")
        if value.period.start != value.period.end:
            raise ResampleRefused(f"{column_label} has a period longer than a day")
        if (value.unit, value.scale, value.measure) != (
            template.unit,
            template.scale,
            template.measure,
        ):
            raise ResampleRefused(f"{column_label} mixes units, scales or measures")
        day = value.period.end
        months.setdefault(month_end(day.year, day.month), []).append((day, value.value))
    days = sorted(day for entries in months.values() for day, _ in entries)
    if len(days) != len(set(days)):
        raise ResampleRefused(f"{column_label} holds a day twice")
    first, last = days[0], days[-1]
    label = f"{column_label} monthly {semantics.aggregation.value}"
    values: list[ResultValue] = []
    coverage: dict[str, JsonValue] = {}
    incomplete: list[date] = []
    for target in sorted(months):
        entries = sorted(months[target])
        begin = date(target.year, target.month, 1)
        expected = len(expected_periods(semantics.frequency, begin, target))
        coverage[target.isoformat()] = {"expected": expected, "observed": len(entries)}
        if len(entries) < expected:
            incomplete.append(target)
        values.append(
            ResultValue(
                label=label,
                value=reducer([number for _, number in entries]),
                unit=template.unit,
                scale=template.scale,
                measure=template.measure,
                period=Period(start=begin, end=target, frequency=Frequency.MONTHLY),
            )
        )
    transformation = TransformationRecord(
        operation="resample",
        parameters={
            "operation": "align_daily_to_monthly",
            "aggregation": semantics.aggregation.value,
            "frequency": semantics.frequency.value,
            "requested_start": first.isoformat(),
            "requested_end": last.isoformat(),
            "method": DAILY_METHOD,
            "coverage": coverage,
        },
        input_refs=[column_label],
        output_ref=label,
    )
    return Resampled(tuple(values), tuple(incomplete), transformation, label)


def resample_column(
    column: Sequence[ResultValue],
    semantics: SeriesSemantics,
    *,
    column_label: str,
    assignment: WeekAssignment | None,
) -> Resampled:
    """Monthly values for a weekly column, by its declared aggregation."""
    if not column:
        raise ResampleRefused(f"No values are labelled {column_label!r}")
    if semantics.frequency in _DAILY:
        return _days_to_months(column, semantics, column_label)
    if semantics.frequency is not Frequency.WEEKLY:
        raise ResampleRefused(
            f"{column_label} is {semantics.frequency.value}; only a weekly or a daily column is "
            "reduced onto months here, and a coarser column is never spread onto finer periods"
        )
    if semantics.aggregation is Aggregation.UNKNOWN:
        raise ResampleRefused(
            f"{column_label} declares no aggregation, so there is no stated way to turn its "
            "weeks into a month"
        )
    if assignment is None:
        raise ResampleRefused(
            f"{column_label} is weekly: state week_assignment (by_end or by_majority), which "
            "month a week spanning two months belongs to is never defaulted"
        )
    observations: list[Observation] = []
    template = column[0]
    for value in column:
        if value.period is None or value.period.frequency is not Frequency.WEEKLY:
            raise ResampleRefused(f"{column_label} is not a weekly column")
        if (value.unit, value.scale, value.measure) != (
            template.unit,
            template.scale,
            template.measure,
        ):
            raise ResampleRefused(f"{column_label} mixes units, scales or measures")
        observations.append(Observation(value.period.start, value.period.end, value.value))
    # The window runs over the months the weeks end in: starting at the first week's
    # start would request a month that holds none of this column's weeks.
    first_end = min(item.period_end for item in observations)
    start = date(first_end.year, first_end.month, 1)
    end = max(item.period_end for item in observations)
    try:
        aligned = to_monthly(
            observations,
            requested_start=start,
            requested_end=end,
            frequency=Frequency.WEEKLY,
            aggregation=semantics.aggregation,
            anchor=semantics.anchor,
            assignment=assignment,
        )
    except AlignmentError as error:
        raise ResampleRefused(str(error)) from error

    label = f"{column_label} monthly {semantics.aggregation.value} ({assignment.value})"
    values = tuple(
        ResultValue(
            label=label,
            value=item.value,
            unit=template.unit,
            scale=template.scale,
            measure=template.measure,
            period=Period(
                start=item.period_start, end=item.period_end, frequency=Frequency.MONTHLY
            ),
        )
        for item in aligned.observations
        if item.value is not None
    )
    incomplete = tuple(aligned.incomplete_periods())
    transformation = TransformationRecord(
        operation="resample",
        parameters={
            **aligned.method,
            "method": METHOD,
            "coverage": {
                end.isoformat(): {"expected": count.expected, "observed": count.observed}
                for end, count in sorted(aligned.coverage.items())
            },
        },
        input_refs=[column_label],
        output_ref=label,
    )
    return Resampled(values, incomplete, transformation, label)
