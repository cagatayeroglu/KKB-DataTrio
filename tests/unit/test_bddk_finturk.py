"""BDDK FinTürk (province tables): listing, declarations, request, loader, route, worker.

Offline throughout. `FinturkSource` answers as the source was measured on 2026-09-21: one
table for one quarter, every province a row, and an error page for a quarter that has not
been published.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import date

import pytest
from test_bounded_fetch import output_for, wire
from test_bounded_fetch import transport as transport
from test_catalog_continuation import CATALOG

from kkb_agent.api.prepared import open_lakehouse
from kkb_agent.catalog.directory import BDDK_FINTURK_EVIDENCE_ID, source_directory
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import is_listed_series, load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionCode,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
    has_reviewed_route,
)
from kkb_agent.ingest.bddk_finturk import (
    PROVINCES,
    SUPPORTED_COLUMNS,
    UnlistedFinturkSelector,
    finturk_directory_catalog,
    listed_finturk,
    place_name,
    province_token,
    supported_finturk_selectors,
)
from kkb_agent.ingest.bddk_finturk_directory import DIRECTORY, DIRECTORY_SHA256
from kkb_agent.ingest.bddk_finturk_load import (
    FinturkLoadCode,
    FinturkLoadError,
    ingest_finturk,
    parse_finturk,
)
from kkb_agent.ingest.bddk_finturk_request import (
    FINTURK_LIMITS,
    FinturkRequest,
    Quarter,
    fetch_finturk,
    newest_quarter,
    quarters_until,
)
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchRequest,
    FetchSuccess,
)
from kkb_agent.knowledge.overlay import effective_snapshot

TODAY = date(2026, 9, 21)
LATEST = Quarter(year=2026, month=6)
QUARTERS = 22  # 2021-3 .. 2026-6


def selector(table=3, column=2, province="ISTANBUL", **updates):
    base = BddkSelector(
        bulletin_family="finturk",
        table=table,
        row=column,
        bank_group=10001,
        presentation_currency="TL",
        value_dimension="TOTAL",
        geography=province,
    )
    return base.model_copy(update=updates)


HOUSING = selector()


def value_of(table: int, column: int, place: str, quarter: Quarter) -> float:
    return float(quarter.year * 100 + quarter.month + column * 1000 + len(place) + table / 10)


def answer(request: FinturkRequest, **changes) -> dict:
    table = request.selector.table
    listed = DIRECTORY["tables"][str(table)]
    columns = len(listed["columns"])
    rows = [
        {
            "cell": [
                10001,
                request.quarter.year,
                request.quarter.month,
                place,
                "SEKTÖR",
                *(value_of(table, n, place, request.quarter) for n in range(1, columns + 1)),
            ]
        }
        for place in listed["provinces"]
    ]
    report = {
        "colNames": [*listed["identity"], *listed["columns"]],
        "data": {"page": 1, "total": 1, "records": len(rows), "rows": rows},
    }
    report.update(changes)
    return {"success": True, "Json": report}


def encoded(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


class FinturkSource:
    def __init__(self, *, latest=LATEST, failure=None, code=FetchCode.HTTP_FAILURE, spoil=None):
        self.latest, self.failure, self.code, self.spoil = latest, failure, code, spoil
        self.asked: list[tuple[int, str]] = []

    def __call__(self, request: FinturkRequest):
        self.asked.append((request.selector.table, request.quarter.key()))
        unpublished = (request.quarter.year, request.quarter.month) > (
            self.latest.year,
            self.latest.month,
        )
        if unpublished or (self.failure is not None and len(self.asked) == self.failure):
            return FetchFailure(
                source_ref=request.fetch_request().source_ref,
                code=FetchCode.HTTP_FAILURE if unpublished else self.code,
            )
        body = answer(request)
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


def test_the_listing_is_pinned_and_holds_the_seven_tables_of_the_page():
    canonical = json.dumps(
        DIRECTORY, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == DIRECTORY_SHA256
    assert list(DIRECTORY["tables"]) == [str(n) for n in range(1, 8)]
    assert [len(DIRECTORY["tables"][str(n)]["columns"]) for n in range(1, 8)] == [
        4,
        7,
        8,
        31,
        16,
        6,
        4,
    ]
    assert len(SUPPORTED_COLUMNS) == 76
    # The ratio and per-head tables have no "abroad" row; the money tables do.
    assert [len(PROVINCES[n]) for n in range(1, 8)] == [82, 82, 82, 82, 81, 81, 82]
    assert len(supported_finturk_selectors()) == sum(
        len(PROVINCES[table]) for table, _ in SUPPORTED_COLUMNS
    )


def test_a_province_is_named_by_plain_capitals_and_shown_as_it_is_written():
    assert province_token("İSTANBUL") == "ISTANBUL"
    assert province_token("AĞRI") == "AGRI"
    assert province_token("YURT DIŞI") == "YURT_DISI"
    assert place_name("İSTANBUL") == "İstanbul"
    assert place_name("ŞANLIURFA") == "Şanlıurfa"
    # No two provinces of a table share a token, or one identity would name two rows.
    for table, places in PROVINCES.items():
        assert len(places) == len(DIRECTORY["tables"][str(table)]["provinces"])


@pytest.mark.parametrize(
    ("chosen", "unit", "scale", "kind"),
    [
        (selector(3, 2), "TRY", Scale.THOUSAND, StockFlow.STOCK),
        (selector(5, 1), "percent", Scale.ONE, StockFlow.RATE),
        (selector(6, 1), "count", Scale.ONE, StockFlow.STOCK),
        (selector(6, 2), "ratio", Scale.ONE, StockFlow.RATE),
        (selector(6, 3), "TRY", Scale.ONE, StockFlow.STOCK),
    ],
)
def test_a_cell_is_a_quarter_end_position_in_its_tables_own_unit(chosen, unit, scale, kind):
    record = finturk_directory_catalog(chosen)
    assert (record.unit, record.scale, record.stock_flow) == (unit, scale, kind)
    assert record.frequency is Frequency.QUARTERLY
    # Measured: İstanbul housing credit does not restart in the first quarter, so it is a
    # position, and a position is reduced over time by its last value and never summed.
    assert record.cumulative is CumulativeKind.NONE
    assert record.aggregation.default is Aggregation.LAST and record.aggregation.sum is False
    assert record.provider == "BDDK" and record.series_id == chosen.internal_id()


def test_a_cell_is_titled_by_its_column_and_its_province():
    record = finturk_directory_catalog(HOUSING)
    assert record.title == "Konut Kredisi - İstanbul"
    assert record.labels[:2] == ("FinTürk", "Sektör") and record.labels[-1] == "İstanbul"
    titles = [finturk_directory_catalog(item).title for item in supported_finturk_selectors()]
    by_table: dict[tuple[int, str], int] = {}
    for item, title in zip(supported_finturk_selectors(), titles, strict=True):
        by_table[(item.table, title)] = by_table.get((item.table, title), 0) + 1
    assert set(by_table.values()) == {1}


@pytest.mark.parametrize(
    "changes",
    [
        {"table": 8},
        {"row": 9},
        {"geography": "ATLANTIS"},
        {"geography": None},
        {"geography": "YURT_DISI", "table": 5, "row": 1},
        {"bank_group": 10002},
        {"presentation_currency": "USD"},
        {"value_dimension": "TP"},
        {"bulletin_family": "monthly"},
    ],
)
def test_a_selector_outside_the_listing_is_refused_before_any_request(lake, changes):
    unlisted = HOUSING.model_copy(update=changes)
    with pytest.raises(UnlistedFinturkSelector):
        listed_finturk(unlisted)
    with pytest.raises(ValueError):
        FinturkRequest(selector=unlisted, quarter=LATEST)
    source = FinturkSource()
    with pytest.raises(ValueError):
        ingest_finturk(lake, unlisted, TODAY, retrieve=source)
    assert not source.asked


# --- the request ---------------------------------------------------------------------------------


def test_the_form_names_the_table_the_quarter_the_sector_and_every_province():
    body = FinturkRequest(selector=HOUSING, quarter=LATEST).form_body().decode("ascii")
    assert body == ("tabloNo=3&donem=2026-6&tarafList%5B0%5D=10001&sehirList%5B0%5D=HEPS%C4%B0")


def test_every_cell_of_a_table_asks_the_source_for_the_same_bytes():
    istanbul = FinturkRequest(selector=HOUSING, quarter=LATEST)
    ankara = FinturkRequest(selector=selector(3, 2, "ANKARA"), quarter=LATEST)
    vehicles = FinturkRequest(selector=selector(3, 1), quarter=LATEST)
    deposits = FinturkRequest(selector=selector(2, 1), quarter=LATEST)
    earlier = FinturkRequest(selector=HOUSING, quarter=Quarter(year=2026, month=3))
    assert istanbul.wire_fingerprint() == ankara.wire_fingerprint() == vehicles.wire_fingerprint()
    assert len({istanbul.fingerprint(), ankara.fingerprint(), vehicles.fingerprint()}) == 3
    assert istanbul.wire_fingerprint() != deposits.wire_fingerprint()
    assert istanbul.wire_fingerprint() != earlier.wire_fingerprint()


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 9, 21), (2026, 6)),
        (date(2026, 9, 30), (2026, 9)),
        (date(2026, 6, 29), (2026, 3)),
        (date(2026, 3, 31), (2026, 3)),
        (date(2026, 1, 15), (2025, 12)),
        (date(2026, 12, 31), (2026, 12)),
    ],
)
def test_the_newest_quarter_is_the_last_one_that_has_ended(today, expected):
    found = newest_quarter(today)
    assert (found.year, found.month) == expected and found.end() <= today


def test_quarters_run_from_the_first_of_the_prepared_period_and_a_month_is_no_quarter():
    found = quarters_until(LATEST)
    assert len(found) == QUARTERS
    assert (found[0].key(), found[-1].key()) == ("2021-3", "2026-6")
    assert [q.key() for q in found[3:5]] == ["2021-12", "2022-3"]
    with pytest.raises(ValueError):
        Quarter(year=2026, month=5)


# --- the parser ----------------------------------------------------------------------------------


def request(chosen=HOUSING, quarter=LATEST):
    return FinturkRequest(selector=chosen, quarter=quarter)


def test_a_cell_is_read_from_its_own_row_and_column_for_the_whole_quarter():
    found = parse_finturk(encoded(answer(request())), request())
    assert (found.period_start, found.period_end) == (date(2026, 4, 1), date(2026, 6, 30))
    assert found.value == value_of(3, 2, "İSTANBUL", LATEST)
    other = request(selector(3, 8, "AGRI"))
    assert parse_finturk(encoded(answer(other)), other).value == value_of(3, 8, "AĞRI", LATEST)


def spoiled(**changes):
    def rows(edit):
        body = answer(request())
        edit(body["Json"]["data"]["rows"])
        return body

    cases = {
        "unsuccessful": {**answer(request()), "success": False},
        "another table": answer(request(selector(2, 1))),
        "renamed column": answer(
            request(),
            colNames=[
                *DIRECTORY["tables"]["3"]["identity"],
                "Konut",
                *DIRECTORY["tables"]["3"]["columns"][1:],
            ],
        ),
        "reordered columns": answer(
            request(),
            colNames=[
                *DIRECTORY["tables"]["3"]["identity"],
                *reversed(DIRECTORY["tables"]["3"]["columns"]),
            ],
        ),
        "another quarter": answer(request(quarter=Quarter(year=2026, month=3))),
        "unknown province": rows(lambda r: r[0]["cell"].__setitem__(3, "ATLANTİS")),
        "province twice": rows(lambda r: r.append(r[0])),
        "another side": rows(lambda r: r[0]["cell"].__setitem__(0, 10002)),
        "another group": rows(lambda r: r[0]["cell"].__setitem__(4, "KAMU")),
        "short row": rows(lambda r: r[0]["cell"].pop()),
        "text value": rows(
            lambda r: [row["cell"].__setitem__(6, "1.234") for row in r if row["cell"][3]]
        ),
        "selected province missing": rows(
            lambda r: r.remove(next(row for row in r if row["cell"][3] == "İSTANBUL"))
        ),
        "no rows": rows(lambda r: r.clear()),
        "not an object": [1, 2],
    }
    return [pytest.param(body, id=name) for name, body in cases.items()]


@pytest.mark.parametrize("body", spoiled())
def test_a_table_that_is_not_the_listed_one_is_refused_whole(body):
    with pytest.raises(FinturkLoadError) as refusal:
        parse_finturk(encoded(body), request())
    assert refusal.value.code is FinturkLoadCode.RESPONSE_INVALID


def test_malformed_bytes_and_a_missing_value():
    for payload in (b"<html>500</html>", b'{"success": true, "success": true}', b"NaN"):
        with pytest.raises(FinturkLoadError):
            parse_finturk(payload, request())
    body = answer(request())
    next(r for r in body["Json"]["data"]["rows"] if r["cell"][3] == "İSTANBUL")["cell"][6] = None
    assert parse_finturk(encoded(body), request()).value is None


# --- the loader ----------------------------------------------------------------------------------


def stored(lake, series_id):
    return lake.connection.execute(
        "SELECT period_start, period_end, value FROM silver_observations WHERE series_id = ?"
        " ORDER BY period_end",
        [series_id],
    ).fetchall()


def test_a_series_is_every_quarter_from_the_first_each_from_its_own_answer(lake):
    source = FinturkSource()
    loaded = ingest_finturk(lake, HOUSING, TODAY, retrieve=source)
    assert (loaded.quarters, loaded.missing_values, loaded.already_present) == (QUARTERS, 0, False)
    assert (loaded.first_quarter, loaded.last_quarter) == (date(2021, 3, 31), date(2026, 6, 30))
    assert source.asked == [(3, q.key()) for q in quarters_until(LATEST)]
    rows = stored(lake, HOUSING.internal_id())
    assert rows[0] == (
        date(2021, 1, 1),
        date(2021, 3, 31),
        value_of(3, 2, "İSTANBUL", Quarter(year=2021, month=3)),
    )
    semantics = lake.semantics_of(HOUSING.internal_id())
    assert (semantics.unit, semantics.scale, semantics.frequency) == (
        "TRY",
        Scale.THOUSAND,
        Frequency.QUARTERLY,
    )
    again = ingest_finturk(lake, HOUSING, TODAY, retrieve=FinturkSource())
    assert again.already_present and again.manifest_id == loaded.manifest_id


def test_a_quarter_that_has_ended_but_is_not_published_is_left_out(lake):
    # On 2026-10-05 the third quarter has ended; the source still answers it with an error.
    source = FinturkSource()
    loaded = ingest_finturk(lake, HOUSING, date(2026, 10, 5), retrieve=source)
    assert source.asked[-1] == (3, "2026-9") and len(source.asked) == QUARTERS + 1
    assert loaded.quarters == QUARTERS and loaded.last_quarter == date(2026, 6, 30)


@pytest.mark.parametrize(
    ("source", "today"),
    [
        (FinturkSource(failure=5), TODAY),  # a quarter in the middle fails
        (FinturkSource(failure=QUARTERS, code=FetchCode.TIMEOUT), TODAY),  # newest, not a 500
        (FinturkSource(latest=Quarter(year=2020, month=12)), date(2021, 4, 2)),  # nothing at all
    ],
)
def test_any_other_failed_quarter_refuses_the_series_and_stores_nothing(lake, source, today):
    with pytest.raises(FinturkLoadError) as refusal:
        ingest_finturk(lake, HOUSING, today, retrieve=source)
    assert refusal.value.code is FinturkLoadCode.RETRIEVAL_FAILED
    assert not stored(lake, HOUSING.internal_id())


def test_a_refused_table_publishes_nothing_and_another_batch_is_a_conflict(lake):
    def renamed(request, body):
        if request.quarter.key() == "2024-6":
            body["Json"]["colNames"][6] = "Konut"
        return body

    with pytest.raises(FinturkLoadError) as refusal:
        ingest_finturk(lake, HOUSING, TODAY, retrieve=FinturkSource(spoil=renamed))
    assert refusal.value.code is FinturkLoadCode.RESPONSE_INVALID
    assert not stored(lake, HOUSING.internal_id())
    ingest_finturk(lake, HOUSING, TODAY, retrieve=FinturkSource())
    with pytest.raises(FinturkLoadError) as conflict:
        ingest_finturk(
            lake,
            HOUSING,
            date(2026, 12, 31),
            retrieve=FinturkSource(latest=Quarter(year=2026, month=9)),
        )
    assert conflict.value.code is FinturkLoadCode.VERSION_CONFLICT


# --- the route and the catalogue -----------------------------------------------------------------


def catalogue():
    reviewed = load_reviewed_snapshot(CATALOG.read_bytes())
    return reviewed, effective_snapshot(reviewed, [], [], source_directory())


def test_every_cell_has_a_route_and_a_table_costs_one_request_a_quarter(tmp_path):
    assert all(has_reviewed_route(item.internal_id()) for item in supported_finturk_selectors())
    store = AcquisitionStore(tmp_path / "kept")
    source = FinturkSource()
    sources = OfficialSources(bddk_finturk=source, store=store, pause=lambda _: None)
    seen = []
    with open_lakehouse(tmp_path / "one") as lake:
        acquirer = TurnAcquirer(lake, TODAY, sources=sources, observe=seen.append)
        first = acquirer.acquire(HOUSING.internal_id())
        ankara = acquirer.acquire(selector(3, 2, "ANKARA").internal_id())
        vehicles = acquirer.acquire(selector(3, 1, "IZMIR").internal_id())
        deposits = acquirer.acquire(selector(2, 1).internal_id())
    assert first.code is AcquisitionCode.ACQUIRED and first.observations == QUARTERS
    assert (first.window_start, first.window_end) == (date(2021, 1, 1), date(2026, 6, 30))
    assert not first.from_store and seen[0] == first
    # Another province and another column of the same table are read from the kept answers.
    assert ankara.code is AcquisitionCode.ACQUIRED and ankara.from_store
    assert vehicles.code is AcquisitionCode.ACQUIRED and vehicles.from_store
    assert not deposits.from_store and len(source.asked) == 2 * QUARTERS
    with open_lakehouse(tmp_path / "two") as lake:
        again = TurnAcquirer(lake, TODAY, sources=sources).acquire(HOUSING.internal_id())
    assert again.code is AcquisitionCode.ACQUIRED and again.from_store
    assert len(source.asked) == 2 * QUARTERS


def test_a_refused_table_is_a_refusal_and_an_unreachable_source_a_retrieval_failure(lake):
    def another(_request, body):
        body["Json"]["colNames"] = body["Json"]["colNames"][:-1]
        return body

    refused = TurnAcquirer(
        lake, TODAY, sources=OfficialSources(bddk_finturk=FinturkSource(spoil=another))
    ).acquire(HOUSING.internal_id())
    assert (refused.code, refused.detail) == (AcquisitionCode.REFUSED, "RESPONSE_INVALID")
    down = TurnAcquirer(
        lake,
        TODAY,
        # The source answers nothing at all, however often it is asked.
        sources=OfficialSources(
            bddk_finturk=FinturkSource(latest=Quarter(year=2020, month=12)), pause=lambda _: None
        ),
    ).acquire(HOUSING.internal_id())
    assert down.code is AcquisitionCode.RETRIEVAL_FAILED and not down.stored


def test_the_inspector_finds_a_fetched_cell_consistent_with_its_entry(lake):
    _, effective = catalogue()
    inspector = AcquiringInspector(
        PreparedSeriesInspector(effective),
        TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk_finturk=FinturkSource())),
    )
    for chosen in (HOUSING, selector(5, 3, "SANLIURFA"), selector(6, 1, "ANKARA")):
        assert inspector.inspect(lake.connection, chosen.internal_id()).status == "consistent"


def test_province_cells_are_a_listed_tier_of_the_catalogue_with_their_own_evidence():
    reviewed, effective = catalogue()
    cells = [
        item
        for item in effective.series
        if item.record.provider == "BDDK" and item.record.frequency is Frequency.QUARTERLY
    ]
    assert len(cells) == len(supported_finturk_selectors())
    assert all(is_listed_series(item) for item in cells)
    assert all(item.evidence_ids == (BDDK_FINTURK_EVIDENCE_ID,) for item in cells)
    assert all(item.geography for item in cells)
    assert BDDK_FINTURK_EVIDENCE_ID in {item.evidence_id for item in effective.evidence}
    ids = [item.record.series_id for item in effective.series]
    assert len(ids) == len(set(ids))
    assert ids[: len(reviewed.series)] == [item.record.series_id for item in reviewed.series]


def found(snapshot, query):
    output = search_catalog(snapshot, CatalogSearchArguments(query=query))
    return [item.series.record.title for item in output.candidates]


def test_a_named_province_is_found_and_unnamed_provinces_are_one_row():
    _, effective = catalogue()
    titles = found(effective, "İzmir'de takipteki alacaklar")
    assert titles[:2] == [
        "Takipteki Alacaklar Toplam Nakdi Kredi Oranı - İzmir",
        "Takipteki Alacaklar - İzmir",
    ]
    assert all(title.endswith(" - İzmir") for title in titles)
    both = found(effective, "İstanbul ve Ankara toplam mevduat")
    assert "Toplam Mevduat - İstanbul" in both and "Toplam Mevduat - Ankara" in both
    # A question that names no province never fills its ten results with one column in ten
    # arbitrary provinces: at most one province stands for each column.
    columns = [
        title.rsplit(" - ", 1)[0]
        for title in found(effective, "altın mevduatı tüzel kişi")
        if " - " in title and title.rsplit(" - ", 1)[1] in {"Adana", "Adıyaman", "Afyonkarahisar"}
    ]
    assert len(columns) == len(set(columns))
    # The national series a reviewed concept maps stay where they were.
    assert found(effective, "konut kredisi bakiyesi") == found(
        load_reviewed_snapshot(CATALOG.read_bytes()), "konut kredisi bakiyesi"
    )


# --- the worker protocol -------------------------------------------------------------------------


def test_the_post_uses_fixed_fields_the_bddk_host_and_no_credentials(transport):
    payload = encoded(answer(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json; charset=utf-8")])
    result = _fetch_worker.fetch_once(
        request().fetch_request(), FINTURK_LIMITS, lambda: None, finturk=request()
    )
    assert isinstance(result, FetchSuccess) and result.content == payload
    assert transport.resolutions == [("www.bddk.org.tr", 443)]
    sent = b"".join(transport.sockets[0].sent)
    assert sent.startswith(b"POST /BultenFinturk/tr/Home/VeriGetir HTTP/1.1\r\n")
    assert b"Content-Type: application/x-www-form-urlencoded\r\n" in sent
    assert sent.endswith(request().form_body())
    assert b"Authorization:" not in sent and b"Cookie:" not in sent


def test_the_worker_refuses_a_changed_address_budget_or_a_second_contract(transport):
    from pydantic import SecretStr
    from test_bddk_weekly import request as weekly_request

    altered = (
        request()
        .fetch_request()
        .model_copy(update={"url": SecretStr("https://www.bddk.org.tr/BultenFinturk/other")})
    )
    for fetch, limits, extra in (
        (altered, FINTURK_LIMITS, {}),
        (request().fetch_request(), FetchLimits(), {}),
        (request().fetch_request(), FINTURK_LIMITS, {"weekly": weekly_request()}),
    ):
        result = _fetch_worker.fetch_once(fetch, limits, lambda: None, finturk=request(), **extra)
        assert result.code == FetchCode.INVALID_REQUEST
    assert not transport.resolutions
    assert (
        _fetch_process.fetch_in_process(altered, FINTURK_LIMITS, finturk=request()).code
        == FetchCode.INVALID_REQUEST
    )


def test_the_parent_hands_the_worker_only_the_closed_contract(transport, monkeypatch):
    payload = encoded(answer(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])

    class InlineWorker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, payload, *, timeout):
            data = json.loads(payload)
            assert set(data["finturk"]) == {"selector", "quarter"}
            assert "body" not in data and "method" not in data
            result = _fetch_worker.fetch_once(
                FetchRequest.model_validate(data["request"]),
                FetchLimits.model_validate(data["limits"]),
                lambda: None,
                finturk=FinturkRequest.model_validate(data["finturk"]),
            )
            return b"CONNECTED\n" + output_for(result), None

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: InlineWorker())
    assert fetch_finturk(request()).content == payload


def test_the_worker_revalidates_the_descriptor_it_was_handed(transport, monkeypatch):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    data = request().fetch_request().model_dump(mode="json")
    data["url"] = request().fetch_request().url.get_secret_value()
    message = {
        "request": data,
        "limits": FINTURK_LIMITS.model_dump(mode="json"),
        "finturk": request().model_dump(mode="json"),
    }

    class Input:
        buffer = io.BytesIO(json.dumps(message).encode())

    class Output:
        buffer = io.BytesIO()

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    assert _fetch_worker.main() == 0
    assert Output.buffer.getvalue().startswith(b"CONNECTED\n")
    message["finturk"]["body"] = "untrusted"
    Input.buffer = io.BytesIO(json.dumps(message).encode())
    Output.buffer = io.BytesIO()
    assert _fetch_worker.main() == 1 and Output.buffer.getvalue() == b""
