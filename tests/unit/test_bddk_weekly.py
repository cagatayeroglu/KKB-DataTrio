"""DEC-182: the BDDK weekly bulletin is listed, declared, fetched and found like its sibling.

No network here. The fake source answers the way the real one was measured to on
2026-09-20: asked for a date, it returns the published weeks dated within the ninety days
up to it, a holiday week dated to its last working day, an unknown id as an empty chart.
"""

import io
import json
from datetime import date, timedelta

import pytest
from test_bounded_fetch import output_for, wire
from test_bounded_fetch import transport as transport
from test_catalog_continuation import CATALOG

from kkb_agent.api.prepared import open_lakehouse
from kkb_agent.catalog.directory import BDDK_WEEKLY_EVIDENCE_ID, source_directory
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import is_listed_series, load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionCode,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
    has_reviewed_route,
    weekly_selector,
)
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.bddk_weekly import (
    SUPPORTED_WEEKLY_ROWS,
    UnlistedWeeklySelector,
    expected_title,
    supported_weekly_selectors,
    weekly_directory_catalog,
)
from kkb_agent.ingest.bddk_weekly_directory import DIRECTORY, DIRECTORY_SHA256
from kkb_agent.ingest.bddk_weekly_load import (
    MAX_LAG_DAYS,
    WeeklyLoadCode,
    WeeklyLoadError,
    ingest_weekly,
    parse_weekly,
)
from kkb_agent.ingest.bddk_weekly_request import (
    FIRST_WEEK,
    WEEKLY_LIMITS,
    WeeklyRequest,
    fetch_weekly,
    friday_of,
    grid_windows,
)
from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchRequest,
    FetchSuccess,
)
from kkb_agent.knowledge.overlay import effective_snapshot

#: A Sunday, as on the day the source was measured; the latest published week ends 11.09.
TODAY = date(2026, 9, 20)
LATEST = date(2026, 9, 11)
#: Weeks the source dates to a working day before their holiday Friday (measured).
HOLIDAYS = {
    date(2021, 1, 1): date(2020, 12, 31),
    date(2021, 5, 14): date(2021, 5, 12),
    date(2021, 7, 23): date(2021, 7, 19),
    date(2023, 4, 21): date(2023, 4, 20),
    date(2024, 4, 12): date(2024, 4, 9),
}


def selector(table=1, row=4, component="TOTAL", **updates):
    base = BddkSelector(
        bulletin_family="weekly",
        table=table,
        row=row,
        bank_group=10001,
        presentation_currency="TL",
        value_dimension=component,
    )
    return base.model_copy(update=updates)


HOUSING = selector()


def value_of(friday: date) -> float:
    return float(friday.toordinal() - FIRST_WEEK.toordinal()) + 0.5


def answer(request: WeeklyRequest, *, latest=LATEST, **changes) -> dict:
    """What the measured source returns: published weeks dated in [asked - 90 days, asked]."""
    weeks = []
    friday = friday_of(request.asked - timedelta(days=97))
    while friday <= latest:
        dated = HOLIDAYS.get(friday, friday)
        if request.asked - timedelta(days=90) <= dated <= request.asked:
            weeks.append((dated, friday))
        friday += timedelta(weeks=1)
    body = {
        "Baslik": expected_title(request.selector),
        "XEkseni": [f"{day.day}.{day.month:02d}.{day.year}" for day, _ in weeks],
        "YEkseni": [value_of(friday) for _, friday in weeks],
    }
    body.update(changes)
    return body


