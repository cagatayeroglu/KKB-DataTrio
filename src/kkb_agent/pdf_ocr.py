"""M7-11: bounded rendering and untrusted OCR text, never unchecked analytical cells.

Rendering runs only inside the PDF parser's terminated worker. The caller
explicitly supplies OCR capability; nothing loads credentials or enables it.

DEC-149: the OCR model writes tables as HTML with row/column spans. `ocr_tables`
reads those blocks into rectangular candidate tables (literal cell text, group
and leaf headers, years stated before the table) under the same row/column/cell
budgets. They are candidates only: the document tools accept a column only
after it adds up to the table's total row (`_document_value.total_checked`).
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import re
import threading
from collections.abc import Sequence
from html.parser import HTMLParser
from typing import Protocol

from kkb_agent.ingestion_policy import AdmissionError, AdmissionLimits
from kkb_agent.llm.provider import Completion, ProviderError

MAX_OCR_PAGES = 3
MAX_PAGE_PIXELS = 4_000_000
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_OCR_TEXT = 65536
RENDER_SCALE = 2.0
_LAYOUT_TAG = re.compile(r"<\|[^<>\r\n]{1,64}\|>")
_NUMBER = re.compile(r"[+\-−]?\d[\d.,]*")
_YEAR = re.compile(r"(?<![\d.,])(19\d{2}|20\d{2}|2100)(?![\d.,])")
_MAX_HEADER_ROWS = 4
_MAX_SPAN = 64


class OcrProvider(Protocol):
    def ocr(self, images: Sequence[bytes]) -> Completion: ...


class OcrError(ValueError):
    """Only fixed local codes, never provider/document text."""


class CachedOcr:
    """One OCR call per page image per process (DEC-179).

    A page without a text layer is read twice in a turn: once for the outline that tells the
    planner which headers exist, once by the tool that reads the column. The model is asked
    once; the second read gets the same completion. Keys are digests of the exact image
    bytes, only complete answers are kept, and the oldest entries leave first.
    """

    def __init__(self, provider: OcrProvider, *, capacity: int = 64) -> None:
        self._provider = provider
        self._capacity = capacity
        self._kept: dict[str, Completion] = {}
        self._lock = threading.Lock()

    def ocr(self, images: Sequence[bytes]) -> Completion:
        key = hashlib.sha256(b"\0".join(hashlib.sha256(i).digest() for i in images)).hexdigest()
        with self._lock:
            kept = self._kept.get(key)
        if kept is not None:
            return kept
        result = self._provider.ocr(images)
        if result.finish_reason == "stop":
            with self._lock:
                self._kept[key] = result
                while len(self._kept) > self._capacity:
                    self._kept.pop(next(iter(self._kept)))
        return result


def render_pages(content: bytes, pages: list[dict[str, object]]) -> None:
    """Attach bounded inline PNGs only for pages without a text layer."""
    # This bounded native renderer ships no typing marker/stubs. Its image/page
    # sizes still pass the explicit checks below; only this import is untyped.
    import pypdfium2 as pdfium  # type: ignore[import-untyped]

    missing: list[tuple[dict[str, object], int]] = []
    for record in pages:
        if not isinstance(record.get("has_text"), bool):
            raise OcrError("PARSER_FAILED")
        if not record["has_text"]:
            number = record.get("number")
            if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                raise OcrError("PARSER_FAILED")
            missing.append((record, number))
    if len(missing) > MAX_OCR_PAGES:
        raise OcrError("LIMIT_EXCEEDED")
    if not missing:
        return
    with pdfium.PdfDocument(content) as pdf:
        # Validate all sizes before allocating the first bitmap.
        for _record, number in missing:
            page = pdf[number - 1]
            try:
                width, height = page.get_size()
                if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                    raise OcrError("LIMIT_EXCEEDED")
                if (
                    math.ceil(width * RENDER_SCALE) * math.ceil(height * RENDER_SCALE)
                    > MAX_PAGE_PIXELS
                ):
                    raise OcrError("LIMIT_EXCEEDED")
            finally:
                page.close()
        for record, number in missing:
            page = pdf[number - 1]
            try:
                bitmap = page.render(scale=RENDER_SCALE)
                try:
                    image = bitmap.to_pil()
                    try:
                        if image.width * image.height > MAX_PAGE_PIXELS:
                            raise OcrError("LIMIT_EXCEEDED")
                        output = io.BytesIO()
                        image.save(output, format="PNG")
                        png = output.getvalue()
                        if len(png) > MAX_IMAGE_BYTES:
                            raise OcrError("LIMIT_EXCEEDED")
                        record["ocr_png"] = base64.b64encode(png).decode("ascii")
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()


def extract_text(provider: OcrProvider, png: bytes, *, max_chars: int) -> str:
    """One page per call, no retry or interpretation; reject incomplete output."""
    try:
        result = provider.ocr((png,))
    except ProviderError:
        raise OcrError("OCR_FAILED") from None
    if result.finish_reason != "stop":
        raise OcrError("OCR_INCOMPLETE")
    if len(result.text) > min(max_chars, MAX_OCR_TEXT):
        raise OcrError("LIMIT_EXCEEDED")
    text = _LAYOUT_TAG.sub("", result.text).strip()
    if not text:
        raise OcrError("OCR_EMPTY")
    return text


class _TableTooComplex(ValueError):
    """An OCR table outside what `ocr_tables` reads; it is skipped, not repaired."""


class _OcrTableParser(HTMLParser):
    """`<table>` blocks as rows of (text, rowspan, colspan); other markup is ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.line_starts: list[int] = [0]
        self.tables: list[tuple[int, list[list[tuple[str, int, int]]] | None]] = []
        self._rows: list[list[tuple[str, int, int]]] | None = None
        self._cell: list[str] | None = None
        self._spans = (1, 1)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self._rows is not None:
                self._rows = None  # A nested table: the outer one is not read.
                self.tables[-1] = (self.tables[-1][0], None)
                return
            self.tables.append((self._index(), []))
            self._rows = self.tables[-1][1]
        elif self._rows is None:
            return
        elif tag == "tr":
            self._rows.append([])
        elif tag in ("td", "th"):
            values = dict(attrs)
            try:
                spans = tuple(int(values.get(name) or "1") for name in ("rowspan", "colspan"))
            except ValueError:
                spans = (0, 0)
            self._spans = (spans[0], spans[1])
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def _index(self) -> int:
        """The character offset of the current tag in the fed text."""
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_endtag(self, tag: str) -> None:
        if self._rows is None:
            return
        if tag in ("td", "th") and self._cell is not None:
            if not self._rows:
                self._rows.append([])
            text = " ".join("".join(self._cell).split())
            self._rows[-1].append((text, *self._spans))
            self._cell = None
        elif tag == "table":
            self._rows = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def ocr_tables(text: str, limits: AdmissionLimits) -> list[dict[str, object]]:
    """Candidate tables in untrusted OCR text: literal cells, never interpreted.

    Spans are expanded into a rectangle; a table that is ragged, nested, has an
    impossible span or exceeds the row/column/cell/field budgets is skipped.
    Leading rows without a number are headers (at most four): a column's
    distinct header texts give a group and a leaf. Years are those written in
    the OCR text before the table.
    """
    parser = _OcrTableParser()
    parser.line_starts += [match.end() for match in re.finditer("\n", text)]
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # noqa: BLE001 - html.parser on model text; nothing is read then
        return []
    found: list[dict[str, object]] = []
    cells = 0
    for offset, rows in parser.tables:
        if not rows:
            continue
        try:
            grid = _expand(rows, limits)
            cells += len(grid) * len(grid[0])
            if cells > limits.max_cells:
                raise _TableTooComplex
        except (_TableTooComplex, AdmissionError):
            continue
        table = _headed(grid)
        if table is None:
            continue
        before = text[:offset]
        table["years"] = sorted({int(year) for year in _YEAR.findall(_LAYOUT_TAG.sub(" ", before))})
        found.append(table)
    return found


