"""The `web_url` tool: a file at an address the user wrote (M7-17/09/18, DEC-121).

On the demo day the organizer puts URLs inside the question (DEC-131). This
reads CSV and XLSX tables and the text and ruled tables of a PDF with a text
layer; optional injected OCR returns untrusted text for scanned pages. Static
HTML returns bounded text and rectangular tables. Image addresses remain unsupported; their
media types are refused before a body is read or their content is refused
with a fixed code.

Three rules carry the security weight, and each is enforced here rather than
asked of the model:

1. **Explicit address authority.** A URL must come from the user's question or
   an actual search result in this turn. A fetched page delegates only its recorded
   same-origin links, at most one hop. `read_from` consumes that actual output;
   model-generated or unrelated addresses never acquire authority.
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
unit, scale and period rules live in `_document_value`; without a selection the
harness may inspect the document in a bounded continuation and show an explicitly
unverified reading. Operator-configured retention uses the existing admission boundary.

Registering the tool is the operator's switch: nothing registers it by
default while the organizer's URL policy (Q-NET-02) is unanswered.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator

from kkb_agent.agent.executor import (
    ExecutionContext,
    ExecutionOutcome,
    ToolResult,
    ToolStatus,
)
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.core import AnalyticalResult, Scale, SourceRef
from kkb_agent.csv_loader import CsvLoadResult, CsvTable
from kkb_agent.html_loader import HtmlDocument, HtmlLoadResult
from kkb_agent.ingest.attached import Attachment
from kkb_agent.ingest.bist_index_semantics import bist_index_close_metrics
from kkb_agent.ingest.fetched import (
    FETCHED_MEDIA_TYPES,
    PLAIN_TEXT_NOT_A_TABLE,
    fetched_source,
    kept_media_type,
    load_document,
    load_fetched,
    source_id_for,
)
from kkb_agent.ingest.json_table import MEDIA_TYPE as JSON_MEDIA_TYPE
from kkb_agent.ingest.json_table import JsonRejected, RecordTable, load_records
from kkb_agent.ingest.page_links import LinkRefused, PageLink, choose_link, page_links
from kkb_agent.ingest.safe_fetch import (
    FetchFailure,
    FetchOutcome,
    FetchRequest,
    FetchSuccess,
    safe_fetch,
)
from kkb_agent.ingest.script_navigation import ScriptedLinks, script_links
from kkb_agent.ingestion_policy import MIME_TYPES, AdmissionError, FileKind
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.pdf_loader import PdfDocument, PdfLoadResult
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.tools._document_column import ColumnRefused
from kkb_agent.tools._document_table import (
    MAX_VALUE_COLUMNS,
    daily_rule_in_question,
    read_daily_table,
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
    header_semantics,
    read_cell,
    record_cell,
    select_cell,
    year_in_question,
)
from kkb_agent.xlsx_loader import XlsxLoadResult, XlsxTable

type Fetcher = Callable[[FetchRequest], FetchOutcome]

#: A data endpoint as named in a page outline (see ingest.address_outline).
ENDPOINT_NAME = re.compile(r"endpoint_[0-9]{1,2}")

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
        description="true to read a document uploaded in this conversation instead of a url",
    )
    found_by: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=(
            "Instead of url: the step_id of a web_search step of this plan, to read one of "
            "the pages it found. Say which with `result` and list the step in depends_on. "
            "Use this rather than writing an address out of a search result: the address is "
            "taken from what the search returned, so it is the page that was found"
        ),
    )
    result: int = Field(
        default=1,
        ge=1,
        le=10,
        description="With found_by: which hit to read, 1 for the first the search returned",
    )
    follow: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "With url: the visible text or file name of a link on that page to read instead, "
            "such as 'Altın İşlemleri' or 'kmp_au.pdf'. Only a link on the same site is "
            "followed, one hop; the address itself always comes from the page"
        ),
    )
    read_from: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=(
            "With follow: the step_id of an already fetched web_url page. "
            "Follow only a link recorded in that page; declare it in depends_on. "
            "Not a way to look inside a document you already have: that is inspect."
        ),
    )
    document: str | None = Field(
        default=None,
        pattern=r"^belge_[0-9]{1,2}$",
        description=(
            "With attached=true: which uploaded document (belge_1, belge_2, ...). May be left "
            "out for the document attached to this question or the conversation's only one"
        ),
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
            "To build a table: the header of the column holding the periods, as the user "
            "named it. A column of months publishes monthly rows and a column of single "
            "days publishes daily rows, as the document dates them. Needs value_columns."
        ),
    )
    value_columns: list[Annotated[str, StringConstraints(min_length=1, max_length=256)]] | None = (
        Field(
            default=None,
            min_length=1,
            max_length=MAX_VALUE_COLUMNS,
            description=(
                "With period_column: the headers of up to twelve value columns, as the user named "
                "them; each becomes a table column labelled by that name"
            ),
        )
    )

    daily_to_monthly: Literal["last", "mean", "sum"] | None = Field(
        default=None,
        description=(
            "Only when the rows are days and the user asked for months: how each complete "
            "month is formed, in the user's own words ('ay sonu' -> last, 'ortalama' -> mean, "
            "'aylık toplam' -> sum). Left out, the days publish as daily rows"
        ),
    )
    column_units: (
        dict[
            Annotated[str, StringConstraints(min_length=1, max_length=256)],
            Annotated[str, StringConstraints(min_length=1, max_length=64)],
        ]
        | None
    ) = Field(
        default=None,
        max_length=MAX_VALUE_COLUMNS,
        description=(
            "Only when the user wrote a column's unit in the question and its header states "
            "none: value column name -> the unit exactly as the user wrote it, such as "
            "'bin TL' or 'adet'. A unit the header states always wins"
        ),
    )

    @model_validator(mode="after")
    def _column_and_row_together(self) -> WebUrlArguments:
        sources = sum(
            (
                self.url is not None,
                self.attached,
                self.found_by is not None,
                self.read_from is not None,
            )
        )
        if sources != 1:
            raise ValueError("give exactly one of url, attached=true, found_by or read_from")
        if self.read_from is not None and self.follow is None:
            # Said with the way that works: live 2026-09-23 the model sent eight of these,
            # one per month, to take cells from a PDF it had already read, and spent its
            # budget learning only that this was not how (QA-A3).
            raise ValueError(
                "read_from needs a follow target from the fetched page. To read a page, a "
                "table or rows of a document you already fetched, use inspect with "
                "source=<its id> (page=N, table=J); web_url fetches, it does not re-read"
            )
        if self.document is not None and not self.attached:
            raise ValueError("document names an upload; it needs attached=true")
        if self.follow is not None and self.attached:
            raise ValueError("follow names a link on a page, not in an uploaded document")
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
        if self.column_units is not None and not set(self.column_units) <= set(
            self.value_columns or ()
        ):
            raise ValueError("column_units names only value_columns")
        return self


def choose_document(
    document: str | None,
    current: Attachment | None,
    library: Mapping[str, Attachment],
) -> Attachment | str:
    """The uploaded document a step reads, or a fixed code; never a guess.

    A named document must exist. Without a name, the document attached to this
    question is read; failing that, the conversation's only document. Several
    documents and no name is ambiguous.
    """
    if document is not None:
        return library.get(document) or "DOCUMENT_UNKNOWN"
    if current is not None:
        return current
    if len(library) == 1:
        return next(iter(library.values()))
    return "DOCUMENT_NOT_NAMED" if library else "NO_ATTACHMENT"


def library_name(chosen: Attachment, library: Mapping[str, Attachment]) -> str | None:
    """The conversation's name for a chosen document, matched by the hash of its bytes.

    Identity was enough while the library was a copy made at the start of the turn. A
    library read when a tool asks (QA-29) returns each document freshly re-read, so
    `is` never matched and a save of the question's attachment named no document. A
    conversation admits a given set of bytes once, so the hash names one document.
    """
    digest = chosen.source.content_hash
    return next(
        (
            label
            for label, item in library.items()
            if item is chosen or (digest is not None and item.source.content_hash == digest)
        ),
        None,
    )


def declared_units(
    column_units: dict[str, str] | None, question: str
) -> dict[str, tuple[str, Scale]] | str:
    """Units the user wrote for columns, or a fixed code; never the model's own words.

    Like an address or a year, a declared unit counts only when the question
    contains it, and only in the vocabulary a header unit uses.
    """
    found: dict[str, tuple[str, Scale]] = {}
    folded_question = f" {normalize_search_text(question)} "
    for label, text in (column_units or {}).items():
        folded = normalize_search_text(text)
        if not folded or f" {folded} " not in folded_question:
            return "UNIT_NOT_IN_QUESTION"
        unit, scale = header_semantics(f"({text})")
        if unit is None or scale is Scale.UNKNOWN:
            return "UNIT_NOT_RECOGNISED"
        found[label] = (unit, scale)
    return found


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
    table: CsvTable | XlsxTable | RecordTable | None = field(default=None, repr=False)
    document: PdfDocument | HtmlDocument | None = field(default=None, repr=False)
    #: The selected cell as a result, when the planner named one (M7-18).
    result: AnalyticalResult | None = field(default=None, repr=False)
    links: tuple[PageLink, ...] = field(default=(), repr=False)
    followed: bool = False
    #: With `followed`: the visible text (or file name) of the link that was followed and the
    #: page it sat on, scheme, host and path only. Live 2026-09-22 (N46): a reading of a
    #: followed press release said no link had needed following, because nothing it was
    #: shown said how the document was reached.
    followed_text: str | None = field(default=None, repr=False)
    followed_from: str | None = field(default=None, repr=False)
    #: Functions this page's markup calls with literal arguments whose target its
    #: same-origin script does not spell out statically (`ingest.script_navigation`).
    #: Said so, rather than guessed: nothing is evaluated.
    unresolved_navigation: tuple[str, ...] = ()
    #: Scripted targets read and then refused for leaving the page's authority.
    refused_navigation: int = 0
    #: The name the conversation now keeps this document under (belge_N), which every
    #: tool working on the conversation's documents takes. None when it was not kept.
    kept_as: str | None = None


def _link_name(link: PageLink) -> str:
    """What a link is called on its page: its visible text, else its file name."""
    return link.text or unquote(urlsplit(link.url).path.rsplit("/", 1)[-1])


def _page_locator(url: str) -> str:
    """Scheme, host and path of a page, without the query or fragment a token may sit in."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))


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


