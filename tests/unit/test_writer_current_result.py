"""The writer is told which table this turn produced (live chain suite S4, 2026-09-18).

Every published table of the conversation stays in the writer's reach so a follow-up can
quote it, and nothing said which one the turn had just computed: an answer about a new
table restated an unrelated earlier one. Each block now carries that mark.
"""

import json

from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import PUBLISHED, QUESTION, fetch, rebase, registry_for
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Session
from kkb_agent.agent.loop import CURRENT_RESULT_MARK, EARLIER_RESULT_MARK, render_results
from kkb_agent.llm import scripted


def test_the_writer_sees_which_table_is_this_turn_s_and_which_are_earlier(pool):  # noqa: F811
    lake_, workspace = pool
    steps = [fetch(), rebase("fetch", ["fetch"])]
    provider = scripted(json.dumps({"question": QUESTION, "steps": steps}), "Tablo hazırlandı.")
    session = Session(provider, registry_for(pool), deterministic_presentation=False)
    answered = session.answer(QUESTION, lake_.connection, workspace=workspace, remember="tufe")
    assert answered.answer.status is AnswerStatus.ACCEPTED
    data = provider.seen[-1][1].content
    assert f"[tufe] ({CURRENT_RESULT_MARK})" in data
    assert f"[{PUBLISHED}] ({EARLIER_RESULT_MARK})" in data


def test_a_single_table_or_no_current_name_is_rendered_as_before(pool):  # noqa: F811
    table = pool[1].value_of(PUBLISHED)
    plain = render_results({PUBLISHED: table})
    assert render_results({PUBLISHED: table}, current=PUBLISHED) == plain
    assert plain.startswith(f"[{PUBLISHED}]\n")
    assert CURRENT_RESULT_MARK not in render_results({"a": table, "b": table})


def test_same_turn_intermediate_does_not_hide_preserved_workspace_ancestors(pool):  # noqa: F811
    from test_turn_two import CPI_ID

    lake_, workspace = pool
    first = {
        "step_id": "add",
        "tool": "table_transform",
        "arguments": {"operation": "add_series", "source": PUBLISHED, "series_id": CPI_ID},
    }
    provider = scripted(json.dumps({"question": "TÜFE ekle", "steps": [first]}), "Tablo hazır.")
    Session(provider, registry_for(pool), deterministic_presentation=False).answer(
        "TÜFE ekle", lake_.connection, workspace=workspace, remember="v2"
    )
    steps = [
        {
            "step_id": identity,
            "tool": "table_transform",
            "arguments": {
                "operation": "change",
                "source": source,
                "column": CPI_ID,
                "kind": "percent",
                "lag": lag,
            },
            "depends_on": deps,
        }
        for identity, source, lag, deps in [("a", "v2", 1, []), ("b", "a", 2, ["a"])]
    ]
    provider = scripted(
        json.dumps({"question": "Değişimleri ekle", "steps": steps}), "Tablo hazır."
    )
    answer = Session(provider, registry_for(pool), deterministic_presentation=False).answer(
        "Değişimleri ekle", lake_.connection, workspace=workspace, remember="v3"
    )
    assert answer.answer.status is AnswerStatus.ACCEPTED
    context = provider.seen[-1][1].content
    assert f"[{PUBLISHED}] ({EARLIER_RESULT_MARK})" not in context
    assert f"[v2] ({EARLIER_RESULT_MARK})" not in context
    assert CPI_ID in context
    assert all(v in workspace.value_of("v3").values for v in workspace.value_of("v2").values)