def encoded(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


class WeeklySource:
    def __init__(self, *, latest=LATEST, failure=None, spoil=None):
        self.latest, self.failure, self.spoil = latest, failure, spoil
        self.asked: list[date] = []

    def __call__(self, request: WeeklyRequest):
        self.asked.append(request.asked)
        if self.failure is not None and len(self.asked) == self.failure:
            return FetchFailure(
                source_ref=request.fetch_request().source_ref, code=FetchCode.HTTP_FAILURE
            )
        body = answer(request, latest=self.latest)
        if self.spoil is not None:
            body = self.spoil(request, body)
        return FetchSuccess(
            source_ref=request.fetch_request().source_ref,
            content=encoded(body),
            media_type="application/json",
            http_status=200,
        )


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as opened:
        yield opened


# --- the listing and what it declares ------------------------------------------------------------


def test_the_listing_is_pinned_and_holds_all_nine_tables_in_page_order():
    assert len(DIRECTORY_SHA256) == 64
    assert DIRECTORY["unit_text"] == "Milyon TL" and DIRECTORY["side"] == "Sektör"
    assert list(DIRECTORY["tables"]) == [str(number) for number in range(1, 10)]
    assert sum(len(table["rows"]) for table in DIRECTORY["tables"].values()) == 179
    # The two tables an id-guessing harvest missed: their item ids do not start at 1.
    assert [row["row"] for row in DIRECTORY["tables"]["9"]["rows"]][:2] == [11, 12]
    assert len(DIRECTORY["tables"]["3"]["rows"]) == 13
    for table in DIRECTORY["tables"].values():
        assert [row["number"] for row in table["rows"]] == list(range(1, len(table["rows"]) + 1))
    # No observation is kept: a row is numbers the page shows it under, labels and columns.
    assert {
        key for table in DIRECTORY["tables"].values() for row in table["rows"] for key in row
    } == {
        "number",
        "row",
        "label",
        "parent",
        "columns",
    }


def test_a_row_is_titled_by_where_it_sits_and_no_table_has_two_rows_of_one_title():
    assert SUPPORTED_WEEKLY_ROWS[1, 4].title == "Tüketici Kredileri - Konut"
    assert SUPPORTED_WEEKLY_ROWS[1, 1].title == "Toplam Krediler"
    # The custody tables repeat their groups for residents and non-residents.
    assert (
        SUPPORTED_WEEKLY_ROWS[7, 3].title == "Yurtiçi Yerleşikler Adına Saklanan - Gerçek Kişiler"
    )
    assert SUPPORTED_WEEKLY_ROWS[7, 25].title == (
        "Yurtdışı Yerleşikler Adına Saklanan - Gerçek Kişiler"
    )
    assert SUPPORTED_WEEKLY_ROWS[7, 26].title.endswith("Gerçek Kişiler - Kamu Borçlanma Senetleri")
    # A memo row no arithmetic names takes the section it stands in.
    assert SUPPORTED_WEEKLY_ROWS[7, 45].title.startswith("Yurtdışı Yerleşikler")
    seen: dict[tuple[int, str], int] = {}
    for (table, row), listed in SUPPORTED_WEEKLY_ROWS.items():
        assert seen.setdefault((table, listed.title), row) == row
    assert len(SUPPORTED_WEEKLY_ROWS) == 179 and len(supported_weekly_selectors()) == 515


def test_a_weekly_item_is_a_week_end_position_in_million_lira_reduced_by_its_last_week():
    record = weekly_directory_catalog(HOUSING)
    assert (record.unit, record.scale) == ("TRY", Scale.MILLION)
    assert (record.frequency, record.weekly_anchor) == (Frequency.WEEKLY, WeeklyAnchor.FRIDAY)
    assert (record.stock_flow, record.cumulative) == (StockFlow.STOCK, CumulativeKind.NONE)
    assert record.aggregation.default is Aggregation.LAST and record.aggregation.sum is False
    assert record.labels[0] == "Haftalık Bülten" and record.labels[2] == "TOTAL"
    assert record.labels[-1] == "Krediler"
    assert "Haftalık" in record.description and "cuma" in record.description
    # The same sub-item of another table is another series, told apart by its table.
    overdue = weekly_directory_catalog(selector(2, 10))
    assert overdue.title == record.title and overdue.series_id != record.series_id
    assert overdue.labels[-1] == "Takipteki Alacaklar"
    # Identity is the selector, and a weekly selector is never a monthly one.
    assert (
        record.series_id != HOUSING.model_copy(update={"bulletin_family": "monthly"}).internal_id()
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"bulletin_family": "monthly"},
        {"bank_group": 10002},
        {"presentation_currency": "USD"},
        {"geography": "TR"},
        {"row": 999},
        {"table": 4, "row": 11, "value_dimension": "YP"},  # that row has no YP column
        {"table": 9, "row": 17, "value_dimension": "TP"},  # that table has a total only
    ],
)
def test_a_selector_outside_the_listing_is_refused_before_any_request(lake, changes):
    chosen = selector(**changes)
    with pytest.raises(UnlistedWeeklySelector):
        weekly_directory_catalog(chosen)
    with pytest.raises(ValueError):
        WeeklyRequest(selector=chosen, asked=TODAY)
    source = WeeklySource()
    with pytest.raises(UnlistedWeeklySelector):
        ingest_weekly(lake, chosen, TODAY, retrieve=source)
    assert not source.asked and weekly_selector(chosen.internal_id()) is None


