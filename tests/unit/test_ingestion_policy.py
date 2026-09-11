"""Synthetic admission inputs; no real source, table engine, or network calls."""

import io
import stat
import zipfile
from dataclasses import replace

import pytest

from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    MIME_TYPES,
    AdmissionError,
    AdmissionLimits,
    FileKind,
    RejectionCode,
    admit_upload,
    staged_upload,
)

CSV = b"when,value\n2026-01-01,10\n"


def archive_bytes(extra=(), *, compression=zipfile.ZIP_STORED):
    # Package envelope only: M1-02 never claims these are parsed workbook cells.
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=compression) as archive:
        for name in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"):
            archive.writestr(name, b"<synthetic/>")
        archive.writestr("xl/worksheets/sheet1.xml", b"<synthetic/>")
        for name, value in extra:
            archive.writestr(name, value)
    return content.getvalue()


def admit(content=CSV, *, filename="unfamiliar.csv", content_type="text/csv", **kwargs):
    return admit_upload(io.BytesIO(content), filename=filename, content_type=content_type, **kwargs)


@pytest.mark.parametrize(
    "filename",
    [
        "../x.csv",
        "/x.csv",
        "C:\\x.csv",
        "a/b.csv",
        "a\\b.csv",
        "a:x.csv",
        "x\x00.csv",
        "x\n.csv",
        "x\x7f.csv",
        " x.csv",
        "x.csv ",
        "",
        "ü" * 130 + ".csv",
    ],
)
def test_unsafe_filename_rejected_before_any_read(filename):
    class Unreadable:
        def read(self, size):
            pytest.fail("Invalid metadata must not cause a read")

    with pytest.raises(AdmissionError) as error:
        admit_upload(Unreadable(), filename=filename, content_type="text/csv")
    assert error.value.code == RejectionCode.INVALID_FILENAME
    assert str(error.value) == "INVALID_FILENAME"


@pytest.mark.parametrize("filename", ["x.xls", "x.xlsm", "x.html", "x.csv.exe", ".csv"])
def test_unsupported_extensions(filename):
    with pytest.raises(AdmissionError, match="^UNSUPPORTED_FORMAT$"):
        admit(filename=filename)


PDF = MIME_TYPES[FileKind.PDF]


@pytest.mark.parametrize("content", [b"%PDF-1.7\n", b"\n" * 1019 + b"%PDF-1.4"])
def test_pdf_admitted_on_its_header_within_the_first_kilobyte(content):
    result = admit(content, filename="report.pdf", content_type=PDF)

    assert result.kind is FileKind.PDF
    assert result.content == content


@pytest.mark.parametrize(
    "content",
    [CSV, b"PK\x03\x04synthetic", b" " * 1020 + b"%PDF-1.7", b"%PS-Adobe-3.0\n"],
)
def test_pdf_without_its_header_is_a_format_mismatch(content):
    with pytest.raises(AdmissionError, match="^FORMAT_MISMATCH$"):
        admit(content, filename="report.pdf", content_type=PDF)


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("report.pdf", "text/csv"), ("report.csv", PDF), ("report.pdf", PDF + "; charset=utf-8")],
)
def test_pdf_metadata_must_agree(filename, content_type):
    with pytest.raises(AdmissionError, match="^FORMAT_MISMATCH$"):
        admit(b"%PDF-1.7\n", filename=filename, content_type=content_type)


@pytest.mark.parametrize(
    "mime",
    [
        "",
        "text/html",
        "application/octet-stream",
        "text/plain",
        "text/csv; charset=latin-1",
        "text/csv; x=unknown",
    ],
)
def test_mismatched_or_ambiguous_mime_is_not_inferred(mime):
    with pytest.raises(AdmissionError, match="^FORMAT_MISMATCH$"):
        admit(content_type=mime)


def test_csv_metadata_normalization_preserves_bytes_and_unknown_values():
    data = b'\xef\xbb\xbfperiod,amount\n01/02/2026,"1,234"\n'
    result = admit(data, filename="yeni.CSV", content_type='TEXT/CSV; charset="UTF-8"')
    assert result.kind == FileKind.CSV
    assert result.content == data
    assert "1,234" not in repr(result)
    assert not hasattr(result, "semantics")  # Admission does not infer financial meaning.


@pytest.mark.parametrize(
    "content,code",
    [
        (b"", "EMPTY_INPUT"),
        (b" \n\t", "EMPTY_INPUT"),
        (b"\xef\xbb\xbf", "EMPTY_INPUT"),
        (b"a,b\n\x00,1", "FORMAT_MISMATCH"),
        (b"%PDF-1.7", "FORMAT_MISMATCH"),
        (b" <html>source</html>", "FORMAT_MISMATCH"),
        (b"\xff\xfea\x00", "UNSUPPORTED_ENCODING"),
    ],
)
def test_csv_content_admission(content, code):
    with pytest.raises(AdmissionError, match=f"^{code}$"):
        admit(content)


