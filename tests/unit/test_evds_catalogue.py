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
    assert output.groups and all("mevduat" in g.series.record.title.lower() for g in output.groups)


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