# --- the request ---------------------------------------------------------------------------------


def test_the_form_is_fixed_and_names_the_item_the_column_and_the_day():
    body = WeeklyRequest(selector=selector(4, 11, "TP"), asked=date(2026, 9, 4)).form_body()
    assert body == (
        b"dil=tr&tarih=04.09.2026&id=4.0.11&parabirimi=TRY&sutun=1&gun=90&tarafKodu=10001"
    )
    one = WeeklyRequest(selector=HOUSING, asked=date(2026, 9, 4))
    other = WeeklyRequest(selector=HOUSING, asked=date(2026, 9, 11))
    assert one.fingerprint() != other.fingerprint()
    assert one.fetch_request().source_ref == "bddk:weekly:" + one.fingerprint()
    with pytest.raises(ValueError):
        WeeklyRequest(selector=HOUSING, asked=date(2020, 12, 25))


def test_windows_sit_on_a_grid_counted_from_the_first_week_never_from_today():
    ends = grid_windows(LATEST)
    assert ends[0] == date(2021, 3, 26) and ends[0] - timedelta(weeks=12) == FIRST_WEEK
    assert all(
        after - before == timedelta(weeks=13) for before, after in zip(ends, ends[1:], strict=False)
    )
    assert ends[-1] == date(2026, 6, 19) and len(ends) == 22
    # A week later the same windows are asked for again, so their kept answers still serve;
    # the grid Friday that week reached is the one window added.
    assert grid_windows(LATEST + timedelta(weeks=1)) == (*ends, date(2026, 9, 18))
    assert grid_windows(date(2021, 1, 8)) == ()
    with pytest.raises(ValueError):
        grid_windows(date(2026, 9, 10))


# --- the parser ----------------------------------------------------------------------------------


def parsed(asked: date, **changes):
    request = WeeklyRequest(selector=HOUSING, asked=asked)
    return parse_weekly(encoded(answer(request, **changes)), request)


def test_an_answer_dated_to_a_published_friday_is_thirteen_consecutive_weeks():
    weeks = parsed(LATEST)
    assert len(weeks) == 13
    assert (weeks[0].period_end, weeks[-1].period_end) == (date(2026, 6, 19), LATEST)
    assert all(week.period_end - week.period_start == timedelta(days=6) for week in weeks)
    # Two days later the ninety days no longer reach the first of them.
    assert [week.period_end for week in parsed(TODAY)][0] == date(2026, 6, 26)
    assert len(parsed(TODAY)) == 12


@pytest.mark.parametrize(
    ("asked", "friday"),
    [
        (date(2021, 8, 13), date(2021, 7, 23)),  # dated Monday 19.07.2021
        (date(2024, 5, 3), date(2024, 4, 12)),  # dated Tuesday 9.04.2024
        (date(2021, 5, 14), date(2021, 5, 14)),  # dated Wednesday 12.05.2021
        (date(2023, 5, 12), date(2023, 4, 21)),  # dated Thursday 20.04.2023
        (date(2021, 1, 8), date(2021, 1, 1)),  # dated to the last day of 2020
    ],
)
def test_a_holiday_week_is_filed_under_its_friday(asked, friday):
    weeks = parsed(asked)
    assert friday in [week.period_end for week in weeks]
    assert all(week.period_end.weekday() == 4 for week in weeks)
    (held,) = [week for week in weeks if week.period_end == friday]
    assert held.value == value_of(friday)


def spoiled(**changes):
    request = WeeklyRequest(selector=HOUSING, asked=LATEST)
    body = answer(request)
    body.update(changes)
    return request, body


