"""M10-04 slice 2: a monthly analytical table built from one document table.

`web_url` table mode turns a period column and up to six value columns of a
fetched or uploaded document into a result that is published like any other
table, so later turns can select it. The rules are the strict document-column
rules (M7-14, DEC-145/146), with one decision of their own (Eray, 2026-09-17):

- **Table-level problems refuse the table.** The period column must be found
  once in exactly one table that also holds a requested value column; every
  non-empty period cell must be an explicit month, once per month.
- **Column-level problems leave that column out.** A value column that is not
  found once, states no recognised unit, holds a number with more than one
  reading, names a prepared series or has fewer than two values is skipped with
  a fixed code in a visible warning; the other columns still publish. No usable
  column refuses the table.

Labels are the names the user gave (from the question); matched headers, sheet
names and cell text stay in the lineage snapshot and never reach the answer.
"""

from __future__ import annotations

import calendar
import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from pydantic import JsonValue

from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
    StockFlow,
    TransformationRecord,
)
from kkb_agent.lakehouse.result_evidence import canonical
from kkb_agent.tools._document_column import (
    ColumnRefused,
    _empty,
    document_measure,
    measure_limitation,
    month_end,
)
from kkb_agent.tools._document_value import (
    Grid,
    ValueNotSelected,
    _text,
    header_matches,
    header_semantics,
    read_number,
)

SNAPSHOT_KIND = "document_table_v1"
METHOD = "document-table-v1"
MAX_VALUE_COLUMNS = 6


@dataclass(frozen=True)
class TableColumn:
    label: str
    header: str
    column_index: int
    unit: str
    scale: Scale
    measure: StockFlow
    #: (month end, value or None for an empty cell, digest of the cell text)
    cells: tuple[tuple[date, float | None, str], ...]


@dataclass(frozen=True)
class DocumentTable:
    location: dict[str, str | int]
    period_header: str
    months: tuple[date, ...]
    columns: tuple[TableColumn, ...]
    #: (label as the user named it, fixed refusal code)
    skipped: tuple[tuple[str, str], ...]


def read_table(
    tables: list[Grid],
    period_column: str,
    value_columns: Sequence[str],
    *,
    is_series: Callable[[str], bool] = lambda label: False,
) -> DocumentTable:
    """The one table holding the period column, read as explicit months per column."""
    found: list[tuple[Grid, int]] = []
    for grid in tables:
        periods = [
            i for i, header in enumerate(grid.headers) if header_matches(header, period_column)
        ]
        if len(periods) > 1:
            raise ColumnRefused("AMBIGUOUS_COLUMN")
        if periods and any(
            header_matches(header, wanted) for header in grid.headers for wanted in value_columns
        ):
            found.append((grid, periods[0]))
    if not found:
        raise ColumnRefused("COLUMN_NOT_FOUND")
    if len(found) > 1:
        raise ColumnRefused("AMBIGUOUS_COLUMN")
    grid, period_index = found[0]

    skipped: list[tuple[str, str]] = []
    targets: list[tuple[str, int]] = []
    for label in value_columns:
        matches = [i for i, header in enumerate(grid.headers) if header_matches(header, label)]
        if len(matches) != 1 or matches[0] == period_index:
            skipped.append((label, "AMBIGUOUS_COLUMN" if matches else "COLUMN_NOT_FOUND"))
        elif any(index == matches[0] for _, index in targets):
            skipped.append((label, "DUPLICATE_COLUMN"))
        elif is_series(label):
            skipped.append((label, "LABEL_IS_A_SERIES"))
        else:
            targets.append((label, matches[0]))

    rows: list[tuple[date, tuple[object, ...]]] = []
    seen: set[date] = set()
    for cells in grid.rows:
        raw_period = cells[period_index] if period_index < len(cells) else None
        requested = [cells[index] if index < len(cells) else None for _, index in targets]
        if _empty(raw_period):
            if all(_empty(value) for value in requested):
                continue  # A blank spacer row carries nothing requested.
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        end = month_end(raw_period)
        if end is None:
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if end in seen:
            raise ColumnRefused("DUPLICATE_PERIOD")
        seen.add(end)
        rows.append((end, cells))
    if not rows:
        raise ColumnRefused("COLUMN_EMPTY")
    rows.sort(key=lambda row: row[0])

    columns: list[TableColumn] = []
    for label, index in targets:
        header = _text(grid.headers[index])
        unit, scale = header_semantics(header)
        if unit is None or scale is Scale.UNKNOWN:
            skipped.append((label, "UNIT_NOT_STATED"))
            continue
        read: list[tuple[date, float | None, str]] = []
        try:
            for end, cells in rows:
                raw = cells[index] if index < len(cells) else None
                value = None if _empty(raw) else read_number(raw)
                read.append((end, value, hashlib.sha256(_text(raw).encode()).hexdigest()))
        except ValueNotSelected as error:
            skipped.append((label, error.code))
            continue
        if sum(1 for _, value, _ in read if value is not None) < 2:
            skipped.append((label, "TOO_FEW_VALUES"))
            continue
        columns.append(
            TableColumn(
                label, header, index + 1, unit, scale, document_measure(unit, scale), tuple(read)
            )
        )
    if not columns:
        raise ColumnRefused("NO_USABLE_COLUMN")
    return DocumentTable(
        location=dict(grid.location),
        period_header=_text(grid.headers[period_index]),
        months=tuple(end for end, _ in rows),
        columns=tuple(columns),
        skipped=tuple(skipped),
    )


