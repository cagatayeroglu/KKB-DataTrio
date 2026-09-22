"""The knowledge base over HTTP: everything visible, every change a version (DEC-157)."""

import pytest
from fastapi.testclient import TestClient
from test_catalog_continuation import CATALOG, TOTAL
from test_conversation_persistence import open_conversation, owner, upload
from test_document_dataset import ADMISSIONS, BASE, seed

from kkb_agent.api.app import create_app
from kkb_agent.api.contracts import SeriesNoteRequest
from kkb_agent.api.knowledge_service import KnowledgeService
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService, ServiceError
from kkb_agent.api.store import DATABASE_NAME, ConversationStore
from kkb_agent.knowledge import KnowledgeStore
from kkb_agent.llm import scripted

#: The consumer price index (2025=100): what one alias turned into "toplam konut kredisi".
CPI = "EVDS:TP.TUKFIY2025.GENEL"
READ_ONLY = {"api_version": 1, "error": "catalog_read_only"}


def served(tmp_path, *, catalog_edits):
    """The knowledge routes over a seeded pool; `catalog_edits` is the operator's flag."""
    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        store=store,
        knowledge=knowledge,
    )
    service = AnalysisService(
        runner,
        mode="scripted",
        document_store=runner.admit_document,
        store=store,
        knowledge=True,
    )
    knowledge_service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        read_document_column=runner.document_column,
        series_values=runner.series_values,
        catalog_edits=catalog_edits,
    )
    client = TestClient(
        create_app(service, prepared=runner.status, knowledge=knowledge_service), base_url=BASE
    )
    client.runner = runner  # type: ignore[attr-defined]
    client.stores = (store, knowledge)  # type: ignore[attr-defined]
    try:
        with client:
            yield client
    finally:
        store.close()
        knowledge.close()


@pytest.fixture
def api(tmp_path):
    # Started with --allow-catalog-edits: these tests are about what a permitted edit does.
    yield from served(tmp_path, catalog_edits=True)


@pytest.fixture
def read_only_api(tmp_path):
    # Started as `serve` starts by default: every key reads the notes, none changes them.
    yield from served(tmp_path, catalog_edits=False)


def manual(**change):
    return {
        "slug": "kart_harcamalari",
        "title": "Kredi kartı harcamaları",
        "unit": "TRY",
        "scale": "million",
        "frequency": "monthly",
        "stock_flow": "flow",
        "aggregation": "sum",
        "aliases": ["kart harcaması"],
        "observations": [
            {"period_end": "2025-01-31", "value": 100.0},
            {"period_end": "2025-02-28", "value": 110.0},
            {"period_end": "2025-03-31", "value": None},
        ],
        **change,
    }


