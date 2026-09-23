"""An address read in a conversation, kept in the knowledge base, found from another one.

QA-29: a conversation that began with an address could read it but not keep it in the
same turn, because the registry was settled before the first read and the document
tools are offered only once there is a document. And what was kept lost where it came
from: no address, no time, no place in the document. These tests hold the whole path -
read, save when the person asked, find it again after a restart in another
conversation - and what the knowledge base records about the source.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date
from uuid import uuid4

from test_dataset_promotion import (  # noqa: F401
    ADMISSIONS,
    SLUG,
    TITLE,
    TestAnAddressTheQuestionNamed,
    csv,
    stack,
)

from kkb_agent.agent.trust_loop import FINISH
from kkb_agent.api.knowledge_service import KnowledgeService, dataset_source
from kkb_agent.api.prepared import address_origin
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.knowledge.store import DatasetVersion, _body
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm.provider import ToolCall
from kkb_agent.tools.promotion import PromotionProposal

URL = "https://example.org/veri/gelir.csv?token=SECRET-QUERY"


def call(tool: str, **arguments: object) -> tuple[ToolCall, ...]:
    return (ToolCall(id=f"c{uuid4().hex[:6]}", name=tool, arguments=json.dumps(arguments)),)


def empty_conversation(store: ConversationStore) -> str:
    owner_id, _ = store.create_owner()
    session_id = uuid4().hex
    store.create_conversation(
        owner_id=owner_id, conversation_id=session_id, token=uuid4().hex, title="URL"
    )
    return session_id


def save_from_address(build, store, *, save_now: bool = True, content: bytes | None = None):
    """One message: read the address, keep it under a name; nothing uploaded before."""
    runner, _ = build(
        call("web_url", url=URL),
        call(
            "promote_series",
            document="belge_1",
            title=TITLE,
            unit="TL",
            scale="million",
            meaning="monthly_total",
            description="Şirketin her ay elde ettiği gelir.",
            aliases=["aylık ciro"],
            save_now=save_now,
        ),
        call(FINISH, answer="Tamam."),
    )
    runner._trust_loop = True
    runner._web_url_fetch = TestAnAddressTheQuestionNamed._fetch(content or csv(), [])
    session_id = empty_conversation(store)
    runner(session_id, uuid4().hex, f"{URL} adresindeki geliri getir ve bilgi tabanına kaydet")
    return runner, session_id


def test_an_address_read_in_an_empty_conversation_is_saved_in_the_same_turn(stack):  # noqa: F811
    build, store, knowledge, _ = stack
    runner, session_id = save_from_address(build, store)

    saved = knowledge.dataset(SLUG)
    assert saved is not None, "the address was read, but the save the person asked for is absent"
    assert runner._pending_promotions.get(session_id) is None  # saved, not offered
    assert saved.description == "Şirketin her ay elde ettiği gelir."
    assert saved.aliases == ("aylık ciro",)
    where = dict(saved.provenance)
    # Where it came from, without the query: a query can carry a key.
    assert where["source_url"] == "https://example.org/veri/gelir.csv"
    assert "SECRET" not in json.dumps(where)
    assert where["document"] == "belge_1" and where["media_type"] == "text/csv"
    assert where["period_column"] == "Ay" and where["value_column"] == "Gelir (milyon TL)"
    assert where["retrieved_at"] and len(where["sha256"]) == 64


def test_the_read_says_which_name_the_document_is_kept_under(stack):  # noqa: F811
    build, store, _, _ = stack
    runner, _ = build(call("web_url", url=URL), call(FINISH, answer="Okundu."))
    runner._trust_loop = True
    runner._web_url_fetch = TestAnAddressTheQuestionNamed._fetch(csv(), [])
    runner(empty_conversation(store), uuid4().hex, f"{URL} adresini oku")
    shown = "\n".join(message.content for message in runner._provider.seen[1])
    assert '"kept_as": "belge_1"' in shown


def test_without_the_persons_request_it_is_only_offered(stack):  # noqa: F811
    build, store, knowledge, _ = stack
    runner, session_id = save_from_address(build, store, save_now=False)
    assert knowledge.dataset(SLUG) is None
    held = runner._pending_promotions[session_id]
    assert dict(held.provenance)["source_url"] == "https://example.org/veri/gelir.csv"


def test_another_conversation_after_a_restart_finds_it_by_its_alias(stack, tmp_path):  # noqa: F811
    build, store, knowledge, _ = stack
    first, session_id = save_from_address(build, store)
    saved = knowledge.dataset(SLUG)
    assert saved is not None

    restarted, _ = build()  # a new process over the same stores
    restarted._restore(session_id)
    (document,) = [d for (owner, _), d in restarted._documents.items() if owner == session_id]
    assert document.origin == "https://example.org/veri/gelir.csv"
    with open_lakehouse(tmp_path / "another-conversation") as lake:
        catalog, loaded = restarted._apply_knowledge(lake)
        assert saved.series_id in loaded
        found = search_catalog(catalog, CatalogSearchArguments(query="aylık ciro"))
        assert saved.series_id in [c.series.record.series_id for c in found.candidates]
        (record,) = [s for s in catalog.series if s.record.series_id == saved.series_id]
        assert "source_url=https://example.org/veri/gelir.csv" in record.note


def rows_of(lake, series_id: str) -> list[float | None]:
    return [
        row[0]
        for row in lake.connection.execute(
            "SELECT value FROM silver_observations WHERE series_id = ? ORDER BY period_end",
            [series_id],
        ).fetchall()
    ]


def test_saving_the_same_series_again_is_a_new_version_and_the_old_one_stands(stack, tmp_path):  # noqa: F811
    """The update: the address serves new numbers, the person saves it again.

    It is the next version of the same record, with its own numbers and its own source;
    the first version's numbers and source are exactly what they were. A conversation
    that analysed the first version keeps it, and a new conversation is given the new one.
    """
    build, store, knowledge, _ = stack
    earlier, _ = save_from_address(build, store)
    with open_lakehouse(tmp_path / "earlier-conversation") as lake:
        _, loaded = earlier._apply_knowledge(lake)
    (first,) = knowledge.dataset_history(SLUG)
    assert loaded == [first.series_id]

    doubled = csv(values=[value * 2 for value in ADMISSIONS])
    later, _ = save_from_address(build, store, content=doubled)
    v1, v2 = knowledge.dataset_history(SLUG)
    assert (v1.version, v2.version) == (1, 2)
    assert v1.content_sha256() == first.content_sha256()  # untouched by the update
    assert [o.value for o in v2.observations] == [2 * o.value for o in v1.observations]
    old, new = dict(v1.provenance), dict(v2.provenance)
    assert old["source_url"] == new["source_url"] == "https://example.org/veri/gelir.csv"
    assert old["sha256"] != new["sha256"]  # each version names the bytes it was read from
    assert old["retrieved_at"] <= new["retrieved_at"]

    with open_lakehouse(tmp_path / "later-conversation") as lake:
        catalog, loaded = later._apply_knowledge(lake)
        listed = {item.record.series_id for item in catalog.series}
        assert v2.series_id in listed and v1.series_id not in listed
        assert loaded == [v2.series_id]
        assert rows_of(lake, v2.series_id) == [o.value for o in v2.observations]
    with open_lakehouse(tmp_path / "earlier-conversation") as lake:
        # What an earlier analysis read is still there, beside the new version.
        later._apply_knowledge(lake)
        assert rows_of(lake, v1.series_id) == [o.value for o in v1.observations]
        assert rows_of(lake, v2.series_id) == [o.value for o in v2.observations]

    # The page shows each version with its own source, and the latest one on top.
    _, page = build()
    shown = page._detail(SLUG)
    assert [item.source.sha256 for item in shown.history] == [old["sha256"], new["sha256"]]
    assert shown.source == shown.history[-1].source
    assert shown.source.kind == "address"
    assert shown.source.url == "https://example.org/veri/gelir.csv"
    assert shown.source.read_at is not None and shown.source.table == 1
    assert (shown.source.period_column, shown.source.value_column) == ("Ay", "Gelir (milyon TL)")
    assert "SECRET" not in shown.model_dump_json()


def test_a_version_typed_into_the_form_has_no_source():
    typed = DatasetVersion(
        slug="elle_girilen",
        version=1,
        title="Elle girilen",
        unit="TRY",
        scale=Scale.ONE,
        frequency=Frequency.MONTHLY,
        stock_flow=StockFlow.FLOW,
        cumulative=CumulativeKind.NONE,
        aggregation=Aggregation.SUM,
        observations=(),
        source_kind="manual",
    )
    assert dataset_source(typed) is None


def test_a_version_saved_before_provenance_keeps_its_identity():
    old = DatasetVersion(
        slug="eski_veri",
        version=1,
        title="Eski",
        unit="TRY",
        scale=Scale.ONE,
        frequency=Frequency.MONTHLY,
        stock_flow=StockFlow.FLOW,
        cumulative=CumulativeKind.NONE,
        aggregation=Aggregation.SUM,
        observations=(),
        source_kind="manual",
    )
    assert "provenance" not in _body(old)


def test_a_store_from_before_origin_is_migrated_in_place(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as old:
        old.execute(
            "CREATE TABLE documents (conversation_id TEXT NOT NULL, document_ref TEXT NOT NULL, "
            "name TEXT NOT NULL, document_format TEXT NOT NULL, media_type TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, byte_count INTEGER NOT NULL, path TEXT NOT NULL, "
            "admitted_at TEXT NOT NULL, PRIMARY KEY (conversation_id, document_ref))"
        )
    store = ConversationStore(path)
    columns = {row[1] for row in store._connection.execute("PRAGMA table_info(documents)")}
    store.close()
    assert "origin" in columns


def test_an_address_origin_keeps_host_port_and_path_only():
    assert (
        address_origin("https://a.example:8443/x/y.pdf?k=1#f") == "https://a.example:8443/x/y.pdf"
    )


class _Index:
    def __init__(self, digest: str) -> None:
        self.snapshot_sha256, self.profile = digest, "profile"


class _Stage:
    def __init__(self, digest: str) -> None:
        self.index = _Index(digest)


def proposal(session_id: str, slug: str) -> PromotionProposal:
    return PromotionProposal(
        slug=slug,
        title=slug.replace("_", " "),
        unit="TRY",
        scale="million",
        stock_flow="flow",
        aggregation="sum",
        cumulative="none",
        base_year=None,
        session_id=session_id,
        document_ref="r",
        document_sha256="0" * 64,
        period_column="Ay",
        value_column="Gelir",
        sheet=None,
        year=None,
        observations=((date(2026, 1, 31), 1.0), (date(2026, 2, 28), 2.0)),
        summary="",
    )


def test_a_save_refreshes_the_vectors_and_a_save_during_a_build_is_not_lost(stack):  # noqa: F811
    """A save used to leave the vectors as they were; now it starts a build of what is new.

    A save that lands while a build runs makes that build refuse to install (it was built
    for the catalogue before the save), and one more build then runs for the catalogue as
    it is, borrowing the vectors the refused build made instead of embedding them again.
    """
    build, store, knowledge, _ = stack
    runner, _ = build()
    session_id = empty_conversation(store)
    built: list[str] = []
    lent: list[object] = []
    release = threading.Event()

    def rebuild(catalog, previous):
        built.append(catalog.content_sha256)
        lent.append(previous)
        release.wait(10)
        return _Stage(catalog.content_sha256)

    service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        rebuild_index=rebuild,
    )
    first = service.promote(proposal(session_id, "birinci_seri"))
    second = service.promote(proposal(session_id, "ikinci_seri"))  # while the first builds
    assert first.index == "refreshing" and second.index == "refreshing"
    release.set()
    for _ in range(200):
        thread = service._build_thread
        if thread is not None:
            thread.join(5)
        if len(built) == 2 and not service._building.locked():
            break
    assert len(built) == 2 and built[0] != built[1]
    # The second build borrowed what the first made, never installed for the wrong catalogue.
    assert lent[1] is not None and lent[1].snapshot_sha256 == built[0]
    assert service._dense is not None
    assert service._dense.index.snapshot_sha256 == service._effective().content_sha256


def indexed(stack, rebuild):  # noqa: F811
    build, store, knowledge, _ = stack
    runner, _ = build()
    service = KnowledgeService(
        knowledge,
        store,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        rebuild_index=rebuild,
    )
    return service, empty_conversation(store)


def settled(service) -> None:
    """Every build started so far, and every build those started, has ended."""
    for _ in range(50):
        thread = service._build_thread
        if thread is None or not thread.is_alive():
            if not service._building.locked():
                return
        else:
            thread.join(5)
    raise AssertionError("a build never ended")


def test_a_build_ending_between_busy_and_the_flag_still_builds_the_save(stack, monkeypatch):  # noqa: F811
    """QA-31: the running build ended after the save was told busy, before the flag was set.

    It read no flag and left, and the save was told "refreshing" with nothing left to
    build it. The save now asks again once the flag is set, and finds no build running.
    """
    built: list[str] = []
    running, release = threading.Event(), threading.Event()

    def rebuild(catalog, previous):
        built.append(catalog.content_sha256)
        running.set()
        assert release.wait(5)
        return _Stage(catalog.content_sha256)

    service, session_id = indexed(stack, rebuild)
    service.promote(proposal(session_id, "ilk_kayit"))
    assert running.wait(5)
    ask = service._start_build

    def ending_right_after_busy(*args, **kwargs):
        started = ask(*args, **kwargs)
        if not started:
            worker = service._build_thread
            release.set()
            worker.join(5)
            assert not worker.is_alive()
        return started

    monkeypatch.setattr(service, "_start_build", ending_right_after_busy)
    receipt = service.promote(proposal(session_id, "ikinci_kayit"))
    settled(service)
    assert receipt.index == "refreshing"
    assert len(built) == 2  # the save's own build, and no more
    assert service._dense is not None
    assert service._dense.index.snapshot_sha256 == service._effective().content_sha256


def test_a_failing_follow_up_is_recorded_and_not_retried(stack):  # noqa: F811
    """The build a save leaves behind may fail; it is said, and nothing loops on it."""
    built: list[str] = []
    running, release = threading.Event(), threading.Event()

    def rebuild(catalog, previous):
        built.append(catalog.content_sha256)
        if len(built) == 1:
            running.set()
            assert release.wait(5)
            return _Stage(catalog.content_sha256)
        raise OSError("/private/path")

    service, session_id = indexed(stack, rebuild)
    service.promote(proposal(session_id, "ilk_kayit"))
    assert running.wait(5)
    service.promote(proposal(session_id, "ikinci_kayit"))
    release.set()
    settled(service)
    assert len(built) == 2
    assert service._build_error == "state_filesystem_failure"
    assert service._dense is None  # the first was built for a catalogue that had moved on


def test_without_an_index_the_receipt_says_words_find_it(stack):  # noqa: F811
    build, store, knowledge, _ = stack
    runner, service = build()
    receipt = service.promote(proposal(empty_conversation(store), "kelime_serisi"))
    assert receipt.index == "lexical" and "anlamsal arama indeksi yok" in receipt.said()


def attached(content: bytes):
    from kkb_agent.core import SourceRef
    from kkb_agent.ingest.attached import Attachment

    return Attachment(
        content,
        "text/csv",
        SourceRef(source_id="upload:x", source_type="upload", locator="upload:x"),
    )


def offer(content: bytes):
    from kkb_agent.agent.executor import ExecutionContext
    from kkb_agent.tools.promotion import make_promote_series_tool

    tool = make_promote_series_tool(
        session_id="s", attachment=attached(content), library={}, propose=lambda _: None
    )
    arguments = tool.parse({"title": TITLE, "unit": "TL", "meaning": "monthly_total"})
    return tool.run(arguments, ExecutionContext("Bu tabloyu kaydet"))


def test_a_table_that_is_not_monthly_is_refused_with_the_limit_said():
    from kkb_agent.tools.promotion import SAVE_LIMIT

    quarterly = b"Donem;Gelir\n2025-Q1;10\n2025-Q2;12\n2025-Q3;14\n"
    refused = offer(quarterly)
    assert refused.warnings[0] == "NO_PERIOD_COLUMN"
    assert SAVE_LIMIT in refused.warnings[1] and "aylık" in refused.output.summary


def test_two_value_columns_ask_which_one_to_keep():
    from test_dataset_promotion import two_value_csv

    refused = offer(two_value_csv())
    assert refused.warnings[0] == "VALUE_COLUMN_NOT_SETTLED"
    assert "tek sütun" in refused.warnings[1]


def read_back(content: bytes, document: str):
    """One message: read the address, save it, then find and read what was saved."""
    return (
        call("web_url", url=URL),
        call(
            "promote_series",
            document=document,
            title=TITLE,
            unit="TL",
            scale="million",
            meaning="monthly_total",
            save_now=True,
        ),
        call("catalog_search", query=TITLE),
        call("lakehouse", series=[f"USER:{SLUG}.v{1 if document == 'belge_1' else 2}"]),
        call(FINISH, answer="Kaydedildi ve geri okundu."),
    )


def outputs(runner) -> dict[str, str]:
    """What each call of the last turn returned to the model, by its id."""
    from kkb_agent.llm.provider import Role

    found: dict[str, str] = {}
    for message in runner._provider.seen[-1]:
        if message.role is Role.TOOL:
            found[json.loads(message.content)["id"]] = message.content
    return found


def read_values(seen: str, series_id: str) -> list[float]:
    import re

    pattern = (
        rf"label='{re.escape(series_id)}', value=([0-9.]+), unit='TRY', "
        r"scale=<Scale\.MILLION: 'million'>, measure=<StockFlow\.FLOW: 'flow'>"
    )
    return [float(value) for value in re.findall(pattern, seen)]


def test_a_series_saved_in_a_turn_is_found_and_read_in_the_same_turn(stack):  # noqa: F811
    """QA-34: after the save, the same turn's search lists it and the lakehouse reads it.

    Live 2026-09-23 the lakehouse answered `unknown_identity` twice for the series just
    saved and the search did not list it, so the person would have had to ask again.
    """
    build, store, knowledge, _ = stack
    runner, _ = build(*read_back(csv(), "belge_1"))
    runner._trust_loop = True
    runner._web_url_fetch = TestAnAddressTheQuestionNamed._fetch(csv(), [])
    runner(empty_conversation(store), uuid4().hex, f"{URL} adresindeki geliri kaydet, geri oku")
    saved = knowledge.dataset(SLUG)
    assert saved is not None and saved.series_id == f"USER:{SLUG}.v1"
    seen = outputs(runner)
    found = json.loads(seen["a3"])["output"]["candidates"]
    assert found[0]["series"]["record"]["series_id"] == saved.series_id
    assert json.loads(seen["a4"])["status"] == "success" and "unknown_identity" not in seen["a4"]
    assert read_values(seen["a4"], saved.series_id) == [float(v) for v in ADMISSIONS]


def test_a_new_version_saved_in_a_turn_is_read_and_the_old_one_stays(stack, tmp_path):  # noqa: F811
    build, store, knowledge, _ = stack
    session_id = empty_conversation(store)
    first, _ = build(*read_back(csv(), "belge_1"))
    first._trust_loop = True
    first._web_url_fetch = TestAnAddressTheQuestionNamed._fetch(csv(), [])
    first(session_id, uuid4().hex, f"{URL} adresindeki geliri kaydet")

    doubled = csv(values=[value * 2 for value in ADMISSIONS])
    later, _ = build(*read_back(doubled, "belge_2"))
    later._trust_loop = True
    later._web_url_fetch = TestAnAddressTheQuestionNamed._fetch(doubled, [])
    later(session_id, uuid4().hex, f"{URL} adresindeki güncel geliri kaydet, geri oku")
    v1, v2 = knowledge.dataset_history(SLUG)
    seen = outputs(later)
    assert read_values(seen["a4"], v2.series_id) == [2.0 * v for v in ADMISSIONS]
    with open_lakehouse(later.run_root / session_id / "lake") as lake:
        assert rows_of(lake, v1.series_id) == [float(v) for v in ADMISSIONS]
        assert rows_of(lake, v2.series_id) == [2.0 * v for v in ADMISSIONS]
