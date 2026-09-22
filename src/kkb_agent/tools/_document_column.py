"""M7-14: one column of a fetched document table, read as explicit monthly values.

Strict by decision (2026-09-17). Nothing the document does not state is decided:

- **Which column.** The planner names the period and value headers as the user
  wrote them. Exactly one table must hold both, each exactly once.
- **Which month.** A row's period cell must be an explicit month: `2026-01`,
  `01.2026`, a Turkish or English month name with its year, or a full date on
  the first or last day of its month (text or spreadsheet date). Any other
  non-empty label refuses the column. Two rows in one month refuse it too:
  choosing one of them, or averaging, would be a frequency conversion. Under
  DEC-148 a month name without a year takes the table's year context, a total
  row (`Toplam / Total`) is skipped and a month ending after the document was
  retrieved is not an observation; both skips are reported.
- **What number.** The cell number reader of M7-18: stored numbers as they are,
  text only with one reading, where the table's own digit convention decides
  `1.234` (DEC-148). An empty cell stays missing and is never filled.
- **Unit and scale.** Only from the value header's trailing parentheses; a
  header without a recognised unit refuses the column.
- **Measure.** A document does not state stock/flow meaning. At scale one a
  header unit of points or index names an index level (DEC-145) and a percent
  unit names a rate (DEC-146); every other column stays unknown.

Refusal codes are fixed and never carry document text.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from pydantic import JsonValue

from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.core import Scale, SourceRef, StockFlow
from kkb_agent.lakehouse.result_evidence import canonical
from kkb_agent.tools._document_value import (
    OCR_LIMITATION,
    Convention,
    Grid,
    ValueNotSelected,
    YearContext,
    _ambiguous,
    _text,
    context_year,
    header_matches,
    header_semantics,
    is_total_label,
    last_day,
    month_label,
    number_convention,
    read_number,
)

SNAPSHOT_KIND = "document_column_v1"
#: DEC-145/146: header units that name a measurement kind by themselves at scale one.
UNIT_MEASURES = {"points": StockFlow.INDEX, "index": StockFlow.INDEX, "percent": StockFlow.RATE}


def document_measure(unit: str | None, scale: Scale) -> StockFlow:
    """The measurement kind a header unit states by itself; unknown otherwise."""
    if unit is None or scale is not Scale.ONE:
        return StockFlow.UNKNOWN
    return UNIT_MEASURES.get(unit, StockFlow.UNKNOWN)


_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DOTTED_DAY = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


class ColumnRefused(ValueError):
    """The column cannot be read without deciding something; `code` is fixed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class RowRules:
    """How a table's rows are read under DEC-148, and what those rules decided."""

    year: YearContext | None
    as_of: date | None
    convention: Convention | None
    skipped: Counter[str] = field(default_factory=Counter)
    year_used: bool = False
    convention_used: bool = False
    #: Per column for an OCR table (DEC-149); None for text the document holds.
    checked: tuple[bool, ...] | None = None
    normalizations: tuple[dict[str, JsonValue], ...] = ()

    @classmethod
    def for_grid(cls, grid: Grid, *, year: int | None, as_of: date | None) -> RowRules:
        try:
            context = context_year(grid, year)
        except ValueNotSelected as error:
            raise ColumnRefused(error.code) from None
        return cls(
            context,
            as_of,
            number_convention(grid.rows),
            checked=grid.checked,
            normalizations=grid.normalizations,
        )

    def column_checked(self, index: int) -> bool:
        """False only for an OCR column that does not add up to its total row."""
        return self.checked is None or self.checked[index]

    def month(self, label: object) -> date | None:
        """The row's month end, or None when the row is skipped (and counted)."""
        if is_total_label(label):
            self.skipped["TOTAL_ROW"] += 1
            return None
        known = self.year.year if self.year is not None else None
        end = month_end(label, known)
        if end is None:
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if known is not None and month_end(label) is None:
            self.year_used = True
        if self.as_of is not None and end > self.as_of:
            self.skipped["FUTURE_PERIOD"] += 1
            return None
        return end

    def day(self, label: object) -> date | None:
        """The row's calendar day, or None when the row is skipped (and counted)."""
        if is_total_label(label):
            self.skipped["TOTAL_ROW"] += 1
            return None
        day = calendar_day(label)
        if day is None:
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if self.as_of is not None and day > self.as_of:
            self.skipped["FUTURE_PERIOD"] += 1
            return None
        return day

    def number(self, raw: object) -> float:
        value = read_number(raw, self.convention)
        if self.convention is not None and _ambiguous(raw):
            self.convention_used = True
        return value

    def evidence(self) -> dict[str, JsonValue]:
        """The decisions to record; empty when none of these rules applied."""
        recorded: dict[str, JsonValue] = {}
        if self.normalizations:
            recorded["normalizations"] = list(self.normalizations)
        if self.checked is not None:
            recorded["extraction"] = "ocr"
            recorded["validation"] = "column total"
        if self.year_used and self.year is not None:
            recorded["year"] = {"value": self.year.year, "source": self.year.source}
        if self.convention_used:
            recorded["number_convention"] = self.convention
        if self.skipped:
            recorded["skipped_rows"] = {code: count for code, count in sorted(self.skipped.items())}
        return recorded

    def warnings(self) -> list[str]:
        notes = []
        if count := self.skipped.get("TOTAL_ROW"):
            notes.append(f"{count} total row(s) were left out of the monthly rows (TOTAL_ROW)")
        if count := self.skipped.get("FUTURE_PERIOD"):
            notes.append(
                f"{count} month(s) ending after the document was retrieved were left out "
                "(FUTURE_PERIOD)"
            )
        return notes

    def limitations(self) -> list[str]:
        notes = [OCR_LIMITATION] if self.checked is not None else []
        if self.year_used and self.year is not None:
            notes.append(
                "Month labels carry no year; the year was taken from "
                + (
                    "the page text above the table"
                    if self.year.source == "document"
                    else "the question"
                )
            )
        if self.convention_used:
            notes.append(
                "Numbers such as 1.234 were read with the digit grouping the rest of the table "
                "uses (" + ("Turkish" if self.convention == "tr" else "English") + " convention)"
            )
        return notes


