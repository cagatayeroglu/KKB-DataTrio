"""M7-14: one column of a fetched document table, read as explicit monthly values.

Strict by decision (2026-09-17). Nothing the document does not state is decided:

- **Which column.** The planner names the period and value headers as the user
  wrote them. Exactly one table must hold both, each exactly once.
- **Which month.** A row's period cell must be an explicit month: `2026-01`,
  `01.2026`, a Turkish or English month name with its year, or a full date on
  the first or last day of its month (text or spreadsheet date). Any other
  non-empty label refuses the column. Two rows in one month refuse it too:
  choosing one of them, or averaging, would be a frequency conversion.
- **What number.** The cell number reader of M7-18: stored numbers as they are,
  text only with one reading. An empty cell stays missing and is never filled.
- **Unit and scale.** Only from the value header's trailing parentheses; a
  header without a recognised unit refuses the column. Stock/flow meaning is
  not stated by a document and stays unknown.

Refusal codes are fixed and never carry document text.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime

from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.core import Scale, SourceRef
from kkb_agent.lakehouse.result_evidence import canonical
from kkb_agent.tools._document_value import (
    Grid,
    ValueNotSelected,
    _text,
    header_matches,
    header_semantics,
    read_number,
)

SNAPSHOT_KIND = "document_column_v1"
_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("ocak", "january"),
            ("subat", "february"),
            ("mart", "march"),
            ("nisan", "april"),
            ("mayis", "may"),
            ("haziran", "june"),
            ("temmuz", "july"),
            ("agustos", "august"),
            ("eylul", "september"),
            ("ekim", "october"),
            ("kasim", "november"),
            ("aralik", "december"),
        ),
        1,
    )
    for name in names
}
_YEAR_MONTH = re.compile(r"(\d{4})-(\d{2})")
_MONTH_YEAR = re.compile(r"(\d{2})\.(\d{4})")
_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DOTTED_DAY = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_NAMED = re.compile(r"([a-z]+) (\d{4})")


class ColumnRefused(ValueError):
    """The column cannot be read without deciding something; `code` is fixed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DocumentColumn:
    location: dict[str, str | int]
    period_header: str
    value_header: str
    unit: str
    scale: Scale
    #: (month end, value or None for an empty cell, digest of the cell text)
    rows: tuple[tuple[date, float | None, str], ...]

    @property
    def levels(self) -> dict[date, float | None]:
        return {end: value for end, value, _ in self.rows}


def month_end(raw: object) -> date | None:
    """The month a period cell names explicitly, as its last day; None otherwise."""
    if isinstance(raw, datetime):
        if raw.time() != datetime.min.time():
            return None
        raw = raw.date()
    if isinstance(raw, date):
        return _edge_day(raw.year, raw.month, raw.day)
    if not isinstance(raw, str):
        return None
    text = normalize_search_text(raw)
    if match := _YEAR_MONTH.fullmatch(text):
        return _last_day(int(match[1]), int(match[2]))
    if match := _MONTH_YEAR.fullmatch(text):
        return _last_day(int(match[2]), int(match[1]))
    if match := _ISO_DAY.fullmatch(text):
        return _edge_day(int(match[1]), int(match[2]), int(match[3]))
    if match := _DOTTED_DAY.fullmatch(text):
        return _edge_day(int(match[3]), int(match[2]), int(match[1]))
    if (match := _NAMED.fullmatch(text)) and match[1] in _MONTHS:
        return _last_day(int(match[2]), _MONTHS[match[1]])
    return None


def read_column(tables: list[Grid], period_column: str, value_column: str) -> DocumentColumn:
    """The value column keyed by explicit months, from the one table holding both headers."""
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
    header = _text(grid.headers[value_index])
    unit, scale = header_semantics(header)
    if unit is None or scale is Scale.UNKNOWN:
        raise ColumnRefused("UNIT_NOT_STATED")

    rows: dict[date, tuple[float | None, str]] = {}
    for cells in grid.rows:
        label = cells[period_index] if period_index < len(cells) else None
        raw = cells[value_index] if value_index < len(cells) else None
        if _empty(label):
            if _empty(raw):
                continue  # A blank spacer row carries nothing.
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        end = month_end(label)
        if end is None:
            raise ColumnRefused("PERIOD_NOT_RECOGNISED")
        if end in rows:
            raise ColumnRefused("DUPLICATE_PERIOD")
        try:
            value = None if _empty(raw) else read_number(raw)
        except ValueNotSelected as error:
            raise ColumnRefused(error.code) from None
        rows[end] = (value, hashlib.sha256(_text(raw).encode()).hexdigest())
    if not rows:
        raise ColumnRefused("COLUMN_EMPTY")
    return DocumentColumn(
        location={**grid.location, "column_index": value_index + 1},
        period_header=_text(grid.headers[period_index]),
        value_header=header,
        unit=unit,
        scale=scale,
        rows=tuple((end, value, digest) for end, (value, digest) in sorted(rows.items())),
    )


def column_snapshot(column: DocumentColumn, source: SourceRef, media_type: str) -> str:
    """The exact cells an execution read, bound to the fetched bytes' hash.

    Kept in the session's own lineage; the proof shows only fixed facts from it.
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
            "rows": [[end, value, digest] for end, value, digest in column.rows],
        }
    )


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _last_day(year: int, month: int) -> date | None:
    if not (1 <= month <= 12 and 1900 <= year <= 2100):
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def _edge_day(year: int, month: int, day: int) -> date | None:
    end = _last_day(year, month)
    if end is None or day not in (1, end.day):
        return None
    return end
