"""M7-18: one value out of a fetched table or PDF, as a result the gate can bind.

`web_url` loads what a document shows; this turns one cell of it into an
`AnalyticalResult` without deciding anything the document did not state:

- **Which cell.** The planner names a column header and a row label. The
  column matches its header with or without a trailing unit in parentheses,
  either side of a bilingual `Hacim/Volume` header, and a drawn group with its
  column (`TL Hacim`, DEC-148); the row matches a label in another cell of that
  row, the same date written another way, or the same month written another
  way (`2025-12`, `12.2025`, `Aralık 2025`; never a day for a month, and never
  a cell that reads as a number). Both compare through the shared Turkish
  normaliser (DEC-116). Exactly one cell across every table must match, or
  nothing is returned: a guessed cell is a wrong figure with a source attached.
- **What number.** A spreadsheet number is used as stored. Text is read only
  when its separators leave one reading: `1.234,56`, `46,75` and `1.234.567`
  are unambiguous, `1.234` is a thousand or a fraction depending on the
  convention and is refused — unless other cells of the same table can be
  read only under one convention, which then decides it (DEC-148).
- **Unit and scale.** Only from a recognised unit in the column header's
  trailing parentheses — `(Milyon TL)`, `(%)`, `(TL/kg)`. Anything else stays
  unresolved: analytical claims are withheld (DEC-104); exact literal quotation
  needs the selected-cell proof and bounded presentation in DEC-132.
- **Period.** A full-date row label, `2026-06-01` or `01.06.2026`, sets that
  single day; a month-form label (DEC-147) sets that calendar month, without
  saying whether the value is a month-end level, an average or a total. A
  month name without a year (`Ocak / January`) takes the one year the page
  states above its table, or a year from the user's own question (DEC-148). A
  year or any other label sets none, and a month that ends after the document
  was retrieved is not an observation (`FUTURE_PERIOD`).

The label shown to the answer writer is the planner's column and row, which
come from the question, never document text; the matched header, row label
and cell text are kept in the result's parameters and provenance.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from pydantic import JsonValue

from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.core import (
    AnalyticalResult,
    ClaimKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
)
from kkb_agent.csv_loader import CsvTable
from kkb_agent.html_loader import HtmlDocument
from kkb_agent.ingest.json_table import RecordTable
from kkb_agent.lakehouse.lineage import EdgeKind, Lineage, NodeKind
from kkb_agent.xlsx_loader import XlsxTable

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.pdf_loader import PdfDocument

_TRAILING_UNIT = re.compile(r"[(\[]\s*([^()\[\]]+?)\s*[)\]]\s*$")
_SCALES = {
    "bin": Scale.THOUSAND,
    "milyon": Scale.MILLION,
    "milyar": Scale.BILLION,
    "thousand": Scale.THOUSAND,
    "million": Scale.MILLION,
    "billion": Scale.BILLION,
}
#: Folded unit spellings a header may state, and the unit recorded for each.
_UNITS = {
    "tl": "TRY",
    "try": "TRY",
    "₺": "TRY",
    "usd": "USD",
    "$": "USD",
    "dolar": "USD",
    "eur": "EUR",
    "€": "EUR",
    "euro": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "chf": "CHF",
    "jpy": "JPY",
    "%": "percent",
    "yuzde": "percent",
    "kg": "kg",
    "g": "g",
    "gr": "g",
    "gram": "g",
    "ton": "t",
    "ons": "troy_ounce",
    "puan": "points",
    "points": "points",
    "endeks": "index",
    "index": "index",
}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DOTTED_DATE = re.compile(r"(\d{2})[.-](\d{2})[.-](\d{4})")
#: Folded Turkish and English month names (DEC-116 normaliser output).
MONTH_NAMES = {
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
MONTH_NAMES.update(
    {
        name: i
        for i, name in enumerate(
            ("oca", "sub", "mar", "nis", "may", "haz", "tem", "agu", "eyl", "eki", "kas", "ara"), 1
        )
    }
)
_YEAR_MONTH = re.compile(r"(\d{4})[-m](\d{1,2})")
_MONTH_YEAR = re.compile(r"(\d{1,2})[./](\d{4})")
_NAMED_MONTH = re.compile(r"([a-z]+)[ -](\d{4}|\d{2})")
#: A digit convention a whole table establishes (DEC-148): Turkish groups with
#: dots and decimals with a comma, English the other way round.
type Convention = Literal["tr", "en"]
_TURKISH = re.compile(r"[+\-−]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
_ENGLISH = re.compile(r"[+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
OCR_LIMITATION = (
    "The values were read by OCR from a page without a text layer; they were accepted only "
    "because each column's rows add up to the table's total row within rounding"
)
#: Folded row labels that name a table's total rather than a period (DEC-148).
TOTAL_LABELS = frozenset({"toplam", "total", "genel toplam", "grand total"})
_MINUS = "-−"  # ASCII hyphen-minus and U+2212


class ValueNotSelected(ValueError):
    """No single, readable value; `code` is fixed and names no document text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HeaderPath:
    """A column header under a drawn group header cell (DEC-148), such as TL + Hacim."""

    group: str
    leaf: str

    def __str__(self) -> str:
        return f"{self.group} {self.leaf}".strip()


