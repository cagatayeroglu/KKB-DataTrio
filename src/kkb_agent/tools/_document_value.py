"""M7-18: one value out of a fetched table or PDF, as a result the gate can bind.

`web_url` loads what a document shows; this turns one cell of it into an
`AnalyticalResult` without deciding anything the document did not state:

- **Which cell.** The planner names a column header and a row label. The
  column matches its header with or without a trailing unit in parentheses;
  the row matches a label in another cell of that row, or the same date
  written another way. Both compare through the shared Turkish normaliser
  (DEC-116). Exactly one cell across every table must match, or nothing is
  returned: a guessed cell is a wrong figure with a source attached.
- **What number.** A spreadsheet number is used as stored. Text is read only
  when its separators leave one reading: `1.234,56`, `46,75` and `1.234.567`
  are unambiguous, `1.234` is a thousand or a fraction depending on the
  convention and is refused.
- **Unit and scale.** Only from a recognised unit in the column header's
  trailing parentheses — `(Milyon TL)`, `(%)`, `(TL/kg)`. Anything else stays
  unresolved: analytical claims are withheld (DEC-104); exact literal quotation
  needs the selected-cell proof and bounded presentation in DEC-132.
- **Period.** Only when the row label is a full date, `2026-06-01` or
  `01.06.2026`, and then that single day. A month or a year label sets none.

The label shown to the answer writer is the planner's column and row, which
come from the question, never document text; the matched header, row label
and cell text are kept in the result's parameters and provenance.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.core import (
    AnalyticalResult,
    ClaimKind,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    SourceRef,
)
from kkb_agent.csv_loader import CsvTable
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
}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DOTTED_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_MINUS = "-−"  # ASCII hyphen-minus and U+2212


class ValueNotSelected(ValueError):
    """No single, readable value; `code` is fixed and names no document text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Grid:
    """One table as a header row and data rows, with where it sits."""

    location: dict[str, str | int]
    headers: tuple[object, ...]
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class Cell:
    """The selected cell and the header and row label that located it."""

    location: dict[str, str | int]
    header: str
    row_label: str
    raw: object


@dataclass(frozen=True)
class Reading:
    """What the cell establishes: its number, and only the semantics stated."""

    value: float
    unit: str | None
    scale: Scale
    period: Period | None


def grids(table: CsvTable | XlsxTable | None, document: PdfDocument | None) -> list[Grid]:
    """Every table the loaded content offers; a PDF table's first row is its header."""
    if table is not None:
        location: dict[str, str | int] = {"table": 1}
        if isinstance(table, XlsxTable):
            location["sheet"] = table.selection
        return [Grid(location, tuple(table.headers), tuple(table.rows))]
    found: list[Grid] = []
    if document is not None:
        for page in document.pages:
            if page.ocr_text is not None:
                continue  # DEC-119: OCR text is not a validated table/cell.
            for index, pdf_table in enumerate(page.tables, 1):
                if pdf_table.rows:
                    header, *rows = pdf_table.rows
                    found.append(Grid({"page": page.number, "table": index}, header, tuple(rows)))
    return found


def select_cell(tables: list[Grid], column: str, row: str) -> Cell:
    """The one cell under `column` in the row labelled `row`, across every table."""
    wanted_column = normalize_search_text(column)
    if not wanted_column or not normalize_search_text(row):
        raise ValueNotSelected("VALUE_NOT_FOUND")
    matches: list[Cell] = []
    for grid in tables:
        columns = [
            index
            for index, header in enumerate(grid.headers)
            if wanted_column
            in (normalize_search_text(_text(header)), normalize_search_text(_bare(_text(header))))
        ]
        if len(columns) > 1:
            raise ValueNotSelected("AMBIGUOUS_VALUE")
        if not columns:
            continue
        target = columns[0]
        for number, cells in enumerate(grid.rows, 1):
            labels = [
                _text(value)
                for index, value in enumerate(cells)
                if index != target and _same_label(_text(value), row)
            ]
            if labels and target < len(cells):
                location = {**grid.location, "row_index": number, "column_index": target + 1}
                matches.append(
                    Cell(location, _text(grid.headers[target]), labels[0], cells[target])
                )
    if not matches:
        raise ValueNotSelected("VALUE_NOT_FOUND")
    if len(matches) > 1:
        raise ValueNotSelected("AMBIGUOUS_VALUE")
    return matches[0]


def read_number(raw: object) -> float:
    """A stored number as is, or text with exactly one reading; otherwise refuse."""
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
            raise ValueNotSelected("AMBIGUOUS_NUMBER")
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


def row_period(label: str) -> Period | None:
    """A single day when the row label is a full date; no period otherwise."""
    day = _as_date(label)
    return None if day is None else Period(start=day, end=day)


def read_cell(cell: Cell) -> Reading:
    """Everything the cell establishes, before anything is recorded anywhere."""
    unit, scale = header_semantics(cell.header)
    return Reading(read_number(cell.raw), unit, scale, row_period(cell.row_label))


def record_cell(lineage: Lineage, source_node: str, cell: Cell) -> str:
    """The cell as a transform of the source file it was read from."""
    reading = read_cell(cell)
    return lineage.record(
        NodeKind.TRANSFORM,
        "web_url_cell",
        attributes={
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
    if reading.period is not None:
        limitations.append(
            "The period is the date written in the selected row; the document does not "
            "say what span the value covers"
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
            "unit_source": "column header" if reading.unit is not None else None,
            "period_source": "row label" if reading.period is not None else None,
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


def _same_label(text: str, wanted: str) -> bool:
    if not text:
        return False
    if normalize_search_text(text) == normalize_search_text(wanted):
        return True
    day = _as_date(text)
    return day is not None and day == _as_date(wanted)


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
