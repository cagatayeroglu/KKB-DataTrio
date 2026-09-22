"""Closed, deterministic transformations of an existing period table.

These operations consume only a trusted published result.  They neither read a
new source nor infer a calendar: rebasing adds one index column, while alignment
and filtering select existing period cells.  Missing cells stay missing and
non-period summary values are dropped when the row set changes because their
old aggregate would no longer describe the result.
"""

from __future__ import annotations

import re
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
from kkb_agent.lakehouse.periods import daily_steps

REBASE_METHOD: Final = "rebase-index-v1"
ALIGN_METHOD: Final = "align-exact-periods-v1"
FILTER_METHOD: Final = "filter-period-range-v1"
REBASE_FORMULA: Final = "new_index = old_index / old_index_reference * new_base"
CHANGE_METHOD: Final = "period-change-v1"
CHANGE_FORMULAS: Final = {
    "difference": "change[t] = value[t] - value[t - lag]",
    "percent": "change[t] = (value[t] / value[t - lag] - 1) * 100",
}
COMBINE_METHOD: Final = "combine-columns-v1"
COMBINE_FORMULA: Final = "combined[t] = column_1[t] + ... + column_n[t]"
#: How an unnamed group is labelled: the summed labels, in the order the reader gave them.
COMBINE_SEPARATOR: Final = " + "
#: A difference of rates is in points and of an index in index points (the convention
#: `compare` and `co_movement` already use); a percent change is a plain percentage.
PERCENTAGE_POINT: Final = "percentage point"
INDEX_POINT: Final = "index point"
ChangeKind = Literal["difference", "percent"]

PeriodKey = tuple[date, date, Frequency, str | None]


#: A month written as YYYY-MM inside a warning, which is how every warning here
#: names a period it is about.
_NAMED_MONTH: Final = re.compile(r"\b(\d{4})-(0[1-9]|1[0-2])\b")


def names_only_excluded_months(warning: str, coverage: Period) -> bool:
    """Whether a warning names months and this coverage holds none of them.

    A table filtered to 2025 kept carrying "1 month(s) not yet ended at retrieval
    were left out" about September 2026, and so did every change computed from it,
    which read as a limitation of the answer it was not (finding L2-4). A warning
    that names no month says nothing about a range and always travels.
    """
    months = [date(int(year), int(month), 1) for year, month in _NAMED_MONTH.findall(warning)]
    if not months:
        return False
    first = coverage.start.replace(day=1)
    last = coverage.end.replace(day=1)
    return all(month < first or month > last for month in months)


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


@dataclass(frozen=True, slots=True)
class CombinedColumn:
    values: tuple[ResultValue, ...]
    transformation: TransformationRecord
    label: str
    #: Period ends where at least one summed column had no finite value, so the group
    #: total was left empty rather than reported as a partial sum.
    empty_periods: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class ChangedColumn:
    values: tuple[ResultValue, ...]
    transformation: TransformationRecord
    label: str
    #: Every period end that shares the largest rise (or fall): a tie is several answers.
    largest_increase: tuple[date, ...]
    largest_decrease: tuple[date, ...]


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


def _steps_apart(earlier: Period, later: Period) -> int | None:
    """How many reporting periods separate two cells, or None when the calendar cannot say.

    DAILY counts calendar days; BUSINESS_DAY counts weekdays, without inventing
    holiday closures. Only an explicitly irregular column uses previous observation.
    """
    months = (later.end.year - earlier.end.year) * 12 + (later.end.month - earlier.end.month)
    days = (later.end - earlier.end).days
    frequency = later.frequency
    if frequency is Frequency.MONTHLY:
        return months
    if frequency is Frequency.QUARTERLY:
        return months // 3 if months % 3 == 0 else -1
    if frequency is Frequency.SEMIANNUAL:
        return months // 6 if months % 6 == 0 else -1
    if frequency is Frequency.ANNUAL:
        return later.end.year - earlier.end.year
    if frequency is Frequency.WEEKLY:
        return days // 7 if days % 7 == 0 else -1
    if frequency in (Frequency.DAILY, Frequency.BUSINESS_DAY):
        return daily_steps(frequency, earlier.end, later.end)
    return None


