"""Cancellation and transport failures at the final model boundary."""

import json

import pytest
from test_result_verification import FULLY_TYPED  # noqa: F401
from test_result_verification import house as house

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.cancellation import CancelToken, TurnCancelled, cancellable
from kkb_agent.llm import scripted
from kkb_agent.tools import make_lakehouse_tool


def session_for(house, provider):
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
    return Session(provider, registry, deterministic_presentation=False)


def plan():
    return json.dumps(
        {
            "question": "Tabloyu getir",
            "steps": [{"step_id": "read", "tool": "lakehouse", "arguments": {"sql": FULLY_TYPED}}],
        }
    )


def test_stop_during_writer_cannot_publish(house):  # noqa: F811
    token = CancelToken()
    inner = scripted(plan(), "Tablo hazır.")

    class CancellingWriter:
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            result = inner.complete(*args, **kwargs)
            if self.calls == 2:
                token.cancel()
            return result

    workspace = Workspace.open(house.connection, "cancel")
    with cancellable(token), pytest.raises(TurnCancelled):
        session_for(house, CancellingWriter()).answer(
            "Tabloyu getir", house.connection, workspace=workspace, remember="table"
        )
    assert workspace.names() == []
    assert house.connection.execute("SELECT count(*) FROM gold_cells").fetchone()[0] == 0
