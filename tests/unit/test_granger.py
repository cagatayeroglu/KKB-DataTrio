"""M6-11: Granger precedence, and the things that make it misleading.

A Granger p-value is easy to compute and easy to over-read. These tests are
about the over-reading as much as the arithmetic:

- the F statistic must be the one statsmodels' own Granger routine computes,
  reached through a different code path;
- a regression row must never reach across a missing period (M6-24's rule,
  applied to lagged regressors);
- searching several orders in two directions finds small p-values in pure
  noise, and the result has to say it searched;
- nothing here may read as a mechanism (DEC-120), which the M6-01 contract
  enforces by refusing a causality result without limitations.
"""

from __future__ import annotations

import random
import re
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from scipy.stats import f as f_distribution
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.stattools import grangercausalitytests

from kkb_agent.agent import ArgumentsRejected, ExecutionContext, ToolRegistry, ToolStatus
from kkb_agent.agent.claim_qualifiers import causal_fault
from kkb_agent.analytics import (
    BASE_LIMITATIONS,
    GRANGER_LIMITATIONS,
    LAG_CAP,
    ROWS_PER_COEFFICIENT,
    granger_precedence,
)
from kkb_agent.core import (
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
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import CausalityArguments, make_causality_tool

NOW = datetime(2026, 9, 11, tzinfo=UTC)

MONTHLY = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)


def _month_end(year: int, month: int) -> date:
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first_of_next - timedelta(days=1)


def monthly(values, *, missing=(), first: date = date(2021, 1, 31)) -> list[Observation]:
    """Contiguous months from `first`, with the indices in `missing` never published."""
    out: list[Observation] = []
    year, month = first.year, first.month
    for index, value in enumerate(values):
        if index not in missing:
            out.append(Observation(date(year, month, 1), _month_end(year, month), value))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def noise(seed: int, count: int = 60, scale: float = 1.0) -> list[float]:
    """Deterministic Gaussian draws; the seed fixes the fixture forever."""
    rng = random.Random(seed)
    return [rng.gauss(0.0, scale) for _ in range(count)]


#: Five years of monthly data, the brief's window. LEADER is noise; FOLLOWER
#: repeats 0.8 of it one month later plus its own noise, so the forward
#: direction has a real order-1 precedence and the backward one has none.
LEADER = noise(11)
_WOBBLE = noise(12, scale=0.5)
FOLLOWER = [_WOBBLE[0]] + [0.8 * LEADER[t - 1] + _WOBBLE[t] for t in range(1, 60)]


def granger(left=LEADER, right=FOLLOWER, *, left_missing=(), right_missing=(), **kwargs):
    kwargs.setdefault("max_order", 4)
    return granger_precedence(
        monthly(left, missing=left_missing),
        MONTHLY,
        monthly(right, missing=right_missing),
        MONTHLY,
        left_id="a",
        right_id="b",
        **kwargs,
    )


def value(result, cause: str, effect: str, order: int, what: str = "p-value") -> float:
    prefix = f"{cause} precedes {effect}, Granger order {order}: "
    return next(
        item.value
        for item in result.values
        if item.label.startswith(prefix) and item.label[len(prefix) :].startswith(what)
    )


def rows_at(result, cause: str, effect: str, order: int) -> int:
    prefix = f"{cause} precedes {effect}, Granger order {order}: p-value"
    return next(item.samples.used for item in result.values if item.label == prefix)


