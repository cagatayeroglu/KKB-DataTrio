"""DEC-177: everything EVDS lists can be found, opened, fetched and named, with no model input.

EVDS publishes about 680 datagroups and tens of thousands of series. The datagroups are
catalogue entries (found by meaning); a found datagroup is opened into the series the source
lists under it, and one of those is fetched on first use by the same adapter and the same
strict loader as a reviewed series. No network here: the series list and the observations
come from fakes shaped like the live answers of 2026-09-19.
"""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, proposal, seed_prepared

from kkb_agent.agent.executor import ExecutionContext
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.catalog.directory import EVDS_GROUP_PREFIX, source_directory
from kkb_agent.catalog.discovered import DiscoveredStore
from kkb_agent.catalog.expansion import MAX_CANDIDATES, expand_groups, rank_series
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import (
    is_listed_series,
    is_source_group,
    load_reviewed_snapshot,
)
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.catalog.search import MAX_GROUPS, CatalogSearchArguments, search_catalog
from kkb_agent.ingest.acquisition import (
    UNREAD_REASONS,
    AcquiringInspector,
    AcquisitionCode,
    OfficialSources,
    TurnAcquirer,
)
from kkb_agent.ingest.evds_load import EvdsLoadCode
from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure, FetchSuccess
from kkb_agent.knowledge.overlay import effective_snapshot
from kkb_agent.llm import scripted
from kkb_agent.tools import make_catalog_search_tool, make_lakehouse_tool

SOURCE_DAY = timezone(timedelta(hours=3))
TODAY = date(2000, 2, 10)  # a listed daily window is then 2000-01-01..2000-02-10
GROUP = "bie_dkdovytl"
DOLLAR, EURO = "EVDS:TP.DK.USD.A.YTL", "EVDS:TP.DK.EUR.A.YTL"


def row(code, name, english, order):
    return {
        "SERIE_CODE": code,
        "DATAGROUP_CODE": GROUP,
        "SERIE_NAME": name,
        "SERIE_NAME_ENG": english,
        "FREQUENCY_STR": "GÜNLÜK",
        "DEFAULT_AGG_METHOD": "avg",
        "SCREEN_ORDER": order,
        "AVGABLE": 1,
        "SUMABLE": 0,
        "FIRSTABLE": 1,
        "LASTABLE": 1,
        "MINABLE": 1,
        "MAXABLE": 1,
    }


SERIES_LIST = [
    row("TP.DK.EUR.A.YTL", "(EUR) Euro (Döviz Alış)", "(EUR) Euro (Buying)", 1),
    row("TP.DK.EUR.S.YTL", "(EUR) Euro (Döviz Satış)", "(EUR) Euro (Selling)", 2),
    row("TP.DK.USD.A.YTL", "(USD) ABD Doları (Döviz Alış)", "(USD) US Dollar (Buying)", 3),
    row("TP.DK.USD.S.YTL", "(USD) ABD Doları (Döviz Satış)", "(USD) US Dollar (Selling)", 4),
    row("TP.DK.GBP.A.YTL", "(GBP) İngiliz Sterlini (Döviz Alış)", "(GBP) Pound (Buying)", 5),
    row("TP.DK.CHF.A.YTL", "(CHF) İsviçre Frangı (Döviz Alış)", "(CHF) Swiss Franc (Buying)", 6),
    row("TP.DK.JPY.A.YTL", "(JPY) Japon Yeni (Döviz Alış)", "(JPY) Japanese Yen (Buying)", 7),
]


