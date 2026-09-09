"""M12-08 regressions for weekly-to-monthly alignment.

The weekly values below are real observations read from an EVDS `fe` response
during the M3-03 inspection. Their series identity was not resolved in the
catalog, so they are used here for their genuine Friday cadence and shape rather
than as a claim about a particular published series. The dates are real: January
and February 2023 hold four Fridays, March holds five, and two of these weeks
straddle a month boundary with the majority of their days on the earlier side.
"""

from __future__ import annotations

from datetime import date

import pytest

from kkb_agent.core import Aggregation, Frequency, WeeklyAnchor
from kkb_agent.lakehouse import (
    AlignmentError,
    Observation,
    WeekAssignment,
    assign_month,
    period_bounds,
    to_monthly,
)

FRIDAY = WeeklyAnchor.FRIDAY
WEEKLY = Frequency.WEEKLY

WEEKLY_RATE = [
    (date(2023, 1, 6), 46.750),
    (date(2023, 1, 13), 48.088),
    (date(2023, 1, 20), 49.588),
    (date(2023, 1, 27), 50.933),
    (date(2023, 2, 3), 51.696),
    (date(2023, 2, 10), 50.007),
    (date(2023, 2, 17), 49.209),
    (date(2023, 2, 24), 49.190),
    (date(2023, 3, 3), 50.078),
    (date(2023, 3, 10), 50.316),
    (date(2023, 3, 17), 52.958),
    (date(2023, 3, 24), 53.358),
    (date(2023, 3, 31), 52.175),
]

JAN, FEB, MAR = date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31)


def weekly(rows=None):
    out = []
    for end, value in rows if rows is not None else WEEKLY_RATE:
        start, _ = period_bounds(WEEKLY, end, anchor=FRIDAY)
        out.append(Observation(start, end, value))
    return out


def align(rows=None, *, aggregation=Aggregation.AVERAGE, assignment=WeekAssignment.BY_END):
    return to_monthly(
        weekly(rows),
        frequency=WEEKLY,
        aggregation=aggregation,
        anchor=FRIDAY,
        assignment=assignment,
    )


def values(alignment):
    return {item.period_end: item.value for item in alignment.observations}


class TestWeekAssignmentIsAPolicy:
    def test_a_week_inside_one_month_is_unambiguous(self):
        for policy in WeekAssignment:
            assert assign_month(date(2023, 3, 6), date(2023, 3, 10), policy) == MAR

    def test_the_two_policies_disagree_on_a_straddling_week(self):
        # 2023-02-25..2023-03-03: four days in February, three in March.
        start, end = period_bounds(WEEKLY, date(2023, 3, 3), anchor=FRIDAY)
        assert assign_month(start, end, WeekAssignment.BY_END) == MAR
        assert assign_month(start, end, WeekAssignment.BY_MAJORITY) == FEB

    def test_a_dead_heat_goes_to_the_end_month(self):
        # 2023-06-29..2023-07-05: three days in June, four in July.
        start, end = period_bounds(WEEKLY, date(2023, 7, 5), anchor=WeeklyAnchor.WEDNESDAY)
        assert assign_month(start, end, WeekAssignment.BY_MAJORITY) == date(2023, 7, 31)

    def test_the_chosen_policy_changes_the_answer(self):
        by_end = values(align())
        by_majority = values(align(assignment=WeekAssignment.BY_MAJORITY))
        assert by_end[FEB] != by_majority[FEB]
        assert by_end[MAR] != by_majority[MAR]


class TestReductionUsesTheDeclaredAggregation:
    def test_monthly_averages_match_hand_calculation(self):
        result = values(align())
        assert result[JAN] == pytest.approx(195.359 / 4)
        assert result[FEB] == pytest.approx(200.102 / 4)
        assert result[MAR] == pytest.approx(258.885 / 5)

    def test_the_majority_policy_moves_two_weeks_and_their_values(self):
        result = values(align(assignment=WeekAssignment.BY_MAJORITY))
        assert result[JAN] == pytest.approx(247.055 / 5)
        assert result[FEB] == pytest.approx(198.484 / 4)
        assert result[MAR] == pytest.approx(208.807 / 4)

    def test_last_takes_the_final_friday_of_the_month(self):
        result = values(align(aggregation=Aggregation.LAST))
        assert result[MAR] == pytest.approx(52.175)
        assert result[JAN] == pytest.approx(50.933)

    def test_first_takes_the_first_friday(self):
        assert values(align(aggregation=Aggregation.FIRST))[MAR] == pytest.approx(50.078)

    def test_min_and_max_span_the_month(self):
        assert values(align(aggregation=Aggregation.MIN))[MAR] == pytest.approx(50.078)
        assert values(align(aggregation=Aggregation.MAX))[MAR] == pytest.approx(53.358)

    def test_an_undeclared_aggregation_is_refused(self):
        with pytest.raises(AlignmentError, match="unknown is not a policy"):
            align(aggregation=Aggregation.UNKNOWN)


