"""EVDS series a catalogue search has listed, kept so they stay known (DEC-177).

EVDS lists about 680 datagroups and tens of thousands of series. The datagroups are pinned
in the repository and searched like any catalogue entry; a datagroup's series are listed by
the source on demand, one bounded read per datagroup, and that list is kept here under the
state root. Everything else is derived again on every use from the kept bytes by
`evds_directory.declare_series`, so a better derivation needs no migration and a kept list
is never trusted more than a fresh one.

What this adds to the catalogue a turn searches: every declared series of every datagroup a
search has opened. The agent "learns" a series the first time someone asks for something
near it, and the knowledge page can show what was learnt.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue

from kkb_agent.catalog.mappings import DIRECTORY_EVIDENCE_PREFIX, Evidence, ReviewedSeries
from kkb_agent.ingest.evds_directory import (
    SERIES_LIST_LIMITS,
    ListedGroup,
    declare_series,
    listed_groups,
    parse_series_list,
    series_list_request,
)
from kkb_agent.ingest.evds_directory_listing import DIRECTORY_SHA256
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, ReviewedEvdsSeries, catalog_record
from kkb_agent.ingest.safe_fetch import FetchOutcome, FetchRequest, FetchSuccess, safe_fetch

EVDS_EVIDENCE_ID = DIRECTORY_EVIDENCE_PREFIX + "evds"
EVDS_PREFIX = "EVDS:"
LISTED_NOTE = (
    "Listed by EVDS's own directory and fetched from it on first use. Unit, scale, frequency "
    "and aggregation come from the source's own fields; the entry was not reviewed one by one."
)


def evds_evidence() -> Evidence:
    import hashlib

    return Evidence(
        evidence_id=EVDS_EVIDENCE_ID,
        path="src/kkb_agent/ingest/evds_directory_listing.py",
        revision=hashlib.sha1(DIRECTORY_SHA256.encode(), usedforsecurity=False).hexdigest(),
        file_sha256=DIRECTORY_SHA256,
        section="EVDS datagroup directory; series lists are read per datagroup on demand.",
    )


def listed_entry(series: ReviewedEvdsSeries) -> ReviewedSeries:
    """The catalogue entry of a series declared from EVDS's own directory."""
    return ReviewedSeries(
        record=catalog_record(series),
        evidence_ids=(EVDS_EVIDENCE_ID,),
        title_basis="documented_title",
        note=LISTED_NOTE,
    )


class DiscoveredStore:
    """Series lists of the datagroups a search has opened, one JSON file per datagroup."""

    def __init__(
        self,
        directory: Path,
        *,
        fetch: Callable[[FetchRequest], FetchOutcome] | None = None,
    ) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._fetch = fetch or (lambda request: safe_fetch(request, limits=SERIES_LIST_LIMITS))
        self._groups = {group.code: group for group in listed_groups()}
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[ReviewedEvdsSeries, ...]] = {}

    def _path(self, group_code: str) -> Path:
        if group_code not in self._groups:
            raise ValueError("datagroup is not in the pinned EVDS directory")
        return self._directory / f"{group_code}.json"

    def group(self, group_code: str) -> ListedGroup | None:
        return self._groups.get(group_code)

    def series_of(self, group_code: str, *, read: bool = True) -> tuple[ReviewedEvdsSeries, ...]:
        """The declared series of one datagroup: kept list first, else one bounded read.

        A failed or malformed read yields nothing and keeps nothing; the next search asks
        again. Reviewed codes are left to the reviewed catalogue and never listed twice.
        """
        group = self._groups.get(group_code)
        if group is None:
            return ()
        with self._lock:
            if group_code in self._cache:
                return self._cache[group_code]
            path = self._path(group_code)
            rows: tuple[dict[str, JsonValue], ...] | None = None
            if path.is_file():
                try:
                    kept = json.loads(path.read_text(encoding="utf-8"))
                    rows, _ = parse_series_list(json.dumps(kept["rows"]).encode("utf-8"))
                except (ValueError, KeyError, TypeError, OSError):
                    rows = None
            if rows is None and read:
                outcome = self._fetch(series_list_request(group_code))
                if not isinstance(outcome, FetchSuccess):
                    return ()
                try:
                    rows, digest = parse_series_list(outcome.content)
                except (ValueError, UnicodeDecodeError):
                    return ()
                path.write_text(
                    json.dumps(
                        {
                            "fetched_at": datetime.now(UTC).isoformat(),
                            "sha256": digest,
                            "rows": list(rows),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            if rows is None:
                return ()
            declared = tuple(
                series
                for series in (declare_series(group, row) for row in rows)
                if series is not None and series.code not in REVIEWED_SERIES
            )
            self._cache[group_code] = declared
            return declared

    def opened_groups(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self._directory.glob("*.json")))

    def declared(self) -> tuple[ReviewedEvdsSeries, ...]:
        """Every declared series of every datagroup opened so far; never reads the source."""
        found: dict[str, ReviewedEvdsSeries] = {}
        for code in self.opened_groups():
            if code in self._groups:
                for series in self.series_of(code, read=False):
                    found.setdefault(series.code, series)
        return tuple(found[code] for code in sorted(found))

    def lookup(self, series_id: str) -> ReviewedEvdsSeries | None:
        """The declared series a catalogue id names, among the datagroups opened so far."""
        if not series_id.startswith(EVDS_PREFIX):
            return None
        code = series_id.removeprefix(EVDS_PREFIX)
        return next((series for series in self.declared() if series.code == code), None)

    def entry(self, series_id: str) -> ReviewedSeries | None:
        series = self.lookup(series_id)
        return listed_entry(series) if series is not None else None