@dataclass(frozen=True)
class Grid:
    """One table as a header row and data rows, with where it sits."""

    location: dict[str, str | int]
    headers: tuple[object, ...]
    rows: tuple[tuple[object, ...], ...]
    #: Distinct years the page states above the table (PDF only, DEC-148).
    years: tuple[int, ...] = ()
    #: OCR tables only (DEC-149): per column, whether it adds up to the total row.
    checked: tuple[bool, ...] | None = None
    normalizations: tuple[dict[str, JsonValue], ...] = ()

    def percent_column(self, index: int) -> bool:
        """Only a whole numeric XLSX column with recorded plain-percent formats qualifies."""
        formatted = {
            item["row"]
            for item in self.normalizations
            if item.get("operation") == "excel_percent_points" and item.get("column") == index + 1
        }
        present = {
            row_number
            for row_number, row in enumerate(self.rows, 2)
            if index < len(row) and row[index] is not None and row[index] != ""
        }
        return bool(present) and present <= formatted


@dataclass(frozen=True)
class YearContext:
    """The year a label without one takes, and where it was stated."""

    year: int
    source: Literal["document", "question"]


@dataclass(frozen=True)
class Cell:
    """The selected cell and the header and row label that located it."""

    location: dict[str, str | int]
    header: str
    row_label: str
    raw: object
    year: YearContext | None = None
    convention: Convention | None = None
    #: Read by OCR from a page without text, from a column that adds up (DEC-149).
    ocr: bool = False
    normalizations: tuple[dict[str, JsonValue], ...] = ()


@dataclass(frozen=True)
class Reading:
    """What the cell establishes: its number, and only the semantics stated."""

    value: float
    unit: str | None
    scale: Scale
    period: Period | None


