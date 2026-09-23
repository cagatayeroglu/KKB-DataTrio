"""A question built from dependent steps gets to finish them (live 2026-09-23, A3).

A PDF's three rows joined to a two-series table is read, open, extract, and one join
per column: seven rounds that each need the one before. With one look at the table in
between, the default budget of eight ran out and the turn closed mid-check. Made-up
tool and figures; only the shape of the turn is the live one's.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_loop import FINISH, Budget, run_turn
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ToolCall


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


def registry() -> ToolRegistry:
    def run(arguments, context):  # noqa: ARG001 - tool contract
        return ToolResult(ToolStatus.SUCCESS, "", "step", output={"got": arguments.text})

    tools = ToolRegistry()
    tools.register(ToolSpec(name="step", description="Step.", arguments=Step, run=run))
    return tools


def rounds(count: int) -> list[tuple[ToolCall, ...]]:
    return [
        (ToolCall(f"c{i}", "step", json.dumps({"text": str(i)})),) for i in range(count)
    ]


def test_nine_dependent_rounds_finish_within_the_default_budget():
    provider = scripted(*rounds(9), (ToolCall("done", FINISH, json.dumps({"answer": "tamam"})),))
    outcome = run_turn("soru", provider=provider, registry=registry(), instructions="")
    assert outcome.exhausted is None
    assert outcome.reply == "tamam"
    assert len(outcome.observations) == 9


def test_the_counter_still_closes_a_turn_that_never_finishes():
    provider = scripted(
        *rounds(Budget().max_iterations),
        (ToolCall("done", FINISH, json.dumps({"answer": "eldekiyle"})),),
    )
    outcome = run_turn("soru", provider=provider, registry=registry(), instructions="")
    assert outcome.exhausted == "iterations"
    assert outcome.reply == "eldekiyle"
