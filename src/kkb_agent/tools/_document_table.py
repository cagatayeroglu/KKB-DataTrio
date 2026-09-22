"""M10-04 slice 2: an analytical table built from one document table.

`web_url` table mode turns a period column and up to twelve value columns of a
fetched or uploaded document into a result that is published like any other
table, so later turns can select it. The rules are the strict document-column
rules (M7-14, DEC-145/146), with one decision of their own (Eray, 2026-09-17):

- **Table-level problems refuse the table.** The period column must be found
  once in exactly one table that also holds a requested value column; every
  non-empty period cell must name the same kind of period, once each -- either an
  explicit month, or a single calendar day when the column dates days. Under
  DEC-148 total rows and months ending after retrieval are skipped with a
  warning instead, and a month name without a year takes the year context.
- **Column-level problems leave that column out.** A value column that is not
  found once, holds a number with more than one reading, names a prepared
  series or has fewer than two values is skipped with a fixed code in a visible
  warning; the other columns still publish. No usable column refuses the table.
- **A missing unit is declared, not a refusal.** A header without a recognised
  unit keeps its values with an unknown unit and scale, recorded in
  `unresolved_semantics`; the answer gate never quotes such a number and each
  operation decides whether it needs the unit. A unit the user wrote in the
  question (`declared_units`) fills it, recorded as coming from the question. A
  header unit always wins; a different declared unit refuses that column.

Labels are the names the user gave (from the question); matched headers, sheet
names and cell text stay in the lineage snapshot and never reach the answer.
"""

from __future__ import annotations

import calendar
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from pydantic import JsonValue

from kkb_agent.catalog.normalization import normalize_search_text
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
from kkb_agent.ingest.bist_index_semantics import ReviewedMetric
from kkb_agent.lakehouse.result_evidence import canonical
from kkb_agent.tools._document_column import (
    ColumnRefused,
    RowRules,
    _empty,
    calendar_day,
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
    is_total_label,
)

SNAPSHOT_KIND = "document_table_v1"
METHOD = "document-table-v1"
#: The published-result ceiling (2048 cells) is the real bound; twelve columns keep fourteen
#: years of months under it. Six left out part of an official table (the Borsa Istanbul gold
#: transactions PDF has ten value columns; live J1, 2026-09-19).
MAX_VALUE_COLUMNS = 12


#: Where a column's unit and scale came from.
UNIT_FROM_HEADER = "column header"
UNIT_FROM_QUESTION = "question"

#: What one row of the table is, per calendar: the word a warning uses, and the recorded
#: rule the rows were read under.
_ROW_WORD = {Frequency.MONTHLY: "month", Frequency.DAILY: "day"}
_PERIOD_RULE = {
    Frequency.MONTHLY: "explicit month label, first or last day of a month",
    Frequency.DAILY: "one calendar day per row, as the document dates it",
}


@dataclass(frozen=True)
class TableColumn:
    label: str
    header: str
    column_index: int
    #: None when neither the header nor the user stated it (scale then UNKNOWN).
    unit: str | None
    scale: Scale
    measure: StockFlow
    #: (period end, value or None for an empty cell, digest of the cell text)
    cells: tuple[tuple[date, float | None, str], ...]
    unit_source: str | None = UNIT_FROM_HEADER


@dataclass(frozen=True)
class DocumentTable:
    location: dict[str, str | int]
    period_header: str
    #: One period end per row, in order; days when `calendar` is DAILY.
    months: tuple[date, ...]
    columns: tuple[TableColumn, ...]
    #: (label as the user named it, fixed refusal code)
    skipped: tuple[tuple[str, str], ...]
    rules: RowRules | None = None
    #: Daily rows reduced to months: rule, days per month, incomplete months skipped.
    aggregation: dict[str, JsonValue] | None = None
    #: The calendar the rows are on: months, or the days the document dates them to.
    calendar: Frequency = Frequency.MONTHLY


