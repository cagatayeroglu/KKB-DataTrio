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
    SampleCounts,
    Scale,
)
from kkb_agent.database import apply_schema


@pytest.fixture(autouse=True)
def verified_execution_boundary(monkeypatch):
    """Unit-test qualifiers after execution proof; never issue fake evidence.

    M8-21's real producer/resolver/gate integration is covered separately in
    test_execution_evidence.py and test_projection_provenance.py.
    """
    monkeypatch.setattr("kkb_agent.agent.verifier.execution_proof", lambda result, db: True)


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


@pytest.mark.parametrize(
    "sentence",
    [
        "Bu veri nedensellik göstermez.",
        "Bu veriler neden-sonuç ilişkisini kanıtlamak için yeterli değildir.",
        "This is association, not causation.",
    ],
)
def test_safe_causal_limitations_without_assertion_words_survive(sentence):
    assert gate_answer(sentence, result()).status is AnswerStatus.ACCEPTED


@pytest.mark.parametrize(
    "sentence",
    [
        "Faiz kredileri artırmış olabilir.",
        "Konut talebi krediyi tetiklemiş olabilir.",
        "Politika kararı kredi büyümesini etkilemiş olabilir.",
        "Faizler kredi miktarını azaltmış olabilir.",
        "The policy move may have affected credit.",
        "Faiz düşüşü kredi artışının sebebi olabilir.",
    ],
)
def test_hedged_positive_causality_remains_unsupported(sentence):
    gated = gate_answer("Ocak 2025'te 100 milyon TL. " + sentence, result())
    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == "Ocak 2025'te 100 milyon TL."
    assert any("causal" in fault for fault in gated.omitted[0].reasons)


def _endpoint_result():
    first = result()
    last = first.values[0].model_copy(
        update={
            "period": Period(
                start=date(2025, 6, 1), end=date(2025, 6, 30), frequency=Frequency.MONTHLY
            ),
            "value": 120.0,
        }
    )
    return first.model_copy(update={"values": [first.values[0], last]})


def test_typed_endpoint_observation_and_qualified_interpretation_survive():
    draft = (
        "İlk ve son dönem arasında kredi arttı. "
        "Yorum: İlk ve son dönem arasındaki artış gözlenen net değişimi özetler; "
        "ara aylarda aynı yönde hareket edildiği bundan çıkmaz."
    )
    gated = gate_answer(draft, _endpoint_result())
    assert gated.status is AnswerStatus.ACCEPTED
    assert gated.text == draft


def test_wrong_direction_or_insufficient_visible_endpoints_is_withheld():
    for response, values in (
        ("İlk ve son dönemde kredi azaldı.", _endpoint_result()),
        ("İlk ve son dönemde kredi arttı.", result()),
        ("İlk ve son dönemde kredi yükselmedi.", _endpoint_result()),
        ("İlk ve son dönemde kredi artmadı.", _endpoint_result()),
    ):
        gated = gate_answer(response, values)
        assert gated.status is AnswerStatus.ABSTAINED
        assert any("endpoint direction" in reason for reason in gated.omitted[0].reasons)


def test_one_series_cannot_borrow_another_series_endpoint_direction():
    rising = _endpoint_result()
    other_first = result(label="other_series").model_copy(update={"result_id": "other-result"})
    other_last = other_first.values[0].model_copy(
        update={
            "period": Period(
                start=date(2025, 6, 1), end=date(2025, 6, 30), frequency=Frequency.MONTHLY
            ),
            "value": 80.0,
        }
    )
    falling = other_first.model_copy(update={"values": [other_first.values[0], other_last]})
    gated = gate_answer(
        "İlk ve son dönem arasında other_series arttı.",
        {"credit": rising, "other": falling},
    )
    assert gated.status is AnswerStatus.ABSTAINED
    assert any("endpoint direction" in reason for reason in gated.omitted[0].reasons)


@pytest.mark.parametrize(
    "sentence",
    [
        "En belirgin artış son dönemde görüldü.",
        "Düşüşlerin büyük bölümü ikinci yarıda görüldü.",
        "Bu dönemde ivme zayıfladı.",
    ],
)
def test_aggregate_or_superlative_requires_more_than_endpoint_values(sentence):
    gated = gate_answer(sentence, _endpoint_result())
    assert gated.status is AnswerStatus.ABSTAINED
    assert any("aggregate observation" in reason for reason in gated.omitted[0].reasons)


