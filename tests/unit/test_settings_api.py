"""A browser may narrow its own runtime, never widen it (DEC-162)."""

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG
from test_conversation_persistence import owner
from test_document_dataset import BASE, seed
from test_prepared_api import wait_http

from kkb_agent.agent.loop import MAX_HISTORY_TURNS
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService, TurnSettings
from kkb_agent.api.store import DATABASE_NAME, ConversationStore
from kkb_agent.llm import scripted


@pytest.fixture
def api(tmp_path):
    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        store=store,
    )
    service = AnalysisService(
        runner,
        mode="scripted",
        document_store=runner.admit_document,
        store=store,
        ocr=True,
        official_acquisition=True,
        web_search=True,
        web_url=True,
    )
    try:
        with TestClient(create_app(service), base_url=BASE) as client:
            yield client, service
    finally:
        service.close()
        store.close()


def test_the_page_lists_what_this_deployment_offers_and_nothing_else(api):
    client, _ = api
    key = {"X-KKB-Owner-Token": owner(client)}

    settings = client.get("/v1/settings", headers=key).json()

    assert settings["available"] == [
        "document_upload",
        "document_ocr",
        "official_acquisition",
        "web_search",
        "web_url",
    ]
    assert settings["disabled"] == []
    assert settings["history_turns"] == settings["max_history_turns"] == MAX_HISTORY_TURNS


def test_a_capability_can_be_switched_off_and_back_on_and_survives_a_reread(api):
    client, service = api
    key = {"X-KKB-Owner-Token": owner(client)}

    off = client.patch(
        "/v1/settings", json={"disabled": ["web_search", "official_acquisition"]}, headers=key
    )
    assert off.status_code == 200
    assert off.json()["disabled"] == ["official_acquisition", "web_search"]
    assert client.get("/v1/settings", headers=key).json()["disabled"] == [
        "official_acquisition",
        "web_search",
    ]

    # Switching one back on is allowed: the operator's own capability is unchanged.
    back = client.patch("/v1/settings", json={"disabled": []}, headers=key)
    assert back.json()["disabled"] == []


def test_a_capability_the_operator_did_not_enable_cannot_be_named(tmp_path):
    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
    )
    service = AnalysisService(runner, mode="scripted", store=store)
    try:
        with TestClient(create_app(service), base_url=BASE) as client:
            key = {"X-KKB-Owner-Token": owner(client)}
            assert client.get("/v1/settings", headers=key).json()["available"] == []
            refused = client.patch("/v1/settings", json={"disabled": ["web_search"]}, headers=key)
            assert refused.status_code == 422
    finally:
        service.close()
        store.close()


def test_history_turns_are_bounded_by_the_built_in_ceiling(api):
    client, _ = api
    key = {"X-KKB-Owner-Token": owner(client)}

    assert (
        client.patch("/v1/settings", json={"history_turns": 2}, headers=key).json()["history_turns"]
        == 2
    )
    assert (
        client.patch(
            "/v1/settings", json={"history_turns": MAX_HISTORY_TURNS + 1}, headers=key
        ).status_code
        == 422
    )


def test_a_switched_off_upload_is_refused_for_that_owner_only(api):
    client, service = api
    key = {"X-KKB-Owner-Token": owner(client)}
    session = client.post("/v1/sessions", json={}, headers=key).json()
    headers = {"X-KKB-Session-Token": session["token"]}
    csv = b"Ay;Deger\n2026-01;1\n"

    client.patch("/v1/settings", json={"disabled": ["document_upload"]}, headers=key)
    refused = client.post(
        f"/v1/sessions/{session['session_id']}/documents",
        content=csv,
        headers={**headers, "Content-Type": "text/csv"},
    )
    assert refused.status_code == 503

    # Another browser's key is unaffected: the choice belongs to one owner.
    other = {"X-KKB-Owner-Token": owner(client)}
    second = client.post("/v1/sessions", json={}, headers=other).json()
    admitted = client.post(
        f"/v1/sessions/{second['session_id']}/documents",
        content=csv,
        headers={"X-KKB-Session-Token": second["token"], "Content-Type": "text/csv"},
    )
    assert admitted.status_code == 201


