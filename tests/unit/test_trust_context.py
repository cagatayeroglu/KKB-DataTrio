"""What the loop's model is actually sent: the conversation's context, as data.

The planned turn was shown the conversation's documents, the page an address in the
question offers and the table the reader selected; the loop was shown none of them
(QA-30), so a question about an attached file reached a model that had never heard
of the file. `context.assembled` recorded the context and proved nothing: these tests
read the messages the provider received. They also hold the prompt to the protocol
the served model really speaks — native calls and `finish`, no `state` field.
"""

from __future__ import annotations

import json
from uuid import uuid4

from test_catalog_continuation import CATALOG, TOTAL, seed_prepared
from test_document_check import QUESTION, FakeFetch
from test_document_upload import csv_with, runtime, session, upload
from test_prepared_api import wait_http
from test_trust_recovery import turn

from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.trust_loop import DROPPED, FINISH, _asked_for, tool_menu
from kkb_agent.agent.trust_memory import Conversation, Exchange
from kkb_agent.agent.trust_prompt import INSTRUCTIONS
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import SelectedResult
from kkb_agent.api.store import ConversationStore
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Completion, Message, Role, ToolCall


def finish(answer: str = "Tamam.", **fields: str) -> tuple[ToolCall, ...]:
    return (
        ToolCall(
            id=f"f{uuid4().hex[:6]}",
            name=FINISH,
            arguments=json.dumps({"answer": answer, **fields}),
        ),
    )


def read_total() -> tuple[ToolCall, ...]:
    return (
        ToolCall(
            id=f"r{uuid4().hex[:6]}", name="lakehouse", arguments=json.dumps({"series": [TOTAL]})
        ),
    )


def served(tmp_path, *responses, **options):
    root = tmp_path.resolve() / "prepared"
    if not root.exists():
        seed_prepared(root)
    provider = scripted(*responses)
    runner = PreparedRunner(
        provider,
        root,
        tmp_path.resolve() / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        trust_loop=True,
        **options,
    )
    return runner, provider


def data(messages: list[Message]) -> list[str]:
    """What travelled as user turns before the question: the conversation's data."""
    return [m.content for m in messages[:-1] if m.role is Role.USER]


def instructions(messages: list[Message]) -> str:
    return "\n".join(m.content for m in messages if m.role is Role.SYSTEM)


def test_an_attached_document_reaches_the_model_as_data_not_instructions(tmp_path):
    """QA-30, through HTTP as Codex reproduced it: upload, ask, read what was sent."""
    provider = scripted(finish("Belge inceleme tamamlandı."))
    runner, client = runtime(tmp_path, provider)
    runner._trust_loop = True
    with client:
        sid, headers = session(client)
        document = upload(client, sid, headers).json()
        route = f"/v1/sessions/{sid}/turns"
        admitted = client.post(
            route,
            headers=headers,
            json={
                "request_id": uuid4().hex,
                "question": "Ekli belgeyi incele.",
                "document_ref": document["document_ref"],
            },
        )
        assert admitted.status_code == 202, admitted.text
        done = wait_http(client, f"{route}/{admitted.json()['turn_id']}", headers)
        assert done["state"] == "completed", done
    first = provider.seen[0]
    assert first[-1] == Message(Role.USER, "Ekli belgeyi incele.")
    assert any("belge_1" in text and "Kapanış" in text for text in data(first))
    # Headers are text someone else wrote; the platform folds system turns into its
    # instructions, so a note sent as one would have become part of them.
    assert "Kapanış" not in instructions(first)
    assert "Documents uploaded in this conversation" not in instructions(first)


def test_two_documents_are_both_named_and_the_attached_one_is_marked(tmp_path):
    provider = scripted(finish())
    runner, client = runtime(tmp_path, provider)
    runner._trust_loop = True
    with client:
        sid, headers = session(client)
        upload(client, sid, headers)
        second = upload(client, sid, headers, content=csv_with(9500)).json()
        route = f"/v1/sessions/{sid}/turns"
        admitted = client.post(
            route,
            headers=headers,
            json={
                "request_id": uuid4().hex,
                "question": "İki belgenin nisan kapanışını karşılaştır.",
                "document_ref": second["document_ref"],
            },
        )
        done = wait_http(client, f"{route}/{admitted.json()['turn_id']}", headers)
        assert done["state"] == "completed", done
    (note,) = [text for text in data(provider.seen[0]) if "belge_1" in text]
    documents = json.loads(note[note.index("{") :])["documents"]
    assert [(d["name"], d["attached_to_this_question"]) for d in documents] == [
        ("belge_1", False),
        ("belge_2", True),
    ]


