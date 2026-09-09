"""Frequency alignment (M12-08).

The reference scenario forces this: BDDK publishes housing credit monthly while
the EVDS housing-loan rate is weekly, anchored to Friday, and no monthly variant
of the rate exists. The two cannot be charted together without reducing one.

Two decisions are made explicit rather than assumed. Which month a week belongs
to when it straddles a boundary is a **policy the caller chooses**, because both
answers are defensible and only one can be right for a given question. And how
much of a target period was actually observed is **reported alongside the
value**, because a month averaged from one Friday and a month averaged from five
are not the same claim, and nothing downstream can tell them apart once the
count is discarded.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.periods import month_end, spine
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, check_period
from kkb_agent.lakehouse.store import Observation


class WeekAssignment(StrEnum):
    """Which month a week that straddles a boundary belongs to.

    BY_END follows how sources label a week and keeps periods contiguous.
    BY_MAJORITY puts the week where most of its days fell, which better reflects
    the underlying activity. Neither is universally correct, so the caller says
    which one this analysis used and the answer records it.
    """

    BY_END = "by_end"
    BY_MAJORITY = "by_majority"


class AlignmentError(ValueError):
    """Alignment was requested in a way the inputs or declaration do not support."""


@dataclass(frozen=True, slots=True)
class Coverage:
    """How much of a target period the source actually supplied."""

    expected: int
    observed: int

    @property
    def missing(self) -> int:
        return self.expected - self.observed

    @property
    def complete(self) -> bool:
        return self.expected > 0 and self.observed == self.expected


@dataclass(frozen=True, slots=True)
class Alignment:
    """Aligned observations plus the coverage and method behind them."""

    observations: list[Observation]
    coverage: dict[date, Coverage]
    method: dict[str, str]

    def incomplete_periods(self) -> list[date]:
        """Target periods that did not see every source period they expected."""
        return [end for end, count in sorted(self.coverage.items()) if not count.complete]


#: Declared aggregation -> the reduction it authorizes over one target period.
_REDUCERS: dict[Aggregation, Callable[[list[float]], float]] = {
    Aggregation.SUM: math.fsum,
    Aggregation.AVERAGE: statistics.fmean,
    Aggregation.FIRST: lambda values: values[0],
    Aggregation.LAST: lambda values: values[-1],
    Aggregation.MIN: min,
    Aggregation.MAX: max,
}


def assign_month(period_start: date, period_end: date, policy: WeekAssignment) -> date:
    """Month-end of the target period this source period is reduced into."""
    if policy is WeekAssignment.BY_END:
        return month_end(period_end.year, period_end.month)
    if period_start.month == period_end.month:
        return month_end(period_end.year, period_end.month)
    # Straddling: whichever month holds more of the week's days wins, and a
    # dead heat goes to the end, matching how the source labelled it.
    days_in_end_month = period_end.day
    days_in_start_month = (period_end - period_start).days + 1 - days_in_end_month
    if days_in_start_month > days_in_end_month:
        return month_end(period_start.year, period_start.month)
    return month_end(period_end.year, period_end.month)


def to_monthly(
    observations: Sequence[Observation],
    *,
    frequency: Frequency,
    aggregation: Aggregation,
    anchor: WeeklyAnchor | None = None,
    assignment: WeekAssignment,
) -> Alignment:
    """Reduce a weekly series onto monthly periods using its declared aggregation.

    `aggregation` must come from the series' recorded semantics. EVDS publishes
    it per series and marks its rates unsummable; passing SUM for a rate is a
    caller error, not something to silently permit.

    A target month with no observation at all is omitted rather than emitted as
    zero. A month with some observations is emitted with its coverage, so a
    reader can see it rested on one Friday instead of five.
    """
    if frequency is not Frequency.WEEKLY:
        raise AlignmentError(
            f"Only weekly series are reduced to monthly here, not {frequency.value}"
        )
    if anchor is None:
        raise AlignmentError("A weekly series needs its anchor weekday")
    reducer = _REDUCERS.get(aggregation)
    if reducer is None:
        raise AlignmentError("Alignment needs a declared aggregation; unknown is not a policy")
    if not observations:
        return Alignment([], {}, _method(aggregation, assignment, anchor))

    supplied = {item.period_end: item for item in observations}
    if len(supplied) != len(observations):
        raise AlignmentError("Duplicate source periods; resolve revisions before aligning")

    # Validate each input against the declared calendar first, so an off-anchor
    # date is named rather than surfacing later as an unexplained spine gap.
    for item in observations:
        try:
            check_period(
                SeriesSemantics(
                    unit="ratio",
                    scale=Scale.ONE,
                    frequency=frequency,
                    anchor=anchor,
                    observation=StockFlow.RATE,
                    cumulative=CumulativeKind.NONE,
                ),
                item.period_start,
                item.period_end,
            )
        except SemanticsError as error:
            raise AlignmentError(str(error)) from error

    # Expectation comes from the canonical spine, not from what arrived, so a
    # week missing from the middle is counted as missing rather than ignored.
    first, last = min(supplied), max(supplied)
    try:
        canonical = spine(frequency, first, last, anchor=anchor)
    except SemanticsError as error:
        raise AlignmentError(str(error)) from error

    expected: dict[date, int] = {}
    values: dict[date, list[float]] = {}
    for start, end in canonical:
        target = assign_month(start, end, assignment)
        expected[target] = expected.get(target, 0) + 1
        observed = supplied.get(end)
        if observed is not None and observed.value is not None:
            values.setdefault(target, []).append(observed.value)

    unexpected = set(supplied) - {end for _, end in canonical}
    if unexpected:
        # Unreachable while every input is on the anchor, kept as an invariant.
        raise AlignmentError(  # pragma: no cover
            f"{len(unexpected)} source period(s) are off the canonical spine"
        )

    aligned: list[Observation] = []
    coverage: dict[date, Coverage] = {}
    for target in sorted(expected):
        present = values.get(target)
        coverage[target] = Coverage(expected=expected[target], observed=len(present or ()))
        if present:
            aligned.append(
                Observation(date(target.year, target.month, 1), target, reducer(present))
            )
    return Alignment(aligned, coverage, _method(aggregation, assignment, anchor))


def _method(
    aggregation: Aggregation, assignment: WeekAssignment, anchor: WeeklyAnchor
) -> dict[str, str]:
    """The parameters a transformation record must carry for this reduction."""
    return {
        "operation": "align_weekly_to_monthly",
        "aggregation": aggregation.value,
        "week_assignment": assignment.value,
        "anchor": anchor.value,
    }
