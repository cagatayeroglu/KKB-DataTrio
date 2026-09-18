"""The knowledge base: append-only user datasets and notes over the reviewed catalog."""

from dataclasses import replace
from datetime import date

import pytest
from test_catalog_continuation import CATALOG, TOTAL

from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.knowledge import (
    DatasetVersion,
    KnowledgeError,
    KnowledgeStore,
    effective_snapshot,
)
from kkb_agent.lakehouse.records import Observation

REVIEWED = load_reviewed_snapshot(CATALOG.read_bytes())


def monthly(values, start_year=2025):
    found = []
    for index, value in enumerate(values):
        year, month = divmod(index, 12)
        year += start_year
        month += 1
        following = date(year + (month == 12), month % 12 + 1, 1)
        found.append(
            Observation(date(year, month, 1), date.fromordinal(following.toordinal() - 1), value)
        )
    return tuple(found)


def dataset(**change):
    base = DatasetVersion(
        slug="kart_harcamalari",
        version=0,
        title="Kredi kartı harcamaları",
        unit="TRY",
        scale=Scale.MILLION,
        frequency=Frequency.MONTHLY,
        stock_flow=StockFlow.FLOW,
        cumulative=CumulativeKind.NONE,
        aggregation=Aggregation.SUM,
        observations=monthly([100.0, 110.0, 125.0]),
        source_kind="manual",
        aliases=("kart harcaması", "kredi kartı"),
    )
    return replace(base, **change)


@pytest.fixture
def store(tmp_path):
    opened = KnowledgeStore(tmp_path / "knowledge.sqlite")
    yield opened
    opened.close()


def test_every_edit_is_a_new_version_and_the_old_one_stays_readable(store):
    first = store.save_dataset(dataset())
    assert (first.version, first.series_id) == (1, "USER:kart_harcamalari.v1")
    # Saying the same thing again is not a new version.
    assert store.save_dataset(dataset()).version == 1

    second = store.save_dataset(dataset(observations=monthly([100.0, 111.0, 125.0])))
    assert second.version == 2 and second.series_id == "USER:kart_harcamalari.v2"
    assert store.dataset("kart_harcamalari", 1).observations[1].value == 110.0
    assert [item.version for item in store.dataset_history("kart_harcamalari")] == [1, 2]


def test_deleting_is_archiving_and_can_be_undone(store):
    store.save_dataset(dataset())
    archived = store.set_dataset_status("kart_harcamalari", "archived", author="o")
    assert archived.status == "archived" and archived.version == 2
    assert store.datasets(include_archived=False) == []
    restored = store.set_dataset_status("kart_harcamalari", "active", author="o")
    assert restored.status == "active" and restored.version == 3
    assert len(store.dataset_history("kart_harcamalari")) == 3  # nothing was removed


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"slug": "Kart"}, "invalid_slug"),
        ({"slug": "synthetic_card"}, "invalid_slug"),  # the reviewed contract refuses it
        ({"scale": Scale.UNKNOWN}, "unresolved_semantics"),
        ({"stock_flow": StockFlow.UNKNOWN}, "unresolved_semantics"),
        ({"observations": ()}, "no_observations"),
        (
            {"observations": (Observation(date(2025, 1, 1), date(2025, 1, 15), 1.0),)},
            "period_does_not_match_frequency",
        ),
        ({"observations": monthly([1.0]) * 2}, "duplicate_period"),
        ({"aliases": tuple(f"ad {i}" for i in range(11))}, "too_many_aliases"),
    ],
)
def test_a_dataset_that_cannot_be_stored_honestly_is_refused(store, change, code):
    with pytest.raises(KnowledgeError, match=code):
        store.save_dataset(dataset(**change))
    assert store.datasets() == []


def test_an_empty_knowledge_base_leaves_the_reviewed_catalog_untouched():
    assert effective_snapshot(REVIEWED, [], []) is REVIEWED


def test_a_user_dataset_becomes_a_discoverable_marked_catalog_series(store):
    saved = store.save_dataset(dataset())
    snapshot = effective_snapshot(REVIEWED, store.datasets(), store.notes())

    assert snapshot.content_sha256 != REVIEWED.content_sha256
    (entry,) = [s for s in snapshot.series if s.record.series_id == saved.series_id]
    assert entry.record.provider == "USER"
    assert entry.record.source.source_type == "user-declared"
    assert "not reviewed" in entry.note
    assert (entry.record.unit, entry.record.scale, entry.record.stock_flow) == (
        "TRY",
        Scale.MILLION,
        StockFlow.FLOW,
    )
    # Reviewed entries are carried over unchanged.
    assert {s.record.series_id for s in REVIEWED.series} < {
        s.record.series_id for s in snapshot.series
    }
    found = search_catalog(snapshot, CatalogSearchArguments(query="kredi kartı harcamaları"))
    assert saved.series_id in [c.series.record.series_id for c in found.candidates]
    # The same state gives the same digest: nothing time-dependent is hashed.
    assert effective_snapshot(REVIEWED, store.datasets(), store.notes()) == snapshot


def test_archiving_a_reviewed_series_takes_it_out_of_search_and_computation(store):
    before = search_catalog(REVIEWED, CatalogSearchArguments(query="toplam konut kredisi"))
    assert TOTAL in [c.series.record.series_id for c in before.candidates]

    store.annotate(TOTAL, archived=True, note="Bu hackathon için kullanılmayacak", author="o")
    snapshot = effective_snapshot(REVIEWED, store.datasets(), store.notes())
    (entry,) = [s for s in snapshot.series if s.record.series_id == TOTAL]
    assert entry.record.status is CatalogStatus.ARCHIVED
    after = search_catalog(snapshot, CatalogSearchArguments(query="toplam konut kredisi"))
    assert TOTAL not in [c.series.record.series_id for c in after.candidates]

    # Restoring is another version, and the series is back.
    store.annotate(TOTAL, archived=False, author="o")
    assert effective_snapshot(REVIEWED, store.datasets(), store.notes()) is REVIEWED
    assert [n.archived for n in store.note_history(TOTAL)] == [True, False]


