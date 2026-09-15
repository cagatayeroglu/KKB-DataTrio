"""A scripted provider for credential-free building and testing (M4-09).

This is not a mock in the test-only sense. The planner, the router and every
tool have to be exercised without a key or a network, and what they run
against should behave like the platform is expected to behave — including
badly. Scripting refusals, rate limits and malformed JSON here is how those
paths get tested; the real transport is `kloudeks.KloudeksProvider`.

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
)
from kkb_agent.llm.structured import complete_with_repair

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
        def ask(conversation: list[Message]) -> tuple[str, str | None]:
            self.seen.append(list(conversation))
            return self._next(), None

        return complete_with_repair(
            ask,
            messages,
            schema=schema,
            max_attempts=self.max_attempts,
            model=model or self.model,
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
