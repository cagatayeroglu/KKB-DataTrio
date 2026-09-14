"""Version-one public JSON contracts; no arbitrary internal objects or attributes."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.core import ClaimKind, Period, ResultKind, SampleCounts, Scale, StockFlow
from kkb_agent.core.models import ContractModel

MAX_BODY_BYTES = 16 * 1024
MAX_QUESTION_BYTES = 8 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_VALUES = 2048
MAX_SESSIONS = 8
MAX_TURNS = 24

Reference = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{32}$")]
Text = Annotated[str, StringConstraints(strict=True, max_length=8192)]
Label = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=240)]
ErrorCode = Literal[
    "invalid_request",
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
]
TurnState = Literal["queued", "running", "completed", "failed"]


class Question(ContractModel):
    request_id: Reference
    question: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]

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
    survives_restart: Literal[False] = False


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


class Result(ContractModel):
    result_ref: Reference
    version: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    kind: ResultKind
    claim_kind: ClaimKind
    # Only an exactly published workspace result may enter this contract.
    published: Literal[True] = True
    cells: Annotated[tuple[Cell, ...], Field(max_length=MAX_VALUES)]
    # Stable references do not claim an implemented public proof traversal.
    proof_graph: Literal["unavailable"] = "unavailable"


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
