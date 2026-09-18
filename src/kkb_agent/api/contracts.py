"""Version-one public JSON contracts; no arbitrary internal objects or attributes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, StringConstraints, model_validator

from kkb_agent.agent.verifier import AnswerStatus
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
    status: Literal["running", "completed", "failed"]
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
    # tool's arguments and a preview of what it produced. Bounded and redacted.
    detail: Annotated[str, StringConstraints(strict=True, max_length=16384)] | None = None
    parent: Annotated[int, Field(strict=True, ge=1)] | None = None


class RunDetail(ContractModel):
    api_version: Literal[1] = 1
    run: RunSummary
    steps: Annotated[tuple[TraceStep, ...], Field(max_length=400)] = ()


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


class Feedback(ContractModel):
    turn_id: Reference
    # The exact answer this rating is about; a re-answered turn rates separately.
    answer_digest: Digest
    run_id: Reference | None = None
    result_version: Digest | None = None
    rating: Literal["up", "down"]
    comment: Annotated[str, StringConstraints(strict=True, max_length=2000)] | None = None
    reasons: Annotated[tuple[FeedbackReason, ...], Field(max_length=8)] = ()
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FeedbackList(ContractModel):
    api_version: Literal[1] = 1
    feedback: Annotated[tuple[Feedback, ...], Field(max_length=200)] = ()