@pytest.mark.xfail(
    strict=True, reason="Free-text external premises have no typed proposition binder"
)
def test_unlisted_external_premise_is_not_yet_deterministically_proven():
    gated = gate_answer("Yorum: Merkez Bankası beklenmedik bir karar aldı.", _endpoint_result())
    assert gated.status is AnswerStatus.ABSTAINED


def test_unqualified_missing_data_cannot_contradict_a_complete_result():
    complete = result().model_copy(update={"samples": SampleCounts(used=3, missing=0)})
    gated = gate_answer("Ocak 2025'te 100 milyon TL. Veri eksik.", complete)
    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == "Ocak 2025'te 100 milyon TL."


def test_typed_missing_samples_allow_only_generic_coverage_disclosure():
    partial = result().model_copy(update={"samples": SampleCounts(used=3, missing=2)})
    supported = gate_answer("Ocak 2025'te 100 milyon TL. Bazı gözlemler eksik.", partial)
    assert supported.status is AnswerStatus.ACCEPTED
    unsupported = gate_answer("Ocak 2025'te 100 milyon TL. Mart verisi eksik.", partial)
    assert unsupported.status is AnswerStatus.QUALIFIED
    assert unsupported.text == "Ocak 2025'te 100 milyon TL."
    # An unnamed absence over two results cannot borrow only one result's gap.
    complete = result().model_copy(update={"samples": SampleCounts(used=3, missing=0)})
    assert (
        gate_answer("Veri eksik.", {"partial": partial, "complete": complete}).status
        is AnswerStatus.ABSTAINED
    )


class TestTheWindowACountDescribes:
    """A sentence about how much data was read is not a claim about a figure."""

    @staticmethod
    def _five_years(**changes):
        """A result over 2021-01..2025-12: sixty monthly observations, five years."""
        return result(
            period=Period(
                start=date(2021, 1, 1), end=date(2025, 12, 31), frequency=Frequency.MONTHLY
            )
        ).model_copy(
            update={
                "coverage": Period(
                    start=date(2021, 1, 1), end=date(2025, 12, 31), frequency=Frequency.MONTHLY
                ),
                "samples": SampleCounts(used=60),
                **changes,
            }
        )

    def test_the_period_count_of_the_window_is_context(self):
        verdict = verify_claims(
            "2021-2025 arasındaki 60 aylık veride bakiye 100 milyon TL oldu.", self._five_years()
        )

        assert verdict.accepted
        sixty = next(item for item in verdict.numbers if item.number.value == 60.0)
        assert sixty.binding is Binding.CONTEXT

    def test_the_window_in_whole_years_is_context(self):
        verdict = verify_claims("Son 5 yılda bakiye 100 milyon TL oldu.", self._five_years())

        assert verdict.accepted

    def test_a_count_the_window_does_not_hold_is_still_unbound(self):
        verdict = verify_claims("Son 7 yılda bakiye 100 milyon TL oldu.", self._five_years())

        assert not verdict.accepted

    def test_a_window_count_cannot_be_quoted_as_an_amount(self):
        # 60 is the number of months read. It is not sixty million lira, and a
        # figure that names a unit still has to be one of the result's values.
        verdict = verify_claims("Bakiye 60 milyon TL oldu.", self._five_years())

        assert not verdict.accepted

    def test_periods_left_out_are_context_too(self):
        # The tools now tell the writer how many periods were skipped; saying so
        # in the answer must not cost the sentence.
        result_with_gap = self._five_years(samples=SampleCounts(used=57, missing=2, excluded=1))
        verdict = verify_claims(
            "2 dönem yayımlanmamıştı ve 1 çift dışlandı; bakiye 100 milyon TL oldu.",
            result_with_gap,
        )

        assert verdict.accepted


