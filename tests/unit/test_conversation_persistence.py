"""A conversation survives a restart: messages, uploads and the published table.

The service is rebuilt from scratch between the two halves of each test, exactly
as a restarted process would be, over the same state root.
"""

import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, TOTAL, proposal
from test_document_dataset import BASE, csv, seed, table_step
from test_document_table import ask, step

from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService
from kkb_agent.api.store import DATABASE_NAME, ConversationStore
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import TransportError


@pytest.fixture
def launch(tmp_path):
    """Start the API over a fixed state root; call it again for a restart."""
    started = []

    def start(*responses, cleanup=True):
        root = tmp_path.resolve() / "prepared"
        if not root.exists():
            seed(root)
        store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
        runner = PreparedRunner(
            scripted(*responses),
            root,
            tmp_path.resolve() / "state" / "runtime",
            catalog_bytes=CATALOG.read_bytes(),
            document_uploads=True,
            store=store,
        )
        service = AnalysisService(
            runner,
            mode="scripted",
            selected_runner=runner.selected,
            document_store=runner.admit_document,
            store=store,
            stored_result=runner.published_result,
            session_cleanup=runner.delete_session if cleanup else None,
        )
        client = TestClient(create_app(service, prepared=runner.status), base_url=BASE)
        client.__enter__()
        started.append((client, store))
        return runner, client

    yield start
    for client, store in started:
        client.__exit__(None, None, None)
        store.close()


def owner(client):
    created = client.post("/v1/owner", json={}).json()
    return created["owner_token"]


def open_conversation(client, owner_token):
    created = client.post(
        "/v1/sessions", json={}, headers={"X-KKB-Owner-Token": owner_token}
    ).json()
    return created["session_id"], {"X-KKB-Session-Token": created["token"]}, created