class ListSource:
    """Answers the fixed series-list address of a datagroup; counts what it was asked."""

    def __init__(self, fail=False):
        self.requests, self.fail = [], fail

    def __call__(self, request):
        self.requests.append(request.source_ref)
        if self.fail:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
        return FetchSuccess(
            source_ref=request.source_ref,
            content=json.dumps(SERIES_LIST, ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


class DailySource:
    """Every calendar day of the asked window, weekends null, as EVDS lists a GÜNLÜK series."""

    def __init__(self, empty=False):
        self.requests, self.empty = [], empty

    def __call__(self, request):
        self.requests.append(request)
        key, items = request.code.replace(".", "_"), []
        cursor = request.window.start
        while cursor <= request.window.end and not self.empty:
            moment = datetime(cursor.year, cursor.month, cursor.day, tzinfo=SOURCE_DAY)
            items.append(
                {
                    "Tarih": f"{cursor:%d-%m-%Y}",
                    key: None if cursor.weekday() >= 5 else f"{30 + cursor.day / 100:.8f}",
                    "UNIXTIME": {"$numberLong": str(int(moment.astimezone(UTC).timestamp()))},
                }
            )
            cursor += timedelta(days=1)
        return FetchSuccess(
            source_ref=request.fetch_request().source_ref,
            content=json.dumps({"totalCount": len(items), "items": items}).encode(),
            media_type="application/json",
            http_status=200,
        )


@pytest.fixture(scope="module")
def catalogue():
    reviewed = load_reviewed_snapshot(CATALOG.read_bytes())
    return reviewed, effective_snapshot(reviewed, [], [], source_directory())


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as opened:
        yield opened


def found(snapshot, query):
    return search_catalog(snapshot, CatalogSearchArguments(query=query))


# --- datagroups are entries, in a lane of their own ----------------------------------------------


def test_every_listed_datagroup_is_an_entry_and_the_catalogue_digest_is_stable(catalogue):
    _, effective = catalogue
    groups = [item for item in effective.series if is_source_group(item)]
    assert len(groups) > 600 and all(is_listed_series(item) for item in groups)
    assert all(item.record.series_id.startswith(EVDS_GROUP_PREFIX) for item in groups)
    archived = [item for item in groups if item.record.status is CatalogStatus.ARCHIVED]
    assert 0 < len(archived) < len(groups)
    # Opening a datagroup never changes the catalogue a vector generation was built for.
    assert source_directory().digest == source_directory().digest
    assert not any(is_source_group(item) for item in catalogue[0].series)


def test_a_datagroup_is_found_but_never_a_candidate(catalogue):
    _, effective = catalogue
    output = found(effective, "döviz kurları dolar")
    assert [g.series.record.series_id for g in output.groups][0] == EVDS_GROUP_PREFIX + GROUP
    assert 0 < len(output.groups) <= MAX_GROUPS
    assert not any(is_source_group(c.series) for c in output.candidates)
    assert all(is_source_group(g.series) for g in output.groups)
    assert all(g.series.record.status is not CatalogStatus.ARCHIVED for g in output.groups)


def test_a_kind_word_in_the_question_does_not_push_datagroups_out(catalogue):
    """Probe 2026-09-19: "faizi" ranked ten reviewed credit rates above every deposit group."""
    _, effective = catalogue
    output = found(effective, "mevduat faizi")
    assert output.groups and "mevduat" in output.groups[0].series.record.title.lower()
    assert not any(is_source_group(c.series) for c in output.candidates)


def test_a_reviewed_concept_still_bounds_the_result_and_carries_no_datagroup(catalogue):
    _, effective = catalogue
    output = found(effective, "konut kredisi faiz oranı")
    assert output.concepts and output.groups == ()
    assert not any(is_listed_series(c.series) for c in output.candidates)


# --- the series lists a search has opened --------------------------------------------------------


def test_a_datagroup_is_read_once_and_kept_under_the_state_root(tmp_path):
    source = ListSource()
    store = DiscoveredStore(tmp_path / "evds", fetch=source)
    declared = store.series_of(GROUP)
    assert [item.code for item in declared][:2] == ["TP.DK.EUR.A.YTL", "TP.DK.EUR.S.YTL"]
    assert len(declared) == len(SERIES_LIST) and store.series_of(GROUP) == declared
    assert source.requests == ["evds:serie-list:" + GROUP]
    # Another process (a restart) reads the kept list, not the source.
    again = DiscoveredStore(tmp_path / "evds", fetch=(unused := ListSource()))
    assert [item.code for item in again.declared()] == sorted(item.code for item in declared)
    assert unused.requests == [] and again.opened_groups() == (GROUP,)
    dollar = again.lookup(DOLLAR)
    assert dollar is not None and (dollar.unit, dollar.frequency.value) == ("TRY", "daily")
    assert again.entry(DOLLAR).record.title == "(USD) ABD Doları (Döviz Alış)"
    assert is_listed_series(again.entry(DOLLAR)) and again.lookup("EVDS:TP.NOT.LISTED") is None
    assert again.lookup("BDDK:anything") is None


def test_a_failed_or_unknown_read_keeps_nothing(tmp_path):
    store = DiscoveredStore(tmp_path / "evds", fetch=(source := ListSource(fail=True)))
    assert store.series_of(GROUP) == () and store.opened_groups() == ()
    assert store.series_of("bie_not_in_the_pinned_directory") == ()
    assert source.requests == ["evds:serie-list:" + GROUP]  # the unknown code was never asked
    assert store.series_of(GROUP, read=False) == ()


# --- expansion -----------------------------------------------------------------------------------


def test_the_series_a_question_names_come_first_within_a_datagroup(tmp_path):
    store = DiscoveredStore(tmp_path / "evds", fetch=ListSource())
    ranked = [item.code for _, item in rank_series("dolar kuru", store.series_of(GROUP))]
    assert ranked[:2] == ["TP.DK.USD.A.YTL", "TP.DK.USD.S.YTL"]
    assert ranked[2:] == [r["SERIE_CODE"] for r in SERIES_LIST if ".USD." not in r["SERIE_CODE"]]


def test_a_found_datagroup_is_replaced_by_its_series_in_turns(catalogue, tmp_path):
    _, effective = catalogue
    store = DiscoveredStore(tmp_path / "evds", fetch=ListSource(fail=False))
    output = found(effective, "döviz kurları dolar")
    opened = expand_groups("döviz kurları dolar", output, store)
    ids = [c.series.record.series_id for c in opened.candidates]
    assert opened.groups == () and len(ids) == len(set(ids)) <= MAX_CANDIDATES
    assert [c.rank for c in opened.candidates] == list(range(1, len(ids) + 1))
    # Lanes take turns: the search's own first candidate, then the first opened series.
    assert ids[0] == output.candidates[0].series.record.series_id and ids[1] == DOLLAR
    assert not any(is_source_group(c.series) for c in opened.candidates)
    assert opened.top_candidate == "unconfirmed" and opened.clarification_required
    assert sum(identity.startswith("EVDS:TP.DK.") for identity in ids) >= 3


def test_without_a_store_datagroups_are_dropped_not_shown(catalogue):
    _, effective = catalogue
    output = found(effective, "döviz kurları dolar")
    closed = expand_groups("döviz kurları dolar", output, None)
    assert closed.groups == () and closed.candidates == output.candidates
    tool = make_catalog_search_tool(snapshot_bytes=effective.model_dump_json().encode())
    result = tool.run(
        CatalogSearchArguments(query="döviz kurları dolar"), ExecutionContext(question="q")
    )
    assert result.output.groups == ()
    assert not any(is_source_group(c.series) for c in result.output.candidates)


# --- fetched by the same adapter, checked by the same inspector ----------------------------------


def acquiring(lake, effective, store, source):
    acquirer = TurnAcquirer(
        lake, TODAY, sources=OfficialSources(evds=source, listed_evds=store.lookup)
    )
    return AcquiringInspector(PreparedSeriesInspector(effective, late=store.entry), acquirer)


def test_a_listed_series_is_fetched_to_the_clocks_day_and_inspected(catalogue, lake, tmp_path):
    _, effective = catalogue
    store = DiscoveredStore(tmp_path / "evds", fetch=ListSource())
    store.series_of(GROUP)
    inspector = acquiring(lake, effective, store, source := DailySource())
    assert inspector.inspect(lake.connection, DOLLAR).status == "consistent"
    (request,) = source.requests
    # A month must be whole; a day need not be (live: the rate of 2026-09-18 on 2026-09-19).
    assert (request.window.start, request.window.end) == (date(2000, 1, 1), TODAY)
    stored = lake.connection.execute(
        "SELECT count(*), count(value), max(period_end) FROM silver_observations "
        "WHERE series_id = ?",
        [DOLLAR],
    ).fetchone()
    assert stored == (41, 29, TODAY)
    assert inspector.name_of(DOLLAR).startswith("EVDS: (USD) ABD Doları (Döviz Alış)")
    assert inspector.why_unread(DOLLAR) is None
    # An identity no search has opened stays unknown: nothing is asked of the source.
    assert inspector.inspect(lake.connection, "EVDS:TP.NEVER.LISTED").status == "unknown_identity"
    assert len(source.requests) == 1


def test_a_series_the_source_publishes_nothing_for_says_so(catalogue, lake, tmp_path):
    """Live 2026-09-19: Germany's policy rate is listed, and empty for every fetched year."""
    _, effective = catalogue
    store = DiscoveredStore(tmp_path / "evds", fetch=ListSource())
    store.series_of(GROUP)
    inspector = acquiring(lake, effective, store, DailySource(empty=True))
    assert inspector.inspect(lake.connection, EURO).status == "not_prepared"
    (attempt,) = inspector._acquirer.attempts
    assert attempt.code is AcquisitionCode.REFUSED
    assert attempt.detail == EvdsLoadCode.NO_OBSERVATIONS.value
    assert inspector.why_unread(EURO) == UNREAD_REASONS["empty"]
    tool = make_lakehouse_tool(lake.connection, lineage=lake.lineage, inspector=inspector)
    refused = tool.run(
        tool.arguments.model_validate({"series": [EURO]}), ExecutionContext(question="q")
    )
    assert refused.error_category == "series_unknown"
    assert "publishes no observation" in refused.warnings[0]


def test_a_typed_read_says_what_each_series_is(catalogue, lake, tmp_path):
    _, effective = catalogue
    store = DiscoveredStore(tmp_path / "evds", fetch=ListSource())
    store.series_of(GROUP)
    inspector = acquiring(lake, effective, store, DailySource())
    tool = make_lakehouse_tool(lake.connection, lineage=lake.lineage, inspector=inspector)
    result = tool.run(
        tool.arguments.model_validate({"series": [DOLLAR], "last": 5}),
        ExecutionContext(question="q"),
    )
    # Weekends are periods without a value in the store; a read of a daily series skips them.
    assert [v.period.end.weekday() < 5 for v in result.output.result.values] == [True] * 5
    assert [v.period.end for v in result.output.result.values][-1] == TODAY
    whole = tool.run(
        tool.arguments.model_validate({"series": [DOLLAR]}), ExecutionContext(question="q")
    )
    assert len(whole.output.result.values) == 29 and not whole.output.truncated
    names = result.output.result.parameters["series_names"]
    assert list(names) == [DOLLAR] and "ABD Doları" in names[DOLLAR]
    assert "daily" in names[DOLLAR] and "TRY" in names[DOLLAR]


# --- a served turn -------------------------------------------------------------------------------


def test_a_served_question_on_a_series_no_catalogue_named_is_answered(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    lists, source = ListSource(), DailySource()
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "döviz kurları dolar"},
                }
            ),
            proposal(
                {
                    "step_id": "read",
                    "tool": "lakehouse",
                    "arguments": {"series": [DOLLAR], "last": 5},
                }
            ),
            "Tabloda ABD doları döviz alış kurunun son beş günlük değerleri yer alıyor.",
        ),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(evds=source),
        clock=lambda: TODAY,
        source_directory=source_directory(),
        discovered=DiscoveredStore(tmp_path / "runtime-evds", fetch=lists),
    )
    answer = runner(uuid4().hex, uuid4().hex, "Dolar kurunun son beş gününü getir.")
    assert answer.status.value == "accepted", answer
    assert len(lists.requests) <= MAX_GROUPS and len(source.requests) == 1
    assert [cell.unit for cell in answer.result.cells] == ["TRY"] * 5
    assert answer.result.cells[-1].value == pytest.approx(30.10)
    # The person is told which entry was picked among neighbours, in words, and what else
    # the search showed; none of it is model text.
    (picked,) = answer.selection.chosen
    assert picked.series_id == DOLLAR and picked.title == "(USD) ABD Doları (Döviz Alış)"
    assert picked.detail == "Döviz Kurları, EVDS/TCMB, günlük, TRY, bakiye (stok)"
    others = [item.title for item in answer.selection.others]
    assert "(USD) ABD Doları (Döviz Satış)" in others and picked.title not in others
    assert all(not item.title.startswith("EVDS:") for item in answer.selection.others)


