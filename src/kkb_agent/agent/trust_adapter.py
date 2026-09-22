"""Present a loop turn in the shape the product already reads.

The API, the projection and the interface were built around `Answered`: a plan,
an execution outcome, the results and a gated answer. None of that has to change
for the loop to be tried — what the loop produces maps onto it directly, because
the pieces were always the same pieces. An action is a step, an observation is a
tool result, and what the model wrote is the answer.

This is a translation, not a second architecture. It exists so the loop can be
switched on without also rewriting the product around it, and it should be
deleted the day the projection reads the loop's own shape.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from kkb_agent.agent.executor import ExecutionOutcome, ValidatedPlan, ValidatedStep
from kkb_agent.agent.loop import Answered, Planned
from kkb_agent.agent.plan import PlanStep
from kkb_agent.agent.trust_answer import Answer
from kkb_agent.agent.trust_loop import TurnOutcome
from kkb_agent.agent.verifier import AnswerStatus, GatedAnswer, Verdict
from kkb_agent.core import AnalyticalResult


def as_answered(question: str, outcome: TurnOutcome, answer: Answer) -> Answered:
    """One loop turn, read as a plan that ran and an answer that was written."""
    steps = tuple(
        ValidatedStep(
            PlanStep(
                step_id=item.action.id,
                tool=item.action.tool,
                arguments=dict(item.action.arguments),
                assumption=item.action.note,
            ),
            _Arguments(),
        )
        for item in outcome.observations
    )
    plan = ValidatedPlan(
        question=question,
        steps=steps,
        clarification="unresolved_semantics" if outcome.ask else None,
        reply=None,
    )
    results = tuple(
        item.result.output
        for item in outcome.observations
        if item.ok and isinstance(item.result.output, AnalyticalResult)
    )
    published = _published(outcome, answer, results)
    return Answered(
        planned=Planned(plan=plan, attempts=outcome.iterations),
        outcome=ExecutionOutcome(
            results=tuple(item.result for item in outcome.observations),
            completed=outcome.exhausted is None,
        ),
        results=results,
        answer=_gated(answer),
        presented=published,
    )


def _published(
    outcome: TurnOutcome, answer: Answer, results: tuple[AnalyticalResult, ...]
) -> tuple[AnalyticalResult, ...]:
    """What the reader is shown: what the model named, else the last result."""
    wanted = answer.published or outcome.publish
    if wanted is not None:
        for item in outcome.observations:
            if item.action.id == wanted and isinstance(item.result.output, AnalyticalResult):
                return (item.result.output,)
    return results[-1:] if results else ()


def _gated(answer: Answer) -> GatedAnswer:
    """The model's text, with what could not be bound reported beside it.

    The status says what happened to the turn, not what happened to a sentence:
    nothing is removed, so an unbound figure qualifies the answer instead of
    shortening it.
    """
    limitations = tuple(dict.fromkeys((*answer.limitations, *answer.notes)))
    if answer.unverified:
        limitations = (
            *limitations,
            "Şu sayılar araç sonuçlarına bağlanamadı: " + " / ".join(answer.unverified),
        )
    status = AnswerStatus.QUALIFIED if (answer.unverified or limitations) else AnswerStatus.ACCEPTED
    if not answer.text.strip():
        status = AnswerStatus.ABSTAINED
    return GatedAnswer(status, answer.text, Verdict(True, ()), limitations=limitations)


class _Arguments(BaseModel):
    """A stand-in for the parsed arguments the projection never reads."""

    model_config = ConfigDict(extra="ignore")


__all__ = ["as_answered"]