def upload(client, sid, headers, content=None):
    response = client.post(
        f"/v1/sessions/{sid}/documents",
        content=content if content is not None else csv(),
        headers={**headers, "Content-Type": "text/csv"},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_ref"]


def test_a_conversation_its_messages_table_and_upload_come_back_after_a_restart(launch):
    runner, client = launch(
        table_step(), "Başvuru tablosu hazır.", proposal(clarification="unsupported_request")
    )
    owner_token = owner(client)
    sid, headers, created = open_conversation(client, owner_token)
    assert created["survives_restart"] is True
    document = upload(client, sid, headers)
    first = ask(client, sid, headers, "Belgeden aylık tablo yap.", document_ref=document)
    assert first["answer"]["status"] == "accepted", first
    table = first["answer"]["result"]

    # --- restart: a new store, runner, service and client over the same state root.
    _, reopened = launch(
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Konut kredisi eklendi.",
    )
    listed = reopened.get("/v1/conversations", headers={"X-KKB-Owner-Token": owner_token}).json()[
        "conversations"
    ]
    assert [item["conversation_id"] for item in listed] == [sid]
    assert listed[0]["title"] == "Belgeden aylık tablo yap." and listed[0]["turns"] == 1

    detail = reopened.get(f"/v1/conversations/{sid}", headers=headers).json()
    assert [(m["role"], m["text"]) for m in detail["messages"]] == [
        ("user", "Belgeden aylık tablo yap."),
        ("assistant", first["answer"]["text"]),
    ]
    assert detail["messages"][1]["result_ref"] == table["result_ref"]
    assert detail["messages"][1]["result_version"] == table["version"]
    assert [(d["name"], d["document_format"]) for d in detail["documents"]] == [("belge_1", "csv")]

    # The table itself comes back from its receipt - same reference, same version,
    # same cells, proof rebuilt - so the reopened conversation shows what it showed.
    stored = reopened.get(f"/v1/conversations/{sid}/results/{first['turn_id']}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["result_ref"] == table["result_ref"]
    assert stored.json()["version"] == table["version"]
    assert [c["value"] for c in stored.json()["cells"]] == [c["value"] for c in table["cells"]]
    assert stored.json()["proof"]["availability"] in ("available", "unavailable")
    # The owner's key reads it too; a turn that published nothing is not found.
    assert (
        reopened.get(
            f"/v1/conversations/{sid}/results/{first['turn_id']}",
            headers={"X-KKB-Session-Token": owner_token},
        ).status_code
        == 200
    )
    assert (
        reopened.get(f"/v1/conversations/{sid}/results/{'0' * 32}", headers=headers).status_code
        == 404
    )

    # The published table is still selectable, and the upload is still readable.
    second = ask(
        reopened,
        sid,
        headers,
        "Tabloya toplam konut kredisini ekle.",
        selected_result_id=table["result_ref"],
    )
    assert second["answer"]["status"] == "accepted", second
    labels = {cell["label"] for cell in second["answer"]["result"]["cells"]}
    assert {"Başvuru Sayısı", TOTAL} <= labels
    # The turn counter continued across the restart: this publication is analiz_2.
    after = reopened.get(f"/v1/conversations/{sid}", headers=headers).json()
    assert [m["role"] for m in after["messages"]] == ["user", "assistant", "user", "assistant"]
    assert after["conversation"]["turns"] == 2
    assert "analiz_2" in json.dumps(second)


def test_the_owner_key_opens_its_conversations_and_an_id_alone_does_not(launch):
    _, client = launch(proposal(clarification="unsupported_request"), "-")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    stranger = owner(client)

    assert client.get(f"/v1/conversations/{sid}", headers=headers).status_code == 200
    assert (
        client.get(
            f"/v1/conversations/{sid}", headers={"X-KKB-Session-Token": owner_token}
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/v1/conversations/{sid}", headers={"X-KKB-Session-Token": stranger}
        ).status_code
        == 404
    )
    assert (
        client.get("/v1/conversations", headers={"X-KKB-Owner-Token": stranger}).json()[
            "conversations"
        ]
        == []
    )
    # A session cannot be created without an owner key when the store is enabled.
    assert client.post("/v1/sessions", json={}).status_code == 403


def test_renaming_and_archiving_survive_and_never_delete_messages(launch):
    _, client = launch(proposal(clarification="unsupported_request"), "-")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    ask(client, sid, headers, "Konut kredisini göster.")

    renamed = client.patch(
        f"/v1/conversations/{sid}", json={"title": "Konut kredisi"}, headers=headers
    ).json()
    assert renamed["title"] == "Konut kredisi"
    client.patch(f"/v1/conversations/{sid}", json={"archived": True}, headers=headers)

    _, reopened = launch()
    header = {"X-KKB-Owner-Token": owner_token}
    assert reopened.get("/v1/conversations", headers=header).json()["conversations"] == []
    archived = reopened.get("/v1/conversations?archived=true", headers=header).json()
    assert [item["title"] for item in archived["conversations"]] == ["Konut kredisi"]
    detail = reopened.get(f"/v1/conversations/{sid}", headers=headers).json()
    assert [m["text"] for m in detail["messages"]][0] == "Konut kredisini göster."
    assert reopened.get("/v1/conversations?search=konut", headers=header).status_code == 200


def test_two_conversations_keep_their_own_documents_and_tables(launch):
    runner, client = launch(
        table_step(),
        "Birinci tablo.",
        table_step(),
        "İkinci tablo.",
    )
    owner_token = owner(client)
    first_id, first_headers, _ = open_conversation(client, owner_token)
    second_id, second_headers, _ = open_conversation(client, owner_token)
    first_document = upload(client, first_id, first_headers)
    second_document = upload(client, second_id, second_headers, csv(header="Yatış"))
    ask(client, first_id, first_headers, "Belgeden tablo yap.", document_ref=first_document)
    ask(client, second_id, second_headers, "Belgeden tablo yap.", document_ref=second_document)

    _, reopened = launch()
    first = reopened.get(f"/v1/conversations/{first_id}", headers=first_headers).json()
    second = reopened.get(f"/v1/conversations/{second_id}", headers=second_headers).json()
    assert [d["document_ref"] for d in first["documents"]] == [first_document]
    assert [d["document_ref"] for d in second["documents"]] == [second_document]
    assert first["messages"][1]["result_ref"] != second["messages"][1]["result_ref"]


def test_soft_delete_hides_chat_but_keeps_trace_and_cleans_session_data(launch):
    runner, client = launch(table_step(), "Tablo hazır.")
    owner_token = owner(client)
    sid, headers, _ = open_conversation(client, owner_token)
    document = upload(client, sid, headers)
    completed = ask(client, sid, headers, "Belgeden tablo yap.", document_ref=document)
    assert completed["answer"]["status"] == "accepted"
    trace = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert trace
    session_dir = runner.run_root / sid
    assert session_dir.exists()
    owner_headers = {"X-KKB-Owner-Token": owner_token}

    deleted = client.delete(f"/v1/conversations/{sid}", headers=owner_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert not session_dir.exists()
    assert client.get("/v1/conversations", headers=owner_headers).json()["conversations"] == []
    assert (
        client.get("/v1/conversations?search=belgeden", headers=owner_headers).json()[
            "conversations"
        ]
        == []
    )
    assert client.get(f"/v1/conversations/{sid}", headers=headers).status_code == 404
    assert client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"] == trace
    indexed = client.get("/v1/trace-conversations", headers=owner_headers).json()["conversations"]
    assert [(item["conversation_id"], item["deleted"]) for item in indexed] == [(sid, True)]
    assert (
        client.get("/v1/trace-conversations?search=belgeden", headers=owner_headers).json()[
            "conversations"
        ]
        == indexed
    )
    assert (
        client.get("/v1/trace-conversations?archived=true", headers=owner_headers).json()[
            "conversations"
        ]
        == indexed
    )
    assert (
        client.get("/v1/trace-conversations", headers={"X-KKB-Owner-Token": owner(client)}).json()[
            "conversations"
        ]
        == []
    )

    _, reopened = launch()
    assert reopened.get("/v1/conversations", headers=owner_headers).json()["conversations"] == []
    assert reopened.get(f"/v1/conversations/{sid}", headers=headers).status_code == 404
    assert reopened.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"] == trace
    assert (
        reopened.get("/v1/trace-conversations", headers=owner_headers).json()["conversations"][0][
            "deleted"
        ]
        is True
    )
    gone = reopened.delete(f"/v1/conversations/{sid}/runs", headers=owner_headers)
    assert gone.status_code == 200, gone.text
    assert gone.json()["deleted_runs"] == len(trace)
    assert reopened.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"] == []
    assert (
        reopened.get("/v1/trace-conversations", headers=owner_headers).json()["conversations"] == []
    )


def test_legacy_free_text_run_error_does_not_break_list_or_leak_detail(launch, tmp_path):
    _, client = launch(table_step(), "Tablo hazır.")
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    document = upload(client, sid, headers)
    ask(client, sid, headers, "Belgeden tablo yap.", document_ref=document)
    path = tmp_path.resolve() / "state" / DATABASE_NAME
    legacy_id = uuid4().hex
    internal_id = uuid4().hex
    with sqlite3.connect(path) as db:
        started = db.execute(
            "SELECT started_at FROM runs WHERE conversation_id = ?", [sid]
        ).fetchone()[0]
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, 'failed', NULL, ?, NULL, 12, ?, ?)",
            [
                legacy_id,
                sid,
                uuid4().hex,
                "Eski sağlayıcı hatası",
                "TransportError: Kloudeks request failed (ReadTimeout) secret/path",
                started,
                started,
            ],
        )
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, 'unknown', NULL, NULL, NULL, 0, ?, ?)",
            [uuid4().hex, sid, uuid4().hex, "Bozuk durum", started, started],
        )
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, 'failed', NULL, NULL, NULL, 0, ?, ?)",
            [uuid4().hex, sid, uuid4().hex, "Bozuk tarih", "not-a-date", started],
        )
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, 'failed', NULL, ?, NULL, 1, ?, ?)",
            [
                internal_id,
                sid,
                uuid4().hex,
                "Eski iç hata",
                "RuntimeError: private/path",
                started,
                started,
            ],
        )
    response = client.get(f"/v1/conversations/{sid}/runs", headers=headers)
    assert response.status_code == 200, response.text
    runs = response.json()["runs"]
    assert len(runs) == 3  # Both malformed rows remain on disk but cannot hide these.
    assert {run["run_id"]: run["error"] for run in runs}[legacy_id] == "provider_failed"
    assert {run["run_id"]: run["error"] for run in runs}[internal_id] == "internal_error"
    assert all(term not in response.text for term in ("ReadTimeout", "secret/path", "private/path"))
    detail = client.get(f"/v1/conversations/{sid}/runs/{legacy_id}", headers=headers)
    assert detail.status_code == 200 and detail.json()["run"]["error"] == "provider_failed"


