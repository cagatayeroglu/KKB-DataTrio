"""One question in, one answer out. The whole turn, with nothing in between.

`TrustSession.answer` is the entry point the product calls. It holds a provider,
a tool registry and a budget, and it does two things with them: run the loop,
then ask the same model to report what the loop found. There is no planner, no
phase, no continuation and no separate writer to arbitrate between.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from duckdb import DuckDBPyConnection

from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.trust_answer import Answer, unsupported_figures, write_answer
from kkb_agent.agent.trust_loop import Budget, TurnOutcome, run_turn
from kkb_agent.agent.trust_memory import Conversation
from kkb_agent.agent.trust_prompt import INSTRUCTIONS
from kkb_agent.core import AnalyticalResult
from kkb_agent.llm.provider import LLMProvider


@dataclass(slots=True)
class Turn:
    """What one question produced: the answer and the work behind it."""

    answer: Answer
    outcome: TurnOutcome
    #: The conversation as this turn left it, ready for the next question.
    conversation: Conversation = field(default_factory=Conversation)


@dataclass(slots=True)
class TrustSession:
    provider: LLMProvider
    registry: ToolRegistry
    model: str | None = None
    budget: Budget = Budget()
    instructions: str = INSTRUCTIONS
    connection: DuckDBPyConnection | None = None
    tracer: Tracer | None = None
    #: What day it is. A model with no clock reasons about what can exist: live
    #: 2026-09-23, asked to read a report for August 2026, it answered that August
    #: 2026 "has not happened yet, so no such report would be published" and stopped
    #: looking — for a month that had ended three weeks earlier. The planned path was
    #: told the date all along; the loop was not. This is a fact, not an instruction.
    today: date | None = None

    def answer(
        self,
        question: str,
        *,
        context: Mapping[str, str] = {},
        data: Sequence[str] = (),
        conversation: Conversation | None = None,
        published: Mapping[str, AnalyticalResult] = {},
    ) -> Turn:
        """Run the loop for one question, then report what it found.

        `conversation` is what earlier turns left: the exchange as it was spoken, and
        the model's carry note when it wrote one. `published` is what those turns put
        on the table, seeded into the workspace so a tool handed one of those names
        finds it. Both are updated when the turn ends, so the next question starts
        where this one stopped. `data` is what this turn brings besides: the
        conversation's documents, the page an address in the question leads to, the
        table the reader selected.

        Everything the conversation holds reaches the model as data, not as
        instructions; only the date is the system's own statement.
        """
        memory = conversation or Conversation()
        known = dict(context)
        if self.today is not None:
            known["today"] = f"Bugünün tarihi: {self.today.isoformat()}."
        outcome = run_turn(
            question,
            provider=self.provider,
            registry=self.registry,
            instructions=self.instructions,
            model=self.model,
            budget=self.budget,
            context=known,
            data=[*memory.context(dict(published)).values(), *data],
            published=dict(published),
            tracer=self.tracer,
            review=lambda text, done: unsupported_figures(text, done, self.connection),
        )
        answer = write_answer(
            question,
            outcome,
            provider=self.provider,
            model=self.model,
            connection=self.connection,
            tracer=self.tracer,
            kept=tuple(published),
        )
        memory.remember(question, answer.text, outcome.state)
        return Turn(answer=answer, outcome=outcome, conversation=memory)


__all__ = ["TrustSession", "Turn"]