def test_a_reviewed_match_needs_no_selection_note(tmp_path):
    from test_catalog_continuation import TOTAL

    root = tmp_path / "prepared"
    seed_prepared(root)
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "toplam konut kredisi bakiyesi"},
                }
            ),
            proposal({"step_id": "r", "tool": "lakehouse", "arguments": {"series": [TOTAL]}}),
            "Tabloda serinin değerleri yer alıyor.",
        ),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        clock=lambda: TODAY,
        source_directory=source_directory(),
    )
    answer = runner(uuid4().hex, uuid4().hex, "Konut kredisi serisini getir.")
    assert answer.status.value == "accepted", answer
    assert answer.selection is None  # a reviewed concept named the series: nothing to disclose


def test_a_series_clarification_offers_its_entries_as_choices(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "döviz kurları dolar"},
                }
            ),
            proposal(clarification="ambiguous_series"),
        ),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(evds=DailySource()),
        clock=lambda: TODAY,
        source_directory=source_directory(),
        discovered=DiscoveredStore(tmp_path / "runtime-evds", fetch=ListSource()),
    )
    answer = runner(uuid4().hex, uuid4().hex, "Dolar kurunu getir.")
    assert answer.status.value == "abstained"
    assert answer.selection.chosen == () and len(answer.selection.others) >= 3
    titles = [item.title for item in answer.selection.others]
    assert "(USD) ABD Doları (Döviz Alış)" in titles
    # The same entries, in the same order, are the lines of the clarification text.
    assert all(title in answer.text for title in titles)


