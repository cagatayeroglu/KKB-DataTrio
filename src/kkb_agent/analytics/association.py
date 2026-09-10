"""Association and lag between two series (M6-07, M6-08, M6-09, M6-10).

This module computes correlation. It does not compute causation, and under
[DEC-120](../../../docs/DECISIONS.md) it never phrases one as the other: every
result it returns carries mandatory limitations, which the M6-01 contract
enforces for relational kinds rather than leaving to a reviewer's memory.

Four things decide whether a correlation here is worth anything.

**Alignment.** Two series are compared only on periods both actually
published, matched by period end. A monthly series and a daily one are
refused rather than resampled: choosing how to resample is a semantic decision
with a right answer per series, and making it silently here is how a number
stops meaning what its label says.

**Sample.** Correlation over a handful of points is noise with a decimal
point. A floor applies, and each lag reports its own count because a lag of
k periods discards k overlapping observations.

**Shape.** Pearson measures *linear* association. Spearman measures monotone
association and is unmoved by a single extreme pair. When they disagree
materially the relationship is not linear, and the result says so instead of
quietly reporting the number that happens to look better.

**Trend.** Two series that both rise steadily correlate near 1 whatever they
measure — the classic spurious result. Each series is scored against time,
and when both are strongly trending the result says the association may be
that shared trend and names differencing as the check. It does not silently
difference: that would answer a question nobody asked.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from math import sqrt
from typing import Final

from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

#: Aligned pairs needed before a correlation means anything. Two years of
#: monthly data. PROPOSED: no benchmark has measured it.
DEFAULT_MINIMUM_PAIRS: Final = 24

#: How far a lag search may reach, and the hard cap on any caller's request.
#: Every extra lag is another chance for noise to produce the largest number.
DEFAULT_MAX_LAG: Final = 6
LAG_CAP: Final = 12

#: |r| against time above which a series counts as strongly trending.
#: PROPOSED; it is a flag for a reader, not a test anything passes or fails.
TREND_LIMIT: Final = 0.9

#: Absolute gap between Pearson and Spearman that says "not linear".
NONLINEAR_GAP: Final = 0.2

DEFAULT_INPUTS: Final = ("silver_observations",)

#: Attached to every result this module produces. DEC-120 makes them mandatory
#: and the M6-01 contract refuses a relational result that omits them.
BASE_LIMITATIONS: Final = (
    "This is association, not causation: it measures whether two series move "
    "together, not whether one moves the other",
    "A third factor moving both would produce the same number",
    "Neither series was tested for stationarity, and no identification strategy was applied",
)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Linear correlation, or None when either series has no variance."""
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    spread_x = sqrt(sum(value * value for value in dx))
    spread_y = sqrt(sum(value * value for value in dy))
    if spread_x == 0 or spread_y == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / (spread_x * spread_y)


