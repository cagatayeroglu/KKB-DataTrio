"""Reviewed v3 discovery, scope distinctions and prepared-runtime composition."""

import hashlib
from pathlib import Path

import pytest
from test_evds_expansion import CPI, ORIGINAL, RATES
from test_evds_load import FakeSource, window

from kkb_agent.api.prepared import inspect_pool
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.core import Frequency
from kkb_agent.ingest.evds_load import ingest_series
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, catalog_record
from kkb_agent.ingest.prepared_series import reviewed_series_names
from kkb_agent.lakehouse import open_lakehouse

ROOT = Path(__file__).parents[2]


@pytest.fixture
def snapshot():
    return load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v3.json").read_bytes())


def test_expansion_preserves_old_snapshot_records_and_pins_reviewed_metadata(snapshot):
    old = load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v2.json").read_bytes())
    assert old.content_sha256 == "723567b3f25c0703ddd2fa9001c67c41fd4f83a6c46ef82f0d40e556e0104e31"
    assert len(snapshot.series) == 37 and len(snapshot.concepts) == 46
    assert set(REVIEWED_SERIES) == ORIGINAL | RATES | CPI
    items = {s.record.series_id: s for s in snapshot.series}
    assert all(items[s.record.series_id] == s for s in old.series)
    assert set(reviewed_series_names()) <= items.keys()
    for series in REVIEWED_SERIES.values():
        assert items[series.series_id].record == catalog_record(series)
    for evidence in snapshot.evidence:
        path = ROOT / evidence.path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence.file_sha256
        assert evidence.section in path.read_text(encoding="utf-8")
    assert all(not s.record.sample_values for s in snapshot.series)


@pytest.mark.parametrize(
    ("query", "codes"),
    [
        ("taşıt kredisi faiz oranı", {"TP.KTF11"}),
        ("ihtiyaç kredisi faiz oranı", {"TP.KTF10", "TP.KTF101"}),
        ("KMH dahil ihtiyaç kredisi faizi", {"TP.KTF101"}),
        ("dolar ticari kredi faiz oranı", {"TP.KTF17.USD"}),
        ("euro ticari kredi faiz oranı", {"TP.KTF17.EUR"}),
        ("ticari kredi faiz oranı", {"TP.KTF17", "TP.KTF17.EUR", "TP.KTF17.USD", "TP.KTF18"}),
        ("gıda fiyat endeksi", {"TP.TUKFIY2025.01"}),
        ("eğitim TÜFE", {"TP.TUKFIY2025.10"}),
        ("konut giderleri TÜFE", {"TP.TUKFIY2025.04"}),
        ("Türkiye konut fiyat endeksi", {"TP.KFE.TR"}),
        ("TÜFE", {"TP.TUKFIY2025.GENEL", "TP.GENENDEKS.T1"}),
    ],
)
def test_expanded_aliases_do_not_silently_collapse_scopes(snapshot, query, codes):
    found = search_catalog(snapshot, CatalogSearchArguments(query=query))
    assert {c.series.record.source_series_id for c in found.candidates} == codes
    assert found.clarification_required
    assert not found.analytical_evidence and not found.observation_fetch_authorized


def test_native_frequency_filter_is_not_a_resampling_request(snapshot):
    result = search_catalog(
        snapshot,
        CatalogSearchArguments(query="taşıt kredisi faiz oranı", frequency=Frequency.DAILY),
    )
    assert result.status == "FILTERED_OUT" and not result.candidates


def test_expanded_prepared_pool_is_inspected_with_matching_catalog(tmp_path, snapshot):
    root = tmp_path / "lake"
    with open_lakehouse(root) as lake:
        for code in ("TP.KTF11", "TP.TUKFIY2025.01"):
            ingest_series(lake, code, window(), retrieve=FakeSource())
        lake.export_silver()
    status = inspect_pool(root, snapshot)
    assert status.prepared_identities == 2 and status.catalog_identities == 37
    assert status.observation_rows == 32
    assert not status.live_model_checked
    old = load_reviewed_snapshot((ROOT / "docs/catalog/prepared_v2.json").read_bytes())
    with pytest.raises(ValueError):
        inspect_pool(root, old)  # Old catalog cannot authorize newly prepared identities.
