"""M1-03 environment checks for the DEC-112/DEC-114 engine.

These assert that the declared dependencies behave on the values this project
actually handles, so a broken environment fails here rather than inside M12.
"""

import io
import math
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from kkb_agent import xlsx_loader as loader
from kkb_agent.core import SourceRef
from kkb_agent.ingestion_policy import MIME_TYPES, FileKind

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/ingestion"
SINGLE = FIXTURES / "single_sheet.xlsx"
MULTI = FIXTURES / "multi_sheet.xlsx"
SOURCE = SourceRef(
    source_id="source:synthetic",
    source_type="upload",
    locator="opaque:fixture",
    retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
    content_hash="synthetic-hash",
)

# XLSX_CASES.md fixes these; a reader that disagrees is not usable for ingestion.
EXPECTED_HEADERS = ("as_of", "measure", "label")
EXPECTED_DATES = (date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31))
EXPECTED_MEASURES = (100.0, None, 125.5)
EXPECTED_LABELS = ("Örnek", "çığ", "C")


def read_calamine(path, sheet):
    return pd.read_excel(path, sheet_name=sheet, engine="calamine")


class TestCalamineBulkPath:
    """DEC-114: the path for spreadsheets this project retrieved itself."""

    def test_reads_the_documented_table_exactly(self):
        frame = read_calamine(SINGLE, "Observations")
        assert tuple(frame.columns) == EXPECTED_HEADERS
        assert len(frame) == 3
        assert tuple(frame["as_of"].dt.date) == EXPECTED_DATES
        assert tuple(frame["label"]) == EXPECTED_LABELS

    def test_missing_measure_stays_missing(self):
        # A blank that silently became 0.0 would corrupt every downstream sum.
        measures = read_calamine(SINGLE, "Observations")["measure"]
        assert math.isnan(measures[1])
        assert (measures[0], measures[2]) == (100.0, 125.5)

    def test_turkish_text_survives_the_reader(self):
        labels = read_calamine(SINGLE, "Observations")["label"]
        assert labels[0] == "Örnek" and labels[1] == "çığ"

    def test_sheet_order_is_preserved_and_not_guessed(self):
        assert pd.ExcelFile(MULTI, engine="calamine").sheet_names == [
            "Observations",
            "Categories",
        ]

    def test_agrees_with_the_untrusted_boundary_loader(self):
        # DEC-111 and DEC-114 read the same bytes by different paths. If they
        # ever disagree on a value, one of the two ingestion routes is wrong.
        result = loader.load_xlsx(
            io.BytesIO(SINGLE.read_bytes()),
            filename="single_sheet.xlsx",
            content_type=MIME_TYPES[FileKind.XLSX],
            source=SOURCE,
            selection="Observations",
        )
        assert result.status == "loaded" and result.table is not None
        frame = read_calamine(SINGLE, "Observations")

        assert result.table.headers == tuple(frame.columns)
        assert result.table.row_count == len(frame)
        for row, (_, series) in zip(result.table.rows, frame.iterrows(), strict=True):
            loaded_date, loaded_measure, loaded_label = row
            assert loaded_date.date() == series["as_of"].date()
            assert loaded_label == series["label"]
            if loaded_measure is None:
                assert math.isnan(series["measure"])
            else:
                assert loaded_measure == series["measure"]


class TestDuckDBLakehouse:
    """DEC-112: the storage round trip every silver and gold table depends on."""

    def test_parquet_round_trip_preserves_values(self, tmp_path):
        frame = pd.DataFrame(
            {
                "period": list(EXPECTED_DATES),
                "value": [100.0, None, 125.5],
                "label": list(EXPECTED_LABELS),
            }
        )
        parquet = tmp_path / "silver.parquet"
        with duckdb.connect() as write_conn:
            write_conn.register("frame", frame)
            write_conn.execute(f"COPY frame TO '{parquet}' (FORMAT PARQUET)")

        with duckdb.connect() as read_conn:
            rows = read_conn.execute(
                f"SELECT period, value, label FROM read_parquet('{parquet}') ORDER BY period"
            ).fetchall()

        assert [row[0] for row in rows] == list(EXPECTED_DATES)
        assert [row[2] for row in rows] == list(EXPECTED_LABELS)
        assert rows[0][1] == 100.0 and rows[2][1] == 125.5

    def test_null_survives_the_round_trip_as_null(self, tmp_path):
        # SUM over a NULL that became 0 is indistinguishable from a real total.
        parquet = tmp_path / "gaps.parquet"
        with duckdb.connect() as conn:
            conn.execute(
                "CREATE TABLE observations AS "
                "SELECT * FROM (VALUES (1, 100.0), (2, NULL), (3, 125.5)) t(period, value)"
            )
            conn.execute(f"COPY observations TO '{parquet}' (FORMAT PARQUET)")
            missing, total = conn.execute(
                f"SELECT count(*) - count(value), sum(value) FROM read_parquet('{parquet}')"
            ).fetchone()
        assert missing == 1
        assert total == pytest.approx(225.5)

    def test_decimals_are_exact_not_floated(self):
        # Money must not acquire a representation error on the way through.
        with duckdb.connect() as conn:
            total = conn.execute(
                "SELECT sum(v) FROM (VALUES (0.1::DECIMAL(18,2)), (0.2::DECIMAL(18,2))) t(v)"
            ).fetchone()[0]
        assert str(total) == "0.30"

    def test_reads_a_dataframe_produced_by_the_bulk_reader(self):
        # bronze XLSX -> pandas -> DuckDB is the actual M12 ingest path.
        observations = read_calamine(SINGLE, "Observations")
        with duckdb.connect() as conn:
            conn.register("observations", observations)
            count, present = conn.execute(
                "SELECT count(*), count(measure) FROM observations"
            ).fetchone()
        assert (count, present) == (3, 2)
