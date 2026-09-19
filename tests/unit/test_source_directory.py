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
from kkb_agent.core import CumulativeKind, Scale, StockFlow
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
    supported_selectors,
    validate_reviewed_monthly_metadata,
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

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        table = DIRECTORY["tables"][str(request.selector.table)]
        month = request.period.month
        rows = [
            {
                "id": number,
                "cell": [
                    "Sektör",
                    int(number),
                    entry["label"],
                    "",
                    int(number) * 10 * month,
                    month,
                    int(number) * 10 * month + month,
                ],
            }
            for number, entry in table["rows"].items()
        ]
        body = {
            "success": True,
            "Json": {
                "caption": (
                    f"{table['title']} ({table['unit_text']}), "
                    f"Dönem:{request.period.year}/{request.period.month}"
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
    # A row that could not be measured, another layout and a caption without a unit: unsupported.
    assert (4, 7) not in SUPPORTED_ROWS
    assert not [key for key in SUPPORTED_ROWS if key[0] in (3, 5, 9, 15, 16)]


@pytest.mark.parametrize(
    "changes",
    [
        {"row": 7},  # listed, never measured
        {"table": 3},  # another column layout
        {"table": 15},  # no caption unit
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
    assert len(supported_selectors()) == (len(SUPPORTED_ROWS) + 0) * 3
    source = TableSource()
    store = AcquisitionStore(tmp_path / "acquired")
    acquirer = TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk=source, store=store))
    first = acquirer.acquire(PERSONAL.internal_id())
    assert first.code is AcquisitionCode.ACQUIRED and first.observations == 3
    assert len(source.requests) == 3
    # Another row and another component of the same table: the kept responses answer them.
    for other in (selector(4, 3, "TP"), selector(4, 9, "TOTAL")):
        again = acquirer.acquire(other.internal_id())
        assert again.code is AcquisitionCode.ACQUIRED and again.from_store
    assert len(source.requests) == 3
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
    assert all(item.evidence_ids == (BDDK_EVIDENCE_ID,) for item in listed)
    assert BDDK_EVIDENCE_ID in {item.evidence_id for item in effective.evidence}


def found(snapshot, query):
    return search_catalog(snapshot, CatalogSearchArguments(query=query))


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
    assert len({c.series.record.title for c in listed}) == len(listed)
    assert {c.series.record.labels[2] for c in listed} == {"TOTAL"}


def test_the_component_the_question_names_is_the_one_shown(catalogue):
    _, effective = catalogue
    output = found(effective, "TL cinsi ihtiyaç kredisi bakiyesi")
    personal = [
        c for c in output.candidates if c.series.record.title == "Tüketici Kredileri - İhtiyaç"
    ]
    assert [c.series.record.labels[2] for c in personal] == ["TP"]


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
    assert len({c.series.record.title for c in listed}) == len(listed)


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
    assert len(source.requests) == 3
    assert [cell.value for cell in answer.result.cells] == [41.0, 82.0, 123.0]
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
