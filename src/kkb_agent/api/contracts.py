"""Version-one public JSON contracts; no arbitrary internal objects or attributes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Final, Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, StringConstraints, model_validator

from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.catalog.records import MAX_CATALOG_SERIES
from kkb_agent.core import ClaimKind, Period, ResultKind, SampleCounts, Scale, StockFlow
from kkb_agent.core.models import ContractModel

MAX_BODY_BYTES = 16 * 1024
MAX_QUESTION_BYTES = 8 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_VALUES = 2048
MAX_SESSIONS = 8
MAX_TURNS = 24
# M10-04: the one route with a non-JSON body, and its per-session budget.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCUMENTS = 4

Reference = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")]
Text = Annotated[str, StringConstraints(strict=True, max_length=8192)]
Label = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=240)]
ErrorCode = Literal[
    "invalid_request",
    "invalid_result",
    "not_found",
    "busy",
    "capacity",
    "request_conflict",
    "unavailable",
    "planning_failed",
    "provider_failed",
    "internal_error",
    "output_limit",
    "forbidden",
    "body_too_large",
    "document_rejected",
    "invalid_document",
    "cancelled",
    "knowledge_rejected",
]
TurnState = Literal["queued", "running", "completed", "failed"]


class Question(ContractModel):
    request_id: Reference
    question: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]
    # Public result_ref from a completed turn in this session, never a workspace name.
    selected_result_id: Reference | None = None
    is_continuation: bool | None = None
    # A document this session uploaded, attached to this one question.
    document_ref: Reference | None = None

    @model_validator(mode="after")
    def bounded_question(self) -> Self:
        if not self.question.strip() or len(self.question.encode("utf-8")) > MAX_QUESTION_BYTES:
            raise ValueError("Question exceeds the text budget or is empty")
        if any(ord(c) < 32 and c not in "\n\t\r" for c in self.question):
            raise ValueError("Question contains unsupported controls")
        return self


class Error(ContractModel):
    api_version: Literal[1] = 1
    error: ErrorCode


class SessionCreated(ContractModel):
    api_version: Literal[1] = 1
    session_id: Reference
    # Capability returned once; supplied as a header, never in a URL or log.
    token: Annotated[str, StringConstraints(strict=True, min_length=43, max_length=43)]
    # True when the operator gave the service a conversation store (M14-01).
    survives_restart: bool = False


class Cell(ContractModel):
    cell_id: Reference
    slot: Annotated[int, Field(strict=True, ge=0, lt=MAX_VALUES)]
    label: Label
    value: Annotated[float, Field(strict=True)]
    display: Text | None
    unit: Label | None
    scale: Scale
    measure: StockFlow
    period: Period | None
    samples: SampleCounts | None
    lag: int | None


Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
# Code-owned identifiers only (tool, operation, parser, semantic codes).
Code = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:;+-]{0,119}$")
]
Count = Annotated[int, Field(strict=True, ge=0)]
ProofGap = Literal[
    "execution_not_verified",
    "input_not_recognized",
    "input_result_not_verified",
    "dataset_record_missing",
    "source_lineage_missing",
    "raw_response_limit",
    "step_limit",
    "source_limit",
    "proof_unreadable",
]
MAX_PROOF_STEPS = 8
MAX_PROOF_SOURCES = 32
MAX_STEP_INPUTS = 16
MAX_PROOF_DOCUMENTS = 4


class ProofSource(ContractModel):
    """A prepared series an execution actually read, and its recorded origin.

    `dataset_sha256` is content identity, not correctness. Only an https host is
    shown for raw responses; locator paths, queries and request bodies are not.
    """

    series_id: Label
    title: Label | None
    # execution_snapshot: artifact identity captured when the tool read the data.
    # series_record: the tool recorded an inspection receipt; the artifact comes
    # from the session's immutable prepared series record instead.
    binding: Literal["execution_snapshot", "series_record"]
    dataset_sha256: Digest | None
    dataset_source_type: Code | None
    # Declared codes as recorded; None when that snapshot did not capture them.
    unit: Label | None
    scale: Code | None
    frequency: Code | None
    measure: Code | None
    cumulative: Code | None
    aggregation: Code | None
    catalog_status: Code | None
    observations: Count | None
    missing_values: Count | None
    first_period: date | None
    last_period: date | None
    parser: Code | None
    normalization: Label | None
    raw_responses: Count
    raw_response_types: Annotated[tuple[Code, ...], Field(max_length=4)]
    hosts: Annotated[tuple[Label, ...], Field(max_length=4)]
    first_retrieved: AwareDatetime | None
    last_retrieved: AwareDatetime | None


class DocumentAdmitted(ContractModel):
    """What an admitted upload returns; never its filename or content."""

    api_version: Literal[1] = 1
    document_ref: Reference
    document_format: Literal["csv", "xlsx", "pdf", "html"]
    bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_DOCUMENT_BYTES)]
    sha256: Digest


class ProofDocument(ContractModel):
    """A fetched document a literal cell (DEC-132) or an added column (M7-14) was read from.

    Only fixed facts recorded with the verified cell: never the address path or
    query, a sheet name, header, row label or cell text, which are document data.
    """

    source_type: Literal["web_url", "upload"]
    document_format: Literal["csv", "xlsx", "pdf", "html"]
    host: Label | None
    content_sha256: Digest
    retrieved_at: AwareDatetime | None
    page: Annotated[int, Field(strict=True, ge=1)] | None
    table: Annotated[int, Field(strict=True, ge=1)] | None
    # None when a whole column (row) or a whole table (row and column) was read.
    row: Annotated[int, Field(strict=True, ge=1)] | None
    column: Annotated[int, Field(strict=True, ge=1)] | None
    values_read: Count | None = None
    # A worksheet was named; its name is document text and is not shown.
    sheet_selected: bool
    # "ocr" when the values came from OCR of a page without text and passed the
    # DEC-149 column-total check.
    extraction: Literal["text", "ocr"] = "text"


class ProofInput(ContractModel):
    kind: Literal["series", "result", "document"]
    # Index into Proof.sources, Proof.steps or Proof.documents respectively.
    index: Annotated[int, Field(strict=True, ge=0, lt=MAX_PROOF_SOURCES)]


class ProofStep(ContractModel):
    producer: Code
    operation: Code | None
    kind: ResultKind
    method: Code | None
    execution: Literal["verified", "not_verified"]
    result_version: Digest
    # Server-owned publication name (analiz_N) when the input was a published table.
    workspace_name: Code | None
    coverage: Period | None
    samples: SampleCounts | None
    inputs: Annotated[tuple[ProofInput, ...], Field(max_length=MAX_STEP_INPUTS)]


class Proof(ContractModel):
    """Bounded, recorded result-level evidence; availability is coverage, not truth."""

    scope: Literal["result"] = "result"
    availability: Literal["available", "partial", "unavailable"]
    # The answer gate's outcome is preserved separately from recorded coverage.
    gate: Literal["accepted"] = "accepted"
    steps: Annotated[tuple[ProofStep, ...], Field(max_length=MAX_PROOF_STEPS)] = ()
    sources: Annotated[tuple[ProofSource, ...], Field(max_length=MAX_PROOF_SOURCES)] = ()
    documents: Annotated[tuple[ProofDocument, ...], Field(max_length=MAX_PROOF_DOCUMENTS)] = ()
    warnings: Annotated[tuple[Text, ...], Field(max_length=16)] = ()
    limitations: Annotated[tuple[Text, ...], Field(max_length=16)] = ()
    unresolved_semantics: Annotated[tuple[Text, ...], Field(max_length=16)] = ()
    gaps: Annotated[tuple[ProofGap, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.availability == "unavailable":
            if self.steps or self.sources or self.documents:
                raise ValueError("Unavailable proof carries no recorded chain")
            return self
        if not self.steps or self.steps[0].execution != "verified":
            raise ValueError("Recorded proof starts at a verified execution")
        if self.availability == "available" and self.gaps:
            raise ValueError("A proof with gaps is partial")
        for step in self.steps:
            for item in step.inputs:
                limit = {
                    "series": len(self.sources),
                    "result": len(self.steps),
                    "document": len(self.documents),
                }[item.kind]
                if item.index >= limit:
                    raise ValueError("Proof input references a missing entry")
        return self


def unavailable_proof(*gaps: ProofGap) -> Proof:
    return Proof(availability="unavailable", gaps=gaps)


class Result(ContractModel):
    result_ref: Reference
    version: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    kind: ResultKind
    claim_kind: ClaimKind
    # Only an exactly published workspace result may enter this contract.
    published: Literal[True] = True
    cells: Annotated[tuple[Cell, ...], Field(max_length=MAX_VALUES)]
    # Built only by the runner that owns the publication's connection.
    proof: Proof = Field(default_factory=unavailable_proof)


class Answer(ContractModel):
    status: AnswerStatus
    text: Text
    omitted_claims: Annotated[int, Field(strict=True, ge=0)]
    notices: Annotated[tuple[Text, ...], Field(max_length=16)] = ()
    result: Result | None = None


class Event(ContractModel):
    sequence: Annotated[int, Field(strict=True, ge=1, le=3)]
    state: TurnState
    elapsed_ms: Annotated[int, Field(strict=True, ge=0)]


class Turn(ContractModel):
    api_version: Literal[1] = 1
    turn_id: Reference
    request_id: Reference
    state: TurnState
    answer: Answer | None = None
    error: ErrorCode | None = None
    events: Annotated[tuple[Event, ...], Field(max_length=3)] = ()


class Health(ContractModel):
    api_version: Literal[1] = 1
    service: Literal["ready"] = "ready"
    model_checked: Literal[False] = False
    execution_mode: Literal["kloudeks", "scripted"]
    max_sessions: int = MAX_SESSIONS
    max_turns_per_session: int = MAX_TURNS
    max_running_turns: Literal[1] = 1
    capabilities: tuple[str, ...] = ("sessions", "questions", "published_values", "turn_events")


#: Capabilities a browser may switch **off** for its own turns. It can never switch
#: one on: the operator decides what this deployment may do at all, and a browser
#: that could widen that would widen the deployment's authority (DEC-162).
RESTRICTABLE_CAPABILITIES: Final = (
    "document_upload",
    "document_ocr",
    "official_acquisition",
    "web_search",
    "web_url",
)


class RuntimeSettings(ContractModel):
    """What this deployment can do, and what this browser chose to switch off."""

    api_version: Literal[1] = 1
    #: Restrictable capabilities the operator actually enabled, in a fixed order.
    available: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    #: The subset this browser turned off; never anything outside `available`.
    disabled: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    #: Earlier turns of the conversation the planner is shown.
    history_turns: Annotated[int, Field(strict=True, ge=0, le=64)]
    max_history_turns: Annotated[int, Field(strict=True, ge=0, le=64)]


class SettingsUpdate(ContractModel):
    """A change to this browser's own settings; absent fields stay as they were."""

    disabled: Annotated[tuple[str, ...], Field(max_length=16)] | None = None
    history_turns: Annotated[int, Field(strict=True, ge=0, le=64)] | None = None