@pytest.mark.parametrize(
    "body",
    [
        {"Baslik": "b) Taşıt (TRY) [Toplam] [Sektör]"},  # another item
        {"Baslik": "a) Konut (TRY) [TP] [Sektör]"},  # another column
        {"Baslik": "a) Konut (TRY) [Toplam] [Mevduat]"},  # another side
        {"Baslik": "Grafik Başlığı", "XEkseni": [], "YEkseni": []},  # an id the source lacks
        {"XEkseni": ["5.09.2026"], "YEkseni": [1.0]},  # a Saturday
        {"XEkseni": ["18.09.2026"], "YEkseni": [1.0]},  # after the day asked for
        {"XEkseni": ["28.08.2026", "11.09.2026"], "YEkseni": [1.0, 2.0]},  # a week is missing
        {"XEkseni": ["4.09.2026", "4.09.2026"], "YEkseni": [1.0, 2.0]},  # a week twice
        {"XEkseni": ["04/09/2026"], "YEkseni": [1.0]},
        {"XEkseni": ["4.09.2026"], "YEkseni": ["1.0"]},  # a number is a JSON number
        {"XEkseni": ["4.09.2026"], "YEkseni": [1.0, 2.0]},
        {"Ek": 1},
    ],
)
def test_an_answer_that_is_not_what_was_asked_is_refused_whole(body):
    request, base = spoiled(**body)
    with pytest.raises(WeeklyLoadError) as refused:
        parse_weekly(encoded(base), request)
    assert refused.value.code is WeeklyLoadCode.RESPONSE_INVALID


def test_the_source_pads_some_titles_and_a_missing_value_stays_missing():
    request = WeeklyRequest(selector=selector(3, 15), asked=LATEST)
    body = answer(request)
    body["Baslik"] = "  " + body["Baslik"].replace(" (TRY)", "  (TRY)")
    body["YEkseni"][3] = None
    weeks = parse_weekly(encoded(body), request)
    assert weeks[3].value is None and weeks[4].value is not None
    duplicate = b'{"Baslik":"x","Baslik":"' + expected_title(HOUSING).encode() + b'"}'
    with pytest.raises(WeeklyLoadError):
        parse_weekly(duplicate, WeeklyRequest(selector=HOUSING, asked=LATEST))


# --- the loader ----------------------------------------------------------------------------------


def stored(lake, series_id):
    return lake.connection.execute(
        "SELECT period_start, period_end, value FROM silver_observations"
        " WHERE series_id = ? ORDER BY period_end",
        [series_id],
    ).fetchall()


def test_a_series_is_every_week_from_the_first_to_the_latest_each_from_one_answer(lake):
    source = WeeklySource()
    done = ingest_weekly(lake, HOUSING, TODAY, retrieve=source)
    assert (done.first_week, done.last_week, done.weeks) == (FIRST_WEEK, LATEST, 298)
    assert done.missing_values == 0 and not done.already_present
    rows = stored(lake, done.series_id)
    assert [row[1] for row in rows] == [FIRST_WEEK + timedelta(weeks=n) for n in range(298)]
    assert all(row[2] == value_of(row[1]) for row in rows)
    # Today's answer first, then the twenty-two fixed windows: they meet, so no bridge.
    assert source.asked == [TODAY, *grid_windows(LATEST)]
    semantics = lake.semantics_of(done.series_id)
    assert (semantics.frequency, semantics.anchor) == (Frequency.WEEKLY, WeeklyAnchor.FRIDAY)
    assert (semantics.observation, semantics.aggregation) == (StockFlow.STOCK, Aggregation.LAST)
    again = ingest_weekly(lake, HOUSING, TODAY, retrieve=WeeklySource())
    assert again.already_present and again.manifest_id == done.manifest_id


def test_when_todays_answer_begins_after_the_last_window_one_more_window_joins_them(lake):
    # Two unpublished weeks: the answer dated today holds eleven weeks and begins 3.07.2026,
    # while the last complete window ended 19.06.2026. The week of 26.06 lies between them.
    today = date(2026, 9, 27)
    source = WeeklySource()
    done = ingest_weekly(lake, HOUSING, today, retrieve=source)
    assert source.asked[0] == today and source.asked[-1] == date(2026, 6, 26)
    assert len(source.asked) == 24
    assert [row[1] for row in stored(lake, done.series_id)] == [
        FIRST_WEEK + timedelta(weeks=n) for n in range(298)
    ]


