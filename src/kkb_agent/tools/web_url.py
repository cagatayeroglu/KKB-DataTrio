"""The `web_url` tool: a file at an address the user wrote (M7-17/09/18, DEC-121).

On the demo day the organizer puts URLs inside the question (DEC-131). This
reads CSV and XLSX tables and the text and ruled tables of a PDF with a text
layer; optional injected OCR returns untrusted text for scanned pages. Static
HTML returns bounded text and rectangular tables. Image addresses remain unsupported; their
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
   destinations only, DNS bound to the socket, bounded bytes and time, and
   bounded redirects with fresh validation/binding at every hop; no TLS downgrade.
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
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import AnalyticalResult, SourceRef
from kkb_agent.csv_loader import CsvLoadResult, CsvTable
from kkb_agent.html_loader import HtmlDocument, HtmlLoadResult
from kkb_agent.ingest.attached import Attachment
from kkb_agent.ingest.fetched import (
    DOCUMENT_MEDIA_TYPES,
    fetched_source,
    load_document,
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
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.pdf_loader import PdfDocument, PdfLoadResult
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.tools._document_column import ColumnRefused
from kkb_agent.tools._document_table import (
    MAX_VALUE_COLUMNS,
    read_table,
    table_result,
    table_snapshot,
)
from kkb_agent.tools._document_value import (
    ValueNotSelected,
    as_of,
    csv_parsing,
    document_value,
    grids,
    read_cell,
    record_cell,
    select_cell,
    year_in_question,
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

    url: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        pattern=r"^https?://\S+$",
        description="The address exactly as the user wrote it in the question",
    )
    attached: bool = Field(
        default=False,
        description="true to read the document the user uploaded with this question instead",
    )
    delimiter: Literal[",", ";", "\t", "|"] | None = Field(
        default=None,
        description=(
            "Column separator of a CSV file, only when the user states it; otherwise it is "
            "detected from the file. Ignored for other formats"
        ),
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

    year: int | None = Field(
        default=None,
        ge=1900,
        le=2100,
        description=(
            "Only when the user wrote a year and the document's month labels may carry none "
            "(such as 'Ocak'): that year. A year the document states itself takes precedence "
            "and a different one is refused"
        ),
    )
    period_column: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description=(
            "To build a monthly table: the header of the column holding the months, as the "
            "user named it. Needs value_columns."
        ),
    )
    value_columns: list[Annotated[str, StringConstraints(min_length=1, max_length=256)]] | None = (
        Field(
            default=None,
            min_length=1,
            max_length=MAX_VALUE_COLUMNS,
            description=(
                "With period_column: the headers of up to six value columns, as the user named "
                "them; each becomes a table column labelled by that name"
            ),
        )
    )

    @model_validator(mode="after")
    def _column_and_row_together(self) -> WebUrlArguments:
        if (self.url is None) == (not self.attached):
            raise ValueError("give either url or attached=true, not both or neither")
        if (self.period_column is None) != (self.value_columns is None):
            raise ValueError("period_column and value_columns build a table together")
        if self.period_column is not None and self.column is not None:
            raise ValueError("read one cell (column, row) or build a table, not both")
        if self.value_columns is not None and len(set(self.value_columns)) != len(
            self.value_columns
        ):
            raise ValueError("value_columns must name each column once")
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
    document: PdfDocument | HtmlDocument | None = field(default=None, repr=False)
    #: The selected cell as a result, when the planner named one (M7-18).
    result: AnalyticalResult | None = field(default=None, repr=False)


@dataclass(frozen=True)
class DocumentRead:
    """A loaded document, or the fixed tool category and codes for why there is none."""

    output: WebUrlOutput
    failure: str | None = None
    reasons: tuple[str, ...] = ()


def read_attachment(
    attachment: Attachment,
    *,
    delimiter: str | None = None,
    sheet: str | None = None,
    ocr: OcrProvider | None = None,
) -> DocumentRead:
    """An uploaded document through the same loaders; it was admitted when stored (M10-04)."""
    source = attachment.source
    try:
        loaded = load_document(
            attachment.content,
            attachment.media_type,
            source=source,
            delimiter=delimiter,
            sheet=sheet,
            ocr=ocr,
        )
    except AdmissionError as error:
        return DocumentRead(
            WebUrlOutput("rejected", error.code.value, source, attachment.media_type),
            "not_admitted",
        )
    return _loaded(loaded, source, attachment.media_type)


def read_document(
    url: str,
    question: str,
    *,
    fetch: Fetcher,
    delimiter: str | None = None,
    sheet: str | None = None,
    ocr: OcrProvider | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DocumentRead:
    """The prompt-address boundary every document reader shares (M7-17, M7-14).

    `question` must be the user's own words: only an address written there is
    requested, through `fetch`, and the bytes meet the upload admission rules.
    A loaded result always carries its source; nothing is recorded here.
    """
    if url not in addresses_in(question):
        return DocumentRead(WebUrlOutput("rejected", "URL_NOT_IN_QUESTION"), "url_not_in_question")

    outcome = fetch(
        FetchRequest(
            source_ref=source_id_for(url),
            url=SecretStr(url),
            accepted_media_types=DOCUMENT_MEDIA_TYPES,
        )
    )
    if isinstance(outcome, FetchFailure):
        reason = () if outcome.target_reason is None else (outcome.target_reason.value,)
        return DocumentRead(WebUrlOutput("rejected", outcome.code.value), "fetch_failed", reason)
    if not isinstance(outcome, FetchSuccess):  # pragma: no cover - FetchOutcome is closed
        raise TypeError("fetch returned neither a success nor a failure")

    source = fetched_source(url, outcome.content, retrieved_at=clock())
    if outcome.effective_locator is not None:
        # Retain the authorized request identity and exact content hash, but
        # identify where these bytes were fetched, not the redirecting page.
        source = source.model_copy(update={"locator": outcome.effective_locator.get_secret_value()})
    try:
        loaded = load_fetched(outcome, source=source, delimiter=delimiter, sheet=sheet, ocr=ocr)
    except AdmissionError as error:
        return DocumentRead(
            WebUrlOutput("rejected", error.code.value, source, outcome.media_type), "not_admitted"
        )

    return _loaded(loaded, source, outcome.media_type)


def _loaded(
    loaded: CsvLoadResult | XlsxLoadResult | PdfLoadResult | HtmlLoadResult,
    source: SourceRef,
    media_type: str,
) -> DocumentRead:
    if isinstance(loaded, (PdfLoadResult, HtmlLoadResult)):
        output = WebUrlOutput(
            loaded.status, loaded.code, source, media_type, document=loaded.document
        )
    else:
        output = WebUrlOutput(
            loaded.status,
            loaded.code,
            source,
            media_type,
            loaded.sheets if isinstance(loaded, XlsxLoadResult) else (),
            loaded.table,
        )
    if loaded.status == "needs_input":
        return DocumentRead(output, "needs_input")
    if loaded.status == "rejected":
        return DocumentRead(output, "not_admitted")
    return DocumentRead(output)


def make_web_url_tool(
    *,
    fetch: Fetcher | None = safe_fetch,
    attachment: Attachment | None = None,
    lineage: Lineage | None = None,
    ocr: OcrProvider | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ToolSpec:
    """Bind the tool to a fetch boundary: the real `safe_fetch` unless a test substitutes it.

    `fetch=None` reads no address at all; `attachment` is the one document the
    user uploaded with this question (M10-04), if any.
    """

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, WebUrlArguments):  # pragma: no cover
            raise TypeError("web_url received arguments it did not declare")
        if arguments.year is not None and not year_in_question(arguments.year, context.question):
            # Like the address, a year is the user's word, never the model's (DEC-148).
            return _failed("needs_input", WebUrlOutput("needs_input", "YEAR_NOT_IN_QUESTION"))
        if arguments.attached:
            if attachment is None:
                return _failed("no_attachment", WebUrlOutput("rejected", "NO_ATTACHMENT"))
            read = read_attachment(
                attachment, delimiter=arguments.delimiter, sheet=arguments.sheet, ocr=ocr
            )
        elif fetch is None or arguments.url is None:
            return _failed("fetch_failed", WebUrlOutput("rejected", "NETWORK_DISABLED"))
        else:
            read = read_document(
                arguments.url,
                context.question,
                fetch=fetch,
                delimiter=arguments.delimiter,
                sheet=arguments.sheet,
                ocr=ocr,
                clock=clock,
            )
        if read.failure is not None:
            return _failed(read.failure, read.output, extra=read.reasons)
        output = read.output
        source, media_type = output.source, output.media_type
        if source is None or media_type is None:  # pragma: no cover - loaded reads carry both
            raise TypeError("a loaded document has no recorded source")
        warnings = output.document.warnings if output.document is not None else ()
        if arguments.period_column is not None and arguments.value_columns is not None:
            if lineage is None:
                return _failed(
                    "needs_input", replace(output, status="needs_input", code="NO_LINEAGE")
                )
            connection = lineage.connection
            try:
                table = read_table(
                    grids(output.table, output.document),
                    arguments.period_column,
                    arguments.value_columns,
                    is_series=lambda label: (
                        connection.execute(
                            "SELECT 1 FROM silver_series WHERE series_id = ? LIMIT 1", [label]
                        ).fetchone()
                        is not None
                    ),
                    year=arguments.year,
                    as_of=as_of(source),
                )
            except ColumnRefused as error:
                return _failed(
                    "needs_input", replace(output, status="needs_input", code=error.code)
                )
            source_node = _record(lineage, source, media_type)
            recorded = arguments.model_dump(mode="json", exclude={"url"})
            recorded["document_source_id"] = source.source_id
            result = _record_execution(
                connection,
                producer="web_url",
                arguments=canonical(recorded),
                inputs=[table_snapshot(table, source, media_type, csv=csv_parsing(output.table))],
                result=table_result(
                    table, source, source_node=source_node, csv=csv_parsing(output.table)
                ),
            )
            return ToolResult(
                ToolStatus.SUCCESS,
                step_id="",
                tool="web_url",
                output=replace(output, result=result),
                warnings=(*warnings, *result.warnings),
                evidence=source_node,
            )
        if arguments.column is None or arguments.row is None:
            return ToolResult(
                ToolStatus.SUCCESS,
                step_id="",
                tool="web_url",
                output=output,
                warnings=warnings,
                evidence=_record(lineage, source, media_type),
            )

        # Everything that can refuse runs before anything is recorded.
        try:
            cell = select_cell(
                grids(output.table, output.document),
                arguments.column,
                arguments.row,
                year=arguments.year,
            )
            reading = read_cell(cell, as_of=as_of(source))
        except ValueNotSelected as error:
            return _failed("needs_input", replace(output, status="needs_input", code=error.code))
        source_node = _record(lineage, source, media_type)
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
            "Read CSV/XLSX tables, PDF text/ruled tables, or static HTML text/tables from a "
            "web address the user wrote in the question. Pass the address exactly as "
            "written; any other address is refused. PDF tables may be ruled or set out with "
            "text alone. A CSV's column separator is detected "
            "from the file: give delimiter only when the user states one, and a CSV whose "
            "separator cannot be detected needs it stated; a workbook with several sheets "
            "needs the sheet named. On its "
            "own it returns the content and where it came from, not an answer. To "
            "answer with one figure, also give column (its header) and row (a label "
            "in that row, such as a date); the figure's unit and scale are only what "
            "the header states in parentheses, like '(Milyon TL)'. It computes "
            "nothing. OCR, when explicitly enabled by the operator, reads PDF pages without a "
            "text layer; its figures count only from a table whose columns add up to its "
            "total row, and other OCR text cannot answer a numeric question. HTML requires "
            "explicit "
            "rectangular tables; no JavaScript, CSS rendering or linked-resource "
            "fetching. Image addresses are not supported. To build a monthly table that later "
            "turns can use, give period_column and up to six value_columns instead of column and "
            "row: months must be explicit, one row per month, and each value header must state "
            "its unit in parentheses; a column that fails is left out with a warning."
            + (
                " The user uploaded a document with this question: read it with attached=true "
                "and no url."
                if attachment is not None
                else ""
            )
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