def _ranks(values: Sequence[float]) -> list[float]:
    """Ranks with ties averaged, so a plateau does not invent an ordering."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared = (position + end) / 2 + 1
        for index in order[position : end + 1]:
            ranks[index] = shared
        position = end + 1
    return ranks


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    return _pearson(_ranks(xs), _ranks(ys))


def _trend(values: Sequence[float]) -> float | None:
    """Correlation against position in time, as a plain trend score."""
    return _pearson([float(index) for index in range(len(values))], values)


def _aligned(
    left: Sequence[Observation], right: Sequence[Observation]
) -> tuple[list[date], list[float], list[float], int]:
    """Periods both series published a value for, and how many they did not."""
    by_end = {item.period_end: item.value for item in right}
    periods: list[date] = []
    xs: list[float] = []
    ys: list[float] = []
    dropped = 0
    for item in sorted(left, key=lambda entry: entry.period_end):
        if item.period_end not in by_end:
            dropped += 1
            continue
        other = by_end[item.period_end]
        if item.value is None or other is None:
            dropped += 1
            continue
        periods.append(item.period_end)
        xs.append(item.value)
        ys.append(other)
    return periods, xs, ys, dropped


def _refuse(
    result_id: str,
    kind: ResultKind,
    status: ResultStatus,
    reason: str,
    samples: SampleCounts,
    unresolved: Sequence[str] = (),
) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=result_id,
        kind=kind,
        status=status,
        tool="analytics",
        method="pearson",
        samples=samples,
        reason=reason,
        unresolved_semantics=list(unresolved),
    )


def _prepare(
    left: Sequence[Observation],
    left_semantics: SeriesSemantics,
    right: Sequence[Observation],
    right_semantics: SeriesSemantics,
    start: date | None,
    end: date | None,
) -> tuple[list[date], list[float], list[float], int] | str:
    """Aligned pairs, or the reason there are none to work with."""
    for semantics, name in ((left_semantics, "first"), (right_semantics, "second")):
        if semantics.unresolved:
            return (
                f"The {name} series' meaning is unresolved "
                f"({', '.join(semantics.unresolved)}); align it before comparing"
            )
    if left_semantics.frequency is not right_semantics.frequency:
        return (
            f"The series are published at different frequencies "
            f"({left_semantics.frequency.value} and {right_semantics.frequency.value}); "
            "align them explicitly rather than comparing across calendars"
        )
    return _aligned(_window(left, start, end), _window(right, start, end))


def _window(
    items: Sequence[Observation], start: date | None, end: date | None
) -> list[Observation]:
    return [
        item
        for item in items
        if (start is None or item.period_end >= start) and (end is None or item.period_end <= end)
    ]


def associate(
    left: Sequence[Observation],
    left_semantics: SeriesSemantics,
    right: Sequence[Observation],
    right_semantics: SeriesSemantics,
    *,
    left_id: str,
    right_id: str,
    start: date | None = None,
    end: date | None = None,
    minimum_pairs: int = DEFAULT_MINIMUM_PAIRS,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """How closely two series moved together over the periods both published."""
    identifier = result_id or f"assoc:{left_id}:{right_id}"
    prepared = _prepare(left, left_semantics, right, right_semantics, start, end)
    if isinstance(prepared, str):
        return _refuse(
            identifier,
            ResultKind.ASSOCIATION,
            ResultStatus.ABSTAINED,
            prepared,
            SampleCounts(used=0),
            left_semantics.unresolved + right_semantics.unresolved,
        )
    periods, xs, ys, dropped = prepared
    if len(xs) < minimum_pairs:
        return _refuse(
            identifier,
            ResultKind.ASSOCIATION,
            ResultStatus.INSUFFICIENT,
            f"{len(xs)} aligned period(s) is below the {minimum_pairs} this measure "
            "requires; a correlation over a handful of points is noise with a decimal point",
            SampleCounts(used=len(xs), missing=dropped, minimum_required=minimum_pairs),
        )

    pearson = _pearson(xs, ys)
    if pearson is None:
        return _refuse(
            identifier,
            ResultKind.ASSOCIATION,
            ResultStatus.UNDEFINED,
            "One of the series does not vary over these periods, so correlation is "
            "undefined rather than zero",
            SampleCounts(used=len(xs), missing=dropped),
        )
    spearman = _spearman(xs, ys)

    values = [
        ResultValue(
            label=f"{left_id} vs {right_id} correlation",
            value=pearson,
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=Period(start=periods[0], end=periods[-1]),
            samples=SampleCounts(used=len(xs)),
        )
    ]
    if spearman is not None:
        values.append(
            ResultValue(
                label=f"{left_id} vs {right_id} rank correlation",
                value=spearman,
                unit=DIMENSIONLESS,
                scale=Scale.ONE,
                period=Period(start=periods[0], end=periods[-1]),
                samples=SampleCounts(used=len(xs)),
            )
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.ASSOCIATION,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="pearson",
        values=values,
        coverage=Period(start=periods[0], end=periods[-1]),
        parameters={
            "left": left_id,
            "right": right_id,
            "method": "Pearson linear correlation, with Spearman rank correlation beside it",
            "missing_value_policy": (
                "periods either series left unpublished are dropped, never filled"
            ),
            "minimum_pairs": minimum_pairs,
            "minimum_pairs_status": "PROPOSED; no benchmark has measured it",
        },
        samples=SampleCounts(used=len(xs), missing=dropped, minimum_required=minimum_pairs),
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=_diagnostics(xs, ys, pearson, spearman, dropped),
        limitations=list(BASE_LIMITATIONS),
    )


def _diagnostics(
    xs: Sequence[float],
    ys: Sequence[float],
    pearson: float,
    spearman: float | None,
    dropped: int,
) -> list[str]:
    """What a reader has to know before quoting the number."""
    notes: list[str] = []
    left_trend, right_trend = _trend(xs), _trend(ys)
    if (
        left_trend is not None
        and right_trend is not None
        and abs(left_trend) > TREND_LIMIT
        and abs(right_trend) > TREND_LIMIT
    ):
        notes.append(
            "Both series trend strongly over this window, and two trending series "
            "correlate whatever they measure; compare their period-over-period "
            "changes before treating this as a relationship"
        )
    if spearman is not None and abs(pearson - spearman) > NONLINEAR_GAP:
        notes.append(
            f"Linear and rank correlation differ by {abs(pearson - spearman):.2f}, so the "
            "relationship is not linear; the rank figure is the more robust of the two"
        )
    if dropped:
        notes.append(
            f"{dropped} period(s) were dropped because one series had no published value; "
            "gaps are never filled to make a pair"
        )
    return notes


def lagged_association(
    left: Sequence[Observation],
    left_semantics: SeriesSemantics,
    right: Sequence[Observation],
    right_semantics: SeriesSemantics,
    *,
    left_id: str,
    right_id: str,
    max_lag: int = DEFAULT_MAX_LAG,
    start: date | None = None,
    end: date | None = None,
    minimum_pairs: int = DEFAULT_MINIMUM_PAIRS,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Correlation at each offset in a bounded window.

    **Sign convention, stated once and repeated in the result**: a lag of `k`
    pairs the first series at period `t` with the second at `t + k`. A positive
    lag with the strongest correlation therefore means the **first series moves
    first**. Getting this backwards inverts the entire reading, which is why it
    is in the label, the parameters and a warning rather than in a comment.
    """
    identifier = result_id or f"lag:{left_id}:{right_id}"
    if not 0 <= max_lag <= LAG_CAP:
        return _refuse(
            identifier,
            ResultKind.LAG,
            ResultStatus.ABSTAINED,
            f"A lag window of {max_lag} is outside the permitted 0..{LAG_CAP}; every extra "
            "lag is another chance for noise to produce the largest number",
            SampleCounts(used=0),
        )
    prepared = _prepare(left, left_semantics, right, right_semantics, start, end)
    if isinstance(prepared, str):
        return _refuse(
            identifier,
            ResultKind.LAG,
            ResultStatus.ABSTAINED,
            prepared,
            SampleCounts(used=0),
            left_semantics.unresolved + right_semantics.unresolved,
        )
    periods, xs, ys, dropped = prepared

    values: list[ResultValue] = []
    strongest: tuple[int, float] | None = None
    for lag in range(-max_lag, max_lag + 1):
        paired_x, paired_y = _shift(xs, ys, lag)
        if len(paired_x) < minimum_pairs:
            continue
        correlation = _pearson(paired_x, paired_y)
        if correlation is None:
            continue
        values.append(
            ResultValue(
                label=f"{left_id} vs {right_id} at lag {lag:+d}",
                value=correlation,
                unit=DIMENSIONLESS,
                scale=Scale.ONE,
                lag=lag,
                period=Period(start=periods[0], end=periods[-1]),
                samples=SampleCounts(used=len(paired_x)),
            )
        )
        if strongest is None or abs(correlation) > abs(strongest[1]):
            strongest = (lag, correlation)

    if strongest is None:
        return _refuse(
            identifier,
            ResultKind.LAG,
            ResultStatus.INSUFFICIENT,
            f"No offset in +/-{max_lag} had {minimum_pairs} aligned pairs with variance in "
            f"both series; {len(xs)} period(s) aligned before shifting",
            SampleCounts(used=len(xs), missing=dropped, minimum_required=minimum_pairs),
        )

    lead, correlation = strongest
    warnings = [
        f"Lag sign: a lag of k pairs {left_id} at period t with {right_id} at t+k, so "
        f"the strongest offset {lead:+d} means "
        + (
            f"{left_id} moves first by {lead} period(s)"
            if lead > 0
            else f"{right_id} moves first by {abs(lead)} period(s)"
            if lead < 0
            else "the two move together with no offset"
        ),
        f"The strongest of {len(values)} offsets was selected, so its apparent strength "
        "is inflated by the search itself; it is not a tested hypothesis",
    ]
    warnings.extend(_diagnostics(xs, ys, correlation, _spearman(xs, ys), dropped))

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.LAG,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="lagged_pearson",
        values=values,
        coverage=Period(start=periods[0], end=periods[-1]),
        parameters={
            "left": left_id,
            "right": right_id,
            "max_lag": max_lag,
            "lag_sign": (
                f"lag k pairs {left_id} at t with {right_id} at t+k; "
                f"positive k means {left_id} leads"
            ),
            "strongest_lag": lead,
            "offsets_examined": len(values),
            "minimum_pairs": minimum_pairs,
        },
        samples=SampleCounts(used=len(xs), missing=dropped, minimum_required=minimum_pairs),
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=warnings,
        limitations=[
            *BASE_LIMITATIONS,
            "A leading correlation is not evidence of direction: both series may follow "
            "a third that moves earlier still",
        ],
    )


def _shift(xs: Sequence[float], ys: Sequence[float], lag: int) -> tuple[list[float], list[float]]:
    """Pair x at t with y at t+k, dropping the k periods that fall off the end."""
    if lag > 0:
        return list(xs[:-lag]), list(ys[lag:])
    if lag < 0:
        return list(xs[-lag:]), list(ys[:lag])
    return list(xs), list(ys)
