"""A3 on 95eebae: every call accounted for, and nothing claimed that was not read.

Live 2026-09-23 (run b453bee2): four of eight calls vanished under the per-iteration
cap (QA-27); the closing request, offered only `finish`, was answered with four
`inspect` calls that nothing ran or recorded; a PDF figure was credited to a page the
model never opened (QA-28); two correct sentences were reported as misdated (QA-26);
and a series read on the way became the published table.

Everything here is made up: no jury series, report or figure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_adapter import as_answered
from kkb_agent.agent.trust_answer import Answer, _figures, write_answer
from kkb_agent.agent.trust_loop import (
    CLOSED,
    CLOSING_AGAIN,
    FINISH,
    Action,
    Budget,
    Observation,
    TurnOutcome,
    run_turn,
)
from kkb_agent.agent.verifier import verify_claims
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
from kkb_agent.tools.inspect_result import InspectOutput
from kkb_agent.tools.web_url import WebUrlArguments


class Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


def echo_registry() -> ToolRegistry:
    def run(arguments, context):  # noqa: ARG001 - tool contract
        return ToolResult(ToolStatus.SUCCESS, "", "echo", output={"got": arguments.text})

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", description="Echo.", arguments=Echo, run=run))
    return registry


def call(identifier: str, name: str, arguments: dict) -> ToolCall:
    return ToolCall(identifier, name, json.dumps(arguments, ensure_ascii=False))


def tool_turns(messages) -> dict[str, str]:
    return {m.tool_call_id: m.content for m in messages if m.role is Role.TOOL}


class TestEveryCallIsAnswered:
    def test_a_call_over_the_per_iteration_cap_is_answered_not_dropped(self):
        calls = tuple(call(f"c{i}", "echo", {"text": str(i)}) for i in range(6))
        provider = scripted(
            calls,
            (call("c6", "echo", {"text": "sonra"}),),
            (call("done", FINISH, {"answer": "bitti"}),),
        )
        tracer = Tracer()
        outcome = run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="",
            budget=Budget(max_actions_per_iteration=4),
            tracer=tracer,
        )
        second = provider.seen[1]
        answered = tool_turns(second)
        assert set(answered) == {f"c{i}" for i in range(6)}
        assert "çalıştırılmadı" in answered["c4"] and "çalıştırılmadı" in answered["c5"]
        assert '"got": "3"' in answered["c3"]
        # The assistant turn the model is shown next still lists every call it made.
        [asked] = [m for m in second if m.tool_calls]
        assert [c.id for c in asked.tool_calls] == [f"c{i}" for i in range(6)]
        # And no id is handed out twice.
        ids = [item.action.id for item in outcome.observations]
        assert len(ids) == len(set(ids)) == 7
        statuses = [e.status for e in tracer.events if e.stage == "tool"]
        assert statuses == ["ok"] * 4 + ["not_run"] * 2 + ["ok"]

    def test_a_call_past_the_tool_budget_is_answered_and_the_turn_closes(self):
        provider = scripted(
            tuple(call(f"c{i}", "echo", {"text": str(i)}) for i in range(3)),
            (call("done", FINISH, {"answer": "eldekiyle bitti"}),),
        )
        outcome = run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="",
            budget=Budget(max_tool_calls=2),
        )
        assert outcome.exhausted == "tool calls" and outcome.reply == "eldekiyle bitti"
        closing = tool_turns(provider.seen[1])
        assert set(closing) == {"c0", "c1", "c2"}
        assert "bütçesi (2) doldu" in closing["c2"]

    def test_bookkeeping_is_not_a_notice_for_the_reader(self):
        provider = scripted(
            tuple(call(f"c{i}", "echo", {"text": str(i)}) for i in range(5)),
            (call("done", FINISH, {"answer": "bitti"}),),
        )
        outcome = run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="",
            budget=Budget(max_actions_per_iteration=4),
        )
        answer = write_answer("soru", outcome, provider=provider)
        assert not any("çalıştırılmadı" in item for item in answer.limitations)


class TestAClosingAnsweredWithToolsIsRecordedAndAskedAgain:
    def turn(self, *closing_replies, tracer=None):
        provider = scripted(
            (call("c1", "echo", {"text": "bir"}),),
            *closing_replies,
        )
        outcome = run_turn(
            "soru",
            provider=provider,
            registry=echo_registry(),
            instructions="",
            budget=Budget(max_iterations=1),
            tracer=tracer,
        )
        return outcome, provider

    def test_refused_calls_are_answered_and_the_model_writes_on_the_second_ask(self):
        tracer = Tracer()
        outcome, provider = self.turn(
            (call("x1", "inspect", {"source": "a1"}), call("x2", "inspect", {"source": "a1"})),
            (call("done", FINISH, {"answer": "kapanış cevabı"}),),
            tracer=tracer,
        )
        assert outcome.reply == "kapanış cevabı"
        again = provider.seen[2]
        answered = tool_turns(again)
        assert set(answered) == {"c1", "x1", "x2"}
        assert CLOSED in answered["x1"] and CLOSED in answered["x2"]
        assert any(m.role is Role.SYSTEM and CLOSING_AGAIN in m.content for m in again)
        [refused] = [e for e in tracer.events if e.name == "closing.refused"]
        assert refused.status == "failed" and refused.attributes["call_ids"] == ["x1", "x2"]
        finished = next(e for e in tracer.events if e.name == "finished")
        assert finished.attributes["closing_requests"] == 2

    def test_a_second_refusal_leaves_the_turn_to_the_writer_and_says_so(self):
        tracer = Tracer()
        outcome, _ = self.turn(
            (call("x1", "inspect", {"source": "a1"}),),
            (call("x2", "inspect", {"source": "a1"}),),
            tracer=tracer,
        )
        assert outcome.reply is None
        assert len([e for e in tracer.events if e.name == "closing.refused"]) == 2
        assert [o.result.error_category for o in outcome.observations[-2:]] == ["closed"] * 2


def month(end: date, value: float, *, tool: str = "lakehouse") -> AnalyticalResult:
    return AnalyticalResult(
        result_id="r",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool=tool,
        values=[
            ResultValue(
                label="bakiye",
                value=value,
                unit="TRY",
                scale=Scale.MILLION,
                measure=StockFlow.STOCK,
                period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
            )
        ],
        coverage=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
        evidence=ResultEvidence(input_refs=["x"]),
    )


def seen(identifier: str, tool: str, output: object) -> Observation:
    return Observation(
        Action(id=identifier, tool=tool),
        ToolResult(ToolStatus.SUCCESS, identifier, tool, output=output),
    )


class TestAReadIsNotPublishedUnlessNamed:
    def published(self, *observations: Observation, publish: str | None = None):
        outcome = TurnOutcome(observations=list(observations), reply="cevap", publish=publish)
        answer = write_answer("soru", outcome, provider=object())  # type: ignore[arg-type]
        return answer.published, as_answered("soru", outcome, answer).presented

    def test_a_turn_that_only_read_publishes_nothing(self):
        name, presented = self.published(seen("a1", "lakehouse", month(date(2026, 6, 30), 1.0)))
        assert name is None and presented == ()

    def test_the_last_built_table_is_the_default(self):
        name, presented = self.published(
            seen("a1", "table_transform", month(date(2026, 5, 31), 1.0, tool="table_transform")),
            seen("a2", "lakehouse", month(date(2026, 6, 30), 2.0)),
        )
        assert name == "a1" and [v.value for v in presented[0].values] == [1.0]

    def test_a_named_read_is_published(self):
        name, presented = self.published(
            seen("a1", "lakehouse", month(date(2026, 6, 30), 2.0)), publish="a1"
        )
        assert name == "a1" and presented


def balances() -> dict[str, AnalyticalResult]:
    return {
        "a1": AnalyticalResult(
            result_id="a1",
            kind=ResultKind.SERIES,
            status=ResultStatus.COMPUTED,
            tool="lakehouse",
            values=[
                month(date(2025, 12, 31), 52044.0).values[0],
                month(date(2026, 1, 31), 50000.0).values[0],
            ],
            coverage=Period(
                start=date(2025, 12, 1), end=date(2026, 1, 31), frequency=Frequency.MONTHLY
            ),
            evidence=ResultEvidence(input_refs=["x"]),
        )
    }


class TestAnAmbiguousDateIsNotAWrongDate:
    """QA-26, on made-up balances: the sentence names the value's month and another."""

    ambiguous = "Ocak 2026 değişimi için Aralık 2025 bakiyesi (52.044 milyon TL) okunmuştur."

    def test_the_report_does_not_call_it_misdated(self):
        reported, _ = _figures(self.ambiguous, balances(), None)
        assert reported == []

    def test_a_sentence_naming_only_another_month_is_still_reported(self):
        reported, _ = _figures("Şubat 2026 bakiyesi 52.044 milyon TL idi.", balances(), None)
        assert reported and reported[0].startswith("52.044")

    def test_the_planned_gate_keeps_its_strict_reading(self):
        verdict = verify_claims(self.ambiguous, balances(), None)
        assert any(item.faults for item in verdict.numbers)


