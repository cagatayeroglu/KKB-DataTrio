"""M6-02/03/04: change and comparison, with hand-calculated oracles.

Every expected number here was worked out by hand and is written in the test
rather than derived from the code under test, which is the only way a test of
arithmetic can fail for the right reason.

The interesting cases are not the additions. They are the refusals: a zero
base, a negative base, a gap that is not a zero, a date that was never
published, and a rate whose change is in points rather than in percent.
"""

from __future__ import annotations

from datetime import date

import pytest

from kkb_agent.analytics import (
    INDEX_POINT,
    PERCENT,
    PERCENTAGE_POINT,
    absolute_change,
    compare_periods,
    relative_change,
)
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    ResultKind,
    ResultStatus,
    Scale,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics

STOCK = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)
INDEX = SeriesSemantics(
    unit="index",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.INDEX,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
    base_year=2017,
)

APRIL, MAY, JUNE = date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30)


def months(*pairs: tuple[date, float | None]) -> list[Observation]:
    return [Observation(date(end.year, end.month, 1), end, value) for end, value in pairs]


#: Real published figures from the BDDK monthly bulletin inventory.
KONUT = months((APRIL, 767314.0), (MAY, 782918.0), (JUNE, 801438.0))


def change(observations, semantics=STOCK, *, start=APRIL, end=JUNE, **kwargs):
    return absolute_change(
        observations, semantics, start=start, end=end, series_id="bddk:konut", **kwargs
    )


def relative(observations, semantics=STOCK, *, start=APRIL, end=JUNE, **kwargs):
    return relative_change(
        observations, semantics, start=start, end=end, series_id="bddk:konut", **kwargs
    )


class TestAbsoluteChange:
    def test_the_arithmetic_is_what_it_says(self):
        # 801438 - 767314 = 34124, by hand.
        result = change(KONUT)

        assert result.status is ResultStatus.COMPUTED
        assert result.kind is ResultKind.CHANGE
        assert result.values[0].value == pytest.approx(34124.0)

    def test_a_fall_is_negative_not_absolute(self):
        result = change(KONUT, start=JUNE, end=APRIL)
        assert result.status is ResultStatus.ABSTAINED

        backwards = months((APRIL, 801438.0), (JUNE, 767314.0))
        assert change(backwards).values[0].value == pytest.approx(-34124.0)

    def test_zero_change_is_computed_not_refused(self):
        flat = months((APRIL, 500.0), (JUNE, 500.0))
        result = change(flat)

        assert result.status is ResultStatus.COMPUTED
        assert result.values[0].value == pytest.approx(0.0)

    def test_it_keeps_the_series_unit_and_scale(self):
        value = change(KONUT).values[0]

        assert value.unit == "TRY"
        assert value.scale is Scale.MILLION
        assert value.measure is StockFlow.STOCK

    def test_a_stock_change_says_it_is_not_new_lending(self):
        # The BDDK inventory found this exact trap: the housing series is an
        # outstanding balance that falls in 8 of 65 steps, so its difference is
        # net change, never disbursement.
        assert any("not new lending" in w for w in change(KONUT).warnings)

    def test_the_period_spans_both_endpoints(self):
        result = change(KONUT)

        assert result.coverage is not None
        assert result.coverage.start == date(2026, 4, 1)
        assert result.coverage.end == JUNE
        assert result.coverage.frequency is Frequency.MONTHLY

    def test_two_observations_are_reported_as_the_sample(self):
        assert change(KONUT).samples.used == 2

    def test_the_evidence_names_where_the_numbers_came_from(self):
        result = change(KONUT, lineage_node="node-1")

        assert result.evidence.input_refs == ["silver_observations"]
        assert result.evidence.lineage_node == "node-1"


