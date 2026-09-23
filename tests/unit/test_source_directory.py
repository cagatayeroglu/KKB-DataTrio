"""DEC-176: what the BDDK monthly bulletin lists itself is found, fetched and declared.

The reviewed catalogue names 37 series. A question about any other published measure ended
in "not found" although the adapter downloaded the very table that holds it (live M1,
2026-09-19: "İhtiyaç kredisi bakiyesi" — row 4 of the table whose row 2 is the housing
series). No network here: the source is a fake that answers with whole synthetic tables.
"""

import json
from datetime import date
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, proposal, seed_prepared

from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.catalog.directory import BDDK_EVIDENCE_ID, source_directory
from kkb_agent.catalog.hybrid import search_hybrid_catalog
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import is_listed_series, load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.ingest import bddk_monthly as monthly
from kkb_agent.ingest import bddk_monthly_load as load
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionCode,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
    has_reviewed_route,
)
from kkb_agent.ingest.bddk_monthly import (
    HOUSING_LABEL,
    SUPPORTED_ROWS,
    BddkSelector,
    MetadataMismatch,
    MonthlyHousingMetadata,
    MonthlyPeriod,
    UnreviewedSelector,
    monthly_directory_catalog,
    reviewed_monthly_catalog,
    row_key,
    supported_selectors,
    validate_reviewed_monthly_metadata,
    value_columns,
)
from kkb_agent.ingest.bddk_monthly_directory import DIRECTORY, DIRECTORY_SHA256
from kkb_agent.ingest.bddk_monthly_request import MonthlyRange, MonthlyRequest
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.knowledge.overlay import effective_snapshot
from kkb_agent.llm import scripted

TODAY = date(2021, 6, 30)  # the window is then 2021-01..2021-03


def selector(table=4, row=4, component="TOTAL"):
    return BddkSelector(
        bulletin_family="monthly",
        table=table,
        row=row,
        bank_group=10001,
        presentation_currency="TL",
        value_dimension=component,
    )


PERSONAL = selector()  # Tüketici Kredileri - İhtiyaç
NET_PROFIT = next(
    selector(2, int(row))
    for row, entry in DIRECTORY["tables"]["2"]["rows"].items()
    if entry["label"].startswith("DÖNEM NET KARI")
)


