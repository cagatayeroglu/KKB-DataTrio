"""Stopping a turn the person no longer wants, at the next safe point.

A Python thread cannot be killed safely, and a model request in flight cannot be
taken back. What can be done honestly is cooperative: a cancel request raises a
flag, and the turn stops at the next checkpoint — before a planner call, before a
tool step, before the answer is written. Work already done stays recorded in the
trace; nothing is published from a cancelled turn.

The flag travels in a context variable rather than through every signature, so
the planning loop and the executor check it without learning about the service
that set it. Outside a service turn there is no flag and `checkpoint` is a no-op.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class TurnCancelled(RuntimeError):
    """The person cancelled this turn; raised at a checkpoint, never mid-request."""


class CancelToken:
    """One turn's cancel flag; set from the request thread, read from the worker."""

    __slots__ = ("_event", "where")

    def __init__(self) -> None:
        self._event = threading.Event()
        #: The checkpoint the turn stopped at, for the trace.
        self.where: str | None = None

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


_current: ContextVar[CancelToken | None] = ContextVar("kkb_turn_cancel", default=None)


@contextmanager
def cancellable(token: CancelToken) -> Iterator[CancelToken]:
    """Make `token` the flag every checkpoint in this context reads."""
    reset = _current.set(token)
    try:
        yield token
    finally:
        _current.reset(reset)


def checkpoint(where: str) -> None:
    """Stop here if this turn was cancelled; otherwise do nothing."""
    token = _current.get()
    if token is not None and token.cancelled:
        token.where = where
        raise TurnCancelled(where)
