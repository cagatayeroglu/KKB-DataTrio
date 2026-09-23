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

from typing import Final

from pydantic import BaseModel, ConfigDict

from kkb_agent.agent.executor import (
    ExecutionOutcome,
    ValidatedPlan,
    ValidatedStep,
    analytical,
)
from kkb_agent.agent.loop import Answered, Planned
from kkb_agent.agent.plan import PlanStep
from kkb_agent.agent.trust_answer import Answer
from kkb_agent.agent.trust_loop import TurnOutcome
from kkb_agent.agent.verifier import AnswerStatus, GatedAnswer, Verdict
from kkb_agent.api.projection import MAX_NOTICE_CHARS, MAX_NOTICES, MAX_TEXT_CHARS
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
        measured
        for item in outcome.observations
        if item.ok and (measured := analytical(item.result.output)) is not None
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
    """What the reader is shown: what the model named, or what the answer defaulted to.

    `answer.published` already holds the default when the model named nothing (the last
    result built this turn, never a plain read). Falling back here to whatever result
    came last undid that and published an intermediate read (QA-A3, 2026-09-23).
    """
    wanted = answer.published or outcome.publish
    if wanted is not None:
        for item in outcome.observations:
            if item.action.id == wanted and (measured := analytical(item.result.output)):
                return (measured,)
    return ()


def _gated(answer: Answer) -> GatedAnswer:
    """The model's text, with what could not be bound reported beside it.

    The status says what happened to the turn, not what happened to a sentence:
    nothing is removed, so an unbound figure qualifies the answer instead of
    shortening it.

    Everything here fits what the reader can be shown. The projection refuses a turn
    whose text or notices exceed its ceilings, and a refused turn shows nothing: live
    2026-09-23 a turn that had read the right PDF ended in `output_limit` and the reader
    got no answer at all (QA-23). So an overlong answer is cut where the reader can see
    it was, and the notices are bounded — never dropped without saying how many.
    """
    text, cut = _fitted(answer.text)
    limitations = tuple(dict.fromkeys((*answer.limitations, *answer.notes)))
    if cut:
        limitations = (*limitations, CUT_NOTE)
    if answer.quoted:
        # Said apart from the unbound figures: these stand in a document the turn read,
        # which is where the reader can check them, and nothing more is claimed.
        limitations = (*limitations, _listed(QUOTED, answer.quoted))
    if answer.unverified:
        limitations = (*limitations, _listed(UNBOUND, answer.unverified))
    limitations = _bounded(limitations)
    status = (
        AnswerStatus.QUALIFIED
        if (answer.unverified or answer.quoted or limitations)
        else AnswerStatus.ACCEPTED
    )
    if not text.strip():
        status = AnswerStatus.ABSTAINED
    return GatedAnswer(status, text, Verdict(True, ()), limitations=limitations)


#: Where an answer longer than the reader can be shown was cut, in the text itself.
CUT: Final = "\n\n[Cevap gösterilebilecek uzunluğu aştığı için burada kesildi.]"
CUT_NOTE: Final = "Cevap uzunluk sınırını aştığı için kısaltıldı; kesildiği yer metinde yazıyor."
UNBOUND: Final = "Şu sayılar araç sonuçlarına bağlanamadı: "
QUOTED: Final = (
    "Belgeden alıntılanan sayılar — okunan belgede aynen geçiyor (yeri parantez içinde); "
    "birimi, dönemi ve neyi saydığı ayrıca doğrulanmadı: "
)


def _fitted(text: str) -> tuple[str, bool]:
    """The text, or as much of it as can be shown, cut at a paragraph or sentence."""
    if len(text) <= MAX_TEXT_CHARS:
        return text, False
    room = MAX_TEXT_CHARS - len(CUT)
    head = text[:room]
    for mark in ("\n\n", ". ", "\n"):
        at = head.rfind(mark)
        if at > room * 2 // 3:
            head = head[: at + len(mark.rstrip())]
            break
    return head.rstrip() + CUT, True


def _listed(prefix: str, figures: list[str]) -> str:
    """Figures under a heading, as many as one notice holds, and how many more."""
    line = prefix
    for index, figure in enumerate(figures):
        rest = len(figures) - index
        addition = (" / " if index else "") + figure
        if len(line) + len(addition) + len(f" / … ve {rest} sayı daha") > MAX_NOTICE_CHARS:
            return f"{line} / … ve {rest} sayı daha"
        line += addition
    return line


def _bounded(notices: tuple[str, ...]) -> tuple[str, ...]:
    """At most as many notices as can be shown, each no longer than one may be."""

    def clipped(text: str) -> str:
        return text if len(text) <= MAX_NOTICE_CHARS else text[: MAX_NOTICE_CHARS - 1] + "…"

    kept = [clipped(item) for item in notices]
    if len(kept) <= MAX_NOTICES:
        return tuple(kept)
    rest = kept[MAX_NOTICES - 1 :]
    return (*kept[: MAX_NOTICES - 1], clipped(f"Diğer {len(rest)} not: " + " | ".join(rest)))


class _Arguments(BaseModel):
    """A stand-in for the parsed arguments the projection never reads."""

    model_config = ConfigDict(extra="ignore")


__all__ = ["as_answered"]
