"""Bounded, process-local capabilities and one owned worker; no database sharing."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from kkb_agent.agent.loop import PlanningFailed
from kkb_agent.api.contracts import (
    MAX_RESPONSE_BYTES,
    MAX_SESSIONS,
    MAX_TURNS,
    Answer,
    ErrorCode,
    Event,
    Health,
    Question,
    SessionCreated,
    Turn,
    TurnState,
)
from kkb_agent.api.projection import OutputRefused
from kkb_agent.llm.provider import ProviderError

# Executed only on the one worker. A runtime must own/open/close its connection
# there and retain session state under the server-issued session_id.
Runner = Callable[[str, str, str], Answer]


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


class AnalysisService:
    """No implicit expiration/deletion/restart recovery, cancellation or retries.

    Eight sessions, twenty-four turns each, one active turn globally. Admission
    is atomic; capacity is checked before submitting to the executor, so its
    unbounded internal queue cannot accumulate application jobs.
    """

    def __init__(self, runner: Runner, *, mode: Literal["kloudeks", "scripted"]):
        if mode not in ("kloudeks", "scripted"):
            raise ValueError("An explicit execution mode is required")
        self._runner = runner
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
            return Health(execution_mode=self._mode)

    def create_session(self) -> SessionCreated:
        with self._lock:
            if self._closed:
                raise ServiceError("unavailable", 503)
            if len(self._sessions) >= MAX_SESSIONS:
                raise ServiceError("capacity", 429)
            session_id, token = uuid4().hex, secrets.token_urlsafe(32)
            self._sessions[session_id] = _Session(hashlib.sha256(token.encode()).digest())
            return SessionCreated(session_id=session_id, token=token)

    def _owned(self, session_id: str, token: str) -> _Session:
        if self._closed:
            raise ServiceError("unavailable", 503)
        session = self._sessions.get(session_id)
        supplied = hashlib.sha256(token.encode()).digest()
        expected = session.token_digest if session else bytes(32)
        valid = secrets.compare_digest(supplied, expected)
        if session is None or not valid:
            raise ServiceError("not_found", 404)
        return session

    def submit(self, session_id: str, token: str, question: Question) -> Turn:
        question = Question.model_validate(question.model_dump())
        digest = hashlib.sha256(question.question.encode()).hexdigest()
        with self._lock:
            session = self._owned(session_id, token)
            previous = session.requests.get(question.request_id)
            if previous is not None:
                if previous[0] != digest:
                    raise ServiceError("request_conflict", 409)
                return session.turns[previous[1]].model_copy(deep=True)
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
                self._executor.submit(self._run, session_id, turn_id, question.question)
            except RuntimeError:
                self._busy = False
                del session.turns[turn_id]
                del session.requests[question.request_id]
                raise ServiceError("unavailable", 503) from None
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

    def _run(self, session_id: str, turn_id: str, question: str) -> None:
        start = time.monotonic()
        answer = None
        error: ErrorCode | None = None
        try:
            self._transition(session_id, turn_id, "running", start)
            answer = Answer.model_validate(self._runner(session_id, turn_id, question).model_dump())
            if len(answer.model_dump_json().encode()) > MAX_RESPONSE_BYTES - 4096:
                raise OutputRefused("output_limit")
        except PlanningFailed:
            error = "planning_failed"
        except ProviderError:
            error = "provider_failed"
        except OutputRefused:
            error = "output_limit"
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
