"""Reviewed v2 development regressions, separate from M13-09 retrieval holdout."""

import hashlib
from pathlib import Path

import pytest

from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.ingest.bddk_monthly import BddkSelector, monthly_housing_catalog
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, catalog_record

ROOT = Path(__file__).parents[2]
ARTIFACT = ROOT / "docs/catalog/prepared_v2.json"
TOTAL = "BDDK:selector:v1:fa6e3c79bc8c9ead8680507965533a20366829cdf7aab8aa754224beb82b0f66"
TP = "BDDK:selector:v1:388f6263c2bd73dafb71579bf74f6756be7d74976a400b5d00798d506d521eb0"
YP = "BDDK:selector:v1:fb2bf2c7a47d0399251e6e46f55f09c7e7d8c85612f44096f66470744774d4d2"
CPI25 = "EVDS:TP.TUKFIY2025.GENEL"
CPI03 = "EVDS:TP.GENENDEKS.T1"


@pytest.fixture
def snapshot():
    return load_reviewed_snapshot(ARTIFACT.read_bytes())


def test_v2_preserves_historical_snapshot_and_evidence(snapshot):
    old = load_reviewed_snapshot((ROOT / "docs/catalog/demo_v1.json").read_bytes())
    assert old.content_sha256 == "230807e195663a59978c69448c8cb63acbd10130080b09a5f3d474a6b58da5f6"
    assert snapshot.snapshot_version == "m13-08-prepared-v2"
    assert snapshot.review_pr.endswith("/pull/152")
    assert len(snapshot.series) == 15
    assert {s.record.series_id for s in old.series} <= {s.record.series_id for s in snapshot.series}
    assert {TOTAL, TP, YP, CPI25, CPI03, "EVDS:TP.KTF12", "EVDS:TP.KFE.TR"} <= {
        s.record.series_id for s in snapshot.series
    }
    for evidence in snapshot.evidence:
        path = ROOT / evidence.path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence.file_sha256
        assert evidence.section in path.read_text(encoding="utf-8")
    for item in snapshot.series:
        assert item.record.sample_values == ()
        # Catalog scope is not a claim of downloaded periods or active status.
        assert item.record.coverage.start is item.record.coverage.end is None
        assert item.record.status in (CatalogStatus.UNKNOWN, CatalogStatus.ARCHIVED)


def test_prepared_metadata_agrees_with_reviewed_adapter_contracts(snapshot):
    records = {s.record.series_id: s.record for s in snapshot.series}
    for reviewed in REVIEWED_SERIES.values():
        if reviewed.series_id not in records:  # v2 is historical, not the current universe.
            continue
        assert records[reviewed.series_id] == catalog_record(reviewed)
    for component, sid in (("TP", TP), ("YP", YP), ("TOTAL", TOTAL)):
        selector = BddkSelector(
            bulletin_family="monthly",
            table=4,
            row=2,
            bank_group=10001,
            presentation_currency="TL",
            value_dimension=component,
        )
        record = records[sid]
        assert record == monthly_housing_catalog(selector)
        assert record.source_series_id.startswith("selector-v1:")
        assert record.unit == "TRY" and record.scale is Scale.MILLION
        assert record.stock_flow is StockFlow.STOCK
        assert record.cumulative is CumulativeKind.NONE
        assert record.frequency is Frequency.MONTHLY
    assert records[CPI25].base_year == 2025
    assert records[CPI03].base_year == 2003
    assert records["EVDS:TP.KFE.TR"].base_year == 2023
    for sid in ("EVDS:TP.KFE.TR10", "EVDS:TP.KFE.TR51", "EVDS:TP.KFE.TR31"):
        assert records[sid].base_year is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("kullanılan toplam konut kredisi", {TOTAL}),
        ("2021–2025 kullanılan toplam konut kredileri getir", {TOTAL}),
        ("toplam konut kredisi bakiyesi", {TOTAL}),
        ("TP konut kredisi bakiyesi", {TP}),
        ("yabancı para konut kredisi bakiyesi", {YP}),
        ("konut kredisi bakiyesi", {TP, YP, TOTAL}),
        ("TÜFE", {CPI25, CPI03}),
        ("TÜFE 2025=100", {CPI25}),
        ("2003 bazlı TÜFE", {CPI03}),
        ("konut kredisi faiz oranı", {"EVDS:TP.KTF12", "EVDS:TP.BKR.TRY.18"}),
        ("yeni konut kredisi faiz oranı", {"EVDS:TP.KTF12"}),
        ("mevcut konut kredisi faiz oranı", {"EVDS:TP.BKR.TRY.18"}),
        ("yeni konut finansmanı kâr payı", {"EVDS:TP.KBK.TRY.18"}),
        ("mevcut konut kredisi kâr payı", {"EVDS:TP.KKP.TRY.18"}),
        ("Türkiye konut fiyat endeksi", {"EVDS:TP.KFE.TR"}),
        ("İstanbul konut fiyat endeksi", {"EVDS:TP.KFE.TR10"}),
    ],
)
def test_precise_aliases_and_generic_ambiguity(snapshot, query, expected):
    result = search_catalog(snapshot, CatalogSearchArguments(query=query))
    assert {c.series.record.series_id for c in result.candidates} == expected
    assert result.status == "MATCH"
    assert result.clarification_required  # Even one candidate needs semantic inspection.
    assert result.analytical_evidence is result.observations_included is False


@pytest.mark.parametrize(
    "query",
    [
        "yeni konut kredisi kullandırımı",
        "konut kredisi akımı",
        "enflasyon oranı",
        "TÜFE artış oranı",
    ],
)
def test_missing_flow_or_rate_does_not_become_nearby_stock_or_index(snapshot, query):
    result = search_catalog(snapshot, CatalogSearchArguments(query=query))
    assert result.status == "UNRESOLVED"
    assert not result.candidates


def test_unqualified_housing_does_not_default_to_total_or_interest(snapshot):
    result = search_catalog(snapshot, CatalogSearchArguments(query="konut kredisi"))
    ids = {c.series.record.series_id for c in result.candidates}
    assert {TP, YP, TOTAL, "EVDS:TP.KTF12", "EVDS:TP.KBK.TRY.18"} <= ids
    assert result.status == "PARTIAL" and result.clarification_required


@pytest.mark.parametrize(
    "arguments",
    [
        CatalogSearchArguments(query="TÜFE", source="BDDK"),
        CatalogSearchArguments(query="konut kredisi bakiyesi", source="EVDS"),
        CatalogSearchArguments(query="konut kredisi bakiyesi", frequency=Frequency.WEEKLY),
        CatalogSearchArguments(query="yeni konut kredisi faiz oranı", frequency=Frequency.MONTHLY),
    ],
)
def test_filters_never_substitute_other_prepared_data(snapshot, arguments):
    result = search_catalog(snapshot, arguments)
    assert result.status == "FILTERED_OUT" and not result.candidates


def test_archives_still_require_explicit_opt_in(snapshot):
    default = search_catalog(snapshot, CatalogSearchArguments(query="konut arşiv serileri"))
    assert default.status == "FILTERED_OUT" and not default.candidates
    requested = search_catalog(
        snapshot, CatalogSearchArguments(query="konut arşiv serileri", include_archived=True)
    )
    assert {c.series.record.series_id for c in requested.candidates} == {
        "EVDS:TP.VK02",
        "EVDS:TP.TK02",
    }