def table_snapshot(
    table: DocumentTable,
    source: SourceRef,
    media_type: str,
    *,
    csv: dict[str, str] | None = None,
) -> str:
    """The exact cells the execution read, bound to the document's content hash.

    `csv` is how a CSV was split (`csv_parsing`), recorded so a detected
    separator is as reproducible as a declared one.
    """
    return canonical(
        {
            "kind": SNAPSHOT_KIND,
            "source_id": source.source_id,
            "source_type": source.source_type,
            "locator": source.locator,
            "content_hash": source.content_hash,
            "media_type": media_type,
            "retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
            "location": table.location,
            "period_header": table.period_header,
            "months": list(table.months),
            "columns": [
                {
                    "label": column.label,
                    "header": column.header,
                    "column_index": column.column_index,
                    "unit": column.unit,
                    "scale": column.scale.value,
                    "measure": column.measure.value,
                    "cells": [[end, value, digest] for end, value, digest in column.cells],
                }
                for column in table.columns
            ],
            "skipped": [[label, code] for label, code in table.skipped],
            **({"csv": csv} if csv is not None else {}),
        }
    )


def table_result(
    table: DocumentTable,
    source: SourceRef,
    *,
    source_node: str | None,
    csv: dict[str, str] | None = None,
) -> AnalyticalResult:
    """The published table: every read value, periods explicit, gaps never filled."""
    values: list[ResultValue] = []
    missing: dict[str, int] = {}
    for column in table.columns:
        for end, value, _ in column.cells:
            if value is None:
                missing[column.label] = missing.get(column.label, 0) + 1
                continue
            values.append(
                ResultValue(
                    label=column.label,
                    value=value,
                    unit=column.unit,
                    scale=column.scale,
                    measure=column.measure,
                    period=_month(end),
                )
            )
    warnings = [
        f"Column {label!r} was left out of the table ({code})" for label, code in table.skipped
    ]
    warnings.extend(
        f"Column {label!r} has {count} empty month(s); those cells are empty, never filled"
        for label, count in missing.items()
    )
    location = canonical(table.location)
    return AnalyticalResult(
        result_id=f"web_url:table:{source.source_id}:{location}",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="web_url",
        method=METHOD,
        values=values,
        coverage=Period(
            start=date(table.months[0].year, table.months[0].month, 1),
            end=table.months[-1],
            frequency=Frequency.MONTHLY,
        ),
        parameters={
            "columns": [column.label for column in table.columns],
            "skipped_columns": [{"label": label, "code": code} for label, code in table.skipped],
            "months": len(table.months),
        },
        evidence=ResultEvidence(
            input_refs=[source_node or source.source_id],
            transformations=[
                TransformationRecord(
                    operation="document_table",
                    parameters={
                        "period_rule": "explicit month label, first or last day of a month",
                        "value_rule": "strict cell number; empty cells stay missing",
                        "unit_source": "column header",
                        "columns": [
                            {
                                "label": column.label,
                                "unit": column.unit,
                                "scale": column.scale.value,
                                "measure": column.measure.value,
                                "values": sum(
                                    1 for _, value, _ in column.cells if value is not None
                                ),
                            }
                            for column in table.columns
                        ],
                        "skipped": [[label, code] for label, code in table.skipped],
                        "months": len(table.months),
                        "content_hash": source.content_hash or "",
                        "fill": "none",
                        **({"csv": dict[str, JsonValue](csv)} if csv is not None else {}),
                    },
                    input_refs=[source.source_id],
                    output_ref=f"web_url:table:{source.source_id}",
                )
            ],
            sources=[source],
        ),
        warnings=warnings,
        limitations=[
            "Read from one document table as published on explicit months only; no resampling, "
            "filling, currency conversion, inflation adjustment or rebasing was applied",
            *(f"{column.label}: {measure_limitation(column.measure)}" for column in table.columns),
        ],
    )


def _month(end: date) -> Period:
    return Period(
        start=date(end.year, end.month, 1),
        end=date(end.year, end.month, calendar.monthrange(end.year, end.month)[1]),
        frequency=Frequency.MONTHLY,
    )
