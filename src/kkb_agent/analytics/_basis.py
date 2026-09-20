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
from math import log

from kkb_agent.core import StockFlow
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


def magnitudes(
    changes: Sequence[tuple[Observation, float, float]], *, ratio: bool
) -> list[float]:
    """The comparable quantity each change is scored on."""
    if ratio:
        return [log(value / previous) for _, previous, value in changes]
    return [value - previous for _, previous, value in changes]
