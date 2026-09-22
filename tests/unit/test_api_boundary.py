"""Real-gate projection and hostile HTTP/session lifecycle; no external services."""

import asyncio
import json
import threading
import time
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_catalog_continuation import CATALOG, QUESTION, TOTAL, proposal, seed_prepared

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.cancellation import checkpoint
from kkb_agent.agent.loop import PlanningFailed
from kkb_agent.agent.verifier import AnswerStatus, OmittedSentence
from kkb_agent.api.app import create_app
from kkb_agent.api.contracts import MAX_BODY_BYTES, MAX_SESSIONS, MAX_TURNS, Answer, Question
from kkb_agent.api.projection import OutputRefused, project_answer, safe_text
from kkb_agent.api.service import AnalysisService, ServiceError
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import TransportError
from kkb_agent.tools import make_change_detection_tool

SENTINEL = "private-canary-never-publish"
BASE = "http://127.0.0.1:8000"


def quiet_answer():
    return Answer(status=AnswerStatus.ABSTAINED, text="Veri kapsamını belirtin.", omitted_claims=0)


def question(text="Konut kredilerini göster", request_id=None):
    return Question(request_id=request_id or uuid4().hex, question=text)


def finished(service, session, turn):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = service.get_turn(session.session_id, session.token, turn.turn_id)
        if current.state in ("completed", "failed"):
            return current
        time.sleep(0.002)
    pytest.fail("bounded worker did not finish")


@pytest.fixture(scope="module")
def verified(tmp_path_factory):
    root = tmp_path_factory.mktemp("api-gate") / "lake"
    seed_prepared(root)
    with open_lakehouse(root) as lake:
        workspace = Workspace.open(lake.connection, "api-verified-fixture")
        registry = ToolRegistry()
        registry.register(
            make_change_detection_tool(
                lake.connection,
                lineage=lake.lineage,
                inspector=PreparedSeriesInspector(load_reviewed_snapshot(CATALOG.read_bytes())),
            )
        )
        provider = scripted(
            proposal(
                {
                    "step_id": "a",
                    "tool": "change_detection",
                    "arguments": {
                        "operation": "compare",
                        "series_id": TOTAL,
                        "start": "2026-04-30",
                        "end": "2026-06-30",
                    },
                }
            ),
            "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
        )
        answered = Session(provider, registry).answer(
            QUESTION,
            lake.connection,
            workspace=workspace,
            remember="analiz",
        )
        assert answered.answer.status is AnswerStatus.ACCEPTED
        yield answered, workspace.value_of("analiz")


def test_published_projection_retains_exact_cells_and_stable_scoped_ids(verified):
    answered, result = verified
    turn_id = uuid4().hex
    output = project_answer(answered, turn_id=turn_id, published=result)
    again = project_answer(answered, turn_id=turn_id, published=result)
    assert output == again and output.result.version == result.digest()
    assert [c.value for c in output.result.cells] == [v.value for v in result.values]
    assert [(c.unit, c.scale, c.period, c.samples) for c in output.result.cells] == [
        (v.unit, v.scale, v.period, v.samples) for v in result.values
    ]
    assert [c.slot for c in output.result.cells] == list(range(len(result.values)))
    assert len({c.cell_id for c in output.result.cells}) == len(result.values)
    other = project_answer(answered, turn_id=uuid4().hex, published=result)
    assert other.result.result_ref != output.result.result_ref
    assert other.result.cells[0].cell_id != output.result.cells[0].cell_id
    # Without the owning runner's connection no proof chain is fabricated.
    assert output.result.proof.availability == "unavailable" and not output.result.proof.steps
    assert (
        "input_refs" not in output.model_dump_json() and "source_id" not in output.model_dump_json()
    )


@pytest.mark.parametrize("state", [AnswerStatus.QUALIFIED, AnswerStatus.ABSTAINED])
def test_nonaccepted_turn_never_promotes_candidate_or_rejected_text(verified, state):
    answered, result = verified
    unsafe = replace(
        answered,
        answer=replace(
            answered.answer,
            status=state,
            text="Açıklama",
            abstention=SENTINEL,
            omitted=(OmittedSentence(SENTINEL, (SENTINEL,)),),
        ),
    )
    output = project_answer(unsafe, turn_id=uuid4().hex, published=None)
    assert output.result is None and output.omitted_claims == 1
    assert SENTINEL not in output.model_dump_json()
    if state is AnswerStatus.ABSTAINED:
        with pytest.raises(OutputRefused):
            project_answer(unsafe, turn_id=uuid4().hex, published=result)
    else:
        # A qualified turn's table is the tools' own and is published; what was withheld
        # from its prose still never leaves the process.
        shown = project_answer(unsafe, turn_id=uuid4().hex, published=result)
        assert shown.result is not None and SENTINEL not in shown.model_dump_json()