class TestTheStatistic:
    @pytest.mark.parametrize("order", [1, 2, 3, 4])
    @pytest.mark.parametrize(
        ("cause", "effect", "cause_values", "effect_values"),
        [("a", "b", LEADER, FOLLOWER), ("b", "a", FOLLOWER, LEADER)],
    )
    def test_matches_statsmodels_own_granger_routine(
        self, order, cause, effect, cause_values, effect_values
    ):
        # grangercausalitytests builds its design with lagmat over a
        # contiguous array; this module builds rows from calendar positions.
        # On contiguous data the two paths must agree exactly.
        oracle = grangercausalitytests(
            [[e, c] for e, c in zip(effect_values, cause_values, strict=True)], maxlag=[order]
        )[order][0]["ssr_ftest"]
        result = granger()

        assert value(result, cause, effect, order, "F") == pytest.approx(float(oracle[0]))
        assert value(result, cause, effect, order) == pytest.approx(
            float(oracle[1]), rel=1e-9, abs=1e-15
        )
        assert f"F({order}, {int(oracle[2])})" in next(
            item.label
            for item in result.values
            if item.label.startswith(f"{cause} precedes {effect}, Granger order {order}: F")
        )
        assert rows_at(result, cause, effect, order) == 60 - order

    def test_a_built_in_lead_is_found_in_its_direction(self):
        result = granger()

        assert result.status is ResultStatus.COMPUTED
        assert result.kind is ResultKind.CAUSALITY
        assert value(result, "a", "b", 1) < 1e-6
        assert value(result, "b", "a", 1) > 0.05

    def test_independent_series_show_no_order_one_precedence(self):
        result = granger(noise(3), noise(4))

        assert value(result, "a", "b", 1) > 0.05
        assert value(result, "b", "a", 1) > 0.05

    def test_searching_finds_small_p_values_in_noise_and_says_so(self):
        # Two independent series, quiet at order 1, yet one of the eight tests
        # falls below 0.005. Across the first 58 seed pairs about one in five
        # shows p < 0.05 somewhere: the reason the result must never present
        # its smallest p-value as a tested hypothesis.
        result = granger(noise(1), noise(2))
        assert value(result, "a", "b", 1) > 0.5 and value(result, "b", "a", 1) > 0.5
        smallest = min(item.value for item in result.values if "p-value" in item.label)

        assert smallest < 0.005
        assert any(
            f"{result.parameters['tests_run']} Granger test(s)" in w
            and "not a pre-specified test" in w
            for w in result.warnings
        )
        assert result.parameters["tests_run"] == len(result.values) // 2 == 8


def calendar_rows(left_missing, right_missing, order, count=60):
    """Independent row oracle: index t is usable when t and its `order`
    predecessors were published by both series. Integer indices only."""
    both = {t for t in range(count) if t not in left_missing and t not in right_missing}
    return [t for t in sorted(both) if all(t - step in both for step in range(1, order + 1))]


def reference_f(target, other, rows, order):
    """F and p from two least-squares fits and the F distribution directly."""
    endog = [target[t] for t in rows]
    own = [[1.0, *(target[t - step] for step in range(1, order + 1))] for t in rows]
    joint = [
        [*base, *(other[t - step] for step in range(1, order + 1))]
        for base, t in zip(own, rows, strict=True)
    ]
    restricted, unrestricted = OLS(endog, own).fit(), OLS(endog, joint).fit()
    df_denom = len(rows) - (2 * order + 1)
    statistic = ((restricted.ssr - unrestricted.ssr) / order) / (unrestricted.ssr / df_denom)
    return float(statistic), float(f_distribution.sf(statistic, order, df_denom))


class TestCalendarRows:
    @pytest.mark.parametrize("order", [1, 2, 3])
    def test_no_row_reaches_across_a_gap(self, order):
        # FOLLOWER never published month 20 and LEADER never published month
        # 41. A row needs its own month and the `order` before it from both.
        result = granger(left_missing={41}, right_missing={20})
        rows = calendar_rows({41}, {20}, order)
        statistic, p_value = reference_f(FOLLOWER, LEADER, rows, order)

        assert rows_at(result, "a", "b", order) == len(rows)
        assert value(result, "a", "b", order, "F") == pytest.approx(statistic)
        assert value(result, "a", "b", order) == pytest.approx(p_value, rel=1e-9, abs=1e-15)

    def test_a_gap_costs_the_rows_that_would_need_it(self):
        # One interior gap removes the gap month and the `order` months after
        # it; compressing the dates instead would keep all but the first rows.
        gapped = granger(right_missing={20})
        compressed = granger(LEADER[:20] + LEADER[21:], FOLLOWER[:20] + FOLLOWER[21:])

        assert rows_at(gapped, "a", "b", 1) == 57
        assert rows_at(compressed, "a", "b", 1) == 58
        assert value(gapped, "a", "b", 1, "F") != pytest.approx(value(compressed, "a", "b", 1, "F"))

    def test_alternating_months_leave_no_row_at_any_order(self):
        # Published every other month: no period has its predecessor.
        result = granger(right_missing=set(range(1, 60, 2)))

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert "calendar-valid rows" in result.reason

    def test_a_gap_is_reported(self):
        result = granger(right_missing={20})

        assert any("no regression row reaches across a gap" in w for w in result.warnings)
        assert "no row reaches across a gap" in result.parameters["lag_unit"]