def test_the_next_question_sees_the_last_exchange_and_its_table(tmp_path):
    runner, provider = served(
        tmp_path, read_total(), finish("Tablo hazır.", publish="a1"), finish("Evet.")
    )
    sid = uuid4().hex
    first = runner(sid, uuid4().hex, "Konut kredisi tablosunu getir.")
    assert first.result is not None
    runner(sid, uuid4().hex, "Bu tablonun son ayı hangisi?")
    shown = "\n".join(data(provider.seen[2]))
    assert "analiz_1" in shown
    assert "Soru: Konut kredisi tablosunu getir." in shown and "Tablo hazır." in shown


def test_a_selected_older_table_is_named_as_the_one_asked_about(tmp_path):
    runner, provider = served(
        tmp_path,
        read_total(),
        finish("Birinci tablo.", publish="a1"),
        read_total(),
        finish("İkinci tablo.", publish="a1"),
        finish("Seçili tablo açıklandı."),
    )
    sid, older = uuid4().hex, uuid4().hex
    first = runner(sid, older, "Konut kredisi tablosunu getir.")
    runner(sid, uuid4().hex, "Aynı tabloyu tekrar getir.")
    assert first.result is not None
    selection = SelectedResult(older, first.result.result_ref, first.result.version)
    runner.selected(sid, uuid4().hex, "Bu tabloyu açıkla.", selection)
    shown = "\n".join(data(provider.seen[-1]))
    assert "analiz_1 tablosunu seçerek sordu" in shown
    assert "analiz_2 tablosunu seçerek" not in shown
    # Both tables stay listed by name; the selection says which one "bu tablo" is.
    assert "- analiz_1:" in shown and "- analiz_2:" in shown


def test_a_return_to_the_first_topic_finds_it_while_it_fits():
    memory = Conversation(
        [Exchange("Konut kredisi nasıl?", "Arttı."), Exchange("Ya taşıt?", "Azaldı.")]
    )
    spoken = memory.context({})["exchange"]
    assert "Konut kredisi nasıl?" in spoken and "yer sınırı" not in spoken


def test_turns_that_no_longer_fit_are_said_to_be_missing_not_summarised():
    long = "x" * 10_000
    memory = Conversation([Exchange(f"soru {n}", long) for n in range(1, 6)])
    spoken = memory.context({})["exchange"]
    assert "en eski 3 turu yer sınırı yüzünden burada yok" in spoken
    assert "soru 1" not in spoken and "soru 5" in spoken


def test_after_a_restart_the_documents_and_the_exchange_reach_the_model(tmp_path):
    store = ConversationStore(tmp_path / "history.sqlite")
    owner, _ = store.create_owner()
    sid = uuid4().hex
    store.create_conversation(owner_id=owner, conversation_id=sid, token="t", title="x")
    before, _ = served(tmp_path, store=store, document_uploads=True)
    before.admit_document(sid, "text/csv", csv_with(9000))
    turn(store, sid, "t1", "Belgedeki kapanışlara bak.", answer="Üç ay okundu.", status="completed")

    after, provider = served(tmp_path, finish(), store=store, document_uploads=True)
    after(sid, uuid4().hex, "İlk sorumda ne sormuştum?")
    shown = data(provider.seen[0])
    assert any("belge_1" in text and "Kapanış" in text for text in shown)
    assert any("Soru: Belgedeki kapanışlara bak." in text for text in shown)


def test_what_an_address_in_the_question_offers_reaches_the_model(tmp_path):
    runner, provider = served(tmp_path, finish(), web_url_fetch=FakeFetch())
    runner(uuid4().hex, uuid4().hex, QUESTION)
    shown = data(provider.seen[0])
    assert any("What the web address in the question offers" in text for text in shown)
    assert any("Tutar (Milyon TL)" in text for text in shown)
    assert "Tutar (Milyon TL)" not in instructions(provider.seen[0])


class TestThePromptSpeaksTheProtocolTheModelIsGiven:
    def test_no_field_the_menu_does_not_have_is_described(self):
        for word in ("`done`", "`state`", "`note`", "`id` ver"):
            assert word not in INSTRUCTIONS
        assert "`finish`" in INSTRUCTIONS and "a1, a2" in INSTRUCTIONS
        assert "state" not in DROPPED

    def test_finish_can_ask_and_the_loop_reads_it(self):
        (entry,) = [e for e in tool_menu(ToolRegistry()) if e["function"]["name"] == FINISH]
        assert set(entry["function"]["parameters"]["properties"]) == {"answer", "publish", "ask"}
        step = _asked_for(
            Completion(
                text="",
                model="m",
                tool_calls=finish("Hangi dönemi kastettiğini bilmiyorum.", ask="Hangi yıl?"),
            )
        )
        assert step is not None and step.done and step.ask == "Hangi yıl?"