def test_a_user_alias_resolves_the_word_the_team_uses_to_one_series(store):
    """ "mortgage stoku" alone is ambiguous between the TL, FX and total balances."""
    query = CatalogSearchArguments(query="mortgage stoku")
    before = search_catalog(REVIEWED, query)
    assert before.status == "PARTIAL" and len(before.candidates) > 1

    store.annotate(TOTAL, archived=False, aliases=("mortgage stoku",), author="o")
    after = search_catalog(effective_snapshot(REVIEWED, store.datasets(), store.notes()), query)

    assert after.status == "MATCH"
    (only,) = after.candidates
    assert only.series.record.series_id == TOTAL
    assert f"user-alias:{TOTAL}" in only.concept_ids  # the trace shows it came from a person


def test_the_inspector_accepts_a_user_series_whose_store_matches_its_declaration(store, tmp_path):
    """The same gate as a reviewed series: the stored declaration must equal the record."""
    from datetime import UTC, datetime

    from kkb_agent.core import SourceRef
    from kkb_agent.lakehouse import open_lakehouse

    saved = store.save_dataset(dataset())
    snapshot = effective_snapshot(REVIEWED, store.datasets(), store.notes())
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b"declared",
            source=SourceRef(source_id="knowledge", source_type="user-declared", locator="k:1"),
            media_type="application/json",
            recorded_at=datetime(2026, 9, 18, tzinfo=UTC),
        )
        lake.register_series(
            saved.series_id,
            title=saved.title,
            semantics=saved.semantics(),
            artifact_id=artifact.artifact_id,
        )
        inspector = PreparedSeriesInspector(snapshot)
        assert inspector.inspect(lake.connection, saved.series_id).status == "consistent"


def _served(pool, tmp_path, store, *responses):
    from kkb_agent.api.prepared import PreparedRunner
    from kkb_agent.api.store import ConversationStore
    from kkb_agent.llm import scripted

    conversations = ConversationStore(tmp_path / "conversations.sqlite")
    runner = PreparedRunner(
        scripted(*responses),
        pool,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=conversations,
        knowledge=store,
    )
    return runner, conversations


@pytest.fixture
def pool(tmp_path):
    from test_catalog_continuation import seed_prepared

    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def test_a_question_is_answered_from_a_dataset_the_person_added(pool, tmp_path, store):
    from uuid import uuid4

    from test_catalog_continuation import proposal

    saved = store.save_dataset(dataset())
    search = {
        "step_id": "d",
        "tool": "catalog_search",
        "arguments": {"query": "kredi kartı harcamaları"},
    }
    compare = {
        "step_id": "a",
        "tool": "change_detection",
        "arguments": {
            "operation": "compare",
            "series_id": saved.series_id,
            "start": "2025-01-31",
            "end": "2025-03-31",
        },
    }
    runner, conversations = _served(
        pool,
        tmp_path,
        store,
        proposal(search),
        proposal(compare),
        "Ocak'tan Mart 2025'e kredi kartı harcamaları 25 milyon TL arttı.",
    )
    owner_id, token = conversations.create_owner()
    sid = uuid4().hex
    conversations.create_conversation(
        owner_id=owner_id, conversation_id=sid, token=token, title="Test"
    )

    answer = runner(sid, uuid4().hex, "Ocak-Mart 2025 kredi kartı harcamaları ne kadar değişti?")

    assert answer.status.value == "accepted", answer
    events = conversations.events(conversations.runs(sid)[0].run_id)
    (applied,) = [e for e in events if e.name == "knowledge.applied"]
    assert applied.attributes["loaded_datasets"] == [saved.series_id]
    assert applied.attributes["reviewed"] is False
    # The seed is untouched: the dataset lives in this conversation's own lake.
    from kkb_agent.lakehouse import open_lakehouse

    with open_lakehouse(pool) as seed:
        assert (
            seed.connection.execute(
                "SELECT count(*) FROM silver_series WHERE series_id = ?", [saved.series_id]
            ).fetchone()[0]
            == 0
        )


def test_an_archived_reviewed_series_cannot_be_computed_on(pool, tmp_path, store):
    from uuid import uuid4

    from test_catalog_continuation import proposal

    store.annotate(TOTAL, archived=True, author="o")
    compare = {
        "step_id": "a",
        "tool": "change_detection",
        "arguments": {
            "operation": "compare",
            "series_id": TOTAL,
            "start": "2026-04-30",
            "end": "2026-06-30",
        },
    }
    search = {"step_id": "d", "tool": "catalog_search", "arguments": {"query": "konut kredisi"}}
    runner, conversations = _served(pool, tmp_path, store, proposal(search), proposal(compare))
    owner_id, token = conversations.create_owner()
    sid = uuid4().hex
    conversations.create_conversation(
        owner_id=owner_id, conversation_id=sid, token=token, title="Test"
    )
    answer = runner(sid, uuid4().hex, "Nisan-Haziran 2026 konut kredisi?")
    assert answer.status.value == "abstained" and answer.result is None
    # The refusal names the archive, so the trace says why it was not computed.
    events = conversations.events(conversations.runs(sid)[0].run_id)
    assert any("archived" in json_text(e) for e in events)


def json_text(event):
    import json

    return json.dumps([event.attributes, event.detail], ensure_ascii=False, default=str)