class TestSamplePolicy:
    def test_orders_without_enough_rows_are_not_tested_and_the_result_says_so(self):
        # 36 months: order p leaves 36 - p rows and needs max(24, 3 * (2p + 1)),
        # so orders 1-4 run and 5-6 do not.
        result = granger(LEADER[:36], FOLLOWER[:36], max_order=6)

        assert result.parameters["orders_tested"] == {
            "forward": [1, 2, 3, 4],
            "backward": [1, 2, 3, 4],
        }
        assert any("Order(s) 5, 6 were not tested" in w for w in result.warnings)
        assert ROWS_PER_COEFFICIENT == 3

    @pytest.mark.parametrize("max_order", [0, LAG_CAP + 1])
    def test_an_order_outside_the_window_is_refused(self, max_order):
        result = granger(max_order=max_order)

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert "outside the permitted" in result.reason

    def test_too_short_is_insufficient(self):
        result = granger(LEADER[:20], FOLLOWER[:20])

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert result.samples.below_floor

    def test_a_constant_series_is_undefined_not_negative(self):
        result = granger(LEADER, [5.0] * 60)

        assert result.status is ResultStatus.UNDEFINED
        assert result.values == []
        assert "does not vary" in result.reason

    def test_an_exact_relationship_leaves_no_statistic_in_that_direction(self):
        # b is exactly 2 * a one month earlier plus 3: the forward regression
        # fits to rounding, so its F is not a statistic and is withheld.
        exact = [3.0] + [2 * LEADER[t - 1] + 3 for t in range(1, 60)]
        result = granger(LEADER, exact)

        assert result.status is ResultStatus.COMPUTED
        assert result.parameters["orders_tested"]["forward"] == []
        assert result.parameters["orders_tested"]["backward"]
        assert any("regression was exact" in w for w in result.warnings)

    def test_nothing_but_exact_regressions_is_undefined(self):
        # A straight line is predicted exactly by its own past, in both roles.
        line = [float(step) for step in range(60)]
        result = granger(line, [2 * step + 3 for step in line])

        assert result.status is ResultStatus.UNDEFINED
        assert "no F statistic" in result.reason


class TestInheritedRefusals:
    def test_different_frequencies_abstain(self):
        quarterly = replace(MONTHLY, frequency=Frequency.QUARTERLY)
        result = granger_precedence(
            monthly(LEADER), MONTHLY, monthly(FOLLOWER), quarterly, left_id="a", right_id="b"
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "different frequencies" in result.reason

    def test_weekly_series_ending_on_different_days_abstain(self):
        friday = replace(MONTHLY, frequency=Frequency.WEEKLY, anchor=WeeklyAnchor.FRIDAY)
        wednesday = replace(friday, anchor=WeeklyAnchor.WEDNESDAY)
        first = date(2024, 1, 5)
        fridays = [
            Observation(first + timedelta(weeks=i, days=-6), first + timedelta(weeks=i), v)
            for i, v in enumerate(LEADER)
        ]
        wednesdays = [
            Observation(o.period_start - timedelta(days=2), o.period_end - timedelta(days=2), v)
            for o, v in zip(fridays, FOLLOWER, strict=True)
        ]
        result = granger_precedence(
            fridays, friday, wednesdays, wednesday, left_id="a", right_id="b"
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "different days" in result.reason

    def test_a_calendar_without_a_canonical_step_abstains(self):
        daily = replace(MONTHLY, frequency=Frequency.DAILY)
        days = [
            Observation(
                date(2024, 1, 1) + timedelta(days=i), date(2024, 1, 1) + timedelta(days=i), v
            )
            for i, v in enumerate(LEADER)
        ]
        result = granger_precedence(days, daily, days, daily, left_id="a", right_id="b")

        assert result.status is ResultStatus.ABSTAINED
        assert "canonical period step" in result.reason

    def test_unresolved_semantics_abstain(self):
        unknown = replace(MONTHLY, frequency=Frequency.UNKNOWN)
        result = granger_precedence(
            monthly(LEADER), unknown, monthly(FOLLOWER), unknown, left_id="a", right_id="b"
        )

        assert result.status is ResultStatus.ABSTAINED
        assert "frequency" in result.unresolved_semantics


class TestNoMechanism:
    """DEC-120: predictive precedence, stated with its limits, never a cause."""

    def test_every_limitation_is_attached(self):
        limitations = set(granger().limitations)

        assert set(BASE_LIMITATIONS) <= limitations
        assert set(GRANGER_LIMITATIONS) <= limitations
        assert any("inflation or the policy rate" in item for item in limitations)
        assert any("Structural breaks" in item for item in limitations)

    def test_no_text_the_result_carries_reads_as_a_cause(self):
        # The labels, warnings and limitations reach the model as prose. None
        # may say one series causes the other, and none may trip the answer
        # gate's own causal-wording check (M8-18).
        result = granger()
        texts = [
            *(item.label for item in result.values),
            *result.warnings,
            *result.limitations,
            str(result.parameters),
        ]

        assert all(not re.search(r"\bcause[sd]?\b", text, re.I) for text in texts)
        assert all(causal_fault(text) is None for text in texts)

    def test_the_reading_is_spelled_out(self):
        result = granger()

        assert any("predictive precedence, not a mechanism" in w for w in result.warnings)
        assert result.parameters["directions"] == {
            "forward": "a precedes b",
            "backward": "b precedes a",
        }

    def test_a_trending_pair_is_warned_about(self):
        rising_a = [100 + 10 * step + value for step, value in enumerate(noise(5))]
        rising_b = [500 + 3 * step + value for step, value in enumerate(noise(6))]
        result = granger(rising_a, rising_b)

        assert any("rejects far too often on trending levels" in w for w in result.warnings)


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"x": 3}',
            source=SourceRef(source_id="evds", source_type="http-json", locator="opaque"),
            media_type="application/json",
            recorded_at=NOW,
        )
        for series_id, values in (("evds:faiz", LEADER), ("bddk:konut", FOLLOWER)):
            lake.register_series(
                series_id, title=series_id, semantics=MONTHLY, artifact_id=artifact.artifact_id
            )
            lake.append_observations(series_id, monthly(values))
        yield lake


