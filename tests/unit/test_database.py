"""The database definition and the schema must not drift apart.

Database definitions are a listed deliverable, and a document that describes a
schema nobody checks is worse than none: it reads as authoritative while being
wrong. These tests fail when a table is added, renamed or removed without the
document following.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest

from kkb_agent.database import TABLES, all_tables, apply_schema, schema_statements

DOCUMENT = Path(__file__).resolve().parents[2] / "docs/DATABASE.md"


@pytest.fixture(scope="module")
def created():
    with duckdb.connect() as connection:
        apply_schema(connection)
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        yield sorted(str(row[0]) for row in rows)


@pytest.fixture(scope="module")
def document():
    return DOCUMENT.read_text(encoding="utf-8")


class TestTheSchemaMatchesItsRegistry:
    def test_every_registered_table_is_created(self, created):
        assert created == list(all_tables())

    def test_the_registry_has_no_duplicates(self):
        names = [name for group in TABLES.values() for name in group]
        assert len(names) == len(set(names))

    def test_applying_twice_is_a_no_op(self):
        with duckdb.connect() as connection:
            first = apply_schema(connection)
            second = apply_schema(connection)
        assert first == second

    def test_every_statement_only_creates_if_absent(self):
        # A migration would silently discard a demo-day database.
        for statement in schema_statements():
            creates = re.findall(r"CREATE TABLE(?! IF NOT EXISTS)", statement)
            assert not creates


class TestTheDocumentMatchesTheSchema:
    def test_every_table_has_a_heading(self, created, document):
        missing = [name for name in created if f"### `{name}`" not in document]
        assert missing == [], f"Undocumented tables: {missing}"

    def test_the_document_describes_no_table_that_does_not_exist(self, created, document):
        documented = set(re.findall(r"^### `(\w+)`", document, re.MULTILINE))
        assert documented - set(created) == set()

    def test_every_column_is_documented(self, created, document):
        with duckdb.connect() as connection:
            apply_schema(connection)
            for table in created:
                columns = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                        [table],
                    ).fetchall()
                }
                section = _section(document, table)
                undocumented = sorted(name for name in columns if f"| `{name}` |" not in section)
                assert undocumented == [], f"{table}: {undocumented}"

    def test_each_layer_is_introduced(self, document):
        for layer in TABLES:
            assert re.search(rf"^## {layer} — ", document, re.MULTILINE), layer


def _section(document: str, table: str) -> str:
    """The document text belonging to one table's heading."""
    start = document.index(f"### `{table}`")
    following = document.find("\n### ", start + 1)
    layer = document.find("\n## ", start + 1)
    end = min(position for position in (following, layer, len(document)) if position != -1)
    return document[start:end]