def grids(
    table: CsvTable | XlsxTable | RecordTable | None,
    document: PdfDocument | HtmlDocument | None,
) -> list[Grid]:
    """Every table the loaded content offers; a PDF table's first row is its header."""
    if isinstance(table, RecordTable):
        return [Grid({"records": "/".join(table.path) or "root"}, table.headers, table.rows)]
    if table is not None:
        location: dict[str, str | int] = {"table": 1}
        if isinstance(table, XlsxTable):
            location["sheet"] = table.selection
        return [
            Grid(
                location,
                tuple(table.headers),
                tuple(table.rows),
                normalizations=table.normalizations if isinstance(table, XlsxTable) else (),
            )
        ]
    if isinstance(document, HtmlDocument):
        return [
            Grid({"table": table.number}, table.rows[0], table.rows[1:])
            for table in document.tables
        ]
    found: list[Grid] = []
    if document is not None:
        for page in document.pages:
            if page.ocr_text is not None:
                # DEC-119/149: OCR text is no cell; its tables are candidates
                # whose columns count only once they add up to the total row.
                for index, ocr_table in enumerate(page.ocr_tables, 1):
                    header, *rows = ocr_table.rows
                    ocr_headers: tuple[object, ...] = tuple(
                        HeaderPath(group, leaf or "") if group else leaf
                        for group, leaf in zip(
                            ocr_table.groups or (None,) * len(header), header, strict=True
                        )
                    )
                    found.append(
                        Grid(
                            {"page": page.number, "table": index},
                            ocr_headers,
                            tuple(rows),
                            ocr_table.years,
                            total_checked(rows),
                        )
                    )
                continue
            for index, pdf_table in enumerate(page.tables, 1):
                if pdf_table.rows:
                    header, *rows = pdf_table.rows
                    headers: tuple[object, ...] = tuple(header)
                    if pdf_table.groups is not None:
                        headers = tuple(
                            HeaderPath(group, _text(leaf)) if group else leaf
                            for group, leaf in zip(pdf_table.groups, header, strict=True)
                        )
                    location = {"page": page.number, "table": index}
                    found.append(Grid(location, headers, tuple(rows), pdf_table.years))
    return found


def csv_parsing(table: CsvTable | XlsxTable | RecordTable | None) -> dict[str, str] | None:
    """How a CSV table was split (DEC-147): its separator, declared or detected."""
    if not isinstance(table, CsvTable):
        return None
    return {"delimiter": table.delimiter, "delimiter_source": table.delimiter_source}


def header_names(header: object) -> set[str]:
    """Every folded name a header answers to.

    As written, without its trailing unit, either side of a bilingual `A/B`
    name (with or without the unit), and for a drawn group the group before or
    after the column's own name (DEC-148). Matching still needs exactly one
    column, so a broader name refuses rather than guesses.
    """
    if isinstance(header, HeaderPath):
        leaves = header_names(header.leaf)
        groups = _alternatives(header.group)
        names = {normalize_search_text(str(header)), *leaves}
        for group in groups:
            for leaf in leaves:
                names.update({f"{group} {leaf}", f"{leaf} {group}"})
        return names - {""}
    text = _text(header)
    bare = _bare(text)
    unit = normalize_search_text(text[len(bare) :]) if text.startswith(bare) else ""
    names = {normalize_search_text(text)}
    for name in _alternatives(bare):
        names.add(name)
        if unit:
            names.add(f"{name} {unit}")
    return names - {""}


def header_matches(header: object, wanted: str) -> bool:
    """A header as the user named it (see `header_names`)."""
    folded = normalize_search_text(wanted)
    return bool(folded) and folded in header_names(header)


def context_year(grid: Grid, requested: int | None) -> YearContext | None:
    """The year for month labels without one: the document's, else the question's.

    One year stated above the table decides it, and a different requested year
    is a conflict. Several stated years decide nothing, not even with a request.
    """
    if len(grid.years) > 1:
        return None
    if len(grid.years) == 1:
        if requested is not None and requested != grid.years[0]:
            raise ValueNotSelected("YEAR_CONFLICT")
        return YearContext(grid.years[0], "document")
    return None if requested is None else YearContext(requested, "question")


def number_convention(rows: Iterable[Iterable[object]]) -> Convention | None:
    """The digit convention a table's text cells establish, if exactly one does.

    A cell readable only with Turkish grouping (`93.824.682.381`, `46,75`) is
    evidence for Turkish, one readable only with English grouping (`1,234.5`,
    `4.5`) for English; `1.234`, `1017` and dates or month labels are neither.
    Evidence for both, or none, decides nothing.
    """
    turkish = english = False
    for row in rows:
        for cell in row:
            if not isinstance(cell, str):
                continue
            text = cell.strip()
            if not text or _as_date(text) is not None or month_label(text) is not None:
                continue
            as_turkish = _TURKISH.fullmatch(text) is not None
            as_english = _ENGLISH.fullmatch(text) is not None
            turkish = turkish or (as_turkish and not as_english)
            english = english or (as_english and not as_turkish)
    if turkish != english:
        return "tr" if turkish else "en"
    return None


