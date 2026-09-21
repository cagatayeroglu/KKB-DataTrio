"""Bookkeeping a plan leaves out is completed by the harness, not refused.

A refusal is a whole planner call, and on the served model that is minutes. What is mended
never changes what the plan computes; what would is still refused (test_same_plan_tables).
"""

from __future__ import annotations

import json

from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import QUESTION, fetch, plan, rebase, registry_for
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Session, ToolStatus
from kkb_agent.agent.plan_healing import heal_plan
from kkb_agent.llm import scripted


def test_a_step_that_reads_another_step_gets_the_edge_it_left_out(pool):
    healed, notes = heal_plan(plan(fetch(), rebase("fetch")), registry_for(pool))
    assert healed.steps[1].depends_on == ["fetch"]
    assert notes == ("step 'rebased': reads 'fetch', added to depends_on",)


def test_a_complete_plan_is_returned_as_it_was(pool):
    original = plan(fetch(), rebase("fetch", ["fetch"]))
    healed, notes = heal_plan(original, registry_for(pool))
    assert healed is original and notes == ()


def test_edges_that_order_nothing_are_dropped(pool):
    step = rebase("fetch", ["fetch", "rebased", "nowhere", "fetch"])
    healed, notes = heal_plan(plan(fetch(), step), registry_for(pool))
    assert healed.steps[1].depends_on == ["fetch"]
    assert len(notes) == 2 and all("orders nothing" in note for note in notes)


def test_an_id_an_earlier_phase_used_is_renamed_with_every_reference_to_it(pool):
    healed, notes = heal_plan(
        plan(fetch(), rebase("fetch", ["fetch"])), registry_for(pool), used_ids={"fetch"}
    )
    assert [step.step_id for step in healed.steps] == ["fetch_2", "rebased"]
    assert healed.steps[1].arguments["source"] == "fetch_2"
    assert healed.steps[1].depends_on == ["fetch_2"]
    assert any("renamed 'fetch_2'" in note for note in notes)


def test_a_published_table_of_the_same_name_is_left_to_the_planner(pool):
    # A reference to that name may mean the table or the step; only the planner knows.
    healed, notes = heal_plan(
        plan(fetch(), rebase("fetch", ["fetch"])),
        registry_for(pool),
        used_ids={"fetch"},
        known_tables={"fetch"},
    )
    assert [step.step_id for step in healed.steps] == ["fetch", "rebased"] and notes == ()


def test_what_changes_the_computation_is_never_mended(pool):
    unknown_tool = {"step_id": "x", "tool": "shell", "arguments": {}}
    bad_arguments = {"step_id": "y", "tool": "table_transform", "arguments": {"operation": "zip"}}
    twice = plan(fetch(), fetch())
    for original in (plan(unknown_tool), plan(bad_arguments), twice):
        healed, notes = heal_plan(original, registry_for(pool))
        assert healed is original and notes == ()


def test_a_turn_whose_plan_left_the_edge_out_runs_without_a_second_planner_call(pool):
    lake, workspace = pool
    steps = [fetch(), rebase("fetch")]
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), "Tablo hazırlandı.")
    session = Session(provider, registry_for(pool))
    answered = session.answer(QUESTION, lake.connection, workspace=workspace, remember="tufe_bazli")
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert [r.status for r in answered.outcome.results] == [ToolStatus.SUCCESS] * 2
    assert session.rejections == [] and answered.planned.attempts == 1
    # The read behind the transform is not shown to the writer beside it: the same figures
    # twice are ambiguous to the gate, and the writer could then quote none of them.
    writer_context = " ".join(message.content for message in provider.seen[-1])
    assert "tufe_bazli_ek_" not in writer_context and "display AMBIGUOUS" not in writer_context
