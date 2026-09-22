"""DEC-167: a plan the tools refuse at run time is planned again once, inside the same budgets.

Live E1 and X4 (2026-09-19) each lost a turn, or a repair, to something only the run could
show: a column label the planner could not see, an operation on the wrong tool. A validation
rejection already gets a repair; a run-time refusal now gets the same one, once.
"""

import json

from test_catalog_continuation import QUESTION as DISCOVERY_QUESTION
from test_catalog_continuation import calculate, enabled, proposal
from test_catalog_continuation import rig as rig  # noqa: F401
from test_co_movement import TOTAL_ID
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import FETCH_SQL, PUBLISHED, registry_for
from test_turn_two import CPI_ID
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Budget, Session
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role

QUESTION = "Konut kredisi tutarlarını Haziran 2021 fiyatlarıyla enflasyondan arındır."


def deflate(column):
    return {
        "step_id": "real",
        "tool": "table_transform",
        "arguments": {
            "operation": "deflate",
            "source": PUBLISHED,
            "column": column,
            "index_series_id": CPI_ID,
            "reference_period": "2021-06-30",
        },
    }


def plan(*steps, question=QUESTION):
    return json.dumps({"question": question, "steps": list(steps)})


def session(provider, pool, **kwargs):  # noqa: F811 - the fixture is a parameter here
    return Session(provider, registry_for(pool), repair_runtime_refusals=True, **kwargs)


