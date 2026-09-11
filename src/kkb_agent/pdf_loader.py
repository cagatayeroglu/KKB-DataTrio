"""M7-09/M7-10 bounded PDF text and ruled-table extraction.

Same shape as the CSV and XLSX loaders: admission first, then one spawn worker
that is terminated and reaped at its deadline, writes bounded JSON to a private
file, and on Linux runs under an address-space cap. A PDF is a container of
compressed streams and fonts, and pdfminer decompresses and lays them out in
memory; the worker, not a timeout around it, is what stops runaway work.

What comes out is what the page shows, not what it means:

- Page text as pdfplumber lays it out, and whether the page has a text layer.
- Tables only where ruling lines draw them (pdfplumber's "lines" strategy),
  with their bounding box in PDF points from the page's top-left corner. A
  table set out with spaces alone stays in the page text; guessing columns
  from whitespace is how a figure lands under the wrong header.
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
from kkb_agent.pdf_ocr import OcrError, OcrProvider, extract_text, render_pages

if TYPE_CHECKING:  # pragma: no cover - the parser is imported in the worker only
    from pdfplumber.pdf import PDF

#: pdfminer's placeholder for a glyph whose font has no Unicode mapping.
_UNMAPPED = "(cid:"


@dataclass(frozen=True)
class PdfTable:
    """One ruled table. `bbox` is (x0, top, x1, bottom) in points, top-left origin."""

    page: int
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str | None, ...], ...] = field(repr=False)


@dataclass(frozen=True)
class PdfPage:
    number: int
    width: float
    height: float
    has_text: bool
    text: str = field(repr=False)
    tables: tuple[PdfTable, ...] = field(repr=False)
    ocr_text: str | None = field(default=None, repr=False)


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
            tables = []
            for table in page.find_tables():
                rows = table.extract()
                width = max((len(row) for row in rows), default=0)
                limits.check_table_size(rows=len(rows), columns=width)
                cells += len(rows) * width
                if cells > limits.max_cells:
                    raise _PdfRejected("LIMIT_EXCEEDED")
                for row in rows:
                    for cell in row:
                        if cell is not None:
                            limits.check_field(cell)
                            unmapped = unmapped or _UNMAPPED in cell
                x0, top, x1, bottom = table.bbox
                tables.append(
                    {"bbox": [float(x0), float(top), float(x1), float(bottom)], "rows": rows}
                )
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
            tables=tuple(
                PdfTable(
                    page=page["number"],
                    bbox=(table["bbox"][0], table["bbox"][1], table["bbox"][2], table["bbox"][3]),
                    rows=tuple(tuple(row) for row in table["rows"]),
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
