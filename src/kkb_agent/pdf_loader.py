"""M7-09/M7-10 bounded PDF text and ruled-table extraction.

Same shape as the CSV and XLSX loaders: admission first, then one spawn worker
that is terminated and reaped at its deadline, writes bounded JSON to a private
file, and on Linux runs under an address-space cap. A PDF is a container of
compressed streams and fonts, and pdfminer decompresses and lays them out in
memory; the worker, not a timeout around it, is what stops runaway work.

What comes out is what the page shows, not what it means:

- Page text as pdfplumber lays it out, and whether the page has a text layer.
- Tables where ruling lines draw them (pdfplumber's "lines" strategy), with
  their bounding box in PDF points from the page's top-left corner.
- Under DEC-148, numeric tables set out with word positions alone ("layout"
  tables): rows by baseline, value columns by the right edges their numbers
  share, a label run on the left and header runs that end on a column edge.
  Nothing is guessed from whitespace: a number that fits no column or two, a
  column edge fewer than two numbers share, or a text cell among the numbers
  leaves the block in the page text. A group label (TL/USD/EUR) belongs to
  columns only through a drawn header cell around it. A "ruled" table that no
  stroked line draws is cell shading: it hides no words from layout reading,
  and it is dropped where it overlaps a layout table, as is a one-column
  fragment of one.
- For every table, the distinct years the page text above it states.
- Cells as literal text. "1.234,56" is not converted, and no unit, date,
  period or scale is inferred.

Unreadable input is refused with a fixed code rather than approximated
(M7-10): a password-protected or unsupported encryption (`ENCRYPTED`), a
document pdfminer cannot parse (`MALFORMED_DOCUMENT`), no pages
(`EMPTY_DOCUMENT`), and no text on any page (`NO_TEXT_LAYER` — a scan, which
needs explicit OCR capability, M7-11). A text-less page inside a readable document is flagged, and
glyphs without a Unicode mapping are reported, instead of being filled in.
pdfplumber's repair option is never used: it runs Ghostscript.
"""

from __future__ import annotations

import base64
import io
import json
import multiprocessing
import os
import re
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal
from uuid import uuid4

from kkb_agent.core import DataContract, SourceRef
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    admit_upload,
)
from kkb_agent.pdf_ocr import (
    OcrError,
    OcrProvider,
    data_years,
    extract_text,
    ocr_tables,
    render_pages,
)

if TYPE_CHECKING:  # pragma: no cover - the parser is imported in the worker only
    from pdfplumber.pdf import PDF

#: pdfminer's placeholder for a glyph whose font has no Unicode mapping.
_UNMAPPED = "(cid:"
#: DEC-148 layout tables: tolerances in PDF points and the tokens they accept.
_LINE_TOLERANCE = 2.5
_EDGE_TOLERANCE = 2.0
_RUN_GAP = 4.0
_MAX_HEADER_LINES = 4
_NUMBER = re.compile(r"[+\-−]?\d[\d.,]*")
_YEAR = re.compile(r"(?<![\d.,])(19\d{2}|20\d{2}|2100)(?![\d.,])")

type _Word = dict[str, Any]


@dataclass(frozen=True)
class PdfTable:
    """One table. `bbox` is (x0, top, x1, bottom) in points, top-left origin."""

    page: int
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str | None, ...], ...] = field(repr=False)
    #: "ruled" where lines draw it, "layout" where word positions set it out (DEC-148),
    #: "ocr" where the OCR model wrote it for a page without text (DEC-149).
    kind: Literal["ruled", "layout", "ocr"] = "ruled"
    #: Per column, the text of a drawn group header cell above it (layout tables).
    groups: tuple[str | None, ...] | None = field(default=None, repr=False)
    #: Distinct years stated in the page text above the table.
    years: tuple[int, ...] = ()