def test_exact_byte_limit_and_one_extra_byte_with_short_reads():
    limits = replace(DEFAULT_LIMITS, max_bytes=len(CSV))
    assert admit(limits=limits).content == CSV

    class ShortReads(io.BytesIO):
        def read(self, size):
            assert 0 < size <= 65_536
            return super().read(min(size, 3))

    source = ShortReads(CSV + b"x" + b"unused" * 100)
    with pytest.raises(AdmissionError, match="^LIMIT_EXCEEDED$"):
        admit_upload(source, filename="x.csv", content_type="text/csv", limits=limits)
    assert source.tell() == limits.max_bytes + 1


def test_read_error_does_not_expose_source_details():
    class BrokenStream:
        def read(self, size):
            raise OSError("sensitive-source-detail")

    with pytest.raises(AdmissionError, match="^READ_FAILED$") as error:
        admit_upload(BrokenStream(), filename="x.csv", content_type="text/csv")
    assert "sensitive-source-detail" not in repr(error.value)
    assert error.value.__suppress_context__


def test_rejection_matches_m1_01_without_fake_profile_or_semantics():
    result = AdmissionError(RejectionCode.LIMIT_EXCEEDED).profile_failure("source:synthetic-1")
    assert result == {
        "status": "rejected",
        "data_ref": None,
        "source_ref": "source:synthetic-1",
        "selection": None,
        "row_count": None,
        "columns": [],
        "unresolved_semantics": [],
        "diagnostics": [{"code": "LIMIT_EXCEEDED"}],
        "diagnostics_truncated": False,
    }


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_limit_configuration(value):
    with pytest.raises(ValueError, match="positive integers"):
        AdmissionLimits(max_bytes=value)


@pytest.mark.parametrize("rows,columns", [(4, 2), (2, 4), (3, 3)])
def test_dimension_limits_cover_rows_columns_and_total_cells(rows, columns):
    limits = AdmissionLimits(max_rows=3, max_columns=3, max_cells=6)
    limits.check_table_size(rows=3, columns=2)
    with pytest.raises(AdmissionError, match="^LIMIT_EXCEEDED$"):
        limits.check_table_size(rows=rows, columns=columns)


def test_invalid_dimensions_and_exact_field_profile_limits():
    limits = AdmissionLimits(max_field_chars=3, max_label_chars=2, max_profile_bytes=4)
    with pytest.raises(ValueError):
        limits.check_table_size(rows=-1, columns=1)
    limits.check_field("üçx")
    limits.check_field("id", label=True)
    limits.check_profile_size(b"1234")
    for call in (
        lambda: limits.check_field("four"),
        lambda: limits.check_field("ids", label=True),
        lambda: limits.check_profile_size(b"12345"),
    ):
        with pytest.raises(AdmissionError, match="^LIMIT_EXCEEDED$"):
            call()


def test_xlsx_envelope_accepted_without_decompression(monkeypatch):
    data = archive_bytes()
    monkeypatch.setattr(zipfile.ZipFile, "open", lambda *a, **k: pytest.fail("No extraction"))
    result = admit(data, filename="new.xlsx", content_type=MIME_TYPES[FileKind.XLSX])
    assert result.kind == FileKind.XLSX
    assert result.content == data


@pytest.mark.parametrize("content", [CSV, b"PK\x03\x04broken", b"not a workbook"])
def test_mislabeled_or_corrupt_xlsx(content):
    with pytest.raises(AdmissionError, match="^FORMAT_MISMATCH$"):
        admit(content, filename="x.xlsx", content_type=MIME_TYPES[FileKind.XLSX])


def test_plain_zip_is_not_xlsx():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("data.txt", "synthetic")
    with pytest.raises(AdmissionError, match="^FORMAT_MISMATCH$"):
        admit(data.getvalue(), filename="x.xlsx", content_type=MIME_TYPES[FileKind.XLSX])


def test_encrypted_archive_entry_rejected():
    data = bytearray(archive_bytes())
    central_header = data.index(b"PK\x01\x02")
    data[central_header + 8] |= 1  # Synthetic central-directory encryption flag.
    with pytest.raises(AdmissionError, match="^UNSAFE_ARCHIVE$"):
        admit(bytes(data), filename="x.xlsx", content_type=MIME_TYPES[FileKind.XLSX])


