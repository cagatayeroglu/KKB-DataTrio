"""QA-23 and QA-22: a long document, a spent budget, and a correctly rounded rate.

Live 2026-09-23 (run 4b95cc06) the loop found and read the right PDF, and the reader
got nothing. The document reached the model as one JSON string cut at 40,000
characters, mid-page, with no index of what was left out; the exchange budget later
pushed it out of view with nothing saying it was still in hand, and the model fetched
it again; the eighth iteration's results never reached the model at all; and a writer
handed every observation produced an answer the product then refused as too long.

Every document here is made up: nothing below knows a site, a report or a figure
from the jury's questions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, ConfigDict

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_adapter import CUT, CUT_NOTE, UNBOUND, _gated, as_answered
from kkb_agent.agent.trust_answer import Answer, _figures, write_answer
from kkb_agent.agent.trust_loop import (
    CLOSING,
    DROPPED,
    FINISH,
    MAX_OBSERVATION_CHARS,
    READ_MORE,
    Budget,
    TurnOutcome,
    _describe,
    run_turn,
)
from kkb_agent.api.projection import (
    MAX_NOTICE_CHARS,
    MAX_NOTICES,
    MAX_TEXT_CHARS,
    project_answer,
)
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
from kkb_agent.llm.provider import Role, ToolCall, TransportError
from kkb_agent.tools.inspect_result import InspectArguments, make_inspect_tool

MINUS = "−"


@dataclass(frozen=True)
class Table:
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Page:
    number: int
    text: str
    tables: tuple[Table, ...] = ()


@dataclass(frozen=True)
class Document:
    pages: tuple[Page, ...]


@dataclass(frozen=True)
class Read:
    """Shaped like a loaded document: the content under `document`."""

    status: str = "loaded"
    document: Document = field(default_factory=lambda: Document(()))


def page_text(number: int) -> str:
    body = f"Başlık {number}\n" + ("gövde metni " * 500) + f"\nDip not {number}: toplam {number}07"
    return body


def long_document(pages: int = 30) -> Read:
    return Read(
        document=Document(
            tuple(
                Page(
                    number,
                    page_text(number),
                    (Table(tuple((f"satır {r}", f"{number}{r}") for r in range(80))),),
                )
                for number in range(1, pages + 1)
            )
        )
    )


class TestALongDocumentArrivesAsAnIndex:
    def test_every_page_is_listed_with_its_start_and_end(self):
        rendered = _describe(
            ToolResult(ToolStatus.SUCCESS, "a1", "reader", output=long_document()), "a1"
        )
        assert len(rendered) <= MAX_OBSERVATION_CHARS
        body = json.loads(rendered)  # Whole JSON, not a string cut mid-value.
        assert body["id"] == "a1" and body["clipped"] is True
        assert body["read_more"] == READ_MORE
        pages = body["output"]["document"]["pages"]
        assert [page["number"] for page in pages] == list(range(1, 31))
        for page in pages:
            # The heading at the top and the footnote at the bottom both survive.
            assert page["text"].startswith(f"Başlık {page['number']}")
            assert page["text"].endswith(f"toplam {page['number']}07")
            assert "karakter]" in page["text"]
            # Every table is there, its rows shortened and counted.
            assert len(page["tables"]) == 1
            assert page["tables"][0]["rows"][-1].startswith("… [+")

    def test_a_result_that_fits_is_shown_whole(self):
        small = Read(document=Document((Page(1, "kısa metin"),)))
        body = json.loads(
            _describe(ToolResult(ToolStatus.SUCCESS, "a1", "reader", output=small), "a1")
        )
        assert (
            "clipped" not in body and body["output"]["document"]["pages"][0]["text"] == "kısa metin"
        )


class TestInspectReadsAPageOrATable:
    def look(self, **arguments) -> ToolResult:
        context = ExecutionContext("soru", outputs={"a1": long_document()})
        return make_inspect_tool().run(InspectArguments(source="a1", **arguments), context)

    def test_one_page_whole(self):
        result = self.look(page=17, limit=60)
        assert result.status is ToolStatus.SUCCESS
        lines = [row["text"] for row in result.output.values]
        assert {row["page"] for row in result.output.values} == {17}
        assert lines[0] == "Başlık 17" and lines[-1] == "Dip not 17: toplam 1707"
        assert "clipped" not in _describe(result, "a2")

    def test_one_table_by_page_and_by_document_order(self):
        on_page = self.look(page=5, table=1, limit=60)
        in_order = self.look(table=5, limit=60)
        assert on_page.output.values == in_order.output.values
        assert on_page.output.rows == 80 and on_page.output.kind == "document_table"
        assert on_page.output.next_offset == 60
        assert on_page.output.values[3] == {
            "page": 5,
            "table_on_page": 1,
            "row": 3,
            "cells": ["satır 3", "53"],
        }

    def test_a_part_that_is_not_there_says_what_is(self):
        missing_page = self.look(page=31)
        missing_table = self.look(page=2, table=2)
        assert missing_page.status is ToolStatus.FAILURE
        assert "30 sayfa" in missing_page.warnings[0]
        assert "1 tablo var" in missing_table.warnings[0]


class Reader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


def reader_registry() -> ToolRegistry:
    def run(arguments, context):  # noqa: ARG001 - tool contract
        return ToolResult(
            ToolStatus.SUCCESS,
            "",
            "reader",
            output={"name": arguments.name, "text": "x" * 6_000, "pages": [1, 2, 3]},
        )

    registry = ToolRegistry()
    registry.register(ToolSpec(name="reader", description="Read.", arguments=Reader, run=run))
    return registry


def call(identifier: str, name: str, arguments: dict) -> tuple[ToolCall, ...]:
    return (ToolCall(identifier, name, json.dumps(arguments, ensure_ascii=False)),)


def system_text(messages) -> str:
    return "\n".join(m.content for m in messages if m.role is Role.SYSTEM)


class TestAResultOutOfViewIsStillNamed:
    def test_the_note_lists_what_was_dropped_and_keeps_listing_it(self):
        provider = scripted(
            call("c1", "reader", {"name": "birinci"}),
            call("c2", "reader", {"name": "ikinci"}),
            call("c3", "reader", {"name": "üçüncü"}),
            call("c4", FINISH, {"answer": "tamam"}),
        )
        run_turn(
            "soru",
            provider=provider,
            registry=reader_registry(),
            instructions="",
            budget=Budget(max_exchange_bytes=10_000),
        )
        third, fourth = system_text(provider.seen[2]), system_text(provider.seen[3])
        assert DROPPED in third
        # By name, with what it was asked and what it holds.
        assert '- a1 (reader {"name": "birinci"}): success; name=birinci' in third
        assert "pages: 3 öğe" in third
        # Still named a request later, although nothing new was dropped by then.
        assert "- a1 (reader" in fourth


class TestASpentBudgetStillEndsInAnAnswer:
    def turn(self, *replies, tracer=None) -> tuple[TurnOutcome, object]:
        provider = scripted(*replies)
        outcome = run_turn(
            "soru",
            provider=provider,
            registry=reader_registry(),
            instructions="",
            budget=Budget(max_iterations=2),
            tracer=tracer,
        )
        return outcome, provider

    def test_the_last_results_reach_the_model_and_it_answers(self):
        tracer = Tracer()
        outcome, provider = self.turn(
            call("c1", "reader", {"name": "birinci"}),
            call("c2", "reader", {"name": "ikinci"}),
            call(
                "c3",
                FINISH,
                {"answer": "İki kaynak okundu; ikincisi eksiksizdi, üçüncü aranamadı."},
            ),
            tracer=tracer,
        )
        assert outcome.exhausted == "iterations"
        assert outcome.reply == "İki kaynak okundu; ikincisi eksiksizdi, üçüncü aranamadı."
        # The last iteration was told it was the last.
        assert "son tur" in system_text(provider.seen[1])
        closing = provider.seen[2]
        # The closing request carries the last call's own result, paired by its id,
        assert [m.tool_call_id for m in closing if m.role is Role.TOOL][-1] == "c2"
        assert CLOSING in system_text(closing)
        # and offers nothing to run but the finish.
        assert provider.offered[2] == (FINISH,)
        finished = next(e for e in tracer.events if e.name == "finished")
        assert finished.attributes["closing"] is True
        closing_step = [e for e in tracer.events if e.name == "iteration"][-1]
        assert closing_step.attributes["closing"] is True

    def test_a_closing_request_that_fails_leaves_the_writer_its_evidence(self):
        outcome, _ = self.turn(
            call("c1", "reader", {"name": "birinci"}),
            call("c2", "reader", {"name": "ikinci"}),
            TransportError("Kloudeks transport failure (502)"),
        )
        assert outcome.exhausted == "iterations" and outcome.reply is None
        assert len(outcome.observations) == 2

    def test_a_turn_that_finished_itself_is_not_asked_again(self):
        outcome, provider = self.turn(
            call("c1", "reader", {"name": "birinci"}),
            call("c2", FINISH, {"answer": "bitti"}),
        )
        assert outcome.exhausted is None and outcome.reply == "bitti"
        assert len(provider.seen) == 2

    def test_the_writer_request_is_on_record(self):
        tracer = Tracer()
        outcome = TurnOutcome(observations=[], exhausted="undecided", state=None)
        provider = scripted("Elde sonuç yok.")
        write_answer("soru", outcome, provider=provider, tracer=tracer)
        [writer] = [e for e in tracer.events if e.stage == "answer" and e.name == "writer"]
        record = json.loads(writer.detail)
        assert record["response"]["content"] == "Elde sonuç yok."
        assert record["request"]["messages"][1] == {"role": "user", "content": "soru"}


class TestAnAnswerAlwaysFitsWhatTheReaderIsShown:
    def test_an_overlong_answer_is_cut_where_the_reader_sees_it(self):
        text = ("Uzun bir paragraf. " * 300 + "\n\n") * 3
        gated = _gated(Answer(text=text))
        assert len(gated.text) <= MAX_TEXT_CHARS
        assert gated.text.endswith(CUT)
        assert CUT_NOTE in gated.limitations

    def test_many_unbound_figures_and_notes_stay_within_the_notices(self):
        answer = Answer(
            text="kısa",
            limitations=[f"not {n}" for n in range(20)],
            unverified=[f"{n}.123 (araç sonuçlarında bu değer yok)" for n in range(200)],
        )
        gated = _gated(answer)
        assert len(gated.limitations) <= MAX_NOTICES
        assert all(len(item) <= MAX_NOTICE_CHARS for item in gated.limitations)
        merged = gated.limitations[-1]
        assert merged.startswith("Diğer ") and UNBOUND in merged

    def test_the_projection_accepts_what_the_adapter_hands_it(self):
        answer = Answer(
            text="Paragraf. " * 2_000,
            limitations=[f"not {n}" for n in range(30)],
            unverified=[f"{n}.123 (araç sonuçlarında bu değer yok)" for n in range(300)],
        )
        projected = project_answer(
            as_answered("soru", TurnOutcome(), answer), turn_id="t1", published=None
        )
        assert projected.text.endswith(CUT.strip())
        assert len(projected.notices) <= MAX_NOTICES + 1


def rate(end: date, value: float) -> ResultValue:
    return ResultValue(
        label="aylık değişim",
        value=value,
        unit="percent",
        scale=Scale.ONE,
        measure=StockFlow.RATE,
        period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
    )


def changes() -> dict[str, AnalyticalResult]:
    values = [
        rate(date(2026, 2, 28), -3.7271133221873365),
        rate(date(2026, 3, 31), -1.2961158880088086),
        rate(date(2026, 6, 30), -2.45327896704044),
    ]
    return {
        "a5": AnalyticalResult(
            result_id="a5",
            kind=ResultKind.SERIES,
            status=ResultStatus.COMPUTED,
            tool="table_transform",
            values=values,
            coverage=Period(
                start=date(2026, 2, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
            ),
            evidence=ResultEvidence(input_refs=["a4"]),
        )
    }


class TestARateRoundedToItsWrittenDecimalsBinds:
    """QA-22: a correct two-decimal presentation was reported as unbound."""

    def test_correct_roundings_bind(self):
        answer = (
            f"Şubat 2026'da aylık değişim %{MINUS}3,73, Mart 2026'da %{MINUS}1,30 ve "
            f"Haziran 2026'da %{MINUS}2,45 oldu."
        )
        reported, _ = _figures(answer, changes(), None)
        assert reported == []

    def test_a_falling_verb_carries_the_sign(self):
        reported, _ = _figures("Şubat 2026'da bakiye %3,73 azaldı.", changes(), None)
        assert reported == []

    def test_a_wrong_digit_a_wrong_sign_and_a_wrong_month_are_still_reported(self):
        for sentence in (
            f"Şubat 2026'da aylık değişim %{MINUS}3,80 oldu.",
            "Şubat 2026'da aylık değişim %+3,73 oldu.",
            f"Nisan 2026'da aylık değişim %{MINUS}3,73 oldu.",
        ):
            reported, _ = _figures(sentence, changes(), None)
            assert reported, sentence

    def test_a_whole_number_still_needs_its_hedge_word(self):
        reported, _ = _figures(f"Şubat 2026'da aylık değişim %{MINUS}4 oldu.", changes(), None)
        assert reported
        hedged, _ = _figures(
            f"Şubat 2026'da aylık değişim yaklaşık %{MINUS}4 oldu.", changes(), None
        )
        assert hedged == []