class TestTheTool:
    def test_numeric_output_has_resolvable_execution_evidence(self, house):
        from kkb_agent.agent import AnswerStatus, gate_answer
        from kkb_agent.agent.presentation import format_number
        from kkb_agent.agent.verifier import result_faults

        result = self.run(house, max_lag=2).output
        assert not result_faults({"result": result}, house.connection)
        value = result.values[
            1
        ]  # F statistic; tiny p-values remain ambiguous under existing tolerance.
        draft = f"Değer {format_number(value.value)}."
        gated = gate_answer(draft, result, house.connection)
        assert gated.status is AnswerStatus.ACCEPTED, gated.verdict.rejected

    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_causality_tool(house.connection, lineage=house.lineage))
        return registry

    def run(self, house, **kwargs):
        kwargs.setdefault("operation", "granger")
        kwargs.setdefault("left_series_id", "evds:faiz")
        kwargs.setdefault("right_series_id", "bddk:konut")
        return (
            self.registry(house)
            .get("causality")
            .run(CausalityArguments(**kwargs), ExecutionContext(question="faiz önce mi geliyor"))
        )

    def test_granger_runs_through_the_lakehouse(self, house):
        outcome = self.run(house, max_lag=3)

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.kind is ResultKind.CAUSALITY
        assert outcome.output.status is ResultStatus.COMPUTED
        assert value(outcome.output, "evds:faiz", "bddk:konut", 1) < 1e-6

    def test_the_limitations_reach_the_model_as_warnings(self, house):
        warnings = self.run(house, max_lag=2).warnings

        assert set(GRANGER_LIMITATIONS) <= set(warnings)

    def test_a_computed_result_records_lineage_marked_as_precedence(self, house):
        outcome = self.run(house, max_lag=2)

        stored = house.connection.execute(
            "SELECT label, attributes FROM lineage_nodes WHERE node_id = ?", [outcome.evidence]
        ).fetchone()
        assert stored[0] == "causality_granger"
        assert "predictive precedence only" in stored[1]

    def test_a_zero_order_refusal_stays_successful_and_records_no_lineage(self, house):
        outcome = self.run(house, max_lag=0)

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.status is ResultStatus.ABSTAINED
        assert outcome.evidence is None
        assert any("outside the permitted" in w for w in outcome.warnings)

    def test_the_schema_offers_granger_and_nothing_invented(self, house):
        tool = self.registry(house).get("causality")

        assert tool.parse({"operation": "granger", "left_series_id": "a", "right_series_id": "b"})
        with pytest.raises(ArgumentsRejected):
            tool.parse(
                {"operation": "cointegration", "left_series_id": "a", "right_series_id": "b"}
            )

    def test_the_description_names_precedence_not_mechanism(self, house):
        described = self.registry(house).descriptions()[0]["description"]

        assert "ASSOCIATION ONLY" in described
        assert "predictive precedence at most" in described
        assert "not available" not in described