def test_a_source_that_stopped_publishing_the_item_is_refused_not_stored_stale(lake):
    late = LATEST + timedelta(days=MAX_LAG_DAYS + 9)
    with pytest.raises(WeeklyLoadError) as refused:
        ingest_weekly(lake, HOUSING, late, retrieve=WeeklySource())
    assert refused.value.code is WeeklyLoadCode.RESPONSE_INVALID
    assert lake.connection.execute("SELECT COUNT(*) FROM silver_series").fetchone() == (0,)


def test_a_fixed_window_that_comes_back_short_refuses_the_whole_series(lake):
    def short(request, body):
        if request.asked == date(2024, 3, 22):
            body["XEkseni"], body["YEkseni"] = body["XEkseni"][:-1], body["YEkseni"][:-1]
        return body

    with pytest.raises(WeeklyLoadError) as refused:
        ingest_weekly(lake, HOUSING, TODAY, retrieve=WeeklySource(spoil=short))
    assert refused.value.code is WeeklyLoadCode.RESPONSE_INVALID
    assert lake.connection.execute("SELECT COUNT(*) FROM silver_series").fetchone() == (0,)


def test_a_failed_request_is_a_retrieval_failure_and_another_batch_is_a_conflict(lake):
    with pytest.raises(WeeklyLoadError) as failed:
        ingest_weekly(lake, HOUSING, TODAY, retrieve=WeeklySource(failure=5))
    assert failed.value.code is WeeklyLoadCode.RETRIEVAL_FAILED
    ingest_weekly(lake, HOUSING, TODAY, retrieve=WeeklySource())
    with pytest.raises(WeeklyLoadError) as conflict:
        ingest_weekly(
            lake,
            HOUSING,
            TODAY + timedelta(weeks=1),
            retrieve=WeeklySource(latest=date(2026, 9, 18)),
        )
    assert conflict.value.code is WeeklyLoadCode.VERSION_CONFLICT


# --- the route and the catalogue -----------------------------------------------------------------


def catalogue():
    reviewed = load_reviewed_snapshot(CATALOG.read_bytes())
    return reviewed, effective_snapshot(reviewed, [], [], source_directory())


def test_every_weekly_selector_has_a_route_and_a_second_lake_asks_only_for_today(tmp_path):
    assert all(has_reviewed_route(item.internal_id()) for item in supported_weekly_selectors())
    store = AcquisitionStore(tmp_path / "kept")
    source = WeeklySource()
    sources = OfficialSources(bddk_weekly=source, store=store, pause=lambda _: None)
    seen = []
    with open_lakehouse(tmp_path / "one") as lake:
        first = TurnAcquirer(lake, TODAY, sources=sources, observe=seen.append).acquire(
            HOUSING.internal_id()
        )
    assert first.code is AcquisitionCode.ACQUIRED and first.observations == 298
    assert (first.window_start, first.window_end) == (FIRST_WEEK, LATEST)
    assert not first.from_store and len(source.asked) == 23 and seen == [first]
    with open_lakehouse(tmp_path / "two") as lake:
        again = TurnAcquirer(lake, TODAY, sources=sources).acquire(HOUSING.internal_id())
        later = TurnAcquirer(lake, TODAY, sources=sources).acquire(selector(1, 5).internal_id())
    assert again.code is AcquisitionCode.ACQUIRED and again.from_store
    assert len(source.asked) == 23 + 23 and later.stored  # another series is asked for afresh
    # A week on, the source has published one more week. Only the answer dated that day and
    # the grid window that week completed are asked for; the rest is served from kept bytes.
    source.latest = date(2026, 9, 18)
    with open_lakehouse(tmp_path / "three") as lake:
        next_week = TurnAcquirer(lake, TODAY + timedelta(weeks=1), sources=sources).acquire(
            HOUSING.internal_id()
        )
    assert next_week.stored and next_week.observations == 299
    assert source.asked[46:] == [TODAY + timedelta(weeks=1), date(2026, 9, 18)]
    assert store.acquisitions()[HOUSING.internal_id()]["observations"] == 299


