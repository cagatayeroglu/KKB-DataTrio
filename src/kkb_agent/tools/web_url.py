"""The `web_url` tool: a file at an address the user wrote (M7-17/09/18, DEC-121).

On the demo day the organizer puts URLs inside the question (DEC-131). This
reads CSV and XLSX tables and the text and ruled tables of a PDF with a text
layer; HTML, images and scanned PDFs are later M7 work, and until then their
media types are refused before a body is read or their content is refused
with a fixed code.

Three rules carry the security weight, and each is enforced here rather than
asked of the model:

1. **Only an address the user wrote.** The URL argument must be one of the
   addresses in the question, character for character. A link inside a
   fetched document, or one a model decides would be useful, cannot become a
   request — so a cell saying "now fetch https://attacker/?data=..." has
   nowhere to send anything. The check reads `ExecutionContext.question`,
   which `Session` fills with the user's own words; a caller building its own
   context must do the same, never pass a plan's restated question.
2. **One fetch boundary.** Every request goes through `safe_fetch`: public
   destinations only, DNS bound to the socket, bounded bytes and time, and no
   redirect followed.
3. **Upload rules for downloaded bytes.** The response goes through M7-08's
   `load_fetched`, the same admission checks and bounded loaders an uploaded
   file meets.

What comes back is a table or a document. It becomes an answer only when the
planner names one cell by its column header and row label (M7-18): then the
output also carries a `LEVEL` `AnalyticalResult` for that cell, which
`collect_results` finds and the answer gate binds like any other result. The
unit, scale and period rules live in `_document_value`; without a selection
nothing is read out of the content. The content is not persisted; retention
permission is still an open question.

Registering the tool is the operator's switch: nothing registers it by
default while the organizer's URL policy (Q-NET-02) is unanswered.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import AnalyticalResult, SourceRef
from kkb_agent.csv_loader import CsvTable
from kkb_agent.ingest.fetched import (
    DOCUMENT_MEDIA_TYPES,
    fetched_source,
    load_fetched,
    source_id_for,
)
from kkb_agent.ingest.safe_fetch import (
    FetchFailure,
    FetchOutcome,
    FetchRequest,
    FetchSuccess,
    safe_fetch,
)
from kkb_agent.ingestion_policy import AdmissionError
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.pdf_loader import PdfDocument, PdfLoadResult
from kkb_agent.tools._document_value import (
    ValueNotSelected,
    document_value,
    grids,
    read_cell,
    record_cell,
    select_cell,
)
from kkb_agent.xlsx_loader import XlsxLoadResult, XlsxTable

type Fetcher = Callable[[FetchRequest], FetchOutcome]

#: An address as someone types it into a sentence. Quotes and apostrophes end
#: it, so a Turkish suffix ("...xlsx'teki") is not part of the address.
_ADDRESS = re.compile(r"https?://[^\s<>\"'`‘’“”«»]+")
_TRAILING = ".,;:!?"
_OPENING = {")": "(", "]": "[", "}": "{"}


def addresses_in(text: str) -> tuple[str, ...]:
    """Every http(s) address in `text`, as written, without sentence punctuation.

    A closing bracket is dropped only when the address does not open it, so a
    wiki-style path ending in ")" survives while a parenthesised link does not
    carry the parenthesis.
    """
    found: list[str] = []
    for match in _ADDRESS.finditer(text):
        address = match.group()
        while address:
            last = address[-1]
            if last in _TRAILING or (
                last in _OPENING and address.count(last) > address.count(_OPENING[last])
            ):
                address = address[:-1]
            else:
                break
        if not address.endswith("://"):  # punctuation was all there was
            found.append(address)
    return tuple(dict.fromkeys(found))


class WebUrlArguments(BaseModel):
    """What the planner may ask for: one address and how to read what it serves."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(
        min_length=1,
        max_length=4096,
        pattern=r"^https?://\S+$",
        description="The address exactly as the user wrote it in the question",
    )
    delimiter: Literal[",", ";", "\t", "|"] | None = Field(
        default=None,
        description="Column separator of a CSV file; required for CSV, ignored otherwise",
    )
    sheet: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Worksheet to read when a workbook has several; ignored otherwise",
    )
    column: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "To answer with one figure: the column header holding it, as the user "
            "named it; a unit in parentheses may be left out. Needs row."
        ),
    )
    row: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "With column: a label written in the same row, such as a date or a name, "
            "that picks out exactly one row"
        ),
    )

    @model_validator(mode="after")
    def _column_and_row_together(self) -> WebUrlArguments:
        if (self.column is None) != (self.row is None):
            raise ValueError("column and row name one cell together; give both or neither")
        return self


@dataclass(frozen=True)
class WebUrlOutput:
    """One loaded table or PDF document, or the fixed reason there is none.

    `code` is a fixed category from this tool, `safe_fetch`, admission or a
    loader — never remote text. `source` exists once bytes were retrieved.
    Sheet names, page text and cells come from the document and are data,
    which is why they stay out of the repr and out of every warning; a PDF's
    own `warnings` are fixed codes.
    """

    status: Literal["loaded", "needs_input", "rejected"]
    code: str | None = None
    source: SourceRef | None = field(default=None, repr=False)
    media_type: str | None = None
    sheets: tuple[str, ...] = field(default=(), repr=False)
    table: CsvTable | XlsxTable | None = field(default=None, repr=False)
    document: PdfDocument | None = field(default=None, repr=False)
    #: The selected cell as a result, when the planner named one (M7-18).
    result: AnalyticalResult | None = field(default=None, repr=False)


