"""FinTürk, BDDK's province breakdown: which cells can be read, and what is declared for each.

FinTürk is the third BDDK dataset the organizer names (DEC-184). It publishes seven tables
every quarter, one row per province, for the sector and six bank groups. This module turns
its own pinned listing into selectors and catalogue declarations; it fetches nothing and
stores no observation.

What is declared comes from the source's own labels and from what was measured on
2026-09-21, never from a response read at question time:

* **the unit is the table's label**, and it differs from the bulletins': "Bin TL" is
  thousand lira where the monthly and weekly bulletins say million, a 1000x error that looks
  plausible on a chart. "Oranlar (%)" is a percentage. The one table whose label names two
  units ("Şubeler (Adet) ve Nüfusa Göre Dağılım (TL)") is declared column by column, and a
  column it does not list is not readable;
* **quarterly**, dated to the quarter's last day: the source offers months 3, 6, 9, 12 only;
* **a position**: İstanbul's housing loans stood at 197,406,766 at 2025/12 and 212,592,596 at
  2026/3, so nothing restarts in January.

An identity is a table, one of its columns and a province. The selector's `row` is the
column's place in the table, its `geography` the province in ASCII capitals, because the
selector syntax (DEC-139) has no other free dimension and must not change for the series
already stored under it.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Final

from pydantic import ConfigDict

from kkb_agent.catalog.records import AggregationPolicy, CatalogRecord, SourceGroup
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_finturk_directory import DIRECTORY, DIRECTORY_SHA256
from kkb_agent.ingest.bddk_monthly import BddkSelector, MetadataText, SelectorNumber

SECTOR: Final = 10001
_LABEL = re.compile(r"^(?P<title>.+?)\s*\((?P<unit>[^()]+)\)\s*$")
#: A table label's one unit -> what is declared for every column of that table.
_LABEL_UNITS: Final = {
    "Bin TL": ("TRY", Scale.THOUSAND, StockFlow.STOCK),
    "%": ("percent", Scale.ONE, StockFlow.RATE),
}
#: The table whose label names two units, column by column. Anything else in it is unread.
_MIXED_TABLE: Final = "Şubeler (Adet) ve Nüfusa Göre Dağılım (TL)"
_MIXED_COLUMNS: Final = {
    "Yurtiçi Şube Sayısı": ("count", Scale.ONE, StockFlow.STOCK),
    "Şubeye Düşen Nüfus": ("ratio", Scale.ONE, StockFlow.RATE),
    "Kişi Başı Nakdi Kredi": ("TRY", Scale.ONE, StockFlow.STOCK),
    "Kişi Başı Takipteki Alacak": ("TRY", Scale.ONE, StockFlow.STOCK),
    "Kişi Başı Tasarruf Mevduatı": ("TRY", Scale.ONE, StockFlow.STOCK),
    "Kişi Başı Toplam Mevduat": ("TRY", Scale.ONE, StockFlow.STOCK),
}
#: A position or a ratio reduces over time by its last value; neither ever adds up.
_LAST: Final = AggregationPolicy(default=Aggregation.LAST, last=True, sum=False)
_UNIT_WORDS: Final = {
    ("TRY", Scale.THOUSAND): "bin TL (aylık ve haftalık bültenler milyon TL'dir)",
    ("TRY", Scale.ONE): "TL",
    ("percent", Scale.ONE): "yüzde",
    ("count", Scale.ONE): "adet",
    ("ratio", Scale.ONE): "kişi/şube",
}


def _digest_of_listing() -> str:
    canonical = json.dumps(DIRECTORY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


if _digest_of_listing() != DIRECTORY_SHA256:  # pragma: no cover - a hand-edited listing
    raise RuntimeError("FinTürk directory does not match its pinned digest")


def province_token(name: str) -> str:
    """A province as the selector writes it: ASCII capitals, words joined by an underscore."""
    folded = name.replace("İ", "I").replace("ı", "i").upper()
    plain = "".join(
        char for char in unicodedata.normalize("NFD", folded) if not unicodedata.combining(char)
    )
    return "_".join(re.findall(r"[A-Z0-9]+", plain))


class FinturkColumn(ContractModel):
    """One column of one FinTürk table, with everything declared for it."""

    model_config = ConfigDict(frozen=True)

    table: SelectorNumber
    column: SelectorNumber
    table_title: MetadataText
    table_label: MetadataText
    name: MetadataText
    unit: str
    scale: Scale
    stock_flow: StockFlow


def _columns() -> dict[tuple[int, int], FinturkColumn]:
    found: dict[tuple[int, int], FinturkColumn] = {}
    if DIRECTORY["side"] != "SEKTÖR":
        return found
    for number, table in DIRECTORY["tables"].items():
        label = table["label"]
        parsed = _LABEL.match(label)
        shared = _LABEL_UNITS.get(parsed["unit"]) if parsed else None
        for position, name in enumerate(table["columns"], start=1):
            declared = shared or (_MIXED_COLUMNS.get(name) if label == _MIXED_TABLE else None)
            if declared is None:
                continue  # a unit this adapter cannot declare: listed, never fetched
            unit, scale, kind = declared
            found[int(number), position] = FinturkColumn(
                table=int(number),
                column=position,
                table_title=parsed["title"] if parsed and shared else label,
                table_label=label,
                name=" ".join(name.split()),
                unit=unit,
                scale=scale,
                stock_flow=kind,
            )
    return found


#: (table, column) -> what is declared for it. Built once from the pinned listing.
SUPPORTED_COLUMNS: Final[dict[tuple[int, int], FinturkColumn]] = _columns()
#: Selector token -> the province as the source writes it, per table (two tables list 81).
PROVINCES: Final[dict[int, dict[str, str]]] = {
    int(number): {province_token(name): name for name in table["provinces"]}
    for number, table in DIRECTORY["tables"].items()
}


class UnlistedFinturkSelector(ValueError):
    """The selector names nothing the FinTürk listing supports."""


def listed_finturk(selector: BddkSelector) -> tuple[BddkSelector, FinturkColumn, str]:
    """The sector aggregate in TL, for a listed column and a province its table has."""
    selector = BddkSelector.model_validate(selector)
    column = SUPPORTED_COLUMNS.get((selector.table, selector.row))
    province = PROVINCES.get(selector.table, {}).get(selector.geography or "")
    if (
        selector.bulletin_family != "finturk"
        or selector.bank_group != SECTOR
        or selector.presentation_currency != "TL"
        or selector.value_dimension != "TOTAL"
        or column is None
        or province is None
    ):
        raise UnlistedFinturkSelector("Selector is outside the listed FinTürk scope")
    return selector, column, province


def supported_finturk_selectors() -> tuple[BddkSelector, ...]:
    """Every selector this adapter accepts: each declared column, in each province."""
    return tuple(
        BddkSelector(
            bulletin_family="finturk",
            table=column.table,
            row=column.column,
            bank_group=SECTOR,
            presentation_currency="TL",
            value_dimension="TOTAL",
            geography=token,
        )
        for _, column in sorted(SUPPORTED_COLUMNS.items())
        for token in sorted(PROVINCES[column.table])
    )


def place_name(province: str) -> str:
    """The province as a reader writes it: "İSTANBUL" -> "İstanbul"."""
    return " ".join(
        word[:1] + word[1:].replace("I", "ı").replace("İ", "i").lower() for word in province.split()
    )


def finturk_directory_catalog(selector: BddkSelector) -> CatalogRecord:
    """Declarations for a listed FinTürk cell: from the listing, never from a response."""
    selector, column, province = listed_finturk(selector)
    place = place_name(province)
    unit_words = _UNIT_WORDS[column.unit, column.scale]
    kind = (
        "Çeyrek sonu oranı."
        if column.stock_flow is StockFlow.RATE
        else "Çeyrek sonu bakiyesi (stok): bakiyesi, tutarı, hacmi; kullandırım ya da akım değil."
    )
    return CatalogRecord(
        series_id=selector.internal_id(),
        provider="BDDK",
        source_series_id="selector-v1:" + selector.canonical_selector(),
        title=f"{column.name} - {place}",
        source=SourceRef(
            source_id="bddk:finturk-directory-v1",
            source_type="repository_inventory",
            locator="repo:src/kkb_agent/ingest/bddk_finturk_directory.py",
            content_hash=DIRECTORY_SHA256,
        ),
        # Turkish first: people ask in Turkish, by province ("İstanbul'da", "illere göre").
        description=(
            f"BDDK FinTürk, il bazında veri: {column.table_label} tablosu, {column.name}, "
            f"{place} ili. Birim: {unit_words}. Çeyreklik (3., 6., 9. ve 12. aylar). {kind} "
            "İllere göre, il kırılımı, şehir bazında; ülke toplamı bu kaynakta yoktur, Aylık "
            "Bülten'dedir. Province-level quarter-end figure, sector aggregate. Kaynağın kendi "
            "listesinden: birim tablo etiketinden; tek tek incelenmedi. Internal composite "
            "selector, not an official BDDK code."
        ),
        # No TP/YP/TOTAL label: FinTürk splits no column by currency, and the ranking reads
        # such a label as one (a deposit column named "(TL)" would be ranked as a total).
        labels=("FinTürk", "Sektör", column.table_title, place),
        group=SourceGroup(
            group_id=f"finturk:{column.table}", group_title=column.table_title, publisher="BDDK"
        ),
        unit=column.unit,
        scale=column.scale,
        frequency=Frequency.QUARTERLY,
        stock_flow=column.stock_flow,
        cumulative=CumulativeKind.NONE,
        aggregation=_LAST,
    )