#: The browser-held keys: an owner key and a conversation token share this shape.
Key = Annotated[str, StringConstraints(strict=True, min_length=43, max_length=43)]


class OwnerCreated(ContractModel):
    """The browser's own key for its conversations; only its digest is stored."""

    api_version: Literal[1] = 1
    owner_token: Key


class ConversationSummary(ContractModel):
    conversation_id: Reference
    title: Label
    archived: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime
    turns: Annotated[int, Field(strict=True, ge=0)]


class ConversationList(ContractModel):
    api_version: Literal[1] = 1
    conversations: Annotated[tuple[ConversationSummary, ...], Field(max_length=200)] = ()


class StoredMessage(ContractModel):
    sequence: Annotated[int, Field(strict=True, ge=1)]
    turn_id: Reference
    role: Literal["user", "assistant"]
    text: Text
    status: AnswerStatus | None = None
    result_ref: Reference | None = None
    result_version: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    document_ref: Reference | None = None
    created_at: AwareDatetime


class ConversationDocument(ContractModel):
    document_ref: Reference
    # Server-owned name (belge_1, ...); an uploaded filename is never kept.
    name: Annotated[str, StringConstraints(strict=True, pattern=r"^belge_[0-9]{1,2}$")]
    document_format: Literal["csv", "xlsx", "pdf", "html"]
    bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_DOCUMENT_BYTES)]
    sha256: Digest
    admitted_at: AwareDatetime