def test_the_listing_shows_every_reviewed_series_and_where_it_stands(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    listed = api.get("/v1/knowledge", headers=key).json()
    assert listed["catalog_digest"] == listed["reviewed_digest"]  # nothing added yet
    by_id = {item["series_id"]: item for item in listed["series"]}
    assert by_id[TOTAL]["prepared"] is True and by_id[TOTAL]["origin"] == "reviewed"
    assert any(not item["prepared"] for item in listed["series"])  # catalog-only entries show
    assert "knowledge_base" in api.get("/v1/health").json()["capabilities"]


def test_a_manual_dataset_is_saved_versioned_archived_and_restored(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    created = api.post("/v1/knowledge/datasets", json=manual(), headers=key)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["series"]["series_id"] == "USER:kart_harcamalari.v1"
    assert [o["value"] for o in body["observations"]] == [100.0, 110.0, None]
    assert body["observations"][0]["period_start"] == "2025-01-01"

    edited = api.post(
        "/v1/knowledge/datasets", json=manual(title="Kart harcamaları (TL)"), headers=key
    ).json()
    assert edited["series"]["version"] == 2 and len(edited["history"]) == 2

    listed = api.get("/v1/knowledge", headers=key).json()
    assert listed["catalog_digest"] != listed["reviewed_digest"]

    archived = api.post(
        "/v1/knowledge/datasets/kart_harcamalari/archive", json={}, headers=key
    ).json()
    assert archived["series"]["status"] == "archived"
    # Editing an archived dataset keeps it archived: an edit is not a restore.
    still = api.post("/v1/knowledge/datasets", json=manual(title="Başka"), headers=key).json()
    assert still["series"]["status"] == "archived"
    restored = api.post(
        "/v1/knowledge/datasets/kart_harcamalari/restore", json={}, headers=key
    ).json()
    assert restored["series"]["status"] == "active"
    assert [v["status"] for v in restored["history"]] == [
        "active",
        "active",
        "archived",
        "archived",
        "active",
    ]


def test_a_dataset_is_read_from_a_table_uploaded_to_a_conversation(api):
    token = owner(api)
    sid, headers, _ = open_conversation(api, token)
    document_ref = upload(api, sid, headers)
    request = manual(
        slug="basvurular",
        title="Aylık başvuru sayısı",
        unit="count",
        scale="one",
        stock_flow="flow",
        observations=[],
        document={
            "session_id": sid,
            "document_ref": document_ref,
            "period_column": "Ay",
            "value_column": "Başvuru Sayısı",
        },
    )
    saved = api.post("/v1/knowledge/datasets", json=request, headers={"X-KKB-Owner-Token": token})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert [o["value"] for o in body["observations"]] == [float(v) for v in ADMISSIONS]
    assert body["source_kind"] == "upload"

    # Another browser's key cannot read a table from this conversation.
    stranger = {"X-KKB-Owner-Token": owner(api)}
    refused = api.post(
        "/v1/knowledge/datasets", json={**request, "slug": "baska"}, headers=stranger
    )
    assert refused.status_code == 422


def test_a_reviewed_series_is_archived_and_annotated_with_its_history(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    path = f"/v1/knowledge/series/{TOTAL}/notes"
    first = api.post(
        path,
        json={"archived": True, "aliases": ["mortgage stoku"], "note": "Kullanma"},
        headers=key,
    )
    assert first.status_code == 200, first.text
    second = api.post(path, json={"archived": False, "aliases": ["mortgage stoku"]}, headers=key)
    assert [v["archived"] for v in second.json()["history"]] == [True, False]
    entry = next(
        item
        for item in api.get("/v1/knowledge", headers=key).json()["series"]
        if item["series_id"] == TOTAL
    )
    # Restored: no longer archived; the catalog's own status for it is "unknown".
    assert entry["status"] != "archived" and entry["aliases"] == ["mortgage stoku"]
    # An identity from neither tier still takes no note.
    assert (
        api.post(
            "/v1/knowledge/series/EVDS:NOPE/notes", json={"archived": True}, headers=key
        ).status_code
        == 404
    )


def test_a_source_directory_record_takes_a_note_like_a_reviewed_one(tmp_path):
    """The overlay applies notes to directory records; the route refused them.

    So the page's own edit form answered 404 and nothing happened, although the
    counter next to it says these records can be annotated (finding F4-bt-7).
    """
    from kkb_agent.catalog.directory import source_directory
    from kkb_agent.catalog.mappings import load_reviewed_snapshot

    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    _, token = store.create_owner()
    directory = source_directory()
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        source_directory=directory,
        catalog_edits=True,
    )
    try:
        reviewed = {series.record.series_id for series in service._reviewed.series}
        listed = sorted(directory.ids() - reviewed)
        assert listed, "the directory must carry records of its own"
        history = service.annotate(
            token,
            listed[0],
            SeriesNoteRequest(archived=False, aliases=("kendi adım",), note="Bunu ben adlandırdım"),
        )
        assert [v.aliases for v in history.history] == [("kendi adım",)]
        entry = next(item for item in service.listing(token).series if item.series_id == listed[0])
        assert entry.aliases == ("kendi adım",) and entry.origin == "listed"
        with pytest.raises(ServiceError):
            service.annotate(token, "EVDS:NOPE", SeriesNoteRequest(archived=True))
    finally:
        store.close()
        knowledge.close()


#: Each kind of catalogue note the page can send: an archive, synonyms, a description.
NOTE_CHANGES = (
    {"archived": True},
    {"archived": False, "aliases": ["mortgage stoku"]},
    {"archived": False, "note": "Bankaların ipotekli finansman alacakları"},
)


def test_without_the_operator_s_flag_no_key_changes_a_catalogue_note(read_only_api):
    """A note applies to every key's catalogue, so it is the operator's (finding N43)."""
    client = read_only_api
    _, knowledge = client.stores
    key = {"X-KKB-Owner-Token": owner(client)}
    path = f"/v1/knowledge/series/{TOTAL}/notes"
    before = client.get("/v1/knowledge", headers=key).json()
    assert before["catalog_editable"] is False
    for change in NOTE_CHANGES:
        refused = client.post(path, json=change, headers=key)
        assert (refused.status_code, refused.json()) == (403, READ_ONLY), change
    # Nothing was written: no version, the same catalogue, and the history still reads.
    assert knowledge.note_history(TOTAL) == [] and knowledge.notes() == []
    after = client.get("/v1/knowledge", headers=key).json()
    assert after["catalog_digest"] == before["catalog_digest"] == before["reviewed_digest"]
    assert client.get(path, headers=key).json()["history"] == []
    # Refused only after the key and the series are known: those still read as not found.
    stranger = client.post(path, json={"archived": True}, headers={"X-KKB-Owner-Token": "x" * 43})
    assert (stranger.status_code, stranger.json()["error"]) == (404, "not_found")
    unknown = client.post(
        "/v1/knowledge/series/EVDS:NOPE/notes", json={"archived": True}, headers=key
    )
    assert (unknown.status_code, unknown.json()["error"]) == (404, "not_found")
    assert knowledge.notes() == []


def test_a_listed_entry_is_read_only_too_and_the_service_fails_closed(tmp_path):
    """No `catalog_edits` given, as a caller that forgot the operator's flag would do."""
    from kkb_agent.catalog.directory import source_directory
    from kkb_agent.catalog.mappings import load_reviewed_snapshot

    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    _, token = store.create_owner()
    directory = source_directory()
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        source_directory=directory,
    )
    try:
        reviewed = {series.record.series_id for series in service._reviewed.series}
        listed = sorted(directory.ids() - reviewed)[0]
        before = service._effective().content_sha256
        for change in NOTE_CHANGES:
            with pytest.raises(ServiceError) as refused:
                service.annotate(token, listed, SeriesNoteRequest.model_validate(change))
            assert (refused.value.code, refused.value.status) == ("catalog_read_only", 403)
        assert knowledge.notes() == [] and service._effective().content_sha256 == before
    finally:
        store.close()
        knowledge.close()


def test_one_browser_cannot_rewrite_the_catalogue_every_other_browser_searches(read_only_api):
    """Finding N43, reproduced 2026-09-22 before this refusal existed.

    Owner B, with a key from the unauthenticated POST /v1/owner, archived the housing-loan
    TOTAL out of owner A's "konut kredisi bakiyesi" search, and one alias on TÜFE made it
    the single unambiguous candidate for "toplam konut kredisi".
    """
    client = read_only_api
    a = {"X-KKB-Owner-Token": owner(client)}
    b = {"X-KKB-Owner-Token": owner(client)}
    archive = client.post(f"/v1/knowledge/series/{TOTAL}/notes", json={"archived": True}, headers=b)
    alias = client.post(
        f"/v1/knowledge/series/{CPI}/notes",
        json={"archived": False, "aliases": ["toplam konut kredisi"]},
        headers=b,
    )
    assert (archive.status_code, archive.json()) == (403, READ_ONLY)
    assert (alias.status_code, alias.json()) == (403, READ_ONLY)

    def search(question):
        return client.get("/v1/knowledge/search", params={"q": question}, headers=a).json()

    balance = search("konut kredisi bakiyesi")
    assert [hit["series_id"] for hit in balance["hits"]][:1] == [TOTAL]
    assert balance["top_candidate"] == "unambiguous"
    total = search("toplam konut kredisi")
    assert [hit["series_id"] for hit in total["hits"]][:1] == [TOTAL]
    assert CPI not in {hit["series_id"] for hit in total["hits"]}


def test_the_note_history_says_whether_the_reading_key_wrote_each_version(api):
    """The store kept each version's author and the history showed none (finding N43)."""
    conversations, knowledge = api.stores
    mine, theirs = owner(api), owner(api)
    path = f"/v1/knowledge/series/{TOTAL}/notes"
    assert api.get("/v1/knowledge", headers={"X-KKB-Owner-Token": mine}).json()["catalog_editable"]
    written = api.post(
        path,
        json={"archived": False, "aliases": ["mortgage stoku"]},
        headers={"X-KKB-Owner-Token": mine},
    )
    assert written.status_code == 200, written.text
    assert [v["by_you"] for v in written.json()["history"]] == [True]
    other = api.post(path, json={"archived": True}, headers={"X-KKB-Owner-Token": theirs})
    assert [v["by_you"] for v in other.json()["history"]] == [False, True]
    # A row stored without an author says nothing about who wrote it.
    knowledge.annotate(TOTAL, archived=False, aliases=("eski",), author=None)
    history = api.get(path, headers={"X-KKB-Owner-Token": mine})
    assert [v["by_you"] for v in history.json()["history"]] == [True, False, None]
    # Only the comparison travels, never the owner ids it was made with.
    assert all("author" not in version for version in history.json()["history"])
    for token in (mine, theirs):
        assert conversations.owner_by_token(token) not in history.text


@pytest.mark.parametrize(
    ("flag", "editable"),
    [({}, False), ({"catalog_edits": False}, False), ({"catalog_edits": True}, True)],
)
def test_the_listing_says_whether_this_installation_takes_catalogue_notes(tmp_path, flag, editable):
    from kkb_agent.catalog.mappings import load_reviewed_snapshot

    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    _, token = store.create_owner()
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        **flag,
    )
    try:
        assert service.listing(token).catalog_editable is editable
        assert service.listing(token, tab="reviewed", page=1).catalog_editable is editable
    finally:
        store.close()
        knowledge.close()


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"slug": "Bad Slug"}, 422),
        ({"scale": "unknown"}, 422),
        ({"frequency": "weekly"}, 422),
        ({"observations": [{"period_end": "2025-01-15", "value": 1.0}]}, 422),
        ({"observations": []}, 422),  # neither observations nor a document
    ],
)
def test_a_dataset_that_cannot_be_stored_honestly_is_refused(api, change, status):
    key = {"X-KKB-Owner-Token": owner(api)}
    assert (
        api.post("/v1/knowledge/datasets", json=manual(**change), headers=key).status_code == status
    )
    listed = api.get("/v1/knowledge", headers=key).json()
    assert not [item for item in listed["series"] if item["origin"] == "user"]


