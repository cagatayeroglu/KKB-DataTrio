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
    is_annotation_label,
    is_total_label,
    number_convention,
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
UNIT_FROM_FORMAT = "Excel percentage number format"

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
    #: When the months were read across one row (`read_row`): which row, how its cells were
    #: laid out and where its year came from. None for a table read down a period column.
    row: dict[str, JsonValue] | None = None


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
        if grid.percent_column(index):
            if unit is not None and (unit, scale) != ("percent", Scale.ONE):
                skipped.append((label, "UNIT_CONFLICT"))
                continue
            if unit is None:
                unit, scale, source = "percent", Scale.ONE, UNIT_FROM_FORMAT
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
        calendar=_daily_calendar(tuple(end for end, _ in rows)) if daily else Frequency.MONTHLY,
    )


#: Where a unit the model named for a row came from: the document's own text.
UNIT_FROM_DOCUMENT = "document text"
#: Words that name a number of things, with no currency or rate.
_COUNT_WORDS = frozenset({"adet", "count", "units", "kisi", "islem", "arac"})
_SCALE_OF = {"bin": Scale.THOUSAND, "milyon": Scale.MILLION, "milyar": Scale.BILLION}


def unit_of(text: str) -> tuple[str, Scale] | None:
    """A unit and scale as written ("milyon TL", "adet", "%"), or None when it names none."""
    unit, scale = header_semantics(f"x ({text})")
    if unit is not None and scale is not Scale.UNKNOWN:
        return unit, scale
    words = normalize_search_text(text).split()
    if words and set(words) - set(_SCALE_OF) <= _COUNT_WORDS and set(words) & _COUNT_WORDS:
        scales = [_SCALE_OF[word] for word in words if word in _SCALE_OF]
        return "count", scales[0] if len(scales) == 1 else Scale.ONE
    return None


def _is_month(token: str) -> bool:
    """Whether one header word names a single month (any year)."""
    return month_end(token, 2000) is not None


def _the_row(grid: Grid, row: str) -> int:
    """The one row whose first cell is `row`, or begins with it as whole words."""
    wanted = normalize_search_text(row)
    matches = [
        index
        for index, cells in enumerate(grid.rows)
        if cells
        and (
            header_matches(_text(cells[0]), row)
            or normalize_search_text(_text(cells[0])).startswith(wanted + " ")
        )
    ]
    if not matches:
        raise ColumnRefused("ROW_NOT_FOUND")
    if len(matches) > 1:
        raise ColumnRefused("AMBIGUOUS_ROW")
    return matches[0]