# --- the directory is read again: what the source added becomes searchable ---------------------


NEW_GROUP = {
    "DATAGROUP_CODE": "bie_yenigrup",
    "DATAGROUP_TYPE": "Yeşil Tahvil İhraçları",
    "DATAGROUP_TYPE_ENG": "Green Bond Issues",
    "FREQUENCY_STR": "AYLIK",
    "DATASOURCE": "TCMB",
    "BIRIMI": "milyon TL",
}


class DirectorySource(ListSource):
    """EVDS's live directory (every pinned datagroup plus one new) and any series list."""

    def __init__(self, fail_directory=False):
        super().__init__()
        self.fail_directory = fail_directory

    def __call__(self, request):
        if request.source_ref != "evds:directory":
            return super().__call__(request)
        self.requests.append(request.source_ref)
        if self.fail_directory:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
        from kkb_agent.ingest.evds_directory import listed_groups

        pinned = [
            {
                "DATAGROUP_CODE": group.code,
                "DATAGROUP_TYPE": group.title,
                "DATAGROUP_TYPE_ENG": group.title_eng,
                "FREQUENCY_STR": group.frequency_str,
                "DATASOURCE": group.data_source,
                "BIRIMI": group.unit_text,
            }
            for group in listed_groups()[1:]  # the source withdrew one
        ]
        categories = [
            {"CATEGORY_ID": 1, "TOPIC_TITLE_TR": "PARA VE BANKA", "UST_CATEGORY_ID": None},
            {
                "CATEGORY_ID": 2,
                "TOPIC_TITLE_TR": "SERMAYE PİYASASI",
                "UST_CATEGORY_ID": 1,
                "DATAGROUPS": [*pinned, NEW_GROUP],
            },
        ]
        return FetchSuccess(
            source_ref=request.source_ref,
            content=json.dumps(categories, ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


def test_a_refresh_lists_new_datagroups_and_rereads_the_opened_ones(tmp_path):
    source = DirectorySource()
    store = DiscoveredStore(tmp_path / "evds", fetch=source)
    store.series_of(GROUP)
    before = source_directory(store.supplement())
    found = store.refresh()
    assert [group.code for group in found.added] == ["bie_yenigrup"]
    assert found.added[0].category == "PARA VE BANKA > SERMAYE PİYASASI"
    assert (found.withdrawn, found.reopened, found.failed) == (1, 1, 0)
    assert source.requests == [
        "evds:serie-list:" + GROUP,
        "evds:directory",
        "evds:serie-list:" + GROUP,
    ]
    # The new datagroup is a catalogue entry, so the catalogue (and its vectors) changed...
    after = source_directory(store.supplement())
    assert after.digest != before.digest and len(after.series) == len(before.series) + 1
    assert EVDS_GROUP_PREFIX + "bie_yenigrup" in after.ids()
    # ...it survives a restart, and it can be opened like any pinned datagroup.
    again = DiscoveredStore(tmp_path / "evds", fetch=(later := DirectorySource()))
    assert [group.code for group in again.supplement()] == ["bie_yenigrup"]
    assert again.opened_groups() == (GROUP,)
    assert again.series_of("bie_yenigrup") != () and later.requests == [
        "evds:serie-list:bie_yenigrup"
    ]


def test_a_refresh_that_cannot_read_the_directory_changes_nothing(tmp_path):
    store = DiscoveredStore(tmp_path / "evds", fetch=DirectorySource(fail_directory=True))
    assert store.refresh() is None and store.supplement() == ()
    assert source_directory(store.supplement()).digest == source_directory().digest


def test_the_knowledge_page_refreshes_the_directory_for_later_turns(tmp_path):
    from fastapi.testclient import TestClient
    from test_conversation_persistence import owner
    from test_document_dataset import BASE

    from kkb_agent.api.app import create_app
    from kkb_agent.api.knowledge_service import KnowledgeService
    from kkb_agent.api.service import AnalysisService
    from kkb_agent.api.store import DATABASE_NAME, ConversationStore
    from kkb_agent.knowledge import KnowledgeStore

    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    conversations = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    knowledge = KnowledgeStore(tmp_path.resolve() / "state" / "knowledge.sqlite")
    discovered = DiscoveredStore(tmp_path / "evds", fetch=DirectorySource())
    directory = source_directory(discovered.supplement())
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=conversations,
        knowledge=knowledge,
        official=OfficialSources(evds=DailySource()),
        source_directory=directory,
        discovered=discovered,
    )
    service = KnowledgeService(
        knowledge,
        conversations,
        runner.catalog,
        prepared=frozenset(item.series_id for item in runner.status.series),
        acquisition=True,
        source_directory=directory,
        discovered=discovered,
        install_directory=runner.use_directory,
    )
    app = create_app(
        AnalysisService(runner, mode="scripted", store=conversations, knowledge=True),
        prepared=runner.status,
        knowledge=service,
    )
    with TestClient(app, base_url=BASE) as client:
        key = {"X-KKB-Owner-Token": owner(client)}
        assert client.post("/v1/knowledge/directory", json={}).status_code >= 400  # no key
        found = client.post("/v1/knowledge/directory", json={}, headers=key)
        assert found.status_code == 200, found.text
        body = found.json()
        assert body["added"] == ["Yeşil Tahvil İhraçları"] and body["added_total"] == 1
        assert body["catalog_changed"] is True and body["withdrawn"] == 1
        # The trial search (what a turn would search) finds the new datagroup's series.
        hits = client.get(
            "/v1/knowledge/search", params={"q": "yeşil tahvil ihraçları"}, headers=key
        )
        assert hits.status_code == 200 and hits.json()["hits"], hits.text
        assert (
            client.post("/v1/knowledge/directory", json={}, headers=key).json()["catalog_changed"]
            is False
        )
    conversations.close()
    knowledge.close()