def make_web_url_tool(
    *,
    fetch: Fetcher = safe_fetch,
    lineage: Lineage | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ToolSpec:
    """Bind the tool to a fetch boundary: the real `safe_fetch` unless a test substitutes it."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, WebUrlArguments):  # pragma: no cover
            raise TypeError("web_url received arguments it did not declare")
        if arguments.url not in addresses_in(context.question):
            return _failed("url_not_in_question", WebUrlOutput("rejected", "URL_NOT_IN_QUESTION"))

        outcome = fetch(
            FetchRequest(
                source_ref=source_id_for(arguments.url),
                url=SecretStr(arguments.url),
                accepted_media_types=DOCUMENT_MEDIA_TYPES,
            )
        )
        if isinstance(outcome, FetchFailure):
            reason = () if outcome.target_reason is None else (outcome.target_reason.value,)
            return _failed(
                "fetch_failed", WebUrlOutput("rejected", outcome.code.value), extra=reason
            )
        if not isinstance(outcome, FetchSuccess):  # pragma: no cover - FetchOutcome is closed
            raise TypeError("fetch returned neither a success nor a failure")

        source = fetched_source(arguments.url, outcome.content, retrieved_at=clock())
        try:
            loaded = load_fetched(
                outcome, source=source, delimiter=arguments.delimiter, sheet=arguments.sheet
            )
        except AdmissionError as error:
            return _failed(
                "not_admitted",
                WebUrlOutput("rejected", error.code.value, source, outcome.media_type),
            )

        if isinstance(loaded, PdfLoadResult):
            output = WebUrlOutput(
                loaded.status, loaded.code, source, outcome.media_type, document=loaded.document
            )
        else:
            output = WebUrlOutput(
                loaded.status,
                loaded.code,
                source,
                outcome.media_type,
                loaded.sheets if isinstance(loaded, XlsxLoadResult) else (),
                loaded.table,
            )
        if loaded.status == "needs_input":
            return _failed("needs_input", output)
        if loaded.status == "rejected":
            return _failed("not_admitted", output)
        warnings = output.document.warnings if output.document is not None else ()
        if arguments.column is None or arguments.row is None:
            return ToolResult(
                ToolStatus.SUCCESS,
                step_id="",
                tool="web_url",
                output=output,
                warnings=warnings,
                evidence=_record(lineage, source, outcome.media_type),
            )

        # Everything that can refuse runs before anything is recorded.
        try:
            cell = select_cell(
                grids(output.table, output.document), arguments.column, arguments.row
            )
            reading = read_cell(cell)
        except ValueNotSelected as error:
            return _failed("needs_input", replace(output, status="needs_input", code=error.code))
        source_node = _record(lineage, source, outcome.media_type)
        cell_node = (
            record_cell(lineage, source_node, cell)
            if lineage is not None and source_node is not None
            else None
        )
        result = document_value(
            cell,
            reading,
            source=source,
            label=f"{arguments.column} | {arguments.row}",
            source_node=source_node,
            cell_node=cell_node,
        )
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="web_url",
            output=replace(output, result=result),
            warnings=warnings,
            evidence=cell_node or source_node,
        )

    return ToolSpec(
        name="web_url",
        description=(
            "Read a CSV or XLSX table, or the text and ruled tables of a PDF, from a "
            "web address the user wrote in the question. Pass the address exactly as "
            "written; any other address is refused. A CSV needs its column separator "
            "declared; a workbook with several sheets needs the sheet named. On its "
            "own it returns the content and where it came from, not an answer. To "
            "answer with one figure, also give column (its header) and row (a label "
            "in that row, such as a date); the figure's unit and scale are only what "
            "the header states in parentheses, like '(Milyon TL)'. It computes "
            "nothing. Scanned PDFs, HTML and image addresses are not supported yet."
        ),
        arguments=WebUrlArguments,
        run=run,
    )


def _failed(category: str, output: WebUrlOutput, *, extra: tuple[str, ...] = ()) -> ToolResult:
    """A refusal that names its fixed code and nothing from the document or URL."""
    return ToolResult(
        ToolStatus.FAILURE,
        step_id="",
        tool="web_url",
        output=output,
        error_category=category,
        warnings=tuple(code for code in (output.code, *extra) if code is not None),
    )


def _record(lineage: Lineage | None, source: SourceRef, media_type: str) -> str | None:
    """The fetched document as a source-file node; its bytes are not stored."""
    if lineage is None:
        return None
    return lineage.record(
        NodeKind.SOURCE_FILE,
        source.source_id,
        attributes={
            "source_type": source.source_type,
            "locator": source.locator,
            "content_hash": source.content_hash or "",
            "media_type": media_type,
        },
    )
