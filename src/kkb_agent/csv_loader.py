"""M1-06 bounded CSV loading, without profiling, conversion or source adapters.

The caller supplies a timeout-controlled binary stream and controlled SourceRef.
Delimiter selection is explicit unless the caller opts into DEC-147 detection;
encoding is always strict UTF-8 (BOM accepted). Only successful tables receive
an opaque reference. Persistence is caller-owned.
"""

from __future__ import annotations

import codecs
import csv
import io
import json
import multiprocessing
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Literal
from uuid import uuid4

from kkb_agent.core import DataContract, SourceRef
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    admit_upload,
)

#: The only separators a declaration may name or detection may choose.
DELIMITERS: tuple[str, ...] = (",", ";", "\t", "|")
#: DEC-147 detection reads at most this many leading characters of the text.
DETECTION_PREFIX_CHARS = 65_536

type DelimiterSource = Literal["declared", "detected"]


@dataclass(frozen=True)
class CsvTable:
    data_ref: str
    contract: DataContract = field(repr=False)
    delimiter: str
    encoding: Literal["utf-8", "utf-8-sig"]
    headers: tuple[str, ...] = field(repr=False)
    rows: tuple[tuple[str | None, ...], ...] = field(repr=False)
    delimiter_source: DelimiterSource = "declared"

    @property
    def column_ids(self) -> tuple[str, ...]:
        return tuple(f"c{i}" for i in range(len(self.headers)))

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class CsvLoadResult:
    """A loaded table is not yet an M1-01 profile or analytical approval."""

    status: Literal["loaded", "needs_input", "rejected"]
    source: SourceRef = field(repr=False)
    code: str | None = None
    table: CsvTable | None = field(default=None, repr=False)


