"""One bounded second catalog phase may find a missing analysis helper, offline."""

import json

import pytest
from pydantic import BaseModel
from test_catalog_continuation import CATALOG
from test_turn_two import CPI_ID, REAL, TOTAL_ID, TURN_TWO, tool, transform
from test_turn_two import lake as lake  # noqa: F401
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Budget, PlanningFailed, Session, ToolRegistry
from kkb_agent.agent.discovery import MAX_DISCOVERY_BYTES, validate_discovery_phase
from kkb_agent.agent.executor import PlanRejected, ValidatedPlan, ValidatedStep
from kkb_agent.agent.plan import PlanStep
from kkb_agent.catalog.search import CatalogSearchArguments
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role
from kkb_agent.tools import make_catalog_search_tool


def plan(*steps, clarification=None, clarification_text=None):
    return json.dumps(
        {
            "question": TURN_TWO,
            "steps": list(steps),
            "clarification": clarification,
            "clarification_text": clarification_text,
        }
    )


def discover(step_id, query):
    return {"step_id": step_id, "tool": "catalog_search", "arguments": {"query": query}}


def deflate():
    return {
        "step_id": "real",
        "tool": "table_transform",
        "arguments": transform().model_dump(mode="json"),
    }


def session(pool, *responses, budget=None, proven=frozenset()):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(make_catalog_search_tool(snapshot_bytes=CATALOG.read_bytes()))
    registry.register(tool(lake, workspace))
    provider = scripted(*responses)
    return (
        Session(
            provider,
            registry,
            catalog_continuation=True,
            require_series_discovery=True,
            proven_series=proven,
            budget=budget or Budget(max_plan_repairs=0, max_discovery_rounds=2),
            series_names=prepared_series_names(lake.connection),
        ),
        provider,
    )


def test_nominal_then_missing_cpi_is_discovered_before_deflation_and_published(pool):  # noqa: F811
    lake, workspace = pool
    before = workspace.value_of("konut_kredisi_ve_faiz")
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("cpi", "TÜFE genel endeksi")),
        plan(deflate()),
    )

    answered = current.answer(
        TURN_TWO, lake.connection, workspace=workspace, remember="reel_konut_kredisi"
    )

    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert answered.planned.discovery_rounds == 2
    assert [item.tool for item in answered.outcome.results] == [
        "catalog_search",
        "catalog_search",
        "table_transform",
    ]
    assert {TOTAL_ID, CPI_ID} <= current.newly_proven
    assert workspace.value_of("konut_kredisi_ve_faiz") == before
    added = [
        value.value
        for value in workspace.value_of("reel_konut_kredisi").values
        if value.label.startswith(f"{TOTAL_ID} real")
    ]
    assert added == pytest.approx(REAL)
    assert len(provider.seen) <= 4
    phases = provider.seen[:3]
    schemas = [
        {
            tool["name"]
            for tool in json.loads(
                next(
                    message.content
                    for message in phase
                    if message.content.startswith("Available tools:")
                )[17:]
            )
        }
        for phase in phases
    ]
    assert schemas == [
        {"catalog_search", "table_transform"},
        {"catalog_search", "table_transform"},
        {"table_transform"},
    ]
    assert any(
        "plan catalog_search steps once more" in message.content
        for message in phases[1]
        if message.role is Role.SYSTEM
    )
    assert any(
        "No further catalog_search" in message.content
        for message in phases[2]
        if message.role is Role.SYSTEM
    )
    first_feedback = [
        message.content
        for message in phases[1]
        if message.role is Role.USER
        and message.content.startswith('{"kind":"untrusted_catalog_discovery"')
    ]
    final_feedback = [
        message.content
        for message in phases[2]
        if message.role is Role.USER
        and message.content.startswith('{"kind":"untrusted_catalog_discovery"')
    ]
    assert len(first_feedback) == 1 and final_feedback[:1] == first_feedback
    assert len(final_feedback) == 2
    assert all(len(item.encode()) <= MAX_DISCOVERY_BYTES for item in final_feedback)
    assert "sample_values" not in "".join(final_feedback)


def test_unproven_helper_read_is_repaired_to_independent_discovery(pool):  # noqa: F811
    lake, workspace = pool
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(deflate()),  # Cannot read CPI merely because its ID appears in a plan.
        plan(discover("cpi", "TÜFE genel endeksi")),
        plan(deflate()),
        budget=Budget(max_plan_repairs=1),
    )
    answered = current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert answered.planned.discovery_rounds == 2
    assert len(answered.planned.rejections) == 1
    assert "Unproven series in continuation" in answered.planned.rejections[0]
    assert [result.tool for result in answered.outcome.results] == [
        "catalog_search",
        "catalog_search",
        "table_transform",
    ]
    assert len(provider.seen) == 4


