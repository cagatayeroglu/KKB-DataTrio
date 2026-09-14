"""The `lakehouse` tool: restricted text-to-SQL over gold (M6-20, DEC-121).

A model writing SQL is the only practical way to answer questions nobody wrote a
function for. It is also the most dangerous thing in this system, because SQL in
an analytical engine can read files, attach databases and load extensions.

So the model's SQL is never trusted and never merely pattern-matched. It goes
through five gates, and a query has to pass all of them:

1. **One statement, and it must be a SELECT.** Parsed by the engine, not by a
   regular expression, so `SELECT 1; DROP TABLE x` cannot hide behind a comment.
2. **No table functions.** `read_csv`, `read_parquet` and friends are how SQL
   reaches the filesystem, and they are refused by AST node type.
3. **Only whitelisted tables.** Every base table that is not a CTE defined in
   the same query must be one this tool is allowed to read.
4. **`EXPLAIN` first.** The engine plans the query without running it, so a
   query that would fail fails before touching data.
5. **A sandboxed database.** The lakehouse is opened with external access and
   community extensions switched off, so a query cannot reach the filesystem or
   the network even if a gate above were wrong.

Gates three and five overlap deliberately. The whitelist is the intent; the
sandbox is what holds if the whitelist is ever wrong. Note that gate three also
catches DuckDB's implicit file scan — `SELECT * FROM \'secrets.parquet\'` parses
as a base table named `secrets.parquet`, which is not on the list.

DuckDB applies configuration per database, not per connection, so the sandbox is
set once when the lakehouse is opened rather than here. The pipeline does its own
file I/O through Python, so nothing needs the capability back.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import AnalyticalResult, ResultStatus
from kkb_agent.database import all_tables
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.tools import _projection

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: What the tool may read. Gold is the analysis surface; silver metadata is
#: readable so a query can state a series' unit without a second round trip.
DEFAULT_READABLE = ("gold_cells", "silver_series", "silver_observations")

#: Rows returned to the model. A larger result is truncated and says so, because
#: a silently cut table is a wrong answer with a plausible shape.
DEFAULT_MAX_ROWS = 500


class SqlRejected(ValueError):
    """The query did not pass a gate. The message is safe to show the model."""


class LakehouseArguments(BaseModel):
    """What the planner may ask for. `sql` is a proposal, not an instruction."""

    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1, max_length=8000)
    purpose: str = Field(default="", max_length=500)


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...] = field(repr=False)
    truncated: bool = False

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class LakehouseOutput:
    """What the tool hands back: the typed result, and the rows behind it.

    Both are needed and neither substitutes for the other. `result` is the
    verifiable part — values with units, periods and sample counts, carrying a
    digest M5 and M8 can check. `table` is presentation data for a table or a
    chart, and is what the model reads when it is looking rather than claiming.

    Keeping them apart is what stops a rendering convenience from becoming an
    analytical claim: nothing in `table` is evidence for anything.
    """

    result: AnalyticalResult
    table: QueryResult

    @property
    def truncated(self) -> bool:
        return self.table.truncated


def _statement_is_a_single_select(sql: str) -> None:
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as error:
        raise SqlRejected(f"SQL did not parse: {error}") from error
    if len(statements) != 1:
        raise SqlRejected(f"Expected one statement, got {len(statements)}")
    kind = str(statements[0].type).rsplit(".", 1)[-1]
    if kind != "SELECT":
        raise SqlRejected(f"Only SELECT is allowed here, got {kind}")


def _ast(connection: DuckDBPyConnection, sql: str) -> dict[str, Any]:
    row = connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()
    if row is None:  # pragma: no cover - the function always returns a row
        raise SqlRejected("SQL could not be analysed")
    document: dict[str, Any] = json.loads(row[0])
    if document.get("error"):
        raise SqlRejected(f"SQL did not parse: {document.get('error_message', 'unknown')}")
    return document


def _collect(node: object, *, key: str, out: list[Any]) -> None:
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for value in node.values():
            _collect(value, key=key, out=out)
    elif isinstance(node, list):
        for value in node:
            _collect(value, key=key, out=out)


def referenced_tables(ast: dict[str, Any]) -> set[str]:
    """Base tables in the query, excluding CTEs it defines itself."""
    nodes: list[Any] = []
    _collect(ast, key="type", out=nodes)
    if "TABLE_FUNCTION" in nodes:
        # This is how read_csv and read_parquet appear, and how SQL reaches disk.
        raise SqlRejected("Table functions are not allowed; query the tables directly")

    defined: set[str] = set()
    maps: list[Any] = []
    _collect(ast, key="cte_map", out=maps)
    for cte_map in maps:
        for entry in cte_map.get("map", []) if isinstance(cte_map, dict) else []:
            if isinstance(entry, dict) and isinstance(entry.get("key"), str):
                defined.add(entry["key"])

    tables: set[str] = set()
    _collect_base_tables(ast, tables)
    return {name for name in tables if name not in defined}


def _collect_base_tables(node: object, out: set[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "BASE_TABLE" and isinstance(node.get("table_name"), str):
            out.add(node["table_name"])
        for value in node.values():
            _collect_base_tables(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_base_tables(value, out)


def check_sql(
    connection: DuckDBPyConnection, sql: str, *, readable: Sequence[str] = DEFAULT_READABLE
) -> set[str]:
    """Run every static gate. Returns the tables the query will read."""
    _statement_is_a_single_select(sql)
    tables = referenced_tables(_ast(connection, sql))
    allowed = set(readable)
    forbidden = sorted(tables - allowed)
    if forbidden:
        raise SqlRejected(
            f"Not readable by this tool: {', '.join(forbidden)}. "
            f"Readable tables are {', '.join(sorted(allowed))}"
        )
    unknown = sorted(tables - set(all_tables()))
    if unknown:  # pragma: no cover - a whitelisted table is always a known one
        raise SqlRejected(f"Unknown tables: {', '.join(unknown)}")
    try:
        connection.execute(f"EXPLAIN {sql}")
    except duckdb.Error as error:
        raise SqlRejected(f"Query could not be planned: {error}") from error
    return tables


def run_query(
    connection: DuckDBPyConnection,
    sql: str,
    *,
    readable: Sequence[str] = DEFAULT_READABLE,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> QueryResult:
    """Validate, then execute on its own cursor.

    The cursor isolates this query's state from the caller's; the database-wide
    sandbox is what removes its capabilities.
    """
    check_sql(connection, sql, readable=readable)
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
        columns = tuple(str(item[0]) for item in cursor.description or ())
        rows = cursor.fetchmany(max_rows + 1)
    except duckdb.Error as error:
        raise SqlRejected(f"Query failed: {error}") from error
    finally:
        cursor.close()
    truncated = len(rows) > max_rows
    return QueryResult(columns, tuple(tuple(row) for row in rows[:max_rows]), truncated)


def make_lakehouse_tool(
    connection: DuckDBPyConnection,
    *,
    readable: Sequence[str] = DEFAULT_READABLE,
    max_rows: int = DEFAULT_MAX_ROWS,
    lineage: Lineage | None = None,
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data.

    When a `lineage` is supplied, each source-backed computed query is recorded as a
    transform node carrying the statement's hash, the tables it read and the
    shape it returned. That provenance is **table-level**: deriving which
    individual cells produced a result needs a full column analyzer, and
    claiming more than we compute would be worse than claiming less. M6-23
    checks direct column origins and exact stored identity before promotion;
    unsupported projections carry no result evidence or query lineage node.
    """

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments against this tool's schema before
        # dispatch, so this is a contract check rather than validation. It is
        # not an assert: asserts vanish under -O, and a runtime guarantee that
        # disappears in production is not a guarantee.
        if not isinstance(arguments, LakehouseArguments):  # pragma: no cover
            raise TypeError("lakehouse received arguments it did not declare")
        try:
            result = run_query(connection, arguments.sql, readable=readable, max_rows=max_rows)
        except SqlRejected as error:
            return ToolResult(
                ToolStatus.FAILURE,
                step_id="",
                tool="lakehouse",
                error_category="sql_rejected",
                warnings=(str(error),),
            )
        ast = _ast_of(arguments.sql)
        tables = sorted(referenced_tables(ast) & set(readable))
        snapshots: list[str] = []
        typed = _projection.project(
            result,
            ast=ast,
            connection=connection,
            result_id=_result_id(arguments, None),
            tables=tables,
            parameters={"purpose": arguments.purpose, "max_rows": max_rows},
            snapshots=snapshots,
        )
        node = None
        if typed.status is ResultStatus.COMPUTED:
            node = _record_query(lineage, arguments, result, tables)
            if node is not None and typed.evidence is not None:
                typed = typed.model_copy(
                    update={
                        "result_id": node,
                        "evidence": typed.evidence.model_copy(update={"lineage_node": node}),
                    }
                )
        typed = _record_execution(
            connection,
            producer="lakehouse",
            arguments=canonical(
                {
                    "sql_sha256": _statement_digest(arguments.sql),
                    "purpose": arguments.purpose,
                    "max_rows": max_rows,
                }
            ),
            inputs=snapshots,
            result=typed,
        )
        warnings = tuple(typed.warnings)
        if result.truncated:
            warnings = (f"Result truncated to {max_rows} rows; narrow the query", *warnings)
        if typed.status is not ResultStatus.COMPUTED and typed.reason is not None:
            # The query ran, so this is not a failure. It is a successful call
            # that established no measurement, and the model has to be told
            # which of the two happened or it will report the rows as a figure.
            warnings = (*warnings, typed.reason)
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="lakehouse",
            output=LakehouseOutput(result=typed, table=result),
            warnings=warnings,
            evidence=node,
        )

    return ToolSpec(
        name="lakehouse",
        description=_describe(readable),
        arguments=LakehouseArguments,
        run=run,
    )