class TestARateChangesInPoints:
    def test_a_rate_difference_is_in_percentage_points(self):
        # 46.75 - 40.00 = 6.75 points, which is a 16.875% rise. Calling the
        # difference "6.75 percent" is the error this exists to prevent.
        faiz = months((APRIL, 40.0), (JUNE, 46.75))
        result = absolute_change(faiz, RATE, start=APRIL, end=JUNE, series_id="evds:TP.KTF12")

        assert result.values[0].value == pytest.approx(6.75)
        assert result.values[0].unit == PERCENTAGE_POINT
        assert result.values[0].scale is Scale.ONE

    def test_the_warning_names_both_readings(self):
        faiz = months((APRIL, 40.0), (JUNE, 46.75))
        result = absolute_change(faiz, RATE, start=APRIL, end=JUNE, series_id="evds:TP.KTF12")
        assert any(PERCENTAGE_POINT in w for w in result.warnings)

    def test_the_relative_change_of_a_rate_is_the_other_number(self):
        # (46.75 - 40) / 40 = 16.875%, distinct from the 6.75 point move.
        faiz = months((APRIL, 40.0), (JUNE, 46.75))
        result = relative_change(faiz, RATE, start=APRIL, end=JUNE, series_id="evds:TP.KTF12")

        assert result.values[0].value == pytest.approx(16.875)
        assert result.values[0].unit == PERCENT
        assert any("not a change in percentage points" in w for w in result.warnings)

    def test_an_index_changes_in_index_points(self):
        endeks = months((APRIL, 200.0), (JUNE, 214.8))
        result = absolute_change(endeks, INDEX, start=APRIL, end=JUNE, series_id="evds:HFE")

        assert result.values[0].value == pytest.approx(14.8)
        assert result.values[0].unit == INDEX_POINT


class TestRelativeChangeNeedsABaseThatCarriesOne:
    def test_the_arithmetic_is_what_it_says(self):
        # 34124 / 767314 = 0.044472015..., so 4.4472015%. Checked by exact
        # decimal division rather than by calling the code under test.
        result = relative(KONUT)

        assert result.status is ResultStatus.COMPUTED
        assert result.values[0].value == pytest.approx(4.4472015, rel=1e-7)
        assert result.values[0].unit == PERCENT

    def test_a_zero_base_is_undefined_not_infinite(self):
        result = relative(months((APRIL, 0.0), (JUNE, 500.0)))

        assert result.status is ResultStatus.UNDEFINED
        assert result.values == []
        assert "base of zero" in result.reason

    def test_a_zero_base_points_at_the_absolute_change_instead(self):
        result = relative(months((APRIL, 0.0), (JUNE, 500.0)))
        assert "absolute change" in result.reason

    def test_a_negative_base_is_undefined_because_the_sign_inverts(self):
        # -100 -> -50 is an improvement that the formula reports as -50%.
        result = relative(months((APRIL, -100.0), (JUNE, -50.0)))

        assert result.status is ResultStatus.UNDEFINED
        assert "inverts its sign" in result.reason

    def test_a_negative_endpoint_over_a_positive_base_is_fine(self):
        # 100 -> -50 is a real -150%, and nothing about it is ambiguous.
        result = relative(months((APRIL, 100.0), (JUNE, -50.0)))

        assert result.status is ResultStatus.COMPUTED
        assert result.values[0].value == pytest.approx(-150.0)

    def test_no_change_is_zero_percent(self):
        result = relative(months((APRIL, 500.0), (JUNE, 500.0)))
        assert result.values[0].value == pytest.approx(0.0)


class TestSelectionIsExact:
    def test_a_date_that_was_never_published_is_refused(self):
        # Resolving to a neighbouring month would be indistinguishable in the
        # output from having compared the right one.
        result = change(KONUT, start=date(2026, 4, 15))

        assert result.status is ResultStatus.INSUFFICIENT
        assert "2026-04-15" in result.reason

    def test_the_refusal_says_what_the_series_does_publish(self):
        result = change(KONUT, start=date(2026, 1, 31))
        assert "2026-04-30..2026-06-30" in result.reason

    def test_an_empty_range_is_insufficient(self):
        result = change([])

        assert result.status is ResultStatus.INSUFFICIENT
        assert "No observations" in result.reason

    def test_a_backwards_range_is_refused(self):
        result = change(KONUT, start=JUNE, end=APRIL)

        assert result.status is ResultStatus.ABSTAINED
        assert "ends before it starts" in result.reason

    def test_the_same_period_twice_is_a_zero_change_not_an_error(self):
        result = change(KONUT, start=JUNE, end=JUNE)

        assert result.status is ResultStatus.COMPUTED
        assert result.values[0].value == pytest.approx(0.0)


