"""M6-01: what a result must state before anyone is allowed to use it.

Most of these are refusals. The contract's job is to make the shapes that
would produce a confidently wrong answer unrepresentable — a number with no
unit, a correlation with no limits, an "insufficient" verdict that still
carries a figure — so those are the cases worth the most tests.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
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
    TransformationRecord,
    WeeklyAnchor,
)

JANUARY = Period(start=date(2026, 1, 1), end=date(2026, 1, 31), frequency=Frequency.MONTHLY)


def amount(value: float = 801_438.0, **overrides: object) -> ResultValue:
    """A fully specified monetary value; overrides remove what a test attacks."""
    fields: dict[str, object] = {
        "label": "Tüketici Kredileri - Konut",
        "value": value,
        "unit": "TRY",
        "scale": Scale.MILLION,
        "measure": StockFlow.STOCK,
        "period": JANUARY,
    }
    fields.update(overrides)
    return ResultValue(**fields)  # type: ignore[arg-type]


def computed(**overrides: object) -> AnalyticalResult:
    fields: dict[str, object] = {
        "result_id": "result-1",
        "kind": ResultKind.LEVEL,
        "status": ResultStatus.COMPUTED,
        "tool": "lakehouse",
        "values": [amount()],
        "coverage": JANUARY,
        "samples": SampleCounts(used=66),
        "evidence": ResultEvidence(input_refs=["lineage-node-1"]),
    }
    fields.update(overrides)
    return AnalyticalResult(**fields)  # type: ignore[arg-type]


class TestAPeriodIsExplicit:
    def test_a_period_cannot_end_before_it_starts(self) -> None:
        with pytest.raises(ValidationError, match="ends on or after"):
            Period(start=date(2026, 2, 1), end=date(2026, 1, 31))

    def test_a_single_day_period_is_valid(self) -> None:
        day = Period(start=date(2026, 1, 5), end=date(2026, 1, 5), frequency=Frequency.DAILY)
        assert day.start == day.end

    def test_a_weekly_period_must_name_its_anchor(self) -> None:
        # EVDS anchors most weekly series to Friday and at least one to
        # Wednesday, so "weekly" alone does not say which days are covered.
        with pytest.raises(ValidationError, match="must name the weekday"):
            Period(start=date(2026, 1, 5), end=date(2026, 1, 9), frequency=Frequency.WEEKLY)

    def test_the_anchor_must_match_the_day_the_period_ends_on(self) -> None:
        with pytest.raises(ValidationError, match="must end on that weekday"):
            Period(
                start=date(2026, 1, 5),
                end=date(2026, 1, 8),  # a Thursday
                frequency=Frequency.WEEKLY,
                weekly_anchor=WeeklyAnchor.FRIDAY,
            )

    def test_a_friday_anchored_week_is_accepted(self) -> None:
        week = Period(
            start=date(2026, 1, 3),
            end=date(2026, 1, 9),  # a Friday
            frequency=Frequency.WEEKLY,
            weekly_anchor=WeeklyAnchor.FRIDAY,
        )
        assert week.weekly_anchor is WeeklyAnchor.FRIDAY

    def test_a_non_weekly_period_may_not_carry_an_anchor(self) -> None:
        with pytest.raises(ValidationError, match="Only a weekly period"):
            Period(
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                frequency=Frequency.MONTHLY,
                weekly_anchor=WeeklyAnchor.FRIDAY,
            )


class TestSampleCountsSurviveIntoTheAnswer:
    def test_counts_are_separate_and_add_up_to_what_was_considered(self) -> None:
        counts = SampleCounts(used=60, missing=4, excluded=2)
        assert counts.considered == 66

    def test_a_negative_count_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            SampleCounts(used=-1)

    def test_a_count_is_not_coerced_from_text(self) -> None:
        with pytest.raises(ValidationError):
            SampleCounts(used="60")  # type: ignore[arg-type]

    def test_a_sample_below_its_own_stated_floor_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="below the stated minimum"):
            SampleCounts(used=3, minimum_required=24)

    def test_zero_used_with_a_floor_is_allowed_so_insufficient_can_state_it(self) -> None:
        # An INSUFFICIENT result still has to report the floor it failed.
        counts = SampleCounts(used=0, missing=24, minimum_required=24)
        assert counts.minimum_required == 24


class TestAValueStatesItsUnit:
    def test_an_unknown_unit_is_not_the_same_as_no_unit(self) -> None:
        unknown = amount(unit=None)
        ratio = amount(unit=DIMENSIONLESS, scale=Scale.ONE)
        assert unknown.semantics_are_unresolved
        assert not ratio.semantics_are_unresolved

    def test_an_unknown_scale_leaves_semantics_unresolved(self) -> None:
        # BDDK publishes in million TRY and FinTürk in thousand; a value
        # without a scale is a silent 1000x error, not a cosmetic gap.
        assert amount(scale=Scale.UNKNOWN).semantics_are_unresolved

    def test_a_value_is_not_coerced_from_a_string(self) -> None:
        # "1.234" is 1234 in a Turkish answer and 1.234 to Python. Refuse it
        # here rather than pick one.
        with pytest.raises(ValidationError):
            amount(value="1.234")

    def test_a_boolean_is_not_a_measurement(self) -> None:
        with pytest.raises(ValidationError):
            amount(value=True)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_a_non_finite_value_is_refused(self, bad: float) -> None:
        with pytest.raises(ValidationError):
            amount(value=bad)

    def test_an_integer_measurement_is_accepted_as_a_float(self) -> None:
        assert amount(value=42).value == pytest.approx(42.0)

    def test_a_blank_label_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            amount(label="   ")


class TestAComputedResultCarriesItsEvidence:
    def test_a_fully_specified_result_validates(self) -> None:
        assert computed().status is ResultStatus.COMPUTED

    def test_a_computed_result_needs_at_least_one_value(self) -> None:
        with pytest.raises(ValidationError, match="at least one value"):
            computed(values=[])

    def test_a_computed_result_must_name_its_inputs(self) -> None:
        with pytest.raises(ValidationError, match="name the inputs"):
            computed(evidence=None)

    def test_evidence_without_an_input_reference_is_refused(self) -> None:
        # A number whose inputs are unnamed cannot be verified or recomputed.
        with pytest.raises(ValidationError):
            ResultEvidence(input_refs=[])

    def test_a_computed_result_cannot_rest_on_zero_observations(self) -> None:
        with pytest.raises(ValidationError, match="zero observations"):
            computed(samples=SampleCounts(used=0, missing=66))

    def test_an_unresolved_unit_must_be_declared_on_the_result(self) -> None:
        with pytest.raises(ValidationError, match="unknown unit or scale"):
            computed(values=[amount(unit=None)])

    def test_declaring_the_unresolved_semantics_makes_it_representable(self) -> None:
        # Unknown semantics stay explicit rather than blocking the analysis.
        result = computed(
            values=[amount(unit=None)],
            unresolved_semantics=["Bulletin caption does not declare a unit"],
        )
        assert result.unresolved_semantics

    def test_a_dimensionless_value_needs_no_unresolved_declaration(self) -> None:
        result = computed(values=[amount(value=0.82, unit=DIMENSIONLESS, scale=Scale.ONE)])
        assert not result.unresolved_semantics

    def test_extra_fields_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            computed(confidence=0.9)


class TestARelationshipStatesItsLimits:
    @pytest.mark.parametrize("kind", [ResultKind.ASSOCIATION, ResultKind.LAG, ResultKind.CAUSALITY])
    def test_a_relational_result_without_limitations_is_refused(self, kind: ResultKind) -> None:
        # DEC-120: association may be reported with mandatory stated limits.
        # A correlation that loses them reads as a cause by the next slide.
        with pytest.raises(ValidationError, match="state its limitations"):
            computed(kind=kind, values=[amount(value=0.71, unit=DIMENSIONLESS, scale=Scale.ONE)])

    def test_a_causality_result_with_its_limits_validates(
        self,
    ) -> None:
        result = computed(
            kind=ResultKind.CAUSALITY,
            method="granger",
            values=[amount(value=0.03, unit=DIMENSIONLESS, scale=Scale.ONE, label="p-value")],
            parameters={"max_lag": 6, "alpha": 0.05},
            limitations=[
                "Granger tests predictive precedence on this sample, not causation",
                "Series were not tested for a common trend",
            ],
        )
        assert result.limitations

    def test_a_measurement_kind_needs_no_limitations(self) -> None:
        assert computed(kind=ResultKind.LEVEL).limitations == []

    def test_a_lag_value_records_its_own_offset_and_sample(self) -> None:
        # Each offset is computed over a different overlap, so the count
        # belongs on the value rather than the result.
        result = computed(
            kind=ResultKind.LAG,
            values=[
                amount(
                    value=0.64,
                    unit=DIMENSIONLESS,
                    scale=Scale.ONE,
                    lag=-3,
                    samples=SampleCounts(used=57),
                    label="lead 3",
                )
            ],
            limitations=["Association only; lag order does not establish direction"],
        )
        assert result.values[0].lag == -3
        assert result.values[0].samples is not None
        assert result.values[0].samples.used == 57


class TestAnUncomputableResultCarriesNoNumber:
    @pytest.mark.parametrize(
        "status",
        [ResultStatus.INSUFFICIENT, ResultStatus.UNDEFINED, ResultStatus.ABSTAINED],
    )
    def test_a_non_computed_result_may_not_carry_values(self, status: ResultStatus) -> None:
        with pytest.raises(ValidationError, match="carries no values"):
            computed(status=status, reason="stated", values=[amount()])

    @pytest.mark.parametrize(
        "status",
        [ResultStatus.INSUFFICIENT, ResultStatus.UNDEFINED, ResultStatus.ABSTAINED],
    )
    def test_a_non_computed_result_must_say_what_stopped_it(self, status: ResultStatus) -> None:
        with pytest.raises(ValidationError, match="say what stopped it"):
            computed(status=status, values=[])

    def test_insufficient_reports_the_floor_it_failed(self) -> None:
        result = computed(
            status=ResultStatus.INSUFFICIENT,
            values=[],
            samples=SampleCounts(used=0, missing=4, minimum_required=24),
            reason="4 of 24 required monthly observations are present",
        )
        assert result.samples is not None
        assert result.samples.minimum_required == 24

    def test_undefined_is_distinct_from_insufficient(self) -> None:
        # A constant series has plenty of data; the statistic still has none.
        result = computed(
            kind=ResultKind.ASSOCIATION,
            status=ResultStatus.UNDEFINED,
            values=[],
            samples=SampleCounts(used=60),
            reason="Correlation is undefined for a constant series",
        )
        assert result.status is ResultStatus.UNDEFINED

    def test_abstained_keeps_the_unresolved_semantics_visible(self) -> None:
        result = computed(
            status=ResultStatus.ABSTAINED,
            values=[],
            reason="Cumulative reset behaviour of the source table is unknown",
            unresolved_semantics=["cumulative", "reset_behavior"],
        )
        assert result.unresolved_semantics == ["cumulative", "reset_behavior"]

    def test_an_uncomputable_result_need_not_name_inputs(self) -> None:
        # Nothing was derived, so there is nothing to derive it from.
        assert computed(status=ResultStatus.ABSTAINED, values=[], evidence=None, reason="x")


class TestIdentityDistinguishesStaleFromRederived:
    def test_serialization_round_trips_through_json(self) -> None:
        original = computed()
        restored = AnalyticalResult.model_validate_json(original.model_dump_json())
        assert restored == original
        assert restored.digest() == original.digest()

    def test_the_digest_ignores_the_caller_chosen_id(self) -> None:
        # The same computation stored under a second name is the same result.
        renamed = computed(result_id="result-2")
        assert computed().describes_same_computation(renamed)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("values", [amount(value=801_439.0)]),
            ("samples", SampleCounts(used=65)),
            ("parameters", {"window": 12}),
            ("coverage", Period(start=date(2026, 1, 1), end=date(2026, 2, 28))),
            ("evidence", ResultEvidence(input_refs=["lineage-node-2"])),
            ("run_id", "run-9"),
            ("warnings", ["Two observations were interpolated"]),
        ],
    )
    def test_any_material_change_changes_the_digest(self, field: str, value: object) -> None:
        # This is what lets M5 reject a stale read and M8 catch an altered
        # result; a digest that ignored evidence or samples would certify both.
        assert computed().digest() != computed(**{field: value}).digest()

    def test_a_tampered_value_is_detectable_after_construction(self) -> None:
        result = computed()
        before = result.digest()
        result.values = [amount(value=999_999.0)]
        assert result.digest() != before

    def test_assignment_is_revalidated_rather_than_trusted(self) -> None:
        result = computed()
        with pytest.raises(ValidationError):
            result.status = ResultStatus.INSUFFICIENT  # values are still present

    def test_a_full_evidence_chain_survives_the_round_trip(self) -> None:
        result = computed(
            run_id="run-1",
            step_id="step-2",
            evidence=ResultEvidence(
                input_refs=["lineage-node-1", "lineage-node-2"],
                transformations=[
                    TransformationRecord(
                        operation="deflate",
                        parameters={"index": "TP.FG.J0", "base_period": "2026-01"},
                        input_refs=["lineage-node-1"],
                        output_ref="lineage-node-3",
                    )
                ],
                lineage_node="lineage-node-3",
                evidence_ids=["evidence-1"],
                sources=[
                    SourceRef(
                        source_id="bddk-monthly",
                        source_type="bulletin",
                        locator="table-4",
                    )
                ],
            ),
        )
        restored = AnalyticalResult.model_validate_json(result.model_dump_json())
        assert restored.evidence is not None
        assert restored.evidence.transformations[0].operation == "deflate"
        assert restored.digest() == result.digest()
