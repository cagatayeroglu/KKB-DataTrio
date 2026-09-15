"""M6-07..10: association, lag, and the things that make both misleading.

The arithmetic is the easy half. What these tests are really about:

- two independent series that both trend correlate near 1, and the result has
  to say so (M6-10);
- the lag sign has exactly one meaning, and getting it backwards inverts the
  whole reading (M6-09);
- a constant series has no correlation, not a zero one (M6-08);
- nothing this module produces may reach an answer without its limitations
  attached (DEC-120), which the M6-01 contract enforces by refusing to
  construct such a result at all;
- a lag counts declared calendar periods, never surviving rows, so a missing
  period cannot pull two observations into one lag pair (M6-24).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from math import exp
from statistics import correlation as reference_pearson

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
    WeeklyAnchor,
)
from kkb_agent.lakehouse import Observation, SemanticsError, SeriesSemantics, open_lakehouse
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

#: M6-24 fixtures. BASE is irregular and does not trend; FOLLOWER repeats it
#: exactly one period later (y[t] = 2 * x[t-1] + 3), so every calendar-valid
#: lag +1 pair lies on one straight line and correlates at exactly 1. A pair
#: bridged across a gap does not, which is what makes the defect visible.
BASE = [float((step * 7) % 11 + (step * 3) % 5) for step in range(36)]
FOLLOWER = [5.0] + [2 * BASE[step - 1] + 3 for step in range(1, 36)]

FRIDAY_WEEKLY = replace(MONTHLY_STOCK, frequency=Frequency.WEEKLY, anchor=WeeklyAnchor.FRIDAY)
QUARTERLY_STOCK = replace(MONTHLY_STOCK, frequency=Frequency.QUARTERLY)


def monthly(values, *, missing=(), first: date = date(2022, 1, 31)) -> list[Observation]:
    """Contiguous months from `first`, with the indices in `missing` never published."""
    return [item for index, item in enumerate(series(values, first)) if index not in missing]


def weekly(values, *, missing=(), first_friday: date = date(2024, 1, 5)) -> list[Observation]:
    out: list[Observation] = []
    for index, value in enumerate(values):
        end = first_friday + timedelta(weeks=index)
        if index not in missing:
            out.append(Observation(end - timedelta(days=6), end, value))
    return out


def quarterly(values, *, missing=(), first: date = date(2019, 3, 31)) -> list[Observation]:
    out: list[Observation] = []
    year, month = first.year, first.month
    for index, value in enumerate(values):
        if index not in missing:
            out.append(Observation(date(year, month - 2, 1), _month_end(year, month), value))
        year, month = (year + 1, 3) if month == 12 else (year, month + 3)
    return out


def daily(values, first: date = date(2024, 1, 1)) -> list[Observation]:
    return [
        Observation(first + timedelta(days=index), first + timedelta(days=index), value)
        for index, value in enumerate(values)
    ]


def calendar_pairs(left_values, right_values, lag, *, left_missing=(), right_missing=()):
    """Independent oracle: pairs exactly `lag` periods apart by integer period index.

    Deliberately shares nothing with the implementation — no dates, no spine,
    no alignment helper — so agreeing with it is evidence, not an echo.
    """
    both = {
        index
        for index in range(len(left_values))
        if index not in left_missing and index not in right_missing
    }
    return [
        (left_values[index], right_values[index + lag])
        for index in sorted(both)
        if index + lag in both
    ]


def by_lag(result) -> dict[int, int]:
    return {value.lag: value.samples.used for value in result.values}


def at_lag(result, lag: int) -> float:
    return next(value.value for value in result.values if value.lag == lag)


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


def lag_of(left_values, right_values, *, left_missing=(), right_missing=(), **kwargs):
    return lagged_association(
        monthly(left_values, missing=left_missing),
        MONTHLY_STOCK,
        monthly(right_values, missing=right_missing),
        MONTHLY_STOCK,
        left_id="a",
        right_id="b",
        **kwargs,
    )


class TestCalendarValidLag:
    """M6-24: a lag of k is k declared calendar periods, never k surviving rows."""

    def test_the_reported_reproduction_no_longer_bridges_the_missing_month(self):
        # The case that exposed the defect: March 2024 missing on one side.
        # Positional shifting paired February with April and reported
        # {-2: 21, -1: 22, 0: 23, 1: 22, 2: 21}. Only pairs whose partner
        # month both series published survive.
        january = date(2024, 1, 31)
        left = monthly([float(step * (step % 5)) for step in range(24)], first=january)
        right = monthly(
            [float((step % 7) * 3 + step) for step in range(24)], missing={2}, first=january
        )
        result = lagged_association(
            left,
            MONTHLY_STOCK,
            right,
            MONTHLY_STOCK,
            left_id="a",
            right_id="b",
            max_lag=2,
            minimum_pairs=12,
        )

        assert date(2024, 3, 31) not in {item.period_end for item in right}
        assert result.status is ResultStatus.COMPUTED
        assert by_lag(result) == {-2: 20, -1: 21, 0: 23, 1: 21, 2: 20}

    def test_contiguous_lag_plus_one(self):
        result = lag_of(BASE, FOLLOWER, max_lag=3)

        assert result.parameters["strongest_lag"] == 1
        assert at_lag(result, 1) == pytest.approx(1.0)
        assert by_lag(result)[1] == 35

    def test_contiguous_lag_minus_one(self):
        result = lag_of(FOLLOWER, BASE, max_lag=3)

        assert result.parameters["strongest_lag"] == -1
        assert at_lag(result, -1) == pytest.approx(1.0)
        assert by_lag(result)[-1] == 35

    def test_one_missing_interior_month_is_not_bridged_by_a_positive_lag(self):
        # Month 10 of FOLLOWER never published. Bridging would pair x[9] with
        # y[11] = 2 * x[10] + 3, which is off the line, so anything short of an
        # exact 1 means a gap was crossed.
        result = lag_of(BASE, FOLLOWER, right_missing={10}, max_lag=3)
        expected = calendar_pairs(BASE, FOLLOWER, 1, right_missing={10})

        assert result.parameters["strongest_lag"] == 1
        assert by_lag(result)[1] == len(expected) == 33
        assert at_lag(result, 1) == pytest.approx(1.0, abs=1e-12)

    def test_one_missing_interior_month_is_not_bridged_by_a_negative_lag(self):
        # The negative branch had its own slicing and the same defect.
        result = lag_of(FOLLOWER, BASE, left_missing={10}, max_lag=3)
        expected = calendar_pairs(FOLLOWER, BASE, -1, left_missing={10})

        assert result.parameters["strongest_lag"] == -1
        assert by_lag(result)[-1] == len(expected) == 33
        assert at_lag(result, -1) == pytest.approx(1.0, abs=1e-12)

    @pytest.mark.parametrize("lag", range(-3, 4))
    def test_counts_and_correlations_match_an_independent_calendar_oracle(self, lag):
        # Several gaps on both sides, including two adjacent months, checked at
        # every offset in both directions against pairs built by index alone.
        left_missing, right_missing = {4, 27}, {10, 11, 20}
        result = lag_of(
            BASE,
            FOLLOWER,
            left_missing=left_missing,
            right_missing=right_missing,
            max_lag=3,
            minimum_pairs=12,
        )
        expected = calendar_pairs(
            BASE, FOLLOWER, lag, left_missing=left_missing, right_missing=right_missing
        )

        assert by_lag(result)[lag] == len(expected)
        assert at_lag(result, lag) == pytest.approx(
            reference_pearson([x for x, _ in expected], [y for _, y in expected]), abs=1e-12
        )

    def test_alternating_months_have_no_one_month_pair(self):
        # Published every other month: rows 1 apart are 2 months apart, so a
        # one-month lag has no evidence at all and must not appear.
        values = [float((step * 5) % 13) for step in range(48)]
        odd = set(range(1, 48, 2))
        result = lag_of(values, values, right_missing=odd, max_lag=2, minimum_pairs=12)

        assert by_lag(result) == {-2: 23, 0: 24, 2: 23}

    def test_an_offset_left_below_the_floor_by_a_gap_is_not_reported(self):
        # 25 aligned months clear the floor at lag 0. Excluding the two pairs
        # that touch the gap leaves 23 at lag +/-1, below the floor of 24,
        # although the compressed rows would have offered 24.
        values = [float(step % 9) * (1 + step % 4) for step in range(26)]
        result = lag_of(values, values, right_missing={12}, max_lag=1)

        assert result.status is ResultStatus.COMPUTED
        assert by_lag(result) == {0: 25}
        assert result.parameters["offsets_examined"] == 1

    def test_too_few_calendar_valid_pairs_is_insufficient(self):
        values = [float(step % 9) for step in range(30)]
        result = lag_of(values, values, right_missing={3, 7, 11, 15, 19, 23, 27}, max_lag=2)

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert "calendar-valid" in result.reason
        assert result.samples.used == 23
        assert result.samples.below_floor

    def test_lag_zero_is_still_the_association_over_the_same_gaps(self):
        left, right = monthly(BASE, missing={4}), monthly(FOLLOWER, missing={10, 11})
        lag = lagged_association(
            left, MONTHLY_STOCK, right, MONTHLY_STOCK, left_id="a", right_id="b", max_lag=2
        )
        same = associate(left, MONTHLY_STOCK, right, MONTHLY_STOCK, left_id="a", right_id="b")

        assert at_lag(lag, 0) == pytest.approx(same.values[0].value)
        assert by_lag(lag)[0] == same.samples.used == 33

    def test_weekly_lag_counts_weeks_and_does_not_bridge_a_missing_week(self):
        base = BASE + BASE[:4]
        follower = [5.0] + [2 * base[step - 1] + 3 for step in range(1, 40)]
        result = lagged_association(
            weekly(base),
            FRIDAY_WEEKLY,
            weekly(follower, missing={15}),
            FRIDAY_WEEKLY,
            left_id="a",
            right_id="b",
            max_lag=2,
        )

        assert result.parameters["strongest_lag"] == 1
        assert by_lag(result)[1] == len(calendar_pairs(base, follower, 1, right_missing={15}))
        assert at_lag(result, 1) == pytest.approx(1.0, abs=1e-12)
        assert "weekly" in result.parameters["lag_unit"]

    def test_quarterly_lag_counts_quarters(self):
        base = BASE[:30]
        follower = FOLLOWER[:30]
        result = lagged_association(
            quarterly(base),
            QUARTERLY_STOCK,
            quarterly(follower, missing={12}),
            QUARTERLY_STOCK,
            left_id="a",
            right_id="b",
            max_lag=2,
        )

        assert result.parameters["strongest_lag"] == 1
        assert by_lag(result)[1] == 27
        assert at_lag(result, 1) == pytest.approx(1.0, abs=1e-12)


class TestCalendarRefusals:
    """M6-24: when the distance between periods cannot be counted, abstain."""

    @pytest.mark.parametrize(
        "frequency",
        [Frequency.DAILY, Frequency.BUSINESS_DAY, Frequency.TWICE_MONTHLY, Frequency.IRREGULAR],
    )
    def test_a_calendar_without_a_canonical_step_abstains(self, frequency):
        semantics = replace(MONTHLY_STOCK, frequency=frequency)
        values = daily([float((step * 7) % 11) for step in range(40)])
        result = lagged_association(
            values, semantics, values, semantics, left_id="a", right_id="b", max_lag=2
        )

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert "canonical period step" in result.reason

    def test_the_same_daily_periods_can_still_be_associated(self):
        # Refusing to count days apart is not refusing to compare the same day.
        semantics = replace(MONTHLY_STOCK, frequency=Frequency.DAILY)
        values = daily([float((step * 7) % 11) for step in range(40)])
        result = associate(values, semantics, values, semantics, left_id="a", right_id="b")

        assert result.status is ResultStatus.COMPUTED

    def test_an_unknown_frequency_abstains(self):
        unknown = replace(MONTHLY_STOCK, frequency=Frequency.UNKNOWN)
        result = lagged_association(
            WAVES, unknown, ECHO, unknown, left_id="a", right_id="b", max_lag=2
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "frequency" in result.unresolved_semantics

    def test_a_weekly_series_cannot_be_declared_without_its_anchor(self):
        # The missing-anchor case cannot even reach this module.
        with pytest.raises(SemanticsError):
            replace(MONTHLY_STOCK, frequency=Frequency.WEEKLY)

    @pytest.mark.parametrize("operation", [associate, lagged_association])
    def test_weekly_series_ending_on_different_days_abstain(self, operation):
        wednesday = replace(FRIDAY_WEEKLY, anchor=WeeklyAnchor.WEDNESDAY)
        fridays = weekly(BASE)
        wednesdays = [
            Observation(
                item.period_start - timedelta(days=2),
                item.period_end - timedelta(days=2),
                item.value,
            )
            for item in fridays
        ]
        result = operation(fridays, FRIDAY_WEEKLY, wednesdays, wednesday, left_id="a", right_id="b")

        assert result.status is ResultStatus.ABSTAINED
        assert "different days" in result.reason

    @pytest.mark.parametrize("position", [0, 17])
    def test_a_date_off_the_declared_calendar_abstains(self, position):
        # Declared monthly, dated mid-month: the distance to its neighbours in
        # declared periods is undefined, at either end or in the middle.
        values = monthly(BASE)
        off = values[position]
        values[position] = Observation(off.period_start, off.period_end.replace(day=15), off.value)
        result = lagged_association(
            values, MONTHLY_STOCK, values, MONTHLY_STOCK, left_id="a", right_id="b", max_lag=2
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "declared monthly calendar" in result.reason

    def test_a_period_published_twice_abstains(self):
        values = monthly(BASE)
        result = lagged_association(
            [*values, values[5]],
            MONTHLY_STOCK,
            values,
            MONTHLY_STOCK,
            left_id="a",
            right_id="b",
            max_lag=2,
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "more than once" in result.reason


class TestLagWarningsAfterM624:
    """The caveats describe the pairs behind the reported number."""

    def test_a_perfect_echo_is_not_called_non_linear(self):
        # Before M6-24 the rank figure came from lag 0 while the linear one
        # came from the strongest lag: ECHO is an exact two-month copy, yet the
        # result claimed they differed by 1.36 and called it non-linear.
        result = lagged(max_lag=6)

        assert not any("not linear" in w for w in result.warnings)

    def test_a_genuinely_curved_lead_is_still_flagged(self):
        curved = [1.0] + [exp(BASE[step - 1] / 2) for step in range(1, 36)]
        result = lag_of(BASE, curved, max_lag=3)

        assert result.parameters["strongest_lag"] == 1
        assert any("not linear" in w for w in result.warnings)

    def test_a_shared_trend_is_still_named_in_a_lag_result(self):
        result = lagged_association(
            RISING_A, MONTHLY_STOCK, RISING_B, MONTHLY_STOCK, left_id="a", right_id="b"
        )

        assert any("correlate whatever they measure" in w for w in result.warnings)

    def test_every_caveat_survives_a_gap(self):
        result = lag_of(BASE, FOLLOWER, right_missing={10}, max_lag=3)

        assert any("moves first by 1 period(s)" in w for w in result.warnings)
        assert any("inflated by the search itself" in w for w in result.warnings)
        assert any("never filled to make a pair" in w for w in result.warnings)
        assert set(BASE_LIMITATIONS).issubset(set(result.limitations))
        assert any("not evidence of direction" in item for item in result.limitations)
        assert result.parameters["offsets_examined"] == len(result.values) == 7
        assert "never bridged" in result.parameters["lag_unit"]


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


@pytest.fixture
def gapped_house(tmp_path):
    """FOLLOWER stored without month 10: the gap lives in the lakehouse itself."""
    with open_lakehouse(tmp_path / "gapped") as lake:
        artifact = lake.record_artifact(
            b'{"x": 2}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque"),
            media_type="application/json",
            recorded_at=NOW,
        )
        for series_id, observations in (
            ("a:base", monthly(BASE)),
            ("b:follower", monthly(FOLLOWER, missing={10})),
        ):
            lake.register_series(
                series_id,
                title=series_id,
                semantics=MONTHLY_STOCK,
                artifact_id=artifact.artifact_id,
            )
            lake.append_observations(series_id, observations)
        yield lake


class TestTheTool:
    @pytest.mark.parametrize("operation", ["association", "lag"])
    def test_numeric_output_has_resolvable_execution_evidence(self, house, operation):
        from kkb_agent.agent import AnswerStatus, gate_answer
        from kkb_agent.agent.presentation import format_number
        from kkb_agent.agent.verifier import result_faults

        result = self.run(house, operation=operation).output
        assert not result_faults({"result": result}, house.connection)
        value = result.values[0]
        draft = (
            f"Gösterge {value.label} için {format_number(value.value)}."
            if operation == "association"
            else f"Değer {format_number(value.value)}."
        )
        gated = gate_answer(draft, result, house.connection)
        assert gated.status is AnswerStatus.ACCEPTED, gated.verdict.rejected

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

    def test_lag_through_the_tool_does_not_bridge_a_stored_gap(self, gapped_house):
        outcome = self.run(
            gapped_house,
            operation="lag",
            max_lag=3,
            left_series_id="a:base",
            right_series_id="b:follower",
        )

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.parameters["strongest_lag"] == 1
        assert by_lag(outcome.output)[1] == 33
        assert at_lag(outcome.output, 1) == pytest.approx(1.0, abs=1e-12)

    def test_the_limitations_reach_the_model_as_warnings(self, house):
        # A model that never sees the caveat will write around it.
        warnings = self.run(house, operation="association").warnings
        assert any("not causation" in w for w in warnings)

    def test_the_description_refuses_the_causal_reading(self, house):
        described = self.registry(house).descriptions()[0]["description"]

        assert "ASSOCIATION ONLY" in described
        assert "predictive precedence at most" in described

    def test_an_operation_that_does_not_exist_is_not_in_the_schema(self, house):
        # Granger joined in M6-11 (tests/unit/test_granger.py); anything else
        # the planner invents is still refused before it can run.
        from kkb_agent.agent import ArgumentsRejected

        with pytest.raises(ArgumentsRejected):
            self.registry(house).get("causality").parse(
                {
                    "operation": "cointegration",
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
