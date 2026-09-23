"""The BDDK weekly bulletin: which items can be read, and what is declared for each.

The weekly bulletin is the monthly one's sibling (DEC-182). Its page lists nine tables of
balance-sheet positions for the sector, in million TL, one observation a week. This module
turns the bulletin's own pinned listing into selectors and catalogue declarations; it
fetches nothing and stores no observation.

What is declared comes from what was measured on 2026-09-20, never from a response read at
question time:

* **unit and scale** from the page's one caption, "Birim: Milyon TL", which all nine tables
  share; any other caption leaves the whole listing unsupported;
* **weekly, ending on a Friday.** Every week is published. A week whose Friday is a holiday is
  dated to its last working day (19.07.2021 a Monday, 9.04.2024 a Tuesday, 12.05.2021 a
  Wednesday, 20.04.2023 a Thursday); the loader files it under that week's Friday;
* **a position, not a flow.** Every table is a balance-sheet, off-balance-sheet, custody or
  currency-position table, so a row is what stood at the week's end. Several weeks reduce to
  one month by the last of them; their sum means nothing and is forbidden.

A sub-item ("a) Konut") is titled with the row it sits under, because the same sub-item
label appears under several rows. Where that is still not one title (the custody tables
repeat "Gerçek Kişiler" for residents and non-residents), the row whose own arithmetic
names it ("Yurtiçi Yerleşikler Adına Saklanan (3+7+11+15+19)") is put in front.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final, Literal

from pydantic import ConfigDict

from kkb_agent.catalog.records import AggregationPolicy, CatalogRecord, SourceGroup
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_monthly import BddkSelector, MetadataText, SelectorNumber
from kkb_agent.ingest.bddk_weekly_directory import DIRECTORY, DIRECTORY_SHA256

SECTOR: Final = 10001
#: Caption units this adapter can declare. Any other caption leaves the listing unsupported.
_CAPTION_UNITS: Final = {"Milyon TL": ("TRY", Scale.MILLION)}
#: The component a selector names -> the column number the source asks for, and the word
#: the source's answer uses for that column in its title.
COLUMNS: Final[dict[str, tuple[int, str]]] = {
    "TP": (1, "TP"),
    "YP": (2, "YP"),
    "TOTAL": (3, "Toplam"),
}
_COMPONENTS: Final[tuple[Literal["TP", "YP", "TOTAL"], ...]] = ("TP", "YP", "TOTAL")
_COMPONENT_WORDS: Final = {
    "TP": "TP (Türk parası, TL cinsi)",
    "YP": "YP (yabancı para, döviz cinsi; TL karşılığı)",
    "TOTAL": "Toplam (TP + YP)",
}
#: A position reduces over time by its last value; several positions never add up.
WEEKLY_POLICY: Final = AggregationPolicy(default=Aggregation.LAST, last=True, sum=False)
_FORMULA = re.compile(r"\s*\((?:\d+[+-])+\d+\)")
_TERMS = re.compile(r"\((\d+(?:[+-]\d+)+)\)")
_MARKER = re.compile(r"^(?:[a-zçğıöşü]\)|-)\s*")


def _digest_of_listing() -> str:
    canonical = json.dumps(DIRECTORY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


if _digest_of_listing() != DIRECTORY_SHA256:  # pragma: no cover - a hand-edited listing
    raise RuntimeError("BDDK weekly directory does not match its pinned digest")


def _plain(label: str) -> str:
    """A label without its row arithmetic ("(4+5+6)") or list marker ("a) ", "- ")."""
    return _MARKER.sub("", _FORMULA.sub("", label)).strip()


def _titles(rows: list[dict[str, Any]]) -> dict[int, str]:
    """One title per row of a table, by the number the page shows it under.

    A sub-item takes the row it sits under. A title two rows still share is told apart by
    the row whose arithmetic names it, read from the page's own "(3+7+11)" labels; a memo
    row no arithmetic names ("Döv. End. KBS (Bilgi)", once per custody section) takes the
    section it stands in.
    """
    heads = {int(entry["number"]): entry for entry in rows if entry["parent"] is None}
    terms = {number: _terms_of(head["label"]) for number, head in heads.items()}
    named_by = {
        number: max((n for n in heads if n < number and str(number) in terms[n]), default=None)
        for number in heads
    }
    sections = [n for n, above in named_by.items() if above is not None and named_by[above] is None]
    titles: dict[int, str] = {}
    owner: dict[int, int] = {}
    for entry in rows:
        number, title = int(entry["number"]), _plain(entry["label"])
        owner[number] = number
        if entry["parent"] is not None:
            title = f"{_plain(entry['parent'])} - {title}"
            # The nearest row above with that label: the same label heads several groups.
            owner[number] = max(
                (n for n, head in heads.items() if n < number and head["label"] == entry["parent"]),
                default=number,
            )
        titles[number] = title
    counted = list(titles.values())
    for number, title in list(titles.items()):
        if counted.count(title) < 2:
            continue
        above = named_by.get(owner[number])
        if above is None:
            above = max((n for n in sections if n < owner[number]), default=None)
        if above is not None:
            titles[number] = f"{_plain(heads[above]['label'])} - {title}"
    return titles


def _terms_of(label: str) -> tuple[str, ...]:
    found = _TERMS.search(label)
    return tuple(re.split(r"[+-]", found.group(1))) if found else ()


class WeeklyRow(ContractModel):
    """One listed item of the weekly bulletin, with everything declared for it."""

    model_config = ConfigDict(frozen=True)

    table: SelectorNumber
    row: SelectorNumber
    number: SelectorNumber
    table_title: MetadataText
    label: MetadataText
    parent: MetadataText | None
    title: MetadataText
    components: tuple[Literal["TP", "YP", "TOTAL"], ...]
    unit: str
    scale: Scale


def _supported_rows() -> dict[tuple[int, int], WeeklyRow]:
    declared = _CAPTION_UNITS.get(DIRECTORY["unit_text"])
    if declared is None or DIRECTORY["side"] != "Sektör":
        return {}
    unit, scale = declared
    found: dict[tuple[int, int], WeeklyRow] = {}
    for number, table in DIRECTORY["tables"].items():
        titles = _titles(table["rows"])
        for entry in table["rows"]:
            components = tuple(
                name for name in _COMPONENTS if str(COLUMNS[name][0]) in entry["columns"]
            )
            if not components:
                continue  # a row with no column this adapter can name: listed, never fetched
            parent = entry["parent"]
            title = titles[int(entry["number"])]
            found[int(number), int(entry["row"])] = WeeklyRow(
                table=int(number),
                row=int(entry["row"]),
                number=int(entry["number"]),
                table_title=table["title"],
                label=entry["label"],
                parent=parent,
                title=title,
                components=components,
                unit=unit,
                scale=scale,
            )
    return found


#: (table, item row) -> what is declared for it. Built once from the pinned listing.
SUPPORTED_WEEKLY_ROWS: Final[dict[tuple[int, int], WeeklyRow]] = _supported_rows()


class UnlistedWeeklySelector(ValueError):
    """The selector names nothing the weekly listing supports."""


def listed_weekly(selector: BddkSelector) -> tuple[BddkSelector, WeeklyRow]:
    """The sector aggregate in TL, for a listed row and a column that row has."""
    selector = BddkSelector.model_validate(selector)
    row = SUPPORTED_WEEKLY_ROWS.get((selector.table, selector.row))
    if (
        selector.bulletin_family != "weekly"
        or selector.bank_group != SECTOR
        or selector.presentation_currency != "TL"
        or selector.geography is not None
        or row is None
        or selector.value_dimension not in row.components
    ):
        raise UnlistedWeeklySelector("Selector is outside the listed weekly bulletin scope")
    return selector, row


def supported_weekly_selectors() -> tuple[BddkSelector, ...]:
    """Every selector this adapter accepts: each listed row, in the columns it has."""
    return tuple(
        BddkSelector(
            bulletin_family="weekly",
            table=row.table,
            row=row.row,
            bank_group=SECTOR,
            presentation_currency="TL",
            value_dimension=component,
        )
        for _, row in sorted(SUPPORTED_WEEKLY_ROWS.items())
        for component in row.components
    )


def expected_title(selector: BddkSelector) -> str:
    """The title the source gives its answer for this selector, whitespace runs collapsed."""
    selector, row = listed_weekly(selector)
    return f"{row.label} (TRY) [{COLUMNS[selector.value_dimension][1]}] [Sektör]"


def weekly_directory_catalog(selector: BddkSelector) -> CatalogRecord:
    """Declarations for a listed weekly item: from the listing, never from a response."""
    selector, row = listed_weekly(selector)
    return CatalogRecord(
        series_id=selector.internal_id(),
        provider="BDDK",
        source_series_id="selector-v1:" + selector.canonical_selector(),
        title=row.title,
        source=SourceRef(
            source_id="bddk:weekly-directory-v1",
            source_type="repository_inventory",
            locator="repo:src/kkb_agent/ingest/bddk_weekly_directory.py",
            content_hash=DIRECTORY_SHA256,
        ),
        # Turkish first: people ask in Turkish, and the words a kind is asked by
        # ("haftalık", "bakiyesi", "tutarı") are what word search can match.
        description=(
            f"BDDK Haftalık Bülten, {row.table_title} tablosu, {row.number}. satır: {row.label}. "
            f"Bileşen: {_COMPONENT_WORDS[selector.value_dimension]}. Haftalık, hafta sonu "
            "(cuma) bakiyesi (stok): bakiyesi, tutarı, hacmi; kullandırım ya da akım değildir. "
            "Cuması tatil olan hafta son iş günüyle yayımlanır ve o haftanın cumasına yazılır. "
            "Aylığa indirgenirken ayın son haftası alınır. Week-end outstanding position, "
            "sector aggregate. Kaynağın kendi listesinden: birim sayfa başlığından; satır satır "
            "incelenmedi. Internal composite selector, not an official BDDK code."
        ),
        # The monthly entries' order, so the component sits where every reader expects it;
        # the table comes last, and tells the loan from the non-performing loan of one name.
        labels=(
            "Haftalık Bülten",
            "Sektör",
            selector.value_dimension,
            "Sunum para birimi: TL",
            row.table_title,
        ),
        group=SourceGroup(
            group_id=f"weekly:{row.table}", group_title=row.table_title, publisher="BDDK"
        ),
        unit=row.unit,
        scale=row.scale,
        frequency=Frequency.WEEKLY,
        weekly_anchor=WeeklyAnchor.FRIDAY,
        stock_flow=StockFlow.STOCK,
        cumulative=CumulativeKind.NONE,
        aggregation=WEEKLY_POLICY,
    )
