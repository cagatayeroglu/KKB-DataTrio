"""A plan may say what it settled for itself, and the reader is told.

A question rarely settles everything - which of two rate bases, which place, which
window - and the alternative to stopping and asking is choosing and saying so. The
choice belongs to the planner, the only part that knows why it chose; the sentence
it writes is shown under the answer and is read by the gate exactly like the rest
of the answer, so it cannot smuggle a figure past it.
"""

import json
from types import SimpleNamespace

import pytest
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import QUESTION, fetch, rebase, registry_for
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, ExecutionOutcome, Session, ToolResult, ToolStatus
from kkb_agent.agent.executor import ValidatedPlan, ValidatedStep
from kkb_agent.agent.loop import ASSUMPTION_LABEL, Planned, plan_assumptions
from kkb_agent.agent.plan import PlanStep
from kkb_agent.llm import scripted

NOTE = "Ulusal seri baz alındı; soru il adı vermedi."


def answered(pool, steps, draft="Tablo hazırlandı."):
    lake, workspace = pool
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), draft)
    return Session(provider, registry_for(pool)).answer(
        QUESTION, lake.connection, workspace=workspace
    )


def with_assumption(note, step_id="fetch"):
    step = dict(fetch())
    step["step_id"] = step_id
    step["assumption"] = note
    return step


def test_a_step_that_ran_puts_its_assumption_under_the_answer(pool):
    result = answered(pool, [with_assumption(NOTE)])

    assert result.answer.status is AnswerStatus.ACCEPTED, result.answer
    assert f"{ASSUMPTION_LABEL}{NOTE}" in result.answer.text


def test_the_same_assumption_written_twice_is_said_once(pool):
    # Two chained steps that settled the same thing; the reader is told once.
    second = dict(rebase("fetch", ["fetch"]))
    second["assumption"] = NOTE
    result = answered(pool, [with_assumption(NOTE), second])

    assert result.answer.text.count(NOTE) == 1


def test_a_plan_without_assumptions_reads_as_before(pool):
    result = answered(pool, [fetch()])

    assert ASSUMPTION_LABEL not in result.answer.text


def test_an_assumption_is_read_by_the_gate_like_any_other_sentence(pool):
    # The footnote is appended before gating, never after: a figure nobody computed
    # is withheld here exactly as it would be in the answer's own prose.
    invented = "Bakiye 123.456 milyon TL varsayıldı."
    result = answered(pool, [with_assumption(invented)])

    assert invented not in result.answer.text
    assert any(invented in omitted.text for omitted in result.answer.omitted)


@pytest.mark.parametrize("note", ["", "   "])
def test_an_empty_assumption_adds_no_line(pool, note):
    result = answered(pool, [with_assumption(note)])

    assert ASSUMPTION_LABEL not in result.answer.text


def test_only_a_step_that_ran_is_footnoted():
    """A choice matters only if it was made; a refused step describes nothing."""
    ran = PlanStep(step_id="fetch", tool="lakehouse", assumption=NOTE)
    refused = PlanStep(step_id="rebased", tool="table_transform", assumption="Çalışmadı.")
    plan = ValidatedPlan(
        QUESTION,
        tuple(ValidatedStep(step, SimpleNamespace()) for step in (ran, refused)),
    )
    outcome = ExecutionOutcome(
        (
            ToolResult(ToolStatus.SUCCESS, "fetch", "lakehouse"),
            ToolResult(ToolStatus.FAILURE, "rebased", "table_transform", error_category="period"),
        ),
        completed=False,
    )

    assert plan_assumptions(Planned(plan, attempts=1), outcome) == (f"{ASSUMPTION_LABEL}{NOTE}",)
