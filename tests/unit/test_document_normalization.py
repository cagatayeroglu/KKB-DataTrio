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


@pytest.mark.parametrize(
    "mixed,header,expected",
    [
        (False, "Faiz", "percent"),
        (True, "Faiz", None),
        (False, "Faiz (TL)", "conflict"),
    ],
)
def test_percentage_format_evidence_is_column_wide_and_cannot_override_unit(
    mixed, header, expected
):
    from test_requested_deliverables import workbook

    from kkb_agent.ingestion_policy import DEFAULT_LIMITS
    from kkb_agent.tools._document_column import ColumnRefused
    from kkb_agent.xlsx_loader import _parse

    payload = _parse(workbook(mixed=mixed, header=header), None, DEFAULT_LIMITS)
    grid = Grid(
        {"table": 1},
        tuple(payload["headers"]),
        tuple(tuple(row) for row in payload["rows"]),
        normalizations=tuple(payload["normalizations"]),
    )
    if expected == "conflict":
        with pytest.raises(ColumnRefused, match="NO_USABLE_COLUMN"):
            read_table([grid], "Ay", ["Faiz"])
    else:
        table = read_table([grid], "Ay", ["Faiz"])
        assert table.columns[0].unit == expected
        if expected:
            assert table.columns[0].unit_source == "Excel percentage number format"
            assert table.columns[0].cells[0][1] == 47.6
            with pytest.raises(ColumnRefused, match="NO_USABLE_COLUMN"):
                from kkb_agent.core import Scale

                read_table([grid], "Ay", ["Faiz"], declared_units={"Faiz": ("TRY", Scale.ONE)})
