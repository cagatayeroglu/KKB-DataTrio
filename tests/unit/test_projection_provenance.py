"""M6-23: an allowed FROM is not proof of projected financial values."""

from __future__ import annotations

import json
from datetime import date

import duckdb
import pytest

from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry, gate_answer
from kkb_agent.core import ResultStatus
from kkb_agent.database import apply_schema
from kkb_agent.lakehouse.lineage import Lineage
from kkb_agent.lakehouse.store import SANDBOX
from kkb_agent.llm.doubles import scripted
from kkb_agent.tools import (
    ChangeDetectionArguments,
    LakehouseArguments,
    QueryResult,
    make_change_detection_tool,
    make_lakehouse_tool,
    run_query,
)
from kkb_agent.tools._projection_provenance import provenance_fault
from kkb_agent.tools.lakehouse import _ast_of

SELECT = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
)
FROM = " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
CANONICAL = SELECT + FROM + " WHERE o.series_id = 'housing' ORDER BY o.period_end"


@pytest.fixture
def connection():
    with duckdb.connect(":memory:", config=SANDBOX) as connection:
        apply_schema(connection)
        connection.execute(
            "INSERT INTO bronze_artifacts VALUES "
            "('fixture', 'synthetic', 'memory', 'opaque:fixture', NULL, "
            "'application/json', 2, 'memory', '2026-09-10')"
        )
        connection.execute(
            "INSERT INTO silver_series VALUES "
            "('housing', 'Synthetic housing', 'fixture', 'TRY', 'million', 'monthly', "
            "NULL, 'stock', 'none', 'last', NULL), "
            "('other', 'Synthetic other', 'fixture', 'USD', 'thousand', 'monthly', "
            "NULL, 'stock', 'none', 'last', NULL)"
        )
        connection.execute(
            "INSERT INTO silver_observations VALUES "
            "('housing', '2026-05-01', '2026-05-31', 782918), "
            "('housing', '2026-06-01', '2026-06-30', 801438), "
            "('other', '2026-06-01', '2026-06-30', 801438)"
        )
        yield connection


def run(connection, sql, *, lineage=True):
    return make_lakehouse_tool(connection, lineage=Lineage(connection) if lineage else None).run(
        LakehouseArguments(sql=sql), ExecutionContext(question="synthetic test")
    )


ATTACKS = [
    pytest.param(
        "SELECT 999999 AS value, 'TRY' AS unit, 'million' AS scale "
        "FROM silver_observations LIMIT 1",
        id="original-literal-value",
    ),
    pytest.param(CANONICAL.replace("o.value", "999999 AS value"), id="literal-value-with-identity"),
    pytest.param(CANONICAL.replace("s.unit", "'USD' AS unit"), id="literal-unit"),
    pytest.param(CANONICAL.replace("s.scale", "'billion' AS scale"), id="literal-scale-mixed"),
    pytest.param(
        CANONICAL.replace("s.unit", "'TRY' AS unit"), id="matching-literal-still-untrusted"
    ),
    pytest.param(
        CANONICAL.replace("SELECT o.series_id", "SELECT 'invented' AS series_id"),
        id="fabricated-series",
    ),
    pytest.param(
        CANONICAL.replace("o.period_end, o.value", "DATE '2025-06-30' AS period_end, o.value"),
        id="fabricated-period-end",
    ),
    pytest.param(
        CANONICAL.replace("o.period_start", "DATE '2026-01-01' AS period_start"),
        id="fabricated-period-start",
    ),
    pytest.param(CANONICAL.replace("o.series_id, ", ""), id="missing-series"),
    pytest.param(CANONICAL.replace("o.period_start, ", ""), id="missing-period"),
    pytest.param(CANONICAL.replace("o.value", "o.value * 2 AS value"), id="arithmetic"),
    pytest.param(CANONICAL.replace("s.unit", "s.title AS unit"), id="renamed-stored-column"),
    pytest.param(
        CANONICAL.replace("s.scale", "s.scale, 'billion' AS scale"), id="duplicate-output"
    ),
    pytest.param(
        "WITH forged AS (SELECT 'invented' AS series_id, 999999 AS value, "
        "'TRY' AS unit, 'million' AS scale FROM silver_observations) SELECT * FROM forged",
        id="cte-laundering",
    ),
    pytest.param(
        "SELECT * FROM (SELECT 999999 AS value, 'TRY' AS unit, 'million' AS scale "
        "FROM silver_observations) forged",
        id="subquery-laundering",
    ),
    pytest.param(
        CANONICAL.replace(" ORDER BY o.period_end", "")
        + " UNION ALL SELECT 'invented', DATE '2026-06-01', DATE '2026-06-30', "
        "999999, 'TRY', 'million', 'monthly', NULL, 'stock'",
        id="union-laundering",
    ),
    pytest.param(
        CANONICAL.replace("s.series_id = o.series_id", "s.series_id = 'other'"),
        id="wrong-metadata-join",
    ),
    pytest.param(
        "SELECT max(value) AS value FROM silver_observations", id="unidentified-aggregate"
    ),
    pytest.param(CANONICAL.replace("s.frequency", "'weekly' AS frequency"), id="literal-frequency"),
    pytest.param(CANONICAL.replace("s.observation", "'flow' AS observation"), id="literal-measure"),
]


