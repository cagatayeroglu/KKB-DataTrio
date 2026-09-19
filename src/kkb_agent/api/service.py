"""Bounded, process-local capabilities and one owned worker; no database sharing."""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Literal, Protocol, get_args
from uuid import uuid4

from pydantic import ValidationError

from kkb_agent.agent.cancellation import (
    CancelToken,
    TurnCancelled,
    cancellable,
    checkpoint,
)
from kkb_agent.agent.loop import MAX_HISTORY_TURNS, PlanningFailed
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.api.contracts import (
    MAX_DOCUMENTS,
    MAX_RESPONSE_BYTES,
    MAX_SESSIONS,
    MAX_TURNS,
    RESTRICTABLE_CAPABILITIES,
    TRACE_PREVIEW_CHARS,
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
    Result,
    RunDetail,
    RunList,
    RunSummary,
    RuntimeSettings,
    SessionCreated,
    SettingsUpdate,
    StoredMessage,
    TraceConversationList,
    TraceConversationSummary,
    TraceStep,
    TraceStepFull,
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

RUN_ERROR_CODES = frozenset(get_args(ErrorCode))


@dataclass(frozen=True, slots=True)
class TurnSettings:
    """What this owner switched off, and how much history they want shown.

    Only ever narrower than the deployment: `disabled` names capabilities the
    operator enabled, and `history_turns` is at most the built-in ceiling.
    """

    disabled: frozenset[str] = frozenset()
    history_turns: int | None = None

    def chosen(self) -> bool:
        return bool(self.disabled) or self.history_turns is not None


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
        # Passed only when the owner changed something, so a runtime that has no
        # settings to apply keeps its existing signature.
        settings: TurnSettings | None = None,
    ) -> Answer: ...


# M10-04: admits and stores one upload for a session; never on the analysis worker.
class DocumentStore(Protocol):
    def __call__(self, session_id: str, media_type: str, content: bytes) -> DocumentAdmitted: ...


class UrlDocumentStore(Protocol):
    def __call__(self, session_id: str, url: str) -> DocumentAdmitted: ...


class StoredResultReader(Protocol):
    def __call__(self, session_id: str, turn_id: str) -> Result: ...


class SessionCleaner(Protocol):
    def __call__(self, session_id: str) -> None: ...


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
        settings: TurnSettings | None = None,
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
    #: One cancel flag per admitted turn, read at the turn's checkpoints.
    cancels: dict[str, CancelToken] = field(default_factory=dict)
    uploads_inflight: int = 0


def answer_digest(text: str) -> str:
    """Identity of one shown answer, so a rating cannot drift onto a new one."""
    return hashlib.sha256(text.encode()).hexdigest()


def _stored_message_status(
    role: Literal["user", "assistant"], status: str | None
) -> AnswerStatus | Literal["queued", "running", "completed", "failed"] | None:
    """Project old/unknown rows safely without losing the surrounding conversation."""
    if role == "user":
        if status == "queued":
            return "queued"
        if status == "running":
            return "running"
        if status == "completed":
            return "completed"
        if status == "failed":
            return "failed"
        return None
    try:
        return AnswerStatus(status) if status is not None else None
    except ValueError:
        return None


