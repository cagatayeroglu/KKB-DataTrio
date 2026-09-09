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


def _walk(
    frequency: Frequency, first_end: date, last_end: date, *, anchor: WeeklyAnchor | None
) -> Iterator[tuple[date, date]]:
    if frequency is Frequency.WEEKLY:
        step = timedelta(days=7)
        end = first_end
        while end <= last_end:
            yield period_bounds(frequency, end, anchor=anchor)
            end += step
        return
    months = _MONTH_STEP.get(frequency)
    if months is None:
        # DAILY and BUSINESS_DAY need a holiday calendar nobody has supplied,
        # and IRREGULAR has no spine by definition.
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