def period_change(
    source: AnalyticalResult,
    *,
    column_label: str,
    kind: ChangeKind,
    lag: int = 1,
) -> ChangedColumn:
    """Add the period-over-period change of one column; every existing cell is kept.

    `difference` is value[t] - value[t-lag] in the column's own unit (points for a rate or
    an index); `percent` is (value[t] / value[t-lag] - 1) * 100 and needs a positive
    predecessor, so it is refused for a rate (its change is read in points) and left empty
    where the predecessor is zero or negative. A period whose predecessor is missing - the
    first `lag` rows, or the row after a gap - gets no value: nothing is bridged.

    A column whose unit a document did not state is still a column of numbers: its percent
    change is a plain percentage, and its difference carries the same unresolved unit the
    column has (live J3, 2026-09-19: the BIST endpoint's `clval` states no unit).
    """
    if source.status is not ResultStatus.COMPUTED:
        raise TableShapeRefused("The source table is not computed")
    if not 1 <= lag <= 12:
        raise TableShapeRefused("lag must be between 1 and 12 periods")
    column = [value for value in source.values if value.label == column_label]
    if not column:
        raise TableShapeRefused(f"No values are labelled {column_label!r}")
    if len(column) <= lag:
        raise TableShapeRefused(
            f"{column_label} has too few rows for a change over {lag} period(s)"
        )
    frequencies: set[Frequency] = set()
    seen: set[PeriodKey] = set()
    cells: list[tuple[ResultValue, Period]] = []
    for value in column:
        if value.period is None or value.period.frequency is Frequency.UNKNOWN:
            raise TableShapeRefused(f"{column_label} is not a period column")
        if not isfinite(value.value):
            raise TableShapeRefused(f"{column_label} holds a non-finite value")
        key = _key(value)
        if key in seen:
            raise TableShapeRefused(f"{column_label} has duplicate periods")
        seen.add(key)
        frequencies.add(value.period.frequency)
        cells.append((value, value.period))
    if len(frequencies) != 1:
        raise TableShapeRefused(f"{column_label} mixes period frequencies")
    first = column[0]
    if kind == "percent" and first.measure is StockFlow.RATE:
        raise TableShapeRefused(
            f"{column_label} is a rate; its change is read in points - use kind=difference"
        )
    label = (
        f"{column_label} change (lag {lag})"
        if kind == "difference"
        else f"{column_label} % change (lag {lag})"
    )
    if any(value.label == label for value in source.values):
        raise TableShapeRefused("The source table already holds that change column")
    unit: str | None
    scale: Scale | None
    measure: StockFlow | None
    if kind == "percent":
        unit, scale, measure = "percent", Scale.ONE, StockFlow.RATE
    elif first.measure is StockFlow.RATE:
        unit, scale, measure = PERCENTAGE_POINT, Scale.ONE, first.measure
    elif first.measure is StockFlow.INDEX:
        unit, scale, measure = INDEX_POINT, Scale.ONE, first.measure
    else:
        unit, scale, measure = first.unit, first.scale, first.measure
    ordered = sorted(cells, key=lambda cell: cell[1].end)
    changed: list[ResultValue] = []
    gaps = 0
    undefined = 0
    for position, (value, period) in enumerate(ordered):
        if position < lag:
            continue
        earlier, earlier_period = ordered[position - lag]
        apart = _steps_apart(earlier_period, period)
        if apart is not None and apart != lag:
            gaps += 1
            continue
        if kind == "percent":
            if earlier.value <= 0:
                undefined += 1
                continue
            amount = (value.value / earlier.value - 1) * 100
        else:
            amount = value.value - earlier.value
        changed.append(
            value.model_copy(
                update={
                    "label": label,
                    "value": amount,
                    "unit": unit,
                    "scale": scale,
                    "measure": measure,
                }
            )
        )
    if not changed:
        raise TableShapeRefused(f"{column_label} has no period with a usable predecessor")
    top = max(item.value for item in changed)
    bottom = min(item.value for item in changed)
    rising = tuple(
        item.period.end for item in changed if item.period is not None and item.value == top > 0
    )
    falling = tuple(
        item.period.end for item in changed if item.period is not None and item.value == bottom < 0
    )
    transformation = TransformationRecord(
        operation="change",
        parameters={
            "formula": CHANGE_FORMULAS[kind],
            "column": column_label,
            "kind": kind,
            "lag": lag,
            "periods_without_predecessor": lag + gaps,
            "periods_with_nonpositive_predecessor": undefined,
            "fill": "none",
        },
        input_refs=[source.result_id, column_label],
        output_ref=label,
    )
    return ChangedColumn(
        tuple(changed),
        transformation,
        label,
        rising,
        falling,
    )


