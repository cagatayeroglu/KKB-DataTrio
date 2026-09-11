"""M8-18: a matching amount does not prove a financial claim.

M8-19 widens the causal-wording check at the end of this file.
"""

from datetime import date

import duckdb
import pytest

from kkb_agent.agent.claim_qualifiers import causal_fault
from kkb_agent.agent.verifier import AnswerStatus, Binding, gate_answer, verify, verify_claims
from kkb_agent.analytics import BASE_LIMITATIONS, GRANGER_LIMITATIONS
from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
)
from kkb_agent.database import apply_schema


@pytest.fixture
def connection():
    with duckdb.connect(":memory:") as connection:
        apply_schema(connection)
        connection.execute(
            "INSERT INTO gold_cells VALUES "
            "('audit', 'housing_credit', DATE '2025-01-01', DATE '2025-01-31', "
            "100, 'synthetic-source')"
        )
        yield connection


def result(**changes):
    value = ResultValue(
        label="housing_credit",
        value=100.0,
        unit="TRY",
        scale=Scale.MILLION,
        period=Period(start=date(2025, 1, 1), end=date(2025, 1, 31), frequency=Frequency.MONTHLY),
    ).model_copy(update=changes)
    return AnalyticalResult(
        result_id="january-credit",
        kind=ResultKind.LEVEL,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=[value],
        evidence=ResultEvidence(input_refs=["gold_cells"]),
    )


@pytest.mark.parametrize(
    "draft",
    [
        "Haziran 2025'te 100 milyon USD.",
        "Haziran 2025'te 100 milyon TL.",
        "June 2025: 100 million TRY.",
        "Ocak 2025'te 100 milyon USD.",
        "Ocak 2025'te USD 100 milyon.",
        "Ocak 2025'te 100 milyon EUR.",
        "Ocak 2025'te 100 percent.",
        "Ocak 2025'te 100 milyar TL.",
        "other_series: Ocak 2025'te 100 milyon TL.",
        "series_id=other_series, Ocak 2025'te 100 milyon TL.",
        "SERİES_ID=other_series, Ocak 2025'te 100 milyon TL.",
        "result_id=other_result: Ocak 2025'te 100 milyon TL.",
        "value_label=other_value: Ocak 2025'te 100 milyon TL.",
        "2025-06-01: 100 milyon TL.",
        "Ocak 2024 ve Ocak 2025'te 100 milyon TL.",
    ],
)
def test_explicit_conflicting_qualifiers_are_withheld(connection, draft):
    gated = gate_answer(draft, {"credit": result()}, connection)
    assert gated.status is AnswerStatus.ABSTAINED
    assert not gated.verdict.accepted
    assert gated.omitted


@pytest.mark.parametrize("draft", ["2024 milyon TL", "2024 TL", "USD 2024", "$2024"])
def test_amount_qualified_year_never_gets_year_exemption(connection, draft):
    verdict = verify_claims(draft, result(), connection)
    assert not verdict.accepted
    assert verdict.numbers[0].binding is Binding.UNBOUND
    assert not verify(draft, connection).accepted


@pytest.mark.parametrize("phrase", ["neden oldu", "sebep oldu", "yol açtı", "caused", "led to"])
@pytest.mark.parametrize("with_number", [False, True])
def test_causal_prose_is_not_certified_by_a_related_number(connection, phrase, with_number):
    draft = f"Faiz düşüşü kredilerin artmasına {phrase}"
    if with_number:
        draft += "; Ocak 2025'te 100 milyon TL"
    gated = gate_answer(draft + ".", result(), connection)
    assert gated.status is AnswerStatus.ABSTAINED
    assert not gated.verdict.accepted
    assert any("causal" in reason for reason in gated.omitted[0].reasons)


def test_only_unsupported_causal_sentence_is_removed(connection):
    draft = "Ocak 2025'te 100 milyon TL. Faiz düşüşü kredilerin artmasına neden oldu."
    gated = gate_answer(draft, result(), connection)
    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == "Ocak 2025'te 100 milyon TL."
    assert len(gated.omitted) == 1


