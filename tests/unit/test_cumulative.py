"""M12-04..07 regressions for the period spine and cumulative semantics.

Every fixture below is a real published BDDK series, quoted from the retrieval
recorded in BDDK_SOURCE. Synthetic numbers would not have exercised the case
that actually matters: a stock that rises monotonically through a January and
therefore looks exactly like a cumulative series.
"""

from __future__ import annotations

from datetime import date

import pytest

from kkb_agent.core import CumulativeKind, Frequency, WeeklyAnchor
from kkb_agent.lakehouse import (
    Confidence,
    CumulativeError,
    Observation,
    PeriodMismatch,
    SemanticsError,
    add_months,
    detect_cumulative,
    is_january,
    month_end,
    spine,
    to_flow,
)

MONTHLY = Frequency.MONTHLY

# BDDK Aylık Bülten table 4, "Tüketici Kredileri - Konut": an outstanding stock.
# This stretch falls for five consecutive months, which no cumulative series can.
KONUT_FALLING = [
    ("2023-07", 441780),
    ("2023-08", 447315),
    ("2023-09", 445908),
    ("2023-10", 443033),
    ("2023-11", 440412),
    ("2023-12", 438222),
    ("2024-01", 436688),
    ("2024-02", 438203),
    ("2024-03", 444323),
]

# The same stock a year later, rising every month including across January.
# Values alone cannot tell this apart from a since-inception cumulative.
KONUT_RISING = [
    ("2025-10", 642144),
    ("2025-11", 658770),
    ("2025-12", 678970),
    ("2026-01", 691343),
    ("2026-02", 715799),
    ("2026-03", 741972),
]

# BDDK table 2, "DÖNEM NET KARI (ZARARI)": year-to-date, reset every January.
NET_PROFIT_RESET = [
    ("2024-10", 515628),
    ("2024-11", 583121),
    ("2024-12", 660278),
    ("2025-01", 47347),
    ("2025-02", 118214),
    ("2025-03", 216651),
    ("2025-04", 264202),
    ("2025-05", 326834),
    ("2025-06", 422459),
    ("2025-07", 479205),
    ("2025-08", 563401),
    ("2025-09", 669676),
    ("2025-10", 751645),
    ("2025-11", 842845),
    ("2025-12", 940183),
    ("2026-01", 87249),
    ("2026-02", 169401),
    ("2026-03", 288688),
    ("2026-04", 363313),
    ("2026-05", 421789),
    ("2026-06", 528431),
]


def monthly(rows):
    """Turn ("YYYY-MM", value) pairs into observations on canonical periods."""
    out = []
    for label, value in rows:
        year, month = (int(part) for part in label.split("-"))
        end = month_end(year, month)
        out.append(Observation(date(year, month, 1), end, None if value is None else float(value)))
    return out


class TestPeriodSpine:
    def test_a_monthly_spine_lands_on_month_ends(self):
        periods = spine(MONTHLY, date(2025, 11, 30), date(2026, 2, 28))
        assert [end for _, end in periods] == [
            date(2025, 11, 30),
            date(2025, 12, 31),
            date(2026, 1, 31),
            date(2026, 2, 28),
        ]

    def test_the_spine_crosses_a_leap_february(self):
        periods = spine(MONTHLY, date(2024, 1, 31), date(2024, 3, 31))
        assert periods[1] == (date(2024, 2, 1), date(2024, 2, 29))

    def test_a_weekly_spine_steps_by_seven_days_on_its_anchor(self):
        periods = spine(
            Frequency.WEEKLY, date(2026, 8, 7), date(2026, 8, 28), anchor=WeeklyAnchor.FRIDAY
        )
        assert [end for _, end in periods] == [
            date(2026, 8, 7),
            date(2026, 8, 14),
            date(2026, 8, 21),
            date(2026, 8, 28),
        ]
        assert all(end.weekday() == WeeklyAnchor.FRIDAY.weekday for _, end in periods)

    def test_a_spine_bound_must_itself_be_a_valid_period_end(self):
        with pytest.raises(PeriodMismatch):
            spine(MONTHLY, date(2026, 1, 15), date(2026, 3, 31))

    def test_an_inverted_range_is_refused(self):
        with pytest.raises(SemanticsError, match="ends before it starts"):
            spine(MONTHLY, date(2026, 3, 31), date(2026, 1, 31))

    def test_both_bounds_are_inclusive(self):
        assert len(spine(MONTHLY, date(2026, 1, 31), date(2026, 1, 31))) == 1

    def test_daily_has_no_spine_without_a_holiday_calendar(self):
        with pytest.raises(SemanticsError, match="No canonical spine"):
            spine(Frequency.DAILY, date(2026, 1, 1), date(2026, 1, 5))

    def test_month_arithmetic_clamps_to_month_ends(self):
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
        assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
        assert add_months(date(2025, 12, 31), 1) == date(2026, 1, 31)

    def test_january_is_recognized_across_frequencies(self):
        assert is_january(date(2026, 1, 31), MONTHLY)
        assert not is_january(date(2026, 2, 28), MONTHLY)
        assert is_january(date(2026, 3, 31), Frequency.QUARTERLY)