def read_row(
    grid: Grid,
    row: str,
    *,
    label: str,
    year: int | None = None,
    columns: Sequence[str] | None = None,
    unit: tuple[str, Scale] | None = None,
    as_of: date | None = None,
) -> DocumentTable:
    """One row of a table whose columns are months, read as a monthly column.

    The shape of a yearly report: a row per year (or per series), a column per month,
    and a total at the end. `read_table` reads months down a period column and had no way
    across, so a model holding such a table could quote its cells and compute nothing
    from them (A3, 2026-09-23). Everything here is read from the table as it stands:

    - **Which row.** The one row whose first cell is `row`, or begins with it.
    - **Which months.** Every header that names one month; a header naming a range
      ("Ocak-Ağustos"), a total or anything else is left out and said so. `columns`
      narrows to headers the model names, and one it names that is not there refuses.
    - **Which year.** A header's own year first; else `year`; else the row's own label
      when it is a year; else the one year the page states above the table. Two that
      disagree, or none where one is needed, refuse (`YEAR_CONFLICT`, `YEAR_NEEDED`).
    - **Which values.** The cells under those headers, read in the table's own digit
      convention. An empty cell stays missing, never zero; a month ending after the
      document was retrieved is left out and counted; two headers for one month refuse.
    - **A collapsed layout.** A PDF extractor can leave a whole row of months in one
      cell under one header cell ("YIL Ocak Şubat …"). Such a cell is split on spaces
      only when its values fill the months in order, and a row with fewer values than
      months only when the months it lacks are exactly those not yet ended at retrieval:
      a gap in the middle would shift every later value into the wrong month, so it
      refuses (`CELLS_NOT_ALIGNED`) rather than guess.
    """
    index = _the_row(grid, row)
    cells = grid.rows[index]
    wanted = normalize_search_text(row)
    row_year = int(wanted) if len(wanted) == 4 and wanted.isdigit() else None
    if year is not None and row_year is not None and year != row_year:
        raise ColumnRefused("YEAR_CONFLICT")
    known: int | None = year if year is not None else row_year
    year_from = "argument" if year is not None else "row label" if row_year is not None else None
    if known is None and len(set(grid.years)) == 1:
        known, year_from = grid.years[0], "page text above the table"

    # (header, raw cell) in column order; the row's own label column is not a value.
    pairs: list[tuple[str, object]] = []
    collapsed = False
    for position, header in enumerate(grid.headers):
        text = _text(header)
        raw = cells[position] if position < len(cells) else None
        words = text.split()
        if sum(_is_month(word) for word in words) >= 2:
            collapsed = True
            values = _text(raw).split()
            if position == 0:
                # The row's label leads its cell, as the label column's name ("YIL") leads
                # the header cell; both are left before the months are paired.
                values = values[len(_text(row).split()) :]
                words = words[next(at for at, word in enumerate(words) if _is_month(word)) :]
            pairs.extend(_aligned(words, values, known, as_of))
        elif position > 0:
            pairs.append((text, raw))

    if collapsed:
        tokens = [
            " ".join(_text(cell) for cell in line).replace("%", " ").split() for line in grid.rows
        ]
        convention = number_convention(tokens)
    else:
        convention = number_convention(grid.rows)
    rules = RowRules(None, as_of, convention)

    chosen = list(columns) if columns is not None else None
    if chosen is not None:
        missing = [name for name in chosen if not any(header_matches(h, name) for h, _ in pairs)]
        if missing:
            raise ColumnRefused("COLUMN_NOT_FOUND")
    read: list[tuple[date, float | None, str]] = []
    left_out: list[str] = []
    yearless = False
    for header, raw in pairs:
        if chosen is not None and not any(header_matches(header, name) for name in chosen):
            continue
        own = month_end(header)
        if own is None and not _is_month(header):
            left_out.append(header or "(unnamed column)")
            continue
        if own is None and known is None:
            raise ColumnRefused("YEAR_NEEDED")
        end = own if own is not None else month_end(header, known)
        yearless = yearless or own is None
        if end is None:  # pragma: no cover - a month word with a year always has an end
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if any(end == seen for seen, _, _ in read):
            raise ColumnRefused("DUPLICATE_PERIOD")
        if as_of is not None and end > as_of:
            rules.skipped["FUTURE_PERIOD"] += 1
            continue
        try:
            value = None if _empty(raw) else rules.number(raw)
        except ValueNotSelected as error:
            raise ColumnRefused(error.code) from None
        read.append((end, value, hashlib.sha256(_text(raw).encode()).hexdigest()))
    if sum(1 for _, value, _ in read if value is not None) < 2:
        raise ColumnRefused("TOO_FEW_VALUES")
    read.sort(key=lambda cell: cell[0])
    unit_name, scale = unit if unit is not None else (None, Scale.UNKNOWN)
    return DocumentTable(
        location=dict(grid.location),
        period_header="(months across the header row)",
        months=tuple(end for end, _, _ in read),
        columns=(
            TableColumn(
                label,
                _text(row),
                index + 1,
                unit_name,
                scale,
                document_measure(unit_name, scale),
                tuple(read),
                UNIT_FROM_DOCUMENT if unit is not None else None,
            ),
        ),
        skipped=tuple((header, "NOT_A_MONTH") for header in left_out),
        rules=rules,
        row={
            "label": _text(row),
            "row_number": index + 1,
            "orientation": "months across columns",
            "layout": "space-aligned cells" if collapsed else "one cell per column",
            "year": known if yearless else None,
            "year_from": year_from if yearless else "header",
        },
    )


