"""Targeted tests for session clarification context lifecycle and retention."""

from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, TOTAL, discover, proposal, seed_prepared
from test_series_inspection import SQL

from kkb_agent.api.prepared import PreparedRunner
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
    """Abstained turn due to ambiguous_series retains original request context for clarification."""
    provider = scripted(
        # Turn 1: Discovery phase then clarification proposal in continuation
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery phase then analysis proposal using merged prompt context
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-04-30", end="2026-06-30")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    # Turn 1: Original query with 2026-04-30..2026-06-30 date range
    q1 = "Nisan-Haziran 2026 konut kredisi bakiyesini göster."
    turn1 = prepared(sid, uuid4().hex, q1)
    assert turn1.status.value == "abstained"
    assert turn1.result is None
    assert sid in prepared._pending_clarifications

    # Turn 2: User provides clarification without repeating date range
    q2 = "BDDK Aylık Bülten toplam bakiyeyi kullan."
    turn2 = prepared(sid, uuid4().hex, q2)
    assert turn2.status.value == "accepted"
    assert turn2.result is not None
    assert sid not in prepared._pending_clarifications

    # Verify that Turn 2 planner received effective_question containing original request
    last_user_prompt = provider.seen[-1][-1].content
    assert "Orijinal istek: " + q1 in last_user_prompt or "Nisan-Haziran 2026" in last_user_prompt


def test_explicit_clarification_overrides_original_date_range(pool, tmp_path):
    """User clarification providing an explicit new date range overrides the original request."""
    provider = scripted(
        # Turn 1: Discovery then clarification
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        # Turn 2: Discovery then analysis with explicit 2026-05-31 override
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-05-31", end="2026-06-30")),
        "Mayıs'tan Haziran 2026'ya konut kredisi stoğu 30 milyon TL arttı.",
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


def test_independent_new_question_does_not_inherit_cleared_context(pool, tmp_path):
    """After turn completion (ACCEPTED), a subsequent independent question gets no stale context."""
    provider = scripted(
        # Turn 1: First question & answer (discovery -> calculate -> synthesis)
        proposal(discover("d1")),
        proposal(calculate("a1")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
        # Turn 2: Independent new question
        proposal(discover("d2")),
        proposal(calculate("a2", start="2026-05-31", end="2026-06-30")),
        "Mayıs'tan Haziran 2026'ya konut kredisi stoğu 30 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    turn1 = prepared(sid, uuid4().hex, "Nisan-Haziran 2026 konut kredisini göster.")
    assert turn1.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

    # Turn 2: Independent question
    q2 = "2026 yılı enflasyon oranını göster."
    turn2 = prepared(sid, uuid4().hex, q2)
    assert turn2.status.value == "accepted"
    assert sid not in prepared._pending_clarifications


def test_unsupported_request_refusal_clears_pending_context(pool, tmp_path):
    """When a request is refused as unsupported_request, pending clarification is cleared."""
    provider = scripted(
        # Turn 1: Refused as unsupported_request (without discovery phase)
        proposal(clarification="unsupported_request"),
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    turn1 = prepared(sid, uuid4().hex, "Desteklenmeyen bir analiz yap.")
    assert turn1.status.value == "abstained"
    assert sid not in prepared._pending_clarifications


def test_repeated_clarification_retains_accumulated_context(pool, tmp_path):
    """If clarification is requested multiple times, context accumulates and is retained."""
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
    assert "Orijinal istek" in prepared._pending_clarifications[sid].question

    q3 = "Milyon TL ay sonu stok bakiyesini kullan."
    turn3 = prepared(sid, uuid4().hex, q3)
    assert turn3.status.value == "accepted"
    assert sid not in prepared._pending_clarifications


def test_published_table_selection_preserved_with_clarification(pool, tmp_path):
    """When a published table exists and clarification is requested, selection reference is kept."""
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

    # Turn 2: Selected table follow-up that yields clarification
    turn2 = prepared.selected(sid, uuid4().hex, "Bu tabloyu filtrele.", sel)
    assert turn2.status.value == "abstained"
    assert sid in prepared._pending_clarifications
    assert prepared._pending_clarifications[sid].selection == sel

    # Turn 3: User clarifies series ID without resending selected_result_id
    turn3 = prepared(sid, uuid4().hex, "Mayıs 2026 sonrasını göster.")
    assert turn3.status.value == "accepted"
    assert sid not in prepared._pending_clarifications