def read_table(
    tables: list[Grid],
    period_column: str,
    value_columns: Sequence[str],
    *,
    is_series: Callable[[str], bool] = lambda label: False,
    year: int | None = None,
    as_of: date | None = None,
    declared_units: Mapping[str, tuple[str, Scale]] | None = None,
) -> DocumentTable:
    """The one table holding the period column, read as explicit months per column.

    `year` is a year from the user's question, `as_of` the document's retrieval date,
    `declared_units` the unit and scale the user wrote for a column label (the
    caller checks that the question contains them).

    A period column that dates single days publishes a daily table (`_daily`). Nothing
    is reduced, so nothing needs the user's word for how to reduce it; asking for days
    as months is `read_daily_table`.
    """
    declared = dict(declared_units or {})
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

    rules = RowRules.for_grid(grid, year=year, as_of=as_of)
    daily = _daily(grid, period_index)
    unchecked = [target for target in targets if not rules.column_checked(target[1])]
    skipped.extend((label, "OCR_NOT_VALIDATED") for label, _ in unchecked)
    targets = [target for target in targets if target not in unchecked]
    rows: list[tuple[date, tuple[object, ...]]] = []
    seen: set[date] = set()
    for cells in grid.rows:
        raw_period = cells[period_index] if period_index < len(cells) else None
        requested = [cells[index] if index < len(cells) else None for _, index in targets]
        if _empty(raw_period):
            if all(_empty(value) for value in requested):
                continue  # A blank spacer row carries nothing requested.
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        end = rules.day(raw_period) if daily else rules.month(raw_period)
        if end is None:
            continue
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
        source: str | None = UNIT_FROM_HEADER
        if unit is None or scale is Scale.UNKNOWN:
            unit, scale, source = None, Scale.UNKNOWN, None
            if label in declared:
                (unit, scale), source = declared[label], UNIT_FROM_QUESTION
        elif label in declared and declared[label] != (unit, scale):
            skipped.append((label, "UNIT_CONFLICT"))
            continue
        read: list[tuple[date, float | None, str]] = []
        try:
            for end, cells in rows:
                raw = cells[index] if index < len(cells) else None
                value = None if _empty(raw) else rules.number(raw)
                read.append((end, value, hashlib.sha256(_text(raw).encode()).hexdigest()))
        except ValueNotSelected as error:
            skipped.append((label, error.code))
            continue
        if sum(1 for _, value, _ in read if value is not None) < 2:
            skipped.append((label, "TOO_FEW_VALUES"))
            continue
        columns.append(
            TableColumn(
                label,
                header,
                index + 1,
                unit,
                scale,
                document_measure(unit, scale),
                tuple(read),
                source,
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
        rules=rules,
        calendar=Frequency.DAILY if daily else Frequency.MONTHLY,
    )


def _daily(grid: Grid, period_index: int) -> bool:
    """Whether this period column dates single days rather than months.

    A monthly table is often written on the edge day of each month ("01.01.2026"), and that
    reading is unchanged: rows become days only when at least one of them dates a day that
    is no month at all. Until this existed, a daily source table could be read only by
    asking for it as months, and only when the question itself carried the word for the
    reduction -- so "the daily closes on this page" refused every time, with
    PERIOD_NOT_RECOGNISED (Eray's audit, 2026-09-22).
    """
    dated = False
    for cells in grid.rows:
        raw = cells[period_index] if period_index < len(cells) else None
        if _empty(raw) or is_total_label(raw):
            continue
        if calendar_day(raw) is None:
            return False
        dated = dated or month_end(raw) is None
    return dated


#: How daily observations become one monthly value, and the words that request each rule.
DAILY_RULES: dict[str, tuple[str, ...]] = {
    "last": ("ay sonu", "ay sonlari", "donem sonu", "ayin son", "month end", "end of month"),
    "mean": ("ortalama", "ortalamasi", "ortalamalari", "average", "mean"),
    "sum": ("aylik toplam", "toplamini", "toplamlari", "monthly total", "sum"),
}
_DAILY_LIMITATIONS = {
    "last": "Each month holds the last daily observation dated in that month, as the user asked",
    "mean": (
        "Each month is the mean of the daily observations dated in that month, as the user "
        "asked; it is derived, not a published figure"
    ),
    "sum": (
        "Each month is the sum of the daily observations dated in that month, as the user "
        "asked; days missing from the source are not filled"
    ),
}


def daily_rule_in_question(rule: str, question: str) -> bool:
    """Whether the question itself asks for this monthly reduction (never the model's choice)."""
    folded = f" {normalize_search_text(question)} "
    return any(f" {word} " in folded or folded.find(f" {word}") >= 0 for word in DAILY_RULES[rule])


def read_daily_table(
    tables: list[Grid],
    period_column: str,
    value_columns: Sequence[str],
    *,
    rule: str,
    as_of: date | None,
    is_series: Callable[[str], bool] = lambda label: False,
    declared_units: Mapping[str, tuple[str, Scale]] | None = None,
    reviewed_metrics: Mapping[str, ReviewedMetric] | None = None,
) -> DocumentTable:
    """A monthly table from daily rows, reduced by a rule the user asked for.

    Every period cell must be one calendar day, once. A month is kept only when
    it has ended by the retrieval date: a running month's "last" value is not a
    month-end value. The rule, the days behind every month and the months left
    out are recorded; nothing is filled. Source-declared header semantics take
    priority over a reviewed source-specific metric, then a question-declared
    unit; unknown columns remain unknown.
    """
    if rule not in DAILY_RULES:
        raise ColumnRefused("UNSUPPORTED_AGGREGATION")
    declared = dict(declared_units or {})
    reviewed = dict(reviewed_metrics or {})
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
    rules = RowRules.for_grid(grid, year=None, as_of=as_of)
    days: dict[date, tuple[object, ...]] = {}
    for cells in grid.rows:
        raw = cells[period_index] if period_index < len(cells) else None
        if _empty(raw):
            continue
        day = calendar_day(raw)
        if day is None:
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if day in days:
            raise ColumnRefused("DUPLICATE_PERIOD")
        days[day] = cells
    if not days:
        raise ColumnRefused("COLUMN_EMPTY")
    by_month: dict[date, list[date]] = {}
    for day in sorted(days):
        end = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
        by_month.setdefault(end, []).append(day)
    incomplete = [end for end in by_month if as_of is None or end > as_of]
    months = [end for end in sorted(by_month) if end not in incomplete]
    if not months:
        raise ColumnRefused("NO_COMPLETE_MONTH")
    columns: list[TableColumn] = []
    for label, index in targets:
        header = _text(grid.headers[index])
        unit, scale = header_semantics(header)
        source: str | None = UNIT_FROM_HEADER
        metric = reviewed.get(label) if header == label else None
        measure = document_measure(unit, scale)
        if unit is None or scale is Scale.UNKNOWN:
            unit, scale, source = None, Scale.UNKNOWN, None
            if metric is not None:
                unit, scale, measure, source = (
                    metric.unit,
                    metric.scale,
                    metric.measure,
                    metric.source,
                )
            elif label in declared:
                (unit, scale), source = declared[label], UNIT_FROM_QUESTION
                measure = document_measure(unit, scale)
        if label in declared and (unit, scale) != declared[label]:
            skipped.append((label, "UNIT_CONFLICT"))
            continue
        read: list[tuple[date, float | None, str]] = []
        try:
            for end in months:
                observed = [
                    (day, rules.number(days[day][index]))
                    for day in by_month[end]
                    if index < len(days[day]) and not _empty(days[day][index])
                ]
                digest = hashlib.sha256(
                    "|".join(
                        day.isoformat()
                        + "="
                        + (_text(days[day][index]) if index < len(days[day]) else "")
                        for day in by_month[end]
                    ).encode()
                ).hexdigest()
                if not observed:
                    read.append((end, None, digest))
                    continue
                values = [value for _, value in observed]
                level = {
                    "last": values[-1],
                    "mean": sum(values) / len(values),
                    "sum": sum(values),
                }[rule]
                read.append((end, level, digest))
        except ValueNotSelected as error:
            skipped.append((label, error.code))
            continue
        if sum(1 for _, value, _ in read if value is not None) < 2:
            skipped.append((label, "TOO_FEW_VALUES"))
            continue
        columns.append(
            TableColumn(
                # A reviewed source names its own column; "clval" told a reader nothing.
                metric.title if metric is not None and metric.title else label,
                header,
                index + 1,
                unit,
                scale,
                measure,
                tuple(read),
                source,
            )
        )
    if not columns:
        raise ColumnRefused("NO_USABLE_COLUMN")
    return DocumentTable(
        location=dict(grid.location),
        period_header=_text(grid.headers[period_index]),
        months=tuple(months),
        columns=tuple(columns),
        skipped=tuple(skipped),
        rules=rules,
        aggregation={
            "from": "daily",
            "rule": rule,
            "days_per_month": {end.isoformat(): len(by_month[end]) for end in months},
            "incomplete_months_left_out": [end.isoformat() for end in sorted(incomplete)],
        },
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
            **({"calendar": "daily"} if table.calendar is Frequency.DAILY else {}),
            "columns": [
                {
                    "label": column.label,
                    "header": column.header,
                    "column_index": column.column_index,
                    "unit": column.unit,
                    "unit_source": column.unit_source,
                    "scale": column.scale.value,
                    "measure": column.measure.value,
                    "cells": [[end, value, digest] for end, value, digest in column.cells],
                }
                for column in table.columns
            ],
            "skipped": [[label, code] for label, code in table.skipped],
            **({"csv": csv} if csv is not None else {}),
            **(table.rules.evidence() if table.rules is not None else {}),
            **({"aggregation": table.aggregation} if table.aggregation is not None else {}),
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
                    period=_dated(end, table.calendar),
                )
            )
    warnings = [
        f"Column {label!r} was left out of the table ({code})" for label, code in table.skipped
    ]
    row = _ROW_WORD[table.calendar]
    warnings.extend(
        f"Column {label!r} has {count} empty {row}(s); those cells are empty, never filled"
        for label, count in missing.items()
    )
    aggregation = table.aggregation or {}
    left_out = aggregation.get("incomplete_months_left_out")
    if isinstance(left_out, list) and left_out:
        # Named, not counted: the reader could not tell which month was missing, and
        # a later filter can drop this warning once it excludes those months (L2-4).
        named = ", ".join(sorted(str(month)[:7] for month in left_out))
        warnings.append(
            f"{len(left_out)} month(s) not yet ended at retrieval were left out of the "
            f"monthly rows ({named})"
        )
    rules = table.rules
    if rules is not None:
        warnings.extend(rules.warnings())
    unresolved = _per_column(
        [
            (column.label, "the document states no unit or scale")
            for column in table.columns
            if column.unit is None
        ]
    )
    location = canonical(table.location)
    published = (
        "Read from one document table as published on the days it dates; no "
        if table.calendar is Frequency.DAILY
        else "Read from one document table as published on explicit months only; no "
    ) + "resampling, filling, currency conversion, inflation adjustment or rebasing was applied"
    return AnalyticalResult(
        result_id=f"web_url:table:{source.source_id}:{location}",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="web_url",
        method=METHOD,
        values=values,
        coverage=_span(table),
        parameters={
            "columns": [column.label for column in table.columns],
            "skipped_columns": [{"label": label, "code": code} for label, code in table.skipped],
            _ROW_WORD[table.calendar] + "s": len(table.months),
        },
        evidence=ResultEvidence(
            input_refs=[source_node or source.source_id],
            transformations=[
                TransformationRecord(
                    operation="document_table",
                    parameters={
                        "period_rule": _PERIOD_RULE[table.calendar],
                        "value_rule": "strict cell number; empty cells stay missing",
                        "unit_source": "per column",
                        "columns": [
                            {
                                "label": column.label,
                                "unit": column.unit,
                                "unit_source": column.unit_source,
                                "scale": column.scale.value,
                                "measure": column.measure.value,
                                "values": sum(
                                    1 for _, value, _ in column.cells if value is not None
                                ),
                            }
                            for column in table.columns
                        ],
                        "skipped": [[label, code] for label, code in table.skipped],
                        _ROW_WORD[table.calendar] + "s": len(table.months),
                        "content_hash": source.content_hash or "",
                        "fill": "none",
                        **({"csv": dict[str, JsonValue](csv)} if csv is not None else {}),
                        **(rules.evidence() if rules is not None else {}),
                        **(
                            {"aggregation": table.aggregation}
                            if table.aggregation is not None
                            else {}
                        ),
                    },
                    input_refs=[source.source_id],
                    output_ref=f"web_url:table:{source.source_id}",
                )
            ],
            sources=[source],
        ),
        warnings=warnings,
        limitations=[
            (
                _DAILY_LIMITATIONS[str(aggregation["rule"])]
                + "; no filling, currency conversion, inflation adjustment or rebasing was applied"
                if "rule" in aggregation
                else published
            ),
            *_per_column(
                [(column.label, measure_limitation(column.measure)) for column in table.columns]
            ),
            *(rules.limitations() if rules is not None else ()),
            *_per_column(
                [
                    (
                        column.label,
                        "unit and scale are as the user stated them in the question, not as "
                        "the document states them",
                    )
                    for column in table.columns
                    if column.unit_source == UNIT_FROM_QUESTION
                ]
            ),
        ],
        unresolved_semantics=unresolved,
    )


