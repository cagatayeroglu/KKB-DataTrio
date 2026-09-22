"""The provider boundary (DEC-122, implementing DEC-102).

Everything the system knows about a language model passes through this
interface. DEC-129 has since fixed Kloudeks' endpoint and model identifiers, and
`kloudeks.KloudeksProvider` is the one transport behind it. What is still open —
structured-output guarantees, limits, the embedding dimension (Q-K-02..05) —
stays confined here, so an answer edits one package rather than the planner,
the router and every tool.

It also keeps DEC-002 checkable by inspection: one module builds the client
that carries the key, and no hosted-LLM endpoint or key variable appears here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

EmbeddingKind = Literal["query", "passage"]


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    #: What a tool returned, addressed to the call that asked for it.
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool the model asked for, as it named it.

    `arguments` is the raw JSON string the model produced. It is parsed where the
    tool is dispatched, so a malformed argument is that tool's observation rather
    than a transport error that ends the turn.
    """

    id: str
    name: str
    arguments: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Message:
    """One turn handed to a model.

    `content` is redacted from the representation: a prompt carries the user's
    question and selected source rows, and neither belongs in a traceback.
    """

    role: Role
    content: str = field(repr=False)
    #: Set on an assistant turn that asked for tools instead of writing prose.
    tool_calls: tuple[ToolCall, ...] = ()
    #: Set on a TOOL turn: which call this result answers.
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class Usage:
    """What a request cost, as the platform reported it; never estimated here."""

    prompt_tokens: int
    completion_tokens: int
    #: Hidden reasoning tokens inside completion_tokens, when the platform reports them.
    reasoning_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Completion:
    """What a model returned, plus what it cost to get there.

    `parsed` is populated only when a schema was requested and validation
    passed. `attempts` counts every request made, so a caller can see when the
    repair loop was doing the work.
    """

    text: str = field(repr=False)
    model: str
    attempts: int = 1
    parsed: BaseModel | None = field(default=None, repr=False)
    finish_reason: str | None = None
    #: What the model asked to run. Empty when it answered in prose instead.
    tool_calls: tuple[ToolCall, ...] = ()
    #: Present only when the platform returned usage counts.
    usage: Usage | None = None
    #: The model's reasoning text, when it returned one beside the answer. It is
    #: never used as an answer; it is kept so a trace shows why a call was slow.
    reasoning: str | None = field(default=None, repr=False)


class ProviderError(RuntimeError):
    """Base for every provider failure. Never carries prompt text or credentials."""


class ConfigurationError(ProviderError):
    """Configuration is missing or unusable. Names the setting, never its value."""


class TransportError(ProviderError):
    """A transient failure. Safe to retry within the configured budget."""


class RateLimited(TransportError):
    """The platform refused for quota reasons; retrying immediately will not help."""


class ModelUnavailable(ProviderError):
    """The requested model is not offered. Not transient; do not retry."""


class Refused(ProviderError):
    """The model declined to answer. A product outcome, not a transport fault."""


class SchemaViolation(ProviderError):
    """Output did not satisfy the requested schema after the repair budget."""

    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


class CapabilityUnavailable(ProviderError):
    """A capability was used that this deployment has not confirmed it has."""


@runtime_checkable
class LLMProvider(Protocol):
    """The only surface through which the product reaches a model.

    Deliberately three methods. Anything a caller wants that is not here is
    either a prompt concern or a decision that belongs above this boundary.
    """

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
        tools: Sequence[Mapping[str, object]] | None = None,
    ) -> Completion:
        """Generate text, optionally validated against a schema.

        Passing a schema means the caller needs a typed object, not prose. The
        implementation is responsible for getting there — through the platform's
        structured output where it exists, and through repair and retry where it
        does not — or for raising `SchemaViolation`.
        """
        ...

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        """Embed text for retrieval.

        `kind` is not decoration. An E5-family model silently loses quality when
        queries and passages are not prefixed differently, and the failure is
        invisible without a recall measurement. The convention itself is Q-K-05.
        """
        ...

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        """Read an image. Output is untrusted extraction, never a verified number."""
        ...
