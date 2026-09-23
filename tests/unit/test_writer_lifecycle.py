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


def test_writer_receives_selected_chat_model_without_changing_publication(house):
    from kkb_agent.llm.config import SELECTABLE_CHAT_MODELS

    inner = scripted(plan(), "Tablo hazır.")
    chosen = []

    class RecordingProvider:
        def complete(self, *args, **kwargs):
            chosen.append(kwargs.get("model"))
            return inner.complete(*args, **kwargs)

    session = session_for(house, RecordingProvider())
    session.model = SELECTABLE_CHAT_MODELS[1]
    answer = session.answer("Tabloyu getir", house.connection)
    assert answer.tables
    assert chosen == [SELECTABLE_CHAT_MODELS[1]] * 2


def test_writer_context_preserves_long_table_cells_meaning_and_provenance():
    from datetime import date

    from kkb_agent.agent.loop import _writer_values, render_result
    from kkb_agent.core import (
        AnalyticalResult,
        Frequency,
        Period,
        ResultEvidence,
        ResultKind,
        ResultStatus,
        ResultValue,
        Scale,
        StockFlow,
    )
    from kkb_agent.core.models import SourceRef, TransformationRecord

    values = [
        ResultValue(
            label="quantity",
            value=float(month),
            unit="kg",
            scale=Scale.ONE,
            measure=StockFlow.FLOW,
            period=Period(
                start=date(2021 + (month - 1) // 12, (month - 1) % 12 + 1, 1),
                end=date(2021 + (month - 1) // 12, (month - 1) % 12 + 1, 28),
                frequency=Frequency.MONTHLY,
            ),
        )
        for month in range(1, 61)
    ]
    transformation = TransformationRecord(
        operation="resample",
        parameters={"aggregation": "sum", "calendar": "business_day"},
        input_refs=["raw"],
        output_ref="monthly",
    )
    result = AnalyticalResult(
        result_id="monthly",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        values=values,
        evidence=ResultEvidence(
            input_refs=["raw"],
            transformations=[transformation],
            sources=[SourceRef(source_id="source", source_type="synthetic", locator="fixture")],
        ),
        parameters={"series_names": {"quantity": "Traded mass"}},
        warnings=["Partial final period"],
        limitations=["No holiday calendar"],
    )
    context = render_result(result)
    assert len(_writer_values(result)[0]) == 60
    for detail in [
        '"measure": "flow"',
        '"frequency": "monthly"',
        '"calendar": "business_day"',
        '"aggregation": "sum"',
        '"source_id": "source"',
        "Traded mass",
        "Partial final period",
        "No holiday calendar",
    ]:
        assert detail in context
    unknown = result.model_copy(
        update={
            "values": [values[0].model_copy(update={"unit": None})],
            "unresolved_semantics": ["unit unknown"],
        }
    )
    assert '"value_state": "value_present_unit_unresolved"' in render_result(unknown)


def test_inherited_semantics_remove_only_exact_copies():
    from kkb_agent.agent.loop import semantic_difference

    current = {
        "parameters": {"basis": "real", "calendar": "business_day"},
        "sources": [{"source_id": "A"}],
    }
    ancestor = {
        "parameters": {"basis": "nominal", "calendar": "business_day"},
        "sources": [{"source_id": "A"}, {"source_id": "B"}],
    }
    assert semantic_difference(ancestor, current) == {
        "parameters": {"basis": "nominal"},
        "sources": [{"source_id": "B"}],
    }


def test_compact_writer_cells_keep_every_period_and_unknown_semantics():
    from test_table_summary import source

    from kkb_agent.agent.loop import render_result
    from kkb_agent.agent.presentation import display_value

    result = source()
    rendered = render_result(result)
    assert rendered.count("unit TRY, scale million") == 1
    for value in result.values:
        assert rendered.count(f"display {display_value(value)}") == 1
        assert f"period {value.period.start}..{value.period.end}" in rendered
    # Ambiguity still withholds the one affected cell, not an entire grouped column.
    ambiguous = render_result(result, frozenset({1}))
    assert "display AMBIGUOUS" in ambiguous
    assert f"display {display_value(result.values[1])}" not in ambiguous


def test_a_count_column_without_a_stated_unit_is_present_not_absent():
    # Live J1 (N47, 2026-09-22): the organizer's gold table carries eight transaction counts
    # per currency, headed "İşlem Sayısı/ Number of Trans." with no unit. The writer read
    # UNAVAILABLE as "no value in any period" and told the reader the column was empty.
    from datetime import date

    from kkb_agent.agent.loop import SYNTHESIS_PROMPT, render_result
    from kkb_agent.core import (
        AnalyticalResult,
        Frequency,
        Period,
        ResultEvidence,
        ResultKind,
        ResultStatus,
        ResultValue,
        Scale,
    )

    months = [
        Period(start=date(2026, m, 1), end=date(2026, m, 28), frequency=Frequency.MONTHLY)
        for m in (1, 2, 3)
    ]
    values = [
        ResultValue(label="TL Miktar/Amount (KG)", value=v, unit="kg", scale=Scale.ONE, period=p)
        for v, p in zip((13837.0, 12001.0, 6316.0), months, strict=True)
    ] + [
        ResultValue(label="TL İşlem Sayısı", value=v, unit=None, scale=Scale.ONE, period=p)
        for v, p in zip((4821.0, 4410.0, 3977.0), months, strict=True)
    ]
    result = AnalyticalResult(
        result_id="gold",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="web_url",
        values=values,
        evidence=ResultEvidence(input_refs=["document:gold"]),
        unresolved_semantics=["TL İşlem Sayısı: the document states no unit or scale"],
    )
    rendered = render_result(result)
    assert "display 13.837 kg" in rendered
    count_lines = [line for line in rendered.splitlines() if "UNAVAILABLE" in line]
    assert len(count_lines) == 3
    assert all("a value is present" in line for line in count_lines)
    assert "never say that such a column or period has no value" in SYNTHESIS_PROMPT


def test_a_monthly_period_reaches_the_writer_with_the_name_a_reader_uses(monkeypatch):
    # N48 (live DeepSeek, 2026-09-22): shown only "2025-01-01..2025-01-31", the writer wrote
    # "2025-01-01..2025-01-31 döneminde" into Turkish prose.
    from datetime import date

    from kkb_agent.agent.loop import SYNTHESIS_PROMPT, render_result
    from kkb_agent.agent.presentation import period_label
    from kkb_agent.agent.verifier import AnswerStatus, gate_answer
    from kkb_agent.core import (
        AnalyticalResult,
        Frequency,
        Period,
        ResultEvidence,
        ResultKind,
        ResultStatus,
        ResultValue,
        Scale,
    )

    may = Period(start=date(2025, 5, 1), end=date(2025, 5, 31), frequency=Frequency.MONTHLY)
    value = ResultValue(label="credit", value=100.0, unit="TRY", scale=Scale.MILLION, period=may)
    result = AnalyticalResult(
        result_id="credit",
        kind=ResultKind.LEVEL,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=[value],
        evidence=ResultEvidence(input_refs=["gold_cells"]),
    )
    assert "period 2025-05-01..2025-05-31 (Mayıs 2025)" in render_result(result)
    assert "('Ocak 2025') is written by that name" in SYNTHESIS_PROMPT
    # A week that starts on the first of a month is not that month.
    week = Period(start=date(2025, 12, 1), end=date(2025, 12, 1), frequency=Frequency.DAILY)
    assert period_label(week) is None
    # The name binds back to the value's own period, and to no other.
    monkeypatch.setattr("kkb_agent.agent.verifier.execution_proof", lambda result, db: True)
    named = {"credit": result}
    assert gate_answer("Mayıs 2025'te 100 milyon TL.", named).status is AnswerStatus.ACCEPTED
    assert gate_answer("Haziran 2025'te 100 milyon TL.", named).status is not (
        AnswerStatus.ACCEPTED
    )
