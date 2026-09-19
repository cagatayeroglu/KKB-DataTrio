"""E1 (2026-09-19): a full request stated as an instruction is a new question, not a reply.

The trace showed "2021-2025 konut kredisi bakiyesini aylık getir, TÜFE ile ... arındır."
merged into a stale pending clarification about İstanbul, so the planner searched
İstanbul and clarified again. A reply to a clarification is short; a long message is
a request of its own whether or not it ends in a question mark.
"""

from uuid import uuid4

import pytest
from test_catalog_continuation import discover, proposal
from test_clarification_context import calculate, runner
from test_clarification_context import pool as pool  # noqa: F401

from kkb_agent.api import prepared as prepared_module
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role

E1_REQUEST = (
    "2021–2025 konut kredisi bakiyesini aylık getir, TÜFE ile Aralık 2025 fiyatlarına "
    "göre enflasyondan arındır."
)


@pytest.mark.parametrize(
    ("message", "new_question"),
    [
        ("BDDK Aylık Bülten toplam bakiyeyi kullan.", False),
        ("BDDK Aylık Bülten toplam bakiyeyi Mayıs-Haziran 2026 dönemi için kullan.", False),
        ("BDDK verisini kullan.", False),
        ("Milyon TL ay sonu stok bakiyesini kullan.", False),
        ("Mayıs 2026 sonrasını göster.", False),
        ("Gelecek yıl tahminleri için regresyon yap.", False),
        ("Mayıs-Haziran 2026 konut kredisi bakiyesi ne kadar arttı?", True),
        ("Yeni soru: konut fiyat endeksi", True),
        (E1_REQUEST, True),
    ],
)
def test_a_reply_is_short_and_a_request_of_its_own_is_a_new_question(message, new_question):
    pending = prepared_module.PendingClarification(
        original_question="konut kredilerini istanbulda göster"
    )
    assert prepared_module._is_new_question(message, None, pending) is new_question


def test_a_long_instruction_after_a_clarification_is_answered_as_its_own_request(pool, tmp_path):
    provider = scripted(
        proposal(discover("d1")),
        proposal(clarification="ambiguous_series"),
        proposal(discover("d2")),
        proposal(calculate("a1", start="2026-04-30", end="2026-06-30")),
        "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
    )
    prepared = runner(pool, tmp_path, provider)
    sid = uuid4().hex

    turn1 = prepared(sid, uuid4().hex, "konut kredilerini istanbulda göster")
    assert turn1.status.value == "abstained" and sid in prepared._pending_clarifications

    turn2 = prepared(sid, uuid4().hex, E1_REQUEST)
    assert turn2.status.value == "accepted" and sid not in prepared._pending_clarifications
    # The planner and the writer saw the request itself, not a merged clarification.
    planner_user_turns = "\n".join(m.content for m in provider.seen[2] if m.role is Role.USER)
    assert E1_REQUEST in planner_user_turns and "Orijinal istek" not in planner_user_turns
    assert provider.seen[-1][-1].content == E1_REQUEST
