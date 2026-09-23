"""QA-24 and the A2 failure on 92651bc: what the loop is shown, and what it keeps.

Live 2026-09-23: a reviewed alias hid the outstanding-portfolio rate a question named
"stok" (QA-24); two model requests of one turn failed to connect and the reader was
handed raw catalogue JSON; a PDF's figures were reported as "not in the tool results";
and a restart erased the conversation the next question depended on.

Every catalogue, document and conversation here is made up or a narrowed copy of the
demo catalogue; nothing names a jury series, report or figure.
"""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.observer import TraceEvent
from kkb_agent.agent.trust_adapter import QUOTED, UNBOUND, _gated
from kkb_agent.agent.trust_answer import INTERRUPTED, write_answer
from kkb_agent.agent.trust_loop import Action, Observation, TurnOutcome
from kkb_agent.agent.trust_memory import restored
from kkb_agent.api.prepared import stored_conversation
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.hybrid import CatalogDenseStage, search_hybrid_catalog
from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.ranking import intent_key
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.catalog.vectors import (
    CatalogVectors,
    QueryVector,
    SeriesVector,
    VectorProfile,
    catalog_documents,
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
from kkb_agent.llm import kloudeks
from kkb_agent.llm.config import ProviderConfig
from kkb_agent.llm.kloudeks import KloudeksProvider, _connect_cause
from kkb_agent.llm.provider import Message, Role, TransportError
from kkb_agent.tools import make_catalog_search_tool

DEMO = Path(__file__).parents[2] / "docs/catalog/demo_v1.json"
NEW = {"EVDS:TP.KBK.TRY.18", "EVDS:TP.KTF12"}
BOOK = {"EVDS:TP.BKR.TRY.18", "EVDS:TP.KKP.TRY.18"}


def rehash(data: dict) -> bytes:
    payload = {k: v for k, v in data.items() if k != "content_sha256"}
    data["content_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return json.dumps(data, ensure_ascii=False).encode()


def narrowed() -> bytes:
    """The demo catalogue with its generic rate alias narrowed to the new-loan members.

    The shape that hid the outstanding-portfolio rate live: a reviewed phrase the
    question contains, whose only members are the other basis.
    """
    data = json.loads(DEMO.read_text(encoding="utf-8"))
    for concept in data["concepts"]:
        if concept["concept_id"] == "housing_rate":
            concept["candidate_series_ids"] = sorted(NEW)
    return rehash(data)


def found(query: str, *, bounded: bool) -> list:
    snapshot = load_reviewed_snapshot(narrowed())
    return list(
        search_catalog(snapshot, CatalogSearchArguments(query=query), bounded=bounded).candidates
    )


class TestAReviewedAliasNoLongerHidesTheRest:
    def test_the_planned_path_keeps_its_closed_set(self):
        assert {
            c.series.record.series_id for c in found("konut kredisi faiz oranı stok", bounded=True)
        } == NEW

    def test_the_loop_sees_the_series_its_qualifier_names_first(self):
        shown = found("konut kredisi faiz oranı stok", bounded=False)
        ids = [c.series.record.series_id for c in shown]
        assert set(ids[:2]) == BOOK, ids
        # The alias's own members stay listed, below: "stok" contradicts their basis.
        assert NEW <= set(ids)
        assert {c.method for c in shown if c.series.record.series_id in NEW} == {"reviewed_phrase"}
        assert {c.method for c in shown if c.series.record.series_id in BOOK} == {"bm25"}

    def test_without_a_qualifier_the_reviewed_members_still_lead(self):
        ids = [c.series.record.series_id for c in found("konut kredisi faiz oranı", bounded=False)]
        assert set(ids[:2]) == NEW, ids
        assert BOOK <= set(ids)

    def test_the_tool_the_loop_is_given_is_open(self):
        tool = make_catalog_search_tool(snapshot_bytes=narrowed(), bounded=False)
        result = tool.run(
            tool.parse({"query": "konut kredisi faiz oranı stok"}), ExecutionContext("offline")
        )
        assert BOOK <= {c.series.record.series_id for c in result.output.candidates}

    def test_the_combined_search_is_open_too(self, tmp_path):
        snapshot = load_reviewed_snapshot(narrowed())
        profile = VectorProfile(
            model="kkbhackathon2026/Qwen3-Embedding-8B",
            dimension=4096,
            input_policy_id="hybrid-fixture-no-model-v1",
            origin="offline_fixture",
        )
        vectors = CatalogVectors(
            snapshot_sha256=snapshot.content_sha256,
            profile=profile,
            vectors=tuple(
                SeriesVector(
                    series_id=d.series_id,
                    text_sha256=d.text_sha256,
                    values=(1.0, i / 10, *([0.0] * 4094)),
                )
                for i, d in enumerate(catalog_documents(snapshot))
            ),
        )
        build_catalog_index(tmp_path / "index", snapshot, vectors)
        stage = CatalogDenseStage(
            LocalCatalogIndex.open(tmp_path / "index", snapshot, profile),
            lambda text: QueryVector(profile=profile, values=(1.0, *([0.0] * 4095))),
        )
        arguments = CatalogSearchArguments(query="konut kredisi faiz oranı stok")
        closed = search_hybrid_catalog(snapshot, arguments, stage)
        opened = search_hybrid_catalog(snapshot, arguments, stage, bounded=False)
        assert {c.series.record.series_id for c in closed.candidates} <= NEW
        assert set([c.series.record.series_id for c in opened.candidates][:2]) == BOOK


class TestAMeasureNamedInPassingIsNotAContradiction:
    def series(self, description: str):
        snapshot = load_reviewed_snapshot(narrowed())
        book = next(s for s in snapshot.series if s.record.series_id == "EVDS:TP.BKR.TRY.18")
        record = book.record.model_copy(update={"description": description})
        return book.model_copy(update={"record": record, "rate_basis": "unknown"})

    def test_a_category_path_naming_both_measures_says_neither(self):
        listed = self.series("Veri grubu: FAİZ VE KÂR PAYI İSTATİSTİKLERİ (STOK)")
        assert intent_key("konut kredisi faiz oranı stok", listed)[1] == 0

    def test_a_description_naming_one_measure_still_counts(self):
        participation = self.series("Katılım bankaları kâr payı oranı")
        assert intent_key("konut kredisi faiz oranı stok", participation)[1] == 1


def provider(*replies) -> tuple[KloudeksProvider, list[httpx.Request]]:
    sent: list[httpx.Request] = []
    queue = list(replies)

    def server(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        item = queue.pop(0)
        if callable(item):
            item()
        return item

    config = ProviderConfig(
        base_url="https://mia.csp.kloudeks.com/v1",
        credential=SecretStr("sk-canary-never-shown"),
        planner_model="m",
        router_model="m",
    )
    return KloudeksProvider(config, transport=httpx.MockTransport(server)), sent


def unreachable(cause: BaseException):
    def fail() -> None:
        try:
            raise cause
        except BaseException as error:
            raise httpx.ConnectError("could not connect to a host") from error

    return fail


def chat(text: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
    )


class TestAConnectionNeverMadeIsTriedAgain:
    @pytest.fixture(autouse=True)
    def no_pause(self, monkeypatch):
        monkeypatch.setattr(kloudeks, "CONNECT_PAUSES", (0.0, 0.0))

    def test_it_succeeds_on_a_later_attempt_and_says_why_the_first_failed(self):
        dns = socket.gaierror(11001, "getaddrinfo failed")
        target, sent = provider(unreachable(dns), unreachable(dns), chat("tamam"))
        completion = target.complete([Message(Role.USER, "soru")])
        assert completion.text == "tamam" and len(sent) == 3
        assert completion.reconnected == ("dns", "dns")

    def test_three_failures_name_the_cause_and_the_count_and_nothing_else(self):
        refused = ConnectionRefusedError(10061, "refused by mia.csp.kloudeks.com")
        target, sent = provider(*(unreachable(refused) for _ in range(3)))
        with pytest.raises(TransportError) as raised:
            target.complete([Message(Role.USER, "gizli soru")])
        message = str(raised.value)
        assert message == "Kloudeks request failed (ConnectError: refused; 3 connection attempts)"
        assert len(sent) == 3

    def test_a_request_that_may_have_been_sent_is_never_repeated(self):
        def lost() -> None:
            raise httpx.ReadError("connection dropped while reading")

        target, sent = provider(lost, chat("olmamalı"))
        with pytest.raises(TransportError, match="ReadError"):
            target.complete([Message(Role.USER, "soru")])
        assert len(sent) == 1

    def test_no_attempt_is_made_past_the_request_deadline(self, monkeypatch):
        monkeypatch.setattr(kloudeks, "CONNECT_PAUSES", (1e9,))
        target, sent = provider(unreachable(TimeoutError()), chat("olmamalı"))
        with pytest.raises(TransportError, match=r"timeout; 1 connection attempt\)"):
            target.complete([Message(Role.USER, "soru")])
        assert len(sent) == 1

    @pytest.mark.parametrize(
        "cause, word",
        [
            (socket.gaierror(11001, "x"), "dns"),
            (ssl.SSLCertVerificationError("x"), "tls-certificate"),
            (ssl.SSLError("x"), "tls"),
            (ConnectionResetError(10054, "x"), "reset"),
            (OSError(10065, "x"), "os-10065"),
        ],
    )
    def test_the_cause_is_one_fixed_word(self, cause, word):
        try:
            unreachable(cause)()
        except httpx.ConnectError as error:
            assert _connect_cause(error) == word


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
    document: Document
    status: str = "loaded"


def report() -> Read:
    return Read(
        Document(
            (
                Page(1, "Pazar Değerlendirmesi"),
                Page(
                    2,
                    "Ay içinde satışlar 81.031 adet oldu.",
                    (Table((("Dönem", "Adet"), ("Ocak-Ağustos", "719.996"))),),
                ),
            )
        )
    )


def balances() -> AnalyticalResult:
    end = date(2026, 6, 30)
    return AnalyticalResult(
        result_id="a2",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=[
            ResultValue(
                label="bakiye",
                value=49046.0,
                unit="TRY",
                scale=Scale.MILLION,
                measure=StockFlow.STOCK,
                period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
            )
        ],
        coverage=Period(start=date(2026, 6, 1), end=end, frequency=Frequency.MONTHLY),
        evidence=ResultEvidence(input_refs=["a1"]),
    )


def seen(identifier: str, tool: str, output: object, **arguments) -> Observation:
    return Observation(
        Action(id=identifier, tool=tool, arguments=arguments),
        ToolResult(ToolStatus.SUCCESS, identifier, tool, output=output),
    )


class TestAFigureFromADocumentIsAQuotation:
    def answer(self, reply: str, *observations: Observation):
        outcome = TurnOutcome(observations=list(observations), reply=reply)
        return write_answer("soru", outcome, provider=object())  # type: ignore[arg-type]

    def test_quoted_figures_are_named_with_where_they_stand(self):
        answer = self.answer(
            "Ay içinde 81.031 adet satıldı, Ocak-Ağustos toplamı 719.996 oldu. Haziran "
            "2026'da bakiye 49.046 milyon TL idi; bir de 12.345 adetten söz edildi.",
            seen("a1", "web_url", report()),
            seen("a2", "lakehouse", balances()),
        )
        assert answer.quoted == ["81.031 (a1, s. 2)", "719.996 (a1, s. 2, tablo 1)"]
        assert answer.unverified == ["12.345 (araç sonuçlarında bu değer yok)"]
        notices = _gated(answer).limitations
        assert any(item.startswith(QUOTED) and "81.031 (a1, s. 2)" in item for item in notices)
        assert any(item.startswith(UNBOUND) and "12.345" in item for item in notices)
        # Found is not verified: the notice says what was not checked.
        assert "doğrulanmadı" in QUOTED

    def test_a_turn_that_only_read_a_document_is_checked_too(self):
        answer = self.answer("Ay içinde 81.031 adet satıldı.", seen("a1", "web_url", report()))
        assert answer.quoted == ["81.031 (a1, s. 2)"] and answer.unverified == []

    def test_a_short_number_is_too_common_to_be_a_quotation(self):
        answer = self.answer(
            "Satışlar 81 bin civarındaydı.",
            seen("a1", "web_url", report()),
            seen("a2", "lakehouse", balances()),
        )
        assert answer.quoted == []


class TestTheFallbackIsReadable:
    def test_a_failed_writer_leaves_a_short_account_not_raw_json(self):
        class Dead:
            def complete(self, messages, **options):  # noqa: ARG002 - provider shape
                raise TransportError(
                    "Kloudeks request failed (ConnectError: dns; 3 connection attempts)"
                )

        tool = make_catalog_search_tool(snapshot_bytes=DEMO.read_bytes())
        listing = tool.run(tool.parse({"query": "konut kredisi"}), ExecutionContext("offline"))
        outcome = TurnOutcome(
            observations=[
                seen("a1", "catalog_search", listing.output, query="konut kredisi"),
                seen("a2", "lakehouse", balances(), purpose="bakiye"),
            ],
            exhausted="provider",
        )
        answer = write_answer("soru", outcome, provider=Dead(), kept=("analiz_1",))
        assert answer.text.startswith(INTERRUPTED.strip())
        assert '{"' not in answer.text and "snapshot_sha256" not in answer.text
        assert "a1 (catalog_search «konut kredisi»): " in answer.text
        assert "Konut Kredisi" in answer.text
        assert "49.046 milyon TL" in answer.text
        assert "analiz_1" in answer.text
        # Written by the harness from the outputs: nothing in it is a claim to check.
        assert answer.unverified == [] and answer.quoted == []


def conversation_store(tmp_path) -> tuple[ConversationStore, str, str]:
    store = ConversationStore(tmp_path / "history.sqlite")
    owner, _ = store.create_owner()
    for session in ("A", "B"):
        store.create_conversation(
            owner_id=owner, conversation_id=session, token=f"t-{session}", title=session
        )
    return store, "A", "B"


def turn(
    store: ConversationStore,
    session: str,
    turn_id: str,
    question: str,
    *,
    answer: str | None,
    status: str,
    detail: str | None = None,
) -> None:
    store.append_message(session, turn_id=turn_id, role="user", text=question, status="running")
    run_id = f"run-{turn_id}"
    store.start_run(session, run_id=run_id, turn_id=turn_id, question=question)
    if detail is not None:
        store.add_event(run_id, TraceEvent(1, "loop", "decision", "ok", 0, 0, {}, detail))
    if status == "running":
        return
    if answer is not None:
        store.append_message(
            session, turn_id=turn_id, role="assistant", text=answer, status="qualified"
        )
    store.finish_run(run_id, status=status, duration_ms=1)
    store.append_message(session, turn_id=turn_id, role="user", text=question, status=status)


class TestAConversationSurvivesARestart:
    def test_finished_turns_come_back_once_in_order_and_nothing_else(self, tmp_path):
        store, a, b = conversation_store(tmp_path)
        turn(
            store,
            a,
            "t1",
            "A1 sorusu",
            answer="A1 cevabı",
            status="completed",
            detail=json.dumps({"state": "not bir"}),
        )
        turn(store, b, "t2", "B sorusu", answer="B cevabı", status="completed")
        turn(
            store,
            a,
            "t3",
            "başarısız soru",
            answer=None,
            status="failed",
            detail=json.dumps({"state": "başarısız turun notu"}),
        )
        turn(
            store,
            a,
            "t4",
            "A2 sorusu",
            answer="A2 cevabı",
            status="completed",
            detail=json.dumps({"actions": []}),
        )
        turn(store, a, "t5", "şu anki soru", answer=None, status="running")

        memory = stored_conversation(store, a)
        assert [(e.question, e.answer) for e in memory.exchanges] == [
            ("A1 sorusu", "A1 cevabı"),
            ("A2 sorusu", "A2 cevabı"),
        ]
        # The failed turn's note never reached memory, and does not now.
        assert memory.note == "not bir"
        assert [e.question for e in stored_conversation(store, b).exchanges] == ["B sorusu"]

    def test_a_note_recorded_before_decisions_were_json_is_read_as_the_note(self, tmp_path):
        store, a, _ = conversation_store(tmp_path)
        turn(store, a, "t1", "soru", answer="cevap", status="completed", detail="eski biçim not")
        assert stored_conversation(store, a).note == "eski biçim not"

    def test_a_replayed_message_is_one_exchange(self):
        memory = restored(
            [
                ("t1", "user", "soru", "queued"),
                ("t1", "user", "soru", "completed"),
                ("t1", "assistant", "cevap", "accepted"),
                ("t1", "assistant", "cevap", "accepted"),
            ],
            {"t1"},
        )
        assert [(e.question, e.answer) for e in memory.exchanges] == [("soru", "cevap")]