def test_new_failed_run_stores_only_structured_provider_error(launch, tmp_path):
    _, client = launch(TransportError("private transport failure"))
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    failed = ask(client, sid, headers, "Sağlayıcı hata testi")
    assert failed["state"] == "failed" and failed["error"] == "provider_failed"
    response = client.get(f"/v1/conversations/{sid}/runs", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["runs"][0]["error"] == "provider_failed"
    assert "private transport failure" not in response.text
    with sqlite3.connect(tmp_path.resolve() / "state" / DATABASE_NAME) as db:
        assert db.execute("SELECT error FROM runs WHERE conversation_id = ?", [sid]).fetchone()[
            0
        ] == ("provider_failed")


def test_restart_projects_interrupted_run_as_finished_trace(launch, tmp_path):
    _, client = launch()
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    stale_id = uuid4().hex
    with sqlite3.connect(tmp_path.resolve() / "state" / DATABASE_NAME) as db:
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, 'running', NULL, NULL, NULL, 0, ?, NULL)",
            [stale_id, sid, uuid4().hex, "Kesilen tur", "2026-09-19T10:00:00+00:00"],
        )
    _, restarted = launch()
    response = restarted.get(f"/v1/conversations/{sid}/runs", headers=headers)
    assert response.status_code == 200, response.text
    (run,) = response.json()["runs"]
    assert run["run_id"] == stale_id and run["status"] == "failed"
    assert run["error"] == "interrupted" and run["ended_at"] is not None
    assert run["duration_ms"] >= 0


