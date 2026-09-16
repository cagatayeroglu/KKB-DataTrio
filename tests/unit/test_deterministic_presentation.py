"""Offline, bounded presentation of trusted analytical tables."""

import json

from test_add_series import arguments as add_arguments
from test_add_series import bound_tool, source_of
from test_co_movement import QUESTION, arguments
from test_co_movement import lake as lake
from test_table_relationship import plan, registry_for
from test_turn_three import ADD_KFE, REAL, comparison, prepared, proposal, step
from test_turn_two import TURN_TWO, tool, transform
from test_turn_two import pool as pool

from kkb_agent import live_check
from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry, gate_answer
from kkb_agent.agent.executor import execute, validate_plan
from kkb_agent.agent.presentation import deterministic_draft, display_value
from kkb_agent.core import Scale
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.llm import scripted
from kkb_agent.tools import make_change_detection_tool


def test_turn_one_known_counts_are_bound_without_a_writer(lake):
    registry = ToolRegistry()
    registry.register(
        make_change_detection_tool(
            lake.connection,
            lineage=lake.lineage,
            series_names=prepared_series_names(lake.connection),
        )
    )
    proposed = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "turn1",
                "tool": "change_detection",
                "arguments": arguments().model_dump(mode="json"),
            }
        ],
    }
    provider = scripted(json.dumps(proposed))
    answer = Session(provider, registry).answer(QUESTION, lake.connection)
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert len(provider.seen) == 1
    assert [number.number.value for number in answer.answer.verdict.numbers] == [5, 4, 1, 3]
    assert len(answer.tables) == 1