@dataclass(frozen=True)
class Page:
    number: int
    text: str
    tables: tuple = ()


@dataclass(frozen=True)
class Document:
    pages: tuple[Page, ...]


@dataclass(frozen=True)
class Read:
    document: Document
    status: str = "loaded"


def long_report() -> Read:
    pages = tuple(Page(n, f"Sayfa {n}\n" + "metin " * 1500) for n in range(1, 30))
    extra = Page(30, "Segment büyümesi %17,3 oldu.")
    return Read(Document((*pages, extra)))


class TestAQuotationIsOfWhatTheModelRead:
    """QA-28: a coincidence on a page the model never opened is not a quotation."""

    sentence = "Kredi bakiyesi %17,3 geriledi."

    def answer(self, *observations: Observation) -> Answer:
        outcome = TurnOutcome(observations=list(observations), reply=self.sentence)
        return write_answer("soru", outcome, provider=object())  # type: ignore[arg-type]

    def test_a_page_seen_only_in_the_index_is_not_quoted(self):
        answer = self.answer(seen("a1", "web_url", long_report()))
        assert answer.quoted == []
        assert answer.unverified == ["17,3 (araç sonuçlarında bu değer yok)"]

    def test_a_page_the_model_opened_is(self):
        window = InspectOutput(
            source="a1",
            kind="text",
            columns=[],
            rows=1,
            offset=0,
            values=[{"page": 30, "line": 0, "text": "Segment büyümesi %17,3 oldu."}],
            more=False,
        )
        answer = self.answer(seen("a1", "web_url", long_report()), seen("a2", "inspect", window))
        assert answer.quoted == ["17,3 (a1, s. 30)"]


class TestTheRightToolIsNamedWhenTheWrongOneIsUsed:
    def test_re_reading_a_fetched_document_through_web_url_points_to_inspect(self):
        with pytest.raises(ValidationError) as raised:
            WebUrlArguments(read_from="a2", column="Ocak", row="2026")
        assert "inspect" in str(raised.value) and "page=N" in str(raised.value)
