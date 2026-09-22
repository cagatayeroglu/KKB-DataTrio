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


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Bakiye 801.438 milyon TL ve", ""),
        ("Tamam. Bakiye 801.438 milyon TL ve", "Tamam."),
        ("Bakiye 801.438 milyon TL. Sonr", "Bakiye 801.438 milyon TL."),
    ],
)
def test_truncation_does_not_cut_inside_a_number(text, expected):
    from kkb_agent.agent.loop import _finished_sentences
    from kkb_agent.llm.provider import Completion

    assert _finished_sentences(Completion(text, "offline", finish_reason="length")) == expected


def test_writer_transport_error_keeps_verified_table(house):  # noqa: F811
    from kkb_agent.agent import AnswerStatus
    from kkb_agent.agent.verifier import result_faults
    from kkb_agent.llm.provider import TransportError

    inner = scripted(plan())

    class FailedWriter:
        def complete(self, *args, **kwargs):
            if kwargs.get("schema") is None:
                raise TransportError("offline timeout")
            return inner.complete(*args, **kwargs)

    workspace = Workspace.open(house.connection, "fallback")
    answer = session_for(house, FailedWriter()).answer(
        "Tabloyu getir", house.connection, workspace=workspace, remember="table"
    )
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert answer.tables and workspace.names() == ["table"]
    assert result_faults({"table": workspace.value_of("table")}, house.connection) == {}
    assert "yazılı değerlendirme üretilemedi" in answer.answer.text
