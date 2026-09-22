"""The answer, written by the same model, checked without being cut.

The old arrangement called a separate writer and then deleted from its draft any
sentence holding a number the verifier could not bind. That check was sound and
its placement was not: over one day of live turns it removed five correct
sentences — four months listed with their four correct balances, a movement
whose direction Turkish puts in the verb, a figure the writer had said was
rounded, and the two most relevant search results because a publication id sat
in a URL. Each was a true sentence, and the reader was told instead that nothing
verifiable could be produced.

So the verification stays and the deletion goes. Every figure is still bound to
what the tools returned; a figure that does not bind is reported beside the
answer rather than taking its sentence with it. A model that invents a number is
still visible, and a model that writes a correct sentence keeps it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from duckdb import DuckDBPyConnection

from kkb_agent.agent.trust_loop import TurnOutcome
from kkb_agent.agent.trust_prompt import EXHAUSTED, WRITER
from kkb_agent.agent.verifier import gate_answer
from kkb_agent.core import AnalyticalResult
from kkb_agent.llm.provider import LLMProvider, Message, Role

#: Said once, beside the answer, when a figure could not be bound to a result.
UNVERIFIED: Final = "Şu sayı araç sonuçlarına bağlanamadı, okurken dikkate alın: "


@dataclass(slots=True)
class Answer:
    """What the reader gets: the model's own text, plus what could not be checked."""

    text: str
    published: str | None = None
    limitations: list[str] = field(default_factory=list)
    #: Figures the verifier could not bind. Reported, never removed.
    unverified: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _computed(outcome: TurnOutcome) -> dict[str, AnalyticalResult]:
    """Every analytical result this turn produced, under the id the model gave it."""
    found: dict[str, AnalyticalResult] = {}
    for item in outcome.observations:
        if item.ok and isinstance(item.result.output, AnalyticalResult):
            found[item.action.id] = item.result.output
    return found


def write_answer(
    question: str,
    outcome: TurnOutcome,
    *,
    provider: LLMProvider,
    model: str | None = None,
    connection: DuckDBPyConnection | None = None,
) -> Answer:
    """Ask the model to report what its own tools returned, then check the figures."""
    if outcome.ask:
        return Answer(text=outcome.ask)

    results = _computed(outcome)
    evidence = "\n\n".join(
        f"{identifier}: {result.model_dump_json(exclude_none=True)}"
        for identifier, result in results.items()
    )
    messages = [
        Message(Role.SYSTEM, WRITER),
        Message(Role.USER, question),
        Message(Role.USER, evidence or "Bu turda hesaplanmış bir sonuç yok."),
    ]
    if outcome.state:
        messages.insert(2, Message(Role.ASSISTANT, outcome.state))
    draft = provider.complete(messages, model=model).text.strip()

    answer = Answer(
        text=draft, published=outcome.publish or (list(results)[-1] if results else None)
    )
    if outcome.exhausted:
        answer.notes.append(EXHAUSTED.get(outcome.exhausted, outcome.exhausted))
    answer.notes.extend(item.action.note for item in outcome.observations if item.action.note)
    for item in outcome.observations:
        answer.limitations.extend(item.result.warnings)

    if results and draft:
        # The same check as before, read as a report: what it would have cut is
        # named instead, and the model's sentence stays where the model put it.
        checked = gate_answer(draft, results, connection)
        answer.unverified = [omitted.text for omitted in checked.omitted if omitted.text.strip()]
        answer.limitations.extend(checked.limitations)
    return answer


__all__ = ["Answer", "UNVERIFIED", "write_answer"]