class ConversationDetail(ContractModel):
    api_version: Literal[1] = 1
    conversation: ConversationSummary
    # Returned so an owner can continue this conversation's turn endpoints.
    token: Key | None = None
    messages: Annotated[tuple[StoredMessage, ...], Field(max_length=512)] = ()
    documents: Annotated[tuple[ConversationDocument, ...], Field(max_length=MAX_DOCUMENTS)] = ()


class ConversationUpdate(ContractModel):
    title: Label | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def one_change(self) -> Self:
        if self.title is None and self.archived is None:
            raise ValueError("Give a title or an archived flag")
        return self


class RunSummary(ContractModel):
    """One executed turn, as a reader picks it from a list."""

    run_id: Reference
    turn_id: Reference
    question: Text
    status: Literal["running", "completed", "failed", "cancelled"]
    answer_status: AnswerStatus | None = None
    error: ErrorCode | Code | None = None
    result_ref: Reference | None = None
    duration_ms: Annotated[int, Field(strict=True, ge=0)]
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    events: Annotated[int, Field(strict=True, ge=0)] = 0


class RunList(ContractModel):
    api_version: Literal[1] = 1
    runs: Annotated[tuple[RunSummary, ...], Field(max_length=200)] = ()


class TraceStep(ContractModel):
    """One recorded step of a run: what ran, how it ended, how long it took."""

    sequence: Annotated[int, Field(strict=True, ge=1)]
    stage: Code
    name: Code
    status: Code
    started_ms: Annotated[int, Field(strict=True, ge=0)]
    duration_ms: Annotated[int, Field(strict=True, ge=0)]
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    # The step's own text: the context sent to the model, what it returned, a
    # tool's arguments and everything it returned. Redacted. In a run listing it is
    # a preview; `detail_chars` is the full length and the step route returns it all.
    detail: Annotated[str, StringConstraints(strict=True, max_length=16384)] | None = None
    detail_chars: Annotated[int, Field(strict=True, ge=0)] | None = None
    detail_complete: bool = True
    parent: Annotated[int, Field(strict=True, ge=1)] | None = None


