"""M1-05 fixture oracles; stdlib CSV here is not the application loader."""

import codecs
import csv
import io
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/ingestion"


@pytest.mark.parametrize(
    ("filename", "delimiter", "has_bom", "expected_table"),
    [
        (
            "semicolon.csv",
            ";",
            False,
            [
                ["as_of", "measure", "label"],
                ["2026-01-31", "100", "A"],
                ["2026-02-28", "", "B"],
            ],
        ),
        (
            "quoted_fields.csv",
            ",",
            False,
            [
                ["as_of", "measure", "label"],
                ["2026-01-31", "100", "A, quoted"],
                ["2026-02-28", "", 'B "quoted"'],
                ["2026-03-31", "125", "C\ncontinued"],
            ],
        ),
        (
            "utf8_bom.csv",
            ",",
            True,
            [
                ["as_of", "measure", "label"],
                ["2026-01-31", "100", "Örnek"],
                ["2026-02-28", "", "çığ"],
            ],
        ),
        (
            "numeric_separators.csv",
            ";",
            False,
            [
                ["as_of", "measure_comma", "measure_dot", "label"],
                ["2026-01-31", "1,234", "1.234", "A"],
                ["2026-02-28", "2,345", "2.345", "B"],
            ],
        ),
    ],
    ids=["semicolon", "quoted-fields", "utf8-bom", "numeric-ambiguity"],
)
def test_csv_edge_fixture_has_declared_bytes_and_table(
    filename: str, delimiter: str, has_bom: bool, expected_table: list[list[str]]
) -> None:
    raw = (FIXTURES / filename).read_bytes()
    assert raw.startswith(codecs.BOM_UTF8) is has_bom
    assert b"\r" not in raw  # These fixture declarations use LF, including quoted LF.
    text = raw.decode("utf-8-sig" if has_bom else "utf-8", errors="strict")
    table = list(
        csv.reader(
            io.StringIO(text, newline=""),
            delimiter=delimiter,
            quotechar='"',
            doublequote=True,
            strict=True,
        )
    )
    # Exact string cells pin ambiguity and missing values without conversion.
    assert table == expected_table