@dataclass(frozen=True)
class DocumentColumn:
    location: dict[str, str | int]
    period_header: str
    value_header: str
    unit: str
    scale: Scale
    measure: StockFlow
    #: (month end, value or None for an empty cell, digest of the cell text)
    rows: tuple[tuple[date, float | None, str], ...]
    rules: RowRules | None = None

    @property
    def levels(self) -> dict[date, float | None]:
        return {end: value for end, value, _ in self.rows}


def measure_limitation(measure: StockFlow) -> str:
    """The fixed statement of how a document column's measurement kind was decided."""
    if measure is StockFlow.INDEX:
        return (
            "The values are treated as index levels only because the column header states "
            "points or index as their unit; no other stock/flow meaning was inferred"
        )
    if measure is StockFlow.RATE:
        return (
            "The values are treated as rates only because the column header states percent "
            "as their unit; a share or percentage change would read the same way"
        )
    return "The document does not state whether the values are stocks, flows, rates or index levels"


def month_end(raw: object, year: int | None = None) -> date | None:
    """The month a period cell names explicitly, as its last day; None otherwise.

    `year` is a table's year context for month names written without one.
    """
    if isinstance(raw, datetime):
        if raw.time() != datetime.min.time():
            return None
        raw = raw.date()
    if isinstance(raw, date):
        return _edge_day(raw.year, raw.month, raw.day)
    if not isinstance(raw, str):
        return None
    if (end := month_label(raw, year)) is not None:
        return end
    text = normalize_search_text(raw)
    if match := _ISO_DAY.fullmatch(text):
        return _edge_day(int(match[1]), int(match[2]), int(match[3]))
    if match := _DOTTED_DAY.fullmatch(text):
        return _edge_day(int(match[3]), int(match[2]), int(match[1]))
    return None


def calendar_day(raw: object) -> date | None:
    """The single calendar day a period cell names; None when it names anything else."""
    if isinstance(raw, datetime):
        return raw.date() if raw.time() == datetime.min.time() else None
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.endswith(("T00:00:00", " 00:00:00")):
        text = text[:10]
    for pattern, order in ((_ISO_DAY, (1, 2, 3)), (_DOTTED_DAY, (3, 2, 1))):
        if match := pattern.fullmatch(text):
            try:
                return date(int(match[order[0]]), int(match[order[1]]), int(match[order[2]]))
            except ValueError:
                return None
    return None


