"""Cumulative detection and conversion to flow (M12-05, M12-06, M12-07).

BDDK publishes both behaviours the brief warns about, in the same bulletin.
Measured over 2021/1 to 2026/6 (see BDDK_SOURCE):

* `Tüketici Kredileri - Konut` is an outstanding **stock**. It fell in 8 of 65
  month-over-month steps, and a cumulative series cannot fall.
* `DÖNEM NET KARI (ZARARI)` is **year-to-date cumulative** and reset at all five
  January boundaries in the window.

So detection runs per series, never per file. It also refuses to answer where
the values genuinely cannot decide: a series that only ever rises is
indistinguishable from a growing stock, and that ambiguity is reported rather
than resolved. Guessing there is exactly how a stock becomes a fake
"disbursement" series that charts beautifully and means nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from kkb_agent.core import CumulativeKind, Frequency
from kkb_agent.lakehouse.periods import add_months, is_january
from kkb_agent.lakehouse.store import Observation

#: Accumulation is only defined where a period has an unambiguous predecessor
#: within a calendar year. Weekly and daily calendars do not, and no source we
#: inspected publishes a cumulative series at those frequencies.
MONTHS_PER_PERIOD = {Frequency.MONTHLY: 1, Frequency.QUARTERLY: 3, Frequency.SEMIANNUAL: 6}

#: Below this many observations, values cannot support any verdict.
MIN_OBSERVATIONS = 6
#: A yearly-reset verdict needs this many observed January boundaries to be firm.
FIRM_RESET_BOUNDARIES = 2


class Confidence(StrEnum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class CumulativeError(ValueError):
    """A cumulative conversion was requested that the inputs do not support."""


@dataclass(frozen=True, slots=True)
class CumulativeVerdict:
    """What the values suggest, how firmly, and why.

    A verdict is evidence for a human or a later declaration. It is never
    authority to convert on its own; `to_flow` takes the declared kind.
    """

    kind: CumulativeKind
    confidence: Confidence
    reasons: tuple[str, ...]

    @property
    def actionable(self) -> bool:
        return self.confidence is Confidence.HIGH


def _require_supported(frequency: Frequency) -> None:
    if frequency not in MONTHS_PER_PERIOD:
        raise CumulativeError(f"Cumulative semantics are not defined for {frequency.value}")


def _ordered(observations: Sequence[Observation]) -> list[Observation]:
    ordered = sorted(observations, key=lambda item: item.period_end)
    ends = [item.period_end for item in ordered]
    if len(set(ends)) != len(ends):
        raise CumulativeError("Duplicate periods; resolve revisions before converting")
    return ordered


def detect_cumulative(
    observations: Sequence[Observation], *, frequency: Frequency
) -> CumulativeVerdict:
    """Infer accumulation behaviour from published values alone.

    Deliberately conservative. A fall outside January rules accumulation out; a
    fall at every January boundary rules it in; a series that only rises decides
    nothing, because a growing stock looks identical.
    """
    _require_supported(frequency)
    # Drop missing values up front so the comparison below needs no narrowing;
    # a gap must not be read as a fall.
    points: list[tuple[date, float]] = [
        (item.period_end, item.value) for item in _ordered(observations) if item.value is not None
    ]
    if len(points) < MIN_OBSERVATIONS:
        return CumulativeVerdict(
            CumulativeKind.UNKNOWN,
            Confidence.NONE,
            (f"Only {len(points)} observations; at least {MIN_OBSERVATIONS} are needed",),
        )

    january_drops = 0
    january_steps = 0
    other_drops: list[date] = []
    for (_, previous_value), (end, value) in zip(points, points[1:], strict=False):
        fell = value < previous_value
        if is_january(end, frequency):
            january_steps += 1
            january_drops += fell
        elif fell:
            other_drops.append(end)

    if other_drops:
        shown = ", ".join(day.isoformat() for day in other_drops[:3])
        return CumulativeVerdict(
            CumulativeKind.NONE,
            Confidence.HIGH,
            (
                f"Value fell in {len(other_drops)} step(s) outside January ({shown})",
                "A cumulative series cannot fall within its accumulation window",
            ),
        )

    if january_steps and january_drops == january_steps:
        firm = january_steps >= FIRM_RESET_BOUNDARIES
        return CumulativeVerdict(
            CumulativeKind.YEARLY_RESET,
            Confidence.HIGH if firm else Confidence.LOW,
            (
                f"Value fell at all {january_steps} observed January boundary(ies)",
                "Non-decreasing within every calendar year",
            )
            + (() if firm else (f"Only {january_steps} boundary observed; needs a longer window",)),
        )

    if january_steps and january_drops:
        return CumulativeVerdict(
            CumulativeKind.UNKNOWN,
            Confidence.LOW,
            (
                f"Value fell at {january_drops} of {january_steps} January boundaries",
                "A reset series resets every year; this one does not",
            ),
        )

    return CumulativeVerdict(
        CumulativeKind.UNKNOWN,
        Confidence.LOW,
        (
            "Series never falls, including across January",
            "A since-inception cumulative and a growing stock are identical here",
            "Resolve from source metadata, not from these values",
        ),
    )


def to_flow(
    observations: Sequence[Observation],
    kind: CumulativeKind,
    *,
    frequency: Frequency,
    baseline: float | None = None,
) -> list[Observation]:
    """Convert a cumulative series to per-period flow.

    Returns one observation per input period. A period whose flow cannot be
    derived — no usable predecessor, a gap in the spine, a missing value —
    comes back with `value=None` rather than a number that spans two periods or
    silently starts from zero.

    `baseline` is the published cumulative value for the period immediately
    before the first one supplied. It is required for SINCE_INCEPTION and
    ignored for YEARLY_RESET, whose January value is already the month itself.
    """
    _require_supported(frequency)
    if kind is CumulativeKind.YEARLY_RESET:
        return _yearly_reset_to_flow(_ordered(observations), frequency)
    if kind is CumulativeKind.SINCE_INCEPTION:
        return _since_inception_to_flow(_ordered(observations), frequency, baseline)
    raise CumulativeError(f"{kind.value} is not a cumulative series; there is nothing to convert")


def _predecessor_value(
    previous: Observation | None, current: Observation, frequency: Frequency
) -> float | None:
    """Usable prior level, or None when differencing would be wrong."""
    if previous is None or previous.value is None or current.value is None:
        return None
    if add_months(previous.period_end, MONTHS_PER_PERIOD[frequency]) != current.period_end:
        # A gap: the difference would span more than one period.
        return None
    return previous.value


def _yearly_reset_to_flow(ordered: list[Observation], frequency: Frequency) -> list[Observation]:
    flows: list[Observation] = []
    previous: Observation | None = None
    for current in ordered:
        if is_january(current.period_end, frequency):
            # The year restarts here, so the published value is the period.
            value = current.value
        else:
            prior = _predecessor_value(previous, current, frequency)
            value = None if prior is None or current.value is None else current.value - prior
        flows.append(Observation(current.period_start, current.period_end, value))
        previous = current
    return flows


def _since_inception_to_flow(
    ordered: list[Observation], frequency: Frequency, baseline: float | None
) -> list[Observation]:
    flows: list[Observation] = []
    previous: Observation | None = None
    for index, current in enumerate(ordered):
        if index == 0:
            # Without the level before the window, the first flow is unknowable.
            value = None if baseline is None or current.value is None else current.value - baseline
        else:
            prior = _predecessor_value(previous, current, frequency)
            value = None if prior is None or current.value is None else current.value - prior
        flows.append(Observation(current.period_start, current.period_end, value))
        previous = current
    return flows
