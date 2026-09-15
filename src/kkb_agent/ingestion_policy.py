"""M1-02 admission guards; no table loader, profiler, or analytical engine."""

from __future__ import annotations

import io
import os
import stat
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import BinaryIO


class FileKind(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"
    HTML = "html"


class RejectionCode(StrEnum):
    INVALID_FILENAME = "INVALID_FILENAME"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FORMAT_MISMATCH = "FORMAT_MISMATCH"
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    EMPTY_INPUT = "EMPTY_INPUT"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    UNSAFE_ARCHIVE = "UNSAFE_ARCHIVE"
    READ_FAILED = "READ_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"


class AdmissionError(ValueError):
    """Only a fixed code escapes; never echo filenames, paths, or source cells."""

    def __init__(self, code: RejectionCode):
        self.code = code
        super().__init__(code.value)

    def profile_failure(self, source_ref: str) -> dict[str, object]:
        """Map failure to M1-01 using a caller-owned, opaque source reference."""
        return {
            "status": "rejected",
            "data_ref": None,
            "source_ref": source_ref,
            "selection": None,
            "row_count": None,
            "columns": [],
            "unresolved_semantics": [],
            "diagnostics": [{"code": self.code.value}],
            "diagnostics_truncated": False,
        }


@dataclass(frozen=True)
class AdmissionLimits:
    """Operator-configured local budgets, not organizer/platform guarantees."""

    max_bytes: int = 10 * 1024 * 1024
    max_rows: int = 100_000
    max_columns: int = 256
    max_cells: int = 1_000_000
    max_field_chars: int = 65_536
    max_label_chars: int = 256
    max_profile_bytes: int = 1024 * 1024
    max_sheets: int = 20
    max_archive_entries: int = 1024
    max_expanded_bytes: int = 50 * 1024 * 1024
    max_compression_ratio: int = 100
    max_parser_seconds: int = 5
    #: PDF layout analysis is slower per byte than a spreadsheet, so it has its
    #: own page cap and deadline rather than stretching the shared one.
    max_pdf_pages: int = 30
    max_pdf_parser_seconds: int = 10

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) is not int or value <= 0:
                raise ValueError("Admission limits must be positive integers")

    def check_table_size(self, *, rows: int, columns: int) -> None:
        """Loaders must call incrementally, before allocating beyond these caps."""
        if any(type(value) is not int or value < 0 for value in (rows, columns)):
            raise ValueError("Table dimensions must be nonnegative integers")
        if rows > self.max_rows or columns > self.max_columns or rows * columns > self.max_cells:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)

    def check_field(self, value: str, *, label: bool = False) -> None:
        if len(value) > (self.max_label_chars if label else self.max_field_chars):
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)

    def check_profile_size(self, serialized: bytes) -> None:
        if len(serialized) > self.max_profile_bytes:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)


DEFAULT_LIMITS = AdmissionLimits()
MIME_TYPES = {
    FileKind.CSV: "text/csv",
    FileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileKind.PDF: "application/pdf",
    FileKind.HTML: "text/html",
}


@dataclass(frozen=True)
class AdmittedFile:
    kind: FileKind
    content: bytes = field(repr=False)


def _metadata_kind(filename: str, content_type: str) -> FileKind:
    if (
        not filename
        or filename != filename.strip()
        or len(filename) > 255
        or len(filename.encode("utf-8", errors="replace")) > 255
        or any(char in filename for char in "/\\:")
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        raise AdmissionError(RejectionCode.INVALID_FILENAME)
    suffix = PurePosixPath(filename).suffix.lower().removeprefix(".")
    try:
        kind = FileKind(suffix)
    except ValueError:
        raise AdmissionError(RejectionCode.UNSUPPORTED_FORMAT) from None
    if len(content_type) > 200:
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    parts = content_type.lower().split(";")
    if parts[0].strip() != MIME_TYPES[kind]:
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    for parameter in parts[1:]:
        key, separator, value = parameter.strip().partition("=")
        if (
            kind not in (FileKind.CSV, FileKind.HTML)
            or key.strip() != "charset"
            or not separator
            or value.strip().strip('"') not in {"utf-8", "utf8"}
        ):
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    return kind


def _bounded_read(stream: BinaryIO, limit: int) -> bytes:
    content = bytearray()
    while True:
        try:
            chunk = stream.read(min(65_536, limit + 1 - len(content)))
        except OSError:
            raise AdmissionError(RejectionCode.READ_FAILED) from None
        if not isinstance(chunk, bytes):
            raise AdmissionError(RejectionCode.READ_FAILED)
        if len(content) + len(chunk) > limit:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        if not chunk:
            break
        content.extend(chunk)
    if not content:
        raise AdmissionError(RejectionCode.EMPTY_INPUT)
    return bytes(content)


def _check_csv_content(content: bytes) -> None:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AdmissionError(RejectionCode.UNSUPPORTED_ENCODING) from None
    if not text.strip():
        raise AdmissionError(RejectionCode.EMPTY_INPUT)
    if any(ord(char) < 32 and char not in "\t\r\n" or ord(char) == 127 for char in text):
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    if text.lstrip().lower().startswith(("<", "%pdf-", "pk\x03\x04")):
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    # CSV has no magic signature. Delimiter, header, width and cell interpretation
    # still require an explicit parsing declaration and the future bounded loader.


def _check_pdf_header(content: bytes) -> None:
    """A `%PDF-` header in the first 1024 bytes, where readers look for it.

    Only the signature is checked here. Objects, streams, encryption and pages
    are the bounded parser's to validate; nothing is decompressed or resolved.
    """
    if content.find(b"%PDF-", 0, 1024) < 0:
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)