def test_delete_requires_owner_key_is_idempotent_and_keeps_other_chats(launch):
    _, client = launch(proposal(clarification="unsupported_request"), "-")
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    other, other_headers, _ = open_conversation(client, own)
    stranger = owner(client)
    owner_headers = {"X-KKB-Owner-Token": own}
    client.patch(f"/v1/conversations/{sid}", json={"archived": True}, headers=headers)
    assert client.delete(f"/v1/conversations/{sid}", headers=headers).status_code == 422
    assert (
        client.delete(
            f"/v1/conversations/{sid}", headers={"X-KKB-Owner-Token": stranger}
        ).status_code
        == 404
    )
    assert client.delete(f"/v1/conversations/{sid}", headers=owner_headers).status_code == 200
    assert client.delete(f"/v1/conversations/{sid}", headers=owner_headers).status_code == 200
    assert (
        client.get("/v1/conversations?archived=true", headers=owner_headers).json()["conversations"]
        == []
    )
    assert client.get(f"/v1/conversations/{other}", headers=other_headers).status_code == 200
    assert (
        client.delete(
            f"/v1/conversations/{other}/runs", headers={"X-KKB-Owner-Token": stranger}
        ).status_code
        == 404
    )
    assert client.delete(f"/v1/conversations/{other}/runs", headers=owner_headers).json() == {
        "api_version": 1,
        "deleted_runs": 0,
    }
    assert client.get(f"/v1/conversations/{other}", headers=other_headers).status_code == 200


def test_explicit_run_delete_never_soft_deletes_conversation_or_table(launch):
    _, client = launch(table_step(), "Tablo hazır.")
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    document = upload(client, sid, headers)
    answer = ask(client, sid, headers, "Belgeden tablo yap.", document_ref=document)
    owner_headers = {"X-KKB-Owner-Token": own}
    runs = client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"]
    assert len(runs) == 1
    removed = client.delete(f"/v1/conversations/{sid}/runs", headers=owner_headers)
    assert removed.status_code == 200 and removed.json()["deleted_runs"] == 1
    assert client.get(f"/v1/conversations/{sid}/runs", headers=headers).json()["runs"] == []
    detail = client.get(f"/v1/conversations/{sid}", headers=headers).json()
    assert detail["conversation"]["conversation_id"] == sid
    assert len(detail["messages"]) == 2
    assert (
        client.get(
            f"/v1/conversations/{sid}/results/{answer['turn_id']}", headers=headers
        ).status_code
        == 200
    )


def test_delete_refuses_linked_session_path_without_touching_target(launch, tmp_path):
    runner, client = launch()
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep")
    linked = runner.run_root / sid
    linked.symlink_to(outside, target_is_directory=True)

    response = client.delete(f"/v1/conversations/{sid}", headers={"X-KKB-Owner-Token": own})
    assert response.status_code == 503
    assert marker.read_text() == "keep" and linked.is_symlink()
    assert client.get(f"/v1/conversations/{sid}", headers=headers).status_code == 404


def test_delete_without_cleanup_binding_fails_closed_and_keeps_chat(launch):
    _, client = launch(cleanup=False)
    own = owner(client)
    sid, headers, _ = open_conversation(client, own)
    response = client.delete(f"/v1/conversations/{sid}", headers={"X-KKB-Owner-Token": own})
    assert response.status_code == 503
    assert client.get(f"/v1/conversations/{sid}", headers=headers).status_code == 200