@pytest.mark.parametrize(
    "draft",
    [
        "housing_credit: Ocak 2025'te 100 milyon TL.",
        "credit: January 2025, 100 million TRY.",
        "result_id=january-credit: Ocak 2025'te 100 milyon TRY.",
        "series_id=housing_credit: Ocak 2025'te 100 milyon TL.",
        "Ocak 2025'te 100 milyon TL.",
        "2025-01-31: 100 milyon TL.",
    ],
)
def test_correct_qualifiers_preserve_explicit_binding(connection, draft):
    gated = gate_answer(draft, {"credit": result()}, connection)
    assert gated.status is AnswerStatus.ACCEPTED, gated.verdict.rejected
    amount = next(n for n in gated.verdict.numbers if n.number.value == 100)
    assert (amount.source, amount.result_id, amount.value_label) == (
        "credit",
        "january-credit",
        "housing_credit",
    )


def test_plain_year_reference_remains_a_year(connection):
    verdict = verify_claims("Seri 2024 yılında başladı.", result(), connection)
    assert verdict.accepted
    assert verdict.numbers[0].binding is Binding.YEAR


def test_explicit_date_cannot_invent_missing_period(connection):
    assert not verify_claims("Ocak 2025'te 100 milyon TL.", result(period=None)).accepted


def test_same_magnitude_needs_unambiguous_identity():
    first = result()
    second = result(label="other_series").model_copy(update={"result_id": "other-result"})
    for table in ({"credit": first, "other": second}, {"other": second, "credit": first}):
        assert not verify_claims("100 milyon TL.", table).accepted
        verdict = verify_claims("credit: 100 milyon TL.", table)
        assert verdict.accepted
        assert verdict.numbers[0].result_id == "january-credit"


def test_period_selects_the_correct_value_not_the_first_magnitude():
    january = result()
    june = result(period=Period(start=date(2025, 6, 1), end=date(2025, 6, 30)))
    combined = january.model_copy(update={"values": [january.values[0], june.values[0]]})
    verdict = verify_claims("Haziran 2025'te 100 milyon TL.", combined)
    assert verdict.accepted


def test_known_conflicting_identity_cannot_borrow_another_value():
    table = {"credit": result(), "other": result(label="other_series", value=200.0)}
    assert not verify_claims("other: 100 milyon TL.", table).accepted


def test_each_clause_checks_its_own_qualifiers():
    table = {
        "credit": result(),
        "rate": result(label="rate", value=5.0, unit="percent", scale=Scale.ONE),
    }
    good = "credit: Ocak 2025'te 100 milyon TL, rate: Ocak 2025'te yüzde 5."
    assert verify_claims(good, table).accepted
    assert not verify_claims(good.replace("rate: Ocak", "rate: Haziran"), table).accepted


def test_a_supported_year_like_amount_binds_as_a_value():
    verdict = verify_claims("Ocak 2025'te 2024 milyon TL.", result(value=2024.0))
    assert verdict.accepted
    assert verdict.numbers[-1].binding is Binding.RESULT


@pytest.mark.parametrize("month", ["MAYIS", "MAYİS", "HAZİRAN", "KASIM"])
def test_turkish_capital_months_fail_closed_without_parser_errors(month):
    assert not verify_claims(f"{month} 2025'te 100 milyon TL.", result()).accepted


def test_currency_qualifiers_select_the_correct_same_magnitude_value():
    usd = result(unit="USD").model_copy(update={"result_id": "usd-result"})
    for table in ({"try": result(), "usd": usd}, {"usd": usd, "try": result()}):
        verdict = verify_claims("Ocak 2025'te 100 milyon USD.", table)
        assert verdict.accepted
        assert verdict.numbers[-1].source == "usd"


def test_an_allowed_magnitude_cannot_override_contradicted_result_semantics():
    verdict = verify_claims("Haziran 2025'te 100 milyon USD.", result(), allowed=[100])
    assert not verdict.accepted


