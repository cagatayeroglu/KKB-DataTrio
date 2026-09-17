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
    Coverage,
    Observation,
    WeekAssignment,
    assign_month,
    month_end,
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
        requested_start=date(2023, 1, 1),
        requested_end=MAR,
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
                requested_start=date(2023, 1, 1),
                requested_end=MAR,
                frequency=Frequency.MONTHLY,
                aggregation=Aggregation.AVERAGE,
                anchor=None,
                assignment=WeekAssignment.BY_END,
            )

    def test_a_weekly_source_without_an_anchor_is_refused(self):
        with pytest.raises(AlignmentError, match="needs its anchor"):
            to_monthly(
                weekly(),
                requested_start=date(2023, 1, 1),
                requested_end=MAR,
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
                requested_start=date(2023, 1, 1),
                requested_end=MAR,
                frequency=WEEKLY,
                aggregation=Aggregation.AVERAGE,
                anchor=FRIDAY,
                assignment=WeekAssignment.BY_END,
            )

    def test_duplicate_source_periods_are_refused(self):
        with pytest.raises(AlignmentError, match="Duplicate source periods"):
            to_monthly(
                weekly() + weekly(WEEKLY_RATE[:1]),
                requested_start=date(2023, 1, 1),
                requested_end=MAR,
                frequency=WEEKLY,
                aggregation=Aggregation.AVERAGE,
                anchor=FRIDAY,
                assignment=WeekAssignment.BY_END,
            )

    def test_no_observations_yields_nothing_rather_than_failing(self):
        alignment = align([])
        assert alignment.observations == []
        assert {end: c.expected for end, c in alignment.coverage.items()} == {
            JAN: 4,
            FEB: 4,
            MAR: 5,
        }
        assert all(c.observed == 0 and not c.complete for c in alignment.coverage.values())
        assert alignment.method["operation"] == "align_weekly_to_monthly"


class TestTheMethodIsRecorded:
    def test_every_parameter_a_transformation_record_needs_is_present(self):
        alignment = align(aggregation=Aggregation.AVERAGE, assignment=WeekAssignment.BY_MAJORITY)
        assert alignment.method == {
            "operation": "align_weekly_to_monthly",
            "aggregation": "average",
            "week_assignment": "by_majority",
            "anchor": "friday",
            "frequency": "weekly",
            "requested_start": "2023-01-01",
            "requested_end": "2023-03-31",
        }

    def test_the_method_distinguishes_two_otherwise_identical_runs(self):
        assert align().method != align(assignment=WeekAssignment.BY_MAJORITY).method


# Synthetic requested-window regressions; the historical reducer fixtures above
# deliberately keep their original values and expected numerical results.
def requested(
    rows=(),
    *,
    start=date(2024, 1, 1),
    end=date(2024, 1, 31),
    anchor=FRIDAY,
    assignment=WeekAssignment.BY_END,
    frequency=WEEKLY,
    aggregation=Aggregation.AVERAGE,
):
    observations = [
        Observation(*period_bounds(WEEKLY, day, anchor=anchor), value) for day, value in rows
    ]
    return to_monthly(
        observations,
        requested_start=start,
        requested_end=end,
        frequency=frequency,
        anchor=anchor,
        aggregation=aggregation,
        assignment=assignment,
    )