def test_nothing_is_readable_or_writable_without_a_key(api):
    assert api.get("/v1/knowledge").status_code == 422
    assert api.get("/v1/knowledge", headers={"X-KKB-Owner-Token": "x" * 43}).status_code == 404
    assert (
        api.post(
            "/v1/knowledge/datasets", json=manual(), headers={"X-KKB-Owner-Token": "x" * 43}
        ).status_code
        == 404
    )


def test_only_the_dataset_route_accepts_a_large_body(api):
    key = {"X-KKB-Owner-Token": owner(api), "Content-Type": "application/json"}
    big = b'{"archived": true, "note": "' + b"a" * 20_000 + b'"}'
    assert (
        api.post(f"/v1/knowledge/series/{TOTAL}/notes", content=big, headers=key).status_code == 413
    )
    rows = [{"period_end": f"{2000 + i // 12}-{i % 12 + 1:02d}-28", "value": 1.0} for i in range(3)]
    assert len(str(rows)) < 1024 * 1024
    too_big = b'{"slug": "' + b"a" * (1024 * 1024) + b'"}'
    assert api.post("/v1/knowledge/datasets", content=too_big, headers=key).status_code == 413


def test_the_listing_says_which_series_can_be_fetched_and_when_one_was(tmp_path):
    """BDDK components and EVDS codes with a reviewed route are fetchable; a fetch is dated."""
    from kkb_agent.catalog.mappings import load_reviewed_snapshot
    from kkb_agent.ingest.acquisition import REVIEWED_SELECTORS

    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    owner_id, token = store.create_owner()
    (tp,) = [sid for sid, sel in REVIEWED_SELECTORS.items() if sel.value_dimension == "TP"]
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        acquisition=True,
        acquisitions=lambda: {"EVDS:TP.KFE.TR": {"fetched_at": "2026-09-18T08:00:00+00:00"}},
    )
    try:
        by_id = {item.series_id: item for item in service.listing(token).series}
        assert by_id[tp].fetchable and not by_id[tp].prepared
        assert by_id["EVDS:TP.KFE.TR"].acquired_at is not None
        assert by_id["EVDS:TP.KFE.TR10"].fetchable is False  # no reviewed route
        assert by_id[TOTAL].fetchable is False  # already prepared
    finally:
        store.close()
        knowledge.close()