def test_unknown_unit_is_not_invented():
    unknown = result().model_copy(
        update={
            "values": [result().values[0].model_copy(update={"unit": None})],
            "unresolved_semantics": ["unit is unknown"],
        }
    )
    assert not verify_claims("Ocak 2025'te 100 milyon TL.", unknown).accepted


# M8-19: causal wording beyond the exact past tense. M6-11 gives the writer
# Granger results, and "Granger-causes" is the phrase econometrics teaches.

WIDER_CAUSAL_WORDING = [
    # The cause verbs in other tenses and hedges.
    "Faiz düşüşü kredilerin artmasına neden oluyor",
    "Faiz düşüşü kredilerin artmasına neden olur",
    "Faiz düşüşü kredilerin artmasına neden olabilir",
    "Faiz düşüşü kredilerin artmasına yol açıyor",
    "Faiz düşüşü artışa sebebiyet verdi",
    "The policy rate causes housing credit to rise",
    # Granger's causal vocabulary.
    "The policy rate Granger-causes housing credit",
    "There is Granger causality from the rate to credit",
    "Faiz, kredilerin Granger nedenidir",
    "Faiz, krediler üzerinde Granger nedenselliğine sahiptir",
    # Attributions.
    "Krediler faiz düşüşü nedeniyle arttı",
    "Krediler faiz yüzünden arttı",
    "Artışın sebebi faizdir",
    "Artışın nedenleri faiz ve kurdur",
    "Credit rose due to lower rates",
    "Credit rose because of lower rates",
    "Credit growth was driven by rates",
    "Lower rates lead to more credit",
    # Case and the dotted capital İ.
    "KREDİLER FAİZ DÜŞÜŞÜ NEDENİYLE ARTTI",
]


@pytest.mark.parametrize("sentence", WIDER_CAUSAL_WORDING)
@pytest.mark.parametrize("with_number", [False, True])
def test_wider_causal_wording_is_withheld(connection, sentence, with_number):
    draft = sentence + ("; Ocak 2025'te 100 milyon TL" if with_number else "") + "."
    gated = gate_answer(draft, result(), connection)

    assert gated.status is AnswerStatus.ABSTAINED
    assert any("causal" in reason for reason in gated.omitted[0].reasons)
    assert not verify_claims(draft, result(), connection).accepted


@pytest.mark.parametrize(
    "sentence",
    [
        "Faizin geçmiş değerleri konut kredisi tahminini iyileştirdi",
        "The policy rate precedes housing credit in the Granger sense",
        "Granger testi birinci derecede öncelik gösteriyor",
        "Bu bir ilişki ölçüsüdür; nedensellik kanıtı değildir",
        "This is association, not causation",
        "Nedensel bir yorum yapılamaz",
        "Krediler neden arttı sorusunu bu analiz yanıtlamaz",
    ],
)
def test_precedence_wording_and_disclaimers_still_pass(connection, sentence):
    gated = gate_answer(f"Ocak 2025'te 100 milyon TL. {sentence}.", result(), connection)

    assert gated.status is AnswerStatus.ACCEPTED
    assert not gated.omitted


@pytest.mark.parametrize("text", [*BASE_LIMITATIONS, *GRANGER_LIMITATIONS])
def test_the_analytics_own_limitations_are_not_causal_wording(text):
    # The writer is shown these; quoting one must not cost the sentence.
    assert causal_fault(text) is None


def test_a_denial_in_causal_words_is_withheld_too(connection):
    # Deliberate: telling "neden olmadı" from "neden oldu" is negation parsing,
    # and a parser that gets it wrong lets an assertion through. The result's
    # own limitations already carry the denial.
    draft = "Ocak 2025'te 100 milyon TL. Faiz düşüşü kredilerin artmasına neden olmadı."
    gated = gate_answer(draft, result(), connection)

    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == "Ocak 2025'te 100 milyon TL."