class AnalysisService:
    """No implicit expiration/deletion/restart recovery or retries.

    Cancellation is explicit and cooperative (DEC-156): `cancel` raises a turn's
    flag and the turn stops at its next checkpoint, never mid-request.

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
        url_document_store: UrlDocumentStore | None = None,
        store: ConversationStore | None = None,
        ocr: bool = False,
        official_acquisition: bool = False,
        knowledge: bool = False,
        web_search: bool = False,
        web_url: bool = False,
        model: str | None = None,
        stored_result: StoredResultReader | None = None,
        session_cleanup: SessionCleaner | None = None,
    ):
        if mode not in ("kloudeks", "scripted"):
            raise ValueError("An explicit execution mode is required")
        self._runner = runner
        # Until the prepared workspace integration is supplied, explicit selection
        # fails closed. Never hand it to the old runner that cannot respect it.
        self._selected_runner = selected_runner
        # Uploads exist only when the operator supplied a store (--enable-uploads).
        self._document_store = document_store
        self._url_document_store = url_document_store
        # Conversations survive a restart only when the operator supplied one.
        self._store = store
        # Scanned pages are read only when the operator enabled OCR (DEC-149).
        self._ocr = ocr
        # Reviewed official series are fetched on first use only when enabled (DEC-155).
        self._official_acquisition = official_acquisition
        # The knowledge base routes exist only when the operator supplied its store.
        self._knowledge = knowledge
        self._web_search = web_search
        # Reading an address written in a question is the operator's switch too.
        self._web_url = web_url
        # The planner model's name, for the page's connection badge; never a switch.
        self._model = model
        # A published table read back from its receipt, after any restart.
        self._stored_result = stored_result
        self._session_cleanup = session_cleanup
        self._mode = mode
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kkb-analysis")
        self._busy = False
        self._closed = False

    def _make_session_room(self, *, keep: str | None = None) -> None:
        """Evict only an idle process-local handle; the owned store stays intact."""
        if len(self._sessions) < MAX_SESSIONS:
            return
        if self._store is None:
            raise ServiceError("capacity", 429)
        for identity, session in self._sessions.items():
            if identity == keep or session.cancels or session.uploads_inflight:
                continue
            if any(turn.state in ("queued", "running") for turn in session.turns.values()):
                continue
            del self._sessions[identity]
            return
        raise ServiceError("capacity", 429)

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
            if self._official_acquisition:
                capabilities = (*capabilities, "official_acquisition")
            if self._knowledge:
                capabilities = (*capabilities, "knowledge_base")
            if self._web_search:
                capabilities = (*capabilities, "web_search")
            return Health(execution_mode=self._mode, capabilities=capabilities, model=self._model)

    def _restrictable(self) -> tuple[str, ...]:
        """Restrictable capabilities this deployment actually offers."""
        offered = set(self.health().capabilities) | ({"web_url"} if self._web_url else set())
        return tuple(name for name in RESTRICTABLE_CAPABILITIES if name in offered)

    def _owner(self, owner_token: str) -> str:
        if self._store is None:
            raise ServiceError("unavailable", 503)
        owner = self._store.owner_by_token(owner_token)
        if owner is None:
            raise ServiceError("forbidden", 403)
        return owner

    def _settings_of(self, owner_id: str) -> TurnSettings:
        """Stored choices, narrowed to what this deployment still offers."""
        if self._store is None:  # pragma: no cover - callers check first
            return TurnSettings()
        stored = self._store.settings_of(owner_id)
        offered = set(self._restrictable())
        disabled = stored.get("disabled")
        chosen = (
            frozenset(name for name in disabled if isinstance(name, str) and name in offered)
            if isinstance(disabled, list)
            else frozenset()
        )
        turns = stored.get("history_turns")
        history = turns if isinstance(turns, int) and 0 <= turns <= MAX_HISTORY_TURNS else None
        return TurnSettings(disabled=chosen, history_turns=history)

    def settings(self, owner_token: str) -> RuntimeSettings:
        """What this deployment offers and what this browser switched off."""
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            owner = self._owner(owner_token)
            chosen = self._settings_of(owner)
        return RuntimeSettings(
            available=self._restrictable(),
            disabled=tuple(sorted(chosen.disabled)),
            history_turns=(
                chosen.history_turns if chosen.history_turns is not None else MAX_HISTORY_TURNS
            ),
            max_history_turns=MAX_HISTORY_TURNS,
        )

    def update_settings(self, owner_token: str, update: SettingsUpdate) -> RuntimeSettings:
        """Narrow this browser's own runtime; a capability can be switched off, never on."""
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            owner = self._owner(owner_token)
            if self._store is None:  # pragma: no cover - _owner refuses without a store
                raise ServiceError("unavailable", 503)
            current = self._settings_of(owner)
            offered = set(self._restrictable())
            if update.disabled is not None and not set(update.disabled) <= offered:
                # Nothing outside what the operator enabled can be named at all,
                # so a browser cannot ask for a capability by switching it "off".
                raise ServiceError("invalid_request", 422)
            disabled = (
                frozenset(update.disabled) if update.disabled is not None else current.disabled
            )
            history = (
                update.history_turns if update.history_turns is not None else current.history_turns
            )
            if history is not None and history > MAX_HISTORY_TURNS:
                raise ServiceError("invalid_request", 422)
            try:
                self._store.save_settings(
                    owner,
                    {
                        "disabled": sorted(disabled),
                        **({} if history is None else {"history_turns": history}),
                    },
                )
            except StoreError:
                raise ServiceError("unavailable", 503) from None
        return self.settings(owner_token)

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
            self._make_session_room()
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
        if self._store is not None and self._store.conversation(session_id) is None:
            raise ServiceError("not_found", 404)
        session = self._sessions.get(session_id)
        supplied = hashlib.sha256(token.encode()).digest()
        expected = session.token_digest if session else bytes(32)
        valid = secrets.compare_digest(supplied, expected)
        if session is not None and valid:
            # Dict insertion order is the idle-handle LRU; access refreshes recency.
            self._sessions.pop(session_id)
            self._sessions[session_id] = session
            return session
        # After a restart the conversation is in the store, not in memory: its own
        # token or its owner's key reopens it, an id on its own never does.
        if self._store is not None and self._store.opens(
            session_id, token=token, owner_token=token
        ):
            if session is None:
                self._make_session_room(keep=session_id)
                session = _Session(bytes(32))
                self._sessions[session_id] = session
            else:
                self._sessions.pop(session_id)
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

    def trace_conversations(
        self, owner_token: str, *, archived: bool = False, search: str | None = None
    ) -> TraceConversationList:
        """Owner-only trace index, including deleted chats that retain runs."""
        owner = self._owner(owner_token)
        if self._store is None:  # pragma: no cover - _owner refuses without a store
            raise ServiceError("unavailable", 503)
        return TraceConversationList(
            conversations=tuple(
                TraceConversationSummary(
                    conversation_id=item.conversation_id,
                    title=item.title,
                    archived=item.archived,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    turns=self._store.turn_count(item.conversation_id),
                    deleted=deleted,
                )
                for item, deleted in self._store.list_trace_conversations(
                    owner, archived=archived, search=search
                )
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
                    status=_stored_message_status(message.role, message.status),
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

    def stored_result(self, session_id: str, token: str, turn_id: str) -> Result:
        """The table a stored turn published, rebuilt from its receipt.

        Authorised exactly like reading the conversation (its token or the
        owner's key); the runner rebuilds cells and proof from the workspace, so
        a reopened conversation shows the table it showed then.
        """
        self._reading(session_id, token)
        if self._stored_result is None:
            raise ServiceError("unavailable", 503)
        return Result.model_validate(self._stored_result(session_id, turn_id).model_dump())

    def runs(self, session_id: str, token: str) -> RunList:
        """Every run of this conversation, newest first; opening one runs nothing."""
        self._trace_access(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        summaries: list[RunSummary] = []
        for item in self._store.runs(session_id):
            try:
                summaries.append(self._run_summary(item, events=0))
            except ValidationError:
                # Preserve the row in SQLite, but do not let one damaged legacy
                # contract make every other run unreadable.
                continue
        return RunList(runs=tuple(summaries))

    def run(self, session_id: str, run_id: str, token: str) -> RunDetail:
        self._trace_access(session_id, token)
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
                detail=(event.detail[:TRACE_PREVIEW_CHARS] if event.detail is not None else None),
                detail_chars=len(event.detail) if event.detail is not None else None,
                detail_complete=event.detail is None or len(event.detail) <= TRACE_PREVIEW_CHARS,
                parent=event.parent,
            )
            for event in self._store.events(run_id)
        )
        return RunDetail(run=self._run_summary(found, events=len(steps)), steps=steps)

    def run_step(self, session_id: str, run_id: str, sequence: int, token: str) -> TraceStepFull:
        """One step's recorded text in full: every prompt, output and tool return."""
        self._trace_access(session_id, token)
        if self._store is None:  # pragma: no cover - _reading refuses without a store
            raise ServiceError("unavailable", 503)
        if self._store.run_of(session_id, run_id) is None:
            raise ServiceError("not_found", 404)
        found = next(
            (event for event in self._store.events(run_id) if event.sequence == sequence), None
        )
        if found is None:
            raise ServiceError("not_found", 404)
        return TraceStepFull(sequence=found.sequence, name=found.name, detail=found.detail)

    @staticmethod
    def _run_summary(item: StoredRun, *, events: int) -> RunSummary:
        # Historical stores may contain exception prose (including provider
        # details). Never return it or let one row invalidate the entire list.
        if item.error is None or item.error in RUN_ERROR_CODES:
            error = item.error
        elif item.error.startswith(("ProviderError", "TransportError")):
            error = "provider_failed"
        else:
            error = "internal_error"
        return RunSummary.model_validate(
            {
                "run_id": item.run_id,
                "turn_id": item.turn_id,
                "question": item.question,
                "status": item.status,
                "answer_status": item.answer_status,
                "error": error,
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
            score=request.score,
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
                "score": item.score,
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

    def _trace_access(self, session_id: str, token: str) -> None:
        """A deleted chat is closed normally, but its retained traces stay owned."""
        if self._store is None:
            raise ServiceError("unavailable", 503)
        if not self._store.opens(session_id, token=token, owner_token=token, include_deleted=True):
            raise ServiceError("not_found", 404)

    def _clean_deleted(self, session_id: str) -> None:
        """Called only after the analysis and any upload for this session have stopped."""
        if self._store is None:
            return
        if self._session_cleanup is not None:
            self._session_cleanup(session_id)
        self._store.clear_session_artifacts(session_id)
        self._sessions.pop(session_id, None)

    def delete_conversation(self, session_id: str, owner_token: str) -> bool:
        """Owner-key-only soft delete. Running work is cancelled and cleaned on exit."""
        with self._lock:
            if self._store is None:
                raise ServiceError("unavailable", 503)
            if self._session_cleanup is None:
                # A deletion cannot succeed while leaving upload/lakehouse files
                # behind merely because a caller omitted the cleanup binding.
                raise ServiceError("unavailable", 503)
            if not self._store.opens(
                session_id, token=None, owner_token=owner_token, include_deleted=True
            ):
                raise ServiceError("not_found", 404)
            session = self._sessions.get(session_id)
            if session is not None and session.uploads_inflight:
                raise ServiceError("busy", 409)
            self._store.soft_delete(session_id)
            if session is not None:
                for flag in session.cancels.values():
                    flag.cancel()
                if session.cancels:
                    return True
            try:
                self._clean_deleted(session_id)
            except Exception:
                raise ServiceError("unavailable", 503) from None
            return True

    def delete_runs(self, session_id: str, owner_token: str) -> int:
        """A separate, irreversible owner-only action; soft deletion never calls it."""
        with self._lock:
            if self._store is None:
                raise ServiceError("unavailable", 503)
            if not self._store.opens(
                session_id, token=None, owner_token=owner_token, include_deleted=True
            ):
                raise ServiceError("not_found", 404)
            session = self._sessions.get(session_id)
            if session is not None and session.cancels:
                raise ServiceError("busy", 409)
            return self._store.delete_runs(session_id)

    def admit_document(
        self, session_id: str, token: str, media_type: str, content: bytes
    ) -> DocumentAdmitted:
        """Authenticate, then admit outside the lock; the store owns bytes and limits."""
        with self._lock:
            session = self._owned(session_id, token)
            if self._document_store is None:
                raise ServiceError("unavailable", 503)
            if "document_upload" in self._session_settings(session_id).disabled:
                # The owner switched uploads off for their own turns.
                raise ServiceError("unavailable", 503)
            if len(session.documents) >= MAX_DOCUMENTS:
                raise ServiceError("capacity", 429)
            session.uploads_inflight += 1
        try:
            admitted = DocumentAdmitted.model_validate(
                self._document_store(session_id, media_type, content).model_dump()
            )
        finally:
            with self._lock:
                session.uploads_inflight -= 1
        with self._lock:
            session = self._owned(session_id, token)
            session.documents.add(admitted.document_ref)
        return admitted

    def admit_document_from_url(self, session_id: str, token: str, url: str) -> DocumentAdmitted:
        """Admit a tabular document at a user-written address, like an upload.

        The same authentication and per-owner upload switch as a file upload; the
        fetch and admission rules live in the store. The address is the person's
        own request from the form, never a planner output or a document's content.
        """
        with self._lock:
            session = self._owned(session_id, token)
            if self._url_document_store is None:
                raise ServiceError("unavailable", 503)
            if "document_upload" in self._session_settings(session_id).disabled:
                raise ServiceError("unavailable", 503)
            if len(session.documents) >= MAX_DOCUMENTS:
                raise ServiceError("capacity", 429)
            session.uploads_inflight += 1
        try:
            admitted = DocumentAdmitted.model_validate(
                self._url_document_store(session_id, url).model_dump()
            )
        finally:
            with self._lock:
                session.uploads_inflight -= 1
        with self._lock:
            session = self._owned(session_id, token)
            session.documents.add(admitted.document_ref)
        return admitted

    def _session_settings(self, session_id: str) -> TurnSettings:
        """The settings of whoever owns this conversation; none when nobody does."""
        if self._store is None:
            return TurnSettings()
        owner = self._store.owner_of_conversation(session_id)
        return self._settings_of(owner) if owner is not None else TurnSettings()

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
            if len(session.turns) >= MAX_TURNS or (
                self._store is not None and self._store.turn_count(session_id) >= MAX_TURNS
            ):
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
            cancel = session.cancels[turn_id] = CancelToken()
            self._busy = True
            try:
                if self._store is not None:
                    self._store.append_message(
                        session_id,
                        turn_id=turn_id,
                        role="user",
                        text=question.question,
                        status="queued",
                        document_ref=question.document_ref,
                    )
                self._executor.submit(
                    self._run,
                    session_id,
                    turn_id,
                    question.question,
                    selected,
                    question.is_continuation,
                    question.document_ref,
                    cancel,
                )
            except Exception:
                self._busy = False
                del session.turns[turn_id]
                del session.requests[question.request_id]
                del session.cancels[turn_id]
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

    def cancel(self, session_id: str, token: str, turn_id: str) -> Turn:
        """Ask a queued or running turn to stop at its next checkpoint.

        Cooperative, never forced: a model request already in flight finishes,
        then the turn stops before the next planner call, tool step or answer.
        Cancelling a finished turn changes nothing and returns it as it is.
        """
        with self._lock:
            session = self._owned(session_id, token)
            turn = session.turns.get(turn_id)
            if turn is None:
                raise ServiceError("not_found", 404)
            flag = session.cancels.get(turn_id)
            if flag is not None and turn.state in ("queued", "running"):
                flag.cancel()
            return turn.model_copy(deep=True)

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
        cancel: CancelToken | None = None,
    ) -> None:
        # Every checkpoint inside this turn reads this turn's own flag.
        with cancellable(cancel) if cancel is not None else nullcontext():
            self._run_turn(session_id, turn_id, question, selected, is_continuation, document_ref)

    def _run_turn(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selected: SelectedResult | None,
        is_continuation: bool | None,
        document_ref: str | None,
    ) -> None:
        start = time.monotonic()
        answer = None
        error: ErrorCode | None = None
        try:
            self._transition(session_id, turn_id, "running", start)
            if self._store is not None:
                self._store.append_message(
                    session_id, turn_id=turn_id, role="user", text=question, status="running"
                )
            checkpoint("start")
            chosen = self._session_settings(session_id)
            extra: dict[str, object] = {"is_continuation": is_continuation}
            if document_ref is not None:
                extra["document_ref"] = document_ref
            if chosen.chosen():
                extra["settings"] = chosen
            if selected is None:
                output = self._runner(session_id, turn_id, question, **extra)  # type: ignore[arg-type]
            else:
                if self._selected_runner is None:  # Defensive: never fall back to latest.
                    raise ServiceError("unavailable", 503)
                output = self._selected_runner(
                    session_id,
                    turn_id,
                    question,
                    selected,
                    **extra,  # type: ignore[arg-type]
                )
            answer = Answer.model_validate(output.model_dump())
            if len(answer.model_dump_json().encode()) > MAX_RESPONSE_BYTES - 4096:
                raise OutputRefused("output_limit")
        except TurnCancelled:
            error = "cancelled"
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
                self._sessions[session_id].cancels.pop(turn_id, None)
                if self._store is not None:
                    self._store.append_message(
                        session_id,
                        turn_id=turn_id,
                        role="user",
                        text=question,
                        status="failed" if error else "completed",
                    )
                if self._store is not None and self._store.is_deleted(session_id):
                    try:
                        self._clean_deleted(session_id)
                    except Exception:
                        # The owner can retry deletion; no failed cleanup may
                        # reopen a deleted conversation or erase its trace.
                        logging.getLogger(__name__).warning("deleted_session_cleanup_failed")

    def close(self) -> None:
        with self._lock:
            self._closed = True
        # Wait for the already admitted bounded provider call; do not claim that
        # a thread can be cancelled safely. No submitted question is retried.
        self._executor.shutdown(wait=True, cancel_futures=False)