def test_a_prepared_series_values_are_visible_and_reading_them_changes_nothing(api):
    from test_document_dataset import CREDIT

    from kkb_agent.api.prepared import manifest

    runner = api.runner
    before = manifest(runner.seed)
    key = {"X-KKB-Owner-Token": owner(api)}

    shown = api.get(f"/v1/knowledge/series/{TOTAL}/values", headers=key)
    assert shown.status_code == 200, shown.text
    values = [item["value"] for item in shown.json()["observations"]]
    assert values == CREDIT
    # Catalog-only series have no stored values to show.
    assert api.get("/v1/knowledge/series/EVDS:TP.KFE.TR/values", headers=key).status_code == 404
    # The verified seed is opened read-only: its manifest is exactly as before.
    assert manifest(runner.seed) == before


def test_a_weekly_dataset_needs_its_anchor_and_periods_that_end_on_it(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    weekly = manual(
        slug="haftalik_mevduat",
        title="Haftalık mevduat",
        frequency="weekly",
        weekly_anchor="friday",
        stock_flow="stock",
        aggregation="last",
        observations=[
            {"period_end": "2026-09-04", "value": 10.0},
            {"period_end": "2026-09-11", "value": 11.0},
        ],
    )
    saved = api.post("/v1/knowledge/datasets", json=weekly, headers=key)
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["observations"][0]["period_start"] == "2026-08-29"  # Saturday..Friday
    assert body["series"]["frequency"] == "weekly"

    thursday = {
        **weekly,
        "slug": "yanlis_gun",
        "observations": [{"period_end": "2026-09-10", "value": 1.0}],
    }
    assert api.post("/v1/knowledge/datasets", json=thursday, headers=key).status_code == 422
    no_anchor = {**weekly, "slug": "capasiz", "weekly_anchor": None}
    assert api.post("/v1/knowledge/datasets", json=no_anchor, headers=key).status_code == 422
    monthly_anchor = manual(slug="aylik_capali", weekly_anchor="friday")
    assert api.post("/v1/knowledge/datasets", json=monthly_anchor, headers=key).status_code == 422


def test_the_inspector_accepts_a_weekly_user_series_with_its_anchor(tmp_path):
    from datetime import UTC, date, datetime

    from kkb_agent.catalog.inspection import PreparedSeriesInspector
    from kkb_agent.catalog.mappings import load_reviewed_snapshot
    from kkb_agent.core import (
        Aggregation,
        CumulativeKind,
        Frequency,
        Scale,
        SourceRef,
        StockFlow,
        WeeklyAnchor,
    )
    from kkb_agent.knowledge import DatasetVersion, effective_snapshot
    from kkb_agent.lakehouse import Observation, open_lakehouse

    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    try:
        saved = knowledge.save_dataset(
            DatasetVersion(
                slug="haftalik",
                version=0,
                title="Haftalık seri",
                unit="TRY",
                scale=Scale.MILLION,
                frequency=Frequency.WEEKLY,
                anchor=WeeklyAnchor.FRIDAY,
                stock_flow=StockFlow.STOCK,
                cumulative=CumulativeKind.NONE,
                aggregation=Aggregation.LAST,
                observations=(Observation(date(2026, 8, 29), date(2026, 9, 4), 1.0),),
                source_kind="manual",
            )
        )
        snapshot = effective_snapshot(
            load_reviewed_snapshot(CATALOG.read_bytes()), knowledge.datasets(), []
        )
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
            inspection = PreparedSeriesInspector(snapshot).inspect(lake.connection, saved.series_id)
            assert inspection.status == "consistent", inspection
    finally:
        knowledge.close()


def test_a_question_can_be_tried_against_the_catalogue_without_running_a_turn(api):
    """The page shows why a series is or is not found, with no model call."""
    client = api
    key = {"X-KKB-Owner-Token": owner(client)}

    found = client.get("/v1/knowledge/search", params={"q": "konut kredisi"}, headers=key)
    assert found.status_code == 200
    body = found.json()
    assert body["query"] == "konut kredisi" and body["total_candidates"] >= 1
    assert all(hit["series_id"] for hit in body["hits"])
    assert body["top_candidate"] == "ambiguous"  # balance or rate: the question does not say

    nothing = client.get("/v1/knowledge/search", params={"q": "zzz kayıt yok"}, headers=key)
    assert nothing.status_code == 200 and nothing.json()["hits"] == []
    assert nothing.json()["top_candidate"] == "none"

    assert client.get("/v1/knowledge/search", params={"q": "x"}).status_code == 422
    assert client.get("/v1/knowledge/search", params={"q": ""}, headers=key).status_code == 422


def test_a_trial_runs_the_same_two_stages_a_turn_runs_and_says_which_ones_ran(tmp_path):
    """With an index the trial is the agent's retrieval; the page never guesses the mode."""
    from test_prepared_dense import build_index

    from kkb_agent.catalog import embedding
    from kkb_agent.catalog.hybrid import CatalogDenseStage
    from kkb_agent.catalog.lance_index import LocalCatalogIndex

    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        store=store,
        knowledge=knowledge,
    )
    provider = scripted(embedding_dimension=4096)
    index = LocalCatalogIndex.open(
        build_index(tmp_path.resolve() / "index", CATALOG),
        runner.catalog,
        embedding.profile_for(embedding.RUNTIME_QUERY_POLICY, "kloudeks"),
    )
    dense = CatalogDenseStage(
        index, embedding.query_embedder(provider, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks")
    )
    service = AnalysisService(
        runner, mode="scripted", document_store=runner.admit_document, store=store, knowledge=True
    )
    knowledge_service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        read_document_column=runner.document_column,
        series_values=runner.series_values,
        dense=dense,
    )
    client = TestClient(
        create_app(service, prepared=runner.status, knowledge=knowledge_service), base_url=BASE
    )
    try:
        with client:
            key = {"X-KKB-Owner-Token": owner(client)}
            body = client.get(
                "/v1/knowledge/search", params={"q": "konut kredisi"}, headers=key
            ).json()
            assert body["retrieval_mode"] == "hybrid" and body["dense_status"] == "success"
            assert body["embedding_model"] == embedding.MODEL
            assert body["input_policy_id"] == embedding.RUNTIME_QUERY_POLICY
            assert {hit["stage"] for hit in body["hits"]} <= {"lexical", "dense", "both"}

            # A knowledge-base entry changes the catalogue the vectors were built for:
            # the trial must say so instead of quietly searching words alone.
            assert (
                client.post("/v1/knowledge/datasets", json=manual(), headers=key).status_code == 201
            )
            after = client.get(
                "/v1/knowledge/search", params={"q": "kart harcaması"}, headers=key
            ).json()
            assert after["retrieval_mode"] == "lexical_degraded"
            assert after["dense_failure"] == "snapshot_mismatch"
            assert any(hit["series_id"].startswith("USER:") for hit in after["hits"])
    finally:
        store.close()
        knowledge.close()


