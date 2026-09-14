"""Monthly co-movement of a driver and a target series (M6-25, organizer Turn 1).

The organizer's first question asks how housing credit moved in months when the
housing-loan rate fell, and whether there were months when the rate fell but
credit did not rise. That is a statement about month-over-month directions on
one monthly calendar, not a correlation, so it is computed as exactly that:

- both inputs must already be monthly (the tool reduces a weekly driver first
  and passes the transformation record in);
- a transition compares a month with the previous calendar month, and only when
  both months hold a value for both series — a gap is never bridged;
- the driver "fell" when its change is below zero; the target "did not rise"
  when its change is zero or below. Those thresholds are the definitions, stated
  in the result's parameters rather than tuned.

What the numbers mean still comes from declared semantics. A stock's change is a
net change in the outstanding balance, never disbursement; rates and indices
change in points. Values are nominal. Co-movement is not a cause.

Labels matter to the verifier. A level carries its registered series id so the
store recheck can re-read it; every derived number carries a distinct label,
because a derived value under a series id would be "rechecked" against the
wrong stored figure.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from datetime import date

from pydantic import JsonValue

from kkb_agent.analytics.change import _difference_scale, _difference_unit
from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    StockFlow,
    TransformationRecord,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD = "monthly-direction-v1"
MINIMUM_TRANSITIONS = 2


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _previous_month_end(end: date) -> date:
    return _month_end(end.year - 1, 12) if end.month == 1 else _month_end(end.year, end.month - 1)


def _monthly_period(end: date) -> Period:
    return Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY)


def _refusal(
    result_id: str, status: ResultStatus, reason: str, unresolved: Sequence[str] = ()
) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=result_id,
        kind=ResultKind.COMPARISON,
        status=status,
        tool="analytics",
        method=METHOD,
        reason=reason,
        unresolved_semantics=list(unresolved),
    )


class _DuplicatePeriods(ValueError):
    pass


def _values(observations: Sequence[Observation], start: date, end: date) -> dict[date, float]:
    found: dict[date, float] = {}
    seen: set[date] = set()
    for item in observations:
        if not start <= item.period_end <= end:
            continue
        if item.period_end in seen:
            raise _DuplicatePeriods
        seen.add(item.period_end)
        if item.value is not None:
            found[item.period_end] = item.value
    return found


def co_movement(
    driver: Sequence[Observation],
    driver_semantics: SeriesSemantics,
    target: Sequence[Observation],
    target_semantics: SeriesSemantics,
    *,
    start: date,
    end: date,
    driver_label: str,
    target_label: str,
    input_refs: Sequence[str],
    transformations: Sequence[TransformationRecord] = (),
    parameters: Mapping[str, JsonValue] | None = None,
) -> AnalyticalResult:
    """Directions of both series over each consecutive month pair in [start, end].

    `driver_label` / `target_label` are the value labels. Pass the registered
    series id only for a series whose monthly values are stored as given; pass a
    distinct label for anything reduced or derived.
    """
    result_id = f"co_movement:{driver_label}:{target_label}:{start}:{end}"
    unresolved = [
        f"{name}: {', '.join(semantics.unresolved)}"
        for name, semantics in (("driver", driver_semantics), ("target", target_semantics))
        if semantics.unresolved
    ]
    if unresolved:
        return _refusal(
            result_id, ResultStatus.ABSTAINED, "Series semantics are unresolved", unresolved
        )
    for name, semantics in (("driver", driver_semantics), ("target", target_semantics)):
        if semantics.frequency is not Frequency.MONTHLY:
            return _refusal(
                result_id,
                ResultStatus.ABSTAINED,
                f"The {name} is not monthly; reduce it onto months before comparing directions",
            )
        if semantics.cumulative is not CumulativeKind.NONE:
            return _refusal(
                result_id,
                ResultStatus.ABSTAINED,
                f"The {name} accumulates; convert it to a flow before comparing directions",
            )
    if end < start:
        return _refusal(result_id, ResultStatus.UNDEFINED, "The window ends before it starts")

    try:
        driver_values = _values(driver, start, end)
        target_values = _values(target, start, end)
    except _DuplicatePeriods:
        return _refusal(
            result_id, ResultStatus.ABSTAINED, "Duplicate monthly periods; resolve revisions first"
        )

    months = sorted(set(driver_values) & set(target_values))
    transitions = [
        (month, _previous_month_end(month))
        for month in months
        if _previous_month_end(month) in driver_values
        and _previous_month_end(month) in target_values
    ]
    calendar_months = 0
    cursor = _month_end(start.year, start.month)
    while cursor <= end:
        calendar_months += 1
        cursor = _month_end(cursor.year + (cursor.month == 12), cursor.month % 12 + 1)
    samples = SampleCounts(
        used=len(transitions),
        missing=max(calendar_months - 1 - len(transitions), 0),
        minimum_required=MINIMUM_TRANSITIONS,
    )
    if len(transitions) < MINIMUM_TRANSITIONS:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.COMPARISON,
            status=ResultStatus.INSUFFICIENT,
            tool="analytics",
            method=METHOD,
            samples=samples,
            reason=(
                f"Only {len(transitions)} consecutive month pair(s) hold both series; "
                f"at least {MINIMUM_TRANSITIONS} are needed"
            ),
        )

    driver_change_unit = _difference_unit(driver_semantics)
    target_change_unit = _difference_unit(target_semantics)
    values: list[ResultValue] = []
    for month in months:
        period = _monthly_period(month)
        values.append(_level(target_label, target_values[month], target_semantics, period))
        values.append(_level(driver_label, driver_values[month], driver_semantics, period))

    fell = rose = not_rose = 0
    flagged: list[ResultValue] = []
    for month, previous in transitions:
        period = _monthly_period(month)
        driver_change = driver_values[month] - driver_values[previous]
        target_change = target_values[month] - target_values[previous]
        values.append(
            _change(driver_label, driver_change, driver_change_unit, driver_semantics, period)
        )
        values.append(
            _change(target_label, target_change, target_change_unit, target_semantics, period)
        )
        if driver_change < 0:
            fell += 1
            if target_change > 0:
                rose += 1
            else:
                not_rose += 1
                flagged.append(
                    ResultValue(
                        label=(
                            f"{target_label} month-over-month change in a month when "
                            f"{driver_label} fell and {target_label} did not rise"
                        ),
                        value=target_change,
                        unit=target_change_unit,
                        scale=_difference_scale(target_semantics),
                        measure=target_semantics.observation,
                        period=period,
                    )
                )
    coverage = Period(
        start=transitions[0][0].replace(day=1), end=transitions[-1][0], frequency=Frequency.MONTHLY
    )
    for label, count in (
        ("consecutive monthly transitions compared", len(transitions)),
        (f"transitions where {driver_label} fell", fell),
        (f"transitions where {driver_label} fell and {target_label} rose", rose),
        (f"transitions where {driver_label} fell and {target_label} did not rise", not_rose),
    ):
        values.append(
            ResultValue(
                label=label,
                value=float(count),
                unit=DIMENSIONLESS,
                scale=Scale.ONE,
                period=coverage,
            )
        )
    values.extend(flagged)

    limitations = [
        "Co-movement of directions is not evidence that one series caused the other",
        "Values are nominal; no inflation adjustment was applied",
        "A transition needs both series in a month and in the previous calendar month; "
        "gaps are not bridged",
    ]
    if target_semantics.observation is StockFlow.STOCK:
        limitations.append(
            f"{target_label} is an outstanding stock: its change is the net change in the "
            "balance, not new lending or disbursement"
        )
    if driver_semantics.observation is StockFlow.STOCK:
        limitations.append(f"{driver_label} is an outstanding stock, not a flow")
    return AnalyticalResult(
        result_id=result_id,
        kind=ResultKind.COMPARISON,
        status=ResultStatus.COMPUTED,
        tool="analytics",
        method=METHOD,
        values=values,
        coverage=coverage,
        parameters={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "driver_fell": "driver change < 0",
            "target_did_not_rise": "target change <= 0",
            "transition": "month versus previous calendar month",
            **dict(parameters or {}),
        },
        samples=samples,
        evidence=ResultEvidence(input_refs=list(input_refs), transformations=list(transformations)),
        limitations=limitations,
    )


def _level(label: str, value: float, semantics: SeriesSemantics, period: Period) -> ResultValue:
    return ResultValue(
        label=label,
        value=value,
        unit=semantics.unit,
        scale=semantics.scale,
        measure=semantics.observation,
        period=period,
    )


def _change(
    label: str, value: float, unit: str, semantics: SeriesSemantics, period: Period
) -> ResultValue:
    return ResultValue(
        label=f"{label} month-over-month change",
        value=value,
        unit=unit,
        scale=_difference_scale(semantics),
        measure=semantics.observation,
        period=period,
    )