def test_missing_auxiliary_measure_clarifies_and_never_publishes(pool):  # noqa: F811
    lake, workspace = pool
    before = workspace.value_of("konut_kredisi_ve_faiz")
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("missing", "no such synthetic measure zzz999")),
        plan(clarification="missing_series"),
    )
    answered = current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert answered.planned.discovery_rounds == 2
    assert len(provider.seen) == 3
    assert "real" not in workspace.names()
    assert workspace.value_of("konut_kredisi_ve_faiz") == before


def test_the_rate_basis_choice_is_the_planners_not_the_harnesss(pool):  # noqa: F811
    # The harness used to end the turn here with a question of its own, before the planner
    # had seen the two candidates. The planner sees them now; whether to take the usual one
    # with an assumption or to ask is its call, and its own question is what is shown.
    lake, workspace = pool
    asked = "Yeni kullandırılan kredilerin faizini mi, portföy faizini mi kullanayım?"
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("rate", "konut kredisi faiz oranı")),
        json.dumps(
            {
                "question": TURN_TWO,
                "steps": [],
                "clarification": "ambiguous_series",
                "clarification_text": asked,
            }
        ),
    )
    answered = current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="rate")
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert answered.planned.plan.clarification_text == asked
    assert answered.planned.discovery_rounds == 2
    assert len(provider.seen) == 3 and "rate" not in workspace.names()
    candidates = provider.seen[2][-1].content
    assert "new_credit" in candidates and "outstanding_portfolio" in candidates


def test_third_search_rejected_and_existing_table_unchanged(pool):  # noqa: F811
    lake, workspace = pool
    before = workspace.value_of("konut_kredisi_ve_faiz")
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("cpi", "TÜFE genel endeksi")),
        plan(discover("third", "another measure")),
    )
    with pytest.raises(PlanningFailed, match="Continuation permits analysis"):
        current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert len(provider.seen) == 3 and "real" not in workspace.names()
    assert workspace.value_of("konut_kredisi_ve_faiz") == before


def test_discovery_budget_is_bounded_and_cannot_be_set_past_it():
    """The planner may look again several times; it may not be handed an open loop."""
    assert Budget(max_discovery_rounds=5).max_discovery_rounds == 5
    with pytest.raises(ValueError, match="at most eight rounds"):
        Budget(max_discovery_rounds=9)


def test_an_auxiliary_query_that_reuses_a_step_id_runs_under_a_fresh_one(pool):  # noqa: F811
    # The name clash used to cost the whole turn ("Continuation step IDs must be new"); the
    # harness knows every ID in use and every reference, so it renames instead.
    lake, workspace = pool
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("credit", "TÜFE genel endeksi")),
        plan(deflate()),
    )
    answered = current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert [item.step_id for item in answered.outcome.results][:2] == ["credit", "credit_2"]
    assert len(provider.seen) == 3 and "real" in workspace.names()


def test_auxiliary_query_count_cannot_exceed_four(pool):  # noqa: F811
    lake, workspace = pool
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(*(discover(f"helper_{index}", "TÜFE") for index in range(5))),
    )
    with pytest.raises(PlanningFailed, match="at most four queries"):
        current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert len(provider.seen) == 2 and "real" not in workspace.names()


def test_auxiliary_uses_remaining_shared_step_budget(pool):  # noqa: F811
    lake, workspace = pool
    current, provider = session(
        pool,
        plan(discover("credit", "toplam konut kredisi bakiyesi")),
        plan(discover("cpi", "TÜFE genel endeksi")),
        plan(deflate()),
        budget=Budget(max_steps=2, max_plan_repairs=0),
    )
    with pytest.raises(PlanningFailed, match="Continuation permits analysis"):
        current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert len(provider.seen) == 2 and "real" not in workspace.names()


def test_known_index_identity_does_not_need_another_catalog_or_planner_call(pool):  # noqa: F811
    lake, workspace = pool
    current, provider = session(
        pool,
        plan(deflate()),
        proven=frozenset({CPI_ID}),
    )
    answered = current.answer(TURN_TWO, lake.connection, workspace=workspace, remember="real")
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert answered.planned.discovery_rounds == 0
    assert [result.tool for result in answered.outcome.results] == ["table_transform"]
    assert len(provider.seen) == 1


@pytest.mark.parametrize(
    "forbidden", ["promote_series", "web_url", "web_search", "table_transform"]
)
def test_auxiliary_phase_cannot_mix_search_with_privileged_or_analysis_tool(forbidden):
    class Arguments(BaseModel):
        pass

    search = ValidatedStep(
        PlanStep(step_id="search", tool="catalog_search", arguments={"query": "TÜFE"}),
        CatalogSearchArguments(query="TÜFE"),
    )
    other = ValidatedStep(PlanStep(step_id="other", tool=forbidden, arguments={}), Arguments())
    with pytest.raises(PlanRejected, match="separate plan"):
        validate_discovery_phase(
            ValidatedPlan(TURN_TWO, (search, other)),
            continuation=True,
            auxiliary_discovery_allowed=True,
            require_series_discovery=True,
        )