def test_the_vectors_can_be_built_again_for_a_catalogue_the_knowledge_base_changed(tmp_path):
    """A knowledge-base entry becomes findable by meaning once vectors cover it."""
    from test_prepared_dense import build_index

    from kkb_agent.catalog import embedding
    from kkb_agent.catalog.hybrid import CatalogDenseStage
    from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index

    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        store=store,
        knowledge=knowledge,
    )
    provider = scripted(embedding_dimension=4096)
    profile = embedding.profile_for(embedding.RUNTIME_QUERY_POLICY, "kloudeks")
    dense = CatalogDenseStage(
        LocalCatalogIndex.open(
            build_index(tmp_path.resolve() / "index", CATALOG), runner.catalog, profile
        ),
        embedding.query_embedder(provider, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks"),
    )
    generations = tmp_path.resolve() / "generations"

    def rebuild(catalog, previous):
        directory = generations / catalog.content_sha256
        if not (directory / "catalog-manifest.json").exists():
            vectors = embedding.embed_catalog(
                provider, catalog, embedding.RUNTIME_QUERY_POLICY, origin="offline_fixture"
            )
            build_catalog_index(directory, catalog, vectors.model_copy(update={"profile": profile}))
        return CatalogDenseStage(
            LocalCatalogIndex.open(directory, catalog, profile),
            embedding.query_embedder(provider, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks"),
        )

    service = AnalysisService(
        runner, mode="scripted", document_store=runner.admit_document, store=store, knowledge=True
    )
    knowledge_service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        read_document_column=runner.document_column,
        series_values=runner.series_values,
        dense=dense,
        rebuild_index=rebuild,
        install_index=runner.use_dense,
    )
    client = TestClient(
        create_app(service, prepared=runner.status, knowledge=knowledge_service), base_url=BASE
    )
    try:
        with client:
            key = {"X-KKB-Owner-Token": owner(client)}
            assert (
                client.post("/v1/knowledge/datasets", json=manual(), headers=key).status_code == 201
            )
            before = client.get("/v1/knowledge/index", headers=key).json()
            assert before["configured"] and not before["covers_catalog"]
            assert before["rebuildable"] and before["missing"] == ["USER:kart_harcamalari.v1"]
            assert before["model"] == embedding.MODEL

            assert client.post("/v1/knowledge/index", json={}, headers=key).status_code == 202
            knowledge_service.close()
            after = client.get("/v1/knowledge/index", headers=key).json()
            assert after["last_error"] is None and after["built_at"]
            assert after["covers_catalog"] and after["missing"] == []
            assert after["series_vectored"] == after["series_total"]

            # The rebuilt generation is what the next turn's discovery searches.
            assert runner.dense is not None
            assert runner.dense.index.snapshot_sha256 == after["catalog_sha256"]
            trial = client.get(
                "/v1/knowledge/search", params={"q": "kart harcaması"}, headers=key
            ).json()
            assert trial["retrieval_mode"] == "hybrid" and trial["dense_status"] == "success"

            # A restart starts from the reviewed generation again. The one built above is on
            # disk for this very catalogue, so it is reopened: no build, no model call.
            def reopen(catalog):
                directory = generations / catalog.content_sha256
                if not (directory / "catalog-manifest.json").exists():
                    return None
                return CatalogDenseStage(
                    LocalCatalogIndex.open(directory, catalog, profile),
                    embedding.query_embedder(
                        provider, embedding.RUNTIME_QUERY_POLICY, origin="kloudeks"
                    ),
                )

            installed = []
            restarted = KnowledgeService(
                knowledge,
                store,
                runner.catalog,
                prepared=frozenset(item.series_id for item in runner.status.series),
                dense=dense,
                rebuild_index=lambda catalog, previous: pytest.fail("a restart must not build"),
                install_index=installed.append,
                reopen_index=reopen,
            )
            assert restarted.index_status(key["X-KKB-Owner-Token"]).covers_catalog is False
            assert restarted.restore_generation() is True
            status = restarted.index_status(key["X-KKB-Owner-Token"])
            assert status.covers_catalog and status.missing == ()
            assert [stage.index.snapshot_sha256 for stage in installed] == [after["catalog_sha256"]]
            assert restarted.restore_generation() is False  # already in use
    finally:
        store.close()
        knowledge.close()


def test_a_series_lists_the_answers_whose_proof_read_it(tmp_path):
    """Reverse lineage: recorded from the proof when the answer is stored, per owner."""
    from test_api_proof import prepare_pool
    from test_catalog_continuation import TOTAL
    from test_prepared_api import responses, wait_http

    root = prepare_pool(tmp_path.resolve() / "prepared")
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    runner = PreparedRunner(
        scripted(*responses()),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
        knowledge=knowledge,
    )
    service = AnalysisService(runner, mode="scripted", store=store, knowledge=True)
    knowledge_service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        series_values=runner.series_values,
    )
    client = TestClient(
        create_app(service, prepared=runner.status, knowledge=knowledge_service), base_url=BASE
    )
    try:
        with client:
            key = {"X-KKB-Owner-Token": owner(client)}
            session = client.post("/v1/sessions", json={}, headers=key).json()
            headers = {"X-KKB-Session-Token": session["token"]}
            turns = f"/v1/sessions/{session['session_id']}/turns"
            question = "Konut kredisi Nisan-Haziran 2026 arasında ne kadar değişti?"
            asked = client.post(
                turns, json={"request_id": "a" * 32, "question": question}, headers=headers
            ).json()
            done = wait_http(client, f"{turns}/{asked['turn_id']}", headers)
            assert done["answer"]["status"] == "accepted", done

            uses = client.get(f"/v1/knowledge/series/{TOTAL}/uses", headers=key)
            assert uses.status_code == 200, uses.text
            body = uses.json()
            assert body["series_id"] == TOTAL
            [use] = body["uses"]
            assert use["conversation_id"] == session["session_id"]
            assert use["turn_id"] == asked["turn_id"] and use["question"] == question
            assert use["title"]

            # A series no answer read has no uses; another browser sees nothing.
            none = client.get("/v1/knowledge/series/EVDS:TP.YOK/uses", headers=key).json()
            assert none["uses"] == []
            other = {"X-KKB-Owner-Token": owner(client)}
            assert (
                client.get(f"/v1/knowledge/series/{TOTAL}/uses", headers=other).json()["uses"] == []
            )
    finally:
        store.close()
        knowledge.close()


