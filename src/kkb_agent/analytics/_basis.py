"""What a period-over-period change is compared with.

Both the anomaly baseline and the breakpoint search read period-over-period
changes, and both have to decide what makes two of them comparable.

A difference in the series' own unit grows with the level. Over a window where a
balance triples, the recent months hold the largest differences whatever happened
in them, so the interesting early month cannot compete with an ordinary late one.
Measured on the prepared CPI (2021-01..2026-06), December 2021 — the record
monthly rise of the window — scored 0.87 on that basis while an ordinary January
2026 scored highest, and nothing at all passed the cut. Scored against the level
it came from, the same December scores 6.32 and is the clear outlier, which is
what a reader asking about that series means.

A rate is already comparable across its window: two percentage points is two
percentage points whether the rate is 8 or 43. A series that reaches zero or
changes sign has no meaningful ratio. Both keep the difference, and every result
records which basis decided it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from math import log

from kkb_agent.core import Frequency, StockFlow
from kkb_agent.lakehouse.periods import daily_steps
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

RATIO_BASIS = (
    "the log ratio to the previous level, so a period is compared with the "
    "others rather than with the size the series has reached"
)
DIFFERENCE_BASIS = "the difference in the series' own unit"


def scored_on_ratio(
    semantics: SeriesSemantics, changes: Sequence[tuple[Observation, float, float]]
) -> bool:
    """Whether these changes are scored against the level they came from."""
    if semantics.observation is StockFlow.RATE:
        return False
    return all(previous > 0 and value > 0 for _, previous, value in changes)


def scored_magnitudes(
    changes: Sequence[tuple[Observation, float, float]], *, ratio: bool
) -> list[float]:
    """The comparable quantity each change is scored on."""
    if ratio:
        return [log(value / previous) for _, previous, value in changes]
    return [value - previous for _, previous, value in changes]


def consecutive_changes(
    window: Sequence[Observation], semantics: SeriesSemantics
) -> tuple[list[tuple[Observation, float, float]], int, int]:
    """Changes between periods that really follow one another, and what was left out.

    Two observations are consecutive when the later period begins the day after the
    earlier one ends. That is one rule for two failures a null-valued row alone does
    not cover. A dataset whose February row is simply absent - which a user's file may
    be, where a prepared series may not - used to have January and March differenced
    and the result labelled one month's move. And a daily series publishes nothing on
    a weekend, so every Monday followed a break and the Friday-to-Monday move, the one
    a reader asks about, was never scored at all.

    DAILY requires the next calendar day; BUSINESS_DAY requires the next weekday.
    Missing weekdays are never treated as inferred holidays or silently bridged.

    Returns the changes, how many rows carried no value, and how many pairs were left
    out because the periods did not follow one another.
    """
    published = [(item, item.value) for item in window if item.value is not None]
    missing = len(window) - len(published)
    daily = semantics.frequency in (Frequency.DAILY, Frequency.BUSINESS_DAY)
    changes: list[tuple[Observation, float, float]] = []
    interrupted = 0
    for (earlier, before), (later, value) in zip(published, published[1:], strict=False):
        consecutive = (
            daily_steps(semantics.frequency, earlier.period_end, later.period_end) == 1
            if daily
            else later.period_start == earlier.period_end + timedelta(days=1)
        )
        if not consecutive:
            interrupted += 1
            continue
        changes.append((later, before, value))
    return changes, missing, interrupted