def _found_address(context: ExecutionContext, step_id: str, rank: int) -> str | None:
    """The address a web_search step of this plan returned at `rank`, or None.

    The planner names the hit, never the address: asked to read what a search found, it
    wrote a TCMB address from memory instead of the one the search had returned, and the
    read was refused as an address nobody had asked for (live 2026-09-22). A redacted
    locator is not offered, because it no longer names the page that was found.
    """
    output = context.outputs.get(step_id)
    hits = [
        candidate
        for candidate in (getattr(output, "candidates", ()) or ())
        if not getattr(candidate, "locator_redacted", True)
    ]
    return str(hits[rank - 1].url) if 0 < rank <= len(hits) else None


def _required_steps(arguments: BaseModel) -> tuple[str, ...]:
    """The earlier search or fetched page whose authority this read consumes."""
    if isinstance(arguments, WebUrlArguments) and arguments.read_from is not None:
        return (arguments.read_from,)
    if isinstance(arguments, WebUrlArguments) and arguments.found_by is not None:
        return (arguments.found_by,)
    return ()


def searched_addresses(source: ExecutionContext | ExecutionOutcome) -> frozenset[str]:
    """Addresses this turn's own web_search steps returned whole.

    Read from the context the executor filled (a search earlier in the same plan) or from
    a finished discovery outcome (a search in the round before this one). A redacted
    locator is left out: its query string was dropped for display, so it no longer names
    the resource the hit named.
    """
    if isinstance(source, ExecutionContext):
        found: set[str] = set(source.searched)
        outputs: list[object] = list(source.outputs.values())
    else:
        found = set()
        outputs = [item.output for item in source.results if item.status is ToolStatus.SUCCESS]
    for output in outputs:
        for candidate in getattr(output, "candidates", ()) or ():
            if not getattr(candidate, "locator_redacted", True):
                found.add(str(candidate.url))
    return frozenset(found)