class TableSource:
    """Answers each monthly request with the whole listed table, as the bulletin does.

    A row's TP, YP and Toplam are `base * month`, `month` and their sum, so a position grows
    every month and a year-to-date total is exactly `base` a month.
    """

    def __init__(self, *, shift_from=None, absent=()):
        self.requests = []
        #: From this row number on, every row sits one number lower in January 2021, as
        #: when the bulletin had not yet inserted a row above them.
        self.shift_from = shift_from
        #: Labels the table did not have yet in January 2021.
        self.absent = tuple(absent)

    def __call__(self, request):
        self.requests.append(request)
        table = DIRECTORY["tables"][str(request.selector.table)]
        month = request.period.month
        width = len(table["headers"]) - 4
        rows = []
        for number, entry in table["rows"].items():
            shown = int(number)
            if month == 1 and entry["label"] in self.absent:
                continue
            if month == 1 and self.shift_from is not None and shown >= self.shift_from:
                shown -= 1
            base = int(number) * 10 * month
            # TP, YP, Toplam for the three-column layout; otherwise the last column is the
            # row's total and every column before it one band of it.
            values = [base, month, base + month] if width == 3 else [base + k for k in range(width)]
            rows.append({"id": str(shown), "cell": ["Sektör", shown, entry["label"], "", *values]})
        unit = f" ({table['unit_text']})" if table["unit_text"] else ""
        body = {
            "success": True,
            "Json": {
                # Measured: a caption with a unit names its period; one without is the title.
                "caption": (
                    f"{table['title']}{unit}, Dönem:{request.period.year}/{request.period.month}"
                    if unit
                    else table["title"]
                ),
                "colNames": table["headers"],
                "data": {"page": "1", "total": "1", "records": str(len(rows)), "rows": rows},
            },
        }
        return FetchSuccess(
            source_ref=request.fetch_request().source_ref,
            content=json.dumps(body, ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as opened:
        yield opened


def window():
    return MonthlyRange(
        start=MonthlyPeriod(year=2021, month=1), end=MonthlyPeriod(year=2021, month=3)
    )


# --- the listing and what it supports ------------------------------------------------------------


def test_the_listing_is_pinned_and_agrees_with_the_reviewed_housing_row():
    canonical = json.dumps(DIRECTORY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib

    assert hashlib.sha256(canonical.encode()).hexdigest() == DIRECTORY_SHA256
    assert DIRECTORY["tables"]["4"]["rows"]["2"]["label"] == HOUSING_LABEL
    assert len(DIRECTORY["tables"]) == 17
    # No observation value is stored: a row is its label and one measured word.
    assert all(
        set(entry) == {"label", "resets"}
        for table in DIRECTORY["tables"].values()
        for entry in table["rows"].values()
    )


def test_semantics_come_from_the_caption_and_the_measured_behaviour_not_from_a_list():
    personal = SUPPORTED_ROWS[4, 4]
    assert (personal.label, personal.unit, personal.scale) == (
        "Tüketici Kredileri - İhtiyaç",
        "TRY",
        Scale.MILLION,
    )
    assert (personal.stock_flow, personal.cumulative) == (StockFlow.STOCK, CumulativeKind.NONE)
    profit = SUPPORTED_ROWS[NET_PROFIT.table, NET_PROFIT.row]
    assert (profit.stock_flow, profit.cumulative) == (
        StockFlow.FLOW,
        CumulativeKind.YEARLY_RESET,
    )
    # Behaviour is per row: the balance sheet carries the period's profit, which resets
    # every January, so it is left out of a table of positions rather than called a stock.
    resetting = [
        int(row)
        for row, entry in DIRECTORY["tables"]["1"]["rows"].items()
        if entry["resets"] == "always"
    ]
    assert resetting and all((1, row) not in SUPPORTED_ROWS for row in resetting)
    # A row that could not be measured, and a table that says no unit anywhere: unsupported.
    assert (4, 7) not in SUPPORTED_ROWS
    assert not [key for key in SUPPORTED_ROWS if key[0] == 17]


@pytest.mark.parametrize(
    "changes",
    [
        {"row": 7},  # listed, never measured
        {"table": 17},  # no unit in its caption, its header or its rows
        {"table": 12, "row": 9, "value_dimension": "TP"},  # a total, and no TP column
        {"bank_group": 10002},
        {"presentation_currency": "USD"},
        {"bulletin_family": "weekly"},
    ],
)
def test_a_selector_outside_the_supported_listing_is_refused_before_any_request(lake, changes):
    source = TableSource()
    candidate = PERSONAL.model_copy(update=changes)
    with pytest.raises(UnreviewedSelector):
        reviewed_monthly_catalog(candidate)
    with pytest.raises(UnreviewedSelector):
        load.ingest_monthly(lake, candidate, window(), retrieve=source)
    assert source.requests == []


def test_a_listed_record_declares_what_the_listing_says_and_never_the_housing_record():
    record = monthly_directory_catalog(PERSONAL)
    housing = reviewed_monthly_catalog(selector(4, 2))
    assert record.series_id != housing.series_id and record.title != housing.title
    assert record.group.group_title == "Tüketici Kredileri" and record.provider == "BDDK"
    assert (record.unit, record.scale, record.stock_flow) == ("TRY", Scale.MILLION, StockFlow.STOCK)
    assert "bakiyesi" in record.description and "incelenmedi" in record.description
    assert record.source.content_hash == DIRECTORY_SHA256
    # The reviewed housing rows keep their separately reviewed record.
    assert housing.title == HOUSING_LABEL and "Reviewed" in housing.description
    with pytest.raises(UnreviewedSelector):
        monthly.monthly_housing_catalog(PERSONAL)


def metadata(**changes):
    base = {
        "success": True,
        "caption": "Tüketici Kredileri (milyon TL), Dönem:2021/1",
        "column_headers": ("", "", "", "BasitFont", "TP", "YP", "Toplam"),
        "row_number": 4,
        "row_label": "Tüketici Kredileri - İhtiyaç",
        "bank_group_label": "Sektör",
    }
    return MonthlyHousingMetadata.model_validate({**base, **changes})


def test_a_response_must_still_be_the_listed_table_unit_row_and_label():
    period = MonthlyPeriod(year=2021, month=1)
    validate_reviewed_monthly_metadata(PERSONAL, metadata(), requested_period=period)
    for changed in (
        {"row_label": "Tüketici Kredileri - Taşıt"},  # the bulletin renumbered its rows
        {"caption": "Tüketici Kredileri (bin TL), Dönem:2021/1"},  # another unit
        {"caption": "Tüketici Kredileri (milyon TL), Dönem:2021/2"},  # another month
        {"bank_group_label": "Mevduat"},
        {"success": False},
    ):
        with pytest.raises(MetadataMismatch):
            validate_reviewed_monthly_metadata(
                PERSONAL, metadata(**changed), requested_period=period
            )


# --- fetching -----------------------------------------------------------------------------------


def test_a_listed_position_and_a_listed_year_to_date_total_are_stored_as_declared(lake):
    source = TableSource()
    load.ingest_monthly(lake, PERSONAL, window(), retrieve=source)
    load.ingest_monthly(lake, NET_PROFIT, window(), retrieve=source)
    rows = lake.connection.execute(
        "SELECT series_id, unit, scale, frequency, observation, cumulative FROM silver_series "
        "ORDER BY series_id"
    ).fetchall()
    declared = {row[0]: row[1:] for row in rows}
    assert declared[PERSONAL.internal_id()] == ("TRY", "million", "monthly", "stock", "none")
    assert declared[NET_PROFIT.internal_id()] == (
        "TRY",
        "million",
        "monthly",
        "flow",
        "yearly_reset",
    )
    values = lake.connection.execute(
        "SELECT value FROM silver_observations WHERE series_id = ? ORDER BY period_end",
        [PERSONAL.internal_id()],
    ).fetchall()
    assert [row[0] for row in values] == [41.0, 82.0, 123.0]  # row 4: 40*m + m


def test_every_supported_selector_has_a_route_and_one_table_response_serves_its_rows(
    tmp_path, lake
):
    assert all(has_reviewed_route(item.internal_id()) for item in supported_selectors())
    # Every readable column of every supported row: its components, and the maturity
    # bands of the layouts that publish them (DEC-193).
    assert len(supported_selectors()) == sum(
        len(row.columns) + len(row.bands) for row in SUPPORTED_ROWS.values()
    )
    source = TableSource()
    store = AcquisitionStore(tmp_path / "acquired")
    acquirer = TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk=source, store=store))
    first = acquirer.acquire(PERSONAL.internal_id())
    # The window opens one month before the prepared period, so the first prepared month
    # has a predecessor and its own change exists (DEC-192): four months here, not three.
    assert first.code is AcquisitionCode.ACQUIRED and first.observations == 4
    assert len(source.requests) == 4
    # Another row and another component of the same table: the kept responses answer them.
    for other in (selector(4, 3, "TP"), selector(4, 9, "TOTAL")):
        again = acquirer.acquire(other.internal_id())
        assert again.code is AcquisitionCode.ACQUIRED and again.from_store
    assert len(source.requests) == 4
    # The request identity still names the row; only the kept bytes are shared.
    one = MonthlyRequest(selector=PERSONAL, period=MonthlyPeriod(year=2021, month=1))
    two = MonthlyRequest(selector=selector(4, 3, "TP"), period=MonthlyPeriod(year=2021, month=1))
    assert one.fingerprint() != two.fingerprint()
    assert one.wire_fingerprint() == two.wire_fingerprint()


# --- the catalogue tier -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalogue():
    reviewed = load_reviewed_snapshot(CATALOG.read_bytes())
    return reviewed, effective_snapshot(reviewed, [], [], source_directory())


def test_the_directory_is_a_second_tier_and_never_replaces_a_reviewed_entry(catalogue):
    reviewed, effective = catalogue
    assert effective_snapshot(reviewed, [], []) is reviewed  # off: nothing changes at all
    assert effective.content_sha256 != reviewed.content_sha256
    ids = [item.record.series_id for item in effective.series]
    assert len(ids) == len(set(ids)) == len(reviewed.series) + len(source_directory().series)
    assert ids[: len(reviewed.series)] == [item.record.series_id for item in reviewed.series]
    housing = selector(4, 2).internal_id()
    (kept,) = [item for item in effective.series if item.record.series_id == housing]
    assert not is_listed_series(kept) and "Reviewed" in kept.record.description
    listed = [item for item in effective.series if is_listed_series(item)]
    assert len(listed) == len(source_directory().series)
    bddk = [
        item
        for item in listed
        if item.record.provider == "BDDK" and item.record.frequency is Frequency.MONTHLY
    ]
    assert len(bddk) == len(supported_selectors()) - 3  # the housing trio stays reviewed
    assert all(item.evidence_ids == (BDDK_EVIDENCE_ID,) for item in bddk)
    assert BDDK_EVIDENCE_ID in {item.evidence_id for item in effective.evidence}


def found(snapshot, query):
    return search_catalog(snapshot, CatalogSearchArguments(query=query))


def row_of(candidate):
    """A listed row: its table and title. The weekly bulletin repeats some monthly titles."""
    record = candidate.series.record
    return record.group.group_id, record.title


def test_a_reviewed_concept_still_bounds_the_candidates_to_reviewed_series(catalogue):
    reviewed, effective = catalogue
    for query in (
        "konut kredisi bakiyesi",
        "konut kredisi faiz oranı",
        "TÜFE",
        "konut fiyat endeksi",
    ):
        before, after = found(reviewed, query), found(effective, query)
        assert [c.series.record.series_id for c in after.candidates] == [
            c.series.record.series_id for c in before.candidates
        ]
        assert (after.status, after.top_candidate) == (before.status, before.top_candidate)


@pytest.mark.parametrize(
    ("query", "title"),
    [
        ("bireysel kredi kartı bakiyesi", "Bireysel Kredi Kartları (10+11)"),
        ("takipteki ihtiyaç kredileri", "Takipteki İhtiyaç Kredileri"),
        ("dönem net karı", "DÖNEM NET KARI (ZARARI) (51-52)"),
        ("taşıt kredisi bakiyesi", "Tüketici Kredileri - Taşıt"),
    ],
)
def test_a_listed_measure_is_found_as_one_unconfirmed_candidate_per_row(catalogue, query, title):
    _, effective = catalogue
    output = found(effective, query)
    assert output.status == "PARTIAL" and output.top_candidate == "unconfirmed"
    titles = [c.series.record.title for c in output.candidates]
    assert title in titles[:3]
    listed = [c for c in output.candidates if is_listed_series(c.series)]
    # One candidate per listed row: the total, since the question names neither TL nor FX.
    assert len({row_of(c) for c in listed}) == len(listed)
    assert {c.series.record.labels[2] for c in listed} == {"TOTAL"}


def test_the_component_the_question_names_is_the_one_shown(catalogue):
    _, effective = catalogue
    output = found(effective, "TL cinsi ihtiyaç kredisi bakiyesi")
    personal = [
        c for c in output.candidates if c.series.record.title == "Tüketici Kredileri - İhtiyaç"
    ]
    # Once per bulletin and table that lists it, and each time the component that was named.
    assert personal and {c.series.record.labels[2] for c in personal} == {"TP"}
    assert len({row_of(c) for c in personal}) == len(personal)


def dense_for(snapshot, root):
    """An offline index over the whole effective catalogue; vectors carry no meaning here."""
    from kkb_agent.catalog.hybrid import CatalogDenseStage
    from kkb_agent.catalog.lance_index import LocalCatalogIndex, build_catalog_index
    from kkb_agent.catalog.vectors import (
        CatalogVectors,
        QueryVector,
        SeriesVector,
        VectorProfile,
        catalog_documents,
    )

    profile = VectorProfile(
        model="kkbhackathon2026/Qwen3-Embedding-8B",
        dimension=4096,
        input_policy_id="hybrid-fixture-no-model-v1",
        origin="offline_fixture",
    )
    vectors = CatalogVectors(
        snapshot_sha256=snapshot.content_sha256,
        profile=profile,
        vectors=tuple(
            SeriesVector(
                series_id=item.series_id,
                text_sha256=item.text_sha256,
                values=(1.0, index / 1000, *([0.0] * 4094)),
            )
            for index, item in enumerate(catalog_documents(snapshot))
        ),
    )
    build_catalog_index(root, snapshot, vectors)
    index = LocalCatalogIndex.open(root, snapshot, profile)
    return CatalogDenseStage(
        index, lambda text: QueryVector(profile=profile, values=(1.0, *([0.0] * 4095)))
    )


def test_hybrid_search_applies_the_same_rule(catalogue, tmp_path):
    _, effective = catalogue
    dense = dense_for(effective, tmp_path / "index")
    output = search_hybrid_catalog(
        effective, CatalogSearchArguments(query="bireysel kredi kartı bakiyesi"), dense
    )
    listed = [c for c in output.candidates if is_listed_series(c.series)]
    assert output.top_candidate == "unconfirmed"
    assert len({row_of(c) for c in listed}) == len(listed)


# --- a served turn ------------------------------------------------------------------------------


def test_a_served_question_on_a_listed_series_is_fetched_and_answered(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    source = TableSource()
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "ihtiyaç kredisi bakiyesi"},
                }
            ),
            proposal(
                {
                    "step_id": "fetch",
                    "tool": "lakehouse",
                    "arguments": {"series": [PERSONAL.internal_id()]},
                }
            ),
            "Tabloda ihtiyaç kredisi bakiyesinin aylık değerleri yer alıyor.",
        ),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(bddk=source),
        clock=lambda: TODAY,
        source_directory=source_directory(),
    )
    answer = runner(uuid4().hex, uuid4().hex, "İhtiyaç kredisi bakiyesini aylık getir.")
    assert answer.status.value == "accepted", answer
    # Four months: the window opens one month before the prepared period, so the first
    # prepared month has a predecessor and its own change exists (DEC-192).
    assert len(source.requests) == 4
    assert [cell.value for cell in answer.result.cells] == [492.0, 41.0, 82.0, 123.0]
    assert {cell.unit for cell in answer.result.cells} == {"TRY"}
    # Without the operator's switch the same identity is unknown and nothing is asked.
    off = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "fetch",
                    "tool": "lakehouse",
                    "arguments": {"series": [PERSONAL.internal_id()]},
                }
            ),
            proposal(clarification="missing_series"),
        ),
        root,
        tmp_path / "runtime-off",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(bddk=(unused := TableSource())),
        clock=lambda: TODAY,
    )
    refused = off(uuid4().hex, uuid4().hex, "İhtiyaç kredisi bakiyesini aylık getir.")
    assert refused.status.value == "abstained" and unused.requests == []