class TestCoverageIsReportedNotHidden:
    def test_a_five_friday_month_expects_five(self):
        alignment = align()
        assert alignment.coverage[MAR].expected == 5
        assert alignment.coverage[JAN].expected == 4
        assert all(count.complete for count in alignment.coverage.values())
        assert alignment.incomplete_periods() == []

    def test_a_week_missing_from_the_middle_is_counted_as_missing(self):
        # Dropping a row must not quietly shrink the denominator: the canonical
        # spine still expects that Friday, so March is reported as incomplete.
        thinned = [row for row in WEEKLY_RATE if row[0] != date(2023, 3, 17)]
        alignment = align(thinned)
        assert alignment.coverage[MAR].expected == 5
        assert alignment.coverage[MAR].observed == 4
        assert alignment.coverage[MAR].missing == 1
        assert alignment.incomplete_periods() == [MAR]

    def test_a_missing_value_counts_as_unobserved(self):
        blanked = [(end, None if end == date(2023, 3, 17) else value) for end, value in WEEKLY_RATE]
        alignment = align(blanked)
        assert alignment.coverage[MAR].observed == 4
        # The average is over what was actually seen, and the count says so.
        assert values(alignment)[MAR] == pytest.approx((258.885 - 52.958) / 4)

    def test_a_month_with_no_observations_is_omitted_not_zeroed(self):
        february_only_blank = [
            (end, None if end.month == 2 else value) for end, value in WEEKLY_RATE
        ]
        alignment = align(february_only_blank)
        assert FEB not in values(alignment)
        assert alignment.coverage[FEB].observed == 0
        assert alignment.coverage[FEB].expected == 4

    def test_a_single_friday_month_is_visibly_thin(self):
        alignment = align(WEEKLY_RATE[:1] + WEEKLY_RATE[4:])
        assert alignment.coverage[JAN].observed == 1
        assert alignment.coverage[JAN].expected == 4
        assert not alignment.coverage[JAN].complete


class TestAlignmentRefusesBadInput:
    def test_a_non_weekly_source_is_refused(self):
        with pytest.raises(AlignmentError, match="Only weekly series"):
            to_monthly(
                [Observation(date(2026, 6, 1), date(2026, 6, 30), 1.0)],
                frequency=Frequency.MONTHLY,
                aggregation=Aggregation.AVERAGE,
                anchor=None,
                assignment=WeekAssignment.BY_END,
            )

    def test_a_weekly_source_without_an_anchor_is_refused(self):
        with pytest.raises(AlignmentError, match="needs its anchor"):
            to_monthly(
                weekly(),
                frequency=WEEKLY,
                aggregation=Aggregation.AVERAGE,
                anchor=None,
                assignment=WeekAssignment.BY_END,
            )

    def test_an_observation_off_the_anchor_is_refused(self):
        thursday = [Observation(date(2023, 2, 24), date(2023, 3, 2), 50.0)] + weekly()
        with pytest.raises(AlignmentError, match="not a friday"):
            to_monthly(
                thursday,
                frequency=WEEKLY,
                aggregation=Aggregation.AVERAGE,
                anchor=FRIDAY,
                assignment=WeekAssignment.BY_END,
            )

    def test_duplicate_source_periods_are_refused(self):
        with pytest.raises(AlignmentError, match="Duplicate source periods"):
            to_monthly(
                weekly() + weekly(WEEKLY_RATE[:1]),
                frequency=WEEKLY,
                aggregation=Aggregation.AVERAGE,
                anchor=FRIDAY,
                assignment=WeekAssignment.BY_END,
            )

    def test_no_observations_yields_nothing_rather_than_failing(self):
        alignment = align([])
        assert alignment.observations == [] and alignment.coverage == {}
        assert alignment.method["operation"] == "align_weekly_to_monthly"


class TestTheMethodIsRecorded:
    def test_every_parameter_a_transformation_record_needs_is_present(self):
        alignment = align(aggregation=Aggregation.AVERAGE, assignment=WeekAssignment.BY_MAJORITY)
        assert alignment.method == {
            "operation": "align_weekly_to_monthly",
            "aggregation": "average",
            "week_assignment": "by_majority",
            "anchor": "friday",
        }

    def test_the_method_distinguishes_two_otherwise_identical_runs(self):
        assert align().method != align(assignment=WeekAssignment.BY_MAJORITY).method
