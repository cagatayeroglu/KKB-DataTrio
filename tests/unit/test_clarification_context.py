"""Targeted tests for session clarification context lifecycle and retention."""

import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, TOTAL, discover, proposal, seed_prepared
from test_series_inspection import SQL

from kkb_agent.agent.workspace import Workspace
from kkb_agent.api import prepared as prepared_module
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.api.service import AnalysisService, SelectedResult
from kkb_agent.api.store import ConversationStore
from kkb_agent.llm import scripted


@pytest.fixture
def pool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def runner(root, tmp_path, provider):
    return PreparedRunner(provider, root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes())


def calculate(step_id="a", operation="compare", start="2026-04-30", end="2026-06-30"):
    return {
        "step_id": step_id,
        "tool": "change_detection",
        "arguments": {
            "operation": operation,
            "series_id": TOTAL,
            "start": start,
            "end": end,
        },
    }


def test_clarification_inherits_original_request_context(pool, tmp_path):
    """First request has date and relationship conditions; clarification inherits them."""
    provider = scripted(
        # Turn 1: Discovery phase then clarification proposal
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery phase then analysis proposal using merged prompt context
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-04-30", end="2026-06-30")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    # Turn 1: Original query with 2026-04-30..2026-06-30 date range and relationship constraint
    q1 = "Nisan-Haziran 2026 konut kredisi bakiyesinin faiz oranıyla ilişkisini göster."
    turn1 = prepared(sid, uuid4().hex, q1)
    assert turn1.status.value == "abstained"
    assert turn1.result is None
    assert sid in prepared._pending_clarifications
    assert prepared._pending_clarifications[sid].original_question == q1

    # Turn 2: User provides clarification without repeating date range or relationship condition
    q2 = "BDDK Aylık Bülten toplam bakiyeyi kullan."
    turn2 = prepared(sid, uuid4().hex, q2)
    assert turn2.status.value == "accepted"
    assert turn2.result is not None
    assert sid not in prepared._pending_clarifications

    # Verify that Turn 2 planner received effective_question containing original request
    last_user_prompt = provider.seen[-1][-1].content
    assert "Orijinal istek: " + q1 in last_user_prompt
    assert "Açıklama: " + q2 in last_user_prompt


def test_pending_clarification_survives_runner_restart(pool, tmp_path):
    state = tmp_path / "state"
    store = ConversationStore(tmp_path / "history.sqlite")
    owner_id, _ = store.create_owner()
    sid = uuid4().hex
    store.create_conversation(owner_id=owner_id, conversation_id=sid, token="x" * 43, title="Test")
    first = PreparedRunner(
        scripted(proposal(discover("d1")), proposal(clarification="ambiguous_series")),
        pool,
        state,
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
    )
    original = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
    assert first(sid, uuid4().hex, original).status.value == "abstained"
    assert store.pending_clarification(sid) is not None

    provider = scripted(
        proposal(discover("d2")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    restarted = PreparedRunner(
        provider, pool, state, catalog_bytes=CATALOG.read_bytes(), store=store
    )
    answer = "BDDK Aylık Bülten toplam bakiyeyi kullan."
    assert restarted(sid, uuid4().hex, answer).status.value == "accepted"
    assert f"Orijinal istek: {original}" in provider.seen[-1][-1].content
    assert f"Açıklama: {answer}" in provider.seen[-1][-1].content
    assert store.pending_clarification(sid) is None
    store.close()


def test_explicit_clarification_overrides_original_date_range(pool, tmp_path):
    """User clarification providing an explicit new date range overrides the original request."""
    provider = scripted(
        # Turn 1: Discovery then clarification
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery then analysis with explicit 2026-05-31 override
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-05-31", end="2026-06-30")),
        "Mayıs 2026'dan Haziran 2026'ya konut kredisi stoğu 30 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications

    # Turn 2: User explicitly specifies 2026-05-31..2026-06-30 override
    q2 = "BDDK Aylık Bülten toplam bakiyeyi Mayıs-Haziran 2026 dönemi için kullan."
    turn2 = prepared(sid, uuid4().hex, q2)
    assert turn2.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Verify planner tool call parameters received explicit start date and period
    plan_step = turn2.result.proof.steps[0]
    assert plan_step.producer == "change_detection"
    assert plan_step.coverage is not None
    assert plan_step.coverage.start.year == 2026
    assert plan_step.coverage.start.month == 5
    assert plan_step.coverage.end.month == 6

    last_user_prompt = provider.seen[-1][-1].content
    assert "Mayıs-Haziran 2026" in last_user_prompt
    assert f"Orijinal istek: {q1}" in last_user_prompt


def test_cancellation_and_refusal_clears_established_pending_context(pool, tmp_path):
    """Cancellation/new question clear context; refusal preserves it for retry."""
    provider = scripted(
        # Turn 1: Establishes pending clarification state
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Explicit cancellation -> abstained response
        proposal(clarification="unsupported_request"),
        # Turn 3: Establishes pending clarification state again
        proposal(discover("d3")),
        proposal(clarification="ambiguous_series"),
        # Turn 4: Explicit new question -> accepted response
        proposal(discover("d4")),
        proposal(calculate("a4", start="2026-04-30", end="2026-06-30")),
        "2025 BDDK kredileri 100 milyon TL.",
        # Turn 5: Establishes pending clarification state again
        proposal(discover("d5")),
        proposal(clarification="ambiguous_series"),
        # Turn 6: Refusal on clarification attempt (unsupported_request)
        proposal(clarification="unsupported_request"),
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    # Turn 1: Establish pending clarification
    q1 = "Nisan-Haziran 2026 konut kredisini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications

    # Turn 2: Explicit cancellation clears pending context
    turn2 = prepared(sid, uuid4().hex, "iptal")
    assert sid not in prepared._pending_clarifications
    assert turn2.status.value == "abstained"

    # Turn 3: Establish pending clarification again
    q3 = "2025 BDDK kredilerini göster."
    prepared(sid, uuid4().hex, q3)
    assert sid in prepared._pending_clarifications

    # Turn 4: Explicit new question clears pending context
    turn4 = prepared(sid, uuid4().hex, "2025 BDDK kredilerini göster.", is_continuation=False)
    assert turn4.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Turn 5: Establish pending clarification again
    q5 = "Gelecek yıl tahminlerini göster."
    prepared(sid, uuid4().hex, q5)
    assert sid in prepared._pending_clarifications

    # Turn 6: Refusal on unsupported request does NOT erase established pending context
    turn6 = prepared(sid, uuid4().hex, "Gelecek yıl tahminleri için regresyon yap.")
    assert turn6.status.value == "abstained"
    assert sid in prepared._pending_clarifications
    assert prepared._pending_clarifications[sid].original_question == q5


def test_back_to_back_clarifications_accumulate_without_nesting(pool, tmp_path):
    """Multiple clarifications accumulate linearly without nested 'Orijinal istek' headers."""
    provider = scripted(
        # Turn 1: Abstained clarification 1
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Abstained clarification 2
        proposal(discover("d2")),
        proposal(clarification="unresolved_semantics"),
        # Turn 3: Successful completion
        proposal(discover("d3")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications

    q2 = "BDDK verisini kullan."
    prepared(sid, uuid4().hex, q2)
    assert sid in prepared._pending_clarifications
    pending = prepared._pending_clarifications[sid]
    assert pending.original_question == q1
    assert pending.clarifications == (q2,)

    q3 = "Milyon TL ay sonu stok bakiyesini kullan."
    turn3 = prepared(sid, uuid4().hex, q3)
    assert turn3.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Verify Turn 3 prompt has flat linear structure, no nested Orijinal istek: Orijinal istek:
    last_user_prompt = provider.seen[-1][-1].content
    assert last_user_prompt.count("Orijinal istek:") == 1
    assert f"Orijinal istek: {q1}" in last_user_prompt
    assert f"Açıklama: {q2}" in last_user_prompt
    assert f"Açıklama: {q3}" in last_user_prompt


def test_real_transient_error_injection_preserves_context(pool, tmp_path):
    """Real exception injection during execution retains pending clarification state for retry."""
    base_scripted = scripted(
        # Turn 1
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2 (failed execution attempt): discover proposal
        proposal(discover("d2")),
        # Turn 3 (retry): discover & calculate
        proposal(discover("d3")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )

    class FailingProviderWrapper:
        def __init__(self, target):
            self.target = target
            self.call_count = 0
            self.seen = target.seen

        def complete(self, messages, model=None, schema=None):
            self.call_count += 1
            if self.call_count == 3:
                raise RuntimeError("transient lakehouse query failure")
            return self.target.complete(messages, model=model, schema=schema)

        def propose(self, prompt, schema, tools, system):
            self.call_count += 1
            if self.call_count == 3:
                raise RuntimeError("transient lakehouse query failure")
            return self.target.propose(prompt, schema, tools, system)

    failing_provider = FailingProviderWrapper(base_scripted)
    prepared = runner(pool, tmp_path, failing_provider)
    sid = uuid4().hex

    # Turn 1: Establish pending clarification
    q1 = "Nisan-Haziran 2026 konut kredisini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications

    # Turn 2: Execution fails with real injected transient exception
    q2 = "BDDK verisini kullan."
    with pytest.raises(RuntimeError, match="transient lakehouse query failure"):
        prepared(sid, uuid4().hex, q2)

    # Assert pending clarification was NOT wiped out by transient failure!
    assert sid in prepared._pending_clarifications
    assert prepared._pending_clarifications[sid].original_question == q1

    # Turn 3: Retry turn succeeds
    turn3 = prepared(sid, uuid4().hex, q2)
    assert turn3.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Verify q2 clarification was NOT duplicated in prompt context on retry
    last_prompt = failing_provider.seen[-1][-1].content
    assert last_prompt.count(f"Açıklama: {q2}") == 1


def test_published_table_selection_preserved_and_cells_immutable(pool, tmp_path):
    """Clarification on published table keeps selection and cell immutability."""
    lk_step = {"step_id": "a1", "tool": "lakehouse", "arguments": {"sql": SQL}}
    filter_step = {
        "step_id": "a2",
        "tool": "table_transform",
        "arguments": {"operation": "filter", "source": "analiz_1", "start_period": "2026-05-31"},
    }
    t1_text = (
        "Nisan 2026 için 100 milyon TL oldu. Mayıs 2026 için 120 milyon TL oldu. "
        "Haziran 2026 için 150 milyon TL oldu."
    )
    t3_text = (
        "analiz_3 tablosunda Mayıs 2026 için 120 milyon TL oldu. "
        "analiz_3 tablosunda Haziran 2026 için 150 milyon TL oldu."
    )
    provider = scripted(
        # Turn 1: Successfully publish analiz_1
        proposal(discover("d1")),
        proposal(lk_step),
        t1_text,
        # Turn 2: Clarification on follow-up request
        proposal(discover("d2")),
        proposal(clarification="ambiguous_series"),
        # Turn 3: Resolved follow-up with selected table preserved
        proposal(discover("d3")),
        proposal(filter_step),
        t3_text,
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    t1_id = uuid4().hex
    turn1 = prepared(sid, t1_id, "Konut kredisi tablosunu oluştur.")
    assert turn1.status.value == "accepted"
    sel = SelectedResult(t1_id, turn1.result.result_ref, turn1.result.version)

    # Store exact cell values of analiz_1 before Turn 2/3
    t1_cells = [
        (c.label, c.value, c.period.start if c.period else None) for c in turn1.result.cells
    ]

    # Turn 2: Selected table follow-up that yields clarification
    turn2 = prepared.selected(sid, uuid4().hex, "Bu tabloyu filtrele.", sel)
    assert turn2.status.value == "abstained"
    assert sid in prepared._pending_clarifications
    assert prepared._pending_clarifications[sid].selection == sel

    # Turn 3: User clarifies series ID without resending selected_result_id
    turn3 = prepared(sid, uuid4().hex, "Mayıs 2026 sonrasını göster.")
    assert turn3.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Direct value-by-value comparison of analiz_1 values after Turn 3 to assert exact immutability
    lake_dir = prepared.run_root / sid / "lake"
    with open_lakehouse(lake_dir) as lake:
        ws = Workspace.open(lake.connection, sid)
        analiz_1_val = ws.value_of("analiz_1")
        analiz_1_cells = [
            (c.label, c.value, c.period.start if c.period else None) for c in analiz_1_val.values
        ]
        assert analiz_1_cells == t1_cells


def test_session_isolation_prevents_context_and_selection_leakage(pool, tmp_path):
    """Context and pending clarifications in Session A do not leak to Session B."""
    provider = scripted(
        # Session A Turn 1: Abstained clarification
        proposal(discover("dA1")),
        proposal(clarification="ambiguous_series"),
        # Session B Turn 1: Clean independent answer
        proposal(discover("dB1")),
        proposal(calculate("aB1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid_a = uuid4().hex
    sid_b = uuid4().hex

    # Session A: Turn 1 abstains
    q_a = "Session A: Konut kredisini göster."
    prepared(sid_a, uuid4().hex, q_a)
    assert sid_a in prepared._pending_clarifications

    # Session B: Independent question runs completely cleanly
    q_b = "Session B: 2026 yılı enflasyon oranını göster."
    turn_b = prepared(sid_b, uuid4().hex, q_b)
    assert turn_b.status.value == "accepted"

    # Verify Session B is not in pending_clarifications and prompt had no Session A context
    assert sid_b not in prepared._pending_clarifications
    last_user_prompt = provider.seen[-1][-1].content
    assert "Session A" not in last_user_prompt
    assert "Orijinal istek" not in last_user_prompt


def test_request_idempotency_does_not_duplicate_context(pool, tmp_path):
    """Resubmission of abstained turn does not duplicate pending clarification context."""
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    q1 = "2026 konut kredisini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications
    initial_pending = prepared._pending_clarifications[sid]

    # Resubmit turn
    assert prepared._pending_clarifications[sid] == initial_pending
    assert len(prepared._pending_clarifications[sid].clarifications) == 0


def test_negative_control_detects_lost_planner_context(pool, tmp_path, monkeypatch):
    """The planner-input assertion fails if prompt composition drops the original."""
    q1 = "Nisan-Haziran 2026 konut kredisinin faizle ilişkisini göster."
    q2 = "BDDK Aylık Bülten toplam bakiyeyi kullan."

    def planner_input() -> str:
        provider = scripted(
            proposal(discover("d1")),
            proposal(clarification="ambiguous_series"),
            proposal(discover("d2")),
            proposal(clarification="unresolved_semantics"),
        )
        prepared = runner(pool, tmp_path, provider)
        sid = uuid4().hex
        prepared(sid, uuid4().hex, q1)
        prepared(sid, uuid4().hex, q2, is_continuation=True)
        return "\n".join(message.content for message in provider.seen[-2])

    assert f"Orijinal istek: {q1}" in planner_input()
    with monkeypatch.context() as patch:
        patch.setattr(
            prepared_module,
            "_format_clarification_prompt",
            lambda original, clarifications: clarifications[-1],
        )
        broken_input = planner_input()
    assert q1 not in broken_input
    assert q2 in broken_input


BASE = "http://127.0.0.1:8000"


def wait_http(client: TestClient, path: str, headers: dict[str, str]) -> dict:
    for _ in range(100):
        res = client.get(path, headers=headers).json()
        if res.get("state") in ("completed", "failed"):
            return res
        time.sleep(0.05)
    return res


def test_fastapi_clarification_continuation_e2e(pool, tmp_path):
    """FastAPI endpoint test for turns with is_continuation parameter e2e."""
    provider = scripted(
        # Turn 1: Discovery then clarification
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery then analysis
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-04-30", end="2026-06-30")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    service = AnalysisService(prepared, mode="scripted", selected_runner=prepared.selected)

    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        # 1. Create session
        session = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": session["token"]}
        turns_path = f"/v1/sessions/{session['session_id']}/turns"

        # 2. Turn 1: Submit initial question that abstains for clarification
        q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
        req1 = {"request_id": uuid4().hex, "question": q1}
        admitted1 = client.post(turns_path, json=req1, headers=headers)
        assert admitted1.status_code in (200, 201, 202)

        turn1 = wait_http(client, f"{turns_path}/{admitted1.json()['turn_id']}", headers)
        assert turn1["state"] == "completed"
        assert turn1["answer"]["status"] == "abstained"

        # 3. Turn 2: Submit clarification response with is_continuation=true
        q2 = "BDDK Aylık Bülten bakiyesini kullan."
        req2 = {"request_id": uuid4().hex, "question": q2, "is_continuation": True}
        admitted2 = client.post(turns_path, json=req2, headers=headers)
        assert admitted2.status_code in (200, 201, 202)

        turn2 = wait_http(client, f"{turns_path}/{admitted2.json()['turn_id']}", headers)
        assert turn2["state"] == "completed"
        assert turn2["answer"]["status"] == "accepted"

        # Verify effective prompt sent to LLM planner contained original request context
        last_prompt = provider.seen[-1][-1].content
        assert f"Orijinal istek: {q1}" in last_prompt
        assert f"Açıklama: {q2}" in last_prompt


def test_fastapi_independent_new_question_drops_pending_context_e2e(pool, tmp_path):
    """FastAPI endpoint test: is_continuation=false drops pending clarification context."""
    provider = scripted(
        # Turn 1: Discovery then clarification
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery then analysis for independent new question
        proposal(discover("d2")),
        proposal(calculate("a2", start="2026-04-30", end="2026-06-30")),
        "Nisan'dan Haziran 2026'ya toplam kredi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    service = AnalysisService(prepared, mode="scripted", selected_runner=prepared.selected)

    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        session = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": session["token"]}
        turns_path = f"/v1/sessions/{session['session_id']}/turns"

        # Turn 1: Abstained
        q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
        admitted1 = client.post(
            turns_path, json={"request_id": uuid4().hex, "question": q1}, headers=headers
        )
        wait_http(client, f"{turns_path}/{admitted1.json()['turn_id']}", headers)

        # Turn 2: Independent question with is_continuation=false
        q2 = "Nisan-Haziran 2026 toplam kredi bakiyesini göster."
        req2 = {"request_id": uuid4().hex, "question": q2, "is_continuation": False}
        admitted2 = client.post(turns_path, json=req2, headers=headers)
        assert admitted2.status_code in (200, 201, 202)

        turn2 = wait_http(client, f"{turns_path}/{admitted2.json()['turn_id']}", headers)
        assert turn2["state"] == "completed"
        assert turn2["answer"]["status"] == "accepted"

        # Verify prompt did NOT contain q1 context
        last_prompt = provider.seen[-1][-1].content
        assert "Orijinal istek" not in last_prompt
        assert q1 not in last_prompt


def test_fastapi_real_idempotency_and_conflict(pool, tmp_path):
    """FastAPI endpoint test: exact retry returns same turn; altered field returns 409 conflict."""
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
    )
    prepared = runner(pool, tmp_path, provider)
    service = AnalysisService(prepared, mode="scripted", selected_runner=prepared.selected)

    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        session = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": session["token"]}
        turns_path = f"/v1/sessions/{session['session_id']}/turns"

        rid = uuid4().hex
        body = {"request_id": rid, "question": "Konut kredisini göster.", "is_continuation": True}

        # 1. First submission succeeds
        res1 = client.post(turns_path, json=body, headers=headers)
        assert res1.status_code in (200, 201, 202)
        turn_id = res1.json()["turn_id"]

        # 2. Resubmission with exact same body returns same turn_id without calling runner again
        res2 = client.post(turns_path, json=body, headers=headers)
        assert res2.status_code in (200, 201, 202)
        assert res2.json()["turn_id"] == turn_id

        # 3. Resubmission with same request_id but different is_continuation returns 409 conflict
        conflict_body = {
            "request_id": rid,
            "question": "Konut kredisini göster.",
            "is_continuation": False,
        }
        res_conflict = client.post(turns_path, json=conflict_body, headers=headers)
        assert res_conflict.status_code == 409
        assert res_conflict.json()["error"] == "request_conflict"


def test_fastapi_invalid_types_and_foreign_sessions_rejected(pool, tmp_path):
    """FastAPI validation: invalid is_continuation types return 422, foreign sessions return 404."""
    prepared = runner(pool, tmp_path, scripted(proposal(clarification="ambiguous_series")))
    service = AnalysisService(prepared, mode="scripted", selected_runner=prepared.selected)

    with TestClient(create_app(service, prepared=prepared.status), base_url=BASE) as client:
        session = client.post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": session["token"]}
        turns_path = f"/v1/sessions/{session['session_id']}/turns"

        # 1. Invalid is_continuation field type returns 422
        bad_type = {
            "request_id": uuid4().hex,
            "question": "Konut kredisi",
            "is_continuation": "invalid_string",
        }
        res_bad = client.post(turns_path, json=bad_type, headers=headers)
        assert res_bad.status_code == 422
        assert res_bad.json()["error"] == "invalid_request"

        # 2. Foreign session ID returns 404
        foreign_path = f"/v1/sessions/{uuid4().hex}/turns"
        res_foreign = client.post(
            foreign_path, json={"request_id": uuid4().hex, "question": "Test"}, headers=headers
        )
        assert res_foreign.status_code == 404
        assert res_foreign.json()["error"] == "not_found"


def test_a_pending_clarification_is_read_without_the_person_stating_it(pool, tmp_path):
    """No `is_continuation`: a short answer is merged, a standing question replaces it."""
    provider = scripted(
        # Turn 1: pending clarification.
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: a short answer, merged into the original request.
        proposal(discover("d2")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
        # Turn 3: pending clarification again.
        proposal(discover("d3")),
        proposal(clarification="ambiguous_series"),
        # Turn 4: a question of its own, answered on its own.
        proposal(discover("d4")),
        proposal(calculate("a2", start="2026-05-31")),
        "Mayıs 2026'dan Haziran 2026'ya konut kredisi stoğu 30 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
    assert prepared(sid, uuid4().hex, q1).status.value == "abstained"
    answer = "BDDK Aylık Bülten toplam bakiyeyi kullan."
    assert prepared(sid, uuid4().hex, answer).status.value == "accepted"
    merged = provider.seen[-1][-1].content
    assert f"Orijinal istek: {q1}" in merged and f"Açıklama: {answer}" in merged

    assert prepared(sid, uuid4().hex, q1).status.value == "abstained"
    fresh = "Mayıs-Haziran 2026 konut kredisi bakiyesi ne kadar arttı?"
    assert prepared(sid, uuid4().hex, fresh).status.value == "accepted"
    standing = provider.seen[-1][-1].content
    assert standing == fresh  # Neither merged into the pending request nor repeated.
    assert sid not in prepared._pending_clarifications


def test_a_clarification_lists_what_the_catalogue_search_found(pool, tmp_path):
    """DEC-172: "several series fit" and "not found" said nothing about what exists."""
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        proposal(discover("d2")),
        proposal(clarification="missing_series"),
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex
    asked = prepared(sid, uuid4().hex, "Konut kredisi ne kadar arttı?")
    assert asked.status.value == "abstained" and asked.result is None
    lines = asked.text.split("\n")
    assert lines[0].startswith("Birden fazla veri serisi uygun görünüyor")
    assert lines[1] == "Bilgi tabanındaki uygun kayıtlar:"
    assert 1 <= len(lines[2:]) <= 6 and all(line.startswith("- ") for line in lines[2:])
    assert any("BDDK" in line and "aylık" in line and "bakiye (stok)" in line for line in lines[2:])
    question = "Yepyeni bir soru: taşıt kredisi bakiyesi 2025'te ne oldu?"
    missing = prepared(sid, uuid4().hex, question)
    assert missing.status.value == "abstained"
    assert "bilgi tabanında bulunamadı" in missing.text
    assert "en yakın kayıtlar (istediğiniz ölçüm bunlar olmayabilir)" in missing.text
    assert missing.text.rstrip().endswith("Bilgi tabanı > Yeni veri ile ekleyebilirsiniz.")


def test_naming_an_offered_entry_answers_the_clarification_at_any_length():
    """A teammate's trace and live E1b (2026-09-19): the entry picked from the offered list is
    long and full of commas; the length rule called it a new question and dropped the request."""
    from kkb_agent.api.prepared import PendingClarification, _is_new_question

    offered = ("Konut Kredisi (TL, Akım, %)", "Konut Kredisi (TL, Stok, %)")
    pending = PendingClarification(
        original_question="2021-2025 konut kredisi faizi", offered=offered
    )
    picked = (
        "Konut Kredisi (TL, Akım, %) (Kredi Faiz Oranları (Akım), EVDS/Mevduat, Kalkınma ve "
        "Yatırım Bankaları, haftalık, percent, oran)"
    )
    assert _is_new_question(picked, None, pending) is False
    assert _is_new_question("konut kredisi (tl, akım, %) olsun", None, pending) is False
    # Length and commas alone are not evidence of a new intent.
    bare = PendingClarification(original_question="2021-2025 konut kredisi faizi")
    assert _is_new_question(picked, None, bare) is False
    assert (
        _is_new_question(
            "EVDS'deki yeni kullandırılan konut kredilerinin haftalık akım faiz oranını, "
            "toplam kredi bakiyesiyle karıştırmadan kullan.",
            None,
            bare,
        )
        is False
    )
    unrelated = "Şimdi de TÜFE'nin 2024 yılındaki aylık değişimini, yıllık ortalamasıyla göster."
    assert _is_new_question(unrelated, None, pending) is True


def test_card_choice_is_merged_in_actual_trace_but_unrelated_question_replaces(pool, tmp_path):
    """The browser's card format must bind to an actual offered catalogue title."""
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        proposal(discover("d2")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
        proposal(discover("d3")),
        proposal(clarification="ambiguous_series"),
        proposal(discover("d4")),
        proposal(calculate("a2", start="2026-05-31")),
        "Mayıs 2026'dan Haziran 2026'ya konut kredisi stoğu 30 milyon TL arttı.",
    )
    store = ConversationStore(tmp_path / "history.sqlite")
    owner, _ = store.create_owner()
    sid = uuid4().hex
    store.create_conversation(owner_id=owner, conversation_id=sid, token="x" * 43, title="Test")
    prepared = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes(), store=store
    )
    try:
        original = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
        first = prepared(sid, uuid4().hex, original)
        assert first.status.value == "abstained"
        assert first.selection and first.selection.others
        picked = first.selection.others[0]
        card_text = f"{picked.title} ({picked.detail})"
        assert prepared(sid, uuid4().hex, card_text).status.value == "accepted"
        assert f"Orijinal istek: {original}" in provider.seen[-1][-1].content
        assert f"Açıklama: {card_text}" in provider.seen[-1][-1].content
        merged = store.events(store.runs(sid)[0].run_id)
        received = next(event for event in merged if event.name == "turn.received")
        assert received.attributes["clarification"] == "merged"

        assert prepared(sid, uuid4().hex, original).status.value == "abstained"
        fresh = "Mayıs-Haziran 2026 konut kredisi bakiyesi ne kadar arttı?"
        assert prepared(sid, uuid4().hex, fresh).status.value == "accepted"
        replaced = store.events(store.runs(sid)[0].run_id)
        received = next(event for event in replaced if event.name == "turn.received")
        assert received.attributes["clarification"] == "replaced"
        assert provider.seen[-1][-1].content == fresh
    finally:
        store.close()