@pytest.mark.parametrize("sql", ATTACKS)
def test_fabricated_projection_cannot_become_evidence(connection, sql):
    before = connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()[0]
    outcome = run(connection, sql)
    result = outcome.output.result
    assert result.status is ResultStatus.ABSTAINED
    assert result.values == []
    assert result.evidence is None
    assert outcome.evidence is None
    assert connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()[0] == before
    for draft in ("Değer 999.999 milyon TL.", "Değer 801.438 milyon TL."):
        answer = gate_answer(draft, result, connection)
        assert answer.status is AnswerStatus.ABSTAINED
        assert not answer.presentable


@pytest.mark.parametrize("lineage", [True, False])
def test_canonical_stored_values_remain_supported(connection, lineage):
    result = run(connection, CANONICAL, lineage=lineage).output.result
    assert result.status is ResultStatus.COMPUTED
    assert [value.value for value in result.values] == [782918.0, 801438.0]
    assert result.values[-1].label == "housing"
    assert result.values[-1].unit == "TRY"
    assert result.values[-1].period.end.isoformat() == "2026-06-30"
    assert gate_answer("Haziran 2026'da 801.438 milyon TL.", result, connection).presentable


def test_supported_filter_order_and_limit_preserve_identity(connection):
    result = run(connection, CANONICAL + " DESC LIMIT 1").output.result
    assert result.status is ResultStatus.COMPUTED
    assert len(result.values) == 1
    assert result.values[0].value == 801438.0
    assert result.values[0].period.end.isoformat() == "2026-06-30"


@pytest.mark.parametrize(
    "sql",
    [
        SELECT + " FROM silver_observations o JOIN silver_series s USING(series_id)"
        " WHERE o.series_id = 'housing' ORDER BY o.period_end",
        SELECT + " FROM silver_series s JOIN silver_observations o ON o.series_id = s.series_id"
        " WHERE o.series_id = 'housing' ORDER BY o.period_end",
        CANONICAL.replace("o.series_id, o.period_start", "s.series_id, o.period_start"),
        "SELECT series_id, period_start, period_end, value, unit, scale "
        "FROM silver_observations JOIN silver_series USING(series_id) "
        "WHERE series_id = 'housing' ORDER BY period_end",
    ],
)
def test_equivalent_canonical_joins_remain_supported(connection, sql):
    result = run(connection, sql).output.result
    assert result.status is ResultStatus.COMPUTED
    assert [value.value for value in result.values] == [782918.0, 801438.0]


@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("series_id", "invented"),
        ("value", 999999.0),
        ("unit", "USD"),
        ("scale", "billion"),
        ("period_start", date(2026, 1, 1)),
        ("period_end", date(2025, 6, 30)),
    ],
)
def test_exact_store_recheck_rejects_missing_or_changed_identity(connection, column, replacement):
    query = run_query(connection, CANONICAL)
    row = list(query.rows[0])
    row[query.columns.index(column)] = replacement
    changed = QueryResult(query.columns, (tuple(row),), False)
    assert provenance_fault(changed, _ast_of(CANONICAL), connection) is not None


def test_existing_deterministic_comparison_keeps_source_backed_evidence(connection):
    result = (
        make_change_detection_tool(connection, lineage=Lineage(connection))
        .run(
            ChangeDetectionArguments(
                operation="compare",
                series_id="housing",
                start=date(2026, 5, 31),
                end=date(2026, 6, 30),
            ),
            ExecutionContext(question="synthetic comparison"),
        )
        .output
    )
    assert result.status is ResultStatus.COMPUTED
    assert result.evidence.lineage_node is not None
    assert result.evidence.input_refs == ["silver_series", "silver_observations"]
    assert any(value.value == 18520.0 for value in result.values)
    assert gate_answer("Değişim 18.520 milyon TL.", result, connection).presentable


def test_original_session_path_abstains_before_drafting(connection):
    sql = "SELECT 999999 AS value, 'TRY' AS unit, 'million' AS scale FROM silver_observations"
    provider = scripted(
        json.dumps(
            {
                "question": "housing",
                "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {"sql": sql}}],
            }
        ),
        "Değer 999.999 milyon TL.",
    )
    registry = ToolRegistry()
    registry.register(make_lakehouse_tool(connection, lineage=Lineage(connection)))
    answered = Session(provider, registry).answer("housing", connection)
    assert answered.results[-1].status is ResultStatus.ABSTAINED
    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert len(provider.seen) == 1
