"""Conservative source proof for M6-23; not a general SQL lineage engine.

Only direct silver observation/metadata projections are currently provable.
Filtering, ordering and limits select stored rows without manufacturing fields.
Aggregates, expressions, CTEs, subqueries and gold projections lack a complete
semantic identity in this contract and must not become COMPUTED measurements.
The SQL capability checks are separate and still run before this check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

    from kkb_agent.tools.lakehouse import QueryResult

_OBSERVATION_COLUMNS = frozenset({"series_id", "period_start", "period_end", "value"})
_SERIES_COLUMNS = frozenset(
    {
        "series_id",
        "title",
        "unit",
        "scale",
        "frequency",
        "anchor",
        "observation",
    }
)
_COLUMNS = {"silver_observations": _OBSERVATION_COLUMNS, "silver_series": _SERIES_COLUMNS}
_REQUIRED = frozenset({"series_id", "period_start", "period_end", "value", "unit", "scale"})
_STORED_COLUMNS = (
    "series_id",
    "period_start",
    "period_end",
    "value",
    "title",
    "unit",
    "scale",
    "frequency",
    "anchor",
    "observation",
)
_SHAPE_REASON = (
    "Unsupported projection provenance: use direct silver observation columns "
    "joined to silver_series by series_id, including series_id, period_start, "
    "period_end, value, unit and scale. Expressions, fabricated metadata and "
    "ambiguous identities cannot establish a measurement"
)


def _base_table(node: dict[str, Any]) -> tuple[str, str] | None:
    if (
        node.get("type") != "BASE_TABLE"
        or node.get("schema_name") not in ("", "main")
        or node.get("catalog_name") != ""
        or node.get("column_name_alias")
        or node.get("sample")
        or node.get("at_clause")
    ):
        return None
    table = node.get("table_name")
    if table not in _COLUMNS:
        return None
    return node.get("alias") or table, table


def _column(expression: dict[str, Any], sources: dict[str, str]) -> tuple[str, str] | None:
    if expression.get("class") != "COLUMN_REF":
        return None
    names = expression.get("column_names", [])
    if len(names) == 2:
        table = sources.get(names[0])
        if table in _COLUMNS and names[1] in _COLUMNS[table]:
            return table, names[1]
    elif len(names) == 1:
        candidates = {table for table in sources.values() if names[0] in _COLUMNS[table]}
        # USING(series_id) and our checked equality join establish the same id.
        if names[0] == "series_id" and candidates:
            return "silver_observations", "series_id"
        if len(candidates) == 1:
            return candidates.pop(), names[0]
    return None


def _sources(node: dict[str, Any]) -> dict[str, str] | None:
    if (
        node.get("type") != "JOIN"
        or node.get("join_type") != "INNER"
        or node.get("ref_type") != "REGULAR"
        or node.get("alias")
        or node.get("sample")
    ):
        return None
    left = _base_table(node.get("left", {}))
    right = _base_table(node.get("right", {}))
    if left is None or right is None or left[0] == right[0]:
        return None
    sources = dict((left, right))
    if set(sources.values()) != set(_COLUMNS):
        return None
    condition = node.get("condition")
    if node.get("using_columns") == ["series_id"] and condition is None:
        return sources
    if not isinstance(condition, dict) or condition.get("type") != "COMPARE_EQUAL":
        return None
    compared = {
        _column(condition.get("left", {}), sources),
        _column(condition.get("right", {}), sources),
    }
    if compared != {("silver_series", "series_id"), ("silver_observations", "series_id")}:
        return None
    return sources


def provenance_fault(
    query: QueryResult, ast: dict[str, Any], connection: DuckDBPyConnection
) -> str | None:
    """Prove column origins, then exact stored identity; absence never passes.

    A magnitude-only recheck would accept a literal equal to a stored value.
    Conversely, column origins alone would miss mismatched identity/metadata.
    Both checks are necessary before any evidence is attached to a result.
    """
    statements = ast.get("statements", [])
    if len(statements) != 1:
        return _SHAPE_REASON
    node = statements[0].get("node", {})
    if (
        node.get("type") != "SELECT_NODE"
        or node.get("cte_map", {}).get("map")
        or node.get("group_expressions")
        or node.get("group_sets")
        or node.get("having")
        or node.get("qualify")
        or node.get("sample")
    ):
        return _SHAPE_REASON
    sources = _sources(node.get("from_table", {}))
    if sources is None:
        return _SHAPE_REASON
    expressions = node.get("select_list", [])
    if len(expressions) != len(query.columns) or len(set(query.columns)) != len(query.columns):
        return _SHAPE_REASON
    if not _REQUIRED.issubset(query.columns):
        return _SHAPE_REASON
    for name, expression in zip(query.columns, expressions, strict=True):
        origin = _column(expression, sources)
        if origin is None or origin[1] != name:
            return _SHAPE_REASON

    positions = {name: i for i, name in enumerate(query.columns)}
    for row in query.rows:
        stored = connection.execute(
            "SELECT o.series_id, o.period_start, o.period_end, o.value, s.title, "
            "s.unit, s.scale, s.frequency, s.anchor, s.observation "
            "FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id "
            "WHERE o.series_id = ? AND o.period_end = ?",
            [row[positions["series_id"]], row[positions["period_end"]]],
        ).fetchone()
        if stored is None:
            return "Projection identity resolves to no stored observation; no evidence established"
        by_name = dict(zip(_STORED_COLUMNS, stored, strict=True))
        if any(row[i] != by_name[name] for name, i in positions.items()):
            return (
                "Projection differs from its stored value, period or semantics; "
                "no evidence established"
            )
    return None
