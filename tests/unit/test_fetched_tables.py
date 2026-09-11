"""M7-08: fetched CSV/XLSX meet the same admission checks and loaders as uploads.

A success record stands in for the transport, which has its own tests. The
loaders are the real ones, because running the same parser is the point.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pdf_builder import build, ruled_table

from kkb_agent.core import SourceRef
from kkb_agent.csv_loader import load_csv
from kkb_agent.ingest import fetched as module
from kkb_agent.ingest.fetched import (
    DOCUMENT_MEDIA_TYPES,
    TABLE_MEDIA_TYPES,
    fetched_source,
    load_fetched,
    source_id_for,
)
from kkb_agent.ingest.safe_fetch import FetchRequest, FetchSuccess
from kkb_agent.ingestion_policy import (
    MIME_TYPES,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    RejectionCode,
)
from kkb_agent.pdf_loader import load_pdf
from kkb_agent.xlsx_loader import load_xlsx

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/ingestion"
SINGLE = (FIXTURES / "single_sheet.xlsx").read_bytes()
MULTI = (FIXTURES / "multi_sheet.xlsx").read_bytes()
CSV, XLSX, PDF = (MIME_TYPES[kind] for kind in (FileKind.CSV, FileKind.XLSX, FileKind.PDF))
TABLE = b"as_of,measure\n2026-01-31,100\n2026-02-28,125\n"
DOCUMENT = build([ruled_table(50, 700, [["as_of", "measure"], ["2026-01-31", "100"]])])
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="web:fixture", source_type="web_url", locator="https://example.test/data"
)


def fetched(content: bytes, media_type: str) -> FetchSuccess:
    return FetchSuccess(
        source_ref="web:fixture", content=content, media_type=media_type, http_status=200
    )


def not_a_workbook() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("readme.txt", "synthetic")
    return output.getvalue()


class TestTheUploadPathIsTheOnlyPath:
    def test_the_accepted_types_are_exactly_the_loadable_ones(self):
        assert TABLE_MEDIA_TYPES == (CSV, XLSX)
        assert DOCUMENT_MEDIA_TYPES == (CSV, XLSX, PDF)

    def test_a_fetched_csv_loads_exactly_as_the_same_upload(self):
        downloaded = load_fetched(fetched(TABLE, CSV), source=SOURCE, delimiter=",")
        uploaded = load_csv(
            io.BytesIO(TABLE), filename="upload.csv", content_type=CSV, source=SOURCE, delimiter=","
        )

        assert downloaded.status == uploaded.status == "loaded"
        assert downloaded.table is not None and uploaded.table is not None
        assert downloaded.table.headers == uploaded.table.headers == ("as_of", "measure")
        assert downloaded.table.rows == uploaded.table.rows

    def test_a_fetched_workbook_loads_exactly_as_the_same_upload(self):
        downloaded = load_fetched(fetched(SINGLE, XLSX), source=SOURCE)
        uploaded = load_xlsx(
            io.BytesIO(SINGLE), filename="u.xlsx", content_type=XLSX, source=SOURCE
        )

        assert downloaded.status == uploaded.status == "loaded"
        assert downloaded.table is not None and uploaded.table is not None
        assert downloaded.table.selection == "Observations"
        assert downloaded.table.headers == uploaded.table.headers
        assert downloaded.table.rows == uploaded.table.rows

    def test_a_fetched_pdf_loads_exactly_as_the_same_upload(self):
        downloaded = load_fetched(fetched(DOCUMENT, PDF), source=SOURCE, delimiter=",", sheet="x")
        uploaded = load_pdf(io.BytesIO(DOCUMENT), filename="u.pdf", content_type=PDF, source=SOURCE)

        assert downloaded.status == uploaded.status == "loaded"
        assert downloaded.document is not None and uploaded.document is not None
        assert downloaded.document.pages == uploaded.document.pages
        assert downloaded.document.tables[0].rows == (("as_of", "measure"), ("2026-01-31", "100"))

    @pytest.mark.parametrize(
        ("media_type", "loader"), [(CSV, "load_csv"), (XLSX, "load_xlsx"), (PDF, "load_pdf")]
    )
    def test_the_media_type_picks_the_loader_and_names_the_file(
        self, monkeypatch, media_type, loader
    ):
        calls = []
        for name in ("load_csv", "load_xlsx", "load_pdf"):
            monkeypatch.setattr(
                module, name, lambda stream, name=name, **kwargs: calls.append((name, kwargs))
            )

        load_fetched(fetched(b"x", media_type), source=SOURCE)

        assert [name for name, _ in calls] == [loader]
        kwargs = calls[0][1]
        assert kwargs["filename"] == f"download.{loader.removeprefix('load_')}"
        assert kwargs["content_type"] == media_type

    @pytest.mark.parametrize(
        "media_type", ["text/html", "application/octet-stream", "text/plain", "image/png"]
    )
    def test_types_no_loader_reads_are_refused_before_parsing(self, monkeypatch, media_type):
        def forbidden(*args, **kwargs):
            pytest.fail("a loader ran for a media type it does not read")

        for name in ("load_csv", "load_xlsx", "load_pdf"):
            monkeypatch.setattr(module, name, forbidden)

        with pytest.raises(AdmissionError) as refused:
            load_fetched(fetched(TABLE, media_type), source=SOURCE, delimiter=",")
        assert refused.value.code is RejectionCode.UNSUPPORTED_FORMAT


class TestTheServersLabelIsCheckedAgainstTheBytes:
    @pytest.mark.parametrize(
        ("content", "media_type", "code"),
        [
            (b"<html><body>not a table</body></html>", CSV, "FORMAT_MISMATCH"),
            (b"%PDF-1.7\nsynthetic", CSV, "FORMAT_MISMATCH"),
            (TABLE, XLSX, "FORMAT_MISMATCH"),
            (not_a_workbook(), XLSX, "FORMAT_MISMATCH"),
            (SINGLE, CSV, "UNSUPPORTED_ENCODING"),
            (b"", CSV, "EMPTY_INPUT"),
            (TABLE, PDF, "FORMAT_MISMATCH"),
            (b"<html>%PDF-1.7</html>" + b" " * 1024, PDF, "MALFORMED_DOCUMENT"),
            (DOCUMENT, CSV, "UNSUPPORTED_ENCODING"),
        ],
    )
    def test_bytes_that_contradict_the_declared_type_are_rejected(self, content, media_type, code):
        result = load_fetched(fetched(content, media_type), source=SOURCE, delimiter=",")

        assert (result.status, result.code) == ("rejected", code)
        assert getattr(result, "table", None) is None
        assert getattr(result, "document", None) is None

    def test_upload_budgets_bound_fetched_bytes_exactly(self):
        at_limit = AdmissionLimits(max_bytes=len(TABLE))
        one_under = AdmissionLimits(max_bytes=len(TABLE) - 1)

        loaded = load_fetched(fetched(TABLE, CSV), source=SOURCE, delimiter=",", limits=at_limit)
        refused = load_fetched(fetched(TABLE, CSV), source=SOURCE, delimiter=",", limits=one_under)

        assert loaded.status == "loaded"
        assert (refused.status, refused.code) == ("rejected", "LIMIT_EXCEEDED")


class TestDeclarationsBelongToTheirFormat:
    def test_a_csv_without_a_separator_needs_one_even_when_a_sheet_is_named(self):
        result = load_fetched(fetched(TABLE, CSV), source=SOURCE, sheet="Observations")

        assert (result.status, result.code) == ("needs_input", "PARSING_DECLARATION_REQUIRED")

    def test_a_workbook_with_several_sheets_needs_one_named(self):
        result = load_fetched(fetched(MULTI, XLSX), source=SOURCE, delimiter=",")

        assert (result.status, result.code) == ("needs_input", "SELECTION_REQUIRED")
        assert result.sheets == ("Observations", "Categories")

    def test_a_named_sheet_loads_and_a_separator_is_not_consulted(self):
        result = load_fetched(
            fetched(MULTI, XLSX), source=SOURCE, delimiter=";", sheet="Categories"
        )

        assert result.status == "loaded"
        assert result.table is not None
        assert result.table.headers == ("code", "description")


class TestProvenance:
    URL = "https://Data.Example.test/files/rates.csv?token=synthetic-secret#row=3"

    def test_the_locator_drops_query_and_fragment_but_keeps_the_path(self):
        source = fetched_source(self.URL, TABLE, retrieved_at=NOW)

        assert source.locator == "https://data.example.test/files/rates.csv"
        assert source.source_type == "web_url"
        assert source.retrieved_at == NOW
        assert source.content_hash == "sha256:" + hashlib.sha256(TABLE).hexdigest()
        assert "synthetic-secret" not in source.model_dump_json()
        assert "row=3" not in source.model_dump_json()

    @pytest.mark.parametrize(
        ("url", "locator"),
        [
            ("https://example.test", "https://example.test/"),
            ("https://example.test./a.xlsx", "https://example.test/a.xlsx"),
            ("https://[2606:4700:4700::1111]/x.csv", "https://[2606:4700:4700::1111]/x.csv"),
        ],
    )
    def test_the_locator_uses_the_boundarys_canonical_host(self, url, locator):
        assert fetched_source(url, TABLE, retrieved_at=NOW).locator == locator

    def test_the_source_id_is_opaque_and_stable_per_address(self):
        first = source_id_for(self.URL)

        assert first == source_id_for(self.URL)
        assert first != source_id_for(self.URL.replace("synthetic-secret", "other"))
        assert "example" not in first and "rates" not in first
        # It must be usable as the fetch boundary's own source reference.
        FetchRequest(source_ref=first, url=self.URL, accepted_media_types=(CSV,))

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/a.csv",
            "http://169.254.169.254/latest/meta-data/",
            "https://user:synthetic-secret@example.test/a.csv",
            "ftp://example.test/a.csv",
        ],
    )
    def test_no_provenance_for_an_address_the_boundary_refuses(self, url):
        with pytest.raises(ValueError, match="refused address") as refused:
            fetched_source(url, TABLE, retrieved_at=NOW)
        assert "synthetic-secret" not in str(refused.value)
        assert "169.254" not in str(refused.value)


@pytest.mark.parametrize(
    "locator",
    [
        "https://example.test/",
        "https://example.test/wrong.xlsx",
        "https://example.test/../unsafe.csv?filename=../x",
    ],
)
def test_synthetic_distance_fare_csv_uses_controlled_metadata(locator):
    # Synthetic shape only: not captured public bytes and no claim about the live failure.
    content = b"Distance (miles),Fare ($)\n4.5,18.00\n"
    source = SOURCE.model_copy(update={"locator": locator})
    downloaded = load_fetched(fetched(content, CSV), source=source, delimiter=",")
    uploaded = load_csv(
        io.BytesIO(content), filename="upload.csv", content_type=CSV, source=source, delimiter=","
    )
    assert downloaded.status == uploaded.status == "loaded"
    assert downloaded.table.headers == ("Distance (miles)", "Fare ($)")
    assert downloaded.table.rows == uploaded.table.rows == (("4.5", "18.00"),)


def test_strict_csv_parser_rejection_is_not_an_admission_failure():
    from kkb_agent.ingestion_policy import admit_upload

    content = b'Distance (miles), "Fare ($)"\n4.5,18.00\n'
    assert (
        admit_upload(io.BytesIO(content), filename="download.csv", content_type=CSV).kind
        == FileKind.CSV
    )
    loaded = load_fetched(fetched(content, CSV), source=SOURCE, delimiter=",")
    assert loaded.status == "rejected"
    assert loaded.code == "MALFORMED_TABLE"
