"""Closed, deterministic transformations of an existing period table.

These operations consume only a trusted published result.  They neither read a
new source nor infer a calendar: rebasing adds one index column, while alignment
and filtering select existing period cells.  Missing cells stay missing and
non-period summary values are dropped when the row set changes because their
old aggregate would no longer describe the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Final, Literal

from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
    TransformationRecord,
)

REBASE_METHOD: Final = "rebase-index-v1"
ALIGN_METHOD: Final = "align-exact-periods-v1"
FILTER_METHOD: Final = "filter-period-range-v1"
REBASE_FORMULA: Final = "new_index = old_index / old_index_reference * new_base"

PeriodKey = tuple[date, date, Frequency, str | None]


class TableShapeRefused(ValueError):
    """The requested shape change cannot be made without inventing semantics."""


@dataclass(frozen=True, slots=True)
class ShapedTable:
    values: tuple[ResultValue, ...]
    coverage: Period
    transformation: TransformationRecord
    dropped_non_period_values: int


@dataclass(frozen=True, slots=True)
class RebasedColumn:
    values: tuple[ResultValue, ...]
    transformation: TransformationRecord
    label: str


def _key(value: ResultValue) -> PeriodKey:
    if value.period is None:  # pragma: no cover - guarded by callers
        raise TableShapeRefused("A table cell needs an explicit period")
    period = value.period
    anchor = period.weekly_anchor.value if period.weekly_anchor is not None else None
    return period.start, period.end, period.frequency, anchor


def _period_columns(source: AnalyticalResult) -> tuple[dict[str, set[PeriodKey]], Frequency, int]:
    # Selecting existing cells reads periods only. A column whose unit a document
    # did not state stays unresolved and travels with the table; it is not a
    # reason to refuse the other columns (operation-scoped semantics).
    if source.status is not ResultStatus.COMPUTED:
        raise TableShapeRefused("The source table is not computed")
    raw: dict[str, set[PeriodKey]] = {}
    non_period = 0
    for value in source.values:
        if value.period is None:
            non_period += 1
            continue
        if value.period.frequency is Frequency.UNKNOWN:
            raise TableShapeRefused("The source table has an unknown period frequency")
        key = _key(value)
        cells = raw.setdefault(value.label, set())
        if key in cells:
            raise TableShapeRefused("The source table has duplicate column-period values")
        cells.add(key)
    columns = {label: cells for label, cells in raw.items() if len(cells) >= 2}
    non_period += sum(len(cells) for cells in raw.values() if len(cells) < 2)
    if not columns:
        raise TableShapeRefused("The source contains no period table with at least two rows")
    frequencies = {key[2] for cells in columns.values() for key in cells}
    if len(frequencies) != 1:
        raise TableShapeRefused("The source table mixes period frequencies; convert them first")
    return columns, next(iter(frequencies)), non_period


def _coverage(values: Sequence[ResultValue], frequency: Frequency) -> Period:
    periods = [value.period for value in values if value.period is not None]
    if not periods:  # pragma: no cover - callers reject an empty selection
        raise TableShapeRefused("The requested table has no period rows")
    return Period(
        start=min(period.start for period in periods),
        end=max(period.end for period in periods),
        frequency=frequency,
        weekly_anchor=periods[0].weekly_anchor if frequency is Frequency.WEEKLY else None,
    )


def rebase_index(
    source: AnalyticalResult,
    *,
    column_label: str,
    reference_period: date,
    new_base: float,
) -> RebasedColumn:
    """Add a rescaled copy of one index column using an explicit reference."""
    # The rebased column itself must be a typed index (checked below); other
    # unresolved columns are unchanged and stay declared.
    if source.status is not ResultStatus.COMPUTED:
        raise TableShapeRefused("The source table is not computed")
    if not isfinite(new_base) or new_base <= 0:
        raise TableShapeRefused("The new index base must be finite and positive")
    column = [value for value in source.values if value.label == column_label]
    if not column:
        raise TableShapeRefused(f"No values are labelled {column_label!r}")
    if len(column) < 2:
        raise TableShapeRefused(f"{column_label} is not a table column with at least two rows")
    periods: set[PeriodKey] = set()
    frequencies: set[Frequency] = set()
    reference: float | None = None
    for value in column:
        if (
            value.period is None
            or value.period.frequency is Frequency.UNKNOWN
            or value.unit != "index"
            or value.scale is not Scale.ONE
            or value.measure is not StockFlow.INDEX
        ):
            raise TableShapeRefused(
                f"{column_label} is not an explicitly typed, unscaled period index"
            )
        if not isfinite(value.value) or value.value <= 0:
            raise TableShapeRefused(f"{column_label} holds a non-positive or non-finite value")
        key = _key(value)
        if key in periods:
            raise TableShapeRefused(f"{column_label} has duplicate periods")
        periods.add(key)
        frequencies.add(value.period.frequency)
        if value.period.end == reference_period:
            reference = value.value
    if len(frequencies) != 1:
        raise TableShapeRefused(f"{column_label} mixes period frequencies")
    if reference is None:
        raise TableShapeRefused(
            f"{column_label} has no value at reference period {reference_period.isoformat()}"
        )
    base_text = format(new_base, ".15g")
    label = f"{column_label} rebased, {reference_period.isoformat()}={base_text}"
    if any(value.label == label for value in source.values):
        raise TableShapeRefused("The source table already holds that rebased column")
    values = tuple(
        value.model_copy(update={"label": label, "value": value.value / reference * new_base})
        for value in column
    )
    transformation = TransformationRecord(
        operation="rebase",
        parameters={
            "formula": REBASE_FORMULA,
            "column": column_label,
            "reference_period": reference_period.isoformat(),
            "reference_value": reference,
            "new_base": new_base,
            "fill": "none",
        },
        input_refs=[source.result_id, column_label],
        output_ref=label,
    )
    return RebasedColumn(values, transformation, label)


def align_periods(
    source: AnalyticalResult,
    *,
    columns: Sequence[str],
    join: Literal["inner", "left"],
    anchor_column: str | None,
) -> ShapedTable:
    """Select exact existing periods by an explicit inner or anchored-left policy."""
    named, frequency, non_period = _period_columns(source)
    selected = tuple(columns)
    if len(selected) < 2 or len(set(selected)) != len(selected):
        raise TableShapeRefused("Alignment needs at least two distinct column labels")
    missing = [label for label in selected if label not in named]
    if missing:
        raise TableShapeRefused(f"Alignment columns are absent: {', '.join(missing)}")
    if join == "inner":
        if anchor_column is not None:
            raise TableShapeRefused("Inner alignment does not take an anchor column")
        target = set.intersection(*(named[label] for label in selected))
    elif join == "left":
        if anchor_column is None or anchor_column not in selected:
            raise TableShapeRefused("Left alignment needs an anchor_column listed in columns")
        target = set(named[anchor_column])
    else:  # pragma: no cover - Literal is also enforced at the tool boundary
        raise TableShapeRefused("Unsupported alignment policy")
    if not target:
        raise TableShapeRefused("The selected columns have no periods under that alignment policy")
    values = tuple(
        value
        for value in source.values
        if value.label in named and value.period is not None and _key(value) in target
    )
    missing_cells = sum(len(target - named[label]) for label in selected)
    transformation = TransformationRecord(
        operation="align",
        parameters={
            "join": f"{join}_exact_period",
            "columns": list(selected),
            "anchor_column": anchor_column,
            "frequency": frequency.value,
            "period_rows": len(target),
            "missing_selected_cells": missing_cells,
            "dropped_non_period_values": non_period,
            "fill": "none",
        },
        input_refs=[source.result_id, *selected],
        output_ref=source.result_id,
    )
    return ShapedTable(values, _coverage(values, frequency), transformation, non_period)


def filter_periods(
    source: AnalyticalResult,
    *,
    start_period: date | None,
    end_period: date | None,
) -> ShapedTable:
    """Keep existing cells whose period end is inside an explicit inclusive range."""
    named, frequency, non_period = _period_columns(source)
    if start_period is None and end_period is None:
        raise TableShapeRefused("Period filtering needs a start_period or end_period")
    if start_period is not None and end_period is not None and start_period > end_period:
        raise TableShapeRefused("start_period must not be after end_period")
    values = tuple(
        value
        for value in source.values
        if value.label in named
        and value.period is not None
        and (start_period is None or value.period.end >= start_period)
        and (end_period is None or value.period.end <= end_period)
    )
    if not values:
        raise TableShapeRefused("The requested period range contains no table rows")
    kept_periods = {_key(value) for value in values}
    transformation = TransformationRecord(
        operation="filter",
        parameters={
            "predicate": "period_end_inclusive",
            "start_period": start_period.isoformat() if start_period is not None else None,
            "end_period": end_period.isoformat() if end_period is not None else None,
            "period_rows": len(kept_periods),
            "dropped_non_period_values": non_period,
        },
        input_refs=[source.result_id],
        output_ref=source.result_id,
    )
    return ShapedTable(values, _coverage(values, frequency), transformation, non_period)