def test_the_inspector_checks_a_fetched_listed_series_against_its_entry(lake):
    _, effective = (
        load_reviewed_snapshot(CATALOG.read_bytes()),
        effective_snapshot(
            load_reviewed_snapshot(CATALOG.read_bytes()), [], [], source_directory()
        ),
    )
    inspector = AcquiringInspector(
        PreparedSeriesInspector(effective),
        TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk=TableSource())),
    )
    assert inspector.inspect(lake.connection, PERSONAL.internal_id()).status == "consistent"
    assert inspector.inspect(lake.connection, NET_PROFIT.internal_id()).status == "consistent"


# --- a source that stumbles ---------------------------------------------------------------------


class StumblingSource(TableSource):
    """Times out on chosen requests (by position), like the bulletin did once in sixty-six."""

    def __init__(self, fail_at=(), always=False):
        super().__init__()
        self.fail_at, self.always = set(fail_at), always

    def __call__(self, request):
        from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure

        position = len(self.requests) + 1
        if self.always or position in self.fail_at:
            self.requests.append(request)
            return FetchFailure(
                source_ref=request.fetch_request().source_ref, code=FetchCode.TIMEOUT
            )
        return super().__call__(request)


def test_one_transient_failure_among_the_months_is_asked_again_not_fatal(lake):
    """Live D1 (2026-09-19): one failed request of sixty-six failed the batch and the turn."""
    source, waits = StumblingSource(fail_at={2}), []
    acquirer = TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk=source, pause=waits.append))
    outcome = acquirer.acquire(PERSONAL.internal_id())
    assert outcome.code is AcquisitionCode.ACQUIRED and outcome.observations == 4
    assert len(source.requests) == 5 and waits == [0.5]