def _aligned(
    words: list[str], values: list[str], year: int | None, as_of: date | None
) -> list[tuple[str, object]]:
    """Header words of a collapsed row paired with its values, or a refusal.

    Values fill the header words in order. A trailing word that is not a month (a
    total) may hold a value or none. Fewer values than months is accepted only when
    every month left without one ends after the document was retrieved.
    """
    months = [word for word in words if _is_month(word)]
    last = max(at for at, word in enumerate(words) if _is_month(word))
    if words[: last + 1] != months:
        raise ColumnRefused("CELLS_NOT_ALIGNED")
    trailing = words[last + 1 :]
    if len(months) <= len(values) <= len(words):
        return [(word, values[at] if at < len(values) else None) for at, word in enumerate(words)]
    if len(values) < len(months) and as_of is not None and year is not None:
        unfilled = months[len(values) :]
        if all((end := month_end(word, year)) is not None and end > as_of for word in unfilled):
            return [
                *zip(months, values, strict=False),
                *((word, None) for word in unfilled),
                *((word, None) for word in trailing),
            ]
    raise ColumnRefused("CELLS_NOT_ALIGNED")


def _daily_calendar(dates: Sequence[date]) -> Frequency:
    """DAILY, or BUSINESS_DAY when the table's own dates are a trading calendar.

    A document table had only these two readings: a calendar day or a month. An
    exchange publishes on trading days, so Friday is followed by Monday, and read as
    DAILY that three-day step is not the one-day step a change asks for: every Monday
    came back empty, and the table said its own weekends were missing observations.

    The calendar is read from the dates the table carries, not from the weekday of any
    particular row: rows that all land Monday to Friday and skip at least one weekend
    are a trading-day series. A table that does date a Saturday or Sunday stays DAILY,
    and so does one too short to have skipped a weekend, because a weekday-only week is
    not evidence of anything. A genuinely missing weekday is still a gap either way:
    BUSINESS_DAY counts weekdays and invents no holiday.
    """
    if len(dates) < 2 or any(day.weekday() > 4 for day in dates):
        return Frequency.DAILY
    ordered = sorted(dates)
    spans_weekend = any(
        (later - earlier).days > 1
        for earlier, later in zip(ordered, ordered[1:], strict=False)
        if earlier.weekday() == 4
    )
    return Frequency.BUSINESS_DAY if spans_weekend else Frequency.DAILY


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
        if _empty(raw) or is_total_label(raw) or is_annotation_label(raw):
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
        if grid.percent_column(index):
            if unit is not None and (unit, scale) != ("percent", Scale.ONE):
                skipped.append((label, "UNIT_CONFLICT"))
                continue
            if unit is None:
                unit, scale, source = "percent", Scale.ONE, UNIT_FROM_FORMAT
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
            **({"row": table.row} if table.row is not None else {}),
        }
    )


def table_result(
    table: DocumentTable,
    source: SourceRef,
    *,
    source_node: str | None,
    csv: dict[str, str] | None = None,
    tool: str = "web_url",
) -> AnalyticalResult:
    """The published table: every read value, periods explicit, gaps never filled.

    `tool` is the tool that read it: `web_url` down a period column, `table_transform`
    across a row of a document already read (`read_row`).
    """
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
        result_id=f"{tool}:table:{source.source_id}:{location}",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool=tool,
        method=METHOD,
        values=values,
        coverage=_span(table),
        parameters={
            "columns": [column.label for column in table.columns],
            "skipped_columns": [{"label": label, "code": code} for label, code in table.skipped],
            _ROW_WORD[table.calendar] + "s": len(table.months),
            **({"row": table.row} if table.row is not None else {}),
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
                        **({"row": table.row} if table.row is not None else {}),
                    },
                    input_refs=[source.source_id],
                    output_ref=f"{tool}:table:{source.source_id}",
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
