"""Fetching a reviewed official series the moment an analysis needs it (DEC-155, DEC-159).

The planner finds series in the reviewed catalog; the prepared pool holds only
some of them. A catalog candidate outside the pool used to end the turn with
"not prepared", although reviewed adapters already knew exactly how to fetch,
parse and store it. This module is the bridge, and it adds no authority those
adapters did not already have:

* Only an identity with a reviewed route reaches transport: `EVDS:<code>` for a
  code in `evds_series.REVIEWED_SERIES`, or a BDDK selector id whose selector is
  in the reviewed monthly housing scope. The model never supplies an endpoint, a
  code outside those registries, a window or a header.
* Windows are the operator's fixed policy, not the question's: silver keeps one
  immutable batch per series, so a window chosen per question would make the
  next question's fetch a version conflict.
* Every batch goes through the same strict loader as the offline operators
  (`ingest_series`, `ingest_monthly`) and then the prepared inspector checks the
  stored declaration against the catalog record. A fetch can make a series
  present; it cannot make it consistent.
* A turn has a small budget of acquisitions, and a refused or failed series is
  not retried within the turn.

What was fetched is kept (DEC-159): an `AcquisitionStore` under the state root
holds each successful raw response by its request fingerprint, so another
conversation, or the same one after a restart, rebuilds the series from those
bytes through the same parser instead of asking the source again, and the
knowledge base can show when each series was fetched. The windows end on the
clock's date, so a new day means a new window and one fresh fetch.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from kkb_agent.catalog.inspection import PreparedSeriesInspector, SeriesInspection
from kkb_agent.ingest.bddk_monthly import BddkSelector, MonthlyPeriod, supported_selectors
from kkb_agent.ingest.bddk_monthly_load import MonthlyLoadCode, MonthlyLoadError, ingest_monthly
from kkb_agent.ingest.bddk_monthly_request import MonthlyRange, MonthlyRequest, fetch_monthly
from kkb_agent.ingest.evds_load import EvdsLoadCode, EvdsLoadError, ingest_series
from kkb_agent.ingest.evds_request import EvdsRequest, EvdsWindow, fetch_series
from kkb_agent.ingest.evds_series import REVIEWED_SERIES
from kkb_agent.ingest.safe_fetch import FetchOutcome, FetchSuccess

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

    from kkb_agent.lakehouse.store import Lakehouse

EVDS_PREFIX: Final = "EVDS:"
#: Years of EVDS history one acquisition covers, ending at the clock's date.
WINDOW_YEARS: Final = 10
#: First month of BDDK bulletin an acquisition covers (one request per month): the start of
#: the period the product is prepared for (DEC-137), so a fetched series spans what the
#: prepared ones span. Two years (the first policy) answered "2021-2025" with half the years.
BDDK_FIRST_MONTH: Final = (2021, 1)
#: The request contract's own ceiling; the window never asks for more months than this.
BDDK_MAX_MONTHS: Final = 120
#: Months before the clock's month the BDDK window ends. The bulletin is published
#: with a lag; a month not yet published would fail the whole batch, never fill it.
BDDK_LAG_MONTHS: Final = 3
#: Acquisitions one turn may start. Each is live traffic to a public source.
MAX_ATTEMPTS_PER_TURN: Final = 3


class AcquisitionCode(StrEnum):
    ACQUIRED = "acquired"
    ALREADY_PRESENT = "already_present"
    NO_REVIEWED_ROUTE = "no_reviewed_route"
    BUDGET_EXHAUSTED = "budget_exhausted"
    RETRIEVAL_FAILED = "retrieval_failed"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class Acquisition:
    """What one attempt did; safe to show, never source text."""

    series_id: str
    code: AcquisitionCode
    observations: int = 0
    missing_values: int = 0
    window_start: date | None = None
    window_end: date | None = None
    detail: str = ""
    #: Rebuilt from bytes fetched earlier rather than asked of the source now.
    from_store: bool = False

    @property
    def stored(self) -> bool:
        return self.code in (AcquisitionCode.ACQUIRED, AcquisitionCode.ALREADY_PRESENT)


def acquisition_window(today: date, years: int = WINDOW_YEARS) -> EvdsWindow:
    """The operator's fixed EVDS window: `years` of history to the last whole month.

    EVDS refuses a monthly window that ends inside a month, so the window ends on
    the last month end on or before `today`, never on `today` itself.
    """
    following = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    month_end = date.fromordinal(following.toordinal() - 1)
    end = today if today == month_end else date.fromordinal(today.replace(day=1).toordinal() - 1)
    start = date(end.year - years, 1, 1)
    return EvdsWindow(start=max(start, date(2000, 1, 1)), end=end)


def bddk_window(today: date) -> MonthlyRange:
    """The operator's fixed BDDK window: `BDDK_FIRST_MONTH` to `BDDK_LAG_MONTHS` ago."""
    last = today.year * 12 + today.month - 1 - BDDK_LAG_MONTHS
    first = max(BDDK_FIRST_MONTH[0] * 12 + BDDK_FIRST_MONTH[1] - 1, last - BDDK_MAX_MONTHS + 1)
    first = min(first, last)  # a clock before the first month still asks for one month
    return MonthlyRange(
        start=MonthlyPeriod(year=first // 12, month=first % 12 + 1),
        end=MonthlyPeriod(year=last // 12, month=last % 12 + 1),
    )


def reviewed_code(series_id: str) -> str | None:
    """The EVDS registry code a catalog id names, or None when no reviewed route exists."""
    if not series_id.startswith(EVDS_PREFIX):
        return None
    code = series_id.removeprefix(EVDS_PREFIX)
    return code if code in REVIEWED_SERIES else None


def _housing(component: str) -> BddkSelector:
    return BddkSelector.model_validate(
        {
            "bulletin_family": "monthly",
            "table": 4,
            "row": 2,
            "bank_group": 10001,
            "presentation_currency": "TL",
            "value_dimension": component,
        }
    )


#: The reviewed monthly housing selectors, by the id the catalog uses for them.
REVIEWED_SELECTORS: Final = {
    selector.internal_id(): selector for selector in map(_housing, ("TP", "YP", "TOTAL"))
}


#: Every selector the monthly adapter accepts, by catalogue id: the reviewed housing rows
#: and the supported rows of the bulletin's own listing (DEC-176).
ROUTED_SELECTORS: Final = {selector.internal_id(): selector for selector in supported_selectors()}


def reviewed_selector(series_id: str) -> BddkSelector | None:
    """The monthly selector a catalogue id names, when the adapter accepts it."""
    return ROUTED_SELECTORS.get(series_id)


def has_reviewed_route(series_id: str) -> bool:
    return reviewed_code(series_id) is not None or reviewed_selector(series_id) is not None


class _Fingerprinted(Protocol):
    def fingerprint(self) -> str: ...

    def fetch_request(self) -> object: ...


class AcquisitionStore:
    """Raw official responses kept by request fingerprint, and a log of acquisitions.

    Only successful, bounded transport results are kept, exactly as received;
    parsing and validation happen again on every use, so a stored response is
    never trusted more than a fresh one.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, fingerprint: str) -> Path:
        if not fingerprint.isalnum() or len(fingerprint) > 128:
            raise ValueError("invalid fingerprint")
        return self._directory / f"{fingerprint}.json"

    def cached(
        self, retrieve: Callable[[_Fingerprinted], FetchOutcome], source: list[bool]
    ) -> Callable[[_Fingerprinted], FetchOutcome]:
        """`retrieve`, answering from kept responses; appends whether each call was live."""

        def wrapped(request: _Fingerprinted) -> FetchOutcome:
            # Kept by what was asked of the source, when the request can say so: one BDDK
            # table response serves every row and component read out of it.
            wire = getattr(request, "wire_fingerprint", None)
            path = self._path(wire() if callable(wire) else request.fingerprint())
            with self._lock:
                if path.is_file():
                    kept = json.loads(path.read_text(encoding="utf-8"))
                    source.append(False)
                    # The kept bytes answer this request: another row of the same BDDK table
                    # shares the wire response, and the loader checks the reply against the
                    # request it made, so the reply carries this request's own reference.
                    asked = getattr(request.fetch_request(), "source_ref", kept["source_ref"])
                    return FetchSuccess(
                        source_ref=asked,
                        content=bytes.fromhex(kept["content"]),
                        media_type=kept["media_type"],
                        http_status=kept["http_status"],
                    )
            outcome = retrieve(request)
            source.append(True)
            if isinstance(outcome, FetchSuccess) and outcome.effective_locator is None:
                with self._lock:
                    path.write_text(
                        json.dumps(
                            {
                                "source_ref": outcome.source_ref,
                                "media_type": outcome.media_type,
                                "http_status": outcome.http_status,
                                "content": outcome.content.hex(),
                            }
                        ),
                        encoding="utf-8",
                    )
            return outcome

        return wrapped

    def record(self, item: Acquisition) -> None:
        """Remember when a series was last fetched, for the knowledge base to show."""
        if not item.stored:
            return
        with self._lock:
            log = self._log()
            log[item.series_id] = {
                "fetched_at": datetime.now(UTC).isoformat(),
                "observations": item.observations,
                "window_start": item.window_start.isoformat() if item.window_start else None,
                "window_end": item.window_end.isoformat() if item.window_end else None,
            }
            (self._directory / "acquisitions.json").write_text(
                json.dumps(log, sort_keys=True), encoding="utf-8"
            )

    def _log(self) -> dict[str, dict[str, object]]:
        path = self._directory / "acquisitions.json"
        if not path.is_file():
            return {}
        found = json.loads(path.read_text(encoding="utf-8"))
        return found if isinstance(found, dict) else {}

    def acquisitions(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return self._log()


@dataclass(frozen=True, slots=True)
class OfficialSources:
    """Operator configuration: the reviewed transports and where fetched bytes are kept."""

    evds: Callable[[EvdsRequest], FetchOutcome] = fetch_series
    bddk: Callable[[MonthlyRequest], FetchOutcome] = fetch_monthly
    store: AcquisitionStore | None = None


@dataclass(slots=True)
class TurnAcquirer:
    """One turn's acquisitions into one session lakehouse.

    `sources` and `today` are trusted operator/test injection. `observe` receives
    every attempt so the turn's trace can show it.
    """

    lake: Lakehouse
    today: date
    sources: OfficialSources = field(default_factory=OfficialSources)
    observe: Callable[[Acquisition], object] | None = None
    budget: int = MAX_ATTEMPTS_PER_TURN
    attempts: list[Acquisition] = field(default_factory=list)

    def acquire(self, series_id: str) -> Acquisition:
        tried = next((item for item in self.attempts if item.series_id == series_id), None)
        if tried is not None:
            return tried  # One attempt per series per turn, whatever it returned.
        code, selector = reviewed_code(series_id), reviewed_selector(series_id)
        if code is None and selector is None:
            outcome = Acquisition(
                series_id,
                AcquisitionCode.NO_REVIEWED_ROUTE,
                detail="Only reviewed EVDS series and reviewed BDDK selectors can be fetched",
            )
        elif sum(1 for item in self.attempts if item.window_start is not None) >= self.budget:
            outcome = Acquisition(
                series_id,
                AcquisitionCode.BUDGET_EXHAUSTED,
                detail=f"This turn already started {self.budget} acquisitions",
            )
        else:
            try:
                outcome = (
                    self._evds(series_id, code)
                    if code is not None
                    else self._bddk(series_id, selector)  # type: ignore[arg-type]
                )
            except ValueError:
                # A window or request the reviewed contract refuses is a refusal, never
                # a crash in the middle of a turn.
                outcome = Acquisition(series_id, AcquisitionCode.REFUSED, detail="REQUEST_REFUSED")
        self.attempts.append(outcome)
        if self.sources.store is not None:
            self.sources.store.record(outcome)
        if self.observe is not None:
            self.observe(outcome)
        return outcome

    def _live(self) -> list[bool]:
        return []

    def _evds(self, series_id: str, code: str) -> Acquisition:
        window = acquisition_window(self.today)
        calls = self._live()
        retrieve = (
            self.sources.store.cached(self.sources.evds, calls)  # type: ignore[arg-type]
            if self.sources.store is not None
            else self.sources.evds
        )
        try:
            loaded = ingest_series(self.lake, code, window, retrieve=retrieve)
        except EvdsLoadError as error:
            return Acquisition(
                series_id,
                AcquisitionCode.RETRIEVAL_FAILED
                if error.code is EvdsLoadCode.RETRIEVAL_FAILED
                else AcquisitionCode.REFUSED,
                window_start=window.start,
                window_end=window.end,
                detail=error.code.value,
            )
        return Acquisition(
            series_id,
            AcquisitionCode.ALREADY_PRESENT if loaded.already_present else AcquisitionCode.ACQUIRED,
            observations=loaded.observations,
            missing_values=loaded.missing_values,
            window_start=window.start,
            window_end=window.end,
            from_store=bool(calls) and not any(calls),
        )

    def _bddk(self, series_id: str, selector: BddkSelector) -> Acquisition:
        window = bddk_window(self.today)
        periods = window.periods()
        start = date(periods[0].year, periods[0].month, 1)
        last = periods[-1]
        end_month = date(last.year + (last.month == 12), last.month % 12 + 1, 1)
        end = date.fromordinal(end_month.toordinal() - 1)
        calls = self._live()
        retrieve = (
            self.sources.store.cached(self.sources.bddk, calls)  # type: ignore[arg-type]
            if self.sources.store is not None
            else self.sources.bddk
        )
        try:
            loaded = ingest_monthly(self.lake, selector, window, retrieve=retrieve)
        except MonthlyLoadError as error:
            return Acquisition(
                series_id,
                AcquisitionCode.RETRIEVAL_FAILED
                if error.code is MonthlyLoadCode.RETRIEVAL_FAILED
                else AcquisitionCode.REFUSED,
                window_start=start,
                window_end=end,
                detail=error.code.value,
            )
        return Acquisition(
            series_id,
            AcquisitionCode.ALREADY_PRESENT if loaded.already_present else AcquisitionCode.ACQUIRED,
            observations=loaded.months,
            missing_values=loaded.missing_values,
            window_start=start,
            window_end=end,
            from_store=bool(calls) and not any(calls),
        )


class AcquiringInspector(PreparedSeriesInspector):
    """The prepared inspector, plus one fetch for a reviewed series not yet stored.

    It changes one thing: a `not_prepared` verdict for a series with a reviewed
    route triggers an acquisition, and the series is inspected again — by the
    same inspector, against the same catalog record. Every other verdict passes
    through unchanged, so an unresolved, archived or mismatched series is refused
    exactly as before.
    """

    def __init__(self, inner: PreparedSeriesInspector, acquirer: TurnAcquirer) -> None:
        # Deliberately not re-validating a snapshot: the inner inspector owns it.
        self._inner = inner
        self._acquirer = acquirer

    def inspect(self, connection: DuckDBPyConnection, series_id: str) -> SeriesInspection:
        found = self._inner.inspect(connection, series_id)
        if found.status != "not_prepared":
            return found
        if not self._acquirer.acquire(series_id).stored:
            return found
        return self._inner.inspect(connection, series_id)