class _CsvRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _CsvNeedsInput(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _check_structure(
    text: str, delimiter: str, limits: AdmissionLimits, *, partial: bool = False
) -> int:
    """Bound dimensions/fields BEFORE csv.reader allocates a record; return the width.

    Also reject bare quotes and text after a closing quote; csv.reader(strict=True)
    alone accepts quotes inside unquoted fields. No dialect repair occurs.
    CRLF, CR and LF terminate records outside quotes and stay literal inside quotes.

    `partial` checks a cut-off prefix: the unfinished last record (possibly inside
    quotes) is ignored, so every checked record is also a record of the full text.
    """
    state = "start"
    field_chars = 0
    columns = 1
    records = 0
    width = None
    record_start = 0
    skip_lf = False

    def finish_record(end: int) -> None:
        nonlocal records, width
        if end == record_start:
            raise _CsvRejected("MALFORMED_TABLE")  # Never silently skip blank lines.
        limits.check_table_size(rows=records, columns=columns)
        if width is not None and columns != width:
            raise _CsvRejected("MALFORMED_TABLE")
        width = columns
        records += 1

    for index, char in enumerate(text):
        if skip_lf and char == "\n":
            skip_lf = False
            record_start = index + 1
            continue
        skip_lf = False
        if state == "quoted":
            if char == '"':
                state = "closed"
            else:
                field_chars += 1
        elif state == "closed" and char == '"':
            state = "quoted"
            field_chars += 1  # Doubled quote represents one literal quote.
        elif char == delimiter:
            columns += 1
            limits.check_table_size(rows=records, columns=columns)
            state, field_chars = "start", 0
        elif char in "\r\n":
            finish_record(index)
            state, field_chars, columns = "start", 0, 1
            record_start = index + 1
            skip_lf = char == "\r"
        elif char == '"' and state == "start":
            state = "quoted"
        elif state == "closed" or char == '"':
            raise _CsvRejected("MALFORMED_TABLE")
        else:
            state = "unquoted"
            field_chars += 1
        cap = limits.max_label_chars if records == 0 else limits.max_field_chars
        if field_chars > cap:
            raise _CsvRejected("LIMIT_EXCEEDED")
    if not partial:
        if state == "quoted":
            raise _CsvRejected("MALFORMED_TABLE")
        if record_start < len(text):
            finish_record(len(text))
    if records < 2 or width is None:
        raise _CsvRejected("EMPTY_TABLE")
    return width


def _detect(text: str, limits: AdmissionLimits) -> str | None:
    """DEC-147: the one separator the leading records allow, or None.

    A separator is a candidate when the strict structure check passes on the
    leading records with the same width of at least two in each. The prefix is
    cut at an arbitrary character, but only records completed before the cut are
    checked, and those are exactly the first records of the full text under that
    separator. A separator refused on them is therefore refused on the whole
    text, so one candidate that also parses the whole text is its only reading.
    Too few complete records under any separator leaves the choice undecided.
    """
    partial = len(text) > DETECTION_PREFIX_CHARS
    prefix = text[:DETECTION_PREFIX_CHARS]
    candidates: list[str] = []
    for delimiter in DELIMITERS:
        try:
            width = _check_structure(prefix, delimiter, limits, partial=partial)
        except _CsvRejected as error:
            if partial and error.code == "EMPTY_TABLE":
                return None  # Not refused, merely unseen: no reading can be excluded.
            continue
        except AdmissionError:
            continue
        if width >= 2:
            candidates.append(delimiter)
    return candidates[0] if len(candidates) == 1 else None


def _parse(
    content: bytes, delimiter: str | None, limits: AdmissionLimits, detect: bool = False
) -> dict[str, object]:
    text = content.decode("utf-8-sig", errors="strict")
    source: DelimiterSource = "declared"
    if detect:
        detected = _detect(text, limits)
        if delimiter is None:
            if detected is None:
                raise _CsvNeedsInput("PARSING_DECLARATION_REQUIRED")
            delimiter, source = detected, "detected"
        elif detected is not None and detected != delimiter:
            raise _CsvNeedsInput("DELIMITER_CONFLICT")
    if delimiter is None:  # pragma: no cover - load_csv refuses this before the worker
        raise _CsvNeedsInput("PARSING_DECLARATION_REQUIRED")
    _check_structure(text, delimiter, limits)
    # Process-local setting: never changes a caller's csv module/global limit.
    csv.field_size_limit(max(limits.max_label_chars, limits.max_field_chars))
    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=delimiter,
        quotechar='"',
        doublequote=True,
        skipinitialspace=False,
        strict=True,
    )
    headers = next(reader)
    if not any(headers):
        raise _CsvRejected("MALFORMED_TABLE")
    rows: list[list[str | None]] = []
    for row in reader:
        limits.check_table_size(rows=len(rows) + 1, columns=len(row))
        rows.append([value if value != "" else None for value in row])
    loaded: dict[str, object] = {"status": "loaded", "headers": headers, "rows": rows}
    if source == "detected":
        loaded["detected"] = delimiter
    return loaded