def _describe(readable: Iterable[str]) -> str:
    return (
        "Run one read-only SELECT over the analysis tables. "
        f"Readable tables: {', '.join(sorted(readable))}. "
        "Only SELECT is accepted; no table functions, no writes, no other tables."
        " Measurements require direct columns: silver_observations o (series_id, period_start,"
        " period_end, value) joined to silver_series s (series_id, unit, scale, frequency,"
        " anchor, observation) on series_id, selecting o.series_id, o.period_start,"
        " o.period_end, o.value, s.unit and s.scale. unit and scale exist only on silver_series."
        " Expressions and other projections return inspection rows only, not financial evidence."
    )


def _statement_digest(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _result_id(arguments: LakehouseArguments, node: str | None) -> str:
    """A stable handle for this query's result.

    The lineage node when there is one, so a stored result and its provenance
    share a name. Otherwise the statement digest, which is stable across two
    identical queries and distinct between different ones.
    """
    return node if node is not None else f"lakehouse:{_statement_digest(arguments.sql)}"


def _record_query(
    lineage: Lineage | None,
    arguments: LakehouseArguments,
    result: QueryResult,
    tables: Sequence[str],
) -> str | None:
    """Record the query as a transform node, or return None when unrecorded."""
    if lineage is None:
        return None
    return lineage.record(
        NodeKind.TRANSFORM,
        "lakehouse_query",
        attributes={
            "sql_sha256": _statement_digest(arguments.sql),
            "purpose": arguments.purpose,
            "tables": ", ".join(tables),
            "columns": ", ".join(result.columns),
            "rows": str(result.row_count),
            "truncated": str(result.truncated).lower(),
            "provenance": (
                "table-level query record; direct column origins and stored row identity checked"
            ),
        },
    )


def _ast_of(sql: str) -> dict[str, Any]:
    """Re-parse for recording. Cheap, and keeps the record independent of state."""
    with duckdb.connect() as scratch:
        return _ast(scratch, sql)
