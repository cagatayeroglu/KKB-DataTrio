"""M6-20 regressions for the lakehouse tool's five gates.

Most of these are attacks. A model writing SQL against an analytical engine is
the largest attack surface in this system, so the interesting cases are the ones
where the query is exactly what an injected instruction would produce.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest

from kkb_agent.agent import ExecutionContext, ToolRegistry, ToolStatus, validate_plan
from kkb_agent.agent.plan import AnalyticalPlan
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, SourceRef, StockFlow
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.tools import (
    DEFAULT_READABLE,
    LakehouseArguments,
    SqlRejected,
    check_sql,
    make_lakehouse_tool,
    run_query,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)
SEMANTICS = SeriesSemantics(
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
            semantics=SEMANTICS,
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations(
            "bddk:konut",
            [
                Observation(date(end.year, end.month, 1), end, value)
                for end, value in PUBLISHED.items()
            ],
        )
        yield lake


def ask(house, sql):
    return run_query(house.connection, sql)


class TestItAnswersRealQuestions:
    def test_a_plain_select_returns_rows(self, house):
        result = ask(house, "SELECT period_end, value FROM silver_observations ORDER BY period_end")
        assert result.columns == ("period_end", "value")
        assert result.row_count == 3
        assert result.rows[-1][1] == pytest.approx(801438.0)

    def test_an_aggregate_works(self, house):
        result = ask(house, "SELECT count(*), max(value) FROM silver_observations")
        assert result.rows[0] == (3, pytest.approx(801438.0))

    def test_a_join_across_whitelisted_tables_works(self, house):
        result = ask(
            house,
            "SELECT s.unit, s.scale, o.value FROM silver_observations o"
            " JOIN silver_series s ON s.series_id = o.series_id"
            " WHERE o.period_end = DATE '2026-06-30'",
        )
        # The unit travels with the number, which is the whole point of silver.
        assert result.rows[0][:2] == ("TRY", "million")

    def test_a_cte_is_allowed_and_not_mistaken_for_a_table(self, house):
        result = ask(
            house,
            "WITH recent AS (SELECT * FROM silver_observations WHERE value IS NOT NULL)"
            " SELECT count(*) FROM recent",
        )
        assert result.rows[0][0] == 3

    def test_a_large_result_is_truncated_and_says_so(self, house):
        result = run_query(house.connection, "SELECT * FROM silver_observations", max_rows=2)
        assert result.row_count == 2
        assert result.truncated


class TestGateOneOneStatementAndItMustBeSelect:
    def test_a_second_statement_is_refused(self, house):
        with pytest.raises(SqlRejected, match="one statement"):
            ask(house, "SELECT 1; DROP TABLE gold_cells")

    def test_a_second_statement_hidden_after_a_comment_is_refused(self, house):
        # Parsed by the engine, so a comment cannot smuggle anything past it.
        with pytest.raises(SqlRejected, match="one statement"):
            ask(house, "SELECT 1 -- innocent\n; DELETE FROM silver_observations")

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM silver_observations",
            "UPDATE silver_series SET unit = 'USD'",
            "INSERT INTO gold_cells VALUES ('t','c','2026-06-01','2026-06-30',1.0,'n')",
            "DROP TABLE gold_cells",
            "CREATE TABLE evil (a INT)",
            "ATTACH 'other.db'",
            "INSTALL httpfs",
            "COPY silver_series TO 'stolen.csv'",
        ],
    )
    def test_anything_that_is_not_a_select_is_refused(self, house, sql):
        with pytest.raises(SqlRejected, match="Only SELECT"):
            ask(house, sql)

    def test_unparseable_sql_is_refused(self, house):
        with pytest.raises(SqlRejected, match="did not parse"):
            ask(house, "SELEC * FROM nowhere")


class TestGateTwoNoTableFunctions:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM read_parquet('/tmp/x.parquet')",
            "SELECT * FROM read_text('/etc/hosts')",
            "SELECT * FROM glob('/**')",
        ],
    )
    def test_file_reading_functions_are_refused(self, house, sql):
        with pytest.raises(SqlRejected, match="Table functions"):
            ask(house, sql)

    def test_a_table_function_inside_a_subquery_is_refused(self, house):
        with pytest.raises(SqlRejected, match="Table functions"):
            ask(house, "SELECT * FROM (SELECT * FROM read_csv('/etc/passwd')) x")


class TestGateThreeOnlyWhitelistedTables:
    def test_a_table_outside_the_whitelist_is_refused(self, house):
        with pytest.raises(SqlRejected, match="Not readable by this tool: lineage_nodes"):
            ask(house, "SELECT * FROM lineage_nodes")

    def test_the_workspace_is_not_readable(self, house):
        with pytest.raises(SqlRejected, match="workspace_artifacts"):
            ask(house, "SELECT * FROM workspace_artifacts")

    def test_an_implicit_file_scan_is_caught_by_the_whitelist(self, house):
        # DuckDB reads `FROM 'x.parquet'` as a table named x.parquet, which is
        # not on the list. This is the gap the whitelist closes.
        with pytest.raises(SqlRejected, match="secrets.parquet"):
            ask(house, "SELECT * FROM 'secrets.parquet'")

    def test_a_forbidden_table_joined_to_a_permitted_one_is_still_refused(self, house):
        with pytest.raises(SqlRejected, match="lineage_edges"):
            ask(
                house,
                "SELECT * FROM silver_series s JOIN lineage_edges e ON e.kind = s.unit",
            )

    def test_a_forbidden_table_hidden_in_a_cte_is_refused(self, house):
        with pytest.raises(SqlRejected, match="lineage_nodes"):
            ask(house, "WITH x AS (SELECT * FROM lineage_nodes) SELECT * FROM x")

    def test_the_error_names_what_is_readable(self, house):
        with pytest.raises(SqlRejected, match="Readable tables are"):
            ask(house, "SELECT * FROM lineage_nodes")

    def test_a_narrower_whitelist_is_honoured(self, house):
        with pytest.raises(SqlRejected, match="silver_series"):
            check_sql(house.connection, "SELECT * FROM silver_series", readable=["gold_cells"])


class TestGateFourExplainFirst:
    def test_an_unknown_column_fails_before_execution(self, house):
        with pytest.raises(SqlRejected, match="could not be planned"):
            ask(house, "SELECT no_such_column FROM silver_observations")

    def test_a_type_error_fails_before_execution(self, house):
        with pytest.raises(SqlRejected, match="could not be planned"):
            ask(house, "SELECT value + period_end FROM silver_observations")


class TestGateFiveTheDatabaseIsSandboxed:
    def test_the_engine_cannot_open_files_even_outside_the_tool(self, house):
        with pytest.raises(duckdb.Error):
            house.connection.execute("SELECT * FROM read_csv('/etc/passwd')")

    def test_the_engine_cannot_install_extensions(self, house):
        with pytest.raises(duckdb.Error):
            house.connection.execute("INSTALL httpfs")

    def test_the_engine_cannot_attach_another_database(self, house, tmp_path):
        with pytest.raises(duckdb.Error):
            house.connection.execute(f"ATTACH '{tmp_path / 'other.db'}'")


class TestTheToolInTheRegistry:
    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection))
        return registry

    def test_it_registers_under_the_brief_name(self, house):
        assert "lakehouse" in self.registry(house)

    def test_its_description_names_the_readable_tables(self, house):
        described = self.registry(house).descriptions()[0]
        for table in DEFAULT_READABLE:
            assert table in described["description"]

    def test_a_validated_plan_runs_it(self, house):
        plan = AnalyticalPlan.model_validate(
            {
                "question": "son değer nedir",
                "steps": [
                    {
                        "step_id": "s1",
                        "tool": "lakehouse",
                        "arguments": {
                            "sql": "SELECT max(value) FROM silver_observations",
                            "purpose": "latest housing credit stock",
                        },
                    }
                ],
            }
        )
        registry = self.registry(house)
        validated = validate_plan(plan, registry)
        spec = registry.get("lakehouse")
        result = spec.run(validated.steps[0].arguments, ExecutionContext(question="x"))
        assert result.status is ToolStatus.SUCCESS
        assert result.output.table.rows[0][0] == pytest.approx(801438.0)

    def test_a_rejected_query_becomes_a_failure_not_an_exception(self, house):
        spec = self.registry(house).get("lakehouse")
        result = spec.run(
            LakehouseArguments(sql="SELECT * FROM lineage_nodes"), ExecutionContext(question="x")
        )
        assert result.status is ToolStatus.FAILURE
        assert result.error_category == "sql_rejected"
        assert "lineage_nodes" in result.warnings[0]

    def test_an_undeclared_argument_is_refused_by_the_schema(self, house):
        with pytest.raises(ValueError, match="extra"):
            LakehouseArguments(sql="SELECT 1", shell="rm -rf /")

    def test_truncation_is_reported_as_a_warning(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, max_rows=1))
        result = registry.get("lakehouse").run(
            LakehouseArguments(sql="SELECT * FROM silver_observations"),
            ExecutionContext(question="x"),
        )
        assert result.status is ToolStatus.SUCCESS
        assert "truncated" in result.warnings[0]