#: Preview length of a step's text inside a run listing.
TRACE_PREVIEW_CHARS = 16_000


class TraceStepFull(ContractModel):
    """One step's text exactly as recorded, never clipped for display."""

    api_version: Literal[1] = 1
    sequence: Annotated[int, Field(strict=True, ge=1)]
    name: Code
    detail: Annotated[str, StringConstraints(strict=True, max_length=2_000_000)] | None = None


class RunDetail(ContractModel):
    api_version: Literal[1] = 1
    run: RunSummary
    steps: Annotated[tuple[TraceStep, ...], Field(max_length=5000)] = ()


#: Why an answer was rated down; a fixed vocabulary, never free-form categories.
FeedbackReason = Literal[
    "accuracy",
    "incomplete",
    "wrong_source",
    "slow",
    "lost_context",
    "unclear",
    "other",
]


class FeedbackRequest(ContractModel):
    """A rating of the answer shown for one turn, with optional words."""

    turn_id: Reference
    rating: Literal["up", "down"]
    comment: Annotated[str, StringConstraints(strict=True, max_length=2000)] | None = None
    reasons: Annotated[tuple[FeedbackReason, ...], Field(max_length=8)] = ()
    #: How useful the answer was, 1 (not at all) to 5 (fully); optional.
    score: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None


class Feedback(ContractModel):
    turn_id: Reference
    # The exact answer this rating is about; a re-answered turn rates separately.
    answer_digest: Digest
    run_id: Reference | None = None
    result_version: Digest | None = None
    rating: Literal["up", "down"]
    comment: Annotated[str, StringConstraints(strict=True, max_length=2000)] | None = None
    reasons: Annotated[tuple[FeedbackReason, ...], Field(max_length=8)] = ()
    #: How useful the answer was, 1 (not at all) to 5 (fully); optional.
    score: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FeedbackList(ContractModel):
    api_version: Literal[1] = 1
    feedback: Annotated[tuple[Feedback, ...], Field(max_length=200)] = ()


# -- Knowledge base (DEC-157) --------------------------------------------------

