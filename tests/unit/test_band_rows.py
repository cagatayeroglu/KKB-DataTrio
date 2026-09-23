"""A maturity band says which row, table and currency it belongs to (live B1, 2026-09-23).

The TP and DTH rows' bands were listed side by side as bare `{band, series_id}` pairs; the
model took the DTH bands for TP maturity groups (their December 2020 sum was the YP
total, 1,458,547) and spent its call budget searching for bands it had been shown. What
is checked here is what the model reads: the tool output as the loop serializes it.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from kkb_agent.agent.trust_loop import observed_payload
from kkb_agent.catalog.directory import source_directory
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.knowledge.overlay import effective_snapshot

CATALOG = Path(__file__).resolve().parents[2] / "docs" / "catalog" / "prepared_v3.json"
TP_ROW = "TP Mevduat / Katılım Fonları - Yurt İçi Yerleşik"
YP_ROW = "Döviz Tevdiat Hesabı / Katılım Fonları - Yurt İçi Yerleşik"
TABLE = "Mevduat Vade İtibarıyla"


@cache
def served():
    reviewed = load_reviewed_snapshot(CATALOG.read_bytes())
    return effective_snapshot(reviewed, [], [], source_directory())


def seen(query: str) -> list[dict]:
    """The candidates as the model is shown them."""
    arguments = CatalogSearchArguments(query=query, source="BDDK")
    output = search_catalog(served(), arguments, bounded=False)
    payload = json.loads(json.dumps(observed_payload(output), ensure_ascii=False, default=str))
    return payload["candidates"]


def bands_of(candidates: list[dict], row: str) -> list[dict]:
    owner = [c for c in candidates if c["series"]["record"]["title"] == row and c.get("bands")]
    assert len(owner) == 1, f"one {row!r} candidate carries its bands"
    return owner[0]["bands"]


def test_the_model_sees_each_bands_row_table_and_currency():
    tp = bands_of(seen("TP mevduat yurt içi yerleşik vade"), TP_ROW)
    yp = bands_of(seen("Döviz tevdiat hesabı yurt içi yerleşik vade"), YP_ROW)
    for bands, row, currency in ((tp, TP_ROW, "TP"), (yp, YP_ROW, "YP")):
        assert len(bands) >= 3
        for band in bands:
            assert set(band) >= {"band", "series_id", "row", "table", "currency"}
            assert band["row"] == row and band["table"] == TABLE
            assert band["currency"] == currency
        # One series per band of a row.
        assert len({b["series_id"] for b in bands}) == len({b["band"] for b in bands}) == len(bands)
    # The TP row's bands and the DTH row's are different series.
    assert not {b["series_id"] for b in tp} & {b["series_id"] for b in yp}


def test_no_candidate_carries_another_rows_bands():
    for query in (
        "TP mevduat yurt içi yerleşik vade",
        "Döviz tevdiat hesabı yurt içi yerleşik vade",
    ):
        for candidate in seen(query):
            for band in candidate.get("bands") or []:
                assert band["row"] == candidate["series"]["record"]["title"]
