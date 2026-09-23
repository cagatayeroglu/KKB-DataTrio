"""What actually happened in a turn, recorded where it happens (M14-02).

The turn events the API used to expose were four states with a stopwatch:
queued, running, completed, failed. That cannot answer the questions people
actually ask of an analytical agent — which context went to the model, what it
proposed, why a plan was rejected, which tool ran with which arguments, what it
returned, and where the time went.

A `Tracer` collects those events as they occur. Three rules keep it honest:

- **Only observed facts.** Every event is written by the code that did the work,
  with its own monotonic timing. Nothing is replayed, back-dated or inferred, and
  a model's hidden reasoning is never reconstructed: what is recorded is what the
  model actually returned (its plan, its draft) and what the harness decided.
- **Bounded and redacted.** Events, attributes and detail text are capped, and
  configured secrets are removed before anything is stored. Large tool output is
  summarized here; the values themselves stay in the lakehouse.
- **No extra model call.** Tracing never asks a model to explain anything.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Final

from pydantic import JsonValue

#: Safety ceilings, not summaries: a development trace records every prompt, model
#: output and tool return in full, and only a pathological turn reaches these.
MAX_EVENTS: Final = 5_000
MAX_DETAIL_CHARS: Final = 2_000_000
MAX_ATTRIBUTE_CHARS: Final = 4_000
MAX_ATTRIBUTES: Final = 64
#: Failures whose message is recorded as the step's reason: validation faults that
#: describe a field and a constraint, and the provider's transport family, whose
#: messages are fixed templates with at most a status code or an exception class.
_TOLD: Final = frozenset(
    {
        "SchemaViolation",
        "PlanRejected",
        "PlanningFailed",
        "TransportError",
        "RateLimited",
        "ModelUnavailable",
    }
)
#: Stages a reader can filter by; each is a phase of one turn.
STAGES: Final = (
    "request",
    "context",
    "planning",
    "discovery",
    "tool",
    "verification",
    "publication",
    "answer",
)


def _dropped(count: int) -> str:
    return f"… [{count} more characters]"


def _clip(text: str, limit: int) -> str:
    """Shorten to `limit` characters, the note about what was dropped included.

    The note used to be appended after the cut, so a step that reached the
    ceiling came back longer than the ceiling and its own contract refused it:
    reading that step answered 500 (finding F4-iz-6).
    """
    if len(text) <= limit:
        return text
    head = limit
    for _ in range(4):
        adjusted = max(0, limit - len(_dropped(len(text) - head)))
        if adjusted == head:
            break
        head = adjusted
    return (text[:head] + _dropped(len(text) - head))[:limit]


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One recorded step: what ran, how it ended, how long it took."""

    sequence: int
    stage: str
    name: str
    status: str
    started_ms: int
    duration_ms: int
    attributes: dict[str, JsonValue] = field(default_factory=dict)
    #: Bounded text a reader may open: a prompt, a model's output, a tool preview.
    detail: str | None = None
    parent: int | None = None


class Span:
    """A step being recorded; attributes and detail are set as they become known."""

    __slots__ = ("attributes", "detail", "name", "sequence", "stage", "status")

    def __init__(self, sequence: int, stage: str, name: str) -> None:
        self.sequence = sequence
        self.stage = stage
        self.name = name
        self.status = "ok"
        self.attributes: dict[str, JsonValue] = {}
        self.detail: str | None = None

    def set(self, **attributes: JsonValue) -> None:
        for key, value in attributes.items():
            if len(self.attributes) >= MAX_ATTRIBUTES:
                return
            if isinstance(value, str):
                value = _clip(value, MAX_ATTRIBUTE_CHARS)
            self.attributes[key] = value

    def describe(self, detail: str) -> None:
        """Attach the step's own text: a prompt, a model output, a tool preview."""
        self.detail = detail

    def failed(self, category: str, reason: str | None = None) -> None:
        self.status = "failed"
        self.attributes["error_category"] = category
        if reason:
            self.attributes["error_reason"] = reason[:400]


