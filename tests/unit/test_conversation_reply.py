"""Conversational replies: no tool for small talk, and earlier analysis stays in reach.

One planner call decides between tool steps, a clarification and a reply. A reply
runs nothing, publishes nothing and is gated: a figure in it must bind to a result
this conversation already published.
"""

import json
import re

from test_catalog_continuation import TOTAL
from test_document_dataset import csv, served, table_step, upload
from test_document_table import ask, step

from kkb_agent.agent import Workspace
from kkb_agent.lakehouse import open_lakehouse

__all__ = ["served"]  # the fixture is imported for use here


def reply(text, question="q"):
    return json.dumps({"question": question, "steps": [], "clarification": None, "reply": text})


def planner_messages(runner):
    return [[m.content for m in conversation] for conversation in runner._provider.seen]


def test_a_greeting_is_answered_without_any_tool_or_publication(served):
    runner, client, sid, headers = served(reply("Merhaba! Verilerle ilgili ne sormak istersiniz?"))
    answer = ask(client, sid, headers, "Merhaba")
    assert answer["state"] == "completed", answer
    assert answer["answer"]["status"] == "accepted"
    assert answer["answer"]["text"].startswith("Merhaba!")
    assert answer["answer"]["result"] is None
    assert answer["answer"]["notices"] == []  # no figure, so no binding notes to show
    assert len(runner._provider.seen) == 1  # one planner call, no writer, no repair
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == []


def test_small_talk_between_analyses_keeps_the_table_and_the_context(served):
    runner, client, sid, headers = served(
        table_step(),
        "Başvuru tablosu hazır.",
        reply("İyiyim, teşekkürler. Tabloyla devam edebiliriz."),
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Konut kredisi eklendi.",
    )
    document = upload(client, sid, headers, csv())
    first = ask(client, sid, headers, "Belgeden aylık tablo yap.", document_ref=document)
    table = first["answer"]["result"]
    chat = ask(client, sid, headers, "Selam, nasılsın?", selected_result_id=table["result_ref"])
    assert chat["answer"]["status"] == "accepted" and chat["answer"]["result"] is None
    follow = ask(
        client,
        sid,
        headers,
        "Peki o tabloya toplam konut kredisini ekler misin?",
        selected_result_id=table["result_ref"],
    )
    assert follow["answer"]["status"] == "accepted", follow
    assert {c["label"] for c in follow["answer"]["result"]["cells"]} >= {"Başvuru Sayısı", TOTAL}
    last_plan = planner_messages(runner)[-2]  # the follow-up's planner call (writer is last)
    history = next(m for m in last_plan if m.startswith("Earlier turns of this conversation"))
    assert "Selam, nasılsın?" in history and "Belgeden aylık tablo yap." in history
    assert any("analiz_1" in m for m in last_plan)  # the published table is still offered
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == ["analiz_1", "analiz_3"]


def test_a_reply_cannot_introduce_a_figure(served):
    _, client, sid, headers = served(reply("Toplam konut kredisi 999 milyon TL oldu."))
    answer = ask(client, sid, headers, "Konut kredisi ne kadar?")
    assert answer["answer"]["status"] == "abstained", answer
    # Identifiers are random hex and contain a digit run such as 999 by chance,
    # which failed this guard in about one run in twenty. Blank them so the
    # guard keeps covering the whole payload the reader receives.
    payload = re.sub(r"[0-9a-f]{16,}", "", json.dumps(answer))
    assert "999" not in payload, payload


def test_a_reply_never_makes_an_unresolved_published_figure_quotable(served):
    runner, client, sid, headers = served(
        table_step(),
        "Tablo hazır.",
        reply("Haziran 2026 başvuru sayısı 512 idi."),
    )
    document = upload(client, sid, headers, csv())
    ask(client, sid, headers, "Belgeden aylık tablo yap.", document_ref=document)
    answer = ask(client, sid, headers, "Hazirandaki başvuru sayısı neydi, tekrar söyler misin?")
    # 512 has no stated unit, so the gate still withholds it: a reply never makes an
    # unresolved figure quotable. The turn abstains rather than inventing a unit.
    assert answer["answer"]["status"] == "abstained", answer


def test_a_message_with_a_document_cannot_be_answered_by_a_reply(served):
    runner, client, sid, headers = served(
        reply("Belgeyi inceledim, güzel görünüyor."),
        table_step(),
        "Tablo hazır.",
    )
    document = upload(client, sid, headers, csv())
    answer = ask(client, sid, headers, "Bu belgeye bak.", document_ref=document)
    assert answer["answer"]["status"] == "accepted" and answer["answer"]["result"], answer
    repair = planner_messages(runner)[1]
    assert any("plan tool steps to read it instead of a reply" in m for m in repair)