def year_in_question(year: int, question: str) -> bool:
    """Whether the user wrote this year as a number of its own (DEC-148)."""
    return re.search(rf"(?<![\d.,]){year}(?![\d.,])", question) is not None


def as_of(source: SourceRef) -> date | None:
    """The date a document was retrieved or uploaded; later periods are not observed."""
    return source.retrieved_at.date() if source.retrieved_at is not None else None


def total_checked(rows: Iterable[Iterable[object]]) -> tuple[bool, ...]:
    """DEC-149: which columns of an OCR table add up to its one total row.

    The table must hold exactly one total row; a value column then counts when
    its other readable cells (at least two) sum to that row's value within
    rounding — at most one half of the last printed digit per summed cell. An
    unreadable cell in the column, or no total row at all, checks nothing.
    """
    table = [tuple(row) for row in rows]
    width = max((len(row) for row in table), default=0)
    totals = [row for row in table if row and is_total_label(row[0])]
    if len(totals) != 1:
        return (False,) * width
    convention = number_convention(table)
    checked = [False]
    for column in range(1, width):
        try:
            total_cell = totals[0][column] if column < len(totals[0]) else None
            if _empty_text(total_cell):
                raise ValueNotSelected("NOT_A_NUMBER")
            total = Decimal(str(read_number(total_cell, convention)))
            parts = [
                row[column]
                for row in table
                if row is not totals[0] and column < len(row) and not _empty_text(row[column])
            ]
            values = [Decimal(str(read_number(cell, convention))) for cell in parts]
        except ValueNotSelected:
            checked.append(False)
            continue
        places = max(_printed_decimals(cell, convention) for cell in [*parts, total_cell])
        tolerance = Decimal(len(values)) * Decimal(5) * Decimal(10) ** -(places + 1)
        checked.append(len(values) >= 2 and abs(sum(values, Decimal(0)) - total) <= tolerance)
    return tuple(checked)


def is_annotation_label(raw: object) -> bool:
    text = _text(raw).strip()
    return normalize_search_text(text) in {"ortalama", "average"} or bool(
        re.match(r"^(?:kaynak|source)\s*:", text, re.IGNORECASE)
    )


def is_total_label(label: object) -> bool:
    """A row label naming the table's total (`Toplam`, `TOPLAM / TOTAL`)."""
    if not isinstance(label, str):
        return False
    parts = [part.strip() for part in normalize_search_text(label).split("/")]
    return bool(parts) and all(part in TOTAL_LABELS for part in parts)


def select_cell(tables: list[Grid], column: str, row: str, *, year: int | None = None) -> Cell:
    """The one cell under `column` in the row labelled `row`, across every table."""
    wanted_column = normalize_search_text(column)
    if not wanted_column or not normalize_search_text(row):
        raise ValueNotSelected("VALUE_NOT_FOUND")
    matches: list[Cell] = []
    for grid in tables:
        columns = [
            index for index, header in enumerate(grid.headers) if header_matches(header, column)
        ]
        if len(columns) > 1:
            raise ValueNotSelected("AMBIGUOUS_VALUE")
        if not columns:
            continue
        target = columns[0]
        if grid.checked is not None and not grid.checked[target]:
            raise ValueNotSelected("OCR_NOT_VALIDATED")
        context = context_year(grid, year)
        known = context.year if context is not None else None
        convention = number_convention(grid.rows)
        for number, cells in enumerate(grid.rows, 1):
            labels = [
                _text(value)
                for index, value in enumerate(cells)
                if index != target and _same_label(_text(value), row, known)
            ]
            if labels and target < len(cells):
                location = {**grid.location, "row_index": number, "column_index": target + 1}
                used = context if _needs_year(labels[0], context) else None
                matches.append(
                    Cell(
                        location,
                        _text(grid.headers[target]),
                        labels[0],
                        cells[target],
                        used,
                        convention,
                        grid.checked is not None,
                        tuple(
                            n
                            for n in grid.normalizations
                            if n["row"] == number + 1 and n["column"] == target + 1
                        ),
                    )
                )
    if not matches:
        raise ValueNotSelected("VALUE_NOT_FOUND")
    if len(matches) > 1:
        raise ValueNotSelected("AMBIGUOUS_VALUE")
    return matches[0]


