"""E1 (2026-09-19): a failed step is not narrated as done, and the answer is not ACCEPTED.

The accepted live run fetched raw balances, failed the deflate step, and the writer
still wrote "enflasyondan arındırılmıştır"; every number bound to the raw values, so
the gate accepted a false description. The writer now sees which steps did not run,
and an answer over an incomplete plan is QUALIFIED with the missing steps named.
"""

import json

from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import PUBLISHED, fetch, registry_for
from test_turn_two import CPI_ID
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Session, ToolStatus
from kkb_agent.agent.loop import INCOMPLETE_STEPS_NOTE
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role

QUESTION = "TÜFE genel endeksini 2021 Haziran fiyatlarıyla enflasyondan arındır."


def deflate_with_an_unregistered_index():
    """Passes validation (the id is well-formed) and fails at run time."""
    return {
        "step_id": "real",
        "tool": "table_transform",
        "arguments": {
            "operation": "deflate",
            "source": "fetch",
            "column": CPI_ID,
            "index_series_id": "EVDS:TP.NOT.REGISTERED",
            "reference_period": "2021-06-30",
        },
        "depends_on": ["fetch"],
    }


def test_a_failed_step_is_named_to_the_writer_and_caps_the_answer_as_qualified(pool):
    lake, workspace = pool
    steps = [fetch(), deflate_with_an_unregistered_index()]
    provider = scripted(
        json.dumps({"question": QUESTION, "steps": steps}),
        # The E1 falsehood: no figure in it, so every gate check passes.
        "Değerler enflasyondan arındırılmıştır.",
    )
    session = Session(provider, registry_for(pool), deterministic_presentation=False)
    answered = session.answer(QUESTION, lake.connection, workspace=workspace, remember="tufe_reel")

    statuses = [r.status for r in answered.outcome.results]
    assert statuses == [ToolStatus.SUCCESS, ToolStatus.FAILURE]
    assert not answered.outcome.completed
    # The writer was told, in a system data turn before the question, which step did not run.
    writer_messages = provider.seen[-1]
    note = next(m.content for m in writer_messages if m.content.startswith(INCOMPLETE_STEPS_NOTE))
    assert "- real (table_transform) failure: series_unknown" in note
    assert all(m.role is Role.SYSTEM for m in writer_messages[:-1])
    assert writer_messages[-1].role is Role.USER
    # Bound figures or not, a plan that did not run whole is never ACCEPTED.
    assert answered.answer.status is AnswerStatus.QUALIFIED
    assert any("real (table_transform) failure" in item for item in answered.answer.limitations)
    assert workspace.names() == [PUBLISHED]  # nothing was published


def test_a_complete_plan_is_not_qualified_by_this_rule(pool):
    lake, workspace = pool
    from test_same_plan_tables import QUESTION as REBASE_QUESTION
    from test_same_plan_tables import rebase

    steps = [fetch(), rebase("fetch", ["fetch"])]
    provider = scripted(
        json.dumps({"question": REBASE_QUESTION, "steps": steps}), "Tablo hazırlandı."
    )
    session = Session(provider, registry_for(pool), deterministic_presentation=False)
    answered = session.answer(
        REBASE_QUESTION, lake.connection, workspace=workspace, remember="tufe_bazli"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert not any(m.content.startswith(INCOMPLETE_STEPS_NOTE) for m in provider.seen[-1])
