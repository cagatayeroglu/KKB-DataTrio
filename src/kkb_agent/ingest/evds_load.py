"""M3-08 bounded EVDS ingestion into existing bronze/silver/lineage.

One `fe` request covers the whole window for one reviewed series. The response
is parsed strictly before a short trusted-publication transaction. Raw bronze may
survive a failed attempt; no partial silver dataset is published.

Measured source behaviour this parser relies on (2026-09-14): `Tarih` is
`YYYY-MM` for monthly and `DD-MM-YYYY` for weekly series under the fixed date
format; `UNIXTIME` is local midnight at an offset that varies (UTC+1 until
2021-03, UTC+3 later), so neither field is trusted alone — the label date must
equal the UNIXTIME date at UTC+3. A weekly request also returns the week whose
Friday falls after the window end; periods ending outside the window are
excluded and counted in the manifest, never silently kept.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from enum import StrEnum

from pydantic import JsonValue

from kkb_agent.core import Frequency, SourceRef
from kkb_agent.ingest.evds_request import (
    EVDS_LIMITS,
    FE_ENDPOINT,
    EvdsRequest,
    EvdsWindow,
    fetch_series,
)
from kkb_agent.ingest.evds_series import ReviewedEvdsSeries, reviewed_series, series_semantics
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchOutcome, FetchSuccess
from kkb_agent.lakehouse.lineage import EdgeKind, NodeKind, node_id
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import check_period, period_bounds
from kkb_agent.lakehouse.store import Lakehouse

PARSER_VERSION = "evds-fe-json-v1"
SEMANTIC_VERSION = "evds-reviewed-v1"
MANIFEST_VERSION = "evds-fe-batch-v1"
TRANSFORMATION = (
    "native-frequency;decimal-string-to-double;label-date-equals-unixtime-utc+3;"
    "period-end-inside-window;null-preserved;no-fill-or-rescale"
)
MAX_ITEMS = 5000
_SOURCE_DAY = timezone(timedelta(hours=3))
_VALUE = re.compile(r"^-?(0|[1-9][0-9]{0,14})(\.[0-9]{1,8})?$")
_UNIXTIME = re.compile(r"^[0-9]{9,11}$")
_YEARWEEK = re.compile(r"^[0-9]{4}-[0-9]{1,2}$")
# Presentation copies and an undocumented conversion flag are inert; anything else fails.
_ROOT_KEYS = {
    "totalCount",
    "items",
    "transposedItems",
    "transposedColumns",
    "seriesNames",
    "frequencyConversion",
}


class EvdsLoadCode(StrEnum):
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"


class EvdsLoadError(ValueError):
    """Fixed diagnostics only, never remote text, numbers, body or headers."""

    def __init__(self, code: EvdsLoadCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ParsedSeries:
    observations: tuple[Observation, ...]
    excluded_outside_window: int


@dataclass(frozen=True, slots=True)
class EvdsMaterialization:
    series_id: str
    manifest_id: str
    lineage_id: str
    observations: int
    missing_values: int
    excluded_outside_window: int
    already_present: bool


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> JsonValue:
    raise ValueError("Non-JSON numeric constant")


def _label_date(series: ReviewedEvdsSeries, label: JsonValue) -> date:
    if not isinstance(label, str):
        raise ValueError("Invalid date label")
    if series.frequency is Frequency.MONTHLY:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", label):
            raise ValueError("Invalid monthly label")
        return date(int(label[:4]), int(label[5:]), 1)
    if not re.fullmatch(r"[0-9]{2}-[0-9]{2}-[0-9]{4}", label):
        raise ValueError("Invalid weekly label")
    return date(int(label[6:]), int(label[3:5]), int(label[:2]))


def _value(raw: JsonValue) -> float | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not _VALUE.fullmatch(raw):
        raise ValueError("Invalid observation value")
    return float(raw)


def _period(series: ReviewedEvdsSeries, label: date) -> tuple[date, date]:
    if series.frequency is Frequency.MONTHLY:
        end = (label.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return period_bounds(Frequency.MONTHLY, end)
    return period_bounds(Frequency.WEEKLY, label, anchor=series.anchor)


def expected_period_ends(series: ReviewedEvdsSeries, window: EvdsWindow) -> tuple[date, ...]:
    """Generated from the calendar alone, never from the rows a response supplies."""
    window = EvdsWindow.model_validate(window)
    ends: list[date] = []
    if series.frequency is Frequency.MONTHLY:
        cursor = window.start.replace(day=1)
        while True:
            _, end = _period(series, cursor)
            if end > window.end:
                break
            if end >= window.start:
                ends.append(end)
            cursor = end + timedelta(days=1)
        return tuple(ends)
    if series.anchor is None:  # pragma: no cover - the reviewed registry forbids it.
        raise ValueError("Weekly series without an anchor")
    cursor = window.start + timedelta(days=(series.anchor.weekday - window.start.weekday()) % 7)
    while cursor <= window.end:
        ends.append(cursor)
        cursor += timedelta(days=7)
    return tuple(ends)


def parse_fe(payload: bytes, request: EvdsRequest) -> ParsedSeries:
    """Validate the whole envelope and every row before any value is used.

    Rows must carry exactly the reviewed keys: a server formula column (`F-1`),
    another series or an unknown field is refused rather than ignored. Values are
    dot-decimal strings or null; group separators, commas and JSON numbers fail.
    The kept periods must equal the independently generated calendar exactly.
    """
    request = EvdsRequest.model_validate(request)
    series = reviewed_series(request.code)
    try:
        if not isinstance(payload, bytes) or len(payload) > EVDS_LIMITS.max_decompressed_bytes:
            raise ValueError("Response budget")
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
        if not isinstance(root, dict) or not {"totalCount", "items"} <= set(root):
            raise ValueError("Invalid envelope")
        if not set(root) <= _ROOT_KEYS:
            raise ValueError("Unknown envelope field")
        items, total = root["items"], root["totalCount"]
        if not isinstance(items, list) or type(total) is not int or total != len(items):
            raise ValueError("Inconsistent item count")
        if len(items) > MAX_ITEMS:
            raise ValueError("Too many items")
        keys = {"Tarih", "UNIXTIME", series.response_key}
        if series.frequency is Frequency.WEEKLY:
            keys.add("YEARWEEK")
        kept: list[Observation] = []
        excluded = 0
        previous: date | None = None
        for raw in items:
            if not isinstance(raw, dict) or set(raw) != keys:
                raise ValueError("Unexpected row fields")
            label = _label_date(series, raw["Tarih"])
            stamp = raw["UNIXTIME"]
            if not isinstance(stamp, dict) or set(stamp) != {"$numberLong"}:
                raise ValueError("Invalid UNIXTIME")
            seconds = stamp["$numberLong"]
            if not isinstance(seconds, str) or not _UNIXTIME.fullmatch(seconds):
                raise ValueError("Invalid UNIXTIME")
            if datetime.fromtimestamp(int(seconds), _SOURCE_DAY).date() != label:
                raise ValueError("Label and UNIXTIME disagree")
            if "YEARWEEK" in raw and (
                not isinstance(raw["YEARWEEK"], str) or not _YEARWEEK.fullmatch(raw["YEARWEEK"])
            ):
                raise ValueError("Invalid YEARWEEK")
            if previous is not None and label <= previous:
                raise ValueError("Rows are not strictly increasing")
            previous = label
            start, end = _period(series, label)
            value = _value(raw[series.response_key])
            if not request.window.start <= end <= request.window.end:
                excluded += 1
                continue
            kept.append(Observation(start, end, value))
        if tuple(o.period_end for o in kept) != expected_period_ends(series, request.window):
            raise ValueError("Periods differ from the requested calendar")
        return ParsedSeries(tuple(kept), excluded)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, OSError):
        raise EvdsLoadError(EvdsLoadCode.RESPONSE_INVALID) from None


def _rows(observations: tuple[Observation, ...]) -> list[tuple[date, date, float | None]]:
    return [(o.period_start, o.period_end, o.value) for o in observations]


def _observations_sha256(observations: tuple[Observation, ...]) -> str:
    return hashlib.sha256(
        _canonical(
            [[o.period_start.isoformat(), o.period_end.isoformat(), o.value] for o in observations]
        )
    ).hexdigest()


def _manifest_nodes(
    manifest_id: str, raw_attributes: dict[str, str], series_id: str
) -> tuple[tuple[NodeKind, str, dict[str, str]], ...]:
    return (
        (NodeKind.SOURCE_FILE, "EVDS fe response", raw_attributes),
        (
            NodeKind.TRANSFORM,
            "Internal EVDS batch manifest",
            {"artifact_id": manifest_id, "transformation": TRANSFORMATION},
        ),
        (
            NodeKind.SERIES,
            "Normalized EVDS observations",
            {"series_id": series_id, "artifact_id": manifest_id, "parser": PARSER_VERSION},
        ),
    )


def _raw_attributes(request: EvdsRequest, artifact_id: str) -> dict[str, str]:
    return {
        "artifact_id": artifact_id,
        "request": request.fingerprint(),
        "source_id": request.fetch_request().source_ref,
        "locator": FE_ENDPOINT,
        "parser": PARSER_VERSION,
    }


def ingest_series(
    lake: Lakehouse,
    code: str,
    window: EvdsWindow,
    *,
    retrieve: Callable[[EvdsRequest], FetchOutcome] = fetch_series,
) -> EvdsMaterialization:
    """One validated dataset or explicit refusal; identical repeats are no-ops.

    retrieve is trusted application/test injection, never a serialized tool arg.
    Current silver permits one immutable batch per series. A different window,
    response hash or parser/semantic contract returns VERSION_CONFLICT.
    """
    request = EvdsRequest(code=code, window=EvdsWindow.model_validate(window))
    series = request.series
    semantics = series_semantics(series)
    try:
        outcome = retrieve(request)
        if isinstance(outcome, FetchFailure):
            raise ValueError("Retrieval failed")
        outcome = FetchSuccess.model_validate(outcome)
        if (
            outcome.source_ref != request.fetch_request().source_ref
            or outcome.media_type != "application/json"
            or len(outcome.content) > EVDS_LIMITS.max_decompressed_bytes
            or outcome.effective_locator is not None
        ):
            raise ValueError("Unexpected retrieval result")
    except Exception:  # Trusted transport boundary: never expose provider exception text.
        raise EvdsLoadError(EvdsLoadCode.RETRIEVAL_FAILED) from None
    now = datetime.now(UTC)
    artifact = lake.record_artifact(
        outcome.content,
        source=SourceRef(
            source_id=request.fetch_request().source_ref,
            source_type="http-json",
            locator=FE_ENDPOINT,
            retrieved_at=now,
            content_hash=hashlib.sha256(outcome.content).hexdigest(),
        ),
        media_type=outcome.media_type,
        recorded_at=now,
    )
    # Parse what bronze holds, so a repeat also verifies stored content.
    parsed = parse_fe(lake.read_artifact(artifact.artifact_id), request)
    for observation in parsed.observations:
        check_period(semantics, observation.period_start, observation.period_end)
    manifest: dict[str, JsonValue] = {
        "schema": MANIFEST_VERSION,
        "series": series.code,
        "start": request.window.start.isoformat(),
        "end": request.window.end.isoformat(),
        "request": request.fingerprint(),
        "raw_artifact_id": artifact.artifact_id,
        "excluded_outside_window": parsed.excluded_outside_window,
        "parser": PARSER_VERSION,
        "semantics": SEMANTIC_VERSION,
        "transformation": TRANSFORMATION,
        "observations_sha256": _observations_sha256(parsed.observations),
    }
    payload = _canonical(manifest)
    manifest_id = hashlib.sha256(payload).hexdigest()
    lake.record_artifact(
        payload,
        source=SourceRef(
            source_id="internal:evds:" + manifest_id,
            source_type="internal-dataset-manifest",
            locator="internal:" + MANIFEST_VERSION,
            content_hash=manifest_id,
        ),
        media_type="application/json",
        recorded_at=datetime.now(UTC),
    )
    lake.read_artifact(manifest_id)
    connection = lake.connection
    # BEGIN outside try: never roll back a transaction owned by another caller.
    connection.execute("BEGIN TRANSACTION")
    try:
        existing = connection.execute(
            "SELECT artifact_id FROM silver_series WHERE series_id = ?", [series.series_id]
        ).fetchone()
        if existing is not None and existing[0] != manifest_id:
            raise EvdsLoadError(EvdsLoadCode.VERSION_CONFLICT)
        lake.register_series(
            series.series_id, title=series.title, semantics=semantics, artifact_id=manifest_id
        )
        if existing is None:
            lake.append_observations(series.series_id, parsed.observations)
        else:
            stored = connection.execute(
                "SELECT period_start, period_end, value FROM silver_observations"
                " WHERE series_id = ? ORDER BY period_end",
                [series.series_id],
            ).fetchall()
            if stored != _rows(parsed.observations):
                raise EvdsLoadError(EvdsLoadCode.VERSION_CONFLICT)
        upstream: list[tuple[str, EdgeKind]] = []
        lineage_id = ""
        for kind, label, attributes in _manifest_nodes(
            manifest_id, _raw_attributes(request, artifact.artifact_id), series.series_id
        ):
            lineage_id = lake.lineage.record(
                kind, label, attributes=attributes, upstream=list(upstream)
            )
            upstream = [(lineage_id, EdgeKind.DERIVES_FROM)]
        connection.execute("COMMIT")
    except BaseException as error:
        connection.execute("ROLLBACK")
        if not isinstance(error, Exception):
            raise
        if isinstance(error, EvdsLoadError):
            raise
        raise EvdsLoadError(EvdsLoadCode.MATERIALIZATION_FAILED) from None
    return EvdsMaterialization(
        series.series_id,
        manifest_id,
        lineage_id,
        len(parsed.observations),
        sum(o.value is None for o in parsed.observations),
        parsed.excluded_outside_window,
        existing is not None,
    )


def materialized_series(
    lake: Lakehouse, code: str, window: EvdsWindow
) -> EvdsMaterialization | None:
    """Offline exact-window check, not a general availability or quality claim.

    Reparse the raw artifact under the current contract, recompute the manifest
    and compare stored semantics, observations and lineage. No network or writes.
    """
    request = EvdsRequest(code=code, window=EvdsWindow.model_validate(window))
    series = request.series
    row = lake.connection.execute(
        "SELECT artifact_id FROM silver_series WHERE series_id = ?", [series.series_id]
    ).fetchone()
    if row is None:
        return None
    try:
        manifest_id = str(row[0])
        manifest = json.loads(lake.read_artifact(manifest_id))
        if not isinstance(manifest, dict):
            return None
        raw_id = manifest.get("raw_artifact_id")
        if not isinstance(raw_id, str):
            return None
        parsed = parse_fe(lake.read_artifact(raw_id), request)
        expected: dict[str, JsonValue] = {
            "schema": MANIFEST_VERSION,
            "series": series.code,
            "start": request.window.start.isoformat(),
            "end": request.window.end.isoformat(),
            "request": request.fingerprint(),
            "raw_artifact_id": raw_id,
            "excluded_outside_window": parsed.excluded_outside_window,
            "parser": PARSER_VERSION,
            "semantics": SEMANTIC_VERSION,
            "transformation": TRANSFORMATION,
            "observations_sha256": _observations_sha256(parsed.observations),
        }
        if hashlib.sha256(_canonical(expected)).hexdigest() != manifest_id:
            return None
        upstream: list[str] = []
        identifiers: list[str] = []
        for kind, label, attributes in _manifest_nodes(
            manifest_id, _raw_attributes(request, raw_id), series.series_id
        ):
            identifiers.append(node_id(kind, label, attributes, upstream))
            upstream = [identifiers[-1]]
        stored = lake.connection.execute(
            "SELECT period_start, period_end, value FROM silver_observations"
            " WHERE series_id = ? ORDER BY period_end",
            [series.series_id],
        ).fetchall()
        if (
            not lake.lineage.exists(identifiers[-1])
            or {n.node_id for n in lake.lineage.sources_of(identifiers[-1])} != {identifiers[0]}
            or lake.semantics_of(series.series_id) != series_semantics(series)
            or stored != _rows(parsed.observations)
        ):
            return None
        return EvdsMaterialization(
            series.series_id,
            manifest_id,
            identifiers[-1],
            len(parsed.observations),
            sum(o.value is None for o in parsed.observations),
            parsed.excluded_outside_window,
            True,
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        return None