class TestAGapIsNotAZero:
    def test_a_missing_endpoint_is_insufficient(self):
        gapped = months((APRIL, None), (JUNE, 801438.0))
        result = change(gapped)

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert "2026-04-30" in result.reason

    def test_the_refusal_says_a_gap_is_not_zero(self):
        result = change(months((APRIL, None), (JUNE, 801438.0)))
        assert "a gap is not zero" in result.reason

    def test_a_missing_value_is_counted_as_missing(self):
        result = change(months((APRIL, None), (JUNE, 801438.0)))

        assert result.samples.used == 0
        assert result.samples.missing == 1

    def test_both_endpoints_missing_are_both_named(self):
        result = change(months((APRIL, None), (JUNE, None)))

        assert result.samples.missing == 2
        assert "2026-04-30" in result.reason
        assert "2026-06-30" in result.reason

    def test_a_gap_between_the_endpoints_does_not_stop_the_change(self):
        # Only the endpoints are read, so an interior gap is not this
        # function's problem and must not be treated as one.
        result = change(months((APRIL, 767314.0), (MAY, None), (JUNE, 801438.0)))
        assert result.status is ResultStatus.COMPUTED


class TestSemanticsCanRefuseTheQuestion:
    def test_an_unresolved_series_abstains_rather_than_computing(self):
        unknown = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.UNKNOWN,
            cumulative=CumulativeKind.UNKNOWN,
        )
        result = change(KONUT, unknown)

        assert result.status is ResultStatus.ABSTAINED
        assert result.unresolved_semantics
        assert "meaning is unresolved" in result.reason

    @pytest.mark.parametrize("kind", [CumulativeKind.SINCE_INCEPTION, CumulativeKind.YEARLY_RESET])
    def test_a_cumulative_series_must_be_converted_first(self, kind):
        # Differencing an accumulating series measures accumulation, not
        # activity — and one BDDK bulletin contains both behaviours.
        accumulating = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.FLOW,
            cumulative=kind,
            aggregation=Aggregation.SUM,
        )
        result = change(KONUT, accumulating)

        assert result.status is ResultStatus.ABSTAINED
        assert "convert it to flow" in result.reason

    def test_a_flow_series_computes_without_the_stock_warning(self):
        flow = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.FLOW,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.SUM,
        )
        result = change(KONUT, flow)

        assert result.status is ResultStatus.COMPUTED
        assert not any("not new lending" in w for w in result.warnings)


class TestPeriodComparison:
    def test_it_reports_both_levels_and_the_move(self):
        result = compare_periods(KONUT, STOCK, start=APRIL, end=JUNE, series_id="bddk:konut")
        by_label = {value.label: value.value for value in result.values}

        assert result.kind is ResultKind.COMPARISON
        assert by_label["bddk:konut at 2026-04-30"] == pytest.approx(767314.0)
        assert by_label["bddk:konut at 2026-06-30"] == pytest.approx(801438.0)
        assert by_label["bddk:konut absolute change"] == pytest.approx(34124.0)
        assert by_label["bddk:konut relative change"] == pytest.approx(4.4472015, rel=1e-7)

    def test_the_levels_carry_their_own_periods(self):
        result = compare_periods(KONUT, STOCK, start=APRIL, end=JUNE, series_id="bddk:konut")
        first = next(v for v in result.values if v.label.endswith("2026-04-30"))

        assert first.period is not None
        assert first.period.end == APRIL

    def test_a_zero_base_leaves_the_levels_and_says_why_the_percentage_is_absent(self):
        result = compare_periods(
            months((APRIL, 0.0), (JUNE, 500.0)),
            STOCK,
            start=APRIL,
            end=JUNE,
            series_id="bddk:konut",
        )

        assert result.status is ResultStatus.COMPUTED
        assert not any("relative change" in v.label for v in result.values)
        assert any("No relative change" in w for w in result.warnings)

    def test_it_refuses_the_same_things_the_change_refuses(self):
        assert (
            compare_periods(
                months((APRIL, None), (JUNE, 1.0)),
                STOCK,
                start=APRIL,
                end=JUNE,
                series_id="bddk:konut",
            ).status
            is ResultStatus.INSUFFICIENT
        )

    def test_every_value_declares_its_semantics(self):
        result = compare_periods(KONUT, STOCK, start=APRIL, end=JUNE, series_id="bddk:konut")
        assert result.unresolved_semantics == []
        assert all(not value.semantics_are_unresolved for value in result.values)