def test_a_refused_answer_is_a_refusal_and_an_unreachable_source_a_retrieval_failure(lake):
    def wrong(_request, body):
        return {**body, "Baslik": "Grafik Başlığı"}

    refused = TurnAcquirer(
        lake, TODAY, sources=OfficialSources(bddk_weekly=WeeklySource(spoil=wrong))
    ).acquire(HOUSING.internal_id())
    assert (refused.code, refused.detail) == (AcquisitionCode.REFUSED, "RESPONSE_INVALID")
    down = TurnAcquirer(
        lake,
        TODAY,
        sources=OfficialSources(bddk_weekly=WeeklySource(failure=1), pause=lambda _: None),
    ).acquire(HOUSING.internal_id())
    assert down.code is AcquisitionCode.RETRIEVAL_FAILED and not down.stored


def test_the_inspector_finds_a_fetched_weekly_series_consistent_with_its_entry(lake):
    _, effective = catalogue()
    inspector = AcquiringInspector(
        PreparedSeriesInspector(effective),
        TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk_weekly=WeeklySource())),
    )
    found = inspector.inspect(lake.connection, HOUSING.internal_id())
    assert found.status == "consistent"


def test_weekly_items_are_a_listed_tier_of_the_catalogue_with_their_own_evidence():
    reviewed, effective = catalogue()
    weekly = [
        item
        for item in effective.series
        if item.record.provider == "BDDK" and item.record.frequency is Frequency.WEEKLY
    ]
    assert len(weekly) == len(supported_weekly_selectors())
    assert all(is_listed_series(item) for item in weekly)
    assert all(item.evidence_ids == (BDDK_WEEKLY_EVIDENCE_ID,) for item in weekly)
    assert BDDK_WEEKLY_EVIDENCE_ID in {item.evidence_id for item in effective.evidence}
    ids = [item.record.series_id for item in effective.series]
    assert len(ids) == len(set(ids))
    assert ids[: len(reviewed.series)] == [item.record.series_id for item in reviewed.series]


def found(snapshot, query, **filters):
    return search_catalog(snapshot, CatalogSearchArguments(query=query, **filters))


def test_a_question_naming_weeks_reaches_the_weekly_series_a_monthly_concept_cannot_give():
    reviewed, effective = catalogue()
    # Unchanged: the reviewed monthly balance still answers the unqualified question.
    plain = found(effective, "konut kredisi bakiyesi")
    assert plain.status == "MATCH" and plain.top_candidate == "unambiguous"
    assert {c.series.record.frequency for c in plain.candidates} == {Frequency.MONTHLY}
    weekly = found(effective, "haftalık konut kredisi bakiyesi")
    assert (weekly.status, weekly.top_candidate) == ("PARTIAL", "unconfirmed")
    first = weekly.candidates[0].series.record
    assert first.series_id == HOUSING.internal_id() and not weekly.concepts
    assert {c.series.record.frequency for c in weekly.candidates} == {Frequency.WEEKLY}
    # One candidate per listed row: the total, since the question names neither TL nor FX.
    assert "TOTAL" in first.labels


def test_the_reviewed_bound_stays_where_lifting_it_would_lead_nowhere_or_backwards():
    reviewed, effective = catalogue()
    # No weekly series is titled with a word of the question: the monthly index still answers.
    index = found(effective, "haftalık TÜFE")
    assert index.status == "MATCH" and index.concepts
    assert {c.series.record.frequency for c in index.candidates} == {Frequency.MONTHLY}
    # A coarser calendar over a finer reviewed series is a resample of it, not another series.
    rate = found(effective, "konut kredisi faiz oranını aylık göster")
    assert rate.concepts and rate.status == "MATCH"
    assert rate.candidates == found(effective, "konut kredisi faiz oranını göster").candidates
    # Without the directory nothing changes at all.
    assert found(reviewed, "haftalık konut kredisi bakiyesi").status == "MATCH"