def test_accepted_but_unpublished_turn_does_not_export_candidate(verified):
    answered, _ = verified
    output = project_answer(answered, turn_id=uuid4().hex, published=None)
    assert output.result is None and output.notices


def test_mismatched_publication_refuses_even_with_same_result_id(verified):
    answered, original = verified
    changed = original.model_copy(deep=True)
    changed.values[0].value += 1
    with pytest.raises(OutputRefused, match="publication_mismatch"):
        project_answer(answered, turn_id=uuid4().hex, published=changed)


@pytest.mark.parametrize(
    "text",
    [
        "https://private.example/a?token=" + SENTINEL,
        "C:\\private\\" + SENTINEL,
        "/home/user/" + SENTINEL,
        "Bearer " + SENTINEL,
        "api_key=" + SENTINEL,
    ],
)
def test_locator_and_credential_patterns_are_removed(text):
    assert SENTINEL not in safe_text(text)


def test_known_secret_and_control_filter_preserves_financial_text():
    assert SENTINEL not in safe_text("Açıklama " + SENTINEL, secrets=(SENTINEL,))
    assert safe_text("50 milyon TL.\n25,5 yüzde.\x00") == "50 milyon TL.\n25,5 yüzde."


def test_projection_output_budget_no_silent_truncation(verified):
    answered, _ = verified
    unsafe = replace(answered, answer=replace(answered.answer, text="x" * 8193))
    with pytest.raises(OutputRefused, match="output_limit"):
        project_answer(unsafe, turn_id=uuid4().hex, published=None)


@pytest.mark.parametrize("bad", ["", " \n", "x" * 4097, "😀" * 3000, "x\x00", 123, True])
def test_question_is_bounded_utf8_and_strict(bad):
    with pytest.raises(ValidationError):
        question(bad)


@pytest.mark.parametrize("field", ["model", "api_key", "gate", "sql", "path", "tools"])
def test_request_cannot_override_runtime_capabilities(field):
    with pytest.raises(ValidationError):
        Question.model_validate({**question().model_dump(), field: SENTINEL})


def test_one_worker_duplicate_request_and_cross_session_ownership():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def run(session_id, turn_id, text, *, is_continuation):
        assert is_continuation is None
        calls.append((session_id, turn_id, text, threading.current_thread().name))
        entered.set()
        assert release.wait(5)
        return quiet_answer()

    service = AnalysisService(run, mode="scripted")
    try:
        first, second = service.create_session(), service.create_session()
        q = question()
        turn = service.submit(first.session_id, first.token, q)
        assert entered.wait(2)
        assert service.submit(first.session_id, first.token, q).turn_id == turn.turn_id
        for session in (first, second):
            with pytest.raises(ServiceError, match="busy"):
                service.submit(session.session_id, session.token, question())
        with pytest.raises(ServiceError, match="request_conflict"):
            service.submit(first.session_id, first.token, question("Different", q.request_id))
        for session_id, token in [
            (first.session_id, second.token),
            (second.session_id, first.token),
            (uuid4().hex, first.token),
            (second.session_id, second.token),
        ]:
            with pytest.raises(ServiceError, match="not_found"):
                service.get_turn(session_id, token, turn.turn_id)
        release.set()
        done = finished(service, first, turn)
        assert done.state == "completed" and done.answer.status is AnswerStatus.ABSTAINED
        assert [e.state for e in done.events] == ["queued", "running", "completed"]
        assert [e.sequence for e in done.events] == [1, 2, 3]
        assert len(calls) == 1 and calls[0][3].startswith("kkb-analysis")
        done.answer.text = SENTINEL
        assert (
            SENTINEL
            not in service.get_turn(first.session_id, first.token, turn.turn_id).model_dump_json()
        )
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize(
    "exception,code",
    [
        (PlanningFailed(SENTINEL), "planning_failed"),
        (TransportError(SENTINEL), "provider_failed"),
        (ValueError(SENTINEL), "internal_error"),
        (OutputRefused(SENTINEL), "output_limit"),
    ],
)
def test_failures_are_safe_terminal_states_and_release_admission(exception, code):
    def run(session_id, turn_id, text, *, is_continuation):
        raise exception

    service = AnalysisService(run, mode="scripted")
    try:
        session = service.create_session()
        for _ in range(2):
            done = finished(
                service, session, service.submit(session.session_id, session.token, question())
            )
            assert done.state == "failed" and done.error == code and done.answer is None
            assert SENTINEL not in done.model_dump_json()
    finally:
        service.close()


