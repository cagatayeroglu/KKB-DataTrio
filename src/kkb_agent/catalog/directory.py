"""What the official sources list themselves, as catalogue entries nobody reviewed (DEC-176).

The reviewed snapshot names the series a person checked one by one. It is a map of 37
places; the sources publish thousands. A question about anything else used to end in "not
found", although the adapters could fetch it, because nothing told the search that it
exists. This module turns a source's own pinned listing into catalogue entries of a second
tier:

* they are found by the same search, after the reviewed tier: a reviewed concept that
  matches a question still bounds the candidates to reviewed series;
* their declarations come only from the source's own fields (see each adapter), never from
  a model and never from a response read at question time;
* they are fetched on first use by the same adapters, through the same strict loaders, and
  the inspector checks the stored declaration against the entry exactly as for any series.

The model still never supplies a code, an address or a window. It can only name an identity
the catalogue search returned.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from kkb_agent.catalog.mappings import (
    DIRECTORY_EVIDENCE_PREFIX,
    Evidence,
    ReviewedSeries,
    is_listed_series,
)
from kkb_agent.ingest.bddk_monthly import (
    HOUSING_ROW,
    HOUSING_TABLE,
    monthly_directory_catalog,
    supported_selectors,
)
from kkb_agent.ingest.bddk_monthly_directory import DIRECTORY_SHA256

BDDK_EVIDENCE_ID: Final = DIRECTORY_EVIDENCE_PREFIX + "bddk-monthly"
DIRECTORY_NOTE: Final = (
    "Listed by the source's own directory and fetched from it on first use. Unit, scale, "
    "frequency and stock/flow come from the source's own fields and measured behaviour; "
    "the entry was not reviewed one by one."
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


@lru_cache(maxsize=1)
def source_directory() -> SourceDirectory:
    """Every listed series of every source with a directory; built once per process."""
    series = _bddk_series()
    evidence = (
        Evidence(
            evidence_id=BDDK_EVIDENCE_ID,
            path="src/kkb_agent/ingest/bddk_monthly_directory.py",
            revision=hashlib.sha1(DIRECTORY_SHA256.encode(), usedforsecurity=False).hexdigest(),
            file_sha256=DIRECTORY_SHA256,
            section="BDDK monthly bulletin listing: tables, caption units, rows, reset behaviour.",
        ),
    )
    state = json.dumps(
        {"bddk": DIRECTORY_SHA256, "series": sorted(item.record.series_id for item in series)},
        sort_keys=True,
    ).encode()
    return SourceDirectory(series, evidence, hashlib.sha256(state).hexdigest())
