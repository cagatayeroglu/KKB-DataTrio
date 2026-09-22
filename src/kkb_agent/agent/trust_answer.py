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

import json
from dataclasses import dataclass, field
from typing import Final

from duckdb import DuckDBPyConnection
from pydantic import BaseModel

from kkb_agent.agent.trust_loop import TurnOutcome
from kkb_agent.agent.trust_prompt import EXHAUSTED, WRITER
from kkb_agent.agent.verifier import gate_answer
from kkb_agent.core import AnalyticalResult
from kkb_agent.llm.provider import LLMProvider, Message, Role

#: How much of one tool's output the writer is shown before it is clipped.
MAX_EVIDENCE_CHARS = 20_000

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


def _evidence(outcome: TurnOutcome) -> str:
    """Everything the tools returned, not only what happened to be a table.

    Reporting only `AnalyticalResult` left the writer with nothing to say about a
    page it had just read: a document, a search listing and an `inspect` window
    are evidence too, and "bu PDF'teki verilerle yorumla" is answered from exactly
    those. A failed observation travels as well, so the answer can say what did
    not work rather than implying it was never tried.
    """
    blocks: list[str] = []
    for item in outcome.observations:
        payload = item.result.output
        if payload is None:
            if item.result.warnings:
                blocks.append(
                    f"{item.action.id} ({item.action.tool}) sonuç vermedi: "
                    + "; ".join(item.result.warnings)
                )
            continue
        if isinstance(payload, BaseModel):
            body = payload.model_dump_json(exclude_none=True)
        else:
            body = json.dumps(payload, ensure_ascii=False, default=str)
        blocks.append(f"{item.action.id} ({item.action.tool}): {body[:MAX_EVIDENCE_CHARS]}")
    return "\n\n".join(blocks)


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
    if outcome.reply:
        # The model already wrote the answer, in the same conversation that gathered
        # the evidence. Asking a second call to say it again would cost a turn and
        # separate the words from what they were written against.
        return _checked(Answer(text=outcome.reply), outcome, results, connection)
    evidence = _evidence(outcome)
    messages = [
        Message(Role.SYSTEM, WRITER),
        Message(Role.USER, question),
        Message(Role.USER, evidence or "Bu turda hiçbir araç sonuç döndürmedi."),
    ]
    if outcome.state:
        messages.insert(2, Message(Role.ASSISTANT, outcome.state))
    draft = provider.complete(messages, model=model).text.strip()

    answer = Answer(text=draft)
    return _checked(answer, outcome, results, connection)


def _checked(
    answer: Answer,
    outcome: TurnOutcome,
    results: dict[str, AnalyticalResult],
    connection: DuckDBPyConnection | None,
) -> Answer:
    """Attach what the turn knows, then report any figure that did not bind."""
    answer.published = outcome.publish or (list(results)[-1] if results else None)
    if outcome.exhausted:
        answer.notes.append(EXHAUSTED.get(outcome.exhausted, outcome.exhausted))
    answer.notes.extend(item.action.note for item in outcome.observations if item.action.note)
    for item in outcome.observations:
        answer.limitations.extend(item.result.warnings)

    if results and answer.text:
        # The same check as before, read as a report: what it would have cut is
        # named instead, and the model's sentence stays where the model put it.
        checked = gate_answer(answer.text, results, connection)
        answer.unverified = [omitted.text for omitted in checked.omitted if omitted.text.strip()]
        answer.limitations.extend(checked.limitations)
    return answer


__all__ = ["Answer", "UNVERIFIED", "write_answer"]