def test_session_turn_capacity_and_shutdown_without_silent_eviction():
    service = AnalysisService(
        lambda sid, tid, text, *, is_continuation: quiet_answer(), mode="scripted"
    )
    sessions = [service.create_session() for _ in range(MAX_SESSIONS)]
    try:
        with pytest.raises(ServiceError, match="capacity"):
            service.create_session()
        session = sessions[0]
        for _ in range(MAX_TURNS):
            finished(
                service, session, service.submit(session.session_id, session.token, question())
            )
        with pytest.raises(ServiceError, match="capacity"):
            service.submit(session.session_id, session.token, question())
    finally:
        service.close()
    with pytest.raises(ServiceError, match="unavailable"):
        service.create_session()
    assert len(service._sessions) == MAX_SESSIONS


def test_persisted_idle_sessions_evict_but_active_one_does_not(tmp_path):
    store = ConversationStore(tmp_path / "history.sqlite")
    _, owner_token = store.create_owner()
    entered, release = threading.Event(), threading.Event()

    def run(session_id, turn_id, text, *, is_continuation):
        entered.set()
        assert release.wait(5)
        return quiet_answer()

    service = AnalysisService(run, mode="scripted", store=store)
    try:
        sessions = [service.create_session(owner_token) for _ in range(MAX_SESSIONS)]
        active = service.submit(sessions[0].session_id, sessions[0].token, question())
        assert entered.wait(2)
        ninth = service.create_session(owner_token)
        assert ninth.session_id in service._sessions
        assert sessions[0].session_id in service._sessions
        assert sessions[1].session_id not in service._sessions
        assert store.conversation(sessions[1].session_id) is not None
        service.conversation(sessions[1].session_id, sessions[1].token)
        assert sessions[1].session_id in service._sessions
        release.set()
        assert finished(service, sessions[0], active).state == "completed"
    finally:
        release.set()
        service.close()
        store.close()


def test_failed_and_cancelled_user_prompts_are_persisted_at_admission(tmp_path):
    store = ConversationStore(tmp_path / "history.sqlite")
    _, owner_token = store.create_owner()
    entered, release = threading.Event(), threading.Event()

    def run(session_id, turn_id, text, *, is_continuation):
        if text == "failed prompt":
            raise TransportError("synthetic timeout")
        entered.set()
        assert release.wait(5)
        checkpoint("after wait")
        return quiet_answer()

    service = AnalysisService(run, mode="scripted", store=store)
    try:
        session = service.create_session(owner_token)
        failed = finished(
            service,
            session,
            service.submit(session.session_id, session.token, question("failed prompt")),
        )
        assert failed.error == "provider_failed"
        saved = store.messages(session.session_id)
        assert [(item.role, item.text, item.status) for item in saved] == [
            ("user", "failed prompt", "failed")
        ]
        turn = service.submit(session.session_id, session.token, question("cancelled prompt"))
        assert entered.wait(2)
        assert store.messages(session.session_id)[-1].status == "running"
        service.cancel(session.session_id, session.token, turn.turn_id)
        release.set()
        cancelled = finished(service, session, turn)
        assert cancelled.error == "cancelled"
        assert [(item.text, item.status) for item in store.messages(session.session_id)] == [
            ("failed prompt", "failed"),
            ("cancelled prompt", "failed"),
        ]
    finally:
        release.set()
        service.close()
        store.close()


@pytest.fixture
def http_api():
    calls = []

    def run(session_id, turn_id, text, *, is_continuation):
        calls.append((session_id, turn_id, text, is_continuation))
        return quiet_answer()

    service = AnalysisService(run, mode="scripted")
    with TestClient(create_app(service), base_url=BASE, raise_server_exceptions=False) as client:
        yield client, service, calls