def read_number(raw: object, convention: Convention | None = None) -> float:
    """A stored number as is, or text with exactly one reading; otherwise refuse.

    `convention`, established by the whole table, only decides a `1.234` or
    `1,234` that alone has two readings; it never changes any other reading.
    """
    if isinstance(raw, bool):
        raise ValueNotSelected("NOT_A_NUMBER")
    if isinstance(raw, int | float):
        if not math.isfinite(raw):
            raise ValueNotSelected("NOT_A_NUMBER")
        return float(raw)
    if not isinstance(raw, str):
        raise ValueNotSelected("NOT_A_NUMBER")
    text = raw.strip()
    sign = text[:1]
    negative = sign != "" and sign in _MINUS
    body = text[1:] if sign != "" and sign in _MINUS + "+" else text
    if not re.fullmatch(r"[0-9][0-9.,]*", body):
        raise ValueNotSelected("NOT_A_NUMBER")
    dots, commas = body.count("."), body.count(",")
    if dots and commas:
        decimal = "." if body.rfind(".") > body.rfind(",") else ","
        grouping = "," if decimal == "." else "."
        integer, _, fraction = body.rpartition(decimal)
        if grouping in fraction or decimal in integer or not _grouped(integer, grouping):
            raise ValueNotSelected("NOT_A_NUMBER")
        digits = f"{integer.replace(grouping, '')}.{fraction}"
    elif dots > 1 or commas > 1:
        separator = "." if dots else ","
        if not _grouped(body, separator):
            raise ValueNotSelected("NOT_A_NUMBER")
        digits = body.replace(separator, "")
    elif dots or commas:
        integer, _, fraction = body.partition("." if dots else ",")
        if not fraction:
            raise ValueNotSelected("NOT_A_NUMBER")
        if len(fraction) == 3 and len(integer) <= 3 and integer != "0":
            # 1.234 is a thousand in Turkish and a fraction in English; 1234.567
            # and 0.125 cannot be grouped, so they have one reading.
            if convention is None:
                raise ValueNotSelected("AMBIGUOUS_NUMBER")
            # The table's convention says whether this separator groups digits.
            groups = (dots and convention == "tr") or (commas and convention == "en")
            digits = integer + fraction if groups else f"{integer}.{fraction}"
        else:
            digits = f"{integer}.{fraction}"
    else:
        digits = body
    value = float(digits)
    return -value if negative else value


def header_semantics(header: str) -> tuple[str | None, Scale]:
    """The unit and scale a header's trailing parentheses state, or nothing."""
    match = _TRAILING_UNIT.search(header)
    if match is None:
        return None, Scale.UNKNOWN
    words = normalize_search_text(match[1]).split(" ")
    scale = Scale.ONE
    if len(words) == 2 and words[0] in _SCALES:
        scale, words = _SCALES[words[0]], words[1:]
    if len(words) != 1:
        return None, Scale.UNKNOWN
    parts = words[0].split("/")
    if not all(part in _UNITS for part in parts):
        return None, Scale.UNKNOWN
    return "/".join(_UNITS[part] for part in parts), scale


def last_day(year: int, month: int) -> date | None:
    """The last day of a month in the supported range; None for an impossible month."""
    if not (1 <= month <= 12 and 1900 <= year <= 2100):
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def month_label(label: str, year: int | None = None) -> date | None:
    """The month a label writes in month form, as its last day; None otherwise.

    `2026-01`, `01.2026`, or a Turkish or English month name with its year. A
    full date is a day rather than a month, and a year alone is not a month.
    With a context `year`, a month name without one also counts, alone or as
    `Ocak / January` naming one month twice (DEC-148).
    """
    text = normalize_search_text(label)
    if match := _YEAR_MONTH.fullmatch(text):
        return last_day(int(match[1]), int(match[2]))
    if match := _MONTH_YEAR.fullmatch(text):
        return last_day(int(match[2]), int(match[1]))
    if (match := _NAMED_MONTH.fullmatch(text)) and match[1] in MONTH_NAMES:
        # The explicitly supported short-year document syntax is 20YY.
        named_year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
        return last_day(named_year, MONTH_NAMES[match[1]])
    if year is not None and text:
        months = {MONTH_NAMES.get(part.strip()) for part in text.split("/")}
        if len(months) == 1 and None not in months:
            return last_day(year, next(iter(months)) or 0)
    return None


