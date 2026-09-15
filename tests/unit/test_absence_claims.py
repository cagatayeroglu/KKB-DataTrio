"""M11-11: a gated answer must not claim that computed values are absent.

The M11-07 live Turn 3 draft said an added column had no values although the
published table carried them; the gate accepted it because it held no number.
"""

import pytest
from test_claim_semantic_binding import connection as connection  # noqa: F401
from test_claim_semantic_binding import result
from test_claim_semantic_binding import (
    verified_execution_boundary as verified_execution_boundary,  # noqa: F401
)

from kkb_agent.agent.claim_qualifiers import absence_fault
from kkb_agent.agent.verifier import AnswerStatus, gate_answer
from kkb_agent.analytics import BASE_LIMITATIONS, GRANGER_LIMITATIONS
from kkb_agent.core import AnalyticalResult, ResultKind, ResultStatus

LIVE_TURN_THREE = (
    "Konut fiyat endeksi sütunu için sonuçlarda değer bulunmuyor. Bu durumda faiz düşüşü, "
    "konut fiyatı yükselişi ve enflasyondan arındırılmış kredi bakiyesinin artmaması birlikte "
    "hesaplanamıyor."
)

ABSENCE = [
    "Konut fiyat endeksi sütunu için sonuçlarda değer bulunmuyor",
    "Kesişim hesaplanamıyor",
    "KFE verisi yok",
    "Değerler mevcut değildir",
    "Sonuçlarda KFE değerleri yer almıyor",
    "İlgili veri bulunamadı",
    "There are no values for the index",
    "The index data is not available",
    "The intersection cannot be computed",
    # Case and the dotted capital İ.
    "SONUÇLARDA DEĞER BULUNMUYOR",
]


@pytest.mark.parametrize("sentence", ABSENCE)
def test_absence_claims_are_withheld_beside_computed_values(connection, sentence):  # noqa: F811
    gated = gate_answer(f"Ocak 2025'te 100 milyon TL. {sentence}.", result(), connection)
    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == "Ocak 2025'te 100 milyon TL."
    assert "absence" in gated.omitted[0].reasons[0]


def test_live_turn_three_draft_cannot_be_accepted(connection):  # noqa: F811
    gated = gate_answer(LIVE_TURN_THREE, result(), connection)
    assert gated.status is AnswerStatus.ABSTAINED
    assert len(gated.omitted) == 2 and not gated.text


@pytest.mark.parametrize(
    "sentence",
    [
        "Eksik gözlem içeren geçiş yok",
        "Dışlanan dönem bulunmuyor",
        "Her dönemin değerleri ayrı tabloda bulunmaktadır",
        "Bu birlikte hareket tek başına kredi artmamasını açıklamaya yetmez",
        "Sonuçlar yalnızca yönleri karşılaştırır",
    ],
)
def test_counts_and_limits_without_absence_wording_still_pass(connection, sentence):  # noqa: F811
    gated = gate_answer(f"Ocak 2025'te 100 milyon TL. {sentence}.", result(), connection)
    assert gated.status is AnswerStatus.ACCEPTED and not gated.omitted


@pytest.mark.parametrize(
    "text",
    [
        *BASE_LIMITATIONS,
        *GRANGER_LIMITATIONS,
        "A transition needs both series in a month and in the previous calendar month; "
        "gaps are not bridged",
        "The added column is aligned by exact monthly periods only; no resampling, filling, "
        "currency conversion, inflation adjustment or rebasing was applied to it",
        "Existing comparison metrics still concern their original columns; adding a column "
        "does not compute a relationship with it",
        "Values are nominal; no inflation adjustment was applied",
    ],
)
def test_the_analytics_own_limitations_are_not_absence_claims(text):
    # The writer is shown these; quoting one must not cost the sentence.
    assert absence_fault(text) is None


def test_rule_needs_a_computed_result(connection):  # noqa: F811
    refused = AnalyticalResult(
        result_id="refused",
        kind=ResultKind.COMPARISON,
        status=ResultStatus.ABSTAINED,
        tool="change_detection",
        reason="The referenced table is unavailable",
    )
    gated = gate_answer("Karşılaştırma için veri bulunamadı.", refused, connection)
    assert all("absence" not in reason for item in gated.omitted for reason in item.reasons)