def _expand(rows: list[list[tuple[str, int, int]]], limits: AdmissionLimits) -> list[list[str]]:
    placed: dict[tuple[int, int], str] = {}
    width = 0
    for r, row in enumerate(rows):
        column = 0
        for text, rowspan, colspan in row:
            if not (1 <= rowspan <= _MAX_SPAN and 1 <= colspan <= _MAX_SPAN):
                raise _TableTooComplex
            limits.check_field(text)
            while (r, column) in placed:
                column += 1
            for dr in range(rowspan):
                for dc in range(colspan):
                    if (r + dr, column + dc) in placed:
                        raise _TableTooComplex
                    placed[(r + dr, column + dc)] = text
            column += colspan
            width = max(width, column)
        limits.check_table_size(rows=r + 1, columns=width)
    height = max(r for r, _ in placed) + 1 if placed else 0
    if height != len(rows) or not width:
        raise _TableTooComplex  # A row span reaching past the table.
    grid = [[placed.get((r, c)) for c in range(width)] for r in range(height)]
    if any(cell is None for row in grid for cell in row):
        raise _TableTooComplex  # Ragged rows are not guessed into shape.
    return [[cell or "" for cell in row] for row in grid]


def _headed(grid: list[list[str]]) -> dict[str, object] | None:
    header_count = 0
    for row in grid:
        if any(_NUMBER.fullmatch(cell) for cell in row[1:]):
            break
        header_count += 1
    if not 1 <= header_count <= _MAX_HEADER_ROWS or len(grid) - header_count < 2:
        return None
    leaves: list[str] = []
    groups: list[str | None] = []
    for column in range(len(grid[0])):
        texts: list[str] = []
        for row in grid[:header_count]:
            if row[column] and (not texts or texts[-1] != row[column]):
                texts.append(row[column])
        leaves.append(texts[-1] if texts else "")
        groups.append(" ".join(texts[:-1]) or None if len(texts) > 1 else None)
    return {
        "rows": [leaves, *grid[header_count:]],
        "groups": groups if any(groups[1:]) else None,
    }
