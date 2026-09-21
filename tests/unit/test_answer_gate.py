"""M8-10: what the verifier lets through, and the first end-to-end slice.

Verification that nothing routes through is a report, not a gate. These tests
are about the decision itself — which sentence is shown, which is withheld,
and when the honest output is no answer at all.

The end-to-end class is the first time a question reaches a gated answer
through the real planner, registry, tool and verifier, with only the model
scripted.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import (
    AnswerStatus,
    ExecutionContext,
    Session,
    ToolRegistry,
    collect_results,
    gate_answer,
    render_result,
)
from kkb_agent.agent.presentation import display_value, format_number
from kkb_agent.agent.verifier import (
    DEFAULT_TOLERANCE,
    Binding,
    OmissionCode,
    extract_numbers,
    parse_written,
)
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm.doubles import scripted
from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)
MONTHLY = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
PUBLISHED = {date(2026, 4, 30): 767314.0, date(2026, 5, 31): 782918.0, date(2026, 6, 30): 801438.0}

JUNE = Period(start=date(2026, 6, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY)
SUPPORTED = "Haziran 2026'da konut kredisi stoğu 801.438 milyon TL."
INVENTED = "Temmuz ayında 912.000 milyon TL'ye ulaştı."


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 801438}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        lake.register_series(
            "bddk:konut",
            title="Tüketici Kredileri - Konut",
            semantics=MONTHLY,
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations(
            "bddk:konut",
            [Observation(date(end.year, end.month, 1), end, v) for end, v in PUBLISHED.items()],
        )
        yield lake


def result(**overrides) -> AnalyticalResult:
    fields = {
        "result_id": "r1",
        "kind": ResultKind.LEVEL,
        "status": ResultStatus.COMPUTED,
        "tool": "lakehouse",
        "values": [
            ResultValue(
                label="bddk:konut",
                value=801438.0,
                unit="TRY",
                scale=Scale.MILLION,
                measure=StockFlow.STOCK,
                period=JUNE,
            )
        ],
        "samples": SampleCounts(used=3),
        "evidence": ResultEvidence(input_refs=["silver_observations"]),
    }
    fields.update(overrides)
    return AnalyticalResult(**fields)


@pytest.fixture(autouse=True)
def producer_fixture_for_sentence_tests(request, monkeypatch):
    if request.cls not in {
        TestASupportedAnswerPassesThrough,
        TestAnUnsupportedSentenceIsWithheld,
        TestTheWithheldSentenceCanBeDiagnosedWithoutItsText,
        TestAbstention,
        TestTheInterpretationParagraph,
    }:
        return
    house = request.getfixturevalue("house")
    produced = (
        make_lakehouse_tool(house.connection)
        .run(LakehouseArguments(sql=FULLY_TYPED), ExecutionContext(question="fixture"))
        .output.result
    )

    def supplied(**overrides):
        return produced.model_copy(deep=True, update=overrides)

    monkeypatch.setattr(__name__ + ".result", supplied)


class TestASupportedAnswerPassesThrough:
    def test_it_is_accepted_whole(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection)

        assert gated.status is AnswerStatus.ACCEPTED
        assert gated.text == SUPPORTED
        assert gated.omitted == ()
        assert gated.presentable

    def test_the_limitations_travel_with_it(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection)
        assert any("bound to these results' values" in item for item in gated.limitations)

    def test_prose_without_numbers_is_kept(self, house):
        draft = f"{SUPPORTED} Seri aylık yayımlanmaktadır."
        gated = gate_answer(draft, result(), house.connection)

        assert gated.status is AnswerStatus.ACCEPTED
        assert "aylık yayımlanmaktadır" in gated.text


class TestAnUnsupportedSentenceIsWithheld:
    def test_only_the_offending_sentence_is_dropped(self, house):
        gated = gate_answer(f"{SUPPORTED} {INVENTED}", result(), house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert gated.text == SUPPORTED
        assert "912.000" not in gated.text

    def test_the_withheld_sentence_is_recorded_not_discarded(self, house):
        # A silently shortened answer is indistinguishable from one that never
        # made the claim, and the operator needs to see the difference.
        gated = gate_answer(f"{SUPPORTED} {INVENTED}", result(), house.connection)

        assert len(gated.omitted) == 1
        assert gated.omitted[0].text == INVENTED
        assert gated.omitted[0].reasons

    def test_a_wrongly_scaled_sentence_is_withheld_though_its_number_is_real(self, house):
        # The figure exists; "bin" contradicts the recorded million scale.
        gated = gate_answer(
            f"{SUPPORTED} Diğer bir deyişle 801.438 bin TL.", result(), house.connection
        )

        assert gated.status is AnswerStatus.QUALIFIED
        assert "bin TL" not in gated.text
        assert any("recorded as million" in r for r in gated.omitted[0].reasons)

    def test_a_sentence_attributed_to_the_wrong_year_is_withheld(self, house):
        gated = gate_answer(
            f"{SUPPORTED} 2019'da da 801.438 milyon TL idi.", result(), house.connection
        )

        assert gated.status is AnswerStatus.QUALIFIED
        assert "2019" not in gated.text

    def test_the_final_sentence_without_trailing_punctuation_is_still_gated(self, house):
        gated = gate_answer(f"{SUPPORTED} Ayrıca 912.000 milyon TL", result(), house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert "912.000" not in gated.text


class TestTheInterpretationParagraph:
    """The jury asks for a reading of the numbers; the gate asks for evidence.

    Both are served by one labelled paragraph: it may read the pattern and name
    factors worth testing, it may hold no number that is not a listed display, and
    it may not assert a cause. It is the only heading the writer is allowed.
    """

    def test_a_labelled_reading_is_kept(self, house):
        reading = (
            " Yorum: Seri yıl boyunca yükselişte; konut talebi ve kredi koşulları test "
            "edilmeye değer etkenlerdir, bu analiz bir açıklama kurmuş değildir."
        )
        gated = gate_answer(SUPPORTED + reading, result(), house.connection)
        assert gated.status is AnswerStatus.ACCEPTED
        assert "Yorum:" in gated.text

    def test_a_cause_in_that_paragraph_is_the_writers_to_state(self, house):
        # The gate binds figures. The vocabulary rule that withheld this sentence could not
        # tell "nedeni" from "nedeni değildir", and the jury asks for exactly this reading.
        causal = " Yorum: Artışın nedeni muhtemelen faiz indirimidir."
        gated = gate_answer(SUPPORTED + causal, result(), house.connection)
        assert gated.status is AnswerStatus.ACCEPTED
        assert "nedeni" in gated.text

    def test_the_optional_wording_contract_still_withholds_it(self, house, monkeypatch):
        monkeypatch.setattr("kkb_agent.agent.verifier.WORDING_RULES", True)
        causal = " Yorum: Artışın nedeni faiz indirimidir."
        gated = gate_answer(SUPPORTED + causal, result(), house.connection)
        assert gated.status is AnswerStatus.QUALIFIED and "nedeni" not in gated.text

    def test_a_new_number_in_that_paragraph_is_still_withheld(self, house):
        invented = " Yorum: Yıl boyunca 912.000 milyon TL seviyesine yaklaşıldı."
        gated = gate_answer(SUPPORTED + invented, result(), house.connection)
        assert gated.status is AnswerStatus.QUALIFIED
        assert "912.000" not in gated.text


class TestAbstention:
    def test_an_answer_with_nothing_left_abstains_rather_than_shrinking(self, house):
        gated = gate_answer(INVENTED, result(), house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.text == ""
        assert not gated.presentable
        assert gated.abstention

    def test_a_disqualified_result_takes_the_whole_draft_with_it(self, house):
        # A dangling evidence reference poisons the unnumbered prose too,
        # because the prose describes the same broken result.
        broken = result(evidence=ResultEvidence(input_refs=["silver_invented"]))
        gated = gate_answer(f"{SUPPORTED} Seri aylıktır.", broken, house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.text == ""
        assert "resolves to no table" in (gated.abstention or "")

    def test_a_tampered_result_abstains(self, house):
        tampered = result(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=850000.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=JUNE,
                )
            ]
        )
        gated = gate_answer("Haziran 2026'da 850.000 milyon TL.", tampered, house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert "stored as 801438.0" in (gated.abstention or "")

    def test_a_sample_floor_failure_abstains(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection, minimum_samples=24)

        assert gated.status is AnswerStatus.ABSTAINED
        assert "below the 24" in (gated.abstention or "")

    def test_an_empty_draft_abstains_and_says_which_kind_of_nothing(self, house):
        gated = gate_answer("   ", result(), house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.abstention == "The answer was empty"


@pytest.fixture
def verified_execution_boundary(monkeypatch):
    """Display/rounding unit tests start after execution verification."""
    monkeypatch.setattr("kkb_agent.agent.verifier.execution_proof", lambda result, db: True)


@pytest.mark.usefixtures("verified_execution_boundary")
class TestReadableVerifiedFigures:
    @pytest.mark.parametrize(
        "number, expected",
        [
            (767314.0, "767.314"),
            (1234567.89, "1.234.570"),
            (4.447201536789372, "4,4472"),
            (0.0000123456789, "0,0000123457"),
            (-767314.0, "-767.314"),
            (-4.447201536789372, "-4,4472"),
            (46.75, "46,75"),
            (1.234, "1,2340"),
            (0.001, "0,0010"),
            (1234.125, "1.234,12"),
            (0.0, "0"),
            (-0.0, "0"),
        ],
    )
    def test_display_round_trips_to_the_original_result(self, number, expected):
        value = ResultValue(label="rate", value=number, unit="percent", scale=Scale.ONE)
        trusted = result(values=[value])
        original = trusted.model_dump_json(), trusted.digest(), value.value.hex()
        assert format_number(number) == expected
        display = display_value(value)
        assert display == f"{expected} yüzde"
        verdict = gate_answer(f"rate: {display}.", trusted)
        assert verdict.status is AnswerStatus.ACCEPTED
        bound = verdict.verdict.numbers
        assert len(bound) == 1
        assert bound[0].binding is Binding.RESULT
        assert bound[0].result_id == trusted.result_id
        assert bound[0].value_label == "rate"
        assert original == (trusted.model_dump_json(), trusted.digest(), value.value.hex())

    @pytest.mark.parametrize(
        "number", [5e-324, 1e-300, -1e-300, 1.23456789e100, 1.7976931348623157e308]
    )
    def test_finite_float_extremes_are_bounded_single_numbers(self, number):
        display = format_number(number)
        extracted = extract_numbers(display)
        assert len(display) < 420
        assert len(extracted) == 1
        assert extracted[0].text == display
        # Relative-only assertion is stricter than the gate's additional 1e-9 floor.
        assert math.isclose(extracted[0].value, number, rel_tol=DEFAULT_TOLERANCE)

    @pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
    def test_nonfinite_values_have_no_display(self, number):
        with pytest.raises(ValueError, match="finite"):
            format_number(number)

    def test_currency_scale_period_and_identity_survive_rendering(self):
        value = ResultValue(
            label="credit", value=767314.0, unit="TRY", scale=Scale.MILLION, period=JUNE
        )
        trusted = result(values=[value])
        before = trusted.model_dump_json(), trusted.digest()
        rendered = render_result(trusted)
        assert "display 767.314 milyon TL" in rendered
        assert "767314.0" not in rendered
        assert "unit TRY, scale million, period 2026-06-01..2026-06-30" in rendered
        gated = gate_answer(f"credit: Haziran 2026'da {display_value(value)}.", trusted)
        assert gated.status is AnswerStatus.ACCEPTED
        assert next(n for n in gated.verdict.numbers if n.binding is Binding.RESULT).source == "r1"
        assert before == (trusted.model_dump_json(), trusted.digest())

    @pytest.mark.parametrize(
        "draft",
        [
            "Haziran 2026'da 801.438 milyon USD.",
            "Haziran 2026'da 801.438 bin TL.",
            "Temmuz 2026'da 801.438 milyon TL.",
            "Haziran 2026'da 912.000 milyon TL.",
            "result_id=wrong 801.438 milyon TL.",
        ],
    )
    def test_display_does_not_bypass_semantic_or_numeric_checks(self, draft):
        assert gate_answer(draft, result()).status is AnswerStatus.ABSTAINED

    def test_a_list_marker_is_not_a_claim(self):
        """Live 2026-09-20: "(1) catalog_search; (2) web_search" lost its sentence.

        Those markers measure nothing and bound to nothing, so the gate withheld
        the only sentence that answered the question and what reached the reader
        began mid-thought.
        """
        from kkb_agent.agent.presentation import display_value

        value = ResultValue(
            label="credit", value=767314.0, unit="TRY", scale=Scale.MILLION, period=JUNE
        )
        trusted = result(values=[value])
        reply = (
            "Elinde iki ana araç var: (1) catalog_search — resmî serileri bulmak için; "
            "(2) web_search — sayfaları bulmak için."
        )
        assert gate_answer(reply, trusted).status is AnswerStatus.ACCEPTED
        assert not gate_answer(reply, trusted).omitted
        # A figure in brackets is still a figure when it carries an amount.
        assert (
            gate_answer("Haziran 2026'da (1) milyon TL.", trusted).status is AnswerStatus.ABSTAINED
        )
        # And a real claim beside markers still has to bind.
        assert (
            gate_answer(f"(1) Haziran 2026'da {display_value(value)}.", trusted).status
            is AnswerStatus.ACCEPTED
        )

    def test_naive_rounding_is_still_withheld(self):
        value = ResultValue(label="rate", value=4.447201536789372, unit="percent", scale=Scale.ONE)
        trusted = result(values=[value])
        assert DEFAULT_TOLERANCE == 5e-4
        assert parse_written("4,447") == 4447.0  # Existing locale policy is not relaxed.
        assert gate_answer("rate: 4,45 yüzde.", trusted).status is AnswerStatus.ABSTAINED
        assert gate_answer("rate: 4,447 yüzde.", trusted).status is AnswerStatus.ABSTAINED
        assert (
            gate_answer(f"rate: {display_value(value)}.", trusted).status is AnswerStatus.ACCEPTED
        )

    @pytest.mark.parametrize(
        "unit, scale, expected",
        [
            ("TRY", Scale.THOUSAND, "12,5 bin TL"),
            ("USD", Scale.BILLION, "12,5 milyar USD"),
            ("%", Scale.ONE, "12,5 yüzde"),
            ("percentage_points", Scale.ONE, "12,5 yüzde puan"),
            ("basis points", Scale.ONE, "12,5 baz puan"),
            ("index points", Scale.ONE, "12,5 endeks puan"),
            ("dimensionless", Scale.ONE, "12,5 dimensionless"),
            # A count is a number of things; the label says what they are, so the
            # display adds no unit word. A quoted price is money per quantity
            # (DEC-177). Neither had a display before (finding DN-6.4).
            ("count", Scale.ONE, "12,5"),
            ("count", Scale.THOUSAND, "12,5 bin"),
            ("TRY/g", Scale.ONE, "12,5 TL/gr"),
            ("USD/oz", Scale.ONE, "12,5 USD/ons"),
            ("TRY/piece", Scale.ONE, "12,5 TL/adet"),
        ],
    )
    def test_only_explicit_unit_and_scale_mappings_are_used(self, unit, scale, expected):
        value = ResultValue(label="metric", value=12.5, unit=unit, scale=scale)
        assert display_value(value) == expected
        assert gate_answer(expected, result(values=[value])).status is AnswerStatus.ACCEPTED

    @pytest.mark.parametrize(
        "unit, scale", [(None, Scale.ONE), ("TRY", Scale.UNKNOWN), ("unlisted-unit", Scale.ONE)]
    )
    def test_unknown_or_unsupported_metadata_has_no_numeric_display(self, unit, scale):
        value = ResultValue(label="metric", value=987654.0, unit=unit, scale=scale)
        trusted = result(values=[value], unresolved_semantics=["unit/scale not established"])
        assert display_value(value) is None
        rendered = render_result(trusted)
        assert "display UNAVAILABLE" in rendered
        assert "987654" not in rendered
        assert gate_answer("987.654 milyon TL.", trusted).status is AnswerStatus.ABSTAINED

    def test_writer_receives_only_display_then_gate_checks_its_actual_draft(self):
        value = ResultValue(label="rate", value=4.447201536789372, unit="percent", scale=Scale.ONE)
        trusted = result(values=[value])
        provider = scripted("rate: 4,45 yüzde.")
        session = Session(provider, ToolRegistry())
        draft = session.draft("Oran?", {"rate": trusted})
        context = "\n".join(m.content for m in provider.seen[-1])
        assert "display 4,4472 yüzde" in context
        assert "4.447201536789372" not in context
        assert "Copy a figure exactly as its display phrase gives it" in context
        assert gate_answer(draft, {"rate": trusted}).status is AnswerStatus.ABSTAINED


class TestAPlainTableStillAnswers:
    def test_the_writer_is_given_each_column_s_first_and_last_period(self):
        """Live 2026-09-20: twelve monthly balances reached the writer with no
        figure at all, because every per-period value belongs to the table shown
        beside the answer. What it wrote said only that a table exists, which the
        reader was already looking at. Two ends per column cannot be aggregated
        into a new number the way rows can, and the gate binds them like any
        other value.
        """
        from datetime import date

        from kkb_agent.agent.loop import render_result
        from kkb_agent.core import Frequency, Period

        months = [
            Period(
                start=date(2025, month, 1),
                end=date(2025, month, 28),
                frequency=Frequency.MONTHLY,
            )
            for month in range(1, 13)
        ]
        values = [
            ResultValue(
                label="konut",
                value=1000.0 + index * 10,
                unit="TRY",
                scale=Scale.MILLION,
                period=period,
            )
            for index, period in enumerate(months)
        ]
        rendered = render_result(result(values=values))
        quoted = [line for line in rendered.splitlines() if line.startswith("- konut:")]
        assert len(quoted) == 2
        assert "2025-01-01..2025-01-28" in quoted[0] and "1.000 milyon TL" in quoted[0]
        assert "2025-12-01..2025-12-28" in quoted[1] and "1.110 milyon TL" in quoted[1]
        assert "No value is listed" not in rendered

    def test_writer_receives_verified_endpoint_without_middle_rows_or_extra_call(self):
        months = [
            Period(
                start=date(2025, month, 1), end=date(2025, month, 28), frequency=Frequency.MONTHLY
            )
            for month in range(1, 13)
        ]
        values = [
            ResultValue(
                label="konut",
                value=float(1000 + index * 10),
                unit="TRY",
                scale=Scale.MILLION,
                period=period,
            )
            for index, period in enumerate(months)
        ]
        provider = scripted("Konut kredisi ilk ve son dönem arasında arttı.")
        draft = Session(provider, ToolRegistry()).draft(
            "Konut kredisi?", {"credit": result(values=values)}
        )
        assert draft and len(provider.seen) == 1
        system, evidence, question = (message.content for message in provider.seen[0])
        assert "Verified endpoint observation for konut: rose" in evidence
        assert evidence.count(": display ") == 2  # the twelve-row table is not sent
        assert "1.050 milyon TL" not in evidence
        assert len(system.encode()) < 3130  # measured pre-workstream system prompt
        assert sum(len(part.encode()) for part in (system, evidence, question)) < 3770


class TestWhatTheWriterIsGiven:
    def test_the_rendered_result_carries_units_and_periods(self):
        rendered = render_result(result())

        assert "display 801.438 milyon TL" in rendered
        assert "801438.0" not in rendered
        assert "unit TRY" in rendered
        assert "scale million" in rendered
        assert "2026-06-01..2026-06-30" in rendered

    def test_an_unknown_unit_is_shown_as_unknown_not_omitted(self):
        rendered = render_result(
            result(
                values=[ResultValue(label="x", value=1.0)],
                unresolved_semantics=["unit is unresolved"],
            )
        )

        assert "unit UNKNOWN" in rendered
        assert "Unresolved: unit is unresolved" in rendered

    def test_limitations_reach_the_writer(self):
        rendered = render_result(
            result(
                kind=ResultKind.ASSOCIATION,
                values=[ResultValue(label="r", value=0.7, unit="dimensionless", scale=Scale.ONE)],
                limitations=["Association only; not a cause"],
            )
        )
        assert "Limitation: Association only" in rendered

    def test_warnings_reach_the_writer_too(self):
        # The tool computed the caution; before this it stopped at the result object
        # and the answer told the reader an unusual month without saying what one is.
        rendered = render_result(
            result(
                kind=ResultKind.ANOMALY,
                values=[ResultValue(label="n", value=2.0, unit="dimensionless", scale=Scale.ONE)],
                warnings=["An unusual change is not an error, an event or a cause"],
            )
        )
        assert "An unusual change is not an error" in rendered
        assert "without a figure" in rendered


def plan_json(sql: str) -> str:
    return json.dumps(
        {
            "question": "konut kredisi",
            "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {"sql": sql}}],
        }
    )


FULLY_TYPED = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    " WHERE o.period_end = DATE '2026-06-30'"
)


class TestTheWholeSliceEndToEnd:
    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
        return registry

    def test_a_question_becomes_a_gated_answer(self, house):
        provider = scripted(plan_json(FULLY_TYPED), SUPPORTED)
        session = Session(provider, self.registry(house))

        answered = session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        assert answered.answer.status is AnswerStatus.ACCEPTED
        assert "801.438" in answered.answer.text
        assert answered.results[-1].status is ResultStatus.COMPUTED

    def test_a_model_that_invents_a_figure_has_it_stripped(self, house):
        provider = scripted(plan_json(FULLY_TYPED), f"{SUPPORTED} {INVENTED}")
        session = Session(provider, self.registry(house))

        answered = session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        assert answered.answer.status is AnswerStatus.QUALIFIED
        assert "912.000" not in answered.answer.text
        assert answered.answer.omitted

    def test_the_writer_never_sees_rows_only_computed_values(self, house):
        provider = scripted(plan_json(FULLY_TYPED), SUPPORTED)
        session = Session(provider, self.registry(house))
        session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        writer_prompt = "\n".join(m.content for m in provider.seen[-1])
        assert "display 801.438 milyon TL" in writer_prompt
        assert "801438.0" not in writer_prompt
        assert "SELECT" not in writer_prompt

    def test_a_query_that_establishes_nothing_abstains_without_a_draft(self, house):
        # The model is never asked to write about an analysis that produced
        # nothing, so there is only one scripted response to consume.
        provider = scripted(plan_json("SELECT series_id, title FROM silver_series"))
        session = Session(provider, self.registry(house))

        answered = session.answer("Hangi seriler var?", house.connection)

        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert "listing" in (answered.answer.abstention or "")

    def test_a_failed_step_yields_an_abstention_not_an_answer(self, house):
        provider = scripted(plan_json("SELECT * FROM lineage_nodes"))
        session = Session(provider, self.registry(house))

        answered = session.answer("Soy ağacı nedir?", house.connection)

        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert "No tool produced an analytical result" in (answered.answer.abstention or "")

    def test_results_are_collected_only_from_successful_steps(self, house):
        registry = self.registry(house)
        outcome = registry.get("lakehouse").run(
            LakehouseArguments(sql="SELECT * FROM lineage_nodes"),
            ExecutionContext(question="q"),
        )

        class Outcome:
            results = (outcome,)

        assert collect_results(Outcome()) == ()


@pytest.mark.parametrize("repaired", [SUPPORTED, "Temmuz 2026'da 801.438 milyon TL.", INVENTED])
def test_period_wording_repair_is_bounded_and_reverified_before_publication(house, repaired):
    from kkb_agent.agent import Workspace

    wrong_period = "Temmuz 2026'da konut kredisi stoğu 801.438 milyon TL."
    provider = scripted(plan_json(FULLY_TYPED), wrong_period, repaired)
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection))
    workspace = Workspace.open(house.connection)
    answer = Session(provider, registry, repair_period_wording=True).answer(
        "Haziran bakiyesi?", house.connection, workspace=workspace, remember="table"
    )
    assert len(provider.seen) == 3
    assert len(answer.outcome.results) == 1
    # The second draft sees exactly the same computed values, not a recomputation.
    assert provider.seen[1][1].content == provider.seen[2][1].content
    assert wrong_period not in provider.seen[2][0].content
    if repaired == SUPPORTED:
        assert answer.answer.status is AnswerStatus.ACCEPTED
        assert workspace.names() == ["table"]
    else:
        assert answer.answer.status is AnswerStatus.ABSTAINED
        assert workspace.names() == []


def test_period_repair_does_not_retry_invented_values(house):
    provider = scripted(plan_json(FULLY_TYPED), INVENTED)
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection))
    answer = Session(provider, registry, repair_period_wording=True).answer("q", house.connection)
    assert answer.answer.status is AnswerStatus.ABSTAINED
    assert len(provider.seen) == 2


@pytest.mark.parametrize("repaired", [SUPPORTED, INVENTED])
def test_unmatched_numeric_repair_is_bounded_and_fully_reverified(house, repaired):
    from kkb_agent.agent import Workspace

    provider = scripted(plan_json(FULLY_TYPED), INVENTED, repaired)
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection))
    workspace = Workspace.open(house.connection)
    prior = result(result_id="prior")
    workspace.publish(workspace.preview("prior", prior))
    prior_digest = workspace.value_of("prior").digest()

    answer = Session(provider, registry, repair_unmatched_numbers=True).answer(
        "Haziran bakiyesi?", house.connection, workspace=workspace, remember="candidate"
    )

    assert len(provider.seen) == 3
    assert provider.seen[1][1].content == provider.seen[2][1].content
    assert INVENTED not in provider.seen[2][0].content
    assert "Do not derive a percentage" in provider.seen[2][0].content
    assert workspace.value_of("prior").digest() == prior_digest
    if repaired == SUPPORTED:
        assert answer.answer.status is AnswerStatus.ACCEPTED
        assert workspace.names() == ["candidate", "prior"]
    else:
        assert answer.answer.status is AnswerStatus.ABSTAINED
        assert workspace.names() == ["prior"]


def test_period_repair_provider_failure_preserves_first_gated_answer(house, monkeypatch):
    from kkb_agent.agent import Workspace
    from kkb_agent.llm.provider import ProviderError

    wrong_period = "Temmuz 2026'da konut kredisi stoğu 801.438 milyon TL."
    provider = scripted(plan_json(FULLY_TYPED), "Seri aylık yayımlanmaktadır. " + wrong_period)
    complete = provider.complete
    calls = []

    def fail_repair(*args, **kwargs):
        calls.append(1)
        if len(calls) == 3:
            raise ProviderError("private transport detail")
        return complete(*args, **kwargs)

    monkeypatch.setattr(provider, "complete", fail_repair)
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection))
    workspace = Workspace.open(house.connection)
    answer = Session(provider, registry, repair_period_wording=True).answer(
        "q", house.connection, workspace=workspace, remember="table"
    )
    # The table is the tools' and is published; the prose about it stays qualified.
    assert len(calls) == 3 and workspace.names() == ["table"]
    assert answer.answer.status is AnswerStatus.QUALIFIED
    assert answer.answer.text == "Seri aylık yayımlanmaktadır."
    assert "private transport detail" not in answer.answer.text


class TestTheWithheldSentenceCanBeDiagnosedWithoutItsText:
    """M11-11: a live omission has to be findable again without another run.

    The reason strings quote the draft, so an operator log cannot keep them.
    These records carry the diagnosis — which sentence, which categories, which
    quantity, and what it bound to — and nothing that rebuilds the wording.
    """

    def test_an_invented_number_is_reported_as_unbound_with_its_parsed_value(self, house):
        gated = gate_answer(f"{SUPPORTED} {INVENTED}", result(), house.connection)

        (omitted,) = gated.omitted
        assert omitted.index == 1
        assert omitted.codes == (OmissionCode.UNMATCHED_NUMBER,)
        (number,) = omitted.numbers
        assert number.value == 912000.0
        assert number.binding is Binding.UNBOUND
        assert (number.result_id, number.value_label) == (None, None)
        assert number.codes == (OmissionCode.UNMATCHED_NUMBER,)

    def test_a_real_value_quoted_at_the_wrong_scale_names_what_it_bound_to(self, house):
        gated = gate_answer(
            f"{SUPPORTED} Diğer bir deyişle 801.438 bin TL.", result(), house.connection
        )

        (omitted,) = gated.omitted
        (number,) = omitted.numbers
        assert number.value == 801438.0
        assert number.binding is not Binding.UNBOUND
        assert number.value_label == "bddk:konut"
        assert OmissionCode.UNIT_SCALE in number.codes

    def test_the_index_locates_the_sentence_among_the_kept_ones(self, house):
        draft = f"{SUPPORTED} Seri aylık yayımlanmaktadır. {INVENTED}"
        gated = gate_answer(draft, result(), house.connection)

        (omitted,) = gated.omitted
        assert omitted.index == 2
        assert gated.text == f"{SUPPORTED} Seri aylık yayımlanmaktadır."

    def test_an_accepted_answer_carries_no_diagnostics_at_all(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection)

        assert gated.omitted == ()

    def test_the_diagnosis_cannot_rebuild_the_draft(self, house):
        # The negative control for the operator log: the record is allowed to
        # carry parsed values and our own identities, never the model's words.
        draft = f"{SUPPORTED} {INVENTED}"
        gated = gate_answer(draft, result(), house.connection)

        (omitted,) = gated.omitted
        exported = json.dumps(
            {
                "sentence": omitted.index,
                "codes": [code.value for code in omitted.codes],
                "numbers": [
                    {
                        "value": number.value,
                        "binding": number.binding.value,
                        "result_id": number.result_id,
                        "value_label": number.value_label,
                        "codes": [code.value for code in number.codes],
                    }
                    for number in omitted.numbers
                ],
            },
            ensure_ascii=False,
        )
        assert "912.000" not in exported
        for word in ("Temmuz", "ulaştı", "milyon", "konut", "kredisi"):
            assert word not in exported
        assert not any(reason in exported for reason in omitted.reasons)
