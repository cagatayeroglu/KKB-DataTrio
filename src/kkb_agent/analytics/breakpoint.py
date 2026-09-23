"""Where a series changed regime (M6-05/06): significant breakpoints, not anomalies.

An anomaly is one period that moved unlike the others. A breakpoint is the month
after which the series *kept* moving differently — the brief asks for both, and
they are different questions with different methods.

What is examined is the **period-over-period change**, for the reason the anomaly
baseline gives: a growing balance makes every recent level extreme, so a level
detector finds only the present. A breakpoint here is a shift in the average
change: housing credit growing by 4 bn a month and then by 20 bn is a regime
change even though no single month is an outlier.

The method is binary segmentation with a two-sample statistic. For every split
that leaves at least `minimum_segment` changes on each side, the standardized
difference of the two means is computed; the largest one becomes a breakpoint
when it passes the threshold, and each resulting segment is searched again up to
`maximum_points`. The threshold and the minimum segment are **PROPOSED defaults,
not measured ones**; they are recorded in the result and are not planner
arguments, because a threshold a model can move is a threshold it will move
until something looks interesting.

A constant series has no spread to standardize against: that is UNDEFINED with
its reason, never a breakpoint at an arbitrary month.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import fmean
from typing import Final

from pydantic import JsonValue

from kkb_agent.analytics._basis import consecutive_changes
from kkb_agent.analytics._window import in_window, window_notes
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
    StockFlow,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD: Final = "mean-shift-binary-segmentation-v1"
#: Standardized difference a split must reach. PROPOSED, not measured.
DEFAULT_THRESHOLD: Final = 3.0
#: Changes each side of a split must have before the two means mean anything.
DEFAULT_MINIMUM_SEGMENT: Final = 6
#: Breakpoints one window may report; a series segmented endlessly explains nothing.
DEFAULT_MAXIMUM_POINTS: Final = 3
DEFAULT_INPUTS: Final = ("silver_observations",)


def _difference_unit(semantics: SeriesSemantics) -> str:
    if semantics.observation is StockFlow.RATE:
        return "percentage point"
    if semantics.observation is StockFlow.INDEX:
        return "index point"
    return semantics.unit


def _difference_scale(semantics: SeriesSemantics) -> Scale:
    if semantics.observation in (StockFlow.RATE, StockFlow.INDEX):
        return Scale.ONE
    return semantics.scale


def _refuse(
    result_id: str,
    status: ResultStatus,
    reason: str,
    samples: SampleCounts,
    unresolved: Sequence[str] = (),
) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=result_id,
        kind=ResultKind.CHANGE_POINT,
        status=status,
        tool="analytics",
        method=METHOD,
        samples=samples,
        reason=reason,
        unresolved_semantics=list(unresolved),
    )


def _statistic(values: Sequence[float], split: int) -> float:
    """Standardized difference of the two segment means; 0 when there is no spread."""
    before, after = values[:split], values[split:]
    spread = _pooled(before, after)
    if spread == 0:
        return 0.0
    standard_error = spread * ((1 / len(before) + 1 / len(after)) ** 0.5)
    return float(abs(fmean(before) - fmean(after)) / standard_error)


def _pooled(before: Sequence[float], after: Sequence[float]) -> float:
    total = 0.0
    for segment in (before, after):
        centre = fmean(segment)
        total += sum((value - centre) ** 2 for value in segment)
    degrees = len(before) + len(after) - 2
    return (total / degrees) ** 0.5 if degrees > 0 else 0.0


def _segment(
    values: Sequence[float], offset: int, minimum_segment: int, threshold: float
) -> tuple[int, float] | None:
    """The best split inside one segment, or None when none passes the threshold."""
    if len(values) < 2 * minimum_segment:
        return None
    best: tuple[int, float] | None = None
    for split in range(minimum_segment, len(values) - minimum_segment + 1):
        statistic = _statistic(values, split)
        if best is None or statistic > best[1]:
            best = (offset + split, statistic)
    if best is None or best[1] < threshold:
        return None
    return best


def detect_breakpoints(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
    start: date | None = None,
    end: date | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    minimum_segment: int = DEFAULT_MINIMUM_SEGMENT,
    maximum_points: int = DEFAULT_MAXIMUM_POINTS,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Find the months after which this series kept moving differently.

    The result always carries a count, including zero: "no breakpoint in this
    window" is an answer, and the verifier can bind its number.
    """
    identifier = result_id or f"breakpoint:{series_id}"
    if semantics.unresolved:
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            "Cannot judge a regime change while the series' meaning is unresolved: "
            + ", ".join(semantics.unresolved),
            SampleCounts(used=0),
            semantics.unresolved,
        )
    if semantics.cumulative.value in ("since_inception", "yearly_reset"):
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            f"The series accumulates ({semantics.cumulative.value}); convert it to flow "
            "before looking for a regime change, or every January looks like one",
            SampleCounts(used=0),
        )

    window = in_window(observations, start, end)
    changes, missing, interrupted = consecutive_changes(window, semantics)
    required = 2 * minimum_segment
    if len(changes) < required:
        return _refuse(
            identifier,
            ResultStatus.INSUFFICIENT,
            f"{len(changes)} period-over-period changes is below the {required} this method "
            f"needs ({minimum_segment} on each side of a split)",
            SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=required,
            ),
        )
    # Measured 2026-09-20 over the whole prepared pool: moving this search onto the
    # relative basis the anomaly baseline uses removes the CPI's 2021-12 and 2023-07
    # regime changes and adds three others to the housing price index, with nothing to
    # say which reading is right. What this statistic should run on is the question
    # B4/B5/B8 of the same audit ask, and it needs its own measured decision; until
    # then the search stays on the difference and the shift is reported in that unit.
    differences = magnitudes = [value - previous for _, previous, value in changes]
    if _pooled(magnitudes[:1], magnitudes[1:]) == 0 and len(set(magnitudes)) == 1:
        return _refuse(
            identifier,
            ResultStatus.UNDEFINED,
            "Every period-over-period change is identical, so there is no spread to "
            "measure a regime change against",
            SampleCounts(used=len(changes), missing=missing, excluded=interrupted),
        )

    found: list[tuple[int, float]] = []
    segments: list[tuple[int, int]] = [(0, len(magnitudes))]
    while segments and len(found) < maximum_points:
        begin, finish = segments.pop(0)
        best = _segment(magnitudes[begin:finish], begin, minimum_segment, threshold)
        if best is None:
            continue
        found.append(best)
        segments.extend([(begin, best[0]), (best[0], finish)])
        segments.sort()
    found.sort()

    coverage = Period(
        start=window[0].period_start,
        end=window[-1].period_end,
        frequency=semantics.frequency,
        weekly_anchor=semantics.anchor,
    )
    values = [
        ResultValue(
            label=f"{series_id} breakpoints found",
            value=float(len(found)),
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=coverage,
        )
    ]
    # Each breakpoint separates the regime before it from the regime after it, so its
    # shift is measured between those two neighbours. Taking the whole window instead
    # mixes every other regime into both means. Measured on the prepared housing
    # balance, which breaks at 2024-10 and 2025-10: the neighbouring regimes differ by
    # +8,921 and +6,535 million TRY a month, and the whole window reported +11,722 and
    # +13,545 - the second one's "before" still held the slow 2021-2024 regime.
    edges = [0, *(position for position, _ in found), len(magnitudes)]
    details: list[JsonValue] = []
    for index, (position, statistic) in enumerate(found):
        observation = changes[position][0]
        before = differences[edges[index] : position]
        after = differences[position : edges[index + 2]]
        shift = fmean(after) - fmean(before)
        values.append(
            ResultValue(
                label=f"{series_id} average change shift at {observation.period_end.isoformat()}",
                value=shift,
                unit=_difference_unit(semantics),
                scale=_difference_scale(semantics),
                measure=semantics.observation,
                period=Period(
                    start=observation.period_start,
                    end=observation.period_end,
                    frequency=semantics.frequency,
                    weekly_anchor=semantics.anchor,
                ),
                samples=SampleCounts(used=len(before) + len(after)),
            )
        )
        details.append(
            {
                "period_end": observation.period_end.isoformat(),
                "mean_change_before": fmean(before),
                "mean_change_after": fmean(after),
                "observations_before": len(before),
                "observations_after": len(after),
                "statistic": statistic,
            }
        )

    warnings = [
        "A breakpoint is where the average period-over-period change shifts; it names "
        "no event and establishes no cause"
    ]
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "Changes are in an outstanding balance, so a regime change is a change in net "
            "movement, not in new lending"
        )
    if missing:
        warnings.append(
            f"{missing} period(s) had no published value; a gap ends a pair rather than "
            "bridging it, so no change was invented across it"
        )
    if interrupted:
        warnings.append(
            f"{interrupted} pair(s) of periods did not follow one another and were left out; "
            "a regime is read from periods that actually succeed each other"
        )
    warnings.extend(window_notes(observations, window, start, end))

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.CHANGE_POINT,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method=METHOD,
        values=values,
        coverage=coverage,
        parameters={
            "series": series_id,
            "examined": "period-over-period change",
            "method": "binary segmentation on a two-sample standardized mean difference",
            "threshold": threshold,
            "minimum_segment": minimum_segment,
            "maximum_points": maximum_points,
            "breakpoints": details,
        },
        samples=SampleCounts(used=len(changes), missing=missing, excluded=interrupted),
        evidence=ResultEvidence(
            input_refs=list(input_refs),
            lineage_node=lineage_node,
        ),
        warnings=warnings,
        limitations=[
            "The threshold and the minimum segment are proposed defaults, not measured "
            "ones; a different window can move where a breakpoint falls",
            "Only shifts in the average change are searched; a change in volatility or "
            "seasonality is not this method's question",
        ],
    )