class TestRequestedWeeklyCoverage:
    @pytest.mark.parametrize(
        "anchor,days,expected",
        [
            (FRIDAY, [12], 4),
            (FRIDAY, [5, 12, 19, 26], 4),
            (WeeklyAnchor.WEDNESDAY, [10], 5),
            (WeeklyAnchor.WEDNESDAY, [3, 10, 17, 24, 31], 5),
            (FRIDAY, [12, 19, 26], 4),
            (FRIDAY, [5, 12, 19], 4),
            (FRIDAY, [12, 19], 4),
            (FRIDAY, [5, 19, 26], 4),
        ],
    )
    def test_expected_does_not_shrink_with_supplied_rows(self, anchor, days, expected):
        result = requested([(date(2024, 1, day), 10.0) for day in days], anchor=anchor)
        count = result.coverage[date(2024, 1, 31)]
        assert (count.expected, count.observed, count.missing) == (
            expected,
            len(days),
            expected - len(days),
        )
        assert count.complete is (len(days) == expected)

    @pytest.mark.parametrize(
        "anchor,days",
        [
            (WeeklyAnchor.MONDAY, [1, 8, 15, 22, 29]),
            (WeeklyAnchor.TUESDAY, [2, 9, 16, 23, 30]),
            (WeeklyAnchor.THURSDAY, [4, 11, 18, 25]),
            (WeeklyAnchor.SATURDAY, [6, 13, 20, 27]),
            (WeeklyAnchor.SUNDAY, [7, 14, 21, 28]),
        ],
    )
    def test_other_declared_anchors(self, anchor, days):
        result = requested([(date(2024, 1, d), 1.0) for d in days], anchor=anchor)
        count = result.coverage[date(2024, 1, 31)]
        assert count.expected == len(days) and count.complete

    @pytest.mark.parametrize(
        "start,end,days",
        [
            (date(2024, 1, 10), date(2024, 1, 15), [12]),
            (date(2024, 1, 12), date(2024, 1, 12), [12]),
            (date(2024, 1, 5), date(2024, 1, 26), [5, 12, 19, 26]),
        ],
    )
    def test_only_ends_must_be_inside_inclusive_window(self, start, end, days):
        result = requested([(date(2024, 1, d), 2.0) for d in days], start=start, end=end)
        count = result.coverage[date(2024, 1, 31)]
        assert count.expected == count.observed == len(days) and count.complete
        assert result.method["requested_start"] == start.isoformat()
        assert result.method["requested_end"] == end.isoformat()
        assert result.method["frequency"] == "weekly"

    @pytest.mark.parametrize(
        "rows",
        [[], [(date(2024, 1, 12), None)], [(date(2024, 1, d), None) for d in (5, 12, 19, 26)]],
    )
    def test_empty_and_null_inputs_preserve_expectation(self, rows):
        result = requested(rows)
        count = result.coverage[date(2024, 1, 31)]
        assert (count.expected, count.observed, count.complete) == (4, 0, False)
        assert result.observations == []

    def test_completely_missing_boundary_months_remain_visible(self):
        result = requested([(date(2024, 2, 9), 10.0)], end=date(2024, 3, 31))
        assert {m: (c.expected, c.observed) for m, c in result.coverage.items()} == {
            date(2024, 1, 31): (4, 0),
            date(2024, 2, 29): (4, 1),
            date(2024, 3, 31): (5, 0),
        }
        assert result.incomplete_periods() == list(result.coverage)
        assert [o.period_end for o in result.observations] == [date(2024, 2, 29)]

    def test_outside_values_do_not_change_counts_or_reduction(self):
        base = requested([(date(2024, 1, 12), 7.0)])
        extra = requested(
            [(date(2023, 12, 29), 999.0), (date(2024, 1, 12), 7.0), (date(2024, 2, 2), -999.0)]
        )
        assert extra == base

    def test_duplicate_periods_still_rejected(self):
        with pytest.raises(AlignmentError, match="Duplicate"):
            requested([(date(2024, 1, 12), 1.0)] * 2)

    def test_wrong_anchor_still_rejected(self):
        with pytest.raises(AlignmentError, match="not a friday"):
            to_monthly(
                [Observation(date(2024, 1, 4), date(2024, 1, 10), 1.0)],
                requested_start=date(2024, 1, 1),
                requested_end=date(2024, 1, 31),
                frequency=WEEKLY,
                anchor=FRIDAY,
                aggregation=Aggregation.AVERAGE,
                assignment=WeekAssignment.BY_END,
            )

    @pytest.mark.parametrize(
        "start,end",
        [
            (date(2024, 2, 1), date(2024, 1, 1)),
            (None, date(2024, 1, 1)),
            (date(2024, 1, 1), "2024-01-31"),
        ],
    )
    def test_invalid_window_is_rejected_even_without_data(self, start, end):
        with pytest.raises(AlignmentError):
            requested(start=start, end=end)

    def test_missing_request_is_not_replaced_by_observed_span(self):
        with pytest.raises(TypeError, match="requested_start"):
            to_monthly(
                weekly(),
                frequency=WEEKLY,
                anchor=FRIDAY,
                aggregation=Aggregation.AVERAGE,
                assignment=WeekAssignment.BY_END,
            )

    def test_zero_expectation_is_explicit_and_never_complete(self):
        result = requested(start=date(2024, 1, 13), end=date(2024, 1, 18))
        count = result.coverage[date(2024, 1, 31)]
        assert (count.expected, count.observed, count.missing, count.complete) == (0, 0, 0, False)
        assert result.incomplete_periods() == [date(2024, 1, 31)]
        assert result.observations == []

    @pytest.mark.parametrize("end", [date(2024, 1, 3), date(2024, 3, 1)])
    @pytest.mark.parametrize("policy", list(WeekAssignment))
    def test_straddling_weeks_keep_consistent_counts_and_values(self, end, policy):
        # Jan 3 -> Dec 31 by majority; Mar 1 -> Feb 29 by majority.
        anchor = WeeklyAnchor.WEDNESDAY if end.month == 1 else FRIDAY
        previous = date(2023, 12, 31) if end.month == 1 else date(2024, 2, 29)
        target = month_end(end.year, end.month) if policy is WeekAssignment.BY_END else previous
        result = requested([(end, 6.0)], start=end, end=end, anchor=anchor, assignment=policy)
        assert sum(c.expected for c in result.coverage.values()) == 1
        assert result.coverage[target].complete
        assert result.coverage[target].observed == 1
        assert values(result) == {target: 6.0}
        assert result.method["week_assignment"] == policy.value
        if policy is WeekAssignment.BY_MAJORITY:
            current = result.coverage[month_end(end.year, end.month)]
            assert current.expected == 0 and not current.complete

    def test_leap_day_anchor_is_inclusive(self):
        result = requested(
            [(date(2024, 2, 29), 1.0)],
            start=date(2024, 2, 1),
            end=date(2024, 2, 29),
            anchor=WeeklyAnchor.THURSDAY,
        )
        count = result.coverage[date(2024, 2, 29)]
        assert (count.expected, count.observed) == (5, 1)

    @pytest.mark.parametrize("frequency", [f for f in Frequency if f is not WEEKLY])
    def test_no_other_calendar_is_silently_added_to_alignment(self, frequency):
        with pytest.raises(AlignmentError, match="Only weekly"):
            requested(frequency=frequency)

    @pytest.mark.parametrize(
        "aggregation,expected",
        [
            (Aggregation.SUM, 12.0),
            (Aggregation.AVERAGE, 4.0),
            (Aggregation.FIRST, 2.0),
            (Aggregation.LAST, 6.0),
            (Aggregation.MIN, 2.0),
            (Aggregation.MAX, 6.0),
        ],
    )
    def test_coverage_window_does_not_change_reducer_values(self, aggregation, expected):
        rows = [(date(2024, 1, d), v) for d, v in [(19, 6.0), (5, 2.0), (12, 4.0)]]
        wide = requested(rows, aggregation=aggregation)
        narrow = requested(rows, end=date(2024, 1, 19), aggregation=aggregation)
        assert values(wide) == values(narrow) == {date(2024, 1, 31): expected}
        assert not wide.coverage[date(2024, 1, 31)].complete
        assert narrow.coverage[date(2024, 1, 31)].complete
        assert wide.method != narrow.method


