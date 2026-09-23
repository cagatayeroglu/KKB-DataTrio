"""`inspect`: look at a table without putting it in the prompt.

A loop that hands every result back in full pays for a sixty-row table in every
iteration after the one that made it, and a model that can only see what it was
handed cannot check its own work. So results travel by name and this tool is how
a name becomes something readable: the columns, the coverage, the count, and a
window of rows the caller asks for.

It is the tool the demo's second question needs. "Taşıt kredisi tutarlarına faiz
oranlarını ekle" only makes sense against a table whose months and cells are
still there, and the only way to know they are is to look.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus, analytical
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import AnalyticalResult

#: Rows one call may return. A window, not a dump: ask again with a new offset.
MAX_ROWS = 60
#: The longest piece of one line shown as a single row; a longer line is cut into parts.
MAX_SEGMENT_CHARS = 4_000
#: Text one window may carry, kept well below what one observation shows the model
#: (`trust_loop.MAX_OBSERVATION_CHARS`), so a window is never clipped on its way there.
MAX_WINDOW_CHARS = 24_000


class InspectArguments(BaseModel):
    """What to look at, and which part of it."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(
        min_length=1,
        max_length=64,
        description="The id of an earlier action, or the name of a published table",
    )
    columns: list[str] | None = Field(
        default=None,
        description="Only these column labels; omit for all of them",
    )
    offset: int = Field(default=0, ge=0, description="First row to return, oldest first")
    limit: int = Field(
        default=20, ge=1, le=MAX_ROWS, description=f"How many rows, at most {MAX_ROWS}"
    )
    page: int | None = Field(
        default=None, ge=1, description="A document read by page (a PDF): only this page"
    )
    table: int | None = Field(
        default=None,
        ge=1,
        description=(
            "A table of a document you read, by number: with page, the n-th table on that "
            "page; without, the n-th in the whole document"
        ),
    )


class InspectOutput(BaseModel):
    """What one look returned."""

    model_config = ConfigDict(extra="forbid")

    source: str
    kind: str
    columns: list[str]
    rows: int
    coverage: str | None = None
    offset: int
    values: list[dict[str, object]]
    #: True when more rows follow this window.
    more: bool
    #: The offset that continues from here, when more follows.
    next_offset: int | None = None


def _rows(result: AnalyticalResult, wanted: list[str] | None) -> list[dict[str, object]]:
    """One entry per period, with the asked-for columns beside it."""
    by_period: dict[str, dict[str, object]] = {}
    for value in result.values:
        if wanted is not None and value.label not in wanted:
            continue
        key = value.period.end.isoformat() if value.period is not None else ""
        row = by_period.setdefault(key, {"period": key})
        row[value.label] = value.value
    return [by_period[key] for key in sorted(by_period)]


def _passages(held: object) -> list[tuple[dict[str, object], str]] | None:
    """The text of something this turn read, each piece with where it came from.

    A page comes back inside a wrapper under `document.text`. A PDF does not: its
    text is per page, under `document.pages[*].text`, and a page with no text layer
    carries what OCR read under `ocr_text`. Reading only `document.text` refused
    every PDF as "not a table and not read text" (QA-13) — the document had been
    read, and the way back to it was closed. The page number travels with each
    piece, so a window says where in the document it is.
    """
    document = getattr(held, "document", None)
    pages = getattr(document, "pages", None)
    if isinstance(pages, tuple):
        found: list[tuple[dict[str, object], str]] = []
        for page in pages:
            number = getattr(page, "number", None)
            text = getattr(page, "text", None)
            if isinstance(text, str) and text:
                found.append(({"page": number}, text))
            ocr = getattr(page, "ocr_text", None)
            if isinstance(ocr, str) and ocr:
                found.append(({"page": number, "ocr": True}, ocr))
        return found or None
    text = getattr(document, "text", None) if document is not None else None
    if text is None:
        text = held if isinstance(held, str) else getattr(held, "text", None)
    return [({}, text)] if isinstance(text, str) and text else None


