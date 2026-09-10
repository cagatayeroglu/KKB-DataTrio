"""M8-06/07: binding a claim to one result instead of to the whole store.

`verify` asks "does a number like this exist anywhere?", which accepts a
right-looking figure taken from the wrong series, the wrong period or the
wrong scale. These tests are about the stronger question — is this the number
*this* analysis produced, and does the sentence around it agree with what the
analysis established?

The cases that matter most are the ones the old check passes and this one
must not: a correct figure quoted at the wrong scale, a correct figure
attributed to the wrong year, and a figure from a result that established
nothing at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import ExecutionContext, ToolRegistry, verify, verify_result
from kkb_agent.agent.verifier import Binding, recheck_against_store
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

FULLY_TYPED = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    " ORDER BY o.period_end"
)


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


@pytest.fixture
def result(house):
    """The real thing: what the lakehouse tool actually produces for a join."""
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
    outcome = registry.get("lakehouse").run(
        LakehouseArguments(sql=FULLY_TYPED, purpose="konut kredisi serisi"),
        ExecutionContext(question="konut kredisi stoğu"),
    )
    return outcome.output.result


def quoted(verdict, text: str):
    """The verdict for one written figure.

    Selecting by index is a trap here: "Haziran 2026'da 801.438 milyon TL."
    contains two numbers, and the year comes first.
    """
    for item in verdict.numbers:
        if item.number.text == text:
            return item
    raise AssertionError(f"{text!r} was not among {[i.number.text for i in verdict.numbers]}")


def synthetic(**overrides) -> AnalyticalResult:
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
                period=Period(
                    start=date(2026, 6, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY
                ),
            )
        ],
        "samples": SampleCounts(used=3),
        "evidence": ResultEvidence(input_refs=["silver_observations"]),
    }
    fields.update(overrides)
    return AnalyticalResult(**fields)


class TestAClaimBindsToThisResult:
    def test_a_correct_answer_is_accepted(self, result, house):
        verdict = verify_result(
            "Haziran 2026'da konut kredisi stoğu 801.438 milyon TL.", result, house.connection
        )

        assert verdict.accepted, verdict.rejected
        figure = quoted(verdict, "801.438")
        assert figure.binding is Binding.RESULT
        assert figure.value_label == "bddk:konut"

    def test_the_verdict_names_the_result_it_bound_to(self, result, house):
        verdict = verify_result("Değer 801.438 milyon TL.", result, house.connection)
        assert quoted(verdict, "801.438").result_id == result.result_id

    def test_the_lineage_node_travels_with_the_binding(self, result, house):
        verdict = verify_result("Değer 801.438 milyon TL.", result, house.connection)

        assert verdict.lineage_nodes()
        assert verdict.lineage_nodes()[0] == result.evidence.lineage_node

    def test_a_number_from_another_series_is_not_accepted(self, result, house):
        # 999.999 exists nowhere; the point is that no store-wide search saves it.
        verdict = verify_result("Değer 999.999 milyon TL.", result, house.connection)

        assert not verdict.accepted
        assert quoted(verdict, "999.999").binding is Binding.UNBOUND
        assert any("does not match any value in these results" in r for r in verdict.rejected)

    def test_a_stored_value_outside_this_result_is_still_refused(self, house):
        # 767314 is genuinely in the lakehouse, so the old `verify` accepts it.
        # It is not in a result restricted to June, so this must not.
        june_only = synthetic()
        answer = "Haziran 2026'da 767.314 milyon TL."

        assert verify(answer, house.connection).accepted
        assert not verify_result(answer, june_only, house.connection).accepted

    def test_a_caller_justified_number_is_context_not_data(self, result, house):
        verdict = verify_result("Yüzde 5 artış oldu.", result, house.connection, allowed=[5.0])
        assert quoted(verdict, "5").binding is Binding.CONTEXT

    def test_a_year_is_recognised_without_a_value(self, result, house):
        verdict = verify_result("2026 yılında 801.438 milyon TL.", result, house.connection)
        assert verdict.accepted, verdict.rejected


class TestScaleIsCheckedAgainstTheData:
    def test_a_thousand_scaled_value_quoted_as_million_is_rejected(self, house):
        # The FinTürk trap: BDDK publishes million TRY and FinTürk thousand.
        # The value is found, and the sentence is still wrong by 1000x.
        finturk = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=801438.0,
                    unit="TRY",
                    scale=Scale.THOUSAND,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        verdict = verify_result("Haziran 2026'da 801.438 milyon TL.", finturk, house.connection)

        assert not verdict.accepted
        figure = quoted(verdict, "801.438")
        assert figure.binding is Binding.RESULT
        assert not figure.supported
        assert any("recorded as thousand" in fault for fault in figure.faults)

    def test_the_matching_scale_word_is_accepted(self, house):
        assert verify_result(
            "Haziran 2026'da 801.438 milyon TL.", synthetic(), house.connection
        ).accepted

    def test_asserting_a_scale_the_result_never_established_is_rejected(self, house):
        unscaled = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=801438.0,
                    unit="TRY",
                    scale=Scale.UNKNOWN,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ],
            unresolved_semantics=["scale is unresolved"],
        )
        verdict = verify_result("Haziran 2026'da 801.438 milyon TL.", unscaled, house.connection)

        assert not verdict.accepted
        assert any("never established a scale" in f for f in quoted(verdict, "801.438").faults)

    def test_no_scale_word_means_no_scale_check(self, house):
        assert verify_result("Değer 801.438 TL.", synthetic(), house.connection).accepted

    def test_a_suffixed_scale_word_is_skipped_rather_than_guessed(self, house):
        # Failing to check is recoverable; wrongly rejecting a correct answer
        # gets the verifier switched off. "milyonu" is not matched.
        assert verify_result("Toplam 801.438 milyonu aştı.", synthetic(), house.connection).accepted


class TestThePeriodIsCheckedAgainstTheSentence:
    def test_a_figure_attributed_to_the_wrong_year_is_rejected(self, house):
        verdict = verify_result(
            "2023'te konut kredisi 801.438 milyon TL.", synthetic(), house.connection
        )

        assert not verdict.accepted
        assert any("attributed to" in fault for fault in quoted(verdict, "801.438").faults)

    def test_a_range_that_includes_the_period_is_accepted(self, house):
        # "2021-2026 arasında" mentions years the value does not cover, but one
        # of them does; a sentence may name a range beside its own figure.
        assert verify_result(
            "2021-2026 arasında en yüksek değer 801.438 milyon TL.",
            synthetic(),
            house.connection,
        ).accepted

    def test_a_year_in_a_neighbouring_sentence_does_not_reject(self, house):
        # The window is the sentence, not a character count, precisely so this
        # does not become a false rejection.
        answer = "Seri 2019'da başlıyor. Haziran 2026'da 801.438 milyon TL."
        assert verify_result(answer, synthetic(), house.connection).accepted

    def test_a_value_without_a_period_is_not_period_checked(self, house):
        undated = synthetic(
            values=[
                ResultValue(label="bddk:konut", value=801438.0, unit="TRY", scale=Scale.MILLION)
            ]
        )
        assert verify_result("2023'te 801.438 milyon TL.", undated, house.connection).accepted


class TestAResultThatEstablishedNothing:
    @pytest.mark.parametrize(
        "status", [ResultStatus.ABSTAINED, ResultStatus.INSUFFICIENT, ResultStatus.UNDEFINED]
    )
    def test_no_number_may_be_quoted_from_it(self, house, status):
        empty = synthetic(status=status, values=[], reason="nothing established")
        verdict = verify_result("Değer 801.438 milyon TL.", empty, house.connection)

        assert not verdict.accepted
        assert any(status.value in reason for reason in verdict.rejected)

    def test_the_reason_reaches_the_verdict(self, house):
        empty = synthetic(
            status=ResultStatus.ABSTAINED,
            values=[],
            reason="The query reads no lakehouse table",
        )
        verdict = verify_result("Sonuç yok.", empty, house.connection)
        assert any("reads no lakehouse table" in reason for reason in verdict.rejected)

    def test_an_abstained_result_rejects_even_an_answer_with_no_numbers(self, house):
        empty = synthetic(status=ResultStatus.ABSTAINED, values=[], reason="no source")
        assert not verify_result("Bir sonuç üretilemedi.", empty, house.connection).accepted

    def test_a_sample_floor_is_enforced_when_the_caller_states_one(self, house):
        verdict = verify_result(
            "Değer 801.438 milyon TL.", synthetic(), house.connection, minimum_samples=24
        )

        assert not verdict.accepted
        assert any("below the 24 this claim requires" in r for r in verdict.rejected)

    def test_no_floor_means_no_sample_check(self, house):
        assert verify_result("Değer 801.438 milyon TL.", synthetic(), house.connection).accepted

    def test_unresolved_semantics_reach_the_stated_limitations(self, house):
        unresolved = synthetic(unresolved_semantics=["unit is unresolved"])
        verdict = verify_result("Değer 801.438.", unresolved, house.connection)
        assert any("unresolved semantics" in item for item in verdict.limitations)


class TestPreservedInputReferencesAreResolved:
    def test_a_real_result_resolves_its_references(self, result, house):
        assert verify_result("Değer 801.438 milyon TL.", result, house.connection).accepted

    def test_an_input_reference_pointing_at_nothing_is_rejected(self, house):
        invented = synthetic(evidence=ResultEvidence(input_refs=["silver_invented"]))
        verdict = verify_result("Değer 801.438 milyon TL.", invented, house.connection)

        assert not verdict.accepted
        assert any("resolves to no table and no lineage node" in r for r in verdict.rejected)

    def test_a_lineage_node_pointing_at_nothing_is_rejected(self, house):
        dangling = synthetic(
            evidence=ResultEvidence(
                input_refs=["silver_observations"], lineage_node="node-that-never-existed"
            )
        )
        verdict = verify_result("Değer 801.438 milyon TL.", dangling, house.connection)

        assert not verdict.accepted
        assert any("referenced but not stored" in r for r in verdict.rejected)

    def test_a_lineage_node_id_is_an_acceptable_input_reference(self, result, house):
        node = result.evidence.lineage_node
        by_node = synthetic(evidence=ResultEvidence(input_refs=[node]))
        assert verify_result("Değer 801.438 milyon TL.", by_node, house.connection).accepted


class TestTheSecondPathRecheck:
    def test_a_result_agreeing_with_the_store_has_no_faults(self, result, house):
        assert recheck_against_store(result, house.connection) == ()

    def test_an_altered_value_is_caught_by_identity_not_magnitude(self, house):
        # The lookup is keyed on series and period, so this cannot be satisfied
        # by some other row that happens to hold the altered figure.
        tampered = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=850000.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        faults = recheck_against_store(tampered, house.connection)

        assert faults
        assert "stored as 801438.0" in faults[0]

    def test_a_wrong_period_is_caught(self, house):
        # April's value reported against June: both figures are real, and the
        # pairing is not.
        misdated = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=767314.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        assert recheck_against_store(misdated, house.connection)

    def test_a_tampered_result_fails_the_whole_verdict(self, house):
        tampered = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=850000.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        verdict = verify_result("Haziran 2026'da 850.000 milyon TL.", tampered, house.connection)
        assert not verdict.accepted

    def test_the_recheck_never_claims_to_be_an_independent_derivation(self, result, house):
        # It reads the same store the result came from. Saying so is the
        # difference between evidence and the appearance of evidence.
        verdict = verify_result("Değer 801.438 milyon TL.", result, house.connection)
        assert any("not an independent derivation" in item for item in verdict.limitations)

    def test_an_unidentifiable_aggregate_is_skipped_not_guessed(self, house):
        aggregate = synthetic(
            values=[
                ResultValue(
                    label="value",
                    value=801438.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        assert recheck_against_store(aggregate, house.connection) == ()


class TestWithoutADatabase:
    def test_the_missing_recheck_is_stated_rather_than_skipped_silently(self):
        verdict = verify_result("Değer 801.438 milyon TL.", synthetic())

        assert verdict.accepted
        assert any("No store recheck was run" in item for item in verdict.limitations)

    def test_binding_and_scale_checks_still_run(self):
        wrong_scale = synthetic(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=801438.0,
                    unit="TRY",
                    scale=Scale.THOUSAND,
                    period=Period(start=date(2026, 6, 1), end=date(2026, 6, 30)),
                )
            ]
        )
        assert not verify_result("Haziran 2026'da 801.438 milyon TL.", wrong_scale).accepted

    def test_the_limitations_never_claim_more_than_was_checked(self):
        verdict = verify_result("Değer 801.438 milyon TL.", synthetic())
        assert any("No external cross-check" in item for item in verdict.limitations)


class TestTheOlderGateStillWorks:
    def test_verify_is_unchanged_for_its_own_callers(self, house):
        # M8-06/07 adds a stronger gate beside the old one rather than
        # redefining it; the end-to-end chain still depends on this behaviour.
        assert verify("Haziran 2026'da 801.438 milyon TL.", house.connection).accepted
        assert not verify("Değer 999.999 milyon TL.", house.connection).accepted
