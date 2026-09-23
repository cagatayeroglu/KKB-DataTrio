"""The country is not a place, and an entry that declares no place is not another's.

Measured 2026-09-23 on the served catalogue: the monthly and weekly bulletins' entries say
"Türkiye", so "Türkiye" was a place, and "Türkiye enflasyon oranı" was searched among
series marked Türkiye only - 0 of the 678 EVDS datagroups, which declare no place, could
be found. "İstanbul konut satışları" held them all back too, although EVDS publishes
per-province housing sales as datagroups.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from kkb_agent.catalog.directory import source_directory
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, eligible_catalog_series, named_places
from kkb_agent.knowledge.overlay import effective_snapshot

CATALOG = Path(__file__).resolve().parents[2] / "docs" / "catalog" / "prepared_v3.json"


@cache
def served():
    return effective_snapshot(
        load_reviewed_snapshot(CATALOG.read_bytes()), [], [], source_directory()
    )


def eligible(query: str):
    return eligible_catalog_series(served(), CatalogSearchArguments(query=query))


def groups(entries) -> int:
    return sum(item.record.series_id.startswith("EVDS:group:") for item in entries)


def test_the_country_is_not_a_place():
    assert not named_places(served(), "Türkiye enflasyon oranı")
    assert not named_places(served(), "Türkiye'de konut kredisi")
    everything = eligible("konut kredisi")
    assert len(eligible("Türkiye konut kredisi")) == len(everything)
    assert groups(eligible("Türkiye enflasyon oranı")) == groups(everything) > 0


def test_a_named_province_keeps_what_declares_no_place_and_drops_the_country():
    assert named_places(served(), "İstanbul konut satışları") == {"istanbul"}
    scoped = eligible("İstanbul konut satışları")
    assert groups(scoped) == groups(eligible("konut satışları")) > 0
    places = {item.geography for item in scoped if item.geography}
    assert places == {"İstanbul"}
