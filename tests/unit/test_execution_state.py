"""Execution status is deterministic; financial prose and qualitative reasoning stay separate."""

import json

import pytest
from test_anomaly import house as house  # noqa: F401

from kkb_agent.agent import Session, ToolRegistry
from kkb_agent.agent.execution_state import ExecutionState, separate_status_claims, status_text
from kkb_agent.llm import scripted
from kkb_agent.tools import make_anomaly_tool, make_lakehouse_tool


@pytest.mark.parametrize(
    "execution,result,expected",
    [
        ("not_called", None, "çağrılmadı"),
        ("not_run", None, "planlandı ancak çalıştırılmadı"),
        ("failure", None, "başarısız"),
        ("success", "abstained", "kaçındı"),
        ("success", "insufficient", "veri yetersiz"),
        ("success", "computed", "sonuç hesaplandı"),
    ],
)
def test_execution_and_analytical_status_are_independent(execution, result, expected):
    state = ExecutionState("anomaly", "check", execution, result, 11, 12)
    assert expected in state.text()
    if result == "insufficient":
        assert "11" in state.text() and "12" in state.text() and "çalıştırıldı" in state.text()


def test_operational_claims_are_replaced_without_suppressing_interpretation():
    rich = (
        "Kredi talebindeki artış beklentilerle ilişkili olabilir. "
        "Bu ilişki nedensellik kanıtı değildir."
    )
    narrative, named = separate_status_claims("Anomali aracı çalıştırılmadı. " + rich)
    assert "çalıştırılmadı" not in narrative and rich.replace(". ", ".\n") == narrative
    assert named == {"anomaly"}
    assert "çağrılmadı" in status_text((), {"causality"})
    narrative, named = separate_status_claims("Causality was executed. " + rich)
    assert named == {"causality"} and "Causality" not in narrative


@pytest.mark.parametrize("terminal", [False, True])
def test_real_insufficient_call_is_never_described_as_not_called(house, terminal):
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
    registry.register(make_anomaly_tool(house.connection, lineage=house.lineage))
    analysis = {
        "step_id": "inspect",
        "tool": "anomaly",
        "arguments": {"series_id": "bddk:konut", "start": "2024-01-31", "end": "2024-12-31"},
    }
    read = {"step_id": "read", "tool": "lakehouse", "arguments": {"series": ["bddk:konut"]}}
    provider = scripted(
        json.dumps(
            {"question": "Analiz et", "steps": [read, analysis] if terminal else [analysis, read]}
        ),
        "Anomali aracı bu turda çalıştırılmadığı için belirlenemedi. "
        "Kredi talebindeki artış beklentilerle ilişkili olabilir. "
        "Finansman koşulları alternatif bir açıklamadır; bu ilişki nedensellik kanıtı değildir.",
    )
    answer = Session(provider, registry, deterministic_presentation=False).answer(
        "Analiz et", house.connection
    )
    text = answer.answer.text + (answer.answer.abstention or "")
    assert "çalıştırılmadığı" not in text
    assert "çalıştırıldı; veri yetersiz" in text
    assert "Kullanılan gözlem: 11" in text and "Gerekli asgari gözlem: 12" in text
    if not terminal:
        assert answer.answer.status.value == "qualified"
        assert "alternatif bir açıklamadır" in text and "nedensellik kanıtı değildir" in text
        assert any('"result": "insufficient"' in m.content for m in provider.seen[-1])