def row_period(label: str, year: int | None = None) -> Period | None:
    """A single day for a full-date row label, a calendar month for a month-form one."""
    day = _as_date(label)
    if day is not None:
        return Period(start=day, end=day)
    end = month_label(label, year)
    if end is None:
        return None
    return Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY)


def read_cell(cell: Cell, *, as_of: date | None = None) -> Reading:
    """Everything the cell establishes, before anything is recorded anywhere.

    With `as_of` (the document's retrieval date) a period ending later is not
    an observation yet and refuses as FUTURE_PERIOD.
    """
    unit, scale = header_semantics(cell.header)
    period = row_period(cell.row_label, cell.year.year if cell.year is not None else None)
    if as_of is not None and period is not None and period.end > as_of:
        raise ValueNotSelected("FUTURE_PERIOD")
    return Reading(read_number(cell.raw, cell.convention), unit, scale, period)


def record_cell(lineage: Lineage, source_node: str, cell: Cell) -> str:
    """The cell as a transform of the source file it was read from."""
    reading = read_cell(cell)
    return lineage.record(
        NodeKind.TRANSFORM,
        "web_url_cell",
        attributes={
            **({"extraction": "ocr"} if cell.ocr else {}),
            "location": json.dumps(cell.location, ensure_ascii=False, sort_keys=True),
            "header": cell.header,
            "row_label": cell.row_label,
            "cell_digest": hashlib.sha256(_text(cell.raw).encode()).hexdigest(),
            "reading": json.dumps(
                {
                    "value": reading.value,
                    "unit": reading.unit,
                    "scale": reading.scale.value,
                    "period": reading.period.model_dump(mode="json") if reading.period else None,
                },
                sort_keys=True,
            ),
        },
        upstream=[(source_node, EdgeKind.DERIVES_FROM)],
    )


def document_value(
    cell: Cell,
    reading: Reading,
    *,
    source: SourceRef,
    label: str,
    source_node: str | None,
    cell_node: str | None,
) -> AnalyticalResult:
    """The cell as a LEVEL result whose evidence names where it was read."""
    location = json.dumps(cell.location, ensure_ascii=False, sort_keys=True)
    fragment = SourceRef(
        source_id=json.dumps([source.source_id, cell.location], ensure_ascii=True, sort_keys=True),
        source_type=source.source_type,
        locator=json.dumps([source.locator, cell.location], ensure_ascii=True, sort_keys=True),
        retrieved_at=source.retrieved_at,
        content_hash=source.content_hash,
    )
    limitations = [
        "Read from one cell of a fetched document as published; not recomputed or "
        "compared with any other source"
    ]
    if reading.period is not None and reading.period.frequency is Frequency.MONTHLY:
        limitations.append(
            "The period is the month written in the selected row; the document does not "
            "say whether the value is a month-end level, a monthly average or a monthly total"
        )
        if cell.year is not None:
            limitations.append(
                "The row names a month without a year; the year was taken from "
                + (
                    "the page text above the table"
                    if cell.year.source == "document"
                    else "the question"
                )
            )
    elif reading.period is not None:
        limitations.append(
            "The period is the date written in the selected row; the document does not "
            "say what span the value covers"
        )
    if cell.ocr:
        limitations.append(OCR_LIMITATION)
    if cell.convention is not None and _ambiguous(cell.raw):
        limitations.append(
            "The figure's digit grouping was read from the other figures in its table ("
            + ("Turkish" if cell.convention == "tr" else "English")
            + " convention)"
        )
    unresolved = []
    if reading.unit is None:
        unresolved.append(
            "The column header states no recognised unit or scale, so the value's unit "
            "and scale are unknown"
        )
    return AnalyticalResult(
        result_id=f"web_url:{source.source_id}:{location}",
        claim_kind=ClaimKind.LITERAL_SOURCE_VALUE,
        kind=ResultKind.LEVEL,
        status=ResultStatus.COMPUTED,
        tool="web_url",
        method="document_cell",
        values=[
            ResultValue(
                label=label,
                value=reading.value,
                unit=reading.unit,
                scale=reading.scale,
                period=reading.period,
            ),
        ],
        parameters={
            **cell.location,
            "header": cell.header,
            "row_label": cell.row_label,
            "cell_text": _text(cell.raw),
            **({"normalizations": list(cell.normalizations)} if cell.normalizations else {}),
            "unit_source": "column header" if reading.unit is not None else None,
            "period_source": _period_source(reading, cell),
        },
        evidence=ResultEvidence(
            input_refs=[source_node or source.source_id],
            lineage_node=cell_node,
            sources=[fragment],
        ),
        limitations=limitations,
        unresolved_semantics=unresolved,
    )


