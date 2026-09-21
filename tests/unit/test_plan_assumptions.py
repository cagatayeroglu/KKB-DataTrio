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


@pytest.mark.parametrize(
    "refused",
    [
        "Soruda pencere verilmediği için son 24 ay kullanıldı.",  # a number nothing computed
    ],
)
def test_a_footnote_the_gate_refuses_falls_alone_and_costs_the_answer_nothing(pool, refused):
    """A footnote is a courtesy, not the answer.

    Withheld with the answer, it used to make an ACCEPTED answer QUALIFIED, and a
    QUALIFIED answer publishes no table: the next turn's "tabloyu bozmadan ..." then had
    nothing to build on, for the sake of a sentence nobody had asked for.
    """
    plain = answered(pool, [fetch()])
    result = answered(pool, [with_assumption(refused)])

    assert plain.answer.status is AnswerStatus.ACCEPTED
    assert result.answer.status is AnswerStatus.ACCEPTED, result.answer
    assert result.answer.text == plain.answer.text and result.tables == plain.tables
    # Still reported: the reader is told a sentence was withheld, and which.
    assert [item.text for item in result.answer.omitted] == [f"{ASSUMPTION_LABEL}{refused}"]


def test_a_refused_footnote_does_not_take_a_sound_one_with_it(pool):
    second = dict(rebase("fetch", ["fetch"]))
    second["assumption"] = "Son 24 ay kullanıldı."
    result = answered(pool, [with_assumption(NOTE), second])

    assert result.answer.status is AnswerStatus.ACCEPTED, result.answer
    assert f"{ASSUMPTION_LABEL}{NOTE}" in result.answer.text
    assert "24" not in result.answer.text


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


def test_a_number_the_reader_wrote_is_theirs_to_read_back(pool):
    # Live, 2026-09-21: every sentence of the model passed, and the harness's own note
    # ("Son 8 haftanın değişimi için ...") was withheld because 8 is no result's value. The
    # answer went QUALIFIED, a 384-second rewrite followed, and it came back worse.
    lake, workspace = pool
    steps = [with_assumption("Son 8 haftanın değişimi için 8 haftalık pencere okundu.")]
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), "Tablo hazırlandı.")
    result = Session(provider, registry_for(pool)).answer(
        "Son 8 haftada TÜFE nasıl değişti?", lake.connection, workspace=workspace
    )
    assert result.answer.status is AnswerStatus.ACCEPTED, result.answer
    assert "8 haftalık" in result.answer.text and result.answer.omitted == ()
