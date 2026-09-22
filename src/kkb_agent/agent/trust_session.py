"""One question in, one answer out. The whole turn, with nothing in between.

`TrustSession.answer` is the entry point the product calls. It holds a provider,
a tool registry and a budget, and it does two things with them: run the loop,
then ask the same model to report what the loop found. There is no planner, no
phase, no continuation and no separate writer to arbitrate between.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from duckdb import DuckDBPyConnection

from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.trust_answer import Answer, write_answer
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

    def answer(
        self,
        question: str,
        *,
        context: Mapping[str, str] = {},
        conversation: Conversation | None = None,
        published: Mapping[str, AnalyticalResult] = {},
    ) -> Turn:
        """Run the loop for one question, then report what it found.

        `conversation` is what earlier turns left: the model's own carry note and
        the exchange as it was spoken. `published` is what those turns put on the
        table, seeded into the workspace so a tool handed one of those names finds
        it. Both are updated when the turn ends, so the next question starts where
        this one stopped.
        """
        memory = conversation or Conversation()
        outcome = run_turn(
            question,
            provider=self.provider,
            registry=self.registry,
            instructions=self.instructions,
            model=self.model,
            budget=self.budget,
            context={**memory.context(dict(published)), **context},
            published=dict(published),
            tracer=self.tracer,
        )
        answer = write_answer(
            question,
            outcome,
            provider=self.provider,
            model=self.model,
            connection=self.connection,
        )
        memory.remember(question, answer.text, outcome.state)
        return Turn(answer=answer, outcome=outcome, conversation=memory)


__all__ = ["TrustSession", "Turn"]
