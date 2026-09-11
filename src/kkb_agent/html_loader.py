"""Bounded static HTML, not a browser. No navigation, CSS or script execution.

Explicitly closed, rectangular tables only: first row supplies nonempty unique
headers, later rows may use th as row labels. Spans and nested tables are
refused, never guessed. Text and cells remain untrusted literal source data.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import BinaryIO, Literal

from kkb_agent.core import SourceRef
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    admit_upload,
)

MAX_DEPTH = 64
MAX_TABLES = 20
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
IGNORE = frozenset("head script style noscript template form iframe object embed svg math".split())
BLOCK = frozenset("p div section article h1 h2 h3 h4 h5 h6 li br hr tr table".split())


@dataclass(frozen=True)
class HtmlTable:
    number: int
    rows: tuple[tuple[str, ...], ...] = field(repr=False)


@dataclass(frozen=True)
class HtmlDocument:
    source: SourceRef = field(repr=False)
    text: str = field(repr=False)
    tables: tuple[HtmlTable, ...] = field(repr=False)
    warnings: tuple[str, ...] = ("STATIC_HTML_ONLY",)
    # Stable source-local fragment: text:1; tables use their one-based number.
    text_fragment: str = "text:1"


@dataclass(frozen=True)
class HtmlLoadResult:
    status: Literal["loaded", "rejected"]
    source: SourceRef = field(repr=False)
    code: str | None = None
    document: HtmlDocument | None = field(default=None, repr=False)


class HtmlRejected(ValueError):
    """Fixed local code only."""


class StaticParser(HTMLParser):
    def __init__(self, limits: AdmissionLimits):
        super().__init__(convert_charrefs=True)
        self.limits = limits
        self.stack: list[tuple[str, bool]] = []
        self.text: list[str] = []
        self.text_size = 0
        self.tables: list[list[list[str]]] = []
        self.rows: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.cell_size = 0
        self.cells = 0
        self.seen_tag = False

    def fail(self, code="MALFORMED_DOCUMENT"):
        raise HtmlRejected(code)

    def add_text(self, text):
        self.text_size += len(text.encode("utf-8"))
        if self.text_size > self.limits.max_profile_bytes:
            self.fail("LIMIT_EXCEEDED")
        self.text.append(text)

    def add_cell(self, text):
        self.cell_size += len(text)
        if self.cell_size > self.limits.max_field_chars:
            self.fail("LIMIT_EXCEEDED")
        self.cell.append(text)

    def handle_starttag(self, tag, attrs):
        self.seen_tag = True
        attrs = dict(attrs)
        # A declaration never switches decoding away from strict UTF-8.
        if tag == "meta":
            charset = attrs.get("charset")
            if charset is None and (attrs.get("http-equiv") or "").lower() == "content-type":
                content = (attrs.get("content") or "").lower()
                if "charset=" in content:
                    charset = content.split("charset=", 1)[1].strip().strip("\"'")
            if charset is not None and charset.lower() not in ("utf-8", "utf8"):
                self.fail("UNSUPPORTED_ENCODING")
        hidden = "hidden" in attrs or (attrs.get("aria-hidden") or "").lower() == "true"
        styles = dict(
            (key.strip().lower(), value.strip().lower().removesuffix("!important").strip())
            for item in (attrs.get("style") or "").split(";")
            for key, sep, value in [item.partition(":")]
            if sep
        )
        hidden = (
            hidden
            or styles.get("display") == "none"
            or styles.get("visibility") in {"hidden", "collapse"}
        )
        if hidden and self.rows is not None:
            self.fail("UNSUPPORTED_TABLE")
        ignored = bool(self.stack and self.stack[-1][1]) or tag in IGNORE or hidden
        if tag not in VOID:
            if len(self.stack) >= MAX_DEPTH:
                self.fail("LIMIT_EXCEEDED")
            self.stack.append((tag, ignored))
        if ignored:
            return
        if tag in BLOCK:
            self.add_text("\n")
            if self.cell is not None:
                self.add_cell(" ")
        if tag == "table":
            if self.rows is not None:
                self.fail("UNSUPPORTED_TABLE")
            if len(self.tables) >= MAX_TABLES:
                self.fail("LIMIT_EXCEEDED")
            self.rows = []
        elif tag == "tr":
            if self.rows is None or self.row is not None:
                self.fail()
            self.row = []
            self.limits.check_table_size(rows=len(self.rows) + 1, columns=0)
        elif tag in ("td", "th"):
            if self.row is None or self.cell is not None:
                self.fail()
            if any(attrs.get(a, "1") != "1" for a in ("rowspan", "colspan")):
                self.fail("UNSUPPORTED_TABLE")
            self.limits.check_table_size(rows=1, columns=len(self.row) + 1)
            self.cells += 1
            if self.cells > self.limits.max_cells:
                self.fail("LIMIT_EXCEEDED")
            self.cell, self.cell_size = [], 0
        elif tag in ("thead", "tbody", "tfoot", "caption", "colgroup", "col") and self.rows is None:
            self.fail()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            self.fail()
        _, ignored = self.stack.pop()
        if ignored:
            return
        if tag in ("td", "th"):
            if self.cell is None or self.row is None:
                self.fail()
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
            self.add_text("\t")
        elif tag == "tr":
            if self.rows is None or not self.row or self.cell is not None:
                self.fail()
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            if not self.rows or self.row is not None:
                self.fail("UNSUPPORTED_TABLE")
            headers = self.rows[0]
            if (
                len(self.rows) < 2
                or not all(headers)
                or len(set(h.casefold() for h in headers)) != len(headers)
            ):
                self.fail("UNSUPPORTED_TABLE")
            if any(len(row) != len(headers) for row in self.rows):
                self.fail("UNSUPPORTED_TABLE")
            for header in headers:
                self.limits.check_field(header, label=True)
            self.tables.append(self.rows)
            self.rows = None
        if tag in BLOCK:
            self.add_text("\n")
            if self.cell is not None:
                self.add_cell(" ")

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        self.add_text(data)
        if self.cell is not None:
            self.add_cell(data)
        elif self.row is not None and data.strip():
            self.fail()

    def result(self):
        if self.stack or self.rows is not None:
            self.fail()
        text = "\n".join(
            " ".join(line.split()) for line in "".join(self.text).splitlines() if line.strip()
        )
        if not self.seen_tag:
            self.fail("FORMAT_MISMATCH")
        if not text:
            self.fail("NO_STATIC_CONTENT")
        return {"status": "loaded", "text": text, "tables": self.tables}


def _parse(content: bytes, limits: AdmissionLimits):
    parser = StaticParser(limits)
    text = content.decode("utf-8-sig")
    # Small feeds plus worker deadline bound pathological tokenizer work.
    for offset in range(0, len(text), 8192):
        parser.feed(text[offset : offset + 8192])
    parser.close()
    return parser.result()


def _worker(content, limits, output):
    try:
        if sys.platform == "linux":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        result = _parse(content, limits)
        data = json.dumps(result, ensure_ascii=True).encode()
        if len(data) > limits.max_expanded_bytes:
            raise HtmlRejected("LIMIT_EXCEEDED")
    except AdmissionError as error:
        data = json.dumps({"status": "rejected", "code": error.code.value}).encode()
    except HtmlRejected as error:
        data = json.dumps({"status": "rejected", "code": str(error)}).encode()
    except MemoryError:
        data = b'{"status":"rejected","code":"LIMIT_EXCEEDED"}'
    except Exception:
        data = b'{"status":"rejected","code":"PARSER_FAILED"}'
    with open(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(data)


def _run_worker(content, limits):
    with tempfile.TemporaryDirectory(prefix="kkb-html-") as directory:
        output = Path(directory) / "result.json"
        process = multiprocessing.get_context("spawn").Process(
            target=_worker, args=(content, limits, output)
        )
        deadline = time.monotonic() + limits.max_parser_seconds
        try:
            process.start()
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                return {"status": "rejected", "code": "LIMIT_EXCEEDED"}
            if process.exitcode != 0 or not output.is_file():
                return {"status": "rejected", "code": "PARSER_FAILED"}
            with output.open("rb") as stream:
                data = stream.read(max(1024, limits.max_expanded_bytes) + 1)
            if len(data) > max(1024, limits.max_expanded_bytes):
                return {"status": "rejected", "code": "LIMIT_EXCEEDED"}
            return json.loads(data)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(0.2)
                if process.is_alive():
                    process.kill()
                    process.join()
            process.close()


def load_html(
    stream: BinaryIO,
    *,
    filename: str,
    content_type: str,
    source: SourceRef,
    limits: AdmissionLimits = DEFAULT_LIMITS,
) -> HtmlLoadResult:
    source = SourceRef.model_validate(source)
    try:
        admitted = admit_upload(stream, filename=filename, content_type=content_type, limits=limits)
        if admitted.kind != FileKind.HTML:
            return HtmlLoadResult("rejected", source, "UNSUPPORTED_FORMAT")
        result = _run_worker(admitted.content, limits)
    except AdmissionError as error:
        return HtmlLoadResult("rejected", source, error.code.value)
    except OSError:
        return HtmlLoadResult("rejected", source, "PARSER_FAILED")
    if result["status"] != "loaded":
        return HtmlLoadResult("rejected", source, result["code"])
    tables = tuple(
        HtmlTable(i, tuple(tuple(row) for row in rows))
        for i, rows in enumerate(result["tables"], 1)
    )
    return HtmlLoadResult("loaded", source, document=HtmlDocument(source, result["text"], tables))