def _check_xlsx_envelope(content: bytes, limits: AdmissionLimits) -> None:
    """Inspect bounded ZIP metadata only; never extract or execute workbook data."""
    if not content.startswith(b"PK\x03\x04"):
        raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > limits.max_archive_entries:
            raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        names: set[str] = set()
        expanded = 0
        sheets = 0
        for entry in entries:
            name = entry.filename
            parts = name.removesuffix("/").split("/")
            if (
                entry.orig_filename != name
                or len(name) > 1024
                or "\\" in name
                or ":" in name
                or any(part in {"", ".", ".."} for part in parts)
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.flag_bits & 1
                or name.casefold() in names
                or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            ):
                raise AdmissionError(RejectionCode.UNSAFE_ARCHIVE)
            names.add(name.casefold())
            if name.lower().endswith("vbaproject.bin") or name.lower().startswith(
                ("xl/externallinks/", "xl/embeddings/")
            ):
                raise AdmissionError(RejectionCode.UNSAFE_ARCHIVE)
            expanded += entry.file_size
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                sheets += 1
            if (
                expanded > limits.max_expanded_bytes
                or sheets > limits.max_sheets
                or entry.file_size > limits.max_compression_ratio * max(1, entry.compress_size)
            ):
                raise AdmissionError(RejectionCode.LIMIT_EXCEEDED)
        if not {"[content_types].xml", "_rels/.rels", "xl/workbook.xml"} <= names:
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
        if not sheets:
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH)


def admit_upload(
    stream: BinaryIO,
    *,
    filename: str,
    content_type: str,
    limits: AdmissionLimits = DEFAULT_LIMITS,
) -> AdmittedFile:
    """Check metadata before reading; read at most max_bytes + one sentinel byte."""
    kind = _metadata_kind(filename, content_type)
    content = _bounded_read(stream, limits.max_bytes)
    if kind == FileKind.CSV:
        _check_csv_content(content)
    elif kind == FileKind.HTML:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise AdmissionError(RejectionCode.UNSUPPORTED_ENCODING) from None
        if not text.lstrip().startswith("<") or any(
            ord(c) < 32 and c not in "\t\r\n" or ord(c) == 127 for c in text
        ):
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH)
    elif kind == FileKind.PDF:
        _check_pdf_header(content)
    else:
        try:
            _check_xlsx_envelope(content, limits)
        except AdmissionError:
            raise
        except (zipfile.BadZipFile, OSError, ValueError):
            raise AdmissionError(RejectionCode.FORMAT_MISMATCH) from None
    return AdmittedFile(kind, content)


@contextmanager
def staged_upload(
    stream: BinaryIO,
    *,
    filename: str,
    content_type: str,
    storage_root: Path,
    limits: AdmissionLimits = DEFAULT_LIMITS,
) -> Iterator[Path]:
    """Stage inside an existing operator-owned root; delete on success or failure.

    The root must not be selected by uploaded metadata or model output. This is
    transient staging, not permission to retain organizer/private data.
    """
    admitted = admit_upload(stream, filename=filename, content_type=content_type, limits=limits)
    try:
        if storage_root.is_symlink() or not storage_root.is_dir():
            raise AdmissionError(RejectionCode.STORAGE_FAILED)
        root = storage_root.resolve(strict=True)
        directory = tempfile.TemporaryDirectory(prefix="upload-", dir=root)
    except OSError:
        raise AdmissionError(RejectionCode.STORAGE_FAILED) from None
    try:
        destination = Path(directory.name) / f"input.{admitted.kind.value}"
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                output = os.fdopen(descriptor, "wb")
            except OSError:
                os.close(descriptor)
                raise
            with output:
                output.write(admitted.content)
        except OSError:
            raise AdmissionError(RejectionCode.STORAGE_FAILED) from None
        yield destination
    finally:
        try:
            directory.cleanup()
        except OSError:
            raise AdmissionError(RejectionCode.STORAGE_FAILED) from None
