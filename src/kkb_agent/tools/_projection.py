"""Turn a validated lakehouse query into a typed result (M6-21).

The `lakehouse` tool returns rows. Rows are not a result: nothing downstream
can tell whether `801438` is million TRY or thousand, which period it covers,
or how many observations stand behind it. The verifier's consequence is
visible today — it binds a written number to any stored value of similar
magnitude, because there is nothing better to bind to.

This module supplies what is missing by reading semantics the lakehouse already
stores rather than inferring any. `silver_series` records unit, scale,
frequency, anchor and observation kind as the exact enum values written by the
store, so recognising those columns is a lookup, not a guess. That is the whole
design rule here: **a column we did not select is a semantic we do not know**,
and an unknown semantic is declared, never filled in.

Two refusals matter more than the projection itself.

A query that reads no lakehouse table produces no measurement, whatever it
returns. `SELECT 42 AS konut_kredisi` is valid SQL and passes every security
gate, because refusing it was never the gates' job — they stop SQL from
reaching the filesystem, not from inventing a figure. Here it becomes an
ABSTAINED result with no values, so a fabricated number cannot acquire the
authority of a computed one.

A value column the query did not join to its semantics yields a number with
`unit=None`, which forces the result to declare unresolved semantics. That is
deliberate pressure: a planner that wants a typed number has to join
`silver_series` and say what the number means.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    StockFlow,
    WeeklyAnchor,
)

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.tools.lakehouse import QueryResult

#: Lakehouse column names whose meaning is fixed by the schema. Nothing else is
#: interpreted: a column called `deger` or `tutar` is data, not a declaration,
#: and treating it as one would be exactly the invented semantics this project
#: refuses. Extend this map only when a schema column is added.
VALUE_COLUMN: Final = "value"
PERIOD_START_COLUMN: Final = "period_start"
PERIOD_END_COLUMN: Final = "period_end"
UNIT_COLUMN: Final = "unit"
SCALE_COLUMN: Final = "scale"
FREQUENCY_COLUMN: Final = "frequency"
ANCHOR_COLUMN: Final = "anchor"
OBSERVATION_COLUMN: Final = "observation"

#: First match wins, so a query joining silver to gold labels rows by series.
LABEL_COLUMNS: Final = ("series_id", "column_name", "title", "table_id")

#: What a row is called when the query selected no recognisable label column.
DEFAULT_LABEL: Final = "value"


def _index_of(columns: Sequence[str], name: str) -> int | None:
    for position, column in enumerate(columns):
        if column == name:
            return position
    return None


def _text(cell: object) -> str | None:
    """A non-empty string, or None. Enum columns are stored as their values."""
    if isinstance(cell, str) and cell.strip():
        return cell
    return None


def _is_measurement(cell: object) -> bool:
    """Numbers only. `bool` is an `int` in Python and is not a measurement."""
    if isinstance(cell, bool) or not isinstance(cell, int | float):
        return False
    return math.isfinite(cell)


def _period_of(row: Sequence[Any], positions: Mapping[str, int], notes: set[str]) -> Period | None:
    """Build a period from the row, degrading loudly rather than guessing.

    A weekly period must name its anchor and end on that weekday. When the
    query did not select the anchor, or the stored anchor disagrees with the
    date, the frequency drops to UNKNOWN and the reason is recorded. Asserting
    a weekly period we cannot substantiate would be worse than admitting the
    calendar is unresolved.
    """
    start_at = positions.get(PERIOD_START_COLUMN)
    end_at = positions.get(PERIOD_END_COLUMN)
    if start_at is None or end_at is None:
        notes.add("period is unresolved: the query selected no period_start/period_end")
        return None
    start, end = row[start_at], row[end_at]
    if not hasattr(start, "year") or not hasattr(end, "year"):
        notes.add("period is unresolved: period_start/period_end are not dates")
        return None

    frequency = Frequency.UNKNOWN
    declared = _text(row[positions[FREQUENCY_COLUMN]]) if FREQUENCY_COLUMN in positions else None
    if declared is not None:
        try:
            frequency = Frequency(declared)
        except ValueError:
            notes.add(f"frequency {declared!r} is not a recognised value")

    anchor: WeeklyAnchor | None = None
    if frequency is Frequency.WEEKLY:
        stored = _text(row[positions[ANCHOR_COLUMN]]) if ANCHOR_COLUMN in positions else None
        try:
            anchor = WeeklyAnchor(stored) if stored is not None else None
        except ValueError:
            notes.add(f"weekly anchor {stored!r} is not a recognised weekday")
        if anchor is None:
            notes.add("weekly anchor is unresolved: the query selected no anchor column")
            frequency = Frequency.UNKNOWN
        elif end.weekday() != anchor.weekday:
            notes.add(
                f"stored anchor {anchor.value} disagrees with a period ending {end.isoformat()}"
            )
            anchor, frequency = None, Frequency.UNKNOWN

    try:
        return Period(start=start, end=end, frequency=frequency, weekly_anchor=anchor)
    except ValueError as error:
        notes.add(f"period is unresolved: {error.__class__.__name__} building it")
        del error
        return None


def _semantics_of(
    row: Sequence[Any], positions: Mapping[str, int], notes: set[str]
) -> tuple[str | None, Scale, StockFlow]:
    """Read declared unit, scale and observation kind. Absent stays absent."""
    unit = _text(row[positions[UNIT_COLUMN]]) if UNIT_COLUMN in positions else None
    if unit is None:
        notes.add("unit is unresolved: join silver_series and select `unit` to state it")

    scale = Scale.UNKNOWN
    declared_scale = _text(row[positions[SCALE_COLUMN]]) if SCALE_COLUMN in positions else None
    if declared_scale is None:
        notes.add("scale is unresolved: BDDK publishes million TRY and FinTürk thousand")
    else:
        try:
            scale = Scale(declared_scale)
        except ValueError:
            notes.add(f"scale {declared_scale!r} is not a recognised value")

    measure = StockFlow.UNKNOWN
    declared_measure = (
        _text(row[positions[OBSERVATION_COLUMN]]) if OBSERVATION_COLUMN in positions else None
    )
    if declared_measure is not None:
        try:
            measure = StockFlow(declared_measure)
        except ValueError:
            notes.add(f"observation kind {declared_measure!r} is not a recognised value")
    return unit, scale, measure


def _label_of(row: Sequence[Any], positions: Mapping[str, int]) -> str:
    for column in LABEL_COLUMNS:
        at = positions.get(column)
        if at is not None:
            label = _text(row[at])
            if label is not None:
                return label
    return DEFAULT_LABEL


def _abstain(result_id: str, reason: str, parameters: dict[str, Any]) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=result_id,
        kind=ResultKind.SERIES,
        status=ResultStatus.ABSTAINED,
        tool="lakehouse",
        parameters=parameters,
        reason=reason,
    )


def project(
    query: QueryResult,
    *,
    result_id: str,
    tables: Sequence[str],
    lineage_node: str | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> AnalyticalResult:
    """Describe what a query actually established, and nothing more.

    `tables` are the whitelisted lakehouse tables the statement read, as the
    tool already resolves them for its own provenance record. They become the
    result's input references, which is why a query that reads none cannot
    produce a computed value here.
    """
    shared: dict[str, Any] = dict(parameters or {})
    shared["row_count"] = query.row_count
    shared["truncated"] = query.truncated

    if not tables:
        return _abstain(
            result_id,
            "The query reads no lakehouse table, so its numbers rest on no source",
            shared,
        )

    positions = {
        name: at
        for name in (
            VALUE_COLUMN,
            PERIOD_START_COLUMN,
            PERIOD_END_COLUMN,
            UNIT_COLUMN,
            SCALE_COLUMN,
            FREQUENCY_COLUMN,
            ANCHOR_COLUMN,
            OBSERVATION_COLUMN,
            *LABEL_COLUMNS,
        )
        if (at := _index_of(query.columns, name)) is not None
    }
    if VALUE_COLUMN not in positions:
        return _abstain(
            result_id,
            f"The query selected no {VALUE_COLUMN!r} column; its rows are a listing, "
            "not a measurement",
            shared,
        )
    if not query.rows:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.INSUFFICIENT,
            tool="lakehouse",
            parameters=shared,
            samples=SampleCounts(used=0),
            reason="The query returned no rows",
        )

    values: list[ResultValue] = []
    notes: set[str] = set()
    missing = 0
    excluded = 0
    value_at = positions[VALUE_COLUMN]
    for row in query.rows:
        cell = row[value_at]
        if cell is None:
            # A period a series did not publish is null and stays null; gold
            # never forward-fills, so this is a real gap rather than a zero.
            missing += 1
            continue
        if not _is_measurement(cell):
            excluded += 1
            continue
        unit, scale, measure = _semantics_of(row, positions, notes)
        values.append(
            ResultValue(
                label=_label_of(row, positions),
                value=float(cell),
                unit=unit,
                scale=scale,
                measure=measure,
                period=_period_of(row, positions, notes),
            )
        )

    if not values:
        reason = (
            f"Every row's {VALUE_COLUMN!r} is non-numeric"
            if excluded
            else "Every row's value is null; the series published nothing in this range"
        )
        status = ResultStatus.ABSTAINED if excluded else ResultStatus.INSUFFICIENT
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=status,
            tool="lakehouse",
            parameters=shared,
            samples=SampleCounts(used=0, missing=missing, excluded=excluded),
            reason=reason,
            unresolved_semantics=sorted(notes),
        )

    evidence = ResultEvidence(input_refs=sorted(tables), lineage_node=lineage_node)
    warnings: list[str] = []
    if query.truncated:
        warnings.append(
            f"Only the first {query.row_count} rows were read; this is a partial series"
        )
    if excluded:
        warnings.append(f"{excluded} row(s) carried a non-numeric value and were excluded")

    return AnalyticalResult(
        result_id=result_id,
        kind=ResultKind.LEVEL if len(values) == 1 else ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        method="sql",
        values=values,
        coverage=_coverage_of(values),
        parameters=shared,
        samples=SampleCounts(used=len(values), missing=missing, excluded=excluded),
        evidence=evidence,
        warnings=warnings,
        unresolved_semantics=sorted(notes),
    )


def _coverage_of(values: Sequence[ResultValue]) -> Period | None:
    """The span the rows cover, stated only when every row carried a period.

    A span computed from some of the rows would understate what is missing,
    and a coverage claim is exactly the kind of thing a reader trusts without
    checking.
    """
    periods = [value.period for value in values]
    if not periods or any(period is None for period in periods):
        return None
    known = [period for period in periods if period is not None]
    frequencies = {period.frequency for period in known}
    anchors = {period.weekly_anchor for period in known}
    single = frequencies.pop() if len(frequencies) == 1 else Frequency.UNKNOWN
    anchor = anchors.pop() if len(anchors) == 1 and single is Frequency.WEEKLY else None
    start = min(period.start for period in known)
    end = max(period.end for period in known)
    try:
        return Period(start=start, end=end, frequency=single, weekly_anchor=anchor)
    except ValueError:
        # A mixed-frequency join has no single calendar; say nothing instead.
        return Period(start=start, end=end)
