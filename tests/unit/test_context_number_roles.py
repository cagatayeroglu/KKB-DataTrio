"""A prompt's window length cannot become an analytical money or rate claim."""

import json

import pytest
from test_result_verification import FULLY_TYPED  # noqa: F401
from test_result_verification import house as house

from kkb_agent.agent import AnswerStatus, Session, ToolRegistry, Workspace
from kkb_agent.llm import scripted
from kkb_agent.tools import make_lakehouse_tool


@pytest.mark.parametrize(
    "draft,accepted",
    [
        ("Bakiye 777 milyon TL.", False),
        ("Oran yüzde 777.", False),
        ("777 seri incelendi.", False),
        ("777 aylık pencere istendi.", True),
        ("2026 yılı için 777 aylık pencere istendi.", True),
    ],
)
def test_question_context_is_bound_by_role(house, draft, accepted):  # noqa: F811
    question = "2026 yılı için 777 aylık pencere istiyorum."
    plan = {
        "question": question,
        "steps": [
            {
                "step_id": "read",
                "tool": "lakehouse",
                "arguments": {"sql": FULLY_TYPED, "purpose": "read"},
                "depends_on": [],
            }
        ],
    }
    provider = scripted(json.dumps(plan), draft, draft, draft)
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
    workspace = Workspace.open(house.connection, "roles")
    answer = Session(provider, registry, deterministic_presentation=False).answer(
        question, house.connection, workspace=workspace, remember="table"
    )
    assert (answer.answer.status is AnswerStatus.ACCEPTED) == accepted
    if not accepted:
        assert not workspace.names()
