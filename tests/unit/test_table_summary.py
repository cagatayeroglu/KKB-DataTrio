"""Independent scalar oracles and the closed table_transform summary boundary."""

import json
from datetime import date

import pytest
from test_add_series import bound_tool
from test_co_movement import lake as lake  # noqa: F401
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry
from kkb_agent.agent.presentation import display_value
from kkb_agent.agent.verifier import gate_answer, result_faults
from kkb_agent.analytics.table_summary import SummaryRefused, summarize_column
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
from kkb_agent.llm import scripted
from kkb_agent.tools.table_transform import TableTransformArguments


def source(measure=StockFlow.FLOW):
    months = (
        (date(2025, 1, 1), date(2025, 1, 31), 10.0),
        (date(2025, 2, 1), date(2025, 2, 28), 30.0),
        (date(2025, 3, 1), date(2025, 3, 31), 20.0),
    )
    return AnalyticalResult(
        result_id="synthetic-flow",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="fixture",
        evidence=ResultEvidence(input_refs=["synthetic"]),
        values=[
            ResultValue(
                label="credit",
                value=value,
                unit="TRY",
                scale=Scale.MILLION,
                measure=measure,
                period=Period(start=start, end=end, frequency=Frequency.MONTHLY),
            )
            for start, end, value in months
        ],
    )


@pytest.mark.parametrize(
    ("aggregation", "values", "periods"),
    [
        ("mean", [20.0], [date(2025, 3, 31)]),
        ("sum", [60.0], [date(2025, 3, 31)]),
        ("min", [10.0], [date(2025, 1, 31)]),
        ("max", [30.0], [date(2025, 2, 28)]),
        ("first", [10.0], [date(2025, 1, 31)]),
        ("last", [20.0], [date(2025, 3, 31)]),
        ("count", [3.0], [None]),
    ],
)
def test_hand_calculated_summary_oracles(aggregation, values, periods):
    result = summarize_column(source(), column_label="credit", aggregation=aggregation)
    assert [item.value for item in result.values] == values
    assert [item.period.end if item.period else None for item in result.values] == periods
    assert result.samples.used == 3
    assert result.transformation.operation == "summarize"
    assert result.transformation.input_refs == ["synthetic-flow", "credit"]


def test_filter_and_invalid_sum_semantics():
    result = summarize_column(
        source(),
        column_label="credit",
        aggregation="mean",
        start_period=date(2025, 2, 1),
        end_period=date(2025, 3, 31),
    )
    assert result.values[0].value == 25.0
    assert result.samples.used == 2
    with pytest.raises(SummaryRefused, match="Summing a stock"):
        summarize_column(source(StockFlow.STOCK), column_label="credit", aggregation="sum")
    with pytest.raises(SummaryRefused, match="no observations"):
        summarize_column(
            source(), column_label="credit", aggregation="max", start_period=date(2026, 1, 1)
        )


def test_tool_summary_is_proof_bound_and_does_not_mutate_prior_table(pool):
    lake, workspace = pool
    original = workspace.value_of("konut_kredisi_ve_faiz")
    label = original.values[0].label
    column = [value for value in original.values if value.label == label and value.period]
    expected = sum(value.value for value in column) / len(column)
    arguments = TableTransformArguments.model_validate(
        {
            "operation": "summarize",
            "source": "konut_kredisi_ve_faiz",
            "column": label,
            "aggregation": "mean",
            "requested_aggregation": "mean",
        }
    )
    result = bound_tool(pool).run(arguments, ExecutionContext("Bu tablonun ortalaması ne?")).output
    assert result.status is ResultStatus.COMPUTED
    assert result.values[0].value == pytest.approx(expected)
    assert result.evidence.lineage_node
    assert result.evidence.transformations[-1].operation == "summarize"
    assert result_faults({"summary": result}, lake.connection) == {}
    assert workspace.value_of("konut_kredisi_ve_faiz").digest() == original.digest()


def test_evidence_backed_qualitative_summary_is_not_rejected(pool):
    lake, workspace = pool
    original = workspace.value_of("konut_kredisi_ve_faiz")
    label = original.values[0].label
    arguments = TableTransformArguments.model_validate(
        {
            "operation": "summarize",
            "source": "konut_kredisi_ve_faiz",
            "column": label,
            "aggregation": "mean",
            "requested_aggregation": "mean",
        }
    )
    result = bound_tool(pool).run(arguments, ExecutionContext("Ortalaması ne?")).output
    amount = display_value(result.values[0])
    assert amount is not None
    draft = (
        f"Seçilen dönemlerin ortalaması {amount}. "
        "Bu özet aylar arasındaki farklılığı göstermez; tek tek aylar ayrıca incelenebilir."
    )
    gated = gate_answer(draft, result, lake.connection)
    assert gated.status is AnswerStatus.ACCEPTED
    assert gated.text == draft


@pytest.mark.parametrize(
    ("draft", "status", "published"),
    [
        ("Tablo aylık değerleri göstermektedir.", "accepted", True),
        ("Aylık ortalama 999 milyon TL'dir.", "abstained", False),
    ],
)
def test_scalar_answer_must_surface_verified_value_or_not_publish(pool, draft, status, published):
    lake, workspace = pool
    source_table = workspace.value_of("konut_kredisi_ve_faiz")
    label = source_table.values[0].label
    expected = sum(v.value for v in source_table.values if v.label == label) / sum(
        v.label == label for v in source_table.values
    )
    step = {
        "step_id": "s",
        "tool": "table_transform",
        "arguments": {
            "operation": "summarize",
            "source": "konut_kredisi_ve_faiz",
            "column": label,
            "aggregation": "mean",
            "requested_aggregation": "mean",
        },
    }
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    provider = scripted(
        json.dumps({"question": "Bu tablonun ortalaması ne?", "steps": [step]}), draft
    )
    answer = Session(
        provider,
        registry,
        deterministic_presentation=False,
        catalog_continuation=True,
        require_series_discovery=True,
    ).answer("Bu tablonun ortalaması ne?", lake.connection, workspace=workspace, remember="summary")
    assert len(provider.seen) == 2  # one planner + writer; no catalog discovery
    assert answer.answer.status.value == status
    assert ("summary" in workspace.names()) is published
    if published:
        assert any(
            item.supported and item.result_id == answer.results[-1].result_id
            for item in answer.answer.verdict.numbers
        )
        assert answer.results[-1].values[0].value == pytest.approx(expected)
    else:
        assert "konut_kredisi_ve_faiz" in workspace.names()
