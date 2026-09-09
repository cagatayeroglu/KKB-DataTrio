"""A scripted provider for building against while the platform is unresolved (M4-09).

This is not a mock in the test-only sense. Q-K-01 through Q-K-03 are unanswered,
so the planner, the router and every tool have to be written and exercised
against something, and that something should behave like the platform is
expected to behave — including badly. Scripting refusals, rate limits and
malformed JSON here is how those paths get tested before a credential exists.

It performs no networking of any kind, which is also what makes it safe to run
in credential-free CI.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel

from kkb_agent.llm.provider import (
    CapabilityUnavailable,
    Completion,
    EmbeddingKind,
    Message,
    ProviderError,
    Role,
    SchemaViolation,
)
from kkb_agent.llm.structured import parse_structured, repair_feedback

#: A scripted turn: text to return, or an error to raise instead.
Scripted = str | ProviderError


@dataclass
class ScriptedProvider:
    """Replays queued responses, applying the real repair loop around them.

    The retry behaviour is deliberately the production one rather than a
    simplification, so a test that scripts two malformed responses followed by a
    good one is testing the loop that will actually run.
    """

    responses: list[Scripted] = field(default_factory=list)
    model: str = "scripted-model"
    max_attempts: int = 3
    embedding_dimension: int | None = 8
    supports_vision: bool = False
    #: Every prompt seen, so a caller can assert what the model was told.
    seen: list[list[Message]] = field(default_factory=list, repr=False)

    def queue(self, *responses: Scripted) -> ScriptedProvider:
        self.responses.extend(responses)
        return self

    def _next(self) -> str:
        if not self.responses:
            raise ProviderError("Scripted provider ran out of responses")
        item = self.responses.pop(0)
        if isinstance(item, ProviderError):
            raise item
        return item

    def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        schema: type[BaseModel] | None = None,
    ) -> Completion:
        conversation = list(messages)
        last_problem = ""
        for attempt in range(1, self.max_attempts + 1):
            self.seen.append(list(conversation))
            text = self._next()
            if schema is None:
                return Completion(text=text, model=model or self.model, attempts=attempt)
            try:
                parsed = parse_structured(text, schema)
            except SchemaViolation as error:
                last_problem = str(error)
                if attempt == self.max_attempts:
                    break
                # Feed the fault back rather than retrying the same prompt: an
                # unchanged prompt tends to reproduce the same malformation.
                conversation = [
                    *conversation,
                    Message(Role.ASSISTANT, text),
                    Message(Role.USER, repair_feedback(schema, last_problem)),
                ]
                continue
            return Completion(text=text, model=model or self.model, attempts=attempt, parsed=parsed)
        raise SchemaViolation(
            f"Schema not satisfied after {self.max_attempts} attempt(s): {last_problem}"
        )

    def embed(self, texts: Sequence[str], *, kind: EmbeddingKind) -> list[list[float]]:
        if self.embedding_dimension is None:
            raise CapabilityUnavailable("This deployment has no embedding model")
        # Deterministic and prefix-sensitive, so a caller that forgets to
        # distinguish queries from passages gets different vectors and a test
        # can catch it. These are not semantic embeddings.
        offset = 0.5 if kind == "query" else 0.0
        return [
            [
                ((hash((kind, text, index)) % 1000) / 1000.0) + offset
                for index in range(self.embedding_dimension)
            ]
            for text in texts
        ]

    def vision(self, image_bytes: bytes, prompt: str) -> Completion:
        if not self.supports_vision:
            raise CapabilityUnavailable("This deployment has no vision model")
        if not image_bytes:
            raise ProviderError("No image supplied")
        return Completion(text=self._next(), model=self.model)


def scripted(*responses: Scripted, **kwargs: object) -> ScriptedProvider:
    """Convenience constructor for a provider with a queue already loaded."""
    provider = ScriptedProvider(**kwargs)  # type: ignore[arg-type]
    provider.queue(*responses)
    return provider


def transcript(provider: ScriptedProvider) -> Iterable[str]:
    """Roles seen in the last conversation, for asserting the repair loop ran."""
    return (message.role.value for message in (provider.seen[-1] if provider.seen else []))