def test_a_refused_column_is_planned_again_once_and_the_corrected_plan_publishes(pool):  # noqa: F811
    lake_, workspace = pool
    provider = scripted(plan(deflate("value")), plan(deflate(TOTAL_ID)), "Tablo hazırlandı.")
    answered = session(provider, pool).answer(
        QUESTION, lake_.connection, workspace=workspace, remember="reel"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert answered.planned.attempts == 2
    assert any("refused at run time" in reason for reason in answered.planned.rejections)
    assert [a.outcome for a in answered.planned.attempts_log] == [
        "accepted",
        "refused_at_runtime",
        "accepted",
    ]
    # The second planner call saw what ran and the tool's own reason, as data turns.
    second = provider.seen[1]
    from kkb_agent.agent.plan import AnalyticalPlan

    assert second[-2].role is Role.ASSISTANT
    feedback = AnalyticalPlan.model_validate_json(second[-2].content)
    assert feedback.question == QUESTION
    assert feedback.steps[0].arguments["column"] == "value"
    assert second[-1].role is Role.USER and "the table's columns are:" in second[-1].content
    assert workspace.names() == [PUBLISHED, "reel"]


def test_runtime_repair_schema_correction_keeps_original_question_and_is_bounded(pool):  # noqa: F811
    from kkb_agent.agent.plan import AnalyticalPlan

    lake_, workspace = pool
    # The model can still omit question despite receiving a valid prior plan.
    missing = json.dumps({"steps": [deflate(TOTAL_ID)]})
    provider = scripted(
        plan(deflate("value"), question="Model paraphrase"),
        missing,
        plan(deflate(TOTAL_ID)),
        "Tablo hazır.",
    )
    answered = session(provider, pool).answer(QUESTION, lake_.connection, workspace=workspace)
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert len(provider.seen) == 3
    repaired = provider.seen[2]
    previous = [message for message in repaired if message.role is Role.ASSISTANT]
    assert AnalyticalPlan.model_validate_json(previous[0].content).question == QUESTION
    assert any(message.content == QUESTION for message in repaired)

    twice = scripted(plan(deflate("value")), missing, missing, plan(deflate(TOTAL_ID)))
    refused = session(twice, pool).answer(QUESTION, lake_.connection, workspace=workspace)
    assert refused.answer.status is AnswerStatus.ABSTAINED
    assert len(twice.seen) == 3 and len(twice.responses) == 1


def test_a_second_refusal_stands_and_costs_no_third_plan(pool):  # noqa: F811
    lake_, workspace = pool
    provider = scripted(plan(deflate("value")), plan(deflate("amount")), plan(deflate(TOTAL_ID)))
    answered = session(provider, pool).answer(
        QUESTION, lake_.connection, workspace=workspace, remember="reel"
    )
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert len(provider.seen) == 2 and len(provider.responses) == 1
    assert workspace.names() == [PUBLISHED]


def test_the_refused_plan_repeated_is_not_run_again(pool):  # noqa: F811
    lake_, workspace = pool
    provider = scripted(plan(deflate("value")), plan(deflate("value")))
    answered = session(provider, pool).answer(
        QUESTION, lake_.connection, workspace=workspace, remember="reel"
    )
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert answered.planned.attempts == 1  # the first run is what stands
    assert sum(1 for r in answered.outcome.results if r.tool == "table_transform") == 1


def test_a_refused_sql_reaches_the_planner_with_the_gate_s_reason(pool):  # noqa: F811
    lake_, workspace = pool
    refused = {"step_id": "fetch", "tool": "lakehouse", "arguments": {"sql": "DROP TABLE x"}}
    fixed = {"step_id": "fetch", "tool": "lakehouse", "arguments": {"sql": FETCH_SQL}}
    provider = scripted(plan(refused), plan(fixed), "Tablo hazırlandı.")
    answered = session(provider, pool).answer(
        "TÜFE genel endeksini getir.", lake_.connection, workspace=workspace, remember="tufe"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert "refused it at run time" in provider.seen[1][-1].content
    assert workspace.names() == [PUBLISHED, "tufe"]


def test_without_the_flag_or_without_budget_the_refusal_is_final(pool):  # noqa: F811
    lake_, workspace = pool
    plain = scripted(plan(deflate("value")), plan(deflate(TOTAL_ID)))
    answered = Session(plain, registry_for(pool)).answer(
        QUESTION, lake_.connection, workspace=workspace, remember="reel"
    )
    assert answered.answer.status is AnswerStatus.ABSTAINED and len(plain.seen) == 1
    spent = scripted(plan(deflate("value")), plan(deflate(TOTAL_ID)))
    answered = session(spent, pool, budget=Budget(max_plan_repairs=0)).answer(
        QUESTION, lake_.connection, workspace=workspace, remember="reel"
    )
    assert answered.answer.status is AnswerStatus.ABSTAINED and len(spent.seen) == 1


def test_an_empty_discovery_is_searched_again_before_any_continuation(rig):  # noqa: F811
    reg, calls = rig
    emptied = {
        "step_id": "d",
        "tool": "catalog_search",
        "arguments": {"query": "toplam konut kredisi", "source": "TÜİK"},
    }
    # A filter that matches nothing used to empty the search, and the turn paid a second
    # discovery call for it. The search now answers without the filter and says so.
    provider = scripted(proposal(emptied), proposal(calculate("a")))
    planned, outcome = enabled(provider, reg, repair_runtime_refusals=True).run(DISCOVERY_QUESTION)
    assert outcome.completed and len(calls) == 1
    assert planned.discovery_rounds == 1 and planned.attempts == 2
    assert planned.rejections == ()
    assert "nothing matched with source" in provider.seen[1][-1].content


def test_an_empty_discovery_still_gets_its_continuation_when_the_repair_fails(rig):  # noqa: F811
    reg, calls = rig
    emptied = {
        "step_id": "d",
        "tool": "catalog_search",
        "arguments": {"query": "toplam konut kredisi", "source": "TÜİK"},
    }
    # The re-plan repeats the emptied search; the continuation then clarifies as before.
    provider = scripted(
        proposal(emptied), proposal(emptied), proposal(clarification="missing_series")
    )
    planned, outcome = enabled(provider, reg, repair_runtime_refusals=True).run(DISCOVERY_QUESTION)
    assert planned.plan.clarification == "missing_series" and not calls
