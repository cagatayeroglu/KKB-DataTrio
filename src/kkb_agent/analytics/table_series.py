"""An exact monthly left join onto a published table (M5-20, M7-14).

The source owns the row set. No calendar reduction, filling, conversion or
relationship calculation is hidden inside a column addition. A registered
series and a column read from a fetched document join the same way.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite

from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
    TransformationRecord,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, period_bounds

METHOD = "add-monthly-series-v1"
DOCUMENT_METHOD = "add-document-column-v1"


class SeriesAdditionRefused(ValueError):
    """The series cannot be added without changing or misrepresenting the table."""


@dataclass(frozen=True, slots=True)
class AddedSeries:
    values: tuple[ResultValue, ...]
    missing_periods: tuple[date, ...]
    transformation: TransformationRecord


def _monthly(start: date, end: date) -> bool:
    try:
        return (start, end) == period_bounds(Frequency.MONTHLY, end)
    except SemanticsError:
        return False


def table_months(source: AnalyticalResult, new_label: str) -> dict[date, Period]:
    """The published table's monthly rows by period end; refuses anything else.

    A new column label must not already exist. Summary metrics and single-period
    prose values do not define rows.
    """
    if source.status is not ResultStatus.COMPUTED or source.unresolved_semantics:
        raise SeriesAdditionRefused("The source table is not computed with resolved semantics")
    periods: dict[date, Period] = {}
    columns: dict[str, list[Period]] = {}
    cells: set[tuple[str, date, date]] = set()
    for value in source.values:
        if value.label == new_label:
            raise SeriesAdditionRefused("That series is already a column in the source table")
        if value.period is None or value.unit == DIMENSIONLESS:
            continue  # Summary metrics do not define rows.
        period = value.period
        cell = (value.label, period.start, period.end)
        if cell in cells:
            raise SeriesAdditionRefused("The source table has duplicate column-period values")
        cells.add(cell)
        columns.setdefault(value.label, []).append(period)
    # Match the existing period renderer: a single-period metric is prose, not
    # a table column. It must not create a new row when another series is added.
    for column in columns.values():
        if len(column) < 2:
            continue
        for period in column:
            if period.frequency is not Frequency.MONTHLY or not _monthly(period.start, period.end):
                raise SeriesAdditionRefused("The source table must use exact monthly periods")
            periods[period.end] = period
    if len(periods) < 2:
        raise SeriesAdditionRefused(
            "The source must contain a monthly table with at least two rows"
        )
    return periods


def add_monthly_series(
    source: AnalyticalResult,
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
) -> AddedSeries:
    """Return the new column; the caller preserves the original values verbatim."""
    if semantics.unresolved:
        raise SeriesAdditionRefused("The selected series has unresolved semantics")
    if semantics.frequency is not Frequency.MONTHLY:
        raise SeriesAdditionRefused("Only monthly series can be added; align other calendars first")
    if semantics.cumulative is not CumulativeKind.NONE:
        raise SeriesAdditionRefused(
            "Cumulative series need an explicit accumulation-aware operation"
        )
    periods = table_months(source, series_id)

    # Check every supplied observation, including dates outside the displayed
    # window. An invalid or duplicated vintage must not disappear in the join.
    levels: dict[date, float | None] = {}
    for item in observations:
        if not _monthly(item.period_start, item.period_end):
            raise SeriesAdditionRefused("The selected series has an invalid monthly period")
        if item.period_end in levels:
            raise SeriesAdditionRefused("The selected series has duplicate periods")
        if item.value is not None and not isfinite(item.value):
            raise SeriesAdditionRefused("The selected series has a non-finite value")
        levels[item.period_end] = item.value
    added: list[ResultValue] = []
    missing: list[date] = []
    for end, period in sorted(periods.items()):
        level = levels.get(end)
        if level is None:
            missing.append(end)
            continue
        added.append(
            ResultValue(
                label=series_id,
                value=level,
                unit=semantics.unit,
                scale=semantics.scale,
                measure=semantics.observation,
                period=period,
            )
        )
    if len(added) < 2:
        # The existing period renderer needs two observations to show a column.
        raise SeriesAdditionRefused("Fewer than two matching observations; no column can be shown")
    transformation = TransformationRecord(
        operation="add_series",
        parameters={
            "join": "left_exact_monthly_period",
            "series_id": series_id,
            "unit": semantics.unit,
            "scale": semantics.scale.value,
            "measure": semantics.observation.value,
            "base_year": semantics.base_year,
            "source_rows": len(periods),
            "matched_rows": len(added),
            "missing_periods": [end.isoformat() for end in missing],
            "outside_table_periods": len(set(levels) - set(periods)),
            "fill": "none",
        },
        input_refs=[source.result_id, series_id],
        output_ref=series_id,
    )
    return AddedSeries(tuple(added), tuple(missing), transformation)


def add_document_column(
    source: AnalyticalResult,
    levels: Mapping[date, float | None],
    *,
    label: str,
    unit: str,
    scale: Scale,
    document_rows: int,
    content_hash: str,
    measure: StockFlow = StockFlow.UNKNOWN,
) -> AddedSeries:
    """Join one fetched document column, keyed by month end, onto the table's months.

    `levels` comes from a strict reader: one explicit month per row, a number
    read without guessing, and a unit the column header stated. `measure` is
    unknown unless the reader's header-unit rule (DEC-145/146) named an index or rate.
    """
    if not label.strip() or not unit or scale is Scale.UNKNOWN:
        raise SeriesAdditionRefused("A document column needs a label and a stated unit and scale")
    if measure not in (StockFlow.UNKNOWN, StockFlow.INDEX, StockFlow.RATE):
        raise SeriesAdditionRefused("A document column states no stock or flow meaning")
    periods = table_months(source, label)
    for end, level in levels.items():
        if not _monthly(date(end.year, end.month, 1), end):
            raise SeriesAdditionRefused("The document column has an invalid monthly period")
        if level is not None and not isfinite(level):
            raise SeriesAdditionRefused("The document column has a non-finite value")
    added: list[ResultValue] = []
    missing: list[date] = []
    for end, period in sorted(periods.items()):
        level = levels.get(end)
        if level is None:
            missing.append(end)
            continue
        added.append(
            ResultValue(
                label=label,
                value=level,
                unit=unit,
                scale=scale,
                measure=measure,
                period=period,
            )
        )
    if len(added) < 2:
        raise SeriesAdditionRefused("Fewer than two matching document rows; no column can be shown")
    transformation = TransformationRecord(
        operation="add_document_column",
        parameters={
            "join": "left_exact_monthly_period",
            "period_rule": "explicit month label, first or last day of a month",
            "value_rule": "strict cell number; empty cells stay missing",
            "unit": unit,
            "unit_source": "column header",
            "scale": scale.value,
            "measure": measure.value,
            "measure_source": "column header unit" if measure is not StockFlow.UNKNOWN else None,
            "document_rows": document_rows,
            "source_rows": len(periods),
            "matched_rows": len(added),
            "missing_periods": [end.isoformat() for end in missing],
            "outside_table_periods": len(set(levels) - set(periods)),
            "content_hash": content_hash,
            "fill": "none",
        },
        input_refs=[source.result_id, content_hash],
        output_ref=label,
    )
    return AddedSeries(tuple(added), tuple(missing), transformation)
