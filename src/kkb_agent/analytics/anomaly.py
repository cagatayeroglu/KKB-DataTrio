"""The anomaly baseline (M6-05, M6-06).

Two choices decide whether this is useful or theatre.

**What is examined.** Anomalies are looked for in **period-over-period
changes**, never in levels. Housing credit rises from 276,785 to 801,438 over
five years, so every recent level is "unusually high" against its own history
and a level-based detector would flag the present and nothing else. The
interesting event is a month that moved unlike other months.

**How the scale is estimated.** Mean and standard deviation are computed from
the same data that contains the outlier, so a single large jump inflates the
spread and hides itself — the more extreme the event, the better it hides.
This uses the **median and the median absolute deviation** instead, which a
handful of extreme points cannot move, and the Iglewicz–Hoaglin modified
z-score built on them.

Both the threshold and the minimum sample are **PROPOSED defaults, not
measured ones**. They are recorded in every result's `parameters` so a reader
can see what produced the flags, and they are not exposed to the planner: a
model that can move a threshold until something looks interesting is a model
that will.

A constant series has a median absolute deviation of zero, which makes the
score undefined rather than infinite. That returns UNDEFINED with the reason,
which is also M6-08's rule about constant series.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import median
from typing import Final

from kkb_agent.analytics._basis import (
    DIFFERENCE_BASIS,
    RATIO_BASIS,
    consecutive_changes,
    magnitudes as _magnitudes,
    scored_on_ratio,
)
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

#: Iglewicz–Hoaglin: the constant that makes the median absolute deviation a
#: consistent estimator of the standard deviation for normally distributed
#: data, and 3.5 as the outlier cut. A published default beats an invented one.
MAD_TO_SIGMA: Final = 0.6745
DEFAULT_THRESHOLD: Final = 3.5

#: The same paper's fallback constant, for the case the median absolute
#: deviation cannot handle. MAD is *exactly zero* whenever more than half the
#: changes are identical — which is the archetypal case here, a very regular
#: series with one jump — and a zero scale would make every score undefined
#: precisely when the answer is most obvious. The mean absolute deviation
#: about the median is not zero unless every change is identical.
MEANAD_TO_SIGMA: Final = 1.253314

#: Changes needed before a median and a spread mean anything. A year of monthly
#: observations, which is 13 levels. PROPOSED: no benchmark has measured it.
DEFAULT_MINIMUM_CHANGES: Final = 12

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
        kind=ResultKind.ANOMALY,
        status=status,
        tool="analytics",
        method="mad_zscore",
        samples=samples,
        reason=reason,
        unresolved_semantics=list(unresolved),
    )


def detect_anomalies(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
    start: date | None = None,
    end: date | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    minimum_changes: int = DEFAULT_MINIMUM_CHANGES,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Flag period-over-period changes that stand apart from the rest.

    The result always carries a count, including when the count is zero: "no
    anomalies" is an answer, and an answer whose number the verifier cannot
    bind is an answer that gets withheld.
    """
    identifier = result_id or f"anomaly:{series_id}"
    if semantics.unresolved:
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            "Cannot judge a change as unusual while the series' meaning is unresolved: "
            + ", ".join(semantics.unresolved),
            SampleCounts(used=0),
            semantics.unresolved,
        )
    if semantics.cumulative.value in ("since_inception", "yearly_reset"):
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            f"The series accumulates ({semantics.cumulative.value}); convert it to flow "
            "before looking for unusual changes, or every period looks like a rise",
            SampleCounts(used=0),
        )

    window = [
        item
        for item in sorted(observations, key=lambda entry: entry.period_end)
        if (start is None or item.period_end >= start) and (end is None or item.period_end <= end)
    ]
    changes, missing, interrupted = consecutive_changes(window, semantics)
    if len(changes) < minimum_changes:
        return _refuse(
            identifier,
            ResultStatus.INSUFFICIENT,
            f"{len(changes)} period-over-period changes is below the {minimum_changes} "
            "this baseline requires for a stable median and spread",
            SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        )

    differences = [value - previous for _, previous, value in changes]
    ratio_basis = scored_on_ratio(semantics, changes)
    # What is scored, against what is reported: the flag is decided on a comparable
    # basis, while the figure the answer quotes stays in the series' own unit.
    magnitudes = _magnitudes(changes, ratio=ratio_basis)
    centre = median(magnitudes)
    deviations = [abs(value - centre) for value in magnitudes]
    spread = median(deviations)
    scale_used = "median absolute deviation"
    if spread == 0:
        # Over half the changes are identical, so MAD collapsed. Fall back to
        # the mean absolute deviation about the same median, which is the
        # published remedy and is zero only when *every* change is identical.
        # The score below is 0.6745 * (value - centre) / spread, so a fallback spread has
        # to be whatever makes that expression the paper's mean-absolute-deviation score,
        # (value - centre) / (1.253314 * meanAD). Dividing by MAD_TO_SIGMA instead of
        # multiplying made the spread 2.198 times too large, which turned the declared
        # 3.5 cut into 7.7 sigma: a flat rate with three +5 point jumps reported none.
        spread = (sum(deviations) / len(deviations)) * MEANAD_TO_SIGMA * MAD_TO_SIGMA
        scale_used = "mean absolute deviation about the median (MAD was zero)"
    if spread == 0:
        return _refuse(
            identifier,
            ResultStatus.UNDEFINED,
            "Every period-over-period change is identical, so there is no spread to "
            "score against; the series moves by the same amount every period or not at all",
            SampleCounts(used=len(changes), missing=missing, excluded=interrupted),
        )

    def score(value: float) -> float:
        return MAD_TO_SIGMA * (value - centre) / spread

    flagged = [
        (observation, difference, score(magnitude))
        for (observation, _, _), difference, magnitude in zip(
            changes, differences, magnitudes, strict=True
        )
        if abs(score(magnitude)) > threshold
    ]

    values = [
        ResultValue(
            label=f"{series_id} anomalies found",
            value=float(len(flagged)),
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=Period(
                start=window[0].period_start,
                end=window[-1].period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
    ]
    values.extend(
        ResultValue(
            label=f"{series_id} change at {observation.period_end.isoformat()}",
            value=value,
            unit=_difference_unit(semantics),
            scale=_difference_scale(semantics),
            measure=semantics.observation,
            period=Period(
                start=observation.period_start,
                end=observation.period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
        for observation, value, _ in flagged
    )

    warnings: list[str] = [
        "An unusual change is not an error, an event or a cause; it is a period that "
        "moved unlike the others in this window"
    ]
    if ratio_basis:
        warnings.append(
            "A period was judged by how much it moved relative to the level before it, "
            "not by the size of the movement; the figure reported stays in the series' unit"
        )
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "Changes are in an outstanding balance, so an unusual month is unusual net "
            "movement, not unusual new lending"
        )
    if missing:
        warnings.append(
            f"{missing} period(s) had no published value and were skipped; a gap is not zero"
        )
    if interrupted:
        warnings.append(
            f"{interrupted} pair(s) of periods did not follow one another and were left out; "
            "differencing across a hole would report several periods of movement as one"
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.ANOMALY,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="mad_zscore",
        values=values,
        coverage=Period(
            start=window[0].period_start,
            end=window[-1].period_end,
            frequency=semantics.frequency,
            weekly_anchor=semantics.anchor,
        ),
        parameters={
            "series": series_id,
            "method": "median absolute deviation, Iglewicz-Hoaglin modified z-score",
            "examined": "period-over-period change",
            "scored_on": RATIO_BASIS if ratio_basis else DIFFERENCE_BASIS,
            "threshold": threshold,
            "minimum_changes": minimum_changes,
            "median_scored_change": centre,
            "scale_estimator": scale_used,
            "scale": spread,
            "threshold_status": "PROPOSED; no benchmark has measured it",
        },
        samples=SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=warnings,
    )


def detect_anomalies(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
    start: date | None = None,
    end: date | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    minimum_changes: int = DEFAULT_MINIMUM_CHANGES,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Flag period-over-period changes that stand apart from the rest.

    The result always carries a count, including when the count is zero: "no
    anomalies" is an answer, and an answer whose number the verifier cannot
    bind is an answer that gets withheld.
    """
    identifier = result_id or f"anomaly:{series_id}"
    if semantics.unresolved:
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            "Cannot judge a change as unusual while the series' meaning is unresolved: "
            + ", ".join(semantics.unresolved),
            SampleCounts(used=0),
            semantics.unresolved,
        )
    if semantics.cumulative.value in ("since_inception", "yearly_reset"):
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            f"The series accumulates ({semantics.cumulative.value}); convert it to flow "
            "before looking for unusual changes, or every period looks like a rise",
            SampleCounts(used=0),
        )

    window = [
        item
        for item in sorted(observations, key=lambda entry: entry.period_end)
        if (start is None or item.period_end >= start) and (end is None or item.period_end <= end)
    ]
    changes, missing, interrupted = consecutive_changes(window, semantics)
    if len(changes) < minimum_changes:
        return _refuse(
            identifier,
            ResultStatus.INSUFFICIENT,
            f"{len(changes)} period-over-period changes is below the {minimum_changes} "
            "this baseline requires for a stable median and spread",
            SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        )

    differences = [value - previous for _, previous, value in changes]
    ratio_basis = scored_on_ratio(semantics, changes)
    # What is scored, against what is reported: the flag is decided on a comparable
    # basis, while the figure the answer quotes stays in the series' own unit.
    magnitudes = _magnitudes(changes, ratio=ratio_basis)
    centre = median(magnitudes)
    deviations = [abs(value - centre) for value in magnitudes]
    spread = median(deviations)
    scale_used = "median absolute deviation"
    if spread == 0:
        # Over half the changes are identical, so MAD collapsed. Fall back to
        # the mean absolute deviation about the same median, which is the
        # published remedy and is zero only when *every* change is identical.
        # The score below is 0.6745 * (value - centre) / spread, so a fallback spread has
        # to be whatever makes that expression the paper's mean-absolute-deviation score,
        # (value - centre) / (1.253314 * meanAD). Dividing by MAD_TO_SIGMA instead of
        # multiplying made the spread 2.198 times too large, which turned the declared
        # 3.5 cut into 7.7 sigma: a flat rate with three +5 point jumps reported none.
        spread = (sum(deviations) / len(deviations)) * MEANAD_TO_SIGMA * MAD_TO_SIGMA
        scale_used = "mean absolute deviation about the median (MAD was zero)"
    if spread == 0:
        return _refuse(
            identifier,
            ResultStatus.UNDEFINED,
            "Every period-over-period change is identical, so there is no spread to "
            "score against; the series moves by the same amount every period or not at all",
            SampleCounts(used=len(changes), missing=missing, excluded=interrupted),
        )

    def score(value: float) -> float:
        return MAD_TO_SIGMA * (value - centre) / spread

    flagged = [
        (observation, difference, score(magnitude))
        for (observation, _, _), difference, magnitude in zip(
            changes, differences, magnitudes, strict=True
        )
        if abs(score(magnitude)) > threshold
    ]

    values = [
        ResultValue(
            label=f"{series_id} anomalies found",
            value=float(len(flagged)),
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=Period(
                start=window[0].period_start,
                end=window[-1].period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
    ]
    values.extend(
        ResultValue(
            label=f"{series_id} change at {observation.period_end.isoformat()}",
            value=value,
            unit=_difference_unit(semantics),
            scale=_difference_scale(semantics),
            measure=semantics.observation,
            period=Period(
                start=observation.period_start,
                end=observation.period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
        for observation, value, _ in flagged
    )

    warnings: list[str] = [
        "An unusual change is not an error, an event or a cause; it is a period that "
        "moved unlike the others in this window"
    ]
    if ratio_basis:
        warnings.append(
            "A period was judged by how much it moved relative to the level before it, "
            "not by the size of the movement; the figure reported stays in the series' unit"
        )
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "Changes are in an outstanding balance, so an unusual month is unusual net "
            "movement, not unusual new lending"
        )
    if missing:
        warnings.append(
            f"{missing} period(s) had no published value and were skipped; a gap is not zero"
        )
    if interrupted:
        warnings.append(
            f"{interrupted} pair(s) of periods did not follow one another and were left out; "
            "differencing across a hole would report several periods of movement as one"
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.ANOMALY,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="mad_zscore",
        values=values,
        coverage=Period(
            start=window[0].period_start,
            end=window[-1].period_end,
            frequency=semantics.frequency,
            weekly_anchor=semantics.anchor,
        ),
        parameters={
            "series": series_id,
            "method": "median absolute deviation, Iglewicz-Hoaglin modified z-score",
            "examined": "period-over-period change",
            "scored_on": RATIO_BASIS if ratio_basis else DIFFERENCE_BASIS,
            "threshold": threshold,
            "minimum_changes": minimum_changes,
            "median_scored_change": centre,
            "scale_estimator": scale_used,
            "scale": spread,
            "threshold_status": "PROPOSED; no benchmark has measured it",
        },
        samples=SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=warnings,
    )


def _changes(window: Sequence[Observation]) -> tuple[list[tuple[Observation, float, float]], int]:
    """Consecutive (observation, previous level, level), and how many periods had no value.

    A gap breaks the chain rather than being bridged: differencing across it
    would report two periods of movement as one, which is a larger change than
    anything that happened.
    """
    changes: list[tuple[Observation, float, float]] = []
    missing = 0
    previous: float | None = None
    for observation in window:
        if observation.value is None:
            missing += 1
            previous = None
            continue
        if previous is not None:
            changes.append((observation, previous, observation.value))
        previous = observation.value
    return changes, missing


def detect_anomalies(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
    start: date | None = None,
    end: date | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    minimum_changes: int = DEFAULT_MINIMUM_CHANGES,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Flag period-over-period changes that stand apart from the rest.

    The result always carries a count, including when the count is zero: "no
    anomalies" is an answer, and an answer whose number the verifier cannot
    bind is an answer that gets withheld.
    """
    identifier = result_id or f"anomaly:{series_id}"
    if semantics.unresolved:
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            "Cannot judge a change as unusual while the series' meaning is unresolved: "
            + ", ".join(semantics.unresolved),
            SampleCounts(used=0),
            semantics.unresolved,
        )
    if semantics.cumulative.value in ("since_inception", "yearly_reset"):
        return _refuse(
            identifier,
            ResultStatus.ABSTAINED,
            f"The series accumulates ({semantics.cumulative.value}); convert it to flow "
            "before looking for unusual changes, or every period looks like a rise",
            SampleCounts(used=0),
        )

    window = [
        item
        for item in sorted(observations, key=lambda entry: entry.period_end)
        if (start is None or item.period_end >= start) and (end is None or item.period_end <= end)
    ]
    changes, missing, interrupted = consecutive_changes(window, semantics)
    if len(changes) < minimum_changes:
        return _refuse(
            identifier,
            ResultStatus.INSUFFICIENT,
            f"{len(changes)} period-over-period changes is below the {minimum_changes} "
            "this baseline requires for a stable median and spread",
            SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        )

    differences = [value - previous for _, previous, value in changes]
    ratio_basis = scored_on_ratio(semantics, changes)
    # What is scored, against what is reported: the flag is decided on a comparable
    # basis, while the figure the answer quotes stays in the series' own unit.
    magnitudes = _magnitudes(changes, ratio=ratio_basis)
    centre = median(magnitudes)
    deviations = [abs(value - centre) for value in magnitudes]
    spread = median(deviations)
    scale_used = "median absolute deviation"
    if spread == 0:
        # Over half the changes are identical, so MAD collapsed. Fall back to
        # the mean absolute deviation about the same median, which is the
        # published remedy and is zero only when *every* change is identical.
        # The score below is 0.6745 * (value - centre) / spread, so a fallback spread has
        # to be whatever makes that expression the paper's mean-absolute-deviation score,
        # (value - centre) / (1.253314 * meanAD). Dividing by MAD_TO_SIGMA instead of
        # multiplying made the spread 2.198 times too large, which turned the declared
        # 3.5 cut into 7.7 sigma: a flat rate with three +5 point jumps reported none.
        spread = (sum(deviations) / len(deviations)) * MEANAD_TO_SIGMA * MAD_TO_SIGMA
        scale_used = "mean absolute deviation about the median (MAD was zero)"
    if spread == 0:
        return _refuse(
            identifier,
            ResultStatus.UNDEFINED,
            "Every period-over-period change is identical, so there is no spread to "
            "score against; the series moves by the same amount every period or not at all",
            SampleCounts(used=len(changes), missing=missing, excluded=interrupted),
        )

    def score(value: float) -> float:
        return MAD_TO_SIGMA * (value - centre) / spread

    flagged = [
        (observation, difference, score(magnitude))
        for (observation, _, _), difference, magnitude in zip(
            changes, differences, magnitudes, strict=True
        )
        if abs(score(magnitude)) > threshold
    ]

    values = [
        ResultValue(
            label=f"{series_id} anomalies found",
            value=float(len(flagged)),
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=Period(
                start=window[0].period_start,
                end=window[-1].period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
    ]
    values.extend(
        ResultValue(
            label=f"{series_id} change at {observation.period_end.isoformat()}",
            value=value,
            unit=_difference_unit(semantics),
            scale=_difference_scale(semantics),
            measure=semantics.observation,
            period=Period(
                start=observation.period_start,
                end=observation.period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )
        for observation, value, _ in flagged
    )

    warnings: list[str] = [
        "An unusual change is not an error, an event or a cause; it is a period that "
        "moved unlike the others in this window"
    ]
    if ratio_basis:
        warnings.append(
            "A period was judged by how much it moved relative to the level before it, "
            "not by the size of the movement; the figure reported stays in the series' unit"
        )
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "Changes are in an outstanding balance, so an unusual month is unusual net "
            "movement, not unusual new lending"
        )
    if missing:
        warnings.append(
            f"{missing} period(s) had no published value and were skipped; a gap is not zero"
        )
    if interrupted:
        warnings.append(
            f"{interrupted} pair(s) of periods did not follow one another and were left out; "
            "differencing across a hole would report several periods of movement as one"
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.ANOMALY,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="mad_zscore",
        values=values,
        coverage=Period(
            start=window[0].period_start,
            end=window[-1].period_end,
            frequency=semantics.frequency,
            weekly_anchor=semantics.anchor,
        ),
        parameters={
            "series": series_id,
            "method": "median absolute deviation, Iglewicz-Hoaglin modified z-score",
            "examined": "period-over-period change",
            "scored_on": RATIO_BASIS if ratio_basis else DIFFERENCE_BASIS,
            "threshold": threshold,
            "minimum_changes": minimum_changes,
            "median_scored_change": centre,
            "scale_estimator": scale_used,
            "scale": spread,
            "threshold_status": "PROPOSED; no benchmark has measured it",
        },
        samples=SampleCounts(
                used=len(changes),
                missing=missing,
                excluded=interrupted,
                minimum_required=minimum_changes,
            ),
        evidence=ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node),
        warnings=warnings,
    )


def _changes(window: Sequence[Observation]) -> tuple[list[tuple[Observation, float, float]], int]:
    """Consecutive (observation, previous level, level), and how many periods had no value.

    A gap breaks the chain rather than being bridged: differencing across it
    would report two periods of movement as one, which is a larger change than
    anything that happened.
    """
    changes: list[tuple[Observation, float, float]] = []
    missing = 0
    previous: float | None = None
    for observation in window:
        if observation.value is None:
            missing += 1
            previous = None
            continue
        if previous is not None:
            changes.append((observation, previous, observation.value))
        previous = observation.value
    return changes, missing


def _scored_on_ratio(
    semantics: SeriesSemantics, changes: Sequence[tuple[Observation, float, float]]
) -> bool:
    """Whether these changes are scored against the level they came from.

    A difference in the series' own unit grows with the level, so on a balance that
    triples the recent months hold the largest differences whatever happened in them:
    the flags pile up at the end of the window and an early shock cannot compete.
    Measured on the prepared CPI, December 2021 - the record monthly rise of the
    window - scored 0.87 while an ordinary January 2026 scored highest.

    A rate is already comparable across its window: two percentage points is two
    percentage points whether the rate is 8 or 43, so a rate keeps its difference.
    A series that reaches zero or turns negative has no meaningful ratio, so it keeps
    its difference too, and the result says which basis it used.
    """
    if semantics.observation is StockFlow.RATE:
        return False
    return all(previous > 0 and value > 0 for _, previous, value in changes)