class TestACountIsOnlyQuotedAsWhatItIs:
    """Holding a number is not licence to use it for anything.

    Over a five-year monthly window the harness holds 60 and 5. Binding those on
    the digits alone accepted "5 dönem yayımlanmamıştı" although nothing was
    missing, and "60 farklı seri incelendi" although one series was read - true
    numbers in a false role, which is the sentence a reader would catch.
    """

    @staticmethod
    def _window(**changes):
        period = Period(start=date(2021, 1, 1), end=date(2025, 12, 31), frequency=Frequency.MONTHLY)
        return result(period=period).model_copy(
            update={"coverage": period, "samples": SampleCounts(used=60), **changes}
        )

    @pytest.mark.parametrize(
        "draft",
        [
            "2021-2025 arasındaki 60 aylık veride bakiye 100 milyon TL oldu.",
            "Son 5 yılda bakiye 100 milyon TL oldu.",
            "60 gözlem okundu; bakiye 100 milyon TL oldu.",
        ],
    )
    def test_a_count_called_what_it_is_passes(self, draft):
        assert verify_claims(draft, self._window()).accepted

    @pytest.mark.parametrize(
        "draft",
        [
            "5 dönem yayımlanmamıştı; bakiye 100 milyon TL oldu.",  # 5 is the years
            "60 farklı seri incelendi; bakiye 100 milyon TL oldu.",  # 60 is the months
            "Analiz 5 ayı kapsıyor; bakiye 100 milyon TL oldu.",  # 5 is years, not months
            "5 gözlem okundu; bakiye 100 milyon TL oldu.",  # 60 observations were read
        ],
    )
    def test_the_same_number_in_another_role_is_unbound(self, draft):
        assert not verify_claims(draft, self._window()).accepted

    def test_periods_read_cannot_be_quoted_as_periods_missing(self):
        gapped = self._window(samples=SampleCounts(used=57, missing=2, excluded=1))

        assert verify_claims("2 dönem eksikti; bakiye 100 milyon TL.", gapped).accepted
        assert not verify_claims("57 dönem eksikti; bakiye 100 milyon TL.", gapped).accepted

    def test_count_role_must_belong_to_the_number_not_a_later_conjoined_phrase(self):
        sample = self._window()
        wrong = "60 farklı seri ve 60 gözlem incelendi. Bakiye 100 milyon TL oldu."
        assert not verify_claims(wrong, sample).accepted
        assert gate_answer(wrong, sample).status is AnswerStatus.QUALIFIED

    def test_preceding_or_following_local_count_role_still_binds(self):
        sample = self._window()
        for phrase in (
            "60 aylık veri ve 60 gözlem incelendi; bakiye 100 milyon TL oldu.",
            "Gözlem sayısı 60 ve dönem 60 ay; bakiye 100 milyon TL oldu.",
        ):
            assert verify_claims(phrase, sample).accepted

    @pytest.mark.parametrize(
        "draft",
        [
            # The months belong to the first 60; they lend the second one nothing.
            "60 aylık dönemde 60 milyarlık artış oldu.",
            "60 aylık dönemde bakiye 60 puan arttı.",
            "Son 5 yılda bakiye 5 kat arttı.",
            # A multiple, an amount or points never count periods, whatever follows them.
            "Bakiye 5 kat arttı; yıllık bazda da yükseldi.",
            "Artış 60 bin aylık ödemeye denk geldi.",
        ],
    )
    def test_a_role_word_another_number_owns_lends_nothing(self, draft):
        assert not verify_claims(draft, self._window()).accepted

    def test_a_role_named_before_its_own_number_still_binds(self):
        sample = self._window()
        for phrase in (
            "Gözlem sayısı 60'tır; bakiye 100 milyon TL oldu.",
            "Pencere 5 yıl, yani 60 ay; bakiye 100 milyon TL oldu.",
        ):
            assert verify_claims(phrase, sample).accepted, phrase

    def test_question_number_does_not_make_a_new_financial_claim(self):
        sample = self._window()
        # The request may mention 60 months, but the result has no 60% rate.
        assert not verify_claims("Faiz %60 oldu.", sample).accepted

    @pytest.mark.parametrize("draft", ["İlk 3 dönemde bakiye arttı.", "Seri 3. sırada yer aldı."])
    def test_ordinal_or_rank_without_typed_evidence_does_not_become_context(self, draft):
        assert not verify_claims(draft, self._window()).accepted
