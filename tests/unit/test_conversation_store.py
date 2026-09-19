"""The conversation store: owned, restart-safe metadata; no analytical values."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from kkb_agent.api.store import DATABASE_NAME, SCHEMA, ConversationStore, StoreError


@pytest.fixture
def store(tmp_path):
    opened = ConversationStore(tmp_path / DATABASE_NAME)
    yield opened
    opened.close()


def conversation(store, title="Yeni sohbet", owner=None):
    owner_id, owner_token = owner if owner is not None else store.create_owner()
    conversation_id, token = uuid4().hex, "conversation-token"
    store.create_conversation(
        owner_id=owner_id, conversation_id=conversation_id, token=token, title=title
    )
    return owner_id, owner_token, conversation_id, token


def test_a_conversation_id_alone_opens_nothing(store):
    owner_id, owner_token, conversation_id, token = conversation(store)
    assert store.opens(conversation_id, token=token, owner_token=None)
    assert store.opens(conversation_id, token=None, owner_token=owner_token)
    assert not store.opens(conversation_id, token=None, owner_token=None)
    assert not store.opens(conversation_id, token="guess", owner_token="guess")
    assert not store.opens(uuid4().hex, token=token, owner_token=owner_token)
    other_id, other_token = store.create_owner()
    assert not store.opens(conversation_id, token=None, owner_token=other_token)
    assert store.owner_of(owner_id, owner_token) and not store.owner_of(other_id, owner_token)


def test_an_unknown_owner_cannot_hold_a_conversation(store):
    with pytest.raises(StoreError, match="unknown_owner"):
        store.create_conversation(
            owner_id=uuid4().hex, conversation_id=uuid4().hex, token="t", title="x"
        )


def test_messages_keep_their_order_and_a_retried_turn_is_not_a_second_message(store):
    _, _, conversation_id, _ = conversation(store)
    turn = uuid4().hex
    store.append_message(conversation_id, turn_id=turn, role="user", text="Merhaba")
    store.append_message(
        conversation_id, turn_id=turn, role="assistant", text="Merhaba!", status="accepted"
    )
    # The same turn answered again (retry, reconnect) updates in place.
    store.append_message(
        conversation_id,
        turn_id=turn,
        role="assistant",
        text="Merhaba, buyurun.",
        status="accepted",
        result_ref="r1",
        result_version="v1",
    )
    second = uuid4().hex
    store.append_message(conversation_id, turn_id=second, role="user", text="Tabloyu göster")
    messages = store.messages(conversation_id)
    assert [(m.sequence, m.role, m.text) for m in messages] == [
        (1, "user", "Merhaba"),
        (2, "assistant", "Merhaba, buyurun."),
        (3, "user", "Tabloyu göster"),
    ]
    assert (messages[1].result_ref, messages[1].result_version) == ("r1", "v1")
    assert store.turn_count(conversation_id) == 2
    assert store.history(conversation_id, 6) == [("Merhaba", "Merhaba, buyurun.")]


def test_listing_is_by_owner_recency_archive_and_search(store):
    owner = store.create_owner()
    owner_id, _, first, _ = conversation(store, title="Konut kredisi", owner=owner)
    _, _, second, _ = conversation(store, title="Satış analizi", owner=owner)
    other_owner, _ = store.create_owner()
    store.create_conversation(
        owner_id=other_owner, conversation_id=uuid4().hex, token="t", title="Başkasının sohbeti"
    )
    store.append_message(second, turn_id=uuid4().hex, role="user", text="EVDS faizi")
    listed = store.list_conversations(owner_id)
    assert [item.conversation_id for item in listed] == [second, first]  # most recent first
    assert [item.title for item in store.list_conversations(owner_id, search="konut")] == [
        "Konut kredisi"
    ]
    # Search also reaches message text, not only titles.
    assert [item.conversation_id for item in store.list_conversations(owner_id, search="evds")] == [
        second
    ]
    store.update_conversation(first, archived=True)
    assert [item.conversation_id for item in store.list_conversations(owner_id)] == [second]
    assert [item.conversation_id for item in store.list_conversations(owner_id, archived=True)] == [
        first
    ]
    # Archiving is not deleting: the messages are still there when it comes back.
    store.update_conversation(first, archived=False, title="Konut kredisi ve faiz")
    assert store.conversation(first).title == "Konut kredisi ve faiz"


def test_documents_and_publications_are_read_back_after_reopening(tmp_path):
    path = tmp_path / DATABASE_NAME
    store = ConversationStore(path)
    _, _, conversation_id, _ = conversation(store)
    store.add_document(
        conversation_id,
        document_ref="a" * 32,
        name="belge_1",
        document_format="csv",
        media_type="text/csv",
        sha256="f" * 64,
        byte_count=59,
        path=tmp_path / "documents" / "a.csv",
        admitted_at=datetime(2026, 9, 17, tzinfo=UTC),
    )
    store.add_publication(
        conversation_id,
        turn_id="b" * 32,
        name="analiz_1",
        artifact_id="c" * 64,
        result_ref="d" * 32,
        result_version="e" * 64,
    )
    store.close()

    reopened = ConversationStore(path)
    try:
        (document,) = reopened.documents(conversation_id)
        assert (document.name, document.sha256, document.byte_count) == ("belge_1", "f" * 64, 59)
        assert document.path == Path(tmp_path / "documents" / "a.csv")
        (publication,) = reopened.publications(conversation_id)
        assert (publication.name, publication.result_ref) == ("analiz_1", "d" * 32)
        assert reopened.conversation(conversation_id).title == "Yeni sohbet"
    finally:
        reopened.close()


def test_old_conversation_schema_migrates_and_soft_delete_filters_every_list(tmp_path):
    path = tmp_path / DATABASE_NAME
    with sqlite3.connect(path) as legacy:
        legacy.executescript(
            SCHEMA.replace(
                "    updated_at      TEXT NOT NULL,\n    deleted_at      TEXT\n",
                "    updated_at      TEXT NOT NULL\n",
            )
        )
    store = ConversationStore(path)
    try:
        owner_id, owner_token, sid, token = conversation(store, title="Eski kredi sohbeti")
        store.append_message(sid, turn_id=uuid4().hex, role="user", text="Konut kredisi")
        assert store.opens(sid, token=token, owner_token=None)
        store.soft_delete(sid)
        assert store.is_deleted(sid)
        assert store.conversation(sid) is None
        assert not store.opens(sid, token=token, owner_token=owner_token)
        assert store.opens(sid, token=token, owner_token=None, include_deleted=True)
        assert store.list_conversations(owner_id) == []
        assert store.list_conversations(owner_id, archived=True) == []
        assert store.list_conversations(owner_id, search="kredi") == []
        assert [m.text for m in store.messages(sid)] == ["Konut kredisi"]
    finally:
        store.close()


def test_restart_finalizes_only_preexisting_unfinished_runs(tmp_path):
    path = tmp_path / DATABASE_NAME
    first = ConversationStore(path)
    _, _, sid, _ = conversation(first)
    old_run, new_run = uuid4().hex, uuid4().hex
    first.start_run(sid, run_id=old_run, turn_id=uuid4().hex, question="Eski tur")
    first.close()

    restarted = ConversationStore(path)
    try:
        (interrupted,) = restarted.runs(sid)
        assert interrupted.run_id == old_run
        assert interrupted.status == "failed" and interrupted.error == "interrupted"
        assert interrupted.ended_at is not None
        assert interrupted.duration_ms >= 0
        assert interrupted.ended_at >= interrupted.started_at

        restarted.start_run(sid, run_id=new_run, turn_id=uuid4().hex, question="Yeni tur")
        fresh = {run.run_id: run for run in restarted.runs(sid)}[new_run]
        assert fresh.status == "running" and fresh.ended_at is None
        assert fresh.error is None
    finally:
        restarted.close()
