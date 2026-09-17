"""Descriptive monthly direction counts over an existing table; no causal inference."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from math import isfinite
from typing import Literal

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
    Scale,
    StockFlow,
    TransformationRecord,
)
from kkb_agent.lakehouse.cumulative import Confidence, detect_cumulative
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, period_bounds

Direction = Literal["up", "down", "unchanged", "non_increasing", "non_decreasing"]
METHOD = "table-direction-comparison-v1"


class TableComparisonRefused(ValueError):
    """The selected columns cannot support the requested comparison."""


def _matches(change: float, direction: Direction) -> bool:
    return {
        "up": change > 0,
        "down": change < 0,
        "unchanged": change == 0,
        "non_increasing": change <= 0,
        "non_decreasing": change >= 0,
    }[direction]


#: Measurement kinds whose month-over-month direction needs no further evidence.
LEVEL_MEASURES = (StockFlow.STOCK, StockFlow.RATE, StockFlow.INDEX)


def _column(source: AnalyticalResult, label: str, notes: list[str]) -> dict[date, float]:
    """One column's monthly values; `notes` receives how its semantics were settled.

    Direction counts compare a column with itself, so they need one consistent
    unit and scale per column, not a known one. What they do need is that a
    month-over-month change means a change in level: a year-to-date cumulative
    column rises all year by construction. A stock, rate or index says so; any
    other column is admitted only when its own values rule accumulation out
    (they fall inside a calendar year), which is recorded, never assumed.
    """
    selected = [value for value in source.values if value.label == label]
    if not selected:
        raise TableComparisonRefused("A selected column does not exist in the table")
    signatures = {(v.unit, v.scale, v.measure) for v in selected}
    if len(signatures) != 1:
        raise TableComparisonRefused("A selected column changes units, scale or measurement kind")
    values: dict[date, float] = {}
    for value in selected:
        if value.unit == DIMENSIONLESS:
            raise TableComparisonRefused("A selected column has summary semantics")
        period = value.period
        if period is None or period.frequency is not Frequency.MONTHLY:
            raise TableComparisonRefused("A selected column is not monthly")
        try:
            valid = (period.start, period.end) == period_bounds(Frequency.MONTHLY, period.end)
        except SemanticsError:
            valid = False
        if not valid or period.end in values or not isfinite(value.value):
            raise TableComparisonRefused("A selected column has invalid/duplicate dates or values")
        values[period.end] = value.value
    first = selected[0]
    if first.semantics_are_unresolved:
        notes.append(
            f"{label!r} has no stated unit or scale; only its own month-over-month "
            "directions were used, never its level"
        )
    if first.measure not in LEVEL_MEASURES:
        verdict = detect_cumulative(
            [
                Observation(date(end.year, end.month, 1), end, level)
                for end, level in sorted(values.items())
            ],
            frequency=Frequency.MONTHLY,
        )
        if verdict.kind is not CumulativeKind.NONE or verdict.confidence is not Confidence.HIGH:
            raise TableComparisonRefused(
                f"{label!r} does not state whether it is a level or a cumulative total, and its "
                "values cannot rule out year-to-date accumulation; state which it is"
            )
        notes.append(
            f"{label!r} does not state its stock/flow meaning; it was compared as a level "
            "because its values fall within calendar years, which rules out year-to-date "
            "accumulation (inferred from the values)"
        )
    return values


def real_counterpart(source: AnalyticalResult, label: str) -> str | None:
    """The deflated column derived from this one, when the table already carries it.

    `deflation` names its output `"<column> real, <YYYY-MM> prices (<index>)"`, so
    the relationship between a nominal column and its real counterpart is readable
    from the labels without re-deriving anything.
    """
    prefix = f"{label} real, "
    return next((value.label for value in source.values if value.label.startswith(prefix)), None)


def compare_table_directions(
    source: AnalyticalResult,
    *,
    driver_column: str,
    target_column: str,
    driver_direction: Direction,
    target_direction: Direction,
    when_column: str | None = None,
    when_direction: Direction | None = None,
) -> AnalyticalResult:
    """Keep the table and count exactly defined patterns over consecutive months.

    A transition requires all selected columns in both months. A missing month
    is never bridged; the optional condition selects a subset of those valid
    transitions. All denominators are explicit, and zero qualifying months is
    a computed zero count rather than a fabricated percentage.
    """
    if source.status is not ResultStatus.COMPUTED:
        raise TableComparisonRefused("The source is not a computed table")
    if driver_column == target_column:
        raise TableComparisonRefused("Select two different columns")
    if (when_column is None) != (when_direction is None):
        raise TableComparisonRefused("The condition column and direction must be given together")
    semantic_notes: list[str] = []
    driver = _column(source, driver_column, semantic_notes)
    target = _column(source, target_column, semantic_notes)
    condition = _column(source, when_column, semantic_notes) if when_column is not None else None
    columns = [driver, target, *([condition] if condition is not None else [])]
    union = set().union(*(column.keys() for column in columns))
    common = set.intersection(*(set(column) for column in columns))
    transitions = [
        (end, end.replace(day=1) - timedelta(days=1))
        for end in sorted(common)
        if end.replace(day=1) - timedelta(days=1) in common
    ]
    if not transitions:
        raise TableComparisonRefused("No consecutive monthly pair has every selected value")
    first, last = min(union), max(union)
    possible = (last.year - first.year) * 12 + last.month - first.month

    criteria = {
        "driver_column": driver_column,
        "driver_direction": driver_direction,
        "target_column": target_column,
        "target_direction": target_direction,
        "when_column": when_column,
        "when_direction": when_direction,
    }
    comparison_id = hashlib.sha256(json.dumps(criteria, sort_keys=True).encode()).hexdigest()[:12]
    prefix = f"table comparison {comparison_id}: "
    if any(value.label.startswith(prefix) for value in source.values):
        raise TableComparisonRefused("This exact comparison is already present in the table")
    eligible: list[date] = []
    driver_matches: list[date] = []
    target_matches: list[date] = []
    joint: list[date] = []
    for end, previous in transitions:
        if condition is not None and when_direction is not None:
            if not _matches(condition[end] - condition[previous], when_direction):
                continue
        eligible.append(end)
        driver_hit = _matches(driver[end] - driver[previous], driver_direction)
        target_hit = _matches(target[end] - target[previous], target_direction)
        if driver_hit:
            driver_matches.append(end)
        if target_hit:
            target_matches.append(end)
        if driver_hit and target_hit:
            joint.append(end)
    coverage = Period(
        start=transitions[0][0].replace(day=1), end=transitions[-1][0], frequency=Frequency.MONTHLY
    )
    # A table that already carries the deflated column can be compared either way,
    # and the counts differ. Say which one this comparison used, so an answer built
    # on it cannot read as a statement about real change.
    nominal_notes = [
        f"{column!r} was compared in nominal terms although this table also carries "
        f"{counterpart!r}; a question about real change needs the real column"
        for column in (driver_column, target_column, *([when_column] if when_column else []))
        if (counterpart := real_counterpart(source, column)) is not None
    ]
    counts = {
        "complete monthly transitions": len(transitions),
        "transitions excluded for missing observations": possible - len(transitions),
        "transitions meeting the condition": len(eligible),
        "eligible transitions matching the driver direction": len(driver_matches),
        "eligible transitions matching the target direction": len(target_matches),
        "eligible transitions matching both directions": len(joint),
    }
    metrics = [
        ResultValue(
            label=prefix + label,
            value=float(count),
            unit=DIMENSIONLESS,
            scale=Scale.ONE,
            period=coverage,
        )
        for label, count in counts.items()
    ]
    record = TransformationRecord(
        operation="table_co_movement",
        parameters={
            **criteria,
            "comparison_id": comparison_id,
            "transition": "current month minus previous calendar month; unrounded stored values",
            "eligible_periods": [end.isoformat() for end in eligible],
            "joint_periods": [end.isoformat() for end in joint],
            "counts": {key: value for key, value in counts.items()},
            "missing_transition_count": possible - len(transitions),
        },
        input_refs=[
            source.result_id,
            driver_column,
            target_column,
            *([when_column] if when_column else []),
        ],
        output_ref=prefix.rstrip(),
    )
    earlier = source.evidence.transformations if source.evidence is not None else []
    return AnalyticalResult(
        result_id=f"table_co_movement:{source.result_id}:{comparison_id}",
        kind=ResultKind.COMPARISON,
        status=ResultStatus.COMPUTED,
        tool="change_detection",
        method=METHOD,
        values=[*source.values, *metrics],
        coverage=source.coverage,
        parameters=dict(source.parameters),
        evidence=ResultEvidence(
            input_refs=[source.evidence.lineage_node]
            if source.evidence and source.evidence.lineage_node
            else [source.result_id],
            transformations=[*earlier, record],
        ),
        warnings=[
            *source.warnings,
            *(
                ["Missing selected observations exclude monthly transitions; no gap is bridged"]
                if possible > len(transitions)
                else []
            ),
        ],
        limitations=[
            *source.limitations,
            *nominal_notes,
            *semantic_notes,
            "Direction counts describe contemporaneous movement, not an identified causal effect; "
            "other factors are not controlled",
            "Directions use the selected column as stored, including its existing price reference; "
            "index levels with different bases are not compared",
            "A stock change is a net balance change, not new lending; "
            "counts condition on complete consecutive monthly observations",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )
