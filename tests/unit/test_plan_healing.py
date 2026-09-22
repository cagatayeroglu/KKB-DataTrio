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


def test_a_tool_is_named_and_described_before_its_schema_and_in_the_order_a_plan_uses_it(pool):
    # Sorted keys put every tool's whole argument schema (15 KB for table_transform) before
    # its name: a model reading left to right learned what the fields belonged to last.
    prompt = Session(scripted(), registry_for(pool))._tools_prompt()
    tools = json.loads(prompt.removeprefix("Available tools:\n"))
    assert [tool["name"] for tool in tools] == ["lakehouse", "table_transform"]
    assert all(list(tool) == ["name", "description", "arguments"] for tool in tools)
    transform = tools[1]
    # What each operation does is said once, side by side, where one is chosen.
    for operation in transform["arguments"]["discriminator"]["mapping"]:
        assert f"\n- {operation}: " in transform["description"], operation
    # Limits only the validator can act on are not the planner's reading.
    assert '"pattern"' not in prompt and '"maxLength"' not in prompt


def test_an_identity_written_without_its_namespace_is_read_as_the_one_it_names(pool):
    # Live 2026-09-22: the reader asked for USER:promotion_test_konut_bakiyesi.v1 by its
    # full identity; the plan came back without the USER:, and the turn was refused with
    # "These series IDs are not in the catalogue" over a prefix.
    lake, _ = pool
    known = {"USER:promotion_test_konut_bakiyesi.v1", "EVDS:TP.KTF12"}
    step = {
        "step_id": "ekle",
        "tool": "table_transform",
        "arguments": {
            "operation": "add_series",
            "source": "fetch",
            "series_id": "promotion_test_konut_bakiyesi.v1",
        },
        "depends_on": ["fetch"],
    }
    healed, notes = heal_plan(plan(fetch(), step), registry_for(pool), known_series=known)
    assert healed.steps[1].arguments["series_id"] == "USER:promotion_test_konut_bakiyesi.v1"
    assert any("read 'promotion_test_konut_bakiyesi.v1' as" in note for note in notes)

    # An identity the catalogue already lists is left exactly as written.
    exact = dict(step, arguments=dict(step["arguments"], series_id="EVDS:TP.KTF12"))
    kept, _ = heal_plan(plan(fetch(), exact), registry_for(pool), known_series=known)
    assert kept.steps[1].arguments["series_id"] == "EVDS:TP.KTF12"

    # A tail that two identities share is a choice, and choosing is the planner's.
    both = {"USER:x.v1", "EVDS:x.v1"}
    ambiguous = dict(step, arguments=dict(step["arguments"], series_id="x.v1"))
    left, _ = heal_plan(plan(fetch(), ambiguous), registry_for(pool), known_series=both)
    assert left.steps[1].arguments["series_id"] == "x.v1"
