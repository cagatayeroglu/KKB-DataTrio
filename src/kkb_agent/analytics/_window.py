"""Which observations a requested window holds, and what that selection is worth saying.

An observation belongs to the window its period **ends** in. A week ending on 1 January
2021 is the first observation of 2021, not the last of 2020, so a reader asking for 2021
onwards gets it -- selecting by period start would silently drop the first week of every
year a source publishes weekly.

What that costs is a date the reader did not ask for: the window then *begins* on 26
December 2020, because that is when the week began. The selection was right and the answer
never said why the date reached back (live 2026-09-22, and Eray's N26 before it), so a
reader could only read it as the requested start being ignored. It is now said once, in the
result's own warnings, and the same two sentences serve every analytic that takes a window.

Neither sentence carries a figure. A warning reaches the reader through the writer, which is
asked to say it "in words and without a figure", and the dates a first draft put in them
(live 2026-09-22) left the writer nothing it could say: the answer named the window as
starting 2020-12-26 and never explained it. The dates are already in the coverage the answer
states; what was missing was the reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from kkb_agent.lakehouse.records import Observation


def in_window(
    observations: Sequence[Observation], start: date | None, end: date | None
) -> list[Observation]:
    """The observations the window holds, oldest first, chosen by where each period ends."""
    return sorted(
        (
            item
            for item in observations
            if (start is None or item.period_end >= start)
            and (end is None or item.period_end <= end)
        ),
        key=lambda item: item.period_end,
    )


def window_notes(
    observations: Sequence[Observation],
    window: Sequence[Observation],
    start: date | None,
    end: date | None,
) -> list[str]:
    """What a reader needs told about the edges of this window; empty when nothing does."""
    notes: list[str] = []
    if window and start is not None and window[0].period_start < start:
        notes.append(
            "The first period examined began before the window asked for and ends inside it, "
            "which is why the window starts earlier than the date in the question: a period "
            "belongs to the window it ends in, and this one is the source's own"
        )
    if end is not None and any(item.period_start <= end < item.period_end for item in observations):
        notes.append(
            "A period that had begun by the end of the window but finishes after it was left "
            "out; a period is examined whole or not at all"
        )
    return notes