def test_deflation_reference_is_calendrical_and_writer_free(pool):
    lake, workspace = pool
    workspace.publish(workspace.preview("unrelated_secret", source_of(pool)))
    registry = ToolRegistry()
    registry.register(tool(lake, workspace))
    proposed = {
        "question": TURN_TWO,
        "steps": [
            {
                "step_id": "deflate",
                "tool": "table_transform",
                "arguments": transform().model_dump(mode="json"),
            }
        ],
    }
    before = source_of(pool).digest()
    provider = scripted(json.dumps(proposed))
    answered = Session(provider, registry).answer(
        TURN_TWO, lake.connection, workspace=workspace, remember="real"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert "2021-06" in answered.answer.text
    assert all(number.binding.value == "year" for number in answered.answer.verdict.numbers)
    assert len(provider.seen) == 1
    assert "unrelated_secret" not in answered.answer.text
    assert workspace.value_of("konut_kredisi_ve_faiz").digest() == before
    assert len(answered.tables) == 1


def test_add_series_and_turn_three_counts_are_writer_free(pool):
    lake, workspace = pool
    registry = registry_for(pool)
    added = bound_tool(pool).run(add_arguments(), ExecutionContext("add")).output
    assert deterministic_draft(added) == "Tabloya aylık seri sütunu eklendi."
    outcome = execute(validate_plan(plan(), registry), registry)
    final = outcome.results[-1].output
    draft = deterministic_draft(final)
    assert draft is not None
    assert "Koşul altında iki yönü birlikte karşılayan dönem sayısı 1." in draft
    assert "Koşul altında sürücü yönünü karşılayan dönem sayısı 2." in draft
    assert "neden" not in draft and "sebep" not in draft
    assert any("causal effect" in limitation for limitation in final.limitations)
    gated = gate_answer(draft, {"comparison": final}, lake.connection)
    assert gated.status is AnswerStatus.ACCEPTED
    assert [item.number.value for item in gated.verdict.numbers] == [5, 0, 5, 2, 3, 1]
    provider = scripted(plan().model_dump_json())
    before = source_of(pool).digest()
    answered = Session(provider, registry).answer(
        plan().question, lake.connection, workspace=workspace, remember="comparison"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert len(provider.seen) == 1
    assert workspace.value_of("konut_kredisi_ve_faiz").digest() == before
    assert "comparison" in workspace.names()


def test_unknown_shapes_and_unresolved_display_fall_back(pool):
    source = source_of(pool)
    assert deterministic_draft(source.model_copy(update={"method": "unknown"})) is None
    bad = source.model_copy(update={"unresolved_semantics": ["unknown unit"]})
    assert deterministic_draft(bad) is None
    unknown_unit = source.values[0].model_copy(update={"unit": "unsupported-unit"})
    assert (
        deterministic_draft(
            source.model_copy(update={"values": [unknown_unit, *source.values[1:]]})
        )
        is None
    )
    unknown_scale = source.values[0].model_copy(update={"scale": Scale.UNKNOWN})
    assert (
        deterministic_draft(
            source.model_copy(update={"values": [unknown_scale, *source.values[1:]]})
        )
        is None
    )
    assert display_value(next(v for v in source.values if v.unit == "TRY")) is not None
    assert display_value(source.values[0].model_copy(update={"unit": "index"})) is None


def test_wrong_and_extra_numbers_still_fail_the_original_gate(pool):
    registry = registry_for(pool)
    final = execute(validate_plan(plan(), registry), registry).results[-1].output
    good = deterministic_draft(final)
    assert good is not None
    wrong = good.replace(
        "Koşul altında iki yönü birlikte karşılayan dönem sayısı 1.",
        "Koşul altında iki yönü birlikte karşılayan dönem sayısı 19.",
    )
    assert (
        gate_answer(wrong, {"comparison": final}, pool[0].connection).status
        is not AnswerStatus.ACCEPTED
    )
    extra = good + " Desteklenmeyen 987654321 dönem vardır."
    assert (
        gate_answer(extra, {"comparison": final}, pool[0].connection).status
        is not AnswerStatus.ACCEPTED
    )


def test_candidate_evidence_fault_prevents_publication_even_with_fast_prose(pool, monkeypatch):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(tool(lake, workspace))
    proposed = {
        "question": TURN_TWO,
        "steps": [
            {
                "step_id": "deflate",
                "tool": "table_transform",
                "arguments": transform().model_dump(mode="json"),
            }
        ],
    }
    before = source_of(pool).digest()
    monkeypatch.setattr(
        "kkb_agent.agent.loop.result_faults", lambda *args, **kwargs: {"real": ["bad proof"]}
    )
    provider = scripted(json.dumps(proposed))
    answered = Session(provider, registry).answer(
        TURN_TWO, lake.connection, workspace=workspace, remember="real"
    )
    assert len(provider.seen) == 1
    assert answered.tables == ()
    assert "real" not in workspace.names()
    assert source_of(pool).digest() == before


def test_abstained_transform_never_publishes_or_calls_writer(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(tool(lake, workspace))
    refused = transform(column="EVDS:TP.KTF12 monthly average (by_end)")
    proposed = {
        "question": TURN_TWO,
        "steps": [
            {
                "step_id": "deflate",
                "tool": "table_transform",
                "arguments": refused.model_dump(mode="json"),
            }
        ],
    }
    before = source_of(pool).digest()
    provider = scripted(json.dumps(proposed))
    answered = Session(provider, registry).answer(
        TURN_TWO, lake.connection, workspace=workspace, remember="real"
    )
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert len(provider.seen) == 1
    assert "real" not in workspace.names()
    assert source_of(pool).digest() == before


def test_prepared_three_turn_rehearsal_needs_only_planner_calls(lake, tmp_path):
    prepared(lake)
    provider = scripted(
        proposal(
            live_check.TURN_ONE_QUESTION,
            [step("change_detection", arguments().model_dump(mode="json"))],
        ),
        proposal(
            live_check.TURN_TWO_QUESTION,
            [step("table_transform", transform().model_dump(mode="json"))],
        ),
        proposal(
            live_check.TURN_THREE_QUESTION,
            [ADD_KFE, comparison("compare", REAL, when=("EVDS:TP.KFE.TR", "up"))],
        ),
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=3)
    assert report["passed"] is True, report
    assert len(provider.seen) == 3
    assert [turn["answer"]["status"] for turn in report["turns"]] == ["accepted"] * 3
    assert len(report["turns"][-1]["published"]) == 3