def test_without_a_reviewed_concept_the_named_calendar_only_orders_the_neighbours():
    _, effective = catalogue()
    weekly = found(effective, "haftalık ihtiyaç kredisi bakiyesi")
    plain = found(effective, "ihtiyaç kredisi bakiyesi")
    assert weekly.candidates[0].series.record.title == "Tüketici Kredileri - İhtiyaç"
    assert weekly.candidates[0].series.record.frequency is Frequency.WEEKLY
    frequencies = [c.series.record.frequency for c in weekly.candidates]
    assert frequencies == sorted(frequencies, key=lambda item: item is not Frequency.WEEKLY)
    assert Frequency.MONTHLY in {c.series.record.frequency for c in plain.candidates}


# --- transport -----------------------------------------------------------------------------------


def request():
    return WeeklyRequest(selector=HOUSING, asked=LATEST)


def test_the_weekly_post_uses_fixed_fields_the_bddk_host_and_no_credentials(transport):
    payload = encoded(answer(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json; charset=utf-8")])
    result = _fetch_worker.fetch_once(
        request().fetch_request(), WEEKLY_LIMITS, lambda: None, weekly=request()
    )
    assert isinstance(result, FetchSuccess) and result.content == payload
    assert transport.resolutions == [("www.bddk.org.tr", 443)]
    sent = b"".join(transport.sockets[0].sent)
    assert sent.startswith(b"POST /BultenHaftalik/tr/Home/KiyaslamaJsonGetir HTTP/1.1\r\n")
    assert b"Content-Type: application/x-www-form-urlencoded\r\n" in sent
    assert sent.endswith(request().form_body())
    assert b"Authorization:" not in sent and b"Cookie:" not in sent


def test_the_worker_refuses_a_changed_address_budget_or_a_second_contract(transport):
    from pydantic import SecretStr
    from test_bddk_monthly_load import request as monthly_request

    altered = (
        request()
        .fetch_request()
        .model_copy(update={"url": SecretStr("https://www.bddk.org.tr/BultenHaftalik/other")})
    )
    for fetch, limits, extra in (
        (altered, WEEKLY_LIMITS, {}),
        (request().fetch_request(), FetchLimits(), {}),
        (request().fetch_request(), WEEKLY_LIMITS, {"monthly": monthly_request()}),
    ):
        result = _fetch_worker.fetch_once(fetch, limits, lambda: None, weekly=request(), **extra)
        assert result.code == FetchCode.INVALID_REQUEST
    assert not transport.resolutions
    assert (
        _fetch_process.fetch_in_process(altered, WEEKLY_LIMITS, weekly=request()).code
        == FetchCode.INVALID_REQUEST
    )


def test_the_parent_hands_the_worker_only_the_closed_weekly_contract(transport, monkeypatch):
    payload = encoded(answer(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])

    class InlineWorker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, payload, *, timeout):
            data = json.loads(payload)
            assert set(data["weekly"]) == {"selector", "asked"}
            assert "body" not in data and "method" not in data
            result = _fetch_worker.fetch_once(
                FetchRequest.model_validate(data["request"]),
                FetchLimits.model_validate(data["limits"]),
                lambda: None,
                weekly=WeeklyRequest.model_validate(data["weekly"]),
            )
            return b"CONNECTED\n" + output_for(result), None

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: InlineWorker())
    assert fetch_weekly(request()).content == payload


def test_the_worker_revalidates_the_weekly_descriptor_it_was_handed(transport, monkeypatch):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    data = request().fetch_request().model_dump(mode="json")
    data["url"] = request().fetch_request().url.get_secret_value()
    message = {
        "request": data,
        "limits": WEEKLY_LIMITS.model_dump(mode="json"),
        "weekly": request().model_dump(mode="json"),
    }

    class Input:
        buffer = io.BytesIO(json.dumps(message).encode())

    class Output:
        buffer = io.BytesIO()

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    assert _fetch_worker.main() == 0
    assert Output.buffer.getvalue().startswith(b"CONNECTED\n")
    message["weekly"]["body"] = "untrusted"
    Input.buffer = io.BytesIO(json.dumps(message).encode())
    Output.buffer = io.BytesIO()
    assert _fetch_worker.main() == 1 and Output.buffer.getvalue() == b""
