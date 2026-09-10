"""Change and period comparison (M6-02, M6-03, M6-04).

Subtracting one number from another is not the hard part. Deciding whether the
subtraction *means* anything is, and that decision comes entirely from the
series' declared semantics rather than from the numbers:

- A **stock** differenced gives the change in an outstanding balance. A **flow**
  differenced gives the change in a rate of activity. Neither is disbursement,
  and the BDDK inventory found exactly this trap: `Tüketici Kredileri - Konut`
  is a stock that falls in 8 of 65 steps, so anyone reading its difference as
  new lending is wrong by the whole repayment stream.
- A **cumulative** series must be converted to flow before any of this, or the
  difference silently measures accumulation instead of activity.
- A **rate** or an **index** changes in *points*, not in its own unit. Reading
  40 -> 46.75 as "+6.75 percent" instead of "+6.75 percentage points" is the
  most common financial-writing error there is, and the two differ by a factor
  of two and a half here.

The refusals matter as much as the arithmetic. A relative change needs a base
that can carry one: zero has no proportion, and a negative base inverts the
sign so that a genuine improvement reads as a fall. Both return UNDEFINED with
a reason rather than a number nobody should use. A missing endpoint returns
INSUFFICIENT and names the period, because forward-filling a gap draws a flat
line indistinguishable from a real one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from kkb_agent.core import (
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

#: A rate's absolute change is in points, not in the rate's own unit. Keeping
#: the two apart in the type is what stops "+6.75 percent" from being written
#: when the series moved 40 -> 46.75.
PERCENTAGE_POINT: Final = "percentage point"
INDEX_POINT: Final = "index point"
PERCENT: Final = "percent"

#: Where observations are read from, unless the caller names something better.
DEFAULT_INPUTS: Final = ("silver_observations",)


def _difference_unit(semantics: SeriesSemantics) -> str:
    if semantics.observation is StockFlow.RATE:
        return PERCENTAGE_POINT
    if semantics.observation is StockFlow.INDEX:
        return INDEX_POINT
    return semantics.unit


def _difference_scale(semantics: SeriesSemantics) -> Scale:
    # A difference in points carries no thousands/millions multiplier, whatever
    # the underlying series declared.
    if semantics.observation in (StockFlow.RATE, StockFlow.INDEX):
        return Scale.ONE
    return semantics.scale


def _at(observations: Sequence[Observation], when: date) -> Observation | None:
    for observation in observations:
        if observation.period_end == when:
            return observation
    return None


def _span(first: Observation, last: Observation, semantics: SeriesSemantics) -> Period:
    return Period(
        start=first.period_start,
        end=last.period_end,
        frequency=semantics.frequency,
        weekly_anchor=semantics.anchor,
    )


def _evidence(input_refs: Sequence[str], lineage_node: str | None) -> ResultEvidence:
    return ResultEvidence(input_refs=list(input_refs), lineage_node=lineage_node)


@dataclass(frozen=True, slots=True)
class _Endpoints:
    """Two published, non-null observations and their values.

    The values travel alongside so nothing downstream has to re-narrow them.
    An `assert` would do it in one line and vanish under `-O`, which is not a
    guarantee at all.
    """

    first: Observation
    last: Observation
    base: float
    final: float


def _abstain(
    result_id: str, kind: ResultKind, reason: str, unresolved: Sequence[str] = ()
) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=result_id,
        kind=kind,
        status=ResultStatus.ABSTAINED,
        tool="analytics",
        method="change",
        reason=reason,
        unresolved_semantics=list(unresolved),
    )


def _endpoints(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    start: date,
    end: date,
    result_id: str,
    kind: ResultKind,
) -> _Endpoints | AnalyticalResult:
    """Both endpoints, or the result explaining why there are not two.

    Selection is by exact period end. A requested date that is not a published
    period is refused rather than resolved to a neighbour: silently comparing
    the wrong month is indistinguishable in the output from comparing the right
    one, which is what makes it dangerous.
    """
    if semantics.unresolved:
        return _abstain(
            result_id,
            kind,
            "Cannot compute a change while the series' meaning is unresolved: "
            + ", ".join(semantics.unresolved),
            semantics.unresolved,
        )
    if semantics.cumulative.value in ("since_inception", "yearly_reset"):
        return _abstain(
            result_id,
            kind,
            f"The series accumulates ({semantics.cumulative.value}); convert it to flow "
            "before differencing, or the change measures accumulation, not activity",
        )
    if end < start:
        return _abstain(result_id, kind, "The comparison ends before it starts")
    if not observations:
        return AnalyticalResult(
            result_id=result_id,
            kind=kind,
            status=ResultStatus.INSUFFICIENT,
            tool="analytics",
            method="change",
            samples=SampleCounts(used=0, minimum_required=2),
            reason="No observations were supplied for this range",
        )

    first, last = _at(observations, start), _at(observations, end)
    if first is None or last is None:
        absent = [
            when.isoformat() for when, found in ((start, first), (end, last)) if found is None
        ]
        published = sorted(item.period_end.isoformat() for item in observations)
        return AnalyticalResult(
            result_id=result_id,
            kind=kind,
            status=ResultStatus.INSUFFICIENT,
            tool="analytics",
            method="change",
            samples=SampleCounts(used=0, minimum_required=2),
            reason=(
                f"No observation ends on {', '.join(absent)}; the series publishes "
                f"{published[0]}..{published[-1]}"
            ),
        )
    base, final = first.value, last.value
    if base is None or final is None:
        empty = [when.isoformat() for when, value in ((start, base), (end, final)) if value is None]
        return AnalyticalResult(
            result_id=result_id,
            kind=kind,
            status=ResultStatus.INSUFFICIENT,
            tool="analytics",
            method="change",
            samples=SampleCounts(used=0, missing=len(empty), minimum_required=2),
            reason=(
                f"The series published no value for {', '.join(empty)}; a gap is not zero "
                "and is not carried forward"
            ),
        )
    return _Endpoints(first, last, base, final)


def absolute_change(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    start: date,
    end: date,
    series_id: str,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """How much the series moved between two published periods.

    For a stock this is the change in the level, which is *not* new activity;
    the warning says so, because the difference between a balance and a flow is
    where a plausible-looking wrong answer comes from.
    """
    identifier = result_id or f"change:{series_id}:{start.isoformat()}:{end.isoformat()}"
    found = _endpoints(observations, semantics, start, end, identifier, ResultKind.CHANGE)
    if isinstance(found, AnalyticalResult):
        return found
    first, last = found.first, found.last

    warnings: list[str] = []
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "This is the change in an outstanding balance, not new lending or disbursement"
        )
    if semantics.observation in (StockFlow.RATE, StockFlow.INDEX):
        warnings.append(f"Stated in {_difference_unit(semantics)}s, not in {semantics.unit}")

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.CHANGE,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="absolute_change",
        values=[
            ResultValue(
                label=f"{series_id} absolute change",
                value=found.final - found.base,
                unit=_difference_unit(semantics),
                scale=_difference_scale(semantics),
                measure=semantics.observation,
                period=_span(first, last, semantics),
            )
        ],
        coverage=_span(first, last, semantics),
        parameters={"from": start.isoformat(), "to": end.isoformat(), "series": series_id},
        samples=SampleCounts(used=2, minimum_required=2),
        evidence=_evidence(input_refs, lineage_node),
        warnings=warnings,
    )


def relative_change(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    start: date,
    end: date,
    series_id: str,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """The move as a percentage of where it started.

    The denominator decides whether this exists at all. Zero has no proportion,
    and a negative base inverts the sign so that a debt shrinking from -100 to
    -50 reads as -50%. Both return UNDEFINED with the reason rather than a
    number that will be quoted without its caveat.
    """
    identifier = result_id or f"relchange:{series_id}:{start.isoformat()}:{end.isoformat()}"
    found = _endpoints(observations, semantics, start, end, identifier, ResultKind.CHANGE)
    if isinstance(found, AnalyticalResult):
        return found
    first, last = found.first, found.last
    base = found.base
    if base == 0:
        return AnalyticalResult(
            result_id=identifier,
            kind=ResultKind.CHANGE,
            status=ResultStatus.UNDEFINED,
            tool="analytics",
            method="relative_change",
            samples=SampleCounts(used=2),
            reason=(
                f"Relative change is undefined from a base of zero on "
                f"{first.period_end.isoformat()}; report the absolute change instead"
            ),
        )
    if base < 0:
        return AnalyticalResult(
            result_id=identifier,
            kind=ResultKind.CHANGE,
            status=ResultStatus.UNDEFINED,
            tool="analytics",
            method="relative_change",
            samples=SampleCounts(used=2),
            reason=(
                f"Relative change from a negative base ({base}) inverts its sign and would "
                "read as a fall when the value rose; report the absolute change instead"
            ),
        )

    warnings: list[str] = []
    if semantics.observation is StockFlow.RATE:
        warnings.append(
            "A percentage change of a rate is not a change in percentage points; "
            f"the point change is the {PERCENTAGE_POINT} figure"
        )

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.CHANGE,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="relative_change",
        values=[
            ResultValue(
                label=f"{series_id} relative change",
                value=(found.final - base) / base * 100.0,
                unit=PERCENT,
                scale=Scale.ONE,
                period=_span(first, last, semantics),
            )
        ],
        coverage=_span(first, last, semantics),
        parameters={"from": start.isoformat(), "to": end.isoformat(), "series": series_id},
        samples=SampleCounts(used=2, minimum_required=2),
        evidence=_evidence(input_refs, lineage_node),
        warnings=warnings,
    )


def compare_periods(
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    start: date,
    end: date,
    series_id: str,
    result_id: str | None = None,
    input_refs: Sequence[str] = DEFAULT_INPUTS,
    lineage_node: str | None = None,
) -> AnalyticalResult:
    """Both endpoint levels and the move between them, in one result.

    An answer about a change needs the levels too — "it rose 4.5%" is not
    checkable without them, and the verifier can only bind numbers it was
    given. The relative figure is included only when it exists; a zero or
    negative base leaves the comparison with its levels and its absolute
    change, and says why the percentage is absent.
    """
    identifier = result_id or f"compare:{series_id}:{start.isoformat()}:{end.isoformat()}"
    found = _endpoints(observations, semantics, start, end, identifier, ResultKind.COMPARISON)
    if isinstance(found, AnalyticalResult):
        return found
    first, last = found.first, found.last

    def level(observation: Observation, value: float) -> ResultValue:
        return ResultValue(
            label=f"{series_id} at {observation.period_end.isoformat()}",
            value=value,
            unit=semantics.unit,
            scale=semantics.scale,
            measure=semantics.observation,
            period=Period(
                start=observation.period_start,
                end=observation.period_end,
                frequency=semantics.frequency,
                weekly_anchor=semantics.anchor,
            ),
        )

    span = _span(first, last, semantics)
    values = [
        level(first, found.base),
        level(last, found.final),
        ResultValue(
            label=f"{series_id} absolute change",
            value=found.final - found.base,
            unit=_difference_unit(semantics),
            scale=_difference_scale(semantics),
            measure=semantics.observation,
            period=span,
        ),
    ]
    warnings: list[str] = []
    if semantics.observation is StockFlow.STOCK:
        warnings.append(
            "This is the change in an outstanding balance, not new lending or disbursement"
        )

    relative = relative_change(
        observations,
        semantics,
        start=start,
        end=end,
        series_id=series_id,
        input_refs=input_refs,
        lineage_node=lineage_node,
    )
    if relative.status is ResultStatus.COMPUTED:
        values.append(relative.values[0])
        warnings.extend(relative.warnings)
    elif relative.reason is not None:
        warnings.append(f"No relative change: {relative.reason}")

    return AnalyticalResult(
        result_id=identifier,
        kind=ResultKind.COMPARISON,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method="compare_periods",
        values=values,
        coverage=span,
        parameters={"from": start.isoformat(), "to": end.isoformat(), "series": series_id},
        samples=SampleCounts(used=2, minimum_required=2),
        evidence=_evidence(input_refs, lineage_node),
        warnings=warnings,
    )