def test_a_turn_carries_the_owners_choices_only_when_they_made_one(api):
    client, service = api
    key = {"X-KKB-Owner-Token": owner(client)}
    seen: list[TurnSettings | None] = []

    answered = service._runner

    def runner(session_id, turn_id, question, *, is_continuation, **extra):
        seen.append(extra.get("settings"))
        return answered(session_id, turn_id, question, is_continuation=is_continuation, **extra)

    service._runner = runner
    session = client.post("/v1/sessions", json={}, headers=key).json()
    headers = {"X-KKB-Session-Token": session["token"]}
    turns = f"/v1/sessions/{session['session_id']}/turns"
    body = {"request_id": "a" * 32, "question": "selam"}
    first = client.post(turns, json=body, headers=headers).json()
    wait_http(client, f"{turns}/{first['turn_id']}", headers)
    client.patch("/v1/settings", json={"disabled": ["web_search"]}, headers=key)
    second = client.post(turns, json={**body, "request_id": "b" * 32}, headers=headers).json()
    wait_http(client, f"{turns}/{second['turn_id']}", headers)

    assert seen[0] is None
    assert seen[1] is not None and seen[1].disabled == frozenset({"web_search"})


def test_the_prompt_parts_are_readable_with_their_digests_and_nothing_is_editable(api):
    """The sources model calls are assembled from; reading is the whole contract."""
    import hashlib

    client, _ = api
    key = {"X-KKB-Owner-Token": owner(client)}

    body = client.get("/v1/prompts", headers=key).json()
    assert len(body["parts"]) >= 8
    by_id = {part["part_id"]: part for part in body["parts"]}
    assert "planner.system" in by_id and "writer.synthesis" in by_id
    for part in body["parts"]:
        assert part["content"].strip() and part["title"].strip()
        assert hashlib.sha256(part["content"].encode()).hexdigest() == part["content_sha256"]

    # No editor exists: a write to the surface is not a route.
    assert client.post("/v1/prompts", json={}, headers=key).status_code in (404, 405)
    assert client.get("/v1/prompts").status_code == 422  # the owner key is required


def test_selected_model_reaches_transport_in_new_chats_and_preserves_other_settings(api):
    import json

    from test_kloudeks_provider import CHAT_MODEL, Server, chat, provider

    from kkb_agent.llm.config import SELECTABLE_CHAT_MODELS

    client, service = api
    service._models = SELECTABLE_CHAT_MODELS
    service._model = CHAT_MODEL
    server = Server(
        *[
            chat(json.dumps({"question": "selam", "steps": [], "reply": "Merhaba."}))
            for _ in range(3)
        ]
    )
    target = provider(server)
    service._runner._provider = target
    key = {"X-KKB-Owner-Token": owner(client)}
    other = {"X-KKB-Owner-Token": owner(client)}
    try:
        initial = client.get("/v1/settings", headers=key).json()
        assert initial["models"] == list(SELECTABLE_CHAT_MODELS)
        assert initial["model"] == CHAT_MODEL
        for index, model in enumerate([CHAT_MODEL, SELECTABLE_CHAT_MODELS[1], CHAT_MODEL]):
            changed = client.patch(
                "/v1/settings", headers=key, json={"model": model, "history_turns": 2}
            ).json()
            assert changed["model"] == model and changed["disabled"] == []
            assert client.get("/v1/settings", headers=other).json()["model"] == CHAT_MODEL
            session = client.post("/v1/sessions", json={}, headers=key).json()
            headers = {"X-KKB-Session-Token": session["token"]}
            turns = f"/v1/sessions/{session['session_id']}/turns"
            turn = client.post(
                turns, json={"request_id": str(index) * 32, "question": "selam"}, headers=headers
            ).json()
            wait_http(client, f"{turns}/{turn['turn_id']}", headers)
            assert server.bodies()[-1]["model"] == model
        refused = client.patch("/v1/settings", headers=key, json={"model": "arbitrary/model"})
        assert refused.status_code == 422
        assert (
            client.patch("/v1/settings", headers=key, json={"disabled": ["web_search"]}).json()[
                "model"
            ]
            == CHAT_MODEL
        )
    finally:
        target.close()
