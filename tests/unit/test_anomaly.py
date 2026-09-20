"""M6-05/06: the anomaly baseline and its tool.

Two properties matter more than any individual flag.

A steadily rising series must **not** flag its own present. Housing credit
triples over five years, so a level-based detector would call every recent
month unusual and be useless; this one examines period-over-period changes.

And the outlier must not hide itself. Mean and standard deviation are computed
from data containing the outlier, so one large jump inflates the spread until
its own score falls below the cut — the more extreme the event, the better it
hides. The MAD-based test is checked against exactly that case.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from math import log
from statistics import median

import pytest

from kkb_agent.agent import ExecutionContext, ToolRegistry, ToolStatus
from kkb_agent.analytics import DEFAULT_MINIMUM_CHANGES, detect_anomalies
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
from kkb_agent.tools import AnomalyArguments, make_anomaly_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)

STOCK = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)

#: A rate is judged in its own points: two points is two points whether the rate
#: is 8 or 43, so a rate never moves to the relative basis.
RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)


def series(*values: float | None, first: date = date(2024, 1, 31)) -> list[Observation]:
    """Consecutive monthly observations starting at `first`."""
    out: list[Observation] = []
    year, month = first.year, first.month
    for value in values:
        end = _month_end(year, month)
        out.append(Observation(date(year, month, 1), end, value))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def _month_end(year: int, month: int) -> date:
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first_of_next - timedelta(days=1)


#: Twenty steady months of +100, then one month of +5000, then steady again.
#: The jump is the only thing that should be flagged.
STEADY_THEN_JUMP = series(
    *[1000.0 + 100 * step for step in range(20)],
    1000.0 + 100 * 19 + 5000.0,
    *[1000.0 + 100 * 19 + 5000.0 + 100 * step for step in range(1, 5)],
)

#: Twenty months rising by exactly +100 and nothing else.
STEADY = series(*[1000.0 + 100 * step for step in range(24)])


def detect(observations, semantics=STOCK, **kwargs):
    return detect_anomalies(observations, semantics, series_id="bddk:konut", **kwargs)


def _levels(first: float, steps):
    """The level series a list of period-over-period steps produces."""
    found = [first]
    for step in steps:
        found.append(found[-1] + step)
    return found


def _rate_with_three_jumps():
    """A rate moving +1 point a month, three times +15: the median deviation is zero."""
    steps = ([1.0] * 7 + [15.0]) * 3
    return series(*_levels(8.0, steps))


class TestItExaminesChangesNotLevels:
    def test_a_steadily_rising_series_flags_nothing(self):
        # This is the whole point. Every recent level is the highest ever, and none of
        # them is unusual. A step of +100 on a level of 1,000 is not the same move as
        # +100 on 3,300, so the relative changes taper instead of repeating; they taper
        # smoothly, and "no anomalies" is the answer, with a count the verifier can bind.
        result = detect(STEADY)
        count = next(v for v in result.values if v.label.endswith("anomalies found"))

        assert result.status is ResultStatus.COMPUTED
        assert count.value == 0.0

    def test_a_series_that_never_moves_is_still_undefined(self):
        # M6-08: no spread at all cannot be scored, on either basis.
        result = detect(series(*[1000.0] * 24))

        assert result.status is ResultStatus.UNDEFINED
        assert "moves by the same amount every period" in result.reason

    def test_a_rising_series_with_varied_steps_still_flags_only_the_jump(self):
        result = detect(STEADY_THEN_JUMP)
        flagged = [v for v in result.values if "change at" in v.label]

        assert result.status is ResultStatus.COMPUTED
        assert len(flagged) == 1
        assert flagged[0].value == pytest.approx(5000.0)

    def test_the_flagged_period_is_the_month_the_jump_landed_in(self):
        flagged = next(v for v in detect(STEADY_THEN_JUMP).values if "change at" in v.label)

        assert flagged.period is not None
        # 20 steady months from 2024-01, so the jump lands on the 21st.
        assert flagged.period.end == date(2025, 9, 30)

    def test_the_outlier_cannot_hide_behind_its_own_spread(self):
        # A plain z-score is computed from data containing the outlier, so the
        # 5000 jump inflates sigma until its own score sits near the cut. The
        # robust centre is unmoved: the median change is still +100.
        result = detect(STEADY_THEN_JUMP)
        magnitudes = [100.0] * 23 + [5000.0]
        mean = sum(magnitudes) / len(magnitudes)
        sigma = (sum((m - mean) ** 2 for m in magnitudes) / len(magnitudes)) ** 0.5
        plain_z = (5000.0 - mean) / sigma

        assert plain_z < 5.0  # a jump 49x the usual step, barely above the cut
        flagged = [v for v in result.values if "change at" in v.label]
        assert [v.value for v in flagged] == pytest.approx([5000.0])

    def test_a_collapsed_median_deviation_falls_back_rather_than_giving_up(self):
        # 21 of 24 changes are identical, so the median absolute deviation is
        # exactly zero. Refusing here would refuse the clearest case there is.
        result = detect(_rate_with_three_jumps(), RATE)

        assert result.status is ResultStatus.COMPUTED
        assert "MAD was zero" in result.parameters["scale_estimator"]

    def test_the_fallback_scale_keeps_the_declared_cut(self):
        # A flat rate moving +1 point a month, with three months of +15. The median
        # deviation is zero, so the fallback decides these, and the mean absolute
        # deviation about the median is 1.75: the paper's score for a +15 point move is
        # 14 / (1.253314 * 1.75) = 6.4, well past 3.5. A fallback scale 2.198 times too
        # large scores it 2.9 and reports nothing at all, which is what this looked like.
        result = detect(_rate_with_three_jumps(), RATE)

        flagged = [v for v in result.values if "change at" in v.label]
        assert [v.value for v in flagged] == pytest.approx([15.0, 15.0, 15.0])


class TestWhatAPeriodIsComparedWith:
    """A period is judged against the other periods, not against the size reached."""

    @staticmethod
    def _index_with_one_record_month():
        """An index rising ~4% a month for five years, with one month of +13.5%.

        This is the shape of the prepared CPI. The record month is early, so it is
        worth about 16 index points, while an ordinary month near the end of the
        window is worth more than twice that in points and nothing at all in meaning.
        """
        steps = [1.04, 1.036, 1.044] * 20
        steps[5] = 1.135
        level = 100.0
        levels = [level]
        for factor in steps:
            level *= factor
            levels.append(level)
        return series(*levels), levels

    def test_the_record_month_is_found_although_later_months_moved_more_in_points(self):
        observations, levels = self._index_with_one_record_month()
        record = levels[6] - levels[5]
        last = levels[-1] - levels[-2]
        assert last > 2 * record  # an ordinary late month dwarfs it in index points

        result = detect(
            observations,
            replace(STOCK, observation=StockFlow.INDEX, unit="index", scale=Scale.ONE, base_year=2025),
        )
        flagged = [v for v in result.values if "change at" in v.label]

        assert [v.value for v in flagged] == pytest.approx([record])
        assert any("relative to the level before it" in w for w in result.warnings)

    def test_a_rate_is_judged_in_its_own_points(self):
        parameters = detect(_rate_with_three_jumps(), RATE).parameters

        assert parameters["scored_on"] == "the difference in the series' own unit"

    def test_a_series_that_reaches_zero_keeps_its_difference(self):
        # There is no ratio to a level of zero, and a sign change has no log.
        balance = series(*_levels(-500.0, [100.0] * 8 + [700.0] + [100.0] * 15))
        parameters = detect(balance).parameters

        assert parameters["scored_on"] == "the difference in the series' own unit"


class TestTheCountIsAlwaysReported:
    def test_a_clean_series_reports_zero_rather_than_nothing(self):
        # "No anomalies" is an answer, and an answer whose number the verifier
        # cannot bind is an answer that gets withheld.
        mixed = series(*[1000.0 + step * 100 + (step % 3) * 40 for step in range(24)])
        result = detect(mixed)

        count = next(v for v in result.values if "anomalies found" in v.label)
        assert result.status is ResultStatus.COMPUTED
        assert count.value == pytest.approx(0.0)

    def test_the_count_is_dimensionless_not_unknown(self):
        result = detect(STEADY_THEN_JUMP)
        count = next(v for v in result.values if "anomalies found" in v.label)

        assert count.unit == DIMENSIONLESS
        assert count.scale is Scale.ONE
        assert result.unresolved_semantics == []

    def test_the_count_matches_the_flagged_periods(self):
        result = detect(STEADY_THEN_JUMP)
        count = next(v for v in result.values if "anomalies found" in v.label)

        assert count.value == len([v for v in result.values if "change at" in v.label])


class TestRefusals:
    def test_too_few_changes_is_insufficient(self):
        result = detect(series(1.0, 2.0, 3.0))

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert str(DEFAULT_MINIMUM_CHANGES) in result.reason
        assert result.samples.minimum_required == DEFAULT_MINIMUM_CHANGES

    def test_a_constant_series_is_undefined_not_infinite(self):
        result = detect(series(*[500.0] * 24))

        assert result.status is ResultStatus.UNDEFINED
        assert "no spread to score against" in result.reason

    def test_an_unresolved_series_abstains(self):
        unknown = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.UNKNOWN,
            cumulative=CumulativeKind.UNKNOWN,
        )
        result = detect(STEADY_THEN_JUMP, unknown)

        assert result.status is ResultStatus.ABSTAINED
        assert result.unresolved_semantics

    def test_a_cumulative_series_abstains(self):
        accumulating = SeriesSemantics(
            unit="TRY",
            scale=Scale.MILLION,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.FLOW,
            cumulative=CumulativeKind.YEARLY_RESET,
            aggregation=Aggregation.SUM,
        )
        result = detect(STEADY_THEN_JUMP, accumulating)

        assert result.status is ResultStatus.ABSTAINED
        assert "every period looks like a rise" in result.reason


class TestGapsBreakTheChain:
    def test_a_gap_is_not_bridged(self):
        # Differencing across a gap would report two periods of movement as
        # one, which is larger than anything that happened.
        # Without the break, the 1000-unit step across the gap would be the
        # largest "change" in the series and would flag itself.
        with_gap = series(
            # The block after the gap repeats the block before it three times over,
            # so the two halves move alike and only the gap itself is under test.
            *[1000.0 + 100 * step + (step % 3) * 30 for step in range(10)],
            None,
            *[3.0 * (1000.0 + 100 * step + (step % 3) * 30) for step in range(10, 24)],
        )
        result = detect(with_gap)
        flagged = [v for v in result.values if "change at" in v.label]

        assert result.status is ResultStatus.COMPUTED
        assert flagged == []

    def test_an_absent_row_is_a_gap_too(self):
        # A user's file may simply not have the February row. Differencing January
        # against March would label four months of movement one month's move, which
        # is how a flat series acquires an anomaly it never had.
        months = series(*[1000.0 + 40 * step + (step % 3) * 15 for step in range(24)])
        without_february = [o for o in months if o.period_end.month != 2]
        result = detect(without_february)

        assert result.samples.excluded == 2  # one February is absent in each year
        assert [v for v in result.values if "change at" in v.label] == []
        assert any("did not follow one another" in w for w in result.warnings)

    def test_a_daily_series_is_not_cut_at_every_weekend(self):
        # Published business days follow one another; the Friday-to-Monday move is
        # the one a reader asks about, and it used to be dropped as a gap.
        start = date(2024, 1, 1)  # a Monday
        days = [start + timedelta(days=step) for step in range(40)]
        business = [day for day in days if day.weekday() < 5]
        observations = [
            Observation(day, day, 100.0 + index * 2.0) for index, day in enumerate(business)
        ]
        daily = replace(STOCK, frequency=Frequency.DAILY, aggregation=Aggregation.LAST)
        result = detect(observations, daily)

        assert result.samples.excluded == 0
        assert result.samples.used == len(business) - 1  # every published pair scored

    def test_the_skipped_period_is_counted_and_reported(self):
        with_gap = series(
            # The block after the gap repeats the block before it three times over,
            # so the two halves move alike and only the gap itself is under test.
            *[1000.0 + 100 * step + (step % 3) * 30 for step in range(10)],
            None,
            *[3.0 * (1000.0 + 100 * step + (step % 3) * 30) for step in range(10, 24)],
        )
        result = detect(with_gap)

        assert result.samples.missing == 1
        assert any("a gap is not zero" in w for w in result.warnings)


class TestWhatTheResultDeclares:
    def test_the_parameters_record_what_produced_the_flags(self):
        parameters = detect(STEADY_THEN_JUMP).parameters

        assert parameters["threshold"] == pytest.approx(3.5)
        assert parameters["examined"] == "period-over-period change"
        assert "median absolute deviation" in parameters["method"]
        # A reader can see which basis decided the flags, and the median it was
        # measured against; on this rising balance that is the relative one.
        assert "log ratio to the previous level" in parameters["scored_on"]
        levels = [o.value for o in STEADY_THEN_JUMP]
        expected = median([log(b / a) for a, b in zip(levels, levels[1:], strict=False)])
        assert parameters["median_scored_change"] == pytest.approx(expected)

    def test_the_threshold_is_marked_as_unmeasured(self):
        # A default nobody benchmarked must not read as a validated one.
        assert "PROPOSED" in detect(STEADY_THEN_JUMP).parameters["threshold_status"]

    def test_it_says_an_unusual_change_is_not_a_cause(self):
        assert any(
            "not an error, an event or a cause" in w for w in detect(STEADY_THEN_JUMP).warnings
        )

    def test_a_stock_says_the_movement_is_net_not_new_lending(self):
        assert any("not unusual new lending" in w for w in detect(STEADY_THEN_JUMP).warnings)

    def test_the_window_can_be_narrowed(self):
        result = detect(STEADY_THEN_JUMP, start=date(2025, 10, 31))

        # The jump is outside this window, and what remains is too short.
        assert result.status is ResultStatus.INSUFFICIENT


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 1}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        lake.register_series(
            "bddk:konut", title="konut", semantics=STOCK, artifact_id=artifact.artifact_id
        )
        lake.append_observations("bddk:konut", STEADY_THEN_JUMP)
        yield lake


class TestTheTool:
    def test_numeric_output_has_resolvable_execution_evidence(self, house):
        from kkb_agent.agent import AnswerStatus, gate_answer
        from kkb_agent.agent.presentation import format_number
        from kkb_agent.agent.verifier import result_faults

        result = self.run(
            house,
        ).output
        assert not result_faults({"result": result}, house.connection)
        value = result.values[0]
        draft = f"Değer {format_number(value.value)}."
        gated = gate_answer(draft, result, house.connection)
        assert gated.status is AnswerStatus.ACCEPTED, gated.verdict.rejected

    def registry(self, house, lineage=True):
        registry = ToolRegistry()
        registry.register(
            make_anomaly_tool(house.connection, lineage=house.lineage if lineage else None)
        )
        return registry

    def run(self, house, lineage=True, **kwargs):
        return (
            self.registry(house, lineage)
            .get("anomaly")
            .run(
                AnomalyArguments(series_id=kwargs.pop("series_id", "bddk:konut"), **kwargs),
                ExecutionContext(question="anomali var mı"),
            )
        )

    def test_it_finds_the_jump_through_the_lakehouse(self, house):
        outcome = self.run(house)

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.kind is ResultKind.ANOMALY
        flagged = [v for v in outcome.output.values if "change at" in v.label]
        assert len(flagged) == 1

    def test_the_semantics_come_from_the_stored_declaration(self, house):
        flagged = next(v for v in self.run(house).output.values if "change at" in v.label)

        assert flagged.unit == "TRY"
        assert flagged.scale is Scale.MILLION

    def test_a_computed_detection_records_lineage(self, house):
        outcome = self.run(house)

        assert outcome.evidence is not None
        stored = house.connection.execute(
            "SELECT label FROM lineage_nodes WHERE node_id = ?", [outcome.evidence]
        ).fetchone()
        assert stored[0] == "anomaly_mad_zscore"

    def test_a_refusal_records_no_lineage_and_stays_successful(self, house):
        outcome = self.run(house, start=date(2026, 1, 31))

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.status is ResultStatus.INSUFFICIENT
        assert outcome.evidence is None

    def test_an_unknown_series_fails(self, house):
        outcome = self.run(house, series_id="bddk:hayalet")

        assert outcome.status is ToolStatus.FAILURE
        assert outcome.error_category == "series_unknown"

    def test_the_threshold_is_not_a_planner_argument(self, house):
        # A model that can move a threshold will move it until something looks
        # interesting, and the output would not show that it had.
        described = self.registry(house).descriptions()[0]["arguments"]["properties"]
        assert set(described) == {"series_id", "start", "end"}