def _locate(tables: list[Grid], period_column: str, value_column: str) -> tuple[Grid, int, int]:
    """The one table holding both headers, and their positions in it."""
    found: list[tuple[Grid, int, int]] = []
    for grid in tables:
        periods = [
            i for i, header in enumerate(grid.headers) if header_matches(header, period_column)
        ]
        values = [
            i for i, header in enumerate(grid.headers) if header_matches(header, value_column)
        ]
        if len(periods) > 1 or len(values) > 1:
            raise ColumnRefused("AMBIGUOUS_COLUMN")
        if periods and values:
            found.append((grid, periods[0], values[0]))
    if not found:
        raise ColumnRefused("COLUMN_NOT_FOUND")
    if len(found) > 1:
        raise ColumnRefused("AMBIGUOUS_COLUMN")
    grid, period_index, value_index = found[0]
    if period_index == value_index:
        raise ColumnRefused("AMBIGUOUS_COLUMN")
    return grid, period_index, value_index


def _month_rows(
    grid: Grid, period_index: int, value_index: int, rules: RowRules
) -> tuple[tuple[date, float | None, str], ...]:
    """Every explicit month and its value, refusing what would need a guess."""
    if not rules.column_checked(value_index):
        raise ColumnRefused("OCR_NOT_VALIDATED")
    rows: dict[date, tuple[float | None, str]] = {}
    for cells in grid.rows:
        label = cells[period_index] if period_index < len(cells) else None
        raw = cells[value_index] if value_index < len(cells) else None
        if _empty(label):
            if _empty(raw):
                continue  # A blank spacer row carries nothing.
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        end = rules.month(label)
        if end is None:
            continue
        if end in rows:
            raise ColumnRefused("DUPLICATE_PERIOD")
        try:
            value = None if _empty(raw) else rules.number(raw)
        except ValueNotSelected as error:
            raise ColumnRefused(error.code) from None
        rows[end] = (value, hashlib.sha256(_text(raw).encode()).hexdigest())
    if not rows:
        raise ColumnRefused("COLUMN_EMPTY")
    return tuple((end, value, digest) for end, (value, digest) in sorted(rows.items()))


def read_column(
    tables: list[Grid],
    period_column: str,
    value_column: str,
    *,
    year: int | None = None,
    as_of: date | None = None,
) -> DocumentColumn:
    """The value column keyed by explicit months, from the one table holding both headers.

    `year` is a year from the user's question, `as_of` the document's retrieval date.
    """
    grid, period_index, value_index = _locate(tables, period_column, value_column)
    header = _text(grid.headers[value_index])
    unit, scale = header_semantics(header)
    if unit is None or scale is Scale.UNKNOWN:
        raise ColumnRefused("UNIT_NOT_STATED")
    rules = RowRules.for_grid(grid, year=year, as_of=as_of)
    return DocumentColumn(
        location={**grid.location, "column_index": value_index + 1},
        period_header=_text(grid.headers[period_index]),
        value_header=header,
        unit=unit,
        scale=scale,
        measure=document_measure(unit, scale),
        rows=_month_rows(grid, period_index, value_index, rules),
        rules=rules,
    )


def read_month_values(
    tables: list[Grid],
    period_column: str,
    value_column: str,
    *,
    year: int | None = None,
    as_of: date | None = None,
) -> tuple[tuple[date, float | None, str], ...]:
    """The same months and values as `read_column`, for a caller that declares the unit.

    Every refusal but one is kept: an ambiguous or missing column, an unchecked
    OCR column, an unrecognised or duplicated period, a cell that is not a single
    number. Only the header's unit is not required, because the knowledge base
    asks the person to state it (DEC-157) instead of reading it from a caption.
    """
    grid, period_index, value_index = _locate(tables, period_column, value_column)
    rules = RowRules.for_grid(grid, year=year, as_of=as_of)
    return _month_rows(grid, period_index, value_index, rules)


def column_snapshot(
    column: DocumentColumn,
    source: SourceRef,
    media_type: str,
    *,
    csv: dict[str, str] | None = None,
) -> str:
    """The exact cells an execution read, bound to the fetched bytes' hash.

    Kept in the session's own lineage; the proof shows only fixed facts from it.
    `csv` records how a CSV was split (DEC-147), declared or detected.
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
            "location": column.location,
            "period_header": column.period_header,
            "value_header": column.value_header,
            "unit": column.unit,
            "scale": column.scale.value,
            "measure": column.measure.value,
            "rows": [[end, value, digest] for end, value, digest in column.rows],
            **({"csv": csv} if csv is not None else {}),
            **(column.rules.evidence() if column.rules is not None else {}),
        }
    )


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _edge_day(year: int, month: int, day: int) -> date | None:
    end = last_day(year, month)
    if end is None or day not in (1, end.day):
        return None
    return end
