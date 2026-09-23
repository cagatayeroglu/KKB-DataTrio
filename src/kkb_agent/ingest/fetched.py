"""M7-08: a downloaded file passes the same guards and loaders as an upload.

`safe_fetch` bounds the transfer; it says nothing about the bytes. Here they
meet the M1 admission checks and the bounded CSV/XLSX/PDF/HTML loaders exactly as an
uploaded file does, so there is one set of file rules rather than a weaker one
for whatever arrived over the network.

The loader is chosen by the response media type, which `safe_fetch` already
matched against the request, never by the URL: a link ending in `.csv` that
serves a workbook is a workbook, and HTML reaches only the static HTML parser.
The server's label is not trusted either — admission re-checks the
bytes, so a PDF sent as `text/csv` fails the content check rather than being
parsed. Generic types such as `application/octet-stream` are refused instead of
sniffed.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from kkb_agent.core import SourceRef
from kkb_agent.csv_loader import CsvLoadResult, load_csv
from kkb_agent.html_loader import HtmlLoadResult, load_html
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.ingest.url_targets import TargetRejection, validate_url_target
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    IMAGE_KINDS,
    IMAGE_MEDIA_TYPES,
    MIME_TYPES,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    RejectionCode,
)
from kkb_agent.pdf_loader import PdfLoadResult, load_pdf
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.xlsx_loader import XlsxLoadResult, load_xlsx

#: The media types this path can load, and so the only ones worth accepting.
TABLE_MEDIA_TYPES: tuple[str, ...] = (MIME_TYPES[FileKind.CSV], MIME_TYPES[FileKind.XLSX])
DOCUMENT_MEDIA_TYPES: tuple[str, ...] = (
    *TABLE_MEDIA_TYPES,
    MIME_TYPES[FileKind.PDF],
    MIME_TYPES[FileKind.HTML],
    # A picture at an address is read as a one-page scanned document (DEC-179).
    *IMAGE_MEDIA_TYPES,
)
#: A table served as plain text (QA-33): raw files on code hosts come as
#: `text/plain; charset=utf-8`, so a real CSV at such an address was refused before a
#: byte was read. Accepted from an address only - never as an upload's declared type -
#: and read only as a CSV that passes every CSV check with at least two columns.
TEXT_PLAIN = "text/plain"
#: What a request for a document at an address accepts, and for a table at one.
FETCHED_MEDIA_TYPES: tuple[str, ...] = (*DOCUMENT_MEDIA_TYPES, TEXT_PLAIN)
FETCHED_TABLE_MEDIA_TYPES: tuple[str, ...] = (*TABLE_MEDIA_TYPES, TEXT_PLAIN)
#: The refusal of plain text that is not a table: a page, prose or a single column.
PLAIN_TEXT_NOT_A_TABLE = "PLAIN_TEXT_NOT_A_TABLE"
_KINDS = {media_type: kind for kind, media_type in MIME_TYPES.items() if kind not in IMAGE_KINDS}
_IMAGE_KINDS = {"image/png": "png", "image/jpeg": "jpg"}

SOURCE_TYPE = "web_url"


def source_id_for(url: str) -> str:
    """An opaque, stable identity for an address; the address itself stays out."""
    return "web:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def fetched_source(url: str, content: bytes, *, retrieved_at: datetime) -> SourceRef:
    """Provenance for fetched bytes, with the locator's sensitive parts removed.

    The locator keeps scheme, canonical host and path, and drops the query and
    fragment, where signed links carry their tokens. The source ID is derived
    from the full address, so two queries remain two sources without either
    being recorded. The content hash identifies the exact bytes admitted. A
    token embedded in a path segment cannot be recognised and is kept.
    """
    target = validate_url_target(url)
    if isinstance(target, TargetRejection):
        # safe_fetch refuses such an address, so no bytes can legitimately
        # carry it; recording it as provenance would make it look fetchable.
        raise ValueError(f"No provenance for a refused address ({target.reason.value})")
    parts = urlsplit(target.url.get_secret_value())
    return SourceRef(
        source_id=source_id_for(url),
        source_type=SOURCE_TYPE,
        locator=urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", "")),
        retrieved_at=retrieved_at,
        content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
    )


def load_fetched(
    fetched: FetchSuccess,
    *,
    source: SourceRef,
    delimiter: str | None = None,
    sheet: str | None = None,
    limits: AdmissionLimits = DEFAULT_LIMITS,
    ocr: OcrProvider | None = None,
) -> CsvLoadResult | XlsxLoadResult | PdfLoadResult | HtmlLoadResult:
    """Admit and load fetched bytes through the upload path for their media type.

    The filename handed to admission is fixed by the media type, so nothing in
    the URL or a response header names or routes the file. `delimiter` applies
    only to CSV and `sheet` only to a workbook: each is a declaration about one
    format and is not consulted for the others. Everything else — byte, row,
    column, cell and page budgets, the terminated parser worker, explicit sheet
    selection, formula and macro rejection — is the loaders' own behaviour,
    unchanged; a CSV separator nobody declared is detected under DEC-147 (see
    `load_document`). Raises AdmissionError for a media type no loader reads,
    before any byte is parsed.
    """
    fetched = FetchSuccess.model_validate(fetched)
    return load_document(
        fetched.content,
        fetched.media_type,
        source=source,
        delimiter=delimiter,
        sheet=sheet,
        limits=limits,
        ocr=ocr,
    )


def load_document(
    content: bytes,
    media_type: str,
    *,
    source: SourceRef,
    delimiter: str | None = None,
    sheet: str | None = None,
    limits: AdmissionLimits = DEFAULT_LIMITS,
    ocr: OcrProvider | None = None,
) -> CsvLoadResult | XlsxLoadResult | PdfLoadResult | HtmlLoadResult:
    """Route document bytes to their loader by media type; fetched and uploaded bytes alike.

    Documents are read for a question whose author may not know a CSV's
    separator, and the planner never sees the bytes, so the CSV loader detects
    it (DEC-147): one separator the leading records allow is used, several or
    none still need a declaration, and a declaration contradicting the one
    detected separator is refused as DELIMITER_CONFLICT.
    """
    if media_type in _IMAGE_KINDS:
        from kkb_agent.image_document import image_to_pdf

        content = image_to_pdf(content, _IMAGE_KINDS[media_type], limits)
        media_type = MIME_TYPES[FileKind.PDF]
    if media_type == TEXT_PLAIN:
        return _plain_table(content, source=source, delimiter=delimiter, limits=limits)
    kind = _KINDS.get(media_type)
    if kind is None:
        raise AdmissionError(RejectionCode.UNSUPPORTED_FORMAT)
    stream = io.BytesIO(content)
    filename = f"download.{kind.value}"
    if kind is FileKind.HTML:
        return load_html(
            stream, filename=filename, content_type=media_type, source=source, limits=limits
        )
    if kind is FileKind.PDF:
        return load_pdf(
            stream,
            filename=filename,
            content_type=media_type,
            source=source,
            limits=limits,
            ocr=ocr,
        )
    if kind is FileKind.CSV:
        return load_csv(
            stream,
            filename=filename,
            content_type=media_type,
            source=source,
            delimiter=delimiter,
            detect_delimiter=True,
            limits=limits,
        )
    return load_xlsx(
        stream,
        filename=filename,
        content_type=media_type,
        source=source,
        selection=sheet,
        limits=limits,
    )


def _plain_table(
    content: bytes,
    *,
    source: SourceRef,
    delimiter: str | None,
    limits: AdmissionLimits,
) -> CsvLoadResult:
    """Plain text read as a CSV, and only ever as one (QA-33).

    The label says nothing about the bytes, so they earn the CSV reading: the same
    admission and strict CSV loader an upload meets (UTF-8, byte and cell budgets, one
    width for every record, no blank lines, at least two records), a page of markup is
    refused before it is parsed, and a single column - prose, a list - is not a table
    even when a separator was declared for it.
    """
    if content.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] == b"<":
        # An HTML or XML page, an error page among them, served as text.
        raise AdmissionError(RejectionCode.UNSUPPORTED_FORMAT)
    loaded = load_csv(
        io.BytesIO(content),
        filename="download.csv",
        content_type=MIME_TYPES[FileKind.CSV],
        source=source,
        delimiter=delimiter,
        detect_delimiter=True,
        limits=limits,
    )
    if loaded.status == "loaded" and (loaded.table is None or len(loaded.table.headers) < 2):
        return CsvLoadResult("rejected", source, PLAIN_TEXT_NOT_A_TABLE)
    return loaded


def kept_media_type(media_type: str, loaded: object) -> str:
    """The media type fetched bytes are kept under: plain text read as a table is a CSV.

    Plain text that did not load as a table keeps its own type, which no admission
    accepts, so it never becomes one of the conversation's documents.
    """
    if media_type == TEXT_PLAIN and isinstance(loaded, CsvLoadResult) and loaded.status == "loaded":
        return MIME_TYPES[FileKind.CSV]
    return media_type
