"""A weekly column of a published table, reduced onto months (M12-08 at runtime).

A weekly rate and a monthly balance cannot sit in one table, or be compared,
until one of them is reduced. `lakehouse.alignment.to_monthly` has always done
that reduction; this module applies it to a column of a published table so the
result can be joined with monthly tables.

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
from datetime import date
from typing import Final

from kkb_agent.core import Aggregation, Frequency, Period, ResultValue, TransformationRecord
from kkb_agent.lakehouse.alignment import AlignmentError, WeekAssignment, to_monthly
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD: Final = "weekly-to-monthly-v1"


class ResampleRefused(ValueError):
    """The column cannot be reduced as asked. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Resampled:
    values: tuple[ResultValue, ...]
    incomplete: tuple[date, ...]
    transformation: TransformationRecord
    label: str


def resample_column(
    column: Sequence[ResultValue],
    semantics: SeriesSemantics,
    *,
    column_label: str,
    assignment: WeekAssignment,
) -> Resampled:
    """Monthly values for a weekly column, by its declared aggregation."""
    if not column:
        raise ResampleRefused(f"No values are labelled {column_label!r}")
    if semantics.frequency is not Frequency.WEEKLY:
        raise ResampleRefused(
            f"{column_label} is {semantics.frequency.value}; only a weekly column is reduced "
            "onto months here"
        )
    if semantics.aggregation is Aggregation.UNKNOWN:
        raise ResampleRefused(
            f"{column_label} declares no aggregation, so there is no stated way to turn its "
            "weeks into a month"
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