def _per_column(notes: Sequence[tuple[str, str]]) -> list[str]:
    """One line per distinct statement, naming every column it is about.

    Five columns that share one reason produced five near-identical lines in the
    answer, which read as five different limitations (finding L2-5). The wording
    for a single column is unchanged.
    """
    grouped: dict[str, list[str]] = {}
    for label, text in notes:
        grouped.setdefault(text, []).append(label)
    return [f"{', '.join(labels)}: {text}" for text, labels in grouped.items()]


def _month(end: date) -> Period:
    return Period(
        start=date(end.year, end.month, 1),
        end=date(end.year, end.month, calendar.monthrange(end.year, end.month)[1]),
        frequency=Frequency.MONTHLY,
    )


def _dated(end: date, frequency: Frequency) -> Period:
    """The period one row stands for: its month, or the single day it is dated to."""
    if frequency is Frequency.DAILY:
        return Period(start=end, end=end, frequency=Frequency.DAILY)
    return _month(end)


def _span(table: DocumentTable) -> Period:
    """The whole range the rows cover, on the calendar they are dated to."""
    if table.calendar is Frequency.DAILY:
        return Period(start=table.months[0], end=table.months[-1], frequency=Frequency.DAILY)
    return Period(
        start=date(table.months[0].year, table.months[0].month, 1),
        end=table.months[-1],
        frequency=Frequency.MONTHLY,
    )
