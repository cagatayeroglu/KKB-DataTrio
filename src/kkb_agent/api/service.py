"""Bounded, process-local capabilities and one owned worker; no database sharing."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import uuid4

from kkb_agent.agent.loop import PlanningFailed
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.api.contracts import (
    MAX_DOCUMENTS,
    MAX_RESPONSE_BYTES,
    MAX_SESSIONS,
    MAX_TURNS,
    Answer,
    ConversationDetail,
    ConversationDocument,
    ConversationList,
    ConversationSummary,
    ConversationUpdate,
    DocumentAdmitted,
    ErrorCode,
    Event,
    Feedback,
    FeedbackList,
    FeedbackRequest,
    Health,
    OwnerCreated,
    Question,
    RunDetail,
    RunList,
    RunSummary,
    SessionCreated,
    StoredMessage,
    TraceStep,
    Turn,
    TurnState,
)
from kkb_agent.api.projection import OutputRefused
from kkb_agent.api.store import (
    DEFAULT_TITLE,
    ConversationStore,
    StoredFeedback,
    StoredRun,
    StoreError,
)
from kkb_agent.llm.provider import ProviderError


# Executed only on the one worker. A runtime must own/open/close its connection
# there and retain session state under the server-issued session_id.
class Runner(Protocol):
    def __call__(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        *,
        is_continuation: bool | None,
        document_ref: str | None = None,
    ) -> Answer: ...


# M10-04: admits and stores one upload for a session; never on the analysis worker.
class DocumentStore(Protocol):
    def __call__(self, session_id: str, media_type: str, content: bytes) -> DocumentAdmitted: ...


@dataclass(frozen=True, slots=True)
class SelectedResult:
    """Server-resolved publication identity; workspace validity is checked by its runner."""

    turn_id: str
    result_ref: str
    version: str


class SelectedRunner(Protocol):
    def __call__(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selection: SelectedResult,
        *,
        is_continuation: bool | None,
        document_ref: str | None = None,
    ) -> Answer: ...


class ServiceError(Exception):
    def __init__(self, code: ErrorCode, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class _Session:
    token_digest: bytes
    turns: dict[str, Turn] = field(default_factory=dict)
    requests: dict[str, tuple[str, str]] = field(default_factory=dict)
    documents: set[str] = field(default_factory=set)


def answer_digest(text: str) -> str:
    """Identity of one shown answer, so a rating cannot drift onto a new one."""
    return hashlib.sha256(text.encode()).hexdigest()


class AnalysisService:
    """No implicit expiration/deletion/restart recovery, cancellation or retries.

    Eight sessions, twenty-four turns each, one active turn globally. Admission
    is atomic; capacity is checked before submitting to the executor, so its
    unbounded internal queue cannot accumulate application jobs.
    """

    def __init__(
        self,
        runner: Runner,
        *,
        mode: Literal["kloudeks", "scripted"],
        selected_runner: SelectedRunner | None = None,
        document_store: DocumentStore | None = None,
        store: ConversationStore | None = None,
        ocr: bool = False,
    ):
        if mode not in ("kloudeks", "scripted"):
            raise ValueError("An explicit execution mode is required")
        self._runner = runner
        # Until the prepared workspace integration is supplied, explicit selection
        # fails closed. Never hand it to the old runner that cannot respect it.
        self._selected_runner = selected_runner
        # Uploads exist only when the operator supplied a store (--enable-uploads).
        self._document_store = document_store
        # Conversations survive a restart only when the operator supplied one.
        self._store = store
        # Scanned pages are read only when the operator enabled OCR (DEC-149).
        self._ocr = ocr
        self._mode = mode
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kkb-analysis")
        self._busy = False
        self._closed = False

    def health(self) -> Health:
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            capabilities = Health.model_fields["capabilities"].default
            if self._document_store is not None:
                capabilities = (*capabilities, "document_upload")
            if self._store is not None:
                capabilities = (*capabilities, "conversation_history")
            if self._ocr:
                capabilities = (*capabilities, "document_ocr")
            return Health(execution_mode=self._mode, capabilities=capabilities)

    def create_owner(self) -> OwnerCreated:
        """A key this browser keeps; without it, earlier conversations stay closed."""
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            if self._store is None:
                raise ServiceError("unavailable", 503)
            _, token = self._store.create_owner()
        return OwnerCreated(owner_token=token)

    def create_session(self, owner_token: str | None = None) -> SessionCreated:
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            if len(self._sessions) >= MAX_SESSIONS:
                raise ServiceError("capacity", 429)
            session_id, token = uuid4().hex, secrets.token_urlsafe(32)
            if self._store is not None:
                owner = self._store.owner_by_token(owner_token) if owner_token else None
                if owner is None:
                    raise ServiceError("forbidden", 403)
                try:
                    self._store.create_conversation(
                        owner_id=owner,
                        conversation_id=session_id,
                        token=token,
                        title=DEFAULT_TITLE,
                    )
                except StoreError:
                    raise ServiceError("unavailable", 503) from None
            self._sessions[session_id] = _Session(hashlib.sha256(token.encode()).digest())
            return SessionCreated(
                session_id=session_id, token=token, survives_restart=self._store is not None
            )

    def _owned(self, session_id: str, token: str) -> _Session:
        if self._closed:
            raise ServiceError("unavailable", 503)
        session = self._sessions.get(session_id)
        supplied = hashlib.sha256(token.encode()).digest()
        expected = session.token_digest if session else bytes(32)
        valid = secrets.compare_digest(supplied, expected)
        if session is not None and valid:
            return session
        # After a restart the conversation is in the store, not in memory: its own
        # token or its owner's key reopens it, an id on its own never does.
        if self._store is not None and self._store.opens(
            session_id, token=token, owner_token=token
        ):
            if session is None:
                session = _Session(bytes(32))
                self._sessions[session_id] = session
            for document in self._store.documents(session_id):
                session.documents.add(document.document_ref)
            return session
        raise ServiceError("not_found", 404)

    def _reading(self, session_id: str, token: str) -> ConversationSummary:
        """Authorize a conversation read and project its summary."""
        with self._lock:
            self._owned(session_id, token)
        if self._store is None:
            raise ServiceError("unavailable", 503)
        found = self._store.conversation(session_id)
        if found is None:
            raise ServiceError("not_found", 404)
        return ConversationSummary(
            conversation_id=found.conversation_id,
            title=found.title,
            archived=found.archived,
            created_at=found.created_at,
            updated_at=found.updated_at,
            turns=self._store.turn_count(session_id),
        )

    def conversations(
        self, owner_token: str, *, archived: bool = False, search: str | None = None
    ) -> ConversationList:
        if self._store is None:
            raise ServiceError("unavailable", 503)
        owner = self._store.owner_by_token(owner_token)
        if owner is None:
            raise ServiceError("forbidden", 403)
        return ConversationList(
            conversations=tuple(
                ConversationSummary(
                    conversation_id=item.conversation_id,
                    title=item.title,
                    archived=item.archived,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    turns=self._store.turn_count(item.conversation_id),
                )
                for item in self._store.list_conversations(owner, archived=archived, search=search)
            )
        )

    def conversation(self, session_id: str, token: str) -> ConversationDetail:
        summary = self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        return ConversationDetail(
            conversation=summary,
            messages=tuple(
                StoredMessage(
                    sequence=message.sequence,
                    turn_id=message.turn_id,
                    role=message.role,
                    text=message.text,
                    status=AnswerStatus(message.status) if message.status else None,
                    result_ref=message.result_ref,
                    result_version=message.result_version,
                    document_ref=message.document_ref,
                    created_at=message.created_at,
                )
                for message in self._store.messages(session_id)
            ),
            documents=tuple(
                # The stored format is text; the contract owns its allowed values.
                ConversationDocument.model_validate(
                    {
                        "document_ref": document.document_ref,
                        "name": document.name,
                        "document_format": document.document_format,
                        "bytes": document.byte_count,
                        "sha256": document.sha256,
                        "admitted_at": document.admitted_at,
                    }
                )
                for document in self._store.documents(session_id)
            ),
        )

    def runs(self, session_id: str, token: str) -> RunList:
        """Every run of this conversation, newest first; opening one runs nothing."""
        self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        return RunList(
            runs=tuple(self._run_summary(item, events=0) for item in self._store.runs(session_id))
        )

    def run(self, session_id: str, run_id: str, token: str) -> RunDetail:
        self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        found = self._store.run_of(session_id, run_id)
        if found is None:
            raise ServiceError("not_found", 404)
        steps = tuple(
            TraceStep(
                sequence=event.sequence,
                stage=event.stage,
                name=event.name,
                status=event.status,
                started_ms=event.started_ms,
                duration_ms=event.duration_ms,
                attributes=dict(event.attributes),
                detail=event.detail,
                parent=event.parent,
            )
            for event in self._store.events(run_id)
        )
        return RunDetail(run=self._run_summary(found, events=len(steps)), steps=steps)

    @staticmethod
    def _run_summary(item: StoredRun, *, events: int) -> RunSummary:
        return RunSummary.model_validate(
            {
                "run_id": item.run_id,
                "turn_id": item.turn_id,
                "question": item.question,
                "status": item.status,
                "answer_status": item.answer_status,
                "error": item.error,
                "result_ref": item.result_ref,
                "duration_ms": item.duration_ms,
                "started_at": item.started_at,
                "ended_at": item.ended_at,
                "events": events,
            }
        )

    def rate(self, session_id: str, token: str, request: FeedbackRequest) -> Feedback:
        """Rate the answer this turn actually produced, as it was shown."""
        self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        answered = next(
            (
                message
                for message in self._store.messages(session_id)
                if message.turn_id == request.turn_id and message.role == "assistant"
            ),
            None,
        )
        if answered is None:
            raise ServiceError("not_found", 404)
        run = next(
            (item for item in self._store.runs(session_id) if item.turn_id == request.turn_id),
            None,
        )
        stored = self._store.rate(
            session_id,
            turn_id=request.turn_id,
            answer_digest=answer_digest(answered.text),
            rating=request.rating,
            comment=request.comment,
            reasons=request.reasons,
            run_id=run.run_id if run is not None else None,
            result_version=answered.result_version,
        )
        return self._feedback(stored)

    def ratings(self, session_id: str, token: str) -> FeedbackList:
        self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        return FeedbackList(
            feedback=tuple(self._feedback(item) for item in self._store.ratings(session_id))
        )

    @staticmethod
    def _feedback(item: StoredFeedback) -> Feedback:
        return Feedback.model_validate(
            {
                "turn_id": item.turn_id,
                "answer_digest": item.answer_digest,
                "run_id": item.run_id,
                "result_version": item.result_version,
                "rating": item.rating,
                "comment": item.comment,
                "reasons": item.reasons,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
        )

    def update_conversation(
        self, session_id: str, token: str, update: ConversationUpdate
    ) -> ConversationSummary:
        self._reading(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        self._store.update_conversation(session_id, title=update.title, archived=update.archived)
        return self._reading(session_id, token)

    def admit_document(
        self, session_id: str, token: str, media_type: str, content: bytes
    ) -> DocumentAdmitted:
        """Authenticate, then admit outside the lock; the store owns bytes and limits."""
        with self._lock:
            session = self._owned(session_id, token)
            if self._document_store is None:
                raise ServiceError("unavailable", 503)
            if len(session.documents) >= MAX_DOCUMENTS:
                raise ServiceError("capacity", 429)
        admitted = DocumentAdmitted.model_validate(
            self._document_store(session_id, media_type, content).model_dump()
        )
        with self._lock:
            session = self._owned(session_id, token)
            session.documents.add(admitted.document_ref)
        return admitted

    def submit(self, session_id: str, token: str, question: Question) -> Turn:
        question = Question.model_validate(question.model_dump())
        digest = hashlib.sha256(
            question.model_dump_json(exclude={"request_id"}).encode()
        ).hexdigest()
        with self._lock:
            session = self._owned(session_id, token)
            previous = session.requests.get(question.request_id)
            if previous is not None:
                if previous[0] != digest:
                    raise ServiceError("request_conflict", 409)
                return session.turns[previous[1]].model_copy(deep=True)
            selected = None
            if question.selected_result_id is not None:
                selected = self._selected(session_id, session, question.selected_result_id)
                if self._selected_runner is None:
                    raise ServiceError("unavailable", 503)
            if question.document_ref is not None and question.document_ref not in session.documents:
                # Unknown, foreign and never-admitted references are indistinguishable.
                raise ServiceError("invalid_document", 422)
            if len(session.turns) >= MAX_TURNS:
                raise ServiceError("capacity", 429)
            if self._busy:
                raise ServiceError("busy", 409)
            turn_id = uuid4().hex
            turn = Turn(
                turn_id=turn_id,
                request_id=question.request_id,
                state="queued",
                events=(Event(sequence=1, state="queued", elapsed_ms=0),),
            )
            session.turns[turn_id] = turn
            session.requests[question.request_id] = (digest, turn_id)
            self._busy = True
            try:
                self._executor.submit(
                    self._run,
                    session_id,
                    turn_id,
                    question.question,
                    selected,
                    question.is_continuation,
                    question.document_ref,
                )
            except RuntimeError:
                self._busy = False
                del session.turns[turn_id]
                del session.requests[question.request_id]
                raise ServiceError("unavailable", 503) from None
            return turn.model_copy(deep=True)

    def _selected(self, session_id: str, session: _Session, result_ref: str) -> SelectedResult:
        matches = []
        for turn in session.turns.values():
            answer = turn.answer
            if (
                turn.state == "completed"
                and answer is not None
                and answer.status is AnswerStatus.ACCEPTED
                and answer.result is not None
                and answer.result.result_ref == result_ref
            ):
                matches.append(SelectedResult(turn.turn_id, result_ref, answer.result.version))
        if not matches and self._store is not None:
            # After a restart the turn is no longer in memory; the conversation's
            # own publications still name which result this reference is.
            matches = [
                SelectedResult(item.turn_id, item.result_ref, item.result_version)
                for item in self._store.publications(session_id)
                if item.result_ref == result_ref
            ]
        if len(matches) != 1:
            # Unknown/foreign/unpublished/ambiguous references are indistinguishable.
            raise ServiceError("invalid_result", 422)
        return matches[0]

    def get_turn(self, session_id: str, token: str, turn_id: str) -> Turn:
        with self._lock:
            session = self._owned(session_id, token)
            turn = session.turns.get(turn_id)
            if turn is None:
                raise ServiceError("not_found", 404)
            return turn.model_copy(deep=True)

    def _transition(
        self,
        session_id: str,
        turn_id: str,
        state: TurnState,
        start: float,
        *,
        answer: Answer | None = None,
        error: ErrorCode | None = None,
    ) -> None:
        with self._lock:
            old = self._sessions[session_id].turns[turn_id]
            self._sessions[session_id].turns[turn_id] = Turn(
                turn_id=turn_id,
                request_id=old.request_id,
                state=state,
                answer=answer,
                error=error,
                events=(
                    *old.events,
                    Event(
                        sequence=len(old.events) + 1,
                        state=state,
                        elapsed_ms=max(0, round((time.monotonic() - start) * 1000)),
                    ),
                ),
            )

    def _run(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selected: SelectedResult | None,
        is_continuation: bool | None = None,
        document_ref: str | None = None,
    ) -> None:
        start = time.monotonic()
        answer = None
        error: ErrorCode | None = None
        try:
            self._transition(session_id, turn_id, "running", start)
            if selected is None:
                output = (
                    self._runner(session_id, turn_id, question, is_continuation=is_continuation)
                    if document_ref is None
                    else self._runner(
                        session_id,
                        turn_id,
                        question,
                        is_continuation=is_continuation,
                        document_ref=document_ref,
                    )
                )
            else:
                if self._selected_runner is None:  # Defensive: never fall back to latest.
                    raise ServiceError("unavailable", 503)
                output = (
                    self._selected_runner(
                        session_id, turn_id, question, selected, is_continuation=is_continuation
                    )
                    if document_ref is None
                    else self._selected_runner(
                        session_id,
                        turn_id,
                        question,
                        selected,
                        is_continuation=is_continuation,
                        document_ref=document_ref,
                    )
                )
            answer = Answer.model_validate(output.model_dump())
            if len(answer.model_dump_json().encode()) > MAX_RESPONSE_BYTES - 4096:
                raise OutputRefused("output_limit")
        except PlanningFailed:
            error = "planning_failed"
        except ProviderError:
            error = "provider_failed"
        except OutputRefused:
            error = "output_limit"
        except ServiceError as failure:
            error = failure.code
        except Exception:
            # No exception formatting, prompts, paths or raw result fallbacks.
            error = "internal_error"
        finally:
            with self._lock:
                self._transition(
                    session_id,
                    turn_id,
                    "failed" if error else "completed",
                    start,
                    answer=answer if not error else None,
                    error=error,
                )
                self._busy = False

    def close(self) -> None:
        with self._lock:
            self._closed = True
        # Wait for the already admitted bounded provider call; do not claim that
        # a thread can be cancelled safely. No submitted question is retried.
        self._executor.shutdown(wait=True, cancel_futures=False)
