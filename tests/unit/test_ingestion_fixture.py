"""Pin the M1-04 synthetic example from docs/INGESTION_PROFILE.md.

An empty field is missing, not zero. Dates/numbers below are literal cells;
they declare no unit, business frequency, time role or stock/flow semantics.
"""

import csv
from pathlib import Path


def test_synthetic_csv_fixture_has_stable_utf8_table() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/ingestion/synthetic_utf8.csv"
    # Opening also verifies presence and strict UTF-8 decoding. This is only a
    # fixture oracle using stdlib CSV, not an application loader or profile.
    with fixture.open(encoding="utf-8", newline="") as source:
        table = list(csv.reader(source, delimiter=",", strict=True))

    assert table == [
        ["as_of", "measure", "label"],
        ["2026-01-31", "100", "A"],
        ["2026-02-28", "", "B"],
        ["2026-03-31", "125", "C"],
    ]