@dataclass(frozen=True)
class PdfPage:
    number: int
    width: float
    height: float
    has_text: bool
    text: str = field(repr=False)
    tables: tuple[PdfTable, ...] = field(repr=False)
    ocr_text: str | None = field(default=None, repr=False)
    #: Candidate tables in the OCR text; unchecked until a column adds up (DEC-149).
    ocr_tables: tuple[PdfTable, ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class PdfDocument:
    """Extracted content with its locations; `warnings` are fixed codes only."""

    data_ref: str
    contract: DataContract = field(repr=False)
    pages: tuple[PdfPage, ...] = field(repr=False)
    warnings: tuple[str, ...] = ()

    @property
    def tables(self) -> tuple[PdfTable, ...]:
        return tuple(table for page in self.pages for table in page.tables)


@dataclass(frozen=True)
class PdfLoadResult:
    """Loading outcome only; `loaded` is not a profile or an analytical result."""

    status: Literal["loaded", "rejected"]
    source: SourceRef = field(repr=False)
    code: str | None = None
    document: PdfDocument | None = field(default=None, repr=False)


class _PdfRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _open(content: bytes) -> PDF:
    """Open without repair; map pdfminer's refusal to a fixed code."""
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
    from pdfplumber.pdf import PDF as Pdf
    from pdfplumber.utils.exceptions import PdfminerException

    try:
        return Pdf(io.BytesIO(content))
    except PdfminerException as error:
        cause = error.args[0] if error.args else None
        if isinstance(cause, PDFPasswordIncorrect | PDFEncryptionError):
            raise _PdfRejected("ENCRYPTED") from None
        raise _PdfRejected("MALFORMED_DOCUMENT") from None


def _parse(content: bytes, limits: AdmissionLimits, ocr_enabled: bool = False) -> dict[str, object]:
    from pdfminer.pdfpage import PDFPage

    pdf = _open(content)
    try:
        # Count before pdfplumber builds every page, so a huge page tree stops
        # at the cap instead of after it.
        count = 0
        for _ in PDFPage.create_pages(pdf.doc):
            count += 1
            if count > limits.max_pdf_pages:
                raise _PdfRejected("LIMIT_EXCEEDED")
        if not count:
            raise _PdfRejected("EMPTY_DOCUMENT")

        pages: list[dict[str, object]] = []
        cells = 0
        output_size = 0
        unmapped = False
        for page in pdf.pages:
            text = page.extract_text() or ""
            limits.check_field(text)
            strokes = [
                [float(item["x0"]), float(item["top"]), float(item["x1"]), float(item["bottom"])]
                for item in [*page.lines, *(rect for rect in page.rects if rect.get("stroke"))]
            ]
            ruled: list[dict[str, Any]] = []
            for drawn in page.find_tables():
                x0, top, x1, bottom = drawn.bbox
                box = [float(x0), float(top), float(x1), float(bottom)]
                stroked = any(_inside(stroke, box) for stroke in strokes)
                ruled.append({"bbox": box, "rows": drawn.extract(), "stroked": stroked})
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            layout = _layout_tables(words, list(page.rects), ruled)
            tables: list[dict[str, Any]] = []
            for table in ruled:
                drawn_grid = table.pop("stroked") and _width(table["rows"]) > 1
                overlaps = any(
                    _mostly_inside(table["bbox"], other["bbox"])
                    or _mostly_inside(other["bbox"], table["bbox"])
                    for other in layout
                )
                if drawn_grid or not overlaps:
                    tables.append(table)
            tables += layout
            for table in tables:
                rows = table["rows"]
                width = _width(rows)
                limits.check_table_size(rows=len(rows), columns=width)
                cells += len(rows) * width
                if cells > limits.max_cells:
                    raise _PdfRejected("LIMIT_EXCEEDED")
                for row in rows:
                    for cell in row:
                        if cell is not None:
                            limits.check_field(cell)
                            unmapped = unmapped or _UNMAPPED in cell
                table["years"] = _years_above(words, table["bbox"][1])
            record = {
                "number": page.page_number,
                "width": float(page.width),
                "height": float(page.height),
                "has_text": bool(page.chars),
                "text": text,
                "tables": tables,
            }
            unmapped = unmapped or _UNMAPPED in text
            output_size += len(json.dumps(record, ensure_ascii=True).encode())
            if output_size > limits.max_expanded_bytes:
                raise _PdfRejected("LIMIT_EXCEEDED")
            pages.append(record)
    finally:
        pdf.close()

    if ocr_enabled:
        render_pages(content, pages)
    if not ocr_enabled and not any(page["has_text"] for page in pages):
        raise _PdfRejected("NO_TEXT_LAYER")
    warnings = []
    if not all(page["has_text"] for page in pages):
        warnings.append("PAGES_WITHOUT_TEXT")
    if unmapped:
        warnings.append("UNMAPPED_GLYPHS")
    return {"status": "loaded", "pages": pages, "warnings": warnings}


def _width(rows: list[list[str | None]]) -> int:
    return max((len(row) for row in rows), default=0)


def _inside(inner: list[float], outer: list[float]) -> bool:
    tolerance = _EDGE_TOLERANCE
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def _mostly_inside(inner: list[float], outer: list[float]) -> bool:
    """At least 80% of `inner`'s area lies within `outer` (a fragment of it)."""
    width = min(inner[2], outer[2]) - max(inner[0], outer[0])
    height = min(inner[3], outer[3]) - max(inner[1], outer[1])
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return width > 0 and height > 0 and area > 0 and width * height >= 0.8 * area


def _years_above(words: list[_Word], top: float) -> list[int]:
    """Distinct years written in the page text above a table's top edge.

    Read line by line rather than word by word, because what a year means depends on what
    sits beside it: "10 Şubat 2025" is the date the document carries, not the year its
    figures are from (`data_years`).
    """
    above = [word for word in words if word["bottom"] <= top + _EDGE_TOLERANCE]
    found: set[int] = set()
    for line in _lines(above):
        found.update(data_years(" ".join(word["text"] for word in line)))
    return sorted(found)


def _lines(words: list[_Word]) -> list[list[_Word]]:
    """Words grouped by baseline, top to bottom, each line left to right."""
    lines: list[list[_Word]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= _LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: item["x0"]) for line in lines]


