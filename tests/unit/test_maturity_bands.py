"""The bulletin's maturity columns: readable series, and listed under their row.

B1 asks for TP deposits grouped by the maturity they were opened at. The bulletin
publishes maturity as columns, and a row was readable only as its total, so six of the
seven columns of a deposit row existed for nobody. The adapter reads a band as a series
of its own (its selector names the band; a selector that names none is the one it always
was). In search, a band is folded under its row's candidate with its series ID, rather
than hidden until a question says "vade", and rather than taking seven of ten places.
"""

from __future__ import annotations

import pytest
from test_source_directory import catalogue  # noqa: F401 - the shared module fixture

from kkb_agent.catalog.mappings import is_listed_series
from kkb_agent.catalog.search import CatalogSearchArguments, fold_bands, search_catalog
from kkb_agent.ingest.bddk_monthly import SUPPORTED_ROWS, BddkSelector

BANDS = ("Vadesiz", "1 Aya Kadar", "1-3 Ay Arası", "3-6 Ay Arası", "6-12 Ay Arası", "1 Yıl Üzeri")
TP_ROW = "TP Mevduat / Katılım Fonları - Yurt İçi Yerleşik"


def deposit_row() -> int:
    (row,) = [
        number
        for (table, number), listed in SUPPORTED_ROWS.items()
        if table == 10 and listed.label == TP_ROW
    ]
    return row


def band_id(band: str) -> str:
    return BddkSelector(
        bulletin_family="monthly",
        table=10,
        row=deposit_row(),
        bank_group=10001,
        presentation_currency="TL",
        value_dimension="TOTAL",
        band=band,
    ).internal_id()


@pytest.mark.parametrize("bounded", [True, False])
def test_a_deposit_row_carries_its_maturity_columns(catalogue, bounded):  # noqa: F811
    _, effective = catalogue
    output = search_catalog(
        effective, CatalogSearchArguments(query="TP mevduat vade", source="BDDK"), bounded=bounded
    )
    [row] = [
        c
        for c in output.candidates
        if c.series.record.title == TP_ROW
        and c.series.record.group is not None
        and c.series.record.group.group_id == "10"
    ]
    # First: the row's title names TP, and its TOTAL label is the layout's total column,
    # not the TP+YP total a question naming TP would contradict.
    assert output.candidates[0] is row
    assert sorted(choice.band for choice in row.bands) == sorted(BANDS)
    assert {choice.series_id for choice in row.bands} == {band_id(band) for band in BANDS}
    # No band sits beside its own row as a candidate of its own.
    titles = [c.series.record.title for c in output.candidates]
    assert not any(title.startswith(TP_ROW + " (") for title in titles)


def test_a_band_is_a_listed_series_with_its_own_identity(catalogue):  # noqa: F811
    _, effective = catalogue
    by_id = {item.record.series_id: item for item in effective.series}
    item = by_id[band_id("1-3 Ay Arası")]
    assert is_listed_series(item)
    assert item.record.title == f"{TP_ROW} (1-3 Ay Arası)"
    assert "Vade: 1-3 Ay Arası" in item.record.labels
    total = BddkSelector(
        bulletin_family="monthly",
        table=10,
        row=deposit_row(),
        bank_group=10001,
        presentation_currency="TL",
        value_dimension="TOTAL",
    )
    assert total.internal_id() != item.record.series_id
    assert '"band"' not in total.canonical_selector()


def test_a_band_whose_row_was_not_reached_stands_for_it(catalogue):  # noqa: F811
    _, effective = catalogue
    bands = [item for item in effective.series if item.record.title.startswith(TP_ROW + " (")]
    assert len(bands) == len(BANDS)
    [(first, siblings)] = fold_bands(bands, reviewed_series=lambda item: item)
    assert first is bands[0] and siblings == bands[1:]
