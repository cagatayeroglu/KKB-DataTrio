"""The canonical period spine (M12-04).

Every series is placed on periods generated here rather than on whatever dates
its source happened to emit. Two series that both claim to be monthly still
disagree if one is dated to the first of the month and the other to the last;
generating both from the same function removes that class of bug entirely.

Ranges are inclusive at both ends and expressed by period **end**, because that
is what the sources publish.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import date, timedelta

from kkb_agent.core import Frequency, WeeklyAnchor
from kkb_agent.lakehouse.semantics import SemanticsError, period_bounds

_MONTH_STEP = {
    Frequency.MONTHLY: 1,
    Frequency.QUARTERLY: 3,
    Frequency.SEMIANNUAL: 6,
    Frequency.ANNUAL: 12,
}


def month_end(year: int, month: int) -> date:
    """Last calendar day of the given month, leap years included."""
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months(day: date, months: int) -> date:
    """Shift by whole months, landing on the same month-end convention."""
    index = (day.year * 12 + day.month - 1) + months
    year, month = divmod(index, 12)
    return month_end(year, month + 1)


def spine(
    frequency: Frequency,
    first_end: date,
    last_end: date,
    *,
    anchor: WeeklyAnchor | None = None,
) -> list[tuple[date, date]]:
    """Every canonical period from `first_end` through `last_end`, inclusive.

    Both bounds must themselves be valid period ends for the frequency, so a
    caller cannot quietly request a range that starts mid-period.
    """
    if last_end < first_end:
        raise SemanticsError(f"Range ends before it starts: {first_end} .. {last_end}")
    period_bounds(frequency, first_end, anchor=anchor)
    period_bounds(frequency, last_end, anchor=anchor)
    return list(_walk(frequency, first_end, last_end, anchor=anchor))


def daily_steps(frequency: Frequency, earlier: date, later: date) -> int:
    """Expected day steps; BUSINESS_DAY is Mon–Fri, with no invented holidays.

    A missing weekday remains a gap. A source holiday calendar, when absent,
    cannot authorize treating an arbitrary missing weekday as a closure.
    """
    days = (later - earlier).days
    if frequency is Frequency.DAILY:
        return days
    if (
        frequency is not Frequency.BUSINESS_DAY
        or days < 0
        or earlier.weekday() > 4
        or later.weekday() > 4
    ):
        return -1
    weeks, tail = divmod(days, 7)
    return weeks * 5 + sum((earlier.weekday() + offset) % 7 < 5 for offset in range(1, tail + 1))


def weekly_window(
    requested_start: date, requested_end: date, *, anchor: WeeklyAnchor
) -> list[tuple[date, date]]:
    """Canonical weeks whose ends fall inside the inclusive requested window.

    Unlike strict ``spine``, request bounds need not be observation dates. This
    only selects weekly ends; it adds no unsupported observation calendars.
    """
    if type(requested_start) is not date or type(requested_end) is not date:
        raise SemanticsError("Requested boundaries must be calendar dates")
    if requested_end < requested_start:
        raise SemanticsError("Requested window ends before it starts")
    if not isinstance(anchor, WeeklyAnchor):
        raise SemanticsError("A weekly window needs a declared weekday anchor")
    first = requested_start.toordinal() + (anchor.weekday - requested_start.weekday()) % 7
    last = requested_end.toordinal() - (requested_end.weekday() - anchor.weekday) % 7
    if first > last:
        return []
    # Ordinal iteration also handles a final anchor at date.max without asking
    # the strict spine walker to step beyond the representable date range.
    return [
        period_bounds(Frequency.WEEKLY, date.fromordinal(end), anchor=anchor)
        for end in range(first, last + 1, 7)
    ]


def _walk(
    frequency: Frequency, first_end: date, last_end: date, *, anchor: WeeklyAnchor | None
) -> Iterator[tuple[date, date]]:
    if frequency in (Frequency.DAILY, Frequency.BUSINESS_DAY):
        if (last_end - first_end).days > 10000:
            raise SemanticsError("Daily spine exceeds the bounded calendar window")
        for ordinal in range(first_end.toordinal(), last_end.toordinal() + 1):
            end = date.fromordinal(ordinal)
            if frequency is Frequency.DAILY or end.weekday() < 5:
                yield end, end
        return
    if frequency is Frequency.WEEKLY:
        step = timedelta(days=7)
        end = first_end
        while end <= last_end:
            yield period_bounds(frequency, end, anchor=anchor)
            end += step
        return
    months = _MONTH_STEP.get(frequency)
    if months is None:
        # IRREGULAR and UNKNOWN have no expected calendar.
        raise SemanticsError(f"No canonical spine is defined for {frequency.value}")
    end = first_end
    while end <= last_end:
        yield period_bounds(frequency, end, anchor=anchor)
        end = add_months(end, months)


def is_january(period_end: date, frequency: Frequency) -> bool:
    """Whether a period is the first of its calendar year.

    A yearly-reset series restarts here, so this is the boundary that decides
    whether a first difference is a monthly flow or an artefact.
    """
    start, _ = period_bounds(frequency, period_end)
    return start.month == 1