def test_a_url_becomes_a_session_document_then_a_persisted_dataset(tmp_path):
    """URL -> safe_fetch -> upload admission -> the existing document-column dataset."""
    from test_document_check import FakeFetch
    from test_document_dataset import ADMISSIONS, csv

    root = tmp_path.resolve() / "prepared"
    seed(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    fetch = FakeFetch(csv())
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        web_url_fetch=fetch,
        store=store,
        knowledge=knowledge,
    )
    service = AnalysisService(
        runner,
        mode="scripted",
        document_store=runner.admit_document,
        url_document_store=runner.admit_document_from_url,
        store=store,
        knowledge=True,
    )
    knowledge_service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        read_document_column=runner.document_column,
        series_values=runner.series_values,
    )
    client = TestClient(
        create_app(service, prepared=runner.status, knowledge=knowledge_service), base_url=BASE
    )
    try:
        with client:
            token = owner(client)
            session = client.post(
                "/v1/sessions", json={}, headers={"X-KKB-Owner-Token": token}
            ).json()
            headers = {"X-KKB-Session-Token": session["token"]}
            sid = session["session_id"]

            # A bare id or a non-https address never reaches the fetcher.
            assert (
                client.post(
                    f"/v1/sessions/{sid}/documents/from-url",
                    json={"url": "ftp://x/y.csv"},
                    headers=headers,
                ).status_code
                == 422
            )

            admitted = client.post(
                f"/v1/sessions/{sid}/documents/from-url",
                json={"url": "https://data.example.test/basvurular.csv"},
                headers=headers,
            )
            assert admitted.status_code == 201, admitted.text
            document_ref = admitted.json()["document_ref"]
            assert admitted.json()["document_format"] == "csv"
            # The fetch obeyed the tabular contract, GET-only, from the given address.
            assert fetch.requests[0].url.get_secret_value().endswith("basvurular.csv")

            saved = client.post(
                "/v1/knowledge/datasets",
                json=manual(
                    slug="basvurular_url",
                    title="URL'den başvurular",
                    unit="count",
                    scale="one",
                    stock_flow="flow",
                    observations=[],
                    document={
                        "session_id": sid,
                        "document_ref": document_ref,
                        "period_column": "Ay",
                        "value_column": "Başvuru Sayısı",
                    },
                ),
                headers={"X-KKB-Owner-Token": token},
            )
            assert saved.status_code == 201, saved.text
            assert [o["value"] for o in saved.json()["observations"]] == [
                float(v) for v in ADMISSIONS
            ]
            assert saved.json()["source_kind"] == "upload"
    finally:
        store.close()
        knowledge.close()


