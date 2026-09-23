"""A table the model built and then rebuilt is its working, not the reader's (live A3).

Live 2026-09-23 a join that would have dropped two months was refused with "clarify or
separate the requested outputs"; the model joined the other way round, published that,
and the reader was still handed the refusal. What the published table was built from
keeps every warning, and so does anything that is not a table: a search that degraded
or a page that could not be read still speaks. Made-up figures.
"""

from __future__ import annotations

from datetime import date

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.trust_answer import Answer, _checked, _computed
from kkb_agent.agent.trust_loop import Action, Observation, TurnOutcome
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


def table(name: str, status: ResultStatus = ResultStatus.COMPUTED) -> AnalyticalResult:
    end = date(2026, 1, 31)
    return AnalyticalResult(
        result_id=name,
        kind=ResultKind.SERIES,
        status=status,
        tool="table_transform",
        values=[]
        if status is ResultStatus.ABSTAINED
        else [
            ResultValue(
                label="satış",
                value=10.0,
                unit="count",
                scale=Scale.ONE,
                measure=StockFlow.FLOW,
                period=Period(start=date(2026, 1, 1), end=end, frequency=Frequency.MONTHLY),
            )
        ],
        reason="refused" if status is ResultStatus.ABSTAINED else None,
        evidence=None if status is ResultStatus.ABSTAINED else ResultEvidence(input_refs=["doc"]),
    )


def step(identifier: str, tool: str, arguments: dict, output: object, *warnings: str):
    return Observation(
        Action(id=identifier, tool=tool, arguments=arguments),
        ToolResult(ToolStatus.SUCCESS, identifier, tool, output=output, warnings=warnings),
    )


def outcome(publish: str | None) -> TurnOutcome:
    return TurnOutcome(
        observations=[
            step("a1", "catalog_search", {"query": "satış"}, None, "SEARCH DEGRADED"),
            step("a2", "table_transform", {"source": "doc"}, table("a2"), "ROW NOTE"),
            step(
                "a3",
                "table_transform",
                {"operation": "join_table", "source": "analiz_1", "other": "a2"},
                table("a3", ResultStatus.ABSTAINED),
                "CLARIFY OR SEPARATE",
            ),
            step(
                "a4",
                "table_transform",
                {"operation": "join_table", "source": "a2", "other": "analiz_1"},
                table("a4"),
                "NEVER FILLED",
            ),
        ],
        publish=publish,
    )


def limitations(publish: str | None) -> list[str]:
    turn = outcome(publish)
    answer = _checked(Answer(text="tamam"), turn, _computed(turn), None, figures=False)
    return answer.limitations


def test_a_superseded_table_does_not_speak_to_the_reader():
    shown = limitations("a4")
    assert "CLARIFY OR SEPARATE" not in shown
    # What the published table was built from, and what is not a table, still speak.
    assert {"NEVER FILLED", "ROW NOTE", "SEARCH DEGRADED"} <= set(shown)


def test_with_nothing_of_this_turn_published_every_warning_stays():
    shown = limitations("analiz_1")
    assert {"CLARIFY OR SEPARATE", "NEVER FILLED", "ROW NOTE", "SEARCH DEGRADED"} <= set(shown)


def test_ids_inside_a_list_of_arguments_count_as_inputs():
    turn = outcome("a5")
    turn.observations.append(
        step("a5", "table_transform", {"sources": ["a3", "a4"]}, table("a5"), "COMBINED")
    )
    answer = _checked(Answer(text="tamam"), turn, _computed(turn), None, figures=False)
    assert {"CLARIFY OR SEPARATE", "NEVER FILLED", "COMBINED"} <= set(answer.limitations)