def read_document(
    url: str,
    question: str,
    *,
    fetch: Fetcher,
    delimiter: str | None = None,
    sheet: str | None = None,
    ocr: OcrProvider | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    follow: str | None = None,
    endpoints: Mapping[str, str] | None = None,
    keep: Callable[[str, bytes, str], str | None] | None = None,
    searched: frozenset[str] = frozenset(),
    delegated: bool = False,
) -> DocumentRead:
    """The prompt-address boundary every document reader shares (M7-17, M7-14).

    `question` must be the user's own words: an address written there is requested,
    through `fetch`, and the bytes meet the upload admission rules. `searched` adds the
    addresses a web_search step of this same turn returned whole - the person asked for
    the search and for what it finds - and nothing else ever widens the set: a fetched
    page's own content cannot name the next request.
    With `follow`, that page is read for its links and the one same-site link
    matching the name is requested instead (see `ingest.page_links`); the
    address always comes from the page bytes, never from the planner.
    A loaded result always carries its source; nothing is recorded here.
    """
    if url not in set(addresses_in(question)) | searched:
        return DocumentRead(WebUrlOutput("rejected", "URL_NOT_IN_QUESTION"), "url_not_in_question")
    if follow is not None and ENDPOINT_NAME.fullmatch(follow):
        # A data endpoint named in this turn's page outline; the address came from the
        # page's own scripts, never from the planner.
        address = (endpoints or {}).get(follow)
        if address is None:
            return DocumentRead(WebUrlOutput("needs_input", "ENDPOINT_UNKNOWN"), "needs_input")
        data = fetch(
            FetchRequest(
                source_ref=source_id_for(address),
                url=SecretStr(address),
                accepted_media_types=(JSON_MEDIA_TYPE,),
                # The page declared this endpoint; authority ends at its origin.
                stay_within_origin=True,
            )
        )
        if isinstance(data, FetchFailure):
            return DocumentRead(WebUrlOutput("rejected", data.code.value), "fetch_failed")
        if not isinstance(data, FetchSuccess):  # pragma: no cover - FetchOutcome is closed
            raise TypeError("fetch returned neither a success nor a failure")
        source = fetched_source(address, data.content, retrieved_at=clock())
        try:
            records = load_records(data.content)
        except JsonRejected as error:
            return DocumentRead(
                WebUrlOutput("rejected", error.code, source, JSON_MEDIA_TYPE), "not_admitted"
            )
        return DocumentRead(WebUrlOutput("loaded", None, source, JSON_MEDIA_TYPE, table=records))
    via: tuple[str, str] | None = None
    if follow is not None:
        page = fetch(
            FetchRequest(
                source_ref=source_id_for(url),
                url=SecretStr(url),
                accepted_media_types=(MIME_TYPES[FileKind.HTML],),
            )
        )
        if isinstance(page, FetchFailure):
            reason = () if page.target_reason is None else (page.target_reason.value,)
            return DocumentRead(WebUrlOutput("rejected", page.code.value), "fetch_failed", reason)
        if not isinstance(page, FetchSuccess):  # pragma: no cover - FetchOutcome is closed
            raise TypeError("fetch returned neither a success nor a failure")
        base = (
            page.effective_locator.get_secret_value() if page.effective_locator is not None else url
        )
        scripted = script_links(page.content, base, fetch)
        try:
            link = choose_link((*page_links(page.content, base), *scripted.links), follow)
        except LinkRefused as error:
            return DocumentRead(
                WebUrlOutput(
                    "needs_input",
                    error.code,
                    unresolved_navigation=scripted.unresolved,
                    refused_navigation=scripted.refused,
                ),
                "needs_input",
            )
        url = link.url
        via = (_link_name(link), _page_locator(base))

    outcome = fetch(
        FetchRequest(
            source_ref=source_id_for(url),
            url=SecretStr(url),
            # Plain text too, read only as a CSV that proves to be one (QA-33).
            accepted_media_types=FETCHED_MEDIA_TYPES,
            # Following a link is delegated authority: it may not leave the page's origin.
            stay_within_origin=follow is not None or delegated,
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

    # Plain text that loaded as a table is a CSV from here on; anything else keeps its type.
    media_type = kept_media_type(outcome.media_type, loaded)
    kept_as = None
    if keep is not None:
        # The same bytes this turn just read, offered once to the conversation's
        # documents so that keeping them later costs no second download (DEC-183).
        # Admission - media type, size, hash, capacity - is unchanged and decides.
        kept_as = keep(media_type, outcome.content, source.locator)
    read = _loaded(loaded, source, media_type)
    if kept_as is not None:
        read = replace(read, output=replace(read.output, kept_as=kept_as))
    if read.failure is None:
        listing = isinstance(read.output.document, HtmlDocument) and follow is None
        scripted = (
            script_links(outcome.content, source.locator, fetch) if listing else ScriptedLinks()
        )
        read = replace(
            read,
            output=replace(
                read.output,
                links=(*page_links(outcome.content, source.locator), *scripted.links)
                if listing
                else (),
                unresolved_navigation=scripted.unresolved,
                refused_navigation=scripted.refused,
                followed=follow is not None,
                followed_text=via[0] if via is not None else None,
                followed_from=via[1] if via is not None else None,
            ),
        )
    return read


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
    library: Mapping[str, Attachment] | None = None,
    endpoints: Mapping[str, str] | None = None,
    keep: Callable[[str, bytes, str], str | None] | None = None,
) -> ToolSpec:
    """Bind the tool to a fetch boundary: the real `safe_fetch` unless a test substitutes it.

    `fetch=None` reads no address at all; `attachment` is the one document the
    user uploaded with this question (M10-04), if any; `library` holds every
    document admitted in the conversation by server-owned name.
    """
    # Read when a call runs: a document admitted during this turn is one of them then.
    documents: Mapping[str, Attachment] = library if library is not None else {}

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, WebUrlArguments):  # pragma: no cover
            raise TypeError("web_url received arguments it did not declare")
        if arguments.year is not None and not year_in_question(arguments.year, context.question):
            # Like the address, a year is the user's word, never the model's (DEC-148).
            return _failed("needs_input", WebUrlOutput("needs_input", "YEAR_NOT_IN_QUESTION"))
        if arguments.attached:
            chosen = choose_document(arguments.document, attachment, documents)
            if isinstance(chosen, str):
                return _failed("no_attachment", WebUrlOutput("rejected", chosen))
            read = read_attachment(
                chosen, delimiter=arguments.delimiter, sheet=arguments.sheet, ocr=ocr
            )
        elif fetch is None:
            return _failed("fetch_failed", WebUrlOutput("rejected", "NETWORK_DISABLED"))
        elif arguments.read_from is not None:
            parent = context.outputs.get(arguments.read_from)
            if not isinstance(parent, WebUrlOutput) or parent.status != "loaded" or parent.followed:
                return _failed(
                    "navigation_refused", WebUrlOutput("rejected", "FOLLOW_SOURCE_INVALID")
                )
            try:
                target = choose_link(parent.links, arguments.follow or "")
            except LinkRefused as error:
                return _failed("navigation_refused", WebUrlOutput("rejected", error.code))
            read = read_document(
                target.url,
                context.question,
                fetch=fetch,
                delimiter=arguments.delimiter,
                sheet=arguments.sheet,
                ocr=ocr,
                clock=clock,
                keep=keep,
                searched=frozenset({target.url}),
                delegated=True,
            )
            read = replace(
                read,
                output=replace(
                    read.output,
                    followed=True,
                    links=(),
                    followed_text=_link_name(target),
                    followed_from=(
                        _page_locator(parent.source.locator) if parent.source is not None else None
                    ),
                ),
            )
        else:
            address = arguments.url
            if arguments.found_by is not None:
                address = _found_address(context, arguments.found_by, arguments.result)
                if address is None:
                    return _failed(
                        "needs_input",
                        WebUrlOutput("rejected", "SEARCH_RESULT_NOT_FOUND"),
                    )
            if address is None:  # pragma: no cover - the validator admits no third case
                return _failed("fetch_failed", WebUrlOutput("rejected", "NETWORK_DISABLED"))
            read = read_document(
                address,
                context.question,
                fetch=fetch,
                delimiter=arguments.delimiter,
                sheet=arguments.sheet,
                ocr=ocr,
                clock=clock,
                follow=arguments.follow,
                endpoints=endpoints,
                keep=keep,
                searched=searched_addresses(context),
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
            units = declared_units(arguments.column_units, context.question)
            if isinstance(units, str):
                return _failed("needs_input", replace(output, status="needs_input", code=units))
            rule = arguments.daily_to_monthly
            if rule is not None and not daily_rule_in_question(rule, context.question):
                # Like a unit or a year, how days become months is the user's word.
                return _failed(
                    "needs_input",
                    replace(output, status="needs_input", code="AGGREGATION_NOT_IN_QUESTION"),
                )

            def is_series(label: str) -> bool:
                return (
                    connection.execute(
                        "SELECT 1 FROM silver_series WHERE series_id = ? LIMIT 1", [label]
                    ).fetchone()
                    is not None
                )

            try:
                reviewed_metrics = (
                    bist_index_close_metrics(arguments.url, endpoint, output.table)
                    if arguments.url is not None
                    and arguments.follow is not None
                    and ENDPOINT_NAME.fullmatch(arguments.follow)
                    and arguments.period_column == "hisTs"
                    and rule in ("last", "mean")
                    and (endpoint := (endpoints or {}).get(arguments.follow)) is not None
                    and isinstance(output.table, RecordTable)
                    and source.source_id == source_id_for(endpoint)
                    and media_type == JSON_MEDIA_TYPE
                    else {}
                )
                table = (
                    read_daily_table(
                        grids(output.table, output.document),
                        arguments.period_column,
                        arguments.value_columns,
                        rule=rule,
                        as_of=as_of(source),
                        is_series=is_series,
                        declared_units=units,
                        reviewed_metrics=reviewed_metrics,
                    )
                    if rule is not None
                    else read_table(
                        grids(output.table, output.document),
                        arguments.period_column,
                        arguments.value_columns,
                        is_series=is_series,
                        year=arguments.year,
                        as_of=as_of(source),
                        declared_units=units,
                    )
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
            "written; any other address is refused. To read a page a web_search step of "
            "this plan found, do not write its address out: give found_by=<that step_id> "
            "with result=<which hit>, and list the step in depends_on - the address is then "
            "taken from what the search returned. PDF tables may be ruled or set out with "
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
            "rectangular tables; no JavaScript or CSS rendering. When the data sits behind a "
            "link on the page the user gave (a PDF or spreadsheet), give follow with that "
            "link's visible text or file name; only same-site links are followed. A page's "
            "links include a row or button that opens its target through the page's own "
            "same-origin script, when that script spells the address out in plain text; a "
            "call it could not read that way is listed under unresolved_navigation. Image "
            "addresses are not supported. To build a monthly table that later turns can use, "
            "give period_column and up to twelve value_columns instead of column and "
            "row: months must be explicit, one row per month. A value header should state its unit "
            "in parentheses; a column without one is kept with its unit unresolved (its figures "
            "are never quoted) unless the user wrote the unit in the question (column_units). A "
            "column that fails is left out with a warning."
            + (
                " The user uploaded a document with this question: read it with attached=true "
                "and no url."
                if attachment is not None
                else ""
            )
            + (
                " Documents uploaded earlier in this conversation stay readable with "
                "attached=true and document=<name>; their outline is provided as data."
                if documents
                else ""
            )
        ),
        arguments=WebUrlArguments,
        run=run,
        required_steps=_required_steps,
    )


def _failed(category: str, output: WebUrlOutput, *, extra: tuple[str, ...] = ()) -> ToolResult:
    """A refusal that names its fixed code and nothing from the document or URL."""
    codes = tuple(code for code in (output.code, *extra) if code is not None)
    return ToolResult(
        ToolStatus.FAILURE,
        step_id="",
        tool="web_url",
        output=output,
        error_category=category,
        warnings=(*codes, *(_EXPLAINED[code] for code in codes if code in _EXPLAINED)),
    )


#: What a code means, said beside it where the code alone sent the model round in
#: circles. Live 2026-09-23 (QA-33) a CSV served as plain text was refused four times as
#: CONTENT_TYPE while the model changed its column arguments, and then concluded that
#: saving was not possible at all. Fixed text: nothing from the document or the address.
_EXPLAINED: dict[str, str] = {
    "CONTENT_TYPE": (
        "The address serves a type no reader here takes (CSV, XLSX, PDF, HTML, a picture, "
        "or a table as plain text are read). Asking again with other arguments does not "
        "change what the address serves."
    ),
    PLAIN_TEXT_NOT_A_TABLE: (
        "The address serves plain text that is not a table: read as a CSV it needs at "
        "least two columns and the same number of fields in every row."
    ),
}


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