def _write_result(output: Path, result: dict[str, object], limit: int) -> None:
    size = 0
    with open(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        for chunk in json.JSONEncoder(ensure_ascii=True).iterencode(result):
            data = chunk.encode("utf-8")
            size += len(data)
            if size > limit:
                raise _CsvRejected("LIMIT_EXCEEDED")
            stream.write(data)


def _worker(
    content: bytes,
    delimiter: str | None,
    limits: AdmissionLimits,
    output: Path,
    detect: bool = False,
) -> None:
    try:
        if sys.platform == "linux":
            import resource

            memory = max(512 * 1024 * 1024, limits.max_expanded_bytes * 8)
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        _write_result(output, _parse(content, delimiter, limits, detect), limits.max_expanded_bytes)
        return
    except _CsvNeedsInput as needs:
        output.unlink(missing_ok=True)
        _write_result(output, {"status": "needs_input", "code": needs.code}, 1024)
        return
    except (AdmissionError, _CsvRejected) as error:
        code = str(error.code)
    except (csv.Error, UnicodeError):
        code = "MALFORMED_TABLE"
    except MemoryError:
        code = "LIMIT_EXCEEDED"
    except Exception:
        code = "PARSER_FAILED"  # Never expose source bytes or library exception text.
    output.unlink(missing_ok=True)
    _write_result(output, {"status": "rejected", "code": code}, 1024)


def _run_worker(
    content: bytes, delimiter: str | None, limits: AdmissionLimits, detect: bool = False
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="kkb-csv-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(
            target=_worker,
            args=(content, delimiter, limits, output),
            kwargs={"detect": True} if detect else {},
        )
        deadline = time.monotonic() + limits.max_parser_seconds
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


def load_csv(
    stream: BinaryIO,
    *,
    filename: str,
    content_type: str,
    source: SourceRef,
    delimiter: str | None = None,
    detect_delimiter: bool = False,
    limits: AdmissionLimits = DEFAULT_LIMITS,
) -> CsvLoadResult:
    """Admit and parse one table under an explicit comma/semicolon/tab/pipe dialect.

    By default no delimiter selection yields needs_input/PARSING_DECLARATION_REQUIRED,
    even if a sample looks unambiguous. With `detect_delimiter` (DEC-147, the
    document path) the worker chooses the one separator the leading records
    allow; none or several still need a declaration, and a declaration that
    contradicts the one detected separator needs input as DELIMITER_CONFLICT.
    The table records which separator was used and whether it was declared or
    detected. No locale/encoding fallback or row repair.
    First record is header; duplicate/empty labels retain ordinal IDs. Empty data
    fields (quoted or unquoted) become None; whitespace, NA, dates, numbers and
    formula/code-looking strings stay literal. Missing rows are not dropped.

    Byte, row, column, cell, field and label caps reuse AdmissionLimits. Table JSON
    uses max_expanded_bytes (not the profile cap); no full profile is produced.
    A terminated/reaped spawn worker enforces max_parser_seconds including parse
    and serialization; Linux also caps address space. Input I/O timeout belongs
    to the caller. Spawn applications need the usual __main__ guard.
    """
    source = SourceRef.model_validate(source)
    if delimiter is not None and delimiter not in DELIMITERS:
        return CsvLoadResult("rejected", source, "UNSUPPORTED_DELIMITER")
    try:
        admitted = admit_upload(stream, filename=filename, content_type=content_type, limits=limits)
        if admitted.kind != FileKind.CSV:
            return CsvLoadResult("rejected", source, "UNSUPPORTED_FORMAT")
        if delimiter is None and not detect_delimiter:
            return CsvLoadResult("needs_input", source, "PARSING_DECLARATION_REQUIRED")
        result = _run_worker(admitted.content, delimiter, limits, detect_delimiter)
    except AdmissionError as error:
        return CsvLoadResult("rejected", source, error.code.value)
    except (OSError, ValueError):
        return CsvLoadResult("rejected", source, "PARSER_FAILED")
    if result["status"] == "needs_input":
        return CsvLoadResult("needs_input", source, result["code"])
    if result["status"] != "loaded":
        return CsvLoadResult("rejected", source, result["code"])
    detected = result.get("detected")
    used = detected if detected is not None else delimiter
    if used not in DELIMITERS:  # pragma: no cover - written by _worker above
        return CsvLoadResult("rejected", source, "PARSER_FAILED")
    data_ref = f"data:{uuid4().hex}"
    table = CsvTable(
        data_ref,
        DataContract(contract_id=data_ref, source=source, title="CSV table"),
        used,
        "utf-8-sig" if admitted.content.startswith(codecs.BOM_UTF8) else "utf-8",
        tuple(result["headers"]),
        tuple(tuple(row) for row in result["rows"]),
        "declared" if detected is None else "detected",
    )
    return CsvLoadResult("loaded", source, table=table)