def _runs(line: list[_Word]) -> list[list[_Word]]:
    """Adjacent words of one line, split where the gap is wider than a space."""
    runs: list[list[_Word]] = []
    for word in line:
        if runs and word["x0"] - runs[-1][-1]["x1"] <= _RUN_GAP:
            runs[-1].append(word)
        else:
            runs.append([word])
    return runs


def _data_line(line: list[_Word]) -> tuple[list[_Word], list[_Word]] | None:
    """A label run with some text, then single numbers only; None for any other line."""
    runs = _runs(line)
    label, values = runs[0], runs[1:]
    if (
        not values
        or all(_NUMBER.fullmatch(word["text"]) for word in label)
        or any(len(run) != 1 or not _NUMBER.fullmatch(run[0]["text"]) for run in values)
    ):
        return None
    return label, [run[0] for run in values]


def _row_like(line: list[_Word]) -> bool:
    """A label followed by some numbers: a data row even if a text cell broke it."""
    runs = _runs(line)
    return not all(_NUMBER.fullmatch(word["text"]) for word in runs[0]) and any(
        _NUMBER.fullmatch(word["text"]) for run in runs[1:] for word in run
    )


def _layout_tables(
    words: list[_Word], rects: list[_Word], ruled: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """DEC-148 numeric tables from word positions, outside stroked multi-column tables."""
    covered = [table["bbox"] for table in ruled if table["stroked"] and _width(table["rows"]) > 1]
    free = [
        word
        for word in words
        if not any(
            _inside([word["x0"], word["top"], word["x1"], word["bottom"]], box) for box in covered
        )
    ]
    lines = _lines(free)
    found: list[dict[str, Any]] = []
    start = 0
    while start < len(lines):
        if _data_line(lines[start]) is None:
            start += 1
            continue
        end = start
        while end + 1 < len(lines) and _data_line(lines[end + 1]) is not None:
            end += 1
        table = _layout_table(lines, start, end, rects)
        if table is not None:
            found.append(table)
        start = end + 1
    return found


def _layout_table(
    lines: list[list[_Word]], start: int, end: int, rects: list[_Word]
) -> dict[str, Any] | None:
    block = [_data_line(line) for line in lines[start : end + 1]]
    parsed = [item for item in block if item is not None]
    if sum(1 for _, values in parsed if len(values) >= 2) < 2:
        return None
    tolerance = _EDGE_TOLERANCE
    clusters: list[list[float]] = []
    for right in sorted(word["x1"] for _, values in parsed for word in values):
        if clusters and right - clusters[-1][0] <= tolerance:
            clusters[-1].append(right)
        else:
            clusters.append([right])
    if any(len(cluster) < 2 for cluster in clusters):
        return None  # An edge only one number has is not a column.
    edges = [max(cluster) for cluster in clusters]
    label_right = max(word["x1"] for label, _ in parsed for word in label)
    lefts = [label_right, *edges[:-1]]

    data: list[list[str | None]] = []
    for label, values in parsed:
        cells: list[str | None] = [None] * len(edges)
        for word in values:
            column = next(
                (i for i, edge in enumerate(edges) if abs(word["x1"] - edge) <= tolerance), None
            )
            if column is None or cells[column] is not None or word["x0"] <= lefts[column]:
                return None  # A number between columns or two in one: no guessing.
            cells[column] = word["text"]
        data.append([" ".join(word["text"] for word in label), *cells])

    block_top = min(word["top"] for word in lines[start])
    pitch = statistics.median(
        min(w["top"] for w in lines[i + 1]) - min(w["top"] for w in lines[i])
        for i in range(start, end)
    )
    header_lines: list[list[_Word]] = []
    above = start - 1
    below_top = block_top
    while above >= 0 and len(header_lines) < _MAX_HEADER_LINES:
        line_top = min(word["top"] for word in lines[above])
        if below_top - line_top > 1.5 * pitch:
            break
        if _row_like(lines[above]):
            return None  # A broken row above the block: the table is interrupted.
        header_lines.insert(0, lines[above])
        below_top = line_top
        above -= 1
    header_top = min((min(w["top"] for w in line) for line in header_lines), default=block_top)

    leaves: list[list[str]] = [[] for _ in edges]
    label_header: list[str] = []
    runs = [run for line in header_lines for run in _runs(line)]
    unplaced: list[list[_Word]] = []
    placed_boxes: list[list[float]] = []
    for run in runs:
        x0, x1 = run[0]["x0"], run[-1]["x1"]
        run_text = " ".join(word["text"] for word in run)
        box = [x0, min(w["top"] for w in run), x1, max(w["bottom"] for w in run)]
        if x1 <= label_right + tolerance:
            label_header.append(run_text)
            placed_boxes.append(box)
            continue
        column = next(
            (
                i
                for i, edge in enumerate(edges)
                if abs(x1 - edge) <= tolerance and x0 > lefts[i] - tolerance
            ),
            None,
        )
        if column is not None:
            leaves[column].append(run_text)
            placed_boxes.append(box)
        else:
            unplaced.append(run)

    groups: list[list[str]] = [[] for _ in edges]
    band = [
        rect
        for rect in rects
        if rect["top"] >= header_top - 2 * _LINE_TOLERANCE
        and rect["bottom"] <= block_top + tolerance
        and rect["x0"] > label_right - tolerance
    ]
    for run in unplaced:
        box = [
            run[0]["x0"],
            min(w["top"] for w in run),
            run[-1]["x1"],
            max(w["bottom"] for w in run),
        ]
        cells_around = [
            rect
            for rect in band
            if _inside(box, [rect["x0"], rect["top"], rect["x1"], rect["bottom"]])
            and not any(
                _inside(other, [rect["x0"], rect["top"], rect["x1"], rect["bottom"]])
                for other in placed_boxes
            )
        ]
        if not cells_around:
            continue  # A group label without a drawn cell binds to nothing.
        cell = min(cells_around, key=lambda rect: rect["width"] * rect["height"])
        for i, edge in enumerate(edges):
            if cell["x0"] - tolerance <= edge <= cell["x1"] + tolerance:
                groups[i].append(" ".join(word["text"] for word in run))

    header: list[str | None] = [" ".join(label_header), *(" ".join(parts) for parts in leaves)]
    everything = [word for line in [*header_lines, *lines[start : end + 1]] for word in line]
    return {
        "bbox": [
            float(min(word["x0"] for word in everything)),
            float(header_top),
            float(max(word["x1"] for word in everything)),
            float(max(word["bottom"] for word in lines[end])),
        ],
        "rows": [header, *data],
        "kind": "layout",
        "groups": ([None, *(" ".join(parts) or None for parts in groups)] if any(groups) else None),
    }


def _write_result(output: Path, result: dict[str, object], limit: int) -> None:
    size = 0
    with open(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        for chunk in json.JSONEncoder(ensure_ascii=True, allow_nan=False).iterencode(result):
            data = chunk.encode("utf-8")
            size += len(data)
            if size > limit:
                raise _PdfRejected("LIMIT_EXCEEDED")
            stream.write(data)


def _worker(
    content: bytes, limits: AdmissionLimits, output: Path, ocr_enabled: bool = False
) -> None:
    import logging
    import warnings

    # pdfminer logs and warns about the objects it meets; in this process that
    # would copy document content to the inherited stderr.
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    try:
        if sys.platform == "linux":
            import resource

            memory = max(512 * 1024 * 1024, limits.max_expanded_bytes * 8)
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        _write_result(
            output,
            _parse(content, limits, True) if ocr_enabled else _parse(content, limits),
            limits.max_expanded_bytes,
        )
        return
    except (AdmissionError, _PdfRejected) as error:
        code = str(error.code)
    except OcrError as error:
        code = str(error)
    except MemoryError:
        code = "LIMIT_EXCEEDED"
    except Exception as error:
        # pdfminer's own syntax errors mean a malformed file; anything else is
        # a parser failure. Neither may carry library or document text out.
        from pdfminer.psexceptions import PSException

        code = "MALFORMED_DOCUMENT" if isinstance(error, PSException) else "PARSER_FAILED"
    output.unlink(missing_ok=True)
    _write_result(output, {"status": "rejected", "code": code}, 1024)


def _run_worker(
    content: bytes, limits: AdmissionLimits, ocr_enabled: bool = False
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="kkb-pdf-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(
            target=_worker,
            args=(content, limits, output, True) if ocr_enabled else (content, limits, output),
        )
        deadline = time.monotonic() + limits.max_pdf_parser_seconds
        try:
            process.start()
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.terminate()
                process.join(0.2)
                if process.is_alive():
                    process.kill()
                    process.join()
                return {"status": "rejected", "code": "LIMIT_EXCEEDED"}
            if process.exitcode != 0 or not output.is_file():
                return {"status": "rejected", "code": "PARSER_FAILED"}
            cap = max(limits.max_expanded_bytes, 1024)
            with output.open("rb") as stream:
                data = stream.read(cap + 1)
            if len(data) > cap:
                return {"status": "rejected", "code": "LIMIT_EXCEEDED"}
            payload: dict[str, Any] = json.loads(data)  # written by _worker above
            return payload
        finally:
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


def load_pdf(
    stream: BinaryIO,
    *,
    filename: str,
    content_type: str,
    source: SourceRef,
    limits: AdmissionLimits = DEFAULT_LIMITS,
    ocr: OcrProvider | None = None,
) -> PdfLoadResult:
    """Admit and extract one PDF under the budgets in `limits`.

    Pages are capped by `max_pdf_pages` before any is laid out, the worker by
    `max_pdf_parser_seconds`; page text and each cell by `max_field_chars`,
    each table by the row/column caps, all tables together by `max_cells`, and
    the serialized result by `max_expanded_bytes`. Exceeding any is a
    rejection, never a truncation. Input I/O timeout belongs to the caller.
    With explicit `ocr`, only text-less pages are rendered in that worker:
    at most three pages, 4 million pixels and 8 MiB PNG per page. OCR calls
    run once per page under the provider transport deadline, without retries.
    OCR text stays separate from native text/tables and cannot become a cell.
    Spawn applications need the usual `__main__` guard.
    """
    source = SourceRef.model_validate(source)
    try:
        admitted = admit_upload(stream, filename=filename, content_type=content_type, limits=limits)
        if admitted.kind != FileKind.PDF:
            return PdfLoadResult("rejected", source, "UNSUPPORTED_FORMAT")
        result = (
            _run_worker(admitted.content, limits)
            if ocr is None
            else _run_worker(admitted.content, limits, True)
        )
    except AdmissionError as error:
        return PdfLoadResult("rejected", source, error.code.value)
    except OSError:
        return PdfLoadResult("rejected", source, "PARSER_FAILED")
    if result["status"] != "loaded":
        return PdfLoadResult("rejected", source, result["code"])

    if ocr is not None:
        try:
            for page in result["pages"]:
                png = page.pop("ocr_png", None)
                if png is not None:
                    page["ocr_text"] = extract_text(
                        ocr, base64.b64decode(png, validate=True), max_chars=limits.max_field_chars
                    )
                    # OCR is never inserted into native text or tables.
                    page["tables"] = []
                    page["ocr_tables"] = ocr_tables(page["ocr_text"], limits)
            if any(page.get("ocr_text") is not None for page in result["pages"]):
                result["warnings"].append("OCR_UNVERIFIED")
            if len(json.dumps(result, ensure_ascii=True).encode()) > limits.max_expanded_bytes:
                raise OcrError("LIMIT_EXCEEDED")
        except OcrError as error:
            return PdfLoadResult("rejected", source, str(error))

    pages = tuple(
        PdfPage(
            number=page["number"],
            width=page["width"],
            height=page["height"],
            has_text=page["has_text"],
            text=page["text"],
            ocr_text=page.get("ocr_text"),
            ocr_tables=tuple(
                PdfTable(
                    page=page["number"],
                    bbox=(0.0, 0.0, page["width"], page["height"]),
                    rows=tuple(tuple(row) for row in table["rows"]),
                    kind="ocr",
                    groups=None if table.get("groups") is None else tuple(table["groups"]),
                    years=tuple(table.get("years", ())),
                )
                for table in page.get("ocr_tables", ())
            ),
            tables=tuple(
                PdfTable(
                    page=page["number"],
                    bbox=(table["bbox"][0], table["bbox"][1], table["bbox"][2], table["bbox"][3]),
                    rows=tuple(tuple(row) for row in table["rows"]),
                    kind=table.get("kind", "ruled"),
                    groups=None if table.get("groups") is None else tuple(table["groups"]),
                    years=tuple(table.get("years", ())),
                )
                for table in page["tables"]
            ),
        )
        for page in result["pages"]
    )
    data_ref = f"data:{uuid4().hex}"
    document = PdfDocument(
        data_ref,
        DataContract(contract_id=data_ref, source=source, title="PDF document"),
        pages,
        tuple(result["warnings"]),
    )
    return PdfLoadResult("loaded", source, document=document)
