"""An answer with figures no tool returned goes back to the model once (live 2026-09-23, A3).

The model wrote "the light-commercial share stayed within 19-23%" from the table by eye;
it was 24.1% in August, and the reader was only told afterwards that 19 and 23 had no tool
behind them. The loop now shows those figures to the model at `finish`, once: it may
compute them, drop them, or answer again as it was. Made-up tool and figures.
"""

from __future__ import annotations

import json
from datetime import date

from pydantic import BaseModel, ConfigDict

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_answer import Answer, _checked, _computed, unsupported_figures
from kkb_agent.agent.trust_loop import FINISH, REVIEW, run_turn
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
from kkb_agent.llm.provider import Role, ToolCall


class Ask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    what: str = "satış"


def sales() -> AnalyticalResult:
    return AnalyticalResult(
        result_id="sales",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        values=[
            ResultValue(
                label="satış",
                value=100.0,
                unit="count",
                scale=Scale.ONE,
                measure=StockFlow.FLOW,
                period=Period(
                    start=date(2026, 1, 1), end=date(2026, 1, 31), frequency=Frequency.MONTHLY
                ),
            )
        ],
        evidence=ResultEvidence(input_refs=["doc"]),
    )


def registry() -> ToolRegistry:
    def run(arguments, context):  # noqa: ARG001 - tool contract
        return ToolResult(ToolStatus.SUCCESS, "", "calc", output=sales())

    tools = ToolRegistry()
    tools.register(ToolSpec(name="calc", description="Satış.", arguments=Ask, run=run))
    return tools


def finish(identifier: str, answer: str) -> tuple[ToolCall, ...]:
    return (ToolCall(identifier, FINISH, json.dumps({"answer": answer}, ensure_ascii=False)),)


CALC = (ToolCall("c1", "calc", "{}"),)
GUESSED = "Ocak 2026'da satış 100 adet; yılın toplamı 250 adet."
FIXED = "Ocak 2026'da satış 100 adet."


def turn(*replies):
    provider = scripted(CALC, *replies)
    outcome = run_turn(
        "soru",
        provider=provider,
        registry=registry(),
        instructions="",
        review=lambda text, done: unsupported_figures(text, done, None),
    )
    return outcome, provider


def test_a_figure_no_tool_returned_is_shown_to_the_model_once():
    outcome, provider = turn(finish("f1", GUESSED), finish("f2", FIXED))
    assert outcome.reply == FIXED
    shown = [m.content for m in provider.seen[2] if m.role is Role.TOOL]
    assert any("250" in text and "yeniden çağır" in text for text in shown)
    assert "250" not in " ".join(m.content for m in provider.seen[1] if m.role is Role.TOOL)


def test_answering_again_as_it_was_ends_the_turn_with_that_answer():
    outcome, provider = turn(finish("f1", GUESSED), finish("f2", GUESSED))
    assert outcome.reply == GUESSED
    assert len(provider.seen) == 3  # asked once, never twice


def test_an_answer_every_figure_of_which_binds_is_not_reviewed():
    outcome, provider = turn(finish("f1", FIXED))
    assert outcome.reply == FIXED
    assert len(provider.seen) == 2


def test_the_review_is_the_models_business_not_the_readers():
    outcome, _ = turn(finish("f1", GUESSED), finish("f2", FIXED))
    answer = _checked(Answer(text=FIXED), outcome, _computed(outcome), None)
    assert not any(REVIEW.split("{")[0] in item for item in answer.limitations)
    assert answer.unverified == []
