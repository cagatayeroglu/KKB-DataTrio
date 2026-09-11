"""A live smoke of the Kloudeks transport that reports only safe metadata (M4-12).

Run by an operator, with the key and DEC-129's settings in the environment:

    python -m kkb_agent.llm.smoke

It sends one synthetic structured-generation request and one embedding request
through `KloudeksProvider` and prints JSON describing what happened: the model
identifier, the outcome or error category, attempts, finish reason, latency and
the embedding vector's dimension. It never prints the key or the model's raw
text, so the report can be pasted into a record as it is.

No test gate calls this against the network: a live call is a separately
authorized step (SEC-KLO-01). The offline tests drive `run_smoke` through a
mock transport instead.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from kkb_agent.llm.kloudeks import KloudeksProvider
from kkb_agent.llm.provider import LLMProvider, Message, ProviderError, Role

#: Synthetic on purpose: nothing from a user, a source or a workspace.
INSTRUCTION = "Reply with one JSON object and nothing else."
QUESTION = 'Return {"status": "ok", "total": N} where N is the sum of 2 and 3.'
EMBEDDING_TEXT = "konut kredisi faiz oranı"

Clock = Callable[[], float]


class SmokeReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    total: int


def run_smoke(provider: LLMProvider, *, clock: Clock = time.perf_counter) -> dict[str, object]:
    """One structured chat and one embedding call, reported as safe metadata."""
    chat = _chat(provider, clock)
    embedding = _embedding(provider, clock)
    return {
        "chat": chat,
        "embedding": embedding,
        "passed": chat["outcome"] == "ok" and embedding["outcome"] == "ok",
    }


def _chat(provider: LLMProvider, clock: Clock) -> dict[str, object]:
    started = clock()
    try:
        completion = provider.complete(
            [Message(Role.SYSTEM, INSTRUCTION), Message(Role.USER, QUESTION)], schema=SmokeReply
        )
    except ProviderError as error:
        # Provider messages are already reduced to a status or fault category.
        return {"outcome": type(error).__name__, "detail": str(error), **_took(started, clock)}
    parsed = completion.parsed
    return {
        "outcome": "ok",
        "model": completion.model,
        "attempts": completion.attempts,
        "finish_reason": completion.finish_reason,
        "answer_correct": isinstance(parsed, SmokeReply) and parsed.total == 5,
        **_took(started, clock),
    }


def _embedding(provider: LLMProvider, clock: Clock) -> dict[str, object]:
    started = clock()
    try:
        vectors = provider.embed([EMBEDDING_TEXT], kind="query")
    except ProviderError as error:
        return {"outcome": type(error).__name__, "detail": str(error), **_took(started, clock)}
    return {
        "outcome": "ok",
        "vectors": len(vectors),
        "dimension": len(vectors[0]),
        **_took(started, clock),
    }


def _took(started: float, clock: Clock) -> dict[str, object]:
    return {"latency_ms": round((clock() - started) * 1000)}


def main() -> int:
    try:
        provider = KloudeksProvider.from_env()
    except ProviderError as error:
        # Configuration errors name settings, never their values.
        print(
            json.dumps(
                {"passed": False, "configuration": type(error).__name__, "detail": str(error)}
            )
        )
        return 2
    with provider:
        report = run_smoke(provider)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":  # pragma: no cover - operator entry point
    sys.exit(main())