class Tracer:
    """Collects one turn's events in order; not thread-safe, one turn at a time."""

    def __init__(
        self,
        *,
        redactions: Sequence[str] = (),
        clock: object = None,
        detail: bool = True,
        sink: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        # A sink receives each event as it is recorded, so a reader can follow a
        # run while it is still going and a crash leaves what already happened.
        self._sink = sink
        self._events: list[TraceEvent] = []
        self._redactions = tuple(value for value in redactions if value)
        self._start = time.monotonic()
        self._next = 0
        self._detail = detail

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def _elapsed(self) -> int:
        return max(0, round((time.monotonic() - self._start) * 1000))

    def _safe(self, text: str) -> str:
        for secret in self._redactions:
            text = text.replace(secret, "[redacted]")
        return text

    def _record(
        self,
        span: Span,
        started_ms: int,
        duration_ms: int,
        parent: int | None,
    ) -> None:
        if len(self._events) >= MAX_EVENTS:
            return
        attributes = {
            key: (self._safe(value) if isinstance(value, str) else value)
            for key, value in span.attributes.items()
        }
        detail = None
        if span.detail is not None and self._detail:
            detail = _clip(self._safe(span.detail), MAX_DETAIL_CHARS)
        event = TraceEvent(
            sequence=span.sequence,
            stage=span.stage,
            name=span.name,
            status=span.status,
            started_ms=started_ms,
            duration_ms=duration_ms,
            attributes=attributes,
            detail=detail,
            parent=parent,
        )
        self._events.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:  # noqa: BLE001 - recording must never break the turn
                self._sink = None

    @contextmanager
    def span(self, stage: str, name: str, *, parent: int | None = None) -> Iterator[Span]:
        """Record one step, including the exception that ended it."""
        self._next += 1
        span = Span(self._next, stage, name)
        started = self._elapsed()
        begin = time.monotonic()
        try:
            yield span
        except BaseException as error:
            # These carry a deliberately value-free description — a field path and a
            # constraint name, never the text that failed — so the reason can be kept.
            # Without it a turn that died on validation says only "SchemaViolation",
            # and 113 seconds of planning left nothing anyone could act on
            # (live 2026-09-22). Everything else records its class alone.
            #
            # The provider's transport family is told too. Every message it raises is a
            # fixed template carrying at most an HTTP status or an `httpx` exception class
            # name — never a body, a URL or a credential (`llm.kloudeks`, all seven raise
            # sites) — and the tracer still redacts what it records. Without it the jury's
            # first live A1 (2026-09-23, run c00e2ae1) failed after 12 s with only
            # "TransportError" in the trace, and a server 5xx, a dropped connection and a
            # DNS failure could not be told apart after the fact.
            told = type(error).__name__ in _TOLD
            span.failed(type(error).__name__, str(error) if told else None)
            self._record(span, started, max(0, round((time.monotonic() - begin) * 1000)), parent)
            raise
        self._record(span, started, max(0, round((time.monotonic() - begin) * 1000)), parent)

    def event(
        self,
        stage: str,
        name: str,
        *,
        status: str = "ok",
        detail: str | None = None,
        parent: int | None = None,
        **attributes: JsonValue,
    ) -> int:
        """Record a step with no duration of its own; returns its sequence."""
        self._next += 1
        span = Span(self._next, stage, name)
        span.status = status
        span.set(**attributes)
        if detail is not None:
            span.describe(detail)
        self._record(span, self._elapsed(), 0, parent)
        return span.sequence


def prompt_outline(messages: Sequence[object]) -> str:
    """The shape of the context sent to a model: every message, its role and size.

    Each message is also recorded as its own event, so a reader opens the one
    they came for instead of reading a truncated wall of text.
    """
    lines = []
    for index, message in enumerate(messages, 1):
        role = getattr(getattr(message, "role", None), "value", "?")
        content = str(getattr(message, "content", ""))
        opening = " ".join(content.split())[:160]
        lines.append(f"{index}. [{role}] {len(content.encode())} bytes: {opening}")
    return "\n".join(lines)


def preview(values: Mapping[str, JsonValue]) -> str:
    """A short, ordered rendering of a tool's own output facts."""
    return "\n".join(f"{key}: {value}" for key, value in values.items())
