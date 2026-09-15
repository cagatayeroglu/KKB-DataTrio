"""Expanded scope keeps native meaning and the existing guarded ingestion boundary."""

from datetime import date

import pytest
from test_evds_load import FakeSource

from kkb_agent.core import Aggregation, Frequency, StockFlow, WeeklyAnchor
from kkb_agent.ingest.evds_load import ingest_series, materialized_series
from kkb_agent.ingest.evds_request import EvdsRequest, EvdsWindow
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, catalog_record, reviewed_series
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.tools.change_detection import read_series

RATES = {
    "TP.KTF10",
    "TP.KTF101",
    "TP.KTF11",
    "TP.KTF17",
    "TP.KTF17.EUR",
    "TP.KTF17.USD",
    "TP.KTF18",
    "TP.KTFTUK",
    "TP.KTFTUK01",
}
CPI = {f"TP.TUKFIY2025.{i:02d}" for i in range(1, 14)}
ORIGINAL = {"TP.KTF12", "TP.TUKFIY2025.GENEL", "TP.GENENDEKS.T1", "TP.KFE.TR"}


def test_closed_expansion_is_exact_and_distinguishes_denominations_and_scope():
    assert set(REVIEWED_SERIES) == ORIGINAL | RATES | CPI
    for code in RATES:
        record = catalog_record(reviewed_series(code))
        assert (record.frequency, record.weekly_anchor, record.stock_flow) == (
            Frequency.WEEKLY,
            WeeklyAnchor.FRIDAY,
            StockFlow.RATE,
        )
        assert record.unit == "percent" and record.base_year is None
        assert record.aggregation.default is Aggregation.AVERAGE
        assert record.aggregation.sum is False
    assert "ABD doları" in reviewed_series("TP.KTF17.USD").title
    assert "Euro" in reviewed_series("TP.KTF17.EUR").title
    assert "KMH Dahil" in reviewed_series("TP.KTF101").title
    assert "Hariç" in reviewed_series("TP.KTF18").title
    for code in CPI:
        record = catalog_record(reviewed_series(code))
        assert (record.unit, record.base_year, record.frequency, record.stock_flow) == (
            "index",
            2025,
            Frequency.MONTHLY,
            StockFlow.INDEX,
        )
        assert record.aggregation.sum is False
        assert record.coverage.start is record.coverage.end is None


@pytest.mark.parametrize("code", sorted(RATES | CPI))
def test_new_series_use_existing_parser_manifest_lineage_and_native_calendar(tmp_path, code):
    window = EvdsWindow(start=date(2021, 1, 1), end=date(2021, 2, 28))
    source = FakeSource()
    with open_lakehouse(tmp_path / "lake") as lake:
        loaded = ingest_series(lake, code, window, retrieve=source)
        repeat = ingest_series(lake, code, window, retrieve=source)
        assert repeat.already_present and repeat.manifest_id == loaded.manifest_id
        assert materialized_series(lake, code, window).manifest_id == loaded.manifest_id
        assert len(lake.lineage.sources_of(loaded.lineage_id)) == 1
        stored = read_series(lake.connection, loaded.series_id)
        assert len(stored.observations) == (9 if code in RATES else 2)
        assert stored.semantics.unit == ("percent" if code in RATES else "index")
        assert loaded.series_id in prepared_series_names(lake.connection)
        assert set(prepared_series_names(lake.connection)) == {loaded.series_id}
        assert all(req.code == code for req in source.requests)
        assert EvdsRequest(code=code, window=window).series.request_frequency == (
            3 if code in RATES else 5
        )


def test_missing_cpi_value_remains_missing_instead_of_becoming_zero(tmp_path):
    def missing(data):
        data["items"][0]["TP_TUKFIY2025_12"] = None

    with open_lakehouse(tmp_path / "lake") as lake:
        result = ingest_series(
            lake,
            "TP.TUKFIY2025.12",
            EvdsWindow(start=date(2021, 1, 1), end=date(2021, 2, 28)),
            retrieve=FakeSource(mutate=missing),
        )
        assert result.missing_values == 1
        assert read_series(lake.connection, result.series_id).observations[0].value is None
