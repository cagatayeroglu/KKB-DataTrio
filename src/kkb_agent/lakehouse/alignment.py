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
from datetime import date, timedelta
from enum import StrEnum

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.periods import add_months, month_end, weekly_window
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, check_period


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
    """Expected versus supplied source ends in the requested window, per month.

    Complete means complete for that window, not necessarily a whole month.
    Zero expectation is represented explicitly and is never complete.
    """

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


def reducer_for(aggregation: Aggregation) -> Callable[[list[float]], float] | None:
    """How several source periods become one, by a declared aggregation; None when unknown."""
    return _REDUCERS.get(aggregation)


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


def _whole_requested_months(requested_start: date, requested_end: date) -> set[date]:
    """Month ends whose entire month lies inside the requested window."""
    whole: set[date] = set()
    target = month_end(requested_start.year, requested_start.month)
    last = month_end(requested_end.year, requested_end.month)
    while True:
        if date(target.year, target.month, 1) >= requested_start and target <= requested_end:
            whole.add(target)
        if target == last:
            break
        target = add_months(target, 1)
    return whole


def _boundary_weeks(
    canonical: Sequence[tuple[date, date]],
    requested_start: date,
    requested_end: date,
    *,
    anchor: WeeklyAnchor,
) -> list[tuple[date, date]]:
    """Weeks just outside the window that BY_MAJORITY places inside a whole month.

    The window selects weeks by end date, so a week straddling its edge is never
    offered to the month that owns most of the week's days. Without this, the
    final month of a whole-month request averages one week short and still
    reports complete coverage — a figure no reader can reproduce from the
    assignment the answer names.

    Only months requested in full draw a week in. A partial month was not asked
    for as a month, so it keeps the plain by-end selection and the neighbouring
    month a straddling week may still be assigned to.
    """
    whole = _whole_requested_months(requested_start, requested_end)
    if not whole:
        return []
    week = timedelta(days=7)
    before = requested_start - week if requested_start > date.min + week else date.min
    after = requested_end + week if requested_end < date.max - week else date.max
    known = {end for _, end in canonical}
    return [
        (start, end)
        for start, end in weekly_window(before, after, anchor=anchor)
        if end not in known and assign_month(start, end, WeekAssignment.BY_MAJORITY) in whole
    ]


def to_monthly(
    observations: Sequence[Observation],
    *,
    requested_start: date,
    requested_end: date,
    frequency: Frequency,
    aggregation: Aggregation,
    anchor: WeeklyAnchor | None = None,
    assignment: WeekAssignment,
) -> Alignment:
    """Reduce a weekly series onto monthly periods using its declared aggregation.

    `aggregation` must come from the series' recorded semantics. EVDS publishes
    it per series and marks its rates unsummable; passing SUM for a rate is a
    caller error, not something to silently permit.

    Only source period ends inside the inclusive requested window contribute,
    plus — under BY_MAJORITY — the weeks straddling the edge of a month that was
    requested in full, which that assignment places inside it.
    Validate supplied periods even outside that window, but do not count or
    reduce them. Never infer expectation from the span of the supplied rows.
    Empty target months have coverage but no synthesized observation. A short
    request may cover all its expected weeks without covering a whole month.
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
    if not isinstance(assignment, WeekAssignment):
        raise AlignmentError("Alignment needs a declared week assignment")
    try:
        canonical = weekly_window(requested_start, requested_end, anchor=anchor)
        if assignment is WeekAssignment.BY_MAJORITY:
            canonical = sorted(
                canonical
                + _boundary_weeks(canonical, requested_start, requested_end, anchor=anchor)
            )
    except SemanticsError as error:
        raise AlignmentError(str(error)) from error

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

    spine_ends = {end for _, end in canonical}
    supplied = {
        end: item
        for end, item in supplied.items()
        if requested_start <= end <= requested_end or end in spine_ends
    }

    expected: dict[date, int] = {}
    # Keep every requested month, even with no expected anchor or no supplied
    # values. Assignment may add a neighbouring month; never drop that week.
    target = month_end(requested_start.year, requested_start.month)
    last_target = month_end(requested_end.year, requested_end.month)
    while True:
        expected[target] = 0
        if target == last_target:
            break
        target = add_months(target, 1)
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
    return Alignment(
        aligned,
        coverage,
        _method(aggregation, assignment, anchor, requested_start, requested_end),
    )


def _method(
    aggregation: Aggregation,
    assignment: WeekAssignment,
    anchor: WeeklyAnchor,
    requested_start: date,
    requested_end: date,
) -> dict[str, str]:
    """The parameters a transformation record must carry for this reduction."""
    return {
        "operation": "align_weekly_to_monthly",
        "aggregation": aggregation.value,
        "week_assignment": assignment.value,
        "anchor": anchor.value,
        "frequency": Frequency.WEEKLY.value,
        "requested_start": requested_start.isoformat(),
        "requested_end": requested_end.isoformat(),
    }