def combine_columns(
    source: AnalyticalResult,
    *,
    columns: Sequence[str],
    label: str | None = None,
) -> CombinedColumn:
    """Add the cell-by-cell sum of several columns as one column; every cell is kept.

    Live 2026-09-22: a reader asked for TP deposits "up to three months" and "over three
    months". Each group is the sum of several of the bulletin's maturity columns, and no
    operation added columns together, so a table already on screen could not answer it.

    The summed columns must share unit, scale and measure. A sum of different measures is
    not a quantity - thousand TRY added to million TRY, or a balance added to a rate, is a
    number with no meaning - so it is refused rather than reported, and a rate or an index
    is refused even when both columns are one, as `StockFlow` states. A period that any of
    the columns lacks stays empty and is counted: a group total missing one of its parts
    is not that group's total, so nothing is bridged or read as zero.
    """
    if source.status is not ResultStatus.COMPUTED:
        raise TableShapeRefused("The source table is not computed")
    selected = tuple(columns)
    if len(selected) < 2:
        raise TableShapeRefused("Combining needs at least two column labels")
    if len(set(selected)) != len(selected):
        raise TableShapeRefused(
            "Combining needs distinct column labels; a column is not summed twice"
        )
    held: dict[str, dict[PeriodKey, ResultValue]] = {}
    semantics: set[tuple[str | None, Scale, StockFlow]] = set()
    frequencies: set[Frequency] = set()
    for name in selected:
        column = [value for value in source.values if value.label == name]
        if not column:
            raise TableShapeRefused(f"No values are labelled {name!r}")
        cells: dict[PeriodKey, ResultValue] = {}
        for value in column:
            if value.period is None or value.period.frequency is Frequency.UNKNOWN:
                raise TableShapeRefused(f"{name} is not a period column")
            key = _key(value)
            if key in cells:
                raise TableShapeRefused(f"{name} has duplicate periods")
            cells[key] = value
            semantics.add((value.unit, value.scale, value.measure))
            frequencies.add(value.period.frequency)
        held[name] = cells
    if len(semantics) != 1:
        raise TableShapeRefused(
            "The columns to combine do not share one unit, scale and measure; their sum "
            "would not be a quantity"
        )
    if len(frequencies) != 1:
        raise TableShapeRefused("The columns to combine mix period frequencies")
    measure = next(iter(semantics))[2]
    # `StockFlow` states it: a rate and an index are neither stock nor flow, and adding
    # two of them produces a number that means nothing. Only their parts' totals add up.
    if measure in (StockFlow.RATE, StockFlow.INDEX):
        raise TableShapeRefused(
            f"A {measure.value} column is not summable; its total means nothing"
        )
    group = label if label is not None else COMBINE_SEPARATOR.join(selected)
    if any(value.label == group for value in source.values):
        raise TableShapeRefused(f"The source table already holds a column labelled {group!r}")
    combined: list[ResultValue] = []
    empty: list[date] = []
    # Every period any named column reaches, so a period only some of them have is
    # reported as left out rather than passing unseen.
    universe = {key for known in held.values() for key in known}
    ordered = sorted(universe, key=lambda item: (item[1], item[0], item[2].value, item[3] or ""))
    for key in ordered:
        parts = [
            cell
            for cell in (held[name].get(key) for name in selected)
            if cell is not None and isfinite(cell.value)
        ]
        if len(parts) != len(selected):
            empty.append(key[1])
            continue
        # Added in the order the reader named, so the total is reproducible by hand.
        total = sum(part.value for part in parts)
        combined.append(parts[0].model_copy(update={"label": group, "value": total}))
    if not combined:
        raise TableShapeRefused("No period has a value in every column to combine")
    transformation = TransformationRecord(
        operation="combine",
        parameters={
            "formula": COMBINE_FORMULA,
            "columns": list(selected),
            "frequency": next(iter(frequencies)).value,
            "period_rows": len(combined),
            "periods_missing_a_column": len(empty),
            "fill": "none",
        },
        input_refs=[source.result_id, *selected],
        output_ref=group,
    )
    return CombinedColumn(tuple(combined), transformation, group, tuple(empty))


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