def _segments(passages: list[tuple[dict[str, object], str]]) -> list[dict[str, object]]:
    """Every line, and every line too long to show at once cut into ordered parts.

    A window counted only in lines has no way into a line longer than what one
    observation can carry: a 50,000-character line came back whole, was clipped
    again on the way to the model, and asking for it once more returned the same
    clip (QA-16). Cut into parts, each part is a row of its own, so the same
    offset/limit reaches the end of it. A short line is one row, as before.
    """
    rows: list[dict[str, object]] = []
    for where, text in passages:
        for number, line in enumerate(text.splitlines()):
            if len(line) <= MAX_SEGMENT_CHARS:
                rows.append({**where, "line": number, "text": line})
                continue
            parts = -(-len(line) // MAX_SEGMENT_CHARS)
            for part in range(parts):
                start = part * MAX_SEGMENT_CHARS
                rows.append(
                    {
                        **where,
                        "line": number,
                        "part": part + 1,
                        "parts": parts,
                        "chars_from": start,
                        "text": line[start : start + MAX_SEGMENT_CHARS],
                    }
                )
    return rows


def _window_of_text(
    arguments: InspectArguments, passages: list[tuple[dict[str, object], str]]
) -> ToolResult:
    """One window of a read text, with the row to continue from when more follows.

    The window stops at `limit` rows or at a character budget below what one
    observation carries, whichever comes first, and always returns at least one row:
    a window the model is shown clipped is a window it cannot continue from.

    The budget is measured on each row as it will be written to the model, not on its
    raw text. JSON escapes a quote or a backslash into two characters and a control
    character into six, so 24,000 raw characters of quotes became 48,000 on the wire,
    the observation was clipped, and `next_offset` was cut off with it (Codex QA,
    2026-09-23). Measured this way, even one segment of the worst case — 4,000 control
    characters, 24,000 escaped — stays below what an observation carries.
    """
    rows = _segments(passages)
    window: list[dict[str, object]] = []
    used = 0
    for row in rows[arguments.offset : arguments.offset + arguments.limit]:
        size = len(json.dumps(row, ensure_ascii=False, default=str))
        if window and used + size > MAX_WINDOW_CHARS:
            break
        window.append(row)
        used += size
    following = arguments.offset + len(window)
    return ToolResult(
        ToolStatus.SUCCESS,
        arguments.source,
        "inspect",
        output=InspectOutput(
            source=arguments.source,
            kind="text",
            columns=[],
            rows=len(rows),
            offset=arguments.offset,
            values=window,
            more=following < len(rows),
            next_offset=following if following < len(rows) else None,
        ),
    )


def _tables(held: object, page: int | None) -> list[tuple[dict[str, object], list[list[str]]]]:
    """The tables of a read document, in document order, each with where it is.

    A PDF keeps its tables per page; a web page numbers its own. Either way a table
    is rows of cells, and that is all a window needs.
    """
    document = getattr(held, "document", None)
    pages = getattr(document, "pages", None)
    found: list[tuple[dict[str, object], list[list[str]]]] = []
    if isinstance(pages, tuple):
        for sheet in pages:
            number = getattr(sheet, "number", None)
            if page is not None and number != page:
                continue
            for index, table in enumerate(getattr(sheet, "tables", ()), 1):
                rows = [["" if cell is None else str(cell) for cell in row] for row in table.rows]
                found.append(({"page": number, "table_on_page": index}, rows))
        return found
    if page is None:
        for table in getattr(document, "tables", None) or ():
            rows = [[str(cell) for cell in row] for row in table.rows]
            found.append(({"table": getattr(table, "number", None)}, rows))
    return found


def _pages(held: object) -> int:
    pages = getattr(getattr(held, "document", None), "pages", None)
    return len(pages) if isinstance(pages, tuple) else 0


def _window_of_table(
    arguments: InspectArguments, where: dict[str, object], rows: list[list[str]]
) -> ToolResult:
    """One window of a document's table: its rows, each with its cells."""
    window: list[dict[str, object]] = []
    used = 0
    for number, cells in enumerate(rows[arguments.offset : arguments.offset + arguments.limit]):
        row: dict[str, object] = {**where, "row": arguments.offset + number, "cells": cells}
        size = len(json.dumps(row, ensure_ascii=False, default=str))
        if window and used + size > MAX_WINDOW_CHARS:
            break
        window.append(row)
        used += size
    following = arguments.offset + len(window)
    return ToolResult(
        ToolStatus.SUCCESS,
        arguments.source,
        "inspect",
        output=InspectOutput(
            source=arguments.source,
            kind="document_table",
            columns=[],
            rows=len(rows),
            offset=arguments.offset,
            values=window,
            more=following < len(rows),
            next_offset=following if following < len(rows) else None,
        ),
    )


def _missing(arguments: InspectArguments, what: str) -> ToolResult:
    return ToolResult(
        ToolStatus.FAILURE,
        arguments.source,
        "inspect",
        error_category="table_reference",
        warnings=(what,),
    )


def _document_part(arguments: InspectArguments, held: object) -> ToolResult | None:
    """A page or a table of a read document, when one was asked for."""
    if arguments.table is not None:
        tables = _tables(held, arguments.page)
        if arguments.table > len(tables):
            scope = f"{arguments.page}. sayfada" if arguments.page is not None else "belgede"
            return _missing(
                arguments,
                f"{arguments.source!r} {scope} {len(tables)} tablo var; "
                f"{arguments.table}. tablo yok.",
            )
        located, rows = tables[arguments.table - 1]
        return _window_of_table(arguments, located, rows)
    if arguments.page is not None:
        passages = [
            (where, text)
            for where, text in (_passages(held) or [])
            if where.get("page") == arguments.page
        ]
        if not passages:
            return _missing(
                arguments,
                f"{arguments.source!r} içinde {arguments.page}. sayfa yok ya da metni yok; "
                f"belge {_pages(held)} sayfa.",
            )
        return _window_of_text(arguments, passages)
    return None


def make_inspect_tool() -> ToolSpec:
    """Bind the tool. It reads what the turn already has and fetches nothing."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(arguments, InspectArguments):  # pragma: no cover - contract
            raise TypeError("inspect received arguments it did not declare")
        held = context.outputs.get(arguments.source)
        found = analytical(held)
        if found is None:
            # A page or a table of a document, asked for by number (QA-23): a long
            # PDF reaches the model as an index, and this is how any part of it is read.
            if (part := _document_part(arguments, held)) is not None:
                return part
            if (passages := _passages(held)) is not None:
                return _window_of_text(arguments, passages)
            known = ", ".join(sorted(context.outputs)) or "yok"
            return ToolResult(
                ToolStatus.FAILURE,
                arguments.source,
                "inspect",
                error_category="table_reference",
                warnings=(
                    f"{arguments.source!r} ne bir tablo ne de okunmuş bir metin. "
                    f"Elde olanlar: {known}",
                ),
            )
        rows = _rows(found, arguments.columns)
        window = rows[arguments.offset : arguments.offset + arguments.limit]
        labels = list(dict.fromkeys(value.label for value in found.values))
        return ToolResult(
            ToolStatus.SUCCESS,
            arguments.source,
            "inspect",
            output=InspectOutput(
                source=arguments.source,
                kind=found.kind.value,
                columns=labels,
                rows=len(rows),
                coverage=(
                    f"{found.coverage.start}..{found.coverage.end}"
                    if found.coverage is not None
                    else None
                ),
                offset=arguments.offset,
                values=window,
                more=arguments.offset + len(window) < len(rows),
                next_offset=(
                    arguments.offset + len(window)
                    if arguments.offset + len(window) < len(rows)
                    else None
                ),
            ),
        )

    return ToolSpec(
        name="inspect",
        description=(
            "Look at something you already have. For a table: its columns, how many "
            "periods it covers, and a window of its rows. For a page or a document you "
            "read (a PDF by page): a window of its lines, a very long line cut into "
            "numbered parts; page=N reads one page, table=J (with page=N, the J-th table "
            "on that page) reads one of its tables row by row. This is how you read the "
            "rest of anything that came back clipped. Give source=<an action id or a "
            "published table name>, optionally columns, page, table, offset and limit. "
            "Nothing is fetched and nothing is changed; continue with offset=next_offset "
            "while more is true."
        ),
        arguments=InspectArguments,
        run=run,
    )


#: What a read document holds, by the same reading `inspect` gives it: its text piece by
#: piece and its tables, each with where it is. The answer's quotation check reads these.
document_passages = _passages
document_tables = _tables

__all__ = [
    "InspectArguments",
    "InspectOutput",
    "MAX_ROWS",
    "document_passages",
    "document_tables",
    "make_inspect_tool",
]
