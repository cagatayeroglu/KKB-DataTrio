"""A conversation survives a restart: messages, uploads and the published table.

The service is rebuilt from scratch between the two halves of each test, exactly
as a restarted process would be, over the same state root.
"""

import json

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


@pytest.fixture
def launch(tmp_path):
    """Start the API over a fixed state root; call it again for a restart."""
    started = []

    def start(*responses):
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
