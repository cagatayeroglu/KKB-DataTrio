"""What the official sources list themselves, as catalogue entries nobody reviewed (DEC-176/177).

The reviewed snapshot names the series a person checked one by one. It is a map of 37
places; the sources publish thousands. A question about anything else used to end in "not
found", although the adapters could fetch it, because nothing told the search that it
exists. This module turns each source's own pinned listing into catalogue entries of a second
tier:

* they are found by the same search, after the reviewed tier: a reviewed concept that
  matches a question still bounds the candidates to reviewed series;
* their declarations come only from the source's own fields (see each adapter), never from
  a model and never from a response read at question time;
* they are fetched on first use by the same adapters, through the same strict loaders, and
  the inspector checks the stored declaration against the entry exactly as for any series.

A source joins by providing entries here and a route in `ingest.acquisition`; search, the
planner, the inspector and the answer gate need no change. Today: the BDDK monthly bulletin
(every supported row, in its three components), the BDDK weekly bulletin (every listed item,
in the columns it has; DEC-182) and EVDS datagroups (found by meaning, then opened into the
series EVDS lists under them by `catalog.expansion`).

The model still never supplies a code, an address or a window. It can only name an identity
the catalogue search returned.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from kkb_agent.catalog.discovered import evds_evidence
from kkb_agent.catalog.mappings import (
    DIRECTORY_EVIDENCE_PREFIX,
    Evidence,
    ReviewedSeries,
    is_listed_series,
)
from kkb_agent.catalog.records import CatalogRecord, CatalogStatus, SourceGroup
from kkb_agent.core import Frequency, SourceRef
from kkb_agent.ingest.bddk_monthly import (
    HOUSING_ROW,
    HOUSING_TABLE,
    monthly_directory_catalog,
    supported_selectors,
)
from kkb_agent.ingest.bddk_monthly_directory import DIRECTORY_SHA256
from kkb_agent.ingest.bddk_weekly import supported_weekly_selectors, weekly_directory_catalog
from kkb_agent.ingest.bddk_weekly_directory import DIRECTORY_SHA256 as WEEKLY_DIRECTORY_SHA256
from kkb_agent.ingest.evds_directory import FREQUENCIES, ListedGroup, listed_groups
from kkb_agent.ingest.evds_directory_listing import DIRECTORY_SHA256 as EVDS_DIRECTORY_SHA256

BDDK_EVIDENCE_ID: Final = DIRECTORY_EVIDENCE_PREFIX + "bddk-monthly"
BDDK_WEEKLY_EVIDENCE_ID: Final = DIRECTORY_EVIDENCE_PREFIX + "bddk-weekly"
EVDS_GROUP_PREFIX: Final = "EVDS:group:"
DIRECTORY_NOTE: Final = (
    "Listed by the source's own directory and fetched from it on first use. Unit, scale, "
    "frequency and stock/flow come from the source's own fields and measured behaviour; "
    "the entry was not reviewed one by one."
)
GROUP_NOTE: Final = (
    "An EVDS datagroup, listed so that search can find it by meaning. It is not a series and "
    "cannot be read; a search result opens it into the series EVDS lists under it."
)
#: Shown with an answer that rests on such a series.
DIRECTORY_LIMITATION: Final = (
    "Bu seri resmî kaynağın kendi dizininden alındı; birim ve ölçüm türü kaynağın alanlarından "
    "türetildi, tek tek incelenmedi."
)


@dataclass(frozen=True, slots=True)
class SourceDirectory:
    """The second tier: entries, the evidence they cite, and one digest for all of it."""

    series: tuple[ReviewedSeries, ...]
    evidence: tuple[Evidence, ...]
    digest: str

    def ids(self) -> frozenset[str]:
        return frozenset(item.record.series_id for item in self.series)


is_directory_series = is_listed_series


def _bddk_series() -> tuple[ReviewedSeries, ...]:
    return tuple(
        ReviewedSeries(
            record=monthly_directory_catalog(selector),
            evidence_ids=(BDDK_EVIDENCE_ID,),
            title_basis="documented_title",
            geography="Türkiye",
            note=DIRECTORY_NOTE,
        )
        for selector in supported_selectors()
        # The housing rows are reviewed series of the snapshot; they are not listed twice.
        if (selector.table, selector.row) != (HOUSING_TABLE, HOUSING_ROW)
    )


def _bddk_weekly_series() -> tuple[ReviewedSeries, ...]:
    return tuple(
        ReviewedSeries(
            record=weekly_directory_catalog(selector),
            evidence_ids=(BDDK_WEEKLY_EVIDENCE_ID,),
            title_basis="documented_title",
            geography="Türkiye",
            note=DIRECTORY_NOTE,
        )
        for selector in supported_weekly_selectors()
    )


def _group_entry(group: ListedGroup) -> ReviewedSeries:
    calendar = FREQUENCIES.get(group.frequency_str)
    return ReviewedSeries(
        record=CatalogRecord(
            series_id=EVDS_GROUP_PREFIX + group.code,
            provider="EVDS",
            source_series_id=group.code,
            title=group.title,
            source=SourceRef(
                source_id="evds:directory-v1",
                source_type="repository_inventory",
                locator="repo:src/kkb_agent/ingest/evds_directory_listing.py",
                content_hash=EVDS_DIRECTORY_SHA256,
            ),
            description=(
                f"EVDS veri grubu (seri değil): {group.category}. "
                f"Birim: {group.unit_text or 'belirtilmemiş'}; sıklık: {group.frequency_str}; "
                f"kaynak: {group.data_source}. Serileri aramada açılır."
            ),
            labels=tuple(
                item for item in (group.title_eng, group.data_source, "veri grubu") if item
            ),
            group=SourceGroup(
                group_id=group.code, group_title=group.title, publisher=group.data_source or None
            ),
            status=CatalogStatus.ARCHIVED if group.archived else CatalogStatus.UNKNOWN,
            frequency=calendar[0] if calendar is not None else Frequency.UNKNOWN,
        ),
        evidence_ids=(evds_evidence().evidence_id,),
        title_basis="documented_title",
        note=GROUP_NOTE,
    )


@lru_cache(maxsize=1)
def _pinned() -> tuple[tuple[ReviewedSeries, ...], tuple[Evidence, ...]]:
    """The entries that come from pinned listings alone; built once per process."""
    bddk = Evidence(
        evidence_id=BDDK_EVIDENCE_ID,
        path="src/kkb_agent/ingest/bddk_monthly_directory.py",
        revision=hashlib.sha1(DIRECTORY_SHA256.encode(), usedforsecurity=False).hexdigest(),
        file_sha256=DIRECTORY_SHA256,
        section="BDDK monthly bulletin listing: tables, caption units, rows, reset behaviour.",
    )
    weekly = Evidence(
        evidence_id=BDDK_WEEKLY_EVIDENCE_ID,
        path="src/kkb_agent/ingest/bddk_weekly_directory.py",
        revision=hashlib.sha1(WEEKLY_DIRECTORY_SHA256.encode(), usedforsecurity=False).hexdigest(),
        file_sha256=WEEKLY_DIRECTORY_SHA256,
        section="BDDK weekly bulletin listing: tables, rows in page order, item ids, columns.",
    )
    groups = tuple(_group_entry(group) for group in listed_groups())
    return (
        (*_bddk_series(), *_bddk_weekly_series(), *groups),
        (bddk, weekly, evds_evidence()),
    )


def source_directory(supplement: Sequence[ListedGroup] = ()) -> SourceDirectory:
    """Every entry the pinned listings give, plus datagroups a refresh found after the pin.

    The series of an opened EVDS datagroup are deliberately not entries here: they arrive
    through `catalog.expansion` and `DiscoveredStore`. The catalogue a vector generation is
    built for therefore changes only when a listing is harvested again, never because a
    question opened a datagroup.
    """
    series, evidence = _pinned()
    known = {item.record.series_id for item in series}
    added = tuple(
        entry
        for entry in (_group_entry(group) for group in supplement)
        if entry.record.series_id not in known
    )
    # Without a supplement the digest is that of the pinned listings alone, so a refresh that
    # finds nothing new never asks for the vectors to be built again.
    state = json.dumps(
        {
            "bddk": DIRECTORY_SHA256,
            "bddk_weekly": WEEKLY_DIRECTORY_SHA256,
            "evds": EVDS_DIRECTORY_SHA256,
            **(
                {"supplement": sorted(f"{group.code}|{group.title}" for group in supplement)}
                if supplement
                else {}
            ),
        },
        sort_keys=True,
    )
    return SourceDirectory((*series, *added), evidence, hashlib.sha256(state.encode()).hexdigest())