def test_the_listing_shows_what_search_reads_for_every_entry(api):
    """Arda (2026-09-19): empty alias/description inputs looked like an empty index."""
    key = {"X-KKB-Owner-Token": owner(api)}
    api.post("/v1/knowledge/datasets", json=manual(description="Aylık kart harcaması"), headers=key)
    series = {s["series_id"]: s for s in api.get("/v1/knowledge", headers=key).json()["series"]}
    total = series[TOTAL]
    assert total["description"] and total["labels"] and total["reviewed_aliases"]
    assert "konut kredisi bakiyesi" in total["reviewed_aliases"]
    # The exact indexed and embedded text: title, description, labels, semantics, aliases.
    assert (
        "tuketici kredileri" in total["search_text"] and "stock flow stock" in total["search_text"]
    )
    assert total["aliases"] == [] and total["note"] is None  # the person's own inputs are empty
    mine = series["USER:kart_harcamalari.v1"]
    assert mine["description"] == "Aylık kart harcaması"
    assert "kart harcamasi" in mine["search_text"] and mine["reviewed_aliases"] == []


def test_a_person_s_description_of_a_reviewed_series_is_searched(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    before = api.get("/v1/knowledge", headers=key).json()
    assert before["catalog_digest"] == before["reviewed_digest"]
    nothing = api.get("/v1/knowledge/search", params={"q": "ipotekli finansman"}, headers=key)
    assert nothing.json()["hits"] == []
    saved = api.post(
        f"/v1/knowledge/series/{TOTAL}/notes",
        json={"archived": False, "note": "Bankaların ipotekli finansman alacakları toplamı"},
        headers=key,
    )
    assert saved.status_code == 200, saved.text
    after = api.get("/v1/knowledge", headers=key).json()
    # The description is part of the catalogue a turn searches: its digest changes, so the
    # page knows the vectors no longer cover it until they are built again.
    assert after["catalog_digest"] != after["reviewed_digest"]
    entry = next(item for item in after["series"] if item["series_id"] == TOTAL)
    assert "ipotekli finansman" in entry["search_text"]
    assert entry["description"].startswith("Reviewed")  # the reviewed text itself is unchanged
    found = api.get("/v1/knowledge/search", params={"q": "ipotekli finansman"}, headers=key)
    assert [hit["series_id"] for hit in found.json()["hits"]][:1] == [TOTAL]


def test_the_whole_directory_is_browsed_one_page_at_a_time(tmp_path):
    """Every listed entry can be browsed, and only one page of them travels.

    Measured on 2026-09-21: the whole list is 1,930 bytes an entry, 3.6 MB for 1,869
    entries, against the web bridge's 1 MiB response bound; the tabs, the search box and
    the province selector therefore run on the server.
    """
    from kkb_agent.catalog.directory import source_directory
    from kkb_agent.catalog.mappings import load_reviewed_snapshot

    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    _, token = store.create_owner()
    directory = source_directory()
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        source_directory=directory,
    )
    try:
        bounded = service.listing(token)
        assert bounded.total is None and all(item.origin != "listed" for item in bounded.series)
        first = service.listing(token, tab="listed", page=1)
        assert len(first.series) == 50 and first.page == 1 and first.page_size == 50
        assert first.total == first.counts["listed"] == bounded.listed_series > 1000
        # Archived entries sit in their own tab, as they did in the browser.
        assert 0 < first.counts["reviewed"] <= len(service._reviewed.series)
        assert all(item.origin == "listed" for item in first.series)
        assert len(first.model_dump_json().encode()) < 512 * 1024
        second = service.listing(token, tab="listed", page=2)
        assert not {item.series_id for item in first.series} & {
            item.series_id for item in second.series
        }
        last = service.listing(token, tab="listed", page=first.total // 50 + 1)
        assert 0 < len(last.series) <= 50
        assert service.listing(token, tab="listed", page=999).series == ()
        found = service.listing(token, tab="all", query="İHTİYAÇ", page=1)
        assert 0 < found.total < first.total
        assert all("htiya" in item.title for item in found.series)
        assert service.listing(token, tab="nonsense", page=1).total == first.counts["all"]
        assert service.listing(token, page=1, page_size=1000).page_size == 100
    finally:
        store.close()
        knowledge.close()


def test_a_page_does_not_rebuild_the_whole_catalogue_every_time(tmp_path, monkeypatch):
    """Live 2026-09-21: with 8,374 listed series every list request rebuilt the effective
    catalogue (about a second) and the search text of all of it (3.5 s) to show fifty; the
    page asks for several things at once, the list passed the client's 12 s and the reader
    saw "Bağlantı kesildi" under an empty list."""
    from kkb_agent.api import knowledge_service as module
    from kkb_agent.catalog.directory import source_directory
    from kkb_agent.catalog.mappings import load_reviewed_snapshot

    built = {"catalogue": 0, "texts": 0}
    snapshot, documents = module.effective_snapshot, module.catalog_documents

    def counted_snapshot(*args, **kwargs):
        built["catalogue"] += 1
        return snapshot(*args, **kwargs)

    def counted_documents(*args, **kwargs):
        built["texts"] += 1
        return documents(*args, **kwargs)

    monkeypatch.setattr(module, "effective_snapshot", counted_snapshot)
    monkeypatch.setattr(module, "catalog_documents", counted_documents)
    store = ConversationStore(tmp_path / "c.sqlite")
    knowledge = KnowledgeStore(tmp_path / "k.sqlite")
    _, token = store.create_owner()
    service = KnowledgeService(
        knowledge,
        store,
        load_reviewed_snapshot(CATALOG.read_bytes()),
        prepared=frozenset({TOTAL}),
        source_directory=source_directory(),
        catalog_edits=True,
    )
    try:
        first = service.listing(token, tab="listed", page=1)
        for page in (2, 3):
            service.listing(token, tab="listed", page=page)
        service.listing(token, tab="all", query="konut", page=1)
        assert built == {"catalogue": 1, "texts": 1}
        assert first.series[0].search_text
        # What a person says about a series changes what search reads: built again, once.
        target = first.series[0].series_id
        service.annotate(token, target, SeriesNoteRequest(archived=False, note="kendi notum"))
        after = service.listing(token, tab="listed", page=1)
        service.listing(token, tab="listed", page=2)
        assert built == {"catalogue": 2, "texts": 2}
        noted = next(item for item in after.series if item.series_id == target)
        assert noted.note == "kendi notum" and "kendi notum" in (noted.search_text or "")
        assert after.catalog_digest != first.catalog_digest
    finally:
        store.close()
        knowledge.close()


def test_the_list_route_takes_its_view_as_a_bounded_query(api):
    key = {"X-KKB-Owner-Token": owner(api)}
    shown = api.get("/v1/knowledge?tab=reviewed&page=1&page_size=5", headers=key)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert len(body["series"]) == 5 and body["total"] == body["counts"]["reviewed"]
    assert api.get("/v1/knowledge?page=0", headers=key).status_code == 422
    assert api.get("/v1/knowledge?page_size=500&page=1", headers=key).status_code == 422


@pytest.mark.parametrize("flag", [True, False])
def test_serve_hands_the_operator_s_catalogue_flag_to_the_knowledge_base(
    tmp_path, monkeypatch, flag
):
    """--allow-catalog-edits is the one way a browser key may change a catalogue note."""
    from test_prepared_api import set_config

    from kkb_agent.api import __main__ as cli

    def no_network(*args, **kwargs):
        raise AssertionError("No live request in this test")

    set_config(monkeypatch)
    monkeypatch.setattr("socket.socket.connect", no_network)
    root = tmp_path.resolve() / "prepared"
    seed(root)
    seen = {}
    real = cli.KnowledgeService

    def capture(*args, **kwargs):
        seen["catalog_edits"] = kwargs.get("catalog_edits")
        return real(*args, **kwargs)

    class Provider:
        def __enter__(self):
            return scripted()

        def __exit__(self, *args):
            return None

    monkeypatch.setattr(cli, "KnowledgeService", capture)
    monkeypatch.setattr(cli, "KloudeksProvider", lambda *a: Provider())
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: None)
    arguments = [
        "--serve",
        "--enable-model-requests",
        "--prepared-root",
        str(root),
        "--catalog",
        str(CATALOG),
        "--state-root",
        str(tmp_path.resolve() / "runtime"),
    ]
    assert cli.main([*arguments, "--allow-catalog-edits"] if flag else arguments) == 0
    assert seen["catalog_edits"] is flag
