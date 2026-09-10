"""M6-07..10: association, lag, and the things that make both misleading.

The arithmetic is the easy half. What these tests are really about:

- two independent series that both trend correlate near 1, and the result has
  to say so (M6-10);
- the lag sign has exactly one meaning, and getting it backwards inverts the
  whole reading (M6-09);
- a constant series has no correlation, not a zero one (M6-08);
- nothing this module produces may reach an answer without its limitations
  attached (DEC-120), which the M6-01 contract enforces by refusing to
  construct such a result at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from math import exp

import pytest

from kkb_agent.agent import ExecutionContext, ToolRegistry, ToolStatus
from kkb_agent.analytics import DEFAULT_MINIMUM_PAIRS, LAG_CAP, associate, lagged_association
from kkb_agent.analytics.association import BASE_LIMITATIONS
from kkb_agent.core import (
    DIMENSIONLESS,
    Aggregation,
    CumulativeKind,
    Frequency,
    ResultKind,
    ResultStatus,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import CausalityArguments, make_causality_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)

MONTHLY_STOCK = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
MONTHLY_RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)
QUARTERLY = SeriesSemantics(
    unit="TRY",
    scale=Scale.THOUSAND,
    frequency=Frequency.QUARTERLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)


def _month_end(year: int, month: int) -> date:
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first_of_next - timedelta(days=1)


def series(values, first: date = date(2022, 1, 31)) -> list[Observation]:
    out: list[Observation] = []
    year, month = first.year, first.month
    for value in values:
        out.append(Observation(date(year, month, 1), _month_end(year, month), value))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


#: Thirty-six months. `WAVES` and `ECHO` share a shape; `ECHO` repeats it two
#: months later, so the lag search has a right answer to find.
WAVES = series([100 + 20 * (step % 6) - 10 * ((step // 6) % 2) for step in range(36)])
ECHO = series([100 + 20 * ((step - 2) % 6) - 10 * (((step - 2) // 6) % 2) for step in range(36)])

#: Two series that share nothing but a direction. Independent slopes, tiny and
#: differently-shaped wiggles: the textbook spurious pair.
RISING_A = series([100 + 10 * step + (step % 5) for step in range(36)])
RISING_B = series([500 + 3 * step - (step % 7) for step in range(36)])


def pair(left=WAVES, right=ECHO, left_sem=MONTHLY_STOCK, right_sem=MONTHLY_RATE, **kwargs):
    return associate(
        left, left_sem, right, right_sem, left_id="bddk:konut", right_id="evds:faiz", **kwargs
    )


def lagged(left=WAVES, right=ECHO, left_sem=MONTHLY_STOCK, right_sem=MONTHLY_RATE, **kwargs):
    return lagged_association(
        left, left_sem, right, right_sem, left_id="bddk:konut", right_id="evds:faiz", **kwargs
    )


class TestAssociation:
    def test_a_perfect_pairing_is_one(self):
        same = series([float(step) for step in range(30)])
        result = associate(same, MONTHLY_STOCK, same, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.status is ResultStatus.COMPUTED
        assert result.kind is ResultKind.ASSOCIATION
        assert result.values[0].value == pytest.approx(1.0)

    def test_an_exact_inversion_is_minus_one(self):
        up = series([float(step) for step in range(30)])
        down = series([float(-step) for step in range(30)])
        result = associate(up, MONTHLY_STOCK, down, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.values[0].value == pytest.approx(-1.0)

    def test_the_correlation_is_dimensionless_not_unknown(self):
        value = pair().values[0]

        assert value.unit == DIMENSIONLESS
        assert value.scale is Scale.ONE
        assert pair().unresolved_semantics == []

    def test_a_rank_correlation_is_reported_beside_the_linear_one(self):
        labels = [value.label for value in pair().values]
        assert any("rank correlation" in label for label in labels)

    def test_the_sample_count_and_missing_policy_are_recorded(self):
        result = pair()

        assert result.samples.used == 36
        assert "never filled" in result.parameters["missing_value_policy"]

    def test_the_limitations_are_attached_to_every_result(self):
        # DEC-120, enforced by the M6-01 contract: a relational result cannot
        # even be constructed without them.
        assert set(BASE_LIMITATIONS).issubset(set(pair().limitations))
        assert any("not causation" in item for item in pair().limitations)


class TestAlignmentAndMissingValues:
    def test_only_periods_both_series_published_are_paired(self):
        left = series([float(step) for step in range(30)])
        right = series([None if step == 5 else float(step) for step in range(30)])
        result = associate(left, MONTHLY_STOCK, right, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.samples.used == 29
        assert result.samples.missing == 1

    def test_a_dropped_period_is_reported_not_filled(self):
        left = series([float(step) for step in range(30)])
        right = series([None if step == 5 else float(step) for step in range(30)])
        result = associate(left, MONTHLY_STOCK, right, MONTHLY_STOCK, left_id="a", right_id="b")

        assert any("never filled to make a pair" in w for w in result.warnings)

    def test_a_period_only_one_series_has_is_dropped(self):
        left = series([float(step) for step in range(30)])
        right = series([float(step) for step in range(30)], first=date(2022, 3, 31))
        result = associate(left, MONTHLY_STOCK, right, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.samples.used == 28

    def test_different_frequencies_are_refused_rather_than_resampled(self):
        # Choosing how to resample is a semantic decision with a right answer
        # per series; making it silently here is how a number stops meaning
        # what its label says.
        result = pair(right_sem=QUARTERLY)

        assert result.status is ResultStatus.ABSTAINED
        assert "different frequencies" in result.reason

    def test_an_unresolved_series_is_refused(self):
        unknown = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.UNKNOWN,
            cumulative=CumulativeKind.UNKNOWN,
        )
        result = pair(right_sem=unknown)

        assert result.status is ResultStatus.ABSTAINED
        assert result.unresolved_semantics


class TestRefusals:
    def test_too_few_pairs_is_insufficient(self):
        short = series([float(step) for step in range(10)])
        result = associate(short, MONTHLY_STOCK, short, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert str(DEFAULT_MINIMUM_PAIRS) in result.reason
        assert "noise with a decimal point" in result.reason

    def test_a_constant_series_is_undefined_not_zero(self):
        flat = series([5.0] * 30)
        moving = series([float(step) for step in range(30)])
        result = associate(flat, MONTHLY_STOCK, moving, MONTHLY_STOCK, left_id="a", right_id="b")

        assert result.status is ResultStatus.UNDEFINED
        assert "does not vary" in result.reason

    def test_an_undefined_result_carries_no_number(self):
        flat = series([5.0] * 30)
        moving = series([float(step) for step in range(30)])
        result = associate(flat, MONTHLY_STOCK, moving, MONTHLY_STOCK, left_id="a", right_id="b")
        assert result.values == []


class TestSpuriousCorrelation:
    def test_two_independent_trending_series_still_correlate(self):
        # The premise of the warning: nothing links these but a direction.
        result = associate(
            RISING_A, MONTHLY_STOCK, RISING_B, MONTHLY_STOCK, left_id="a", right_id="b"
        )
        assert result.values[0].value > 0.99

    def test_and_the_result_says_the_trend_may_be_all_of_it(self):
        result = associate(
            RISING_A, MONTHLY_STOCK, RISING_B, MONTHLY_STOCK, left_id="a", right_id="b"
        )

        assert any("correlate whatever they measure" in w for w in result.warnings)
        assert any("period-over-period changes" in w for w in result.warnings)

    def test_it_does_not_silently_difference_them(self):
        # Differencing would answer a question nobody asked, and the reported
        # number would no longer be the one the label describes.
        result = associate(
            RISING_A, MONTHLY_STOCK, RISING_B, MONTHLY_STOCK, left_id="a", right_id="b"
        )
        assert result.values[0].value > 0.99

    def test_a_non_trending_pair_gets_no_trend_warning(self):
        assert not any("correlate whatever they measure" in w for w in pair().warnings)

    def test_a_non_linear_relationship_is_flagged(self):
        # Exponential growth against a straight line: Pearson 0.77, Spearman
        # 1.00. This is not a contrived shape here — nominal Turkish series in
        # the brief's window grow close to exponentially.
        straight = series([float(step) for step in range(30)])
        curved = series([exp(step / 4) for step in range(30)])
        result = associate(
            straight, MONTHLY_STOCK, curved, MONTHLY_STOCK, left_id="a", right_id="b"
        )

        assert any("not linear" in w for w in result.warnings)
        assert any("rank figure is the more robust" in w for w in result.warnings)

    def test_a_mildly_curved_relationship_is_not_flagged(self):
        # x squared gives a gap of 0.03. Flagging that would train a reader to
        # ignore the warning, which is worse than not having it.
        straight = series([float(step) for step in range(30)])
        curved = series([float(step) ** 2 for step in range(30)])
        result = associate(
            straight, MONTHLY_STOCK, curved, MONTHLY_STOCK, left_id="a", right_id="b"
        )

        assert not any("not linear" in w for w in result.warnings)


class TestLag:
    def test_it_finds_the_offset_the_data_was_built_with(self):
        # ECHO repeats WAVES two months later, so WAVES leads by 2.
        result = lagged(max_lag=6)

        assert result.status is ResultStatus.COMPUTED
        assert result.kind is ResultKind.LAG
        assert result.parameters["strongest_lag"] == 2

    def test_the_sign_convention_is_spelled_out_in_words(self):
        # Reading this backwards inverts the entire finding, so it is not left
        # to a convention the reader has to remember.
        result = lagged(max_lag=6)

        assert any("moves first by 2 period(s)" in w for w in result.warnings)
        assert "positive k means bddk:konut leads" in result.parameters["lag_sign"]

    def test_swapping_the_series_inverts_the_reported_offset(self):
        forward = lagged(max_lag=6).parameters["strongest_lag"]
        backward = lagged_association(
            ECHO,
            MONTHLY_RATE,
            WAVES,
            MONTHLY_STOCK,
            left_id="evds:faiz",
            right_id="bddk:konut",
            max_lag=6,
        ).parameters["strongest_lag"]

        assert forward == -backward

    def test_every_offset_reports_its_own_sample_count(self):
        # A lag of k discards k overlapping observations, and the counts have
        # to show it or the far offsets look as well-evidenced as the near ones.
        result = lagged(max_lag=6)
        by_lag = {value.lag: value.samples.used for value in result.values}

        assert by_lag[0] == 36
        assert by_lag[6] == 30
        assert by_lag[-6] == 30

    def test_the_search_itself_is_declared_as_inflating_the_result(self):
        result = lagged(max_lag=6)

        assert any("inflated by the search itself" in w for w in result.warnings)
        assert result.parameters["offsets_examined"] == len(result.values)

    def test_a_window_beyond_the_cap_is_refused(self):
        result = lagged(max_lag=LAG_CAP + 1)

        assert result.status is ResultStatus.ABSTAINED
        assert "outside the permitted" in result.reason

    def test_a_zero_window_is_just_the_association(self):
        result = lagged(max_lag=0)

        assert len(result.values) == 1
        assert result.values[0].lag == 0

    def test_lag_carries_the_direction_limitation_too(self):
        assert any("not evidence of direction" in item for item in lagged().limitations)

    def test_too_short_for_any_offset_is_insufficient(self):
        short = series([float(step) for step in range(10)])
        result = lagged_association(
            short, MONTHLY_STOCK, short, MONTHLY_STOCK, left_id="a", right_id="b", max_lag=3
        )

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"x": 1}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque"),
            media_type="application/json",
            recorded_at=NOW,
        )
        for series_id, semantics, observations in (
            ("bddk:konut", MONTHLY_STOCK, WAVES),
            ("evds:faiz", MONTHLY_RATE, ECHO),
        ):
            lake.register_series(
                series_id, title=series_id, semantics=semantics, artifact_id=artifact.artifact_id
            )
            lake.append_observations(series_id, observations)
        yield lake


class TestTheTool:
    def registry(self, house, lineage=True):
        registry = ToolRegistry()
        registry.register(
            make_causality_tool(house.connection, lineage=house.lineage if lineage else None)
        )
        return registry

    def run(self, house, lineage=True, **kwargs):
        kwargs.setdefault("left_series_id", "bddk:konut")
        kwargs.setdefault("right_series_id", "evds:faiz")
        return (
            self.registry(house, lineage)
            .get("causality")
            .run(CausalityArguments(**kwargs), ExecutionContext(question="ilişki var mı"))
        )

    def test_association_runs_through_the_lakehouse(self, house):
        outcome = self.run(house, operation="association")

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.kind is ResultKind.ASSOCIATION
        assert outcome.output.status is ResultStatus.COMPUTED

    def test_lag_finds_the_built_in_offset(self, house):
        outcome = self.run(house, operation="lag", max_lag=6)
        assert outcome.output.parameters["strongest_lag"] == 2

    def test_the_limitations_reach_the_model_as_warnings(self, house):
        # A model that never sees the caveat will write around it.
        warnings = self.run(house, operation="association").warnings
        assert any("not causation" in w for w in warnings)

    def test_the_description_refuses_the_causal_reading(self, house):
        described = self.registry(house).descriptions()[0]["description"]

        assert "ASSOCIATION ONLY" in described
        assert "Granger testing is not available yet" in described

    def test_granger_is_not_in_the_schema(self, house):
        from kkb_agent.agent import ArgumentsRejected

        with pytest.raises(ArgumentsRejected):
            self.registry(house).get("causality").parse(
                {
                    "operation": "granger",
                    "left_series_id": "bddk:konut",
                    "right_series_id": "evds:faiz",
                }
            )

    def test_a_lag_beyond_the_cap_is_refused_by_the_schema(self, house):
        from kkb_agent.agent import ArgumentsRejected

        with pytest.raises(ArgumentsRejected):
            self.registry(house).get("causality").parse(
                {
                    "operation": "lag",
                    "left_series_id": "bddk:konut",
                    "right_series_id": "evds:faiz",
                    "max_lag": LAG_CAP + 1,
                }
            )

    def test_a_computed_result_records_lineage_marked_as_association(self, house):
        outcome = self.run(house, operation="association")

        assert outcome.evidence is not None
        stored = house.connection.execute(
            "SELECT label, attributes FROM lineage_nodes WHERE node_id = ?", [outcome.evidence]
        ).fetchone()
        assert stored[0] == "causality_association"
        assert "association only" in stored[1]

    def test_an_unknown_series_fails(self, house):
        outcome = self.run(house, operation="association", right_series_id="evds:hayalet")

        assert outcome.status is ToolStatus.FAILURE
        assert outcome.error_category == "series_unknown"

    def test_a_refusal_stays_successful_and_records_no_lineage(self, house):
        outcome = self.run(house, operation="association", start=date(2024, 9, 30))

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.status is ResultStatus.INSUFFICIENT
        assert outcome.evidence is None
