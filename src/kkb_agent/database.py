"""One place that knows every table this system creates.

The schema statements live next to the code that reads and writes them, which
keeps each table's rules beside its enforcement. But there has to be a single
answer to "what is in this database", or the deliverable the brief asks for gets
assembled from four modules by hand and drifts the first time someone adds a
table.

`TABLES` is that answer, `apply_schema` is the only thing that creates them, and
a test asserts the two agree with [DATABASE](../../docs/DATABASE.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: Every table, grouped by the layer that owns it. Adding a table here without
#: describing it in DATABASE.md fails the schema-documentation test.
TABLES: Mapping[str, tuple[str, ...]] = {
    "bronze": ("bronze_artifacts",),
    "silver": ("silver_series", "silver_observations"),
    "gold": ("gold_cells",),
    "lineage": ("lineage_nodes", "lineage_edges"),
    "workspace": ("workspace_artifacts", "workspace_bindings", "workspace_history"),
}


def all_tables() -> tuple[str, ...]:
    return tuple(sorted(name for group in TABLES.values() for name in group))


def schema_statements() -> tuple[str, ...]:
    """Every DDL block, in dependency order. Imported here to avoid a cycle."""
    from kkb_agent.agent.workspace import WORKSPACE_SCHEMA
    from kkb_agent.lakehouse.gold import GOLD_SCHEMA
    from kkb_agent.lakehouse.lineage import LINEAGE_SCHEMA
    from kkb_agent.lakehouse.store import SCHEMA

    return (SCHEMA, LINEAGE_SCHEMA, GOLD_SCHEMA, WORKSPACE_SCHEMA)


def apply_schema(connection: DuckDBPyConnection) -> tuple[str, ...]:
    """Create every table if absent, and return their names.

    Idempotent: every statement is `CREATE TABLE IF NOT EXISTS`, so reopening an
    existing database is a no-op rather than a migration.
    """
    for statement in schema_statements():
        connection.execute(statement)
    return all_tables()