def _text(value: object) -> str:
    """A cell as comparable text: dates as ISO days, whole floats without `.0`."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.time() == datetime.min.time():
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def _bare(header: str) -> str:
    """The header without its trailing parenthesised unit."""
    return _TRAILING_UNIT.sub("", header).strip()


def _empty_text(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _printed_decimals(cell: object, convention: Convention | None) -> int:
    """How many decimal digits a figure was printed with, under the table's convention."""
    if not isinstance(cell, str):
        return 0
    text = cell.strip()
    separator = {"tr": ",", "en": "."}.get(convention or "")
    if separator is None:
        marks = [char for char in text if char in ".,"]
        tail = re.split(r"[.,]", text)[-1] if marks else ""
        return len(tail) if len(marks) == 1 and len(tail) != 3 else 0
    return len(text.rsplit(separator, 1)[1]) if separator in text else 0


def _alternatives(text: str) -> set[str]:
    """A folded name and, for a bilingual `A/B` name, each side."""
    folded = normalize_search_text(text)
    parts = [part.strip() for part in folded.split("/")]
    return {folded, *parts} if len(parts) > 1 and all(parts) else {folded}


def _period_source(reading: Reading, cell: Cell) -> str | None:
    if reading.period is None:
        return None
    if cell.year is None:
        return "row label"
    return f"row label with the {cell.year.source} year"


def _needs_year(label: str, context: YearContext | None) -> bool:
    return (
        context is not None
        and _as_date(label) is None
        and month_label(label) is None
        and month_label(label, context.year) is not None
    )


def _ambiguous(raw: object) -> bool:
    try:
        read_number(raw)
    except ValueNotSelected as error:
        return error.code == "AMBIGUOUS_NUMBER"
    return False


def _same_label(text: str, wanted: str, year: int | None = None) -> bool:
    if not text:
        return False
    if normalize_search_text(text) == normalize_search_text(wanted):
        return True
    day = _as_date(text)
    if day is not None:
        return day == _as_date(wanted)
    month = month_label(text, year)
    return month is not None and month == month_label(wanted, year) and not _is_number(text)


def _is_number(text: str) -> bool:
    """Whether a cell reads as a number, as `12.2025` does; such a cell is no month label."""
    try:
        read_number(text)
    except ValueNotSelected:
        return False
    return True


def _as_date(text: str) -> date | None:
    text = text.strip()
    try:
        if _ISO_DATE.fullmatch(text):
            return date.fromisoformat(text)
        if match := _DOTTED_DATE.fullmatch(text):
            return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        return None
    return None


def _grouped(integer: str, separator: str) -> bool:
    head, *rest = integer.split(separator)
    return (
        bool(rest)
        and 1 <= len(head) <= 3
        and head.isdigit()
        and all(len(part) == 3 and part.isdigit() for part in rest)
    )
