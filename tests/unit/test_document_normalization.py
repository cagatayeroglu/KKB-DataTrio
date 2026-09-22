from datetime import date

import pytest

from kkb_agent.tools._document_column import month_end
from kkb_agent.tools._document_table import read_table
from kkb_agent.tools._document_value import Grid


@pytest.mark.parametrize(
    "text", ["2024-1", "Oca.24", "Oca 2024", "Ocak-24", "2024M01", "01/2024", "31-01-2024"]
)
def test_unambiguous_turkish_period_spellings(text):
    assert month_end(text) == date(2024, 1, 31)


@pytest.mark.parametrize("marker", ["-", "–", "...", "..", "n/a"])
def test_missing_marker_preserves_numeric_column(marker):
    table = read_table(
        [
            Grid(
                {"table": 1},
                ("Ay", "Faiz (%)"),
                (("2024-01", 4), ("2024-02", marker), ("2024-03", 6)),
            )
        ],
        "Ay",
        ["Faiz"],
    )
    assert [value for _, value, _ in table.columns[0].cells] == [4, None, 6]


def test_explicit_footers_are_recorded_and_not_numeric_observations():
    table = read_table(
        [
            Grid(
                {"table": 1},
                ("Ay", "Faiz (%)"),
                (("2024-01", 4), ("2024-02", 6), ("Ortalama", 5), ("Kaynak: Resmi bülten", None)),
            )
        ],
        "Ay",
        ["Faiz"],
    )
    assert [value for _, value, _ in table.columns[0].cells] == [4, 6]
    assert table.rules.evidence()["skipped_rows"]["ANNOTATION_ROW"] == 2