#: A catalog identity as the API shows it: reviewed ids and USER:<slug>.v<N>.
SeriesIdentity = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
]
Slug = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z][a-z0-9_]{2,39}$")]
ShortText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strict=True, max_length=1000)]
AliasText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)]
MAX_KNOWLEDGE_OBSERVATIONS = 5000


class KnowledgeSeries(ContractModel):
    """One entry the agent can know about, and where its meaning comes from."""

    series_id: SeriesIdentity
    title: str
    provider: str
    #: reviewed: from the reviewed catalog; user: declared by a person here.
    origin: Literal["reviewed", "user"]
    status: Literal["active", "archived", "unknown"]
    #: Stored in the prepared pool every conversation starts from.
    prepared: bool
    #: Not stored yet, but fetched from its reviewed source on first use (DEC-155).
    fetchable: bool
    unit: str | None
    scale: str
    frequency: str
    stock_flow: str
    cumulative: str
    base_year: int | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    observations: int | None = None
    aliases: tuple[str, ...] = ()
    note: str | None = None
    version: int | None = None
    slug: str | None = None
    updated_at: AwareDatetime | None = None
    #: When the series was last fetched from its reviewed source (DEC-159).
    acquired_at: AwareDatetime | None = None


class KnowledgeList(ContractModel):
    api_version: Literal[1] = 1
    #: Digest of the catalog a turn searches now; equals the reviewed one when nothing is added.
    catalog_digest: str
    reviewed_digest: str
    series: Annotated[tuple[KnowledgeSeries, ...], Field(max_length=MAX_CATALOG_SERIES)] = ()


class SearchHit(ContractModel):
    """One candidate as discovery would hand it to the planner, without scores."""

    series_id: SeriesIdentity
    title: str
    provider: str
    unit: str | None
    frequency: str
    stock_flow: str
    prepared: bool
    archived: bool
    stage: Literal["lexical", "dense", "both"]
    concepts: Annotated[tuple[str, ...], Field(max_length=20)] = ()


class SearchTrial(ContractModel):
    """What a question would find in this catalogue, run here and kept nowhere."""

    api_version: Literal[1] = 1
    query: str
    status: str
    clarification_required: bool
    total_candidates: Annotated[int, Field(strict=True, ge=0, le=MAX_CATALOG_SERIES)]
    hits: Annotated[tuple[SearchHit, ...], Field(max_length=10)] = ()
    #: Which retrieval stages ran, exactly as the search tool recorded them, so a
    #: catalogue the vector generation no longer covers is visible instead of
    #: silently falling back to words alone.
    retrieval_mode: Literal["lexical_only", "hybrid", "lexical_degraded"] = "lexical_only"
    dense_status: Literal["not_configured", "skipped_no_eligible", "success", "failed"] = (
        "not_configured"
    )
    dense_failure: Literal["snapshot_mismatch", "embedding_failed", "index_failed"] | None = None
    embedding_model: str | None = None
    input_policy_id: str | None = None


class SeriesUse(ContractModel):
    """One answer whose proof read the series: where it lives and what was asked."""

    conversation_id: Reference
    title: str
    turn_id: Reference
    question: str
    used_at: str


class SeriesUses(ContractModel):
    """Reverse lineage for one series: this browser's answers that rest on it.

    Recorded from each published answer's proof sources at the moment the
    answer is stored, never inferred from wording. Answers stored before this
    record existed are not listed.
    """

    api_version: Literal[1] = 1
    series_id: SeriesIdentity
    uses: Annotated[tuple[SeriesUse, ...], Field(max_length=200)] = ()


class VectorIndexStatus(ContractModel):
    """Which generation of meaning vectors this deployment searches, and what it covers.

    A generation is built for one exact catalogue. Everything the knowledge base
    adds or archives makes a different catalogue, so the vectors stop covering it
    until they are built again with the same model and input policy.
    """

    api_version: Literal[1] = 1
    configured: bool
    model: str | None = None
    input_policy_id: str | None = None
    origin: str | None = None
    dimension: Annotated[int, Field(strict=True, ge=0, le=1 << 16)] = 0
    #: The catalogue digest the vectors were built for, and the one in use now.
    generation_sha256: str | None = None
    generation_version: str | None = None
    catalog_sha256: str
    catalog_version: str
    covers_catalog: bool
    series_total: Annotated[int, Field(strict=True, ge=0, le=MAX_CATALOG_SERIES)]
    series_vectored: Annotated[int, Field(strict=True, ge=0, le=MAX_CATALOG_SERIES)]
    #: Catalogue entries with no vector in this generation, newest concern first.
    missing: Annotated[tuple[SeriesIdentity, ...], Field(max_length=50)] = ()
    #: A build in progress, and how the last one ended. A build never edits a
    #: generation in place: it writes a new one and installs it for later turns.
    rebuilding: bool = False
    rebuildable: bool = False
    built_at: datetime | None = None
    last_error: str | None = None