class TestAWholeMonthKeepsTheWeekTheAssignmentGivesIt:
    """The window selects weeks by end date, but BY_MAJORITY answers in months.

    Measured on 2026-09-16: a 2021-01..2025-12 request published December 2025 as
    the average of the four weeks *ending* in December while calling it a
    by-majority average, and reported that month as fully covered. The week
    2025-12-27..2026-01-02 has four of its days in December and belongs there.
    """

    #: 2024-01-26 and 2024-02-02 both sit in the requested January by majority;
    #: 2024-03-01 does not, so it must stay out of a January-only request.
    JANUARY = date(2024, 1, 31)

    def rows(self):
        return [
            (date(2024, 1, 5), 1.0),
            (date(2024, 1, 12), 2.0),
            (date(2024, 1, 19), 3.0),
            (date(2024, 1, 26), 4.0),
            (date(2024, 2, 2), 10.0),
        ]

    def test_the_straddling_week_joins_the_month_that_owns_its_days(self):
        # 2024-01-27..2024-02-02: five days in January, two in February.
        result = requested(
            self.rows(), end=date(2024, 1, 31), assignment=WeekAssignment.BY_MAJORITY
        )
        assert values(result)[self.JANUARY] == pytest.approx((1 + 2 + 3 + 4 + 10) / 5)

    def test_the_coverage_counts_it_too_instead_of_claiming_completeness(self):
        result = requested(
            self.rows(), end=date(2024, 1, 31), assignment=WeekAssignment.BY_MAJORITY
        )
        count = result.coverage[self.JANUARY]
        assert (count.expected, count.observed, count.complete) == (5, 5, True)

    def test_a_missing_straddling_week_is_reported_as_missing(self):
        result = requested(
            self.rows()[:-1], end=date(2024, 1, 31), assignment=WeekAssignment.BY_MAJORITY
        )
        count = result.coverage[self.JANUARY]
        assert (count.expected, count.observed, count.complete) == (5, 4, False)
        assert self.JANUARY in result.incomplete_periods()

    def test_by_end_is_untouched_and_still_stops_at_the_window(self):
        result = requested(self.rows(), end=date(2024, 1, 31), assignment=WeekAssignment.BY_END)
        assert values(result)[self.JANUARY] == pytest.approx((1 + 2 + 3 + 4) / 4)
        assert result.coverage[self.JANUARY] == Coverage(expected=4, observed=4)

    def test_a_partial_month_is_not_completed_from_outside_the_request(self):
        # The caller asked for three weeks, not for January; pulling in a week it
        # never requested would answer a different question.
        result = requested(
            self.rows(),
            start=date(2024, 1, 1),
            end=date(2024, 1, 19),
            assignment=WeekAssignment.BY_MAJORITY,
        )
        assert values(result)[self.JANUARY] == pytest.approx((1 + 2 + 3) / 3)
        assert result.coverage[self.JANUARY].expected == 3

    def test_a_week_inside_the_window_still_goes_to_the_month_that_owns_it(self):
        # Unchanged rule: 2024-02-24..2024-03-01 ends inside a March request, and
        # February owns four of its days, so February is reported rather than the
        # week being dropped. Drawing weeks in must not start discarding them.
        result = requested(
            [(date(2024, 3, 1), 9.0), (date(2024, 3, 8), 1.0)],
            start=date(2024, 3, 1),
            end=date(2024, 3, 31),
            assignment=WeekAssignment.BY_MAJORITY,
        )
        assert values(result)[date(2024, 2, 29)] == pytest.approx(9.0)
        assert values(result)[date(2024, 3, 31)] == pytest.approx(1.0)

    def test_a_week_outside_the_window_is_not_drawn_into_a_month_it_does_not_own(self):
        # 2024-04-01..2024-04-05 lies wholly in April; a March request must not
        # acquire it, and no April month may appear from a March request.
        result = requested(
            [(date(2024, 3, 8), 1.0), (date(2024, 4, 5), 99.0)],
            start=date(2024, 3, 1),
            end=date(2024, 3, 31),
            assignment=WeekAssignment.BY_MAJORITY,
        )
        assert date(2024, 4, 30) not in values(result)
        assert 99.0 not in values(result).values()

    def test_the_drawn_in_week_does_not_leak_into_a_neighbouring_month(self):
        result = requested(
            self.rows(), end=date(2024, 1, 31), assignment=WeekAssignment.BY_MAJORITY
        )
        assert set(values(result)) == {self.JANUARY}