def test_a_source_that_stays_down_is_said_to_the_person(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    source = StumblingSource(always=True)
    read = {
        "step_id": "fetch",
        "tool": "lakehouse",
        "arguments": {"series": [PERSONAL.internal_id()]},
    }
    runner = PreparedRunner(
        scripted(
            proposal(
                {
                    "step_id": "d",
                    "tool": "catalog_search",
                    "arguments": {"query": "ihtiyaç kredisi bakiyesi"},
                }
            ),
            proposal(read),
            proposal(clarification="missing_series"),
        ),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        official=OfficialSources(bddk=source, pause=lambda _: None),
        clock=lambda: TODAY,
        source_directory=source_directory(),
    )
    answer = runner(uuid4().hex, uuid4().hex, "İhtiyaç kredisi bakiyesini aylık getir.")
    assert answer.status.value == "abstained" and answer.result is None
    assert len(source.requests) == 3  # three attempts at the first month, then the batch stops
    assert any("kaynak bu turda yanıt vermedi" in notice for notice in answer.notices)


# --- other layouts, and rows the bulletin renumbers (DEC-185) ------------------------------------

LOANS_TOTAL = selector(3, 20)  # Krediler: maturity bands closed by Toplam TP, Toplam YP, Toplam
CAPITAL_RATIO = selector(12, 9)  # a "(YÜZDE)" row of a table captioned in million TL
NPL_RATIO = selector(15, 1)  # Rasyolar: one "Rasyo" column, percent by its own label
ATMS = selector(16, 5)  # Diğer Bilgiler: one "Adet" column


def test_a_table_is_read_by_the_total_its_own_layout_has():
    assert value_columns(monthly.COLUMN_HEADERS) == {"TP": 4, "YP": 5, "TOTAL": 6}
    loans = SUPPORTED_ROWS[3, 20]
    assert [loans.headers[loans.columns[part]] for part in ("TP", "YP", "TOTAL")] == [
        "Toplam TP",
        "Toplam YP",
        "Toplam",
    ]
    sector = SUPPORTED_ROWS[5, 1]
    assert [sector.headers[index] for index in sector.columns.values()] == ["Toplam Nakdi Krediler"]
    assert set(SUPPORTED_ROWS[6, 1].columns) == {"TP", "YP", "TOTAL"}
    deposits = SUPPORTED_ROWS[9, 1]
    assert deposits.columns == {"TOTAL": len(deposits.headers) - 1}
    # Bands without a total this adapter knows, or a repeated header: nothing is read.
    assert value_columns(["", "", "", "BasitFont", "Kısa", "Uzun"]) == {}
    assert value_columns(["", "", "", "BasitFont", "Toplam", "Toplam"]) == {}
    assert len(supported_selectors()) > 900 and {key[0] for key in SUPPORTED_ROWS} == {
        *range(1, 17)
    }


def test_a_row_is_declared_by_its_own_label_before_its_tables_caption():
    ratio, equity = SUPPORTED_ROWS[12, 9], SUPPORTED_ROWS[12, 5]
    assert (ratio.unit, ratio.scale, ratio.stock_flow) == ("percent", Scale.ONE, StockFlow.RATE)
    assert (equity.unit, equity.scale, equity.stock_flow) == ("TRY", Scale.MILLION, StockFlow.STOCK)
    assert SUPPORTED_ROWS[15, 1].unit == "percent" and SUPPORTED_ROWS[16, 5].unit == "count"
    # A ratio built on a year-to-date amount falls every January; a row in thousand TL per
    # head says a unit of its own. Neither has a declaration here, so neither is read.
    assert (15, 8) not in SUPPORTED_ROWS and (15, 18) not in SUPPORTED_ROWS
    described = monthly_directory_catalog(CAPITAL_RATIO).description
    assert "Okunan sütun: Toplam." in described and "oran" in described
    assert "Okunan sütun" not in monthly_directory_catalog(PERSONAL).description


def test_a_row_is_known_by_its_label_without_arithmetic_or_footnote_marks():
    assert row_key("Menkul Değerler (2 den 24'e)") == row_key("Menkul  Değerler (2 den 26'ya)")
    assert row_key("Ortaklık Finansmanı*") == row_key("Ortaklık Finansmanı")
    assert row_key("Kredi Riskine Esas Tutar (11+12+13+29)*") == row_key(
        "Kredi Riskine Esas Tutar (11+12+13)*"
    )
    # A parenthesis that says what the row is stays part of its name.
    assert row_key("Sermaye Yeterliliği Standart Rasyosu ((5/7)*100) (YÜZDE)").endswith("(yüzde)")
    assert row_key("Tasarruf Mevduatı (DTH)") != row_key("Tasarruf Mevduatı")


def observed(lake, chosen):
    rows = lake.connection.execute(
        "SELECT value FROM silver_observations WHERE series_id = ? ORDER BY period_end",
        [chosen.internal_id()],
    ).fetchall()
    return [row[0] for row in rows]


def test_the_other_layouts_are_stored_as_declared(lake):
    source = TableSource()
    for chosen in (LOANS_TOTAL, CAPITAL_RATIO, NPL_RATIO, ATMS):
        load.ingest_monthly(lake, chosen, window(), retrieve=source)
    assert observed(lake, LOANS_TOTAL) == [208.0, 408.0, 608.0]  # 20*10*m, last of nine columns
    assert observed(lake, selector(3, 20, "TP")) == []  # another identity, not fetched here
    declared = {
        row[0]: row[1:]
        for row in lake.connection.execute(
            "SELECT series_id, unit, scale, observation, cumulative FROM silver_series"
        ).fetchall()
    }
    assert declared[CAPITAL_RATIO.internal_id()] == ("percent", "one", "rate", "none")
    assert declared[ATMS.internal_id()] == ("count", "one", "stock", "none")


def test_a_renumbered_row_is_found_by_its_label(lake):
    # Measured: Krediler gained two rows in 2022-01 and "Toplam Krediler" moved from 18 to
    # 20; Menkul Kıymetler and Sermaye Yeterliliği moved the same way. The number a row had
    # in the harvested month names the identity; the label finds the row.
    inserted = DIRECTORY["tables"]["3"]["rows"]["19"]["label"]  # not there yet in January
    source = TableSource(shift_from=20, absent=(inserted,))
    loaded = load.ingest_monthly(lake, LOANS_TOTAL, window(), retrieve=source)
    assert loaded.missing_values == 0
    assert observed(lake, LOANS_TOTAL) == [208.0, 408.0, 608.0]


def test_a_month_without_the_row_is_a_missing_value_never_another_rows_number(lake):
    gold_bond = selector(8, 21)  # "Altın Tahvili": the bulletin has had it since 2022-09
    source = TableSource(absent=(SUPPORTED_ROWS[8, 21].label,), shift_from=22)
    loaded = load.ingest_monthly(lake, gold_bond, window(), retrieve=source)
    assert loaded.missing_values == 1
    assert observed(lake, gold_bond) == [None, 422.0, 633.0]


def test_two_rows_of_the_asked_name_refuse_the_answer(lake):
    class Doubled(TableSource):
        def __call__(self, request):
            answer = super().__call__(request)
            body = json.loads(answer.content)
            rows = body["Json"]["data"]["rows"]
            twin = next(row for row in rows if row["cell"][1] == 20)
            rows.append({"id": "99", "cell": [*twin["cell"][:1], 99, *twin["cell"][2:]]})
            return answer.model_copy(update={"content": json.dumps(body).encode()})

    with pytest.raises(load.MonthlyLoadError) as refusal:
        load.ingest_monthly(lake, LOANS_TOTAL, window(), retrieve=Doubled())
    assert refusal.value.code is load.MonthlyLoadCode.RESPONSE_INVALID


def test_a_total_that_changed_its_name_is_refused_and_a_redrawn_band_is_not():
    period = MonthlyPeriod(year=2021, month=1)
    loans = SUPPORTED_ROWS[3, 20]
    base = {
        "success": True,
        "caption": "Krediler (milyon TL), Dönem:2021/1",
        "row_number": 18,  # where the row sat before the bulletin inserted two rows
        "row_label": "Toplam Krediler",
        "bank_group_label": "Sektör",
    }
    redrawn = ("", "", "", "BasitFont", "0-1 Yıl", "Toplam TP", "Toplam YP", "Toplam")
    validate_reviewed_monthly_metadata(
        LOANS_TOTAL,
        MonthlyHousingMetadata.model_validate({**base, "column_headers": redrawn}),
        requested_period=period,
    )
    renamed = (*loans.headers[:-1], "Genel Toplam")
    for changed in ({"column_headers": renamed}, {"row_label": "Toplam Krediler (Net)"}):
        with pytest.raises(MetadataMismatch):
            validate_reviewed_monthly_metadata(
                LOANS_TOTAL,
                MonthlyHousingMetadata.model_validate(
                    {**base, "column_headers": loans.headers, **changed}
                ),
                requested_period=period,
            )


def test_two_rows_of_one_number_do_not_stop_a_row_found_by_its_label(lake):
    # Measured: from 2021-11 to 2022-05 the capital table itself numbers two rows 28.
    class Misnumbered(TableSource):
        def __call__(self, request):
            answer = super().__call__(request)
            body = json.loads(answer.content)
            rows = body["Json"]["data"]["rows"]
            rows[-1]["cell"][1], rows[-1]["id"] = rows[-2]["cell"][1], rows[-2]["id"]
            return answer.model_copy(update={"content": json.dumps(body).encode()})

    loaded = load.ingest_monthly(lake, CAPITAL_RATIO, window(), retrieve=Misnumbered())
    assert loaded.months == 3 and loaded.missing_values == 0


def test_a_row_published_by_maturity_is_one_row_until_the_question_asks_about_maturity(
    catalogue,
):
    """Live 2026-09-22: the bulletin publishes maturity as columns, so a deposit row is
    seven entries with one title. A question that names no maturity is about the row."""
    from kkb_agent.catalog.search import one_per_listed_row

    _, effective = catalogue
    row = [
        item
        for item in effective.series
        if item.record.title.startswith("TP Mevduat / Katılım Fonları - Yurt İçi Yerleşik")
        and item.record.group is not None
        and item.record.group.group_id == "10"
    ]
    assert len(row) == 7  # the six maturity columns and the row's own total

    plain = one_per_listed_row(row, reviewed_series=lambda item: item, query="tp mevduat bakiyesi")
    assert [item.record.title for item in plain] == [row[0].record.title]

    asked = one_per_listed_row(
        row, reviewed_series=lambda item: item, query="tp mevduatın vade dağılımı"
    )
    assert len(asked) == 7
    # A band named by its own words is told apart from its row; the five the question did
    # not name stay inside it.
    named = one_per_listed_row(
        row, reviewed_series=lambda item: item, query="1-3 ay arası tp mevduat"
    )
    assert [item.record.title for item in named] == [
        row[0].record.title,
        row[0].record.title + " (1-3 Ay Arası)",
    ]


def test_a_maturity_column_never_outranks_its_own_row_for_a_question_about_the_row(catalogue):
    """Live 2026-09-22: three buckets of one liquidity row filled the top of a question
    that named no maturity at all."""
    from kkb_agent.catalog.ranking import intent_key

    _, effective = catalogue
    by_title = {item.record.title: item for item in effective.series}
    row = by_title["Kredi Kartı Ödemelerinden Borçlar"]
    band = by_title["Kredi Kartı Ödemelerinden Borçlar (Yedi Gün)"]
    question = "bireysel kredi kartı bakiyesi"
    assert intent_key(question, row) < intent_key(question, band)
    maturity = "yedi gün vadeli kredi kartı ödemelerinden borçlar"
    assert intent_key(maturity, band) <= intent_key(maturity, row)


DEPOSIT_ROW = "TP Mevduat / Katılım Fonları - Yurt İçi Yerleşik"
COMPONENT_ROW = "Yurt İçi Bankalarca İhraç Edilen Tahviller"


def test_a_row_the_source_names_in_a_currency_is_about_that_currency(catalogue):
    """Measured 2026-09-23: the deposit rows publish maturity as their columns, so the
    row's own total is their only cell. Reading that cell as `total` made the `TP` in a
    question a conflict, and conflicts outrank every score."""
    from kkb_agent.catalog.ranking import _candidate_intent

    _, effective = catalogue
    named = [item for item in effective.series if item.record.title == DEPOSIT_ROW]
    assert named
    assert {_candidate_intent(item).currency for item in named} == {"try"}
    assert {_candidate_intent(item).component for item in named} == {"total"}
    # A row the source names in no currency still reads as the total it is, and an
    # explicit TP or YP cell still decides its own currency.
    siblings = {
        _candidate_intent(item).component: _candidate_intent(item).currency
        for item in effective.series
        if item.record.title == COMPONENT_ROW
    }
    assert siblings == {"total": "total", "tp": "try", "yp": "foreign"}


def test_a_question_that_names_a_row_retrieves_that_row(catalogue):
    """Measured 2026-09-23: the row scored highest of every document in the catalogue
    and the intent order then dropped it out of the ten candidates altogether, leaving
    rows that match `mevduat` nowhere."""
    _, effective = catalogue
    candidates = found(effective, "TP mevduat yurt içi yerleşik").candidates
    assert candidates[0].series.record.title == DEPOSIT_ROW
    assert "mevduat" in candidates[0].matched_terms