class TestDetectionOnRealSeries:
    def test_a_falling_stock_is_ruled_out_as_cumulative(self):
        verdict = detect_cumulative(monthly(KONUT_FALLING), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.NONE
        assert verdict.confidence is Confidence.HIGH
        assert verdict.actionable
        assert "outside January" in verdict.reasons[0]

    def test_the_real_yearly_reset_is_detected(self):
        verdict = detect_cumulative(monthly(NET_PROFIT_RESET), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.YEARLY_RESET
        assert verdict.confidence is Confidence.HIGH

    def test_a_single_boundary_lowers_confidence(self):
        verdict = detect_cumulative(monthly(NET_PROFIT_RESET[10:17]), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.YEARLY_RESET
        assert verdict.confidence is Confidence.LOW
        assert not verdict.actionable

    def test_a_monotonic_stock_is_not_called_cumulative(self):
        # The case that matters: this really is a stock, and it only rises,
        # including across January. Anything that answers here is guessing.
        verdict = detect_cumulative(monthly(KONUT_RISING), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.UNKNOWN
        assert verdict.confidence is Confidence.LOW
        assert any("growing stock" in reason for reason in verdict.reasons)

    def test_resetting_in_some_years_only_decides_nothing(self):
        # Real 2024-12..2025-12, which resets once, plus a contrived January
        # that does not. A reset series resets every year, so this is not one.
        mixed = NET_PROFIT_RESET[2:15] + [("2026-01", 1_000_000)]
        verdict = detect_cumulative(monthly(mixed), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.UNKNOWN
        assert verdict.confidence is Confidence.LOW
        assert "1 of 2 January boundaries" in verdict.reasons[0]

    def test_too_few_observations_yields_no_confidence(self):
        verdict = detect_cumulative(monthly(KONUT_FALLING[:3]), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.UNKNOWN
        assert verdict.confidence is Confidence.NONE

    def test_missing_values_do_not_fabricate_a_fall(self):
        rows = [(label, value) for label, value in KONUT_RISING]
        rows[2] = (rows[2][0], None)
        verdict = detect_cumulative(monthly(rows), frequency=MONTHLY)
        assert verdict.kind is CumulativeKind.UNKNOWN

    def test_duplicate_periods_are_refused(self):
        doubled = monthly(KONUT_RISING) + monthly(KONUT_RISING[:1])
        with pytest.raises(CumulativeError, match="Duplicate periods"):
            detect_cumulative(doubled, frequency=MONTHLY)


class TestYearlyResetConversion:
    def test_within_year_flow_is_the_first_difference(self):
        flows = to_flow(monthly(NET_PROFIT_RESET), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        by_end = {item.period_end: item.value for item in flows}
        assert by_end[date(2025, 12, 31)] == pytest.approx(940183 - 842845)
        assert by_end[date(2026, 2, 28)] == pytest.approx(169401 - 87249)
        assert by_end[date(2026, 6, 30)] == pytest.approx(528431 - 421789)

    def test_january_is_already_the_month_itself(self):
        flows = to_flow(monthly(NET_PROFIT_RESET), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        january = next(item for item in flows if item.period_end == date(2026, 1, 31))
        assert january.value == pytest.approx(87249)

    def test_the_boundary_artefact_never_appears(self):
        # Differencing across the reset would give -852,934: a fake catastrophe.
        flows = to_flow(monthly(NET_PROFIT_RESET), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        assert all(item.value is None or item.value > 0 for item in flows)

    def test_the_first_period_needs_no_baseline_when_it_is_january(self):
        flows = to_flow(
            monthly(NET_PROFIT_RESET[15:]), CumulativeKind.YEARLY_RESET, frequency=MONTHLY
        )
        assert flows[0].value == pytest.approx(87249)

    def test_a_mid_year_first_period_is_unresolved(self):
        flows = to_flow(
            monthly(NET_PROFIT_RESET[11:]), CumulativeKind.YEARLY_RESET, frequency=MONTHLY
        )
        assert flows[0].value is None

    def test_a_gap_leaves_the_next_flow_unresolved(self):
        rows = NET_PROFIT_RESET[15:18] + NET_PROFIT_RESET[19:]  # drop 2026-04
        flows = to_flow(monthly(rows), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        by_end = {item.period_end: item.value for item in flows}
        assert by_end[date(2026, 5, 31)] is None
        assert by_end[date(2026, 6, 30)] == pytest.approx(528431 - 421789)

    def test_a_missing_predecessor_leaves_the_next_flow_unresolved(self):
        rows = [(label, None if label == "2026-04" else value) for label, value in NET_PROFIT_RESET]
        flows = to_flow(monthly(rows), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        by_end = {item.period_end: item.value for item in flows}
        assert by_end[date(2026, 4, 30)] is None
        assert by_end[date(2026, 5, 31)] is None

    def test_period_count_is_preserved(self):
        flows = to_flow(monthly(NET_PROFIT_RESET), CumulativeKind.YEARLY_RESET, frequency=MONTHLY)
        assert [item.period_end for item in flows] == [
            item.period_end for item in monthly(NET_PROFIT_RESET)
        ]


class TestSinceInceptionConversion:
    SERIES = [("2026-01", 100.0), ("2026-02", 250.0), ("2026-03", 430.0)]

    def test_a_baseline_makes_the_first_period_derivable(self):
        flows = to_flow(
            monthly(self.SERIES), CumulativeKind.SINCE_INCEPTION, frequency=MONTHLY, baseline=40.0
        )
        assert [item.value for item in flows] == pytest.approx([60.0, 150.0, 180.0])

    def test_without_a_baseline_the_first_period_is_unresolved_not_zero(self):
        flows = to_flow(monthly(self.SERIES), CumulativeKind.SINCE_INCEPTION, frequency=MONTHLY)
        assert flows[0].value is None
        assert [item.value for item in flows[1:]] == pytest.approx([150.0, 180.0])

    def test_january_gets_no_special_treatment_here(self):
        # Unlike a yearly-reset series, January is an ordinary period.
        flows = to_flow(
            monthly([("2025-12", 900.0)] + self.SERIES),
            CumulativeKind.SINCE_INCEPTION,
            frequency=MONTHLY,
            baseline=800.0,
        )
        january = next(item for item in flows if item.period_end == date(2026, 1, 31))
        assert january.value == pytest.approx(100.0 - 900.0)


class TestConversionRefusesWhatItCannotSupport:
    @pytest.mark.parametrize("kind", [CumulativeKind.NONE, CumulativeKind.UNKNOWN])
    def test_a_non_cumulative_series_is_not_converted(self, kind):
        with pytest.raises(CumulativeError, match="nothing to convert"):
            to_flow(monthly(KONUT_FALLING), kind, frequency=MONTHLY)

    def test_a_stock_cannot_be_differenced_into_disbursement_by_accident(self):
        # The reference scenario's trap: housing credit is a stock, and the
        # detector says so, so the caller has no verdict that permits this.
        verdict = detect_cumulative(monthly(KONUT_FALLING), frequency=MONTHLY)
        with pytest.raises(CumulativeError):
            to_flow(monthly(KONUT_FALLING), verdict.kind, frequency=MONTHLY)

    def test_an_unsupported_frequency_is_refused(self):
        rows = monthly(NET_PROFIT_RESET)
        with pytest.raises(CumulativeError, match="not defined for"):
            to_flow(rows, CumulativeKind.YEARLY_RESET, frequency=Frequency.WEEKLY)


@pytest.mark.parametrize(
    "frequency,first,last,ends",
    [
        (
            Frequency.QUARTERLY,
            date(2024, 3, 31),
            date(2024, 12, 31),
            [date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31)],
        ),
        (
            Frequency.SEMIANNUAL,
            date(2024, 6, 30),
            date(2024, 12, 31),
            [date(2024, 6, 30), date(2024, 12, 31)],
        ),
        (
            Frequency.ANNUAL,
            date(2023, 12, 31),
            date(2025, 12, 31),
            [date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31)],
        ),
    ],
)
def test_month_based_spines_remain_strict_and_unchanged(frequency, first, last, ends):
    assert [end for _, end in spine(frequency, first, last)] == ends
    with pytest.raises(PeriodMismatch):
        spine(frequency, first.replace(day=15), last)


@pytest.mark.parametrize(
    "frequency",
    [
        Frequency.UNKNOWN,
        Frequency.DAILY,
        Frequency.BUSINESS_DAY,
        Frequency.TWICE_MONTHLY,
        Frequency.IRREGULAR,
    ],
)
def test_unsupported_calendars_still_have_no_spine(frequency):
    with pytest.raises(SemanticsError):
        spine(frequency, date(2024, 1, 1), date(2024, 1, 31))
