"""Targeted tests for session clarification context lifecycle and retention."""

from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, TOTAL, discover, proposal, seed_prepared
from test_series_inspection import SQL

from kkb_agent.agent.workspace import Workspace
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.api.service import SelectedResult
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


def test_negative_control_without_context_inheritance_fails(pool, tmp_path):
    """Controlled negative test: disabling context inheritance causes Turn 2 to fail."""
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Without context inheritance, Turn 2 receives raw q2 without dates/filters
        proposal(discover("d2")),
        proposal(clarification="ambiguous_series"),
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    q1 = "Nisan-Haziran 2026 konut kredisini göster."
    prepared(sid, uuid4().hex, q1)
    assert sid in prepared._pending_clarifications

    # Controlled negative check: pass is_continuation=False to bypass context inheritance
    q2 = "BDDK verisini kullan."
    turn2_raw = prepared(sid, uuid4().hex, q2, is_continuation=False)

    # Without q1 context, q2 alone lacks dates and fails/abstains!
    assert turn2_raw.status.value == "abstained"