def new_http_session(client):
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 201, response.text
    return response.json()


def test_health_openapi_and_session_creation_are_offline(http_api):
    client, service, calls = http_api
    health = client.get("/v1/health")
    assert health.status_code == 200 and health.json()["model_checked"] is False
    assert health.json()["execution_mode"] == "scripted"
    assert health.headers["cache-control"] == "no-store"
    schema = client.get("/openapi.json").json()
    assert "Question" in schema["components"]["schemas"]
    assert schema["components"]["schemas"]["Question"]["additionalProperties"] is False
    session = new_http_session(client)
    assert len(session["token"]) == 43 and session["survives_restart"] is False
    assert not calls and client.get("/docs").status_code == 404


def test_http_turn_retrieval_and_bounded_real_event_replay(http_api):
    client, service, calls = http_api
    owned = new_http_session(client)
    headers = {"X-KKB-Session-Token": owned["token"]}
    path = f"/v1/sessions/{owned['session_id']}/turns"
    q = question().model_dump()
    response = client.post(path, json=q, headers=headers)
    assert response.status_code == 202, response.text
    tid = response.json()["turn_id"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        item = client.get(path + "/" + tid, headers=headers).json()
        if item["state"] == "completed":
            break
        time.sleep(0.002)
    assert item["state"] == "completed" and len(calls) == 1
    assert client.post(path, json=q, headers=headers).json()["turn_id"] == tid
    stream = client.get(path + "/" + tid + "/events", headers=headers)
    assert stream.status_code == 200 and "id: 1\n" in stream.text and "id: 3\n" in stream.text
    assert q["question"] not in stream.text and "token" not in stream.text
    replay = client.get(path + "/" + tid + "/events", headers={**headers, "Last-Event-ID": "2"})
    assert "id: 1\n" not in replay.text and "id: 3\n" in replay.text
    assert len(calls) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.invalid"},
        {"Host": "127.0.0.1:9999"},
        {"Origin": "https://evil.invalid"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        [("Host", "127.0.0.1:8000"), ("Host", "evil.invalid")],
    ],
)
def test_dns_rebinding_and_cross_origin_are_refused_before_work(http_api, headers):
    client, _, calls = http_api
    response = client.post("/v1/sessions", json={}, headers=headers)
    assert response.status_code in (400, 403) and response.json()["error"] in (
        "forbidden",
        "invalid_request",
    )
    assert not calls


@pytest.mark.parametrize(
    "payload,content_type,status",
    [
        ("{}", "text/plain", 415),
        ("{}", "application/x-www-form-urlencoded", 415),
        ('{"secret": "' + SENTINEL + '"}', "application/json", 422),
        ('{"secret": "' + SENTINEL + '"', "application/json", 422),
        ("x" * (MAX_BODY_BYTES + 1), "application/json", 413),
    ],
)
def test_request_errors_do_not_echo_inputs(http_api, payload, content_type, status):
    client, _, calls = http_api
    response = client.post("/v1/sessions", content=payload, headers={"Content-Type": content_type})
    assert response.status_code == status, response.text
    assert SENTINEL not in response.text and not calls


def test_missing_wrong_and_unowned_http_tokens(http_api):
    client, _, calls = http_api
    a, b = new_http_session(client), new_http_session(client)
    path = f"/v1/sessions/{a['session_id']}/turns"
    assert client.post(path, json=question().model_dump()).status_code == 422
    response = client.post(
        path, json=question().model_dump(), headers={"X-KKB-Session-Token": b["token"]}
    )
    assert response.status_code == 404 and not calls
    assert client.get("/v1/health?token=" + a["token"]).status_code == 400


def test_chunked_body_cannot_bypass_declared_length():
    service = AnalysisService(
        lambda sid, tid, text, *, is_continuation: pytest.fail("must not run"),
        mode="scripted",
    )

    async def scenario():
        async def chunks():
            yield b"a" * 8192
            yield b"b" * (MAX_BODY_BYTES + 1)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(service)), base_url=BASE
        ) as client:
            response = await client.post(
                "/v1/sessions",
                content=chunks(),
                headers={"Content-Type": "application/json", "Content-Length": "0"},
            )
            assert response.status_code == 413

    try:
        asyncio.run(scenario())
    finally:
        service.close()