class ObservationIn(ContractModel):
    period_end: date
    value: float | None


class DocumentColumnRef(ContractModel):
    """Read a dataset's numbers from a table already uploaded to one of your conversations."""

    session_id: Reference
    document_ref: Reference
    period_column: ShortText
    value_column: ShortText
    sheet: ShortText | None = None
    year: Annotated[int, Field(ge=1900, le=2100)] | None = None


class DatasetRequest(ContractModel):
    """A dataset and the meaning its author declares; every save is a new version."""

    slug: Slug
    title: ShortText
    description: LongText | None = None
    unit: ShortText
    scale: Literal["one", "thousand", "million", "billion"]
    frequency: Literal["weekly", "monthly", "quarterly", "annual"]
    #: Required for weekly data: the weekday each period ends on.
    weekly_anchor: (
        Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] | None
    ) = None
    stock_flow: Literal["stock", "flow", "rate", "index"]
    cumulative: Literal["none", "yearly_reset", "since_inception"] = "none"
    aggregation: Literal["sum", "average", "first", "last", "min", "max"]
    base_year: Annotated[int, Field(ge=1900, le=2100)] | None = None
    aliases: Annotated[tuple[AliasText, ...], Field(max_length=10)] = ()
    observations: Annotated[
        tuple[ObservationIn, ...], Field(max_length=MAX_KNOWLEDGE_OBSERVATIONS)
    ] = ()
    document: DocumentColumnRef | None = None

    @model_validator(mode="after")
    def one_source(self) -> Self:
        if bool(self.observations) == (self.document is not None):
            raise ValueError("give either observations or a document column, not both")
        if self.document is not None and self.frequency != "monthly":
            raise ValueError("a document column is read by month")
        if (self.frequency == "weekly") != (self.weekly_anchor is not None):
            raise ValueError("weekly data needs its anchor weekday, and only weekly data has one")
        return self


class DatasetVersionSummary(ContractModel):
    version: int
    status: Literal["active", "archived"]
    observations: int
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: AwareDatetime


class StoredObservation(ContractModel):
    period_start: date
    period_end: date
    value: float | None


class DatasetDetail(ContractModel):
    api_version: Literal[1] = 1
    series: KnowledgeSeries
    source_kind: Literal["upload", "manual"]
    description: str | None = None
    aggregation: str
    #: The weekday a weekly period ends on; carried so an edit or an export
    #: cannot silently change a declared anchor.
    weekly_anchor: str | None = None
    observations: Annotated[
        tuple[StoredObservation, ...], Field(max_length=MAX_KNOWLEDGE_OBSERVATIONS)
    ] = ()
    history: Annotated[tuple[DatasetVersionSummary, ...], Field(max_length=500)] = ()


class SeriesNoteRequest(ContractModel):
    archived: bool
    aliases: Annotated[tuple[AliasText, ...], Field(max_length=10)] = ()
    note: LongText | None = None


class SeriesNoteVersion(ContractModel):
    version: int
    archived: bool
    aliases: tuple[str, ...]
    note: str | None
    created_at: AwareDatetime


class SeriesNoteHistory(ContractModel):
    api_version: Literal[1] = 1
    series_id: SeriesIdentity
    history: Annotated[tuple[SeriesNoteVersion, ...], Field(max_length=500)] = ()


class SeriesValues(ContractModel):
    """A prepared series' stored observations, as the seed holds them."""

    api_version: Literal[1] = 1
    series_id: SeriesIdentity
    observations: Annotated[
        tuple[StoredObservation, ...], Field(max_length=MAX_KNOWLEDGE_OBSERVATIONS)
    ] = ()
