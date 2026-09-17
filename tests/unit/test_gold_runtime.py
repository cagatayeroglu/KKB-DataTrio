"""A published table reaches the store, not only the workspace (M12-13 at runtime).

Gold existed as a shape and a builder; nothing wrote it while the service ran, so
`gold_cells` was empty and SQL over published tables had nothing to read. These
tests pin the wiring: a turn that publishes a period table writes its columns
with a lineage node, a later turn can query them by identity, and a table that
cannot be written traceably leaves the store untouched instead of half-written.
"""

from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
from test_series_inspection import SQL

from kkb_agent.agent import Workspace
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.llm import scripted

CREDIT_VALUES = [100.0, 120.0, 150.0]


@pytest.fixture
def pool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def runner(pool, tmp_path, provider):
    return PreparedRunner(provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes())


def table_step(step_id="a", sql=SQL):
    return {"step_id": step_id, "tool": "lakehouse", "arguments": {"sql": sql}}


def test_a_published_table_is_written_to_gold_with_a_lineage_node(pool, tmp_path):
    prepared = runner(pool, tmp_path, scripted(proposal(table_step()), "Tablo hazır."))
    sid = uuid4().hex

    answer = prepared(sid, uuid4().hex, "Konut kredisi tablosunu getir.")

    assert answer.status.value == "accepted"
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        rows = lake.connection.execute(
            "SELECT table_id, column_name, period_end, value, column_node_id"
            " FROM gold_cells ORDER BY period_end"
        ).fetchall()
        assert [row[0] for row in rows] == ["analiz_1"] * 3
        assert {row[1] for row in rows} == {TOTAL}
        assert [row[3] for row in rows] == CREDIT_VALUES
        # Every cell carries a node that exists in the graph, not a free string.
        for row in rows:
            assert lake.lineage.node(row[4]) is not None


def test_a_derived_column_can_be_rechecked_against_the_store_afterwards(pool, tmp_path):
    """Why gold is written: a derived column had no stored row to be rechecked against.

    The recheck is a second read keyed on label and period, on a path the model
    did not write. Before this wiring it could only reach `silver_observations`,
    so a deflated or joined column was verifiable against context alone.
    """
    from kkb_agent.agent.verifier import recheck_against_store

    prepared = runner(pool, tmp_path, scripted(proposal(table_step()), "Tablo hazır."))
    sid = uuid4().hex
    prepared(sid, uuid4().hex, "Konut kredisi tablosunu getir.")

    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        published = workspace.value_of("analiz_1")
        assert recheck_against_store(published, lake.connection) == ()
        # Positive control: the recheck reads the store, not the result it is given.
        lake.connection.execute(
            "UPDATE gold_cells SET value = 999 WHERE period_end = DATE '2026-06-30'"
        )
        lake.connection.execute(
            "DELETE FROM silver_observations WHERE period_end = DATE '2026-06-30'"
        )
        faults = recheck_against_store(published, lake.connection)
        assert len(faults) == 1 and "999" in faults[0]


def test_a_turn_that_publishes_no_period_table_writes_no_cells(pool, tmp_path):
    """A single comparison is prose, not a table; gold stays empty rather than guessing."""
    from test_catalog_continuation import discover

    def calculate(step_id, **arguments):
        return {
            "step_id": step_id,
            "tool": "change_detection",
            "arguments": {"series_id": TOTAL, "operation": "compare", **arguments},
        }

    prepared = runner(
        pool,
        tmp_path,
        scripted(
            proposal(discover("d")),
            proposal(calculate("a", start="2026-04-30", end="2026-06-30")),
            "Nisan'dan Haziran 2026'ya konut kredisi stoğu 50 milyon TL arttı.",
        ),
    )
    sid = uuid4().hex

    answer = prepared(sid, uuid4().hex, "Nisan-Haziran 2026 konut kredisi ne kadar değişti?")

    assert answer.status.value == "accepted"
    with open_lakehouse(prepared.run_root / sid / "lake") as lake:
        assert lake.connection.execute("SELECT count(*) FROM gold_cells").fetchone()[0] == 0


def test_the_trace_says_what_was_written(pool, tmp_path):
    """The written table is visible in the turn's stored trace, like every other step."""
    from kkb_agent.api.store import ConversationStore

    store = ConversationStore(tmp_path / "conversations.sqlite")
    prepared = PreparedRunner(
        scripted(proposal(table_step()), "Tablo hazır."),
        pool,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
    )
    owner_id, token = store.create_owner()
    sid = uuid4().hex
    store.create_conversation(owner_id=owner_id, conversation_id=sid, token=token, title="Test")

    prepared(sid, uuid4().hex, "Konut kredisi tablosunu getir.")

    run = store.runs(sid)[0]
    written = [event for event in store.events(run.run_id) if event.name == "gold.materialized"]
    assert len(written) == 1
    detail = written[0].detail
    assert detail["table"] == "analiz_1"
    assert detail["rows"] == 3 and detail["columns"] == 1 and detail["incomplete"] == []