def test_real_verified_result_passes_http_json_without_model_reshaping(verified):
    answered, published = verified
    service = AnalysisService(
        lambda sid, tid, q, *, is_continuation: project_answer(
            answered, turn_id=tid, published=published
        ),
        mode="scripted",
    )
    with TestClient(create_app(service), base_url=BASE) as client:
        owned = new_http_session(client)
        header = {"X-KKB-Session-Token": owned["token"]}
        path = f"/v1/sessions/{owned['session_id']}/turns"
        turn = client.post(path, json=question().model_dump(), headers=header).json()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = client.get(path + "/" + turn["turn_id"], headers=header).json()
            if result["state"] == "completed":
                break
            time.sleep(0.002)
        assert result["answer"]["result"]["version"] == published.digest()
        assert [c["value"] for c in result["answer"]["result"]["cells"]] == [
            v.value for v in published.values
        ]
        assert "source_id" not in json.dumps(result)


def test_unexpected_route_exception_is_redacted_without_bubbling_to_server(caplog):
    service = AnalysisService(
        lambda sid, tid, text, *, is_continuation: quiet_answer(), mode="scripted"
    )
    app = create_app(service)

    @app.get("/test-fault")
    def explode():
        raise RuntimeError(SENTINEL)

    # raise_server_exceptions=True ensures the ASGI boundary actually contains it.
    with TestClient(app, base_url=BASE, raise_server_exceptions=True) as client:
        response = client.get("/test-fault")
        assert response.status_code == 500
        assert response.json() == {"api_version": 1, "error": "internal_error"}
        assert SENTINEL not in response.text and SENTINEL not in caplog.text


def test_shutdown_waits_for_existing_work_and_does_not_retry_it():
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def run(session_id, turn_id, text, *, is_continuation):
        calls.append((session_id, turn_id, text, is_continuation))
        entered.set()
        assert release.wait(5)
        return quiet_answer()

    service = AnalysisService(run, mode="scripted")
    session = service.create_session()
    service.submit(session.session_id, session.token, question())
    assert entered.wait(2)

    def close():
        service.close()
        closed.set()

    thread = threading.Thread(target=close)
    thread.start()
    try:
        assert not closed.wait(0.02)
        with pytest.raises(ServiceError, match="unavailable"):
            service.submit(session.session_id, session.token, question())
    finally:
        release.set()
        thread.join(timeout=3)
    assert closed.is_set() and len(calls) == 1


def test_changed_result_makes_new_version_and_cell_reference(verified):
    answered, result = verified
    original = project_answer(answered, turn_id="a" * 32, published=result)
    changed = result.model_copy(deep=True)
    changed.values[0].value += 1
    # A separately published changed result; this test checks identity, not gate quality.
    updated = project_answer(
        replace(answered, results=(changed,), presented=(changed,)),
        turn_id="a" * 32,
        published=changed,
    )
    assert original.result.version != updated.result.version
    assert original.result.cells[0].cell_id != updated.result.cells[0].cell_id


def test_serialization_rejects_extra_and_overlong_output():
    with pytest.raises(ValidationError):
        Answer.model_validate({**quiet_answer().model_dump(), "debug": SENTINEL})
    with pytest.raises(ValidationError):
        Answer(status="accepted", text="x" * 8193, omitted_claims=0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_cannot_cross_public_cell_contract(verified, bad):
    answered, result = verified
    projected = project_answer(answered, turn_id=uuid4().hex, published=result)
    cell = projected.result.cells[0]
    with pytest.raises(ValidationError):
        type(cell).model_validate({**cell.model_dump(), "value": bad})


def test_duplicate_sensitive_headers_are_rejected(http_api):
    client, _, calls = http_api
    response = client.post(
        "/v1/sessions",
        content="{}",
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Type", "text/plain"),
        ],
    )
    assert response.status_code == 400 and not calls


def test_addresses_a_web_search_returned_are_shown_and_any_other_is_not():
    # Live 2026-09-21: "webde ara" listed four pages and every address was replaced by the
    # placeholder, under a sentence telling the reader to write the address in a question.
    from kkb_agent.api.projection import safe_text

    found = "https://www.bddk.org.tr/BultenHaftalik"
    text = f"- Haftalık Bülten — www.bddk.org.tr: {found}\n- başka: https://other.example/x"
    shown = safe_text(text, shown_urls=frozenset({found}))
    assert found in shown and "other.example" not in shown
    assert found not in safe_text(text)
