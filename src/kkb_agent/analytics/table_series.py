"""An exact monthly left join onto a published table (M5-20).

The source owns the row set. No calendar reduction, filling, conversion or
relationship calculation is hidden inside a column addition.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    TransformationRecord,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, period_bounds

METHOD = "add-monthly-series-v1"


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


def add_monthly_series(
    source: AnalyticalResult,
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    *,
    series_id: str,
) -> AddedSeries:
    """Return the new column; the caller preserves the original values verbatim."""
    if source.status is not ResultStatus.COMPUTED or source.unresolved_semantics:
        raise SeriesAdditionRefused("The source table is not computed with resolved semantics")
    if semantics.unresolved:
        raise SeriesAdditionRefused("The selected series has unresolved semantics")
    if semantics.frequency is not Frequency.MONTHLY:
        raise SeriesAdditionRefused("Only monthly series can be added; align other calendars first")
    if semantics.cumulative is not CumulativeKind.NONE:
        raise SeriesAdditionRefused(
            "Cumulative series need an explicit accumulation-aware operation"
        )
    periods: dict[date, Period] = {}
    columns: dict[str, list[Period]] = {}
    cells: set[tuple[str, date, date]] = set()
    for value in source.values:
        if value.label == series_id:
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
