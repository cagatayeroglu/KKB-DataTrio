"""M6-21: what a lakehouse query is allowed to claim about its own rows.

The projection reads semantics the lakehouse stores and refuses to supply any
it was not given. Most of these tests check that refusal, because the failure
mode is silent: a number that arrives without its scale looks exactly like one
that arrived with it, right up to the point where a million-TRY figure is
compared against a thousand-TRY one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import ExecutionContext, ToolRegistry, ToolStatus
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    ResultKind,
    ResultStatus,
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


def run(house, sql, *, lineage=True, **kwargs):
    registry = ToolRegistry()
    registry.register(
        make_lakehouse_tool(house.connection, lineage=house.lineage if lineage else None, **kwargs)
    )
    return registry.get("lakehouse").run(
        LakehouseArguments(sql=sql, purpose="test"), ExecutionContext(question="q")
    )


FULLY_TYPED = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    " ORDER BY o.period_end"
)


class TestAFullyJoinedQueryProducesATypedResult:
    def test_the_values_carry_the_declared_semantics(self, house):
        result = run(house, FULLY_TYPED).output.result

        assert result.status is ResultStatus.COMPUTED
        assert result.kind is ResultKind.SERIES
        assert [value.value for value in result.values] == pytest.approx(
            [767314.0, 782918.0, 801438.0]
        )
        latest = result.values[-1]
        assert latest.unit == "TRY"
        assert latest.scale is Scale.MILLION
        assert latest.measure is StockFlow.STOCK
        assert latest.label == "bddk:konut"

    def test_each_value_carries_the_period_it_covers(self, house):
        latest = run(house, FULLY_TYPED).output.result.values[-1]

        assert latest.period is not None
        assert latest.period.end == date(2026, 6, 30)
        assert latest.period.frequency is Frequency.MONTHLY

    def test_coverage_spans_the_rows_that_were_actually_read(self, house):
        result = run(house, FULLY_TYPED).output.result

        assert result.coverage is not None
        assert result.coverage.start == date(2026, 4, 1)
        assert result.coverage.end == date(2026, 6, 30)

    def test_a_fully_typed_result_declares_nothing_unresolved(self, house):
        assert run(house, FULLY_TYPED).output.result.unresolved_semantics == []

    def test_sample_counts_report_what_was_used(self, house):
        samples = run(house, FULLY_TYPED).output.result.samples

        assert samples is not None
        assert samples.used == 3
        assert samples.missing == 0

    def test_a_single_row_is_a_level_rather_than_a_series(self, house):
        result = run(house, FULLY_TYPED + " LIMIT 1").output.result
        assert result.kind is ResultKind.LEVEL

    def test_the_result_is_addressable_and_carries_its_lineage(self, house):
        outcome = run(house, FULLY_TYPED)
        result = outcome.output.result

        assert result.evidence is not None
        assert result.evidence.lineage_node == outcome.evidence
        assert result.result_id == outcome.evidence

    def test_the_input_references_name_the_tables_that_were_read(self, house):
        evidence = run(house, FULLY_TYPED).output.result.evidence

        assert evidence is not None
        assert evidence.input_refs == ["silver_observations", "silver_series"]


class TestAnUnjoinedNumberCannotBecomeEvidence:
    def test_a_bare_value_without_identity_abstains(self, house):
        result = run(house, "SELECT value FROM silver_observations").output.result

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert result.evidence is None

    def test_the_refusal_names_the_required_identity_and_semantics(self, house):
        result = run(house, "SELECT value FROM silver_observations").output.result
        assert "series_id, period_start, period_end, value, unit and scale" in result.reason

    def test_a_value_without_a_period_claims_no_coverage(self, house):
        result = run(house, "SELECT value FROM silver_observations").output.result

        assert result.values == []
        assert result.coverage is None

    def test_an_aggregate_without_identity_is_only_an_inspection_row(self, house):
        output = run(house, "SELECT max(value) AS value FROM silver_observations").output

        assert output.result.status is ResultStatus.ABSTAINED
        assert output.result.values == []
        assert output.result.evidence is None
        assert output.table.rows[0][0] == pytest.approx(801438.0)


class TestAQueryThatEstablishesNothing:
    def test_a_number_resting_on_no_table_is_refused(self, house):
        # `SELECT 42 AS value` passes every security gate: refusing it was
        # never their job. Without this the model can mint a figure.
        outcome = run(house, "SELECT 42 AS value")

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.result.status is ResultStatus.ABSTAINED
        assert outcome.output.result.values == []
        assert "rest on no source" in (outcome.output.result.reason or "")

    def test_the_model_is_told_the_query_established_nothing(self, house):
        outcome = run(house, "SELECT 42 AS value")
        assert any("rest on no source" in warning for warning in outcome.warnings)

    def test_a_listing_without_a_value_column_claims_no_measurement(self, house):
        outcome = run(house, "SELECT series_id, title FROM silver_series")

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.result.status is ResultStatus.ABSTAINED
        assert "listing" in (outcome.output.result.reason or "")
        # The rows are still there; the tool declines to call them a result.
        assert outcome.output.table.rows[0][0] == "bddk:konut"

    def test_an_empty_range_is_insufficient_rather_than_zero(self, house):
        outcome = run(
            house,
            "SELECT value FROM silver_observations WHERE period_end = DATE '1999-01-01'",
        )
        result = outcome.output.result

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.values == []
        assert result.samples is not None
        assert result.samples.used == 0

    def test_an_all_null_column_is_insufficient_not_a_computed_zero(self, house):
        house.connection.execute("UPDATE silver_observations SET value = NULL")
        result = run(house, FULLY_TYPED).output.result

        assert result.status is ResultStatus.INSUFFICIENT
        assert result.samples is not None
        assert result.samples.missing == 3
        assert "published nothing" in (result.reason or "")

    def test_a_text_value_column_is_not_a_measurement(self, house):
        result = run(house, "SELECT 'yaklasik' AS value FROM silver_observations").output.result

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert result.evidence is None
        assert "provenance" in result.reason

    def test_a_boolean_column_is_not_a_measurement(self, house):
        # `bool` is an `int` in Python, so this would otherwise become 1.0.
        result = run(
            house, "SELECT value IS NOT NULL AS value FROM silver_observations"
        ).output.result
        assert result.status is ResultStatus.ABSTAINED


class TestPartialAndInconsistentData:
    def test_a_null_period_is_counted_as_missing_not_dropped(self, house):
        house.connection.execute(
            "INSERT INTO silver_observations VALUES "
            "('bddk:konut', '2026-07-01', '2026-07-31', NULL)"
        )
        result = run(house, FULLY_TYPED).output.result

        assert result.samples is not None
        assert result.samples.used == 3
        assert result.samples.missing == 1

    def test_truncation_is_reported_as_a_partial_series(self, house):
        outcome = run(house, FULLY_TYPED, max_rows=2)

        assert outcome.output.result.status is ResultStatus.COMPUTED
        assert any("partial series" in w for w in outcome.output.result.warnings)
        assert outcome.output.truncated

    def test_a_literal_weekly_frequency_cannot_change_a_stored_calendar(self, house):
        result = run(
            house,
            "SELECT o.period_start, o.period_end, o.value, 'weekly' AS frequency"
            " FROM silver_observations o",
        ).output.result

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert result.evidence is None

    def test_a_literal_anchor_cannot_acquire_stored_semantic_authority(self, house):
        result = run(
            house,
            "SELECT o.period_start, o.period_end, o.value, 'weekly' AS frequency,"
            " 'friday' AS anchor FROM silver_observations o"
            " WHERE o.period_end = DATE '2026-06-30'",
        ).output.result

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert result.evidence is None

    def test_an_unrecognised_scale_is_reported_rather_than_guessed(self, house):
        result = run(
            house,
            "SELECT o.value, 'katrilyon' AS scale FROM silver_observations o",
        ).output.result

        assert result.status is ResultStatus.ABSTAINED
        assert result.values == []
        assert result.evidence is None


class TestTheRowsAndTheResultStayApart:
    def test_both_travel_on_the_tool_result(self, house):
        output = run(house, FULLY_TYPED).output

        assert output.result.status is ResultStatus.COMPUTED
        assert output.table.row_count == 3
        assert "period_end" in output.table.columns

    def test_a_rejected_query_is_still_a_failure_with_no_result(self, house):
        outcome = run(house, "SELECT * FROM lineage_nodes")

        assert outcome.status is ToolStatus.FAILURE
        assert outcome.error_category == "sql_rejected"
        assert outcome.output is None

    def test_the_security_gates_run_before_any_projection(self, house):
        # The projection must never be reachable for a refused statement.
        assert run(house, "SELECT * FROM read_csv('/etc/passwd')").status is ToolStatus.FAILURE


class TestTheResultIdentityIsUsable:
    def test_the_same_query_twice_describes_the_same_computation(self, house):
        first = run(house, FULLY_TYPED).output.result
        second = run(house, FULLY_TYPED).output.result
        assert first.describes_same_computation(second)

    def test_a_different_query_over_the_same_table_differs(self, house):
        whole = run(house, FULLY_TYPED).output.result
        part = run(house, FULLY_TYPED + " LIMIT 2").output.result
        assert not whole.describes_same_computation(part)

    def test_without_lineage_the_result_is_still_addressable(self, house):
        result = run(house, FULLY_TYPED, lineage=False).output.result

        assert result.result_id.startswith("lakehouse:")
        assert result.evidence is not None
        assert result.evidence.lineage_node is None

    def test_the_result_survives_a_json_round_trip(self, house):
        result = run(house, FULLY_TYPED).output.result
        restored = AnalyticalResult.model_validate_json(result.model_dump_json())
        assert restored.digest() == result.digest()