def test_unsupported_archive_compression_rejected():
    data = archive_bytes(compression=zipfile.ZIP_BZIP2)
    with pytest.raises(AdmissionError, match="^UNSAFE_ARCHIVE$"):
        admit(data, filename="x.xlsx", content_type=MIME_TYPES[FileKind.XLSX])


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "a\\b",
        "a/./b",
        "a//b",
        "xl/vbaProject.bin",
        "xl/externalLinks/link1.xml",
        "xl/embeddings/oleObject1.bin",
        "XL/WORKBOOK.XML",
    ],
)
def test_unsafe_archive_members(name):
    with pytest.raises(AdmissionError, match="^UNSAFE_ARCHIVE$"):
        admit(
            archive_bytes([(name, b"synthetic")]),
            filename="x.xlsx",
            content_type=MIME_TYPES[FileKind.XLSX],
        )


def test_symlink_archive_member():
    link = zipfile.ZipInfo("xl/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(AdmissionError, match="^UNSAFE_ARCHIVE$"):
        admit(
            archive_bytes([(link, b"../outside")]),
            filename="x.xlsx",
            content_type=MIME_TYPES[FileKind.XLSX],
        )


@pytest.mark.parametrize(
    "limit,value",
    [
        ("max_archive_entries", 3),
        ("max_expanded_bytes", 47),
        ("max_sheets", 1),
        ("max_compression_ratio", 1),
    ],
)
def test_archive_resource_limits(limit, value):
    extras = [("xl/worksheets/sheet2.xml", b"A" * 100)]
    data = archive_bytes(extras, compression=zipfile.ZIP_DEFLATED)
    with pytest.raises(AdmissionError, match="^LIMIT_EXCEEDED$"):
        admit(
            data,
            filename="x.xlsx",
            content_type=MIME_TYPES[FileKind.XLSX],
            limits=replace(DEFAULT_LIMITS, **{limit: value}),
        )


def test_archive_exact_entry_expansion_sheet_limits():
    data = archive_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        expanded = sum(entry.file_size for entry in archive.infolist())
    limits = replace(
        DEFAULT_LIMITS, max_archive_entries=4, max_expanded_bytes=expanded, max_sheets=1
    )
    assert admit(data, filename="x.xlsx", content_type=MIME_TYPES[FileKind.XLSX], limits=limits)


@pytest.mark.parametrize("raise_inside", [False, True])
def test_staging_uses_generated_private_paths_and_always_cleans_up(tmp_path, raise_inside):
    sentinel = tmp_path / "original.csv"
    sentinel.write_bytes(b"existing file")
    destination = None
    try:
        with staged_upload(
            io.BytesIO(CSV), filename="original.csv", content_type="text/csv", storage_root=tmp_path
        ) as destination:
            assert destination.name == "input.csv"
            assert destination.parent.parent == tmp_path.resolve()
            assert destination.read_bytes() == CSV
            assert stat.S_IMODE(destination.stat().st_mode) == 0o600
            assert stat.S_IMODE(destination.parent.stat().st_mode) == 0o700
            if raise_inside:
                raise RuntimeError("synthetic downstream failure")
    except RuntimeError:
        assert raise_inside
    assert destination is not None and not destination.exists()
    assert list(tmp_path.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"existing file"


def test_rejected_input_is_never_staged(tmp_path):
    with pytest.raises(AdmissionError):
        with staged_upload(
            io.BytesIO(b"<html>bad</html>"),
            filename="x.csv",
            content_type="text/csv",
            storage_root=tmp_path,
        ):
            pytest.fail("Rejected content cannot reach a downstream loader")
    assert list(tmp_path.iterdir()) == []


def test_failed_storage_write_is_sanitized_and_cleans_directory(tmp_path, monkeypatch):
    from kkb_agent import ingestion_policy

    opened = []

    def fail_write(descriptor, *args, **kwargs):
        opened.append(descriptor)
        raise OSError("sensitive-storage-path")

    monkeypatch.setattr(ingestion_policy.os, "fdopen", fail_write)
    with pytest.raises(AdmissionError, match="^STORAGE_FAILED$"):
        with staged_upload(
            io.BytesIO(CSV), filename="x.csv", content_type="text/csv", storage_root=tmp_path
        ):
            pytest.fail("Failed write cannot yield storage")
    assert len(opened) == 1
    with pytest.raises(OSError):
        ingestion_policy.os.fstat(opened[0])
    assert list(tmp_path.iterdir()) == []


def test_symlink_or_missing_storage_root_rejected(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    for root in (link, tmp_path / "missing"):
        with pytest.raises(AdmissionError, match="^STORAGE_FAILED$"):
            with staged_upload(
                io.BytesIO(CSV), filename="x.csv", content_type="text/csv", storage_root=root
            ):
                pytest.fail("Invalid storage root")
    assert list(tmp_path.iterdir()) == [link]
