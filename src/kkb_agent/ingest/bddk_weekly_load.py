"""Strict weekly-bulletin ingestion into the existing bronze/silver/lineage.

No planner registration, user URLs, free-form semantics or analytical results. Every window
is fetched and parsed before the short publication transaction; raw bronze may survive a
failed attempt, no partial silver dataset is published.

One series is read as the request dated today, which says which week is the latest
published one, the fixed thirteen-week windows that ended on or before that week, and,
when those two do not meet, one window ending just before today's answer begins. Each
stored week comes from exactly one answer.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Final, cast

from pydantic import JsonValue

from kkb_agent.core import SourceRef
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.bddk_weekly import expected_title, weekly_directory_catalog
from kkb_agent.ingest.bddk_weekly_request import (
    FIRST_WEEK,
    WEEKLY_ENDPOINT,
    WEEKLY_LIMITS,
    WEEKS_PER_ANSWER,
    WeeklyRequest,
    fetch_weekly,
    friday_of,
    grid_windows,
)
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchOutcome, FetchSuccess
from kkb_agent.lakehouse.lineage import EdgeKind, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics, check_period
from kkb_agent.lakehouse.store import Lakehouse

PARSER_VERSION: Final = "bddk-weekly-json-v1"
SEMANTIC_VERSION: Final = "bddk-weekly-listed-v1"
MANIFEST_VERSION: Final = "bddk-weekly-batch-v1"
TRANSFORMATION: Final = (
    "native-weekly;holiday-week-filed-under-its-friday;json-number-to-double;"
    "null-preserved;no-fill-or-rescale"
)
#: The source's latest week may trail the clock by its publication lag, never by this much:
#: an answer whose last week is older is an item the source stopped publishing, or another
#: answer than the one asked for.
MAX_LAG_DAYS: Final = 42
_KEYS: Final = frozenset({"Baslik", "XEkseni", "YEkseni"})
_DAY = re.compile(r"([0-9]{1,2})\.([0-9]{2})\.([0-9]{4})")


class WeeklyLoadCode(StrEnum):
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"


class WeeklyLoadError(ValueError):
    """Fixed diagnostics only, never remote text, numbers, body or headers."""

    def __init__(self, code: WeeklyLoadCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class WeeklyMaterialization:
    series_id: str
    manifest_id: str
    lineage_id: str
    weeks: int
    missing_values: int
    already_present: bool
    first_week: date
    last_week: date


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


def _invalid_json_constant(_value: str) -> JsonValue:
    raise ValueError("Non-JSON numeric constant")


def _number(value: JsonValue) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError("Expected JSON number or null")
    number = float(cast(int | float, value))
    if not math.isfinite(number):
        raise ValueError("Expected finite number")
    # Silver is DOUBLE. Do not silently round an integer not representable there.
    if isinstance(value, int) and number != value:
        raise ValueError("Integer cannot be represented as DOUBLE")
    return number


def _day(label: JsonValue) -> date:
    found = _DAY.fullmatch(label) if isinstance(label, str) else None
    if found is None:
        raise ValueError("Invalid week label")
    return date(int(found.group(3)), int(found.group(2)), int(found.group(1)))


def parse_weekly(payload: bytes, request: WeeklyRequest) -> tuple[Observation, ...]:
    """Validate the whole answer before any value is used: up to thirteen consecutive weeks.

    The title must be the listed item, column and side. A week is dated to a working day;
    a holiday week's Monday-to-Thursday date is filed under that week's Friday, a weekend
    date is refused. Weeks must follow one another without a gap or a repeat, and none may
    be dated after the day that was asked for. An answer without a week is refused: the
    source answers an id it does not know with an empty chart.
    """
    request = WeeklyRequest.model_validate(request)
    try:
        if not isinstance(payload, bytes) or len(payload) > WEEKLY_LIMITS.max_decompressed_bytes:
            raise ValueError("Response budget")
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_json_constant,
        )
        if not isinstance(root, dict) or set(root) != _KEYS:
            raise ValueError("Unexpected envelope")
        title, labels, values = root["Baslik"], root["XEkseni"], root["YEkseni"]
        if not isinstance(title, str) or " ".join(title.split()) != expected_title(
            request.selector
        ):
            raise ValueError("Another item, column or side than the one asked for")
        if (
            not isinstance(labels, list)
            or not isinstance(values, list)
            or not 1 <= len(labels) <= WEEKS_PER_ANSWER
            or len(values) != len(labels)
        ):
            raise ValueError("Not the weeks one answer carries")
        weeks: list[Observation] = []
        for label, raw in zip(labels, values, strict=True):
            day = _day(label)
            if day.weekday() > 4 or day > request.asked:
                raise ValueError("A week dated to a weekend or after the asked day")
            end = friday_of(day)
            if weeks and end != weeks[-1].period_end + timedelta(weeks=1):
                raise ValueError("Weeks do not follow one another")
            weeks.append(Observation(end - timedelta(days=6), end, _number(raw)))
        return tuple(weeks)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise WeeklyLoadError(WeeklyLoadCode.RESPONSE_INVALID) from None


def _semantics(selector: BddkSelector) -> SeriesSemantics:
    record = weekly_directory_catalog(selector)
    if record.unit is None:  # pragma: no cover - the listing declares one unit
        raise ValueError("Unresolved listed unit")
    semantics = SeriesSemantics(
        unit=record.unit,
        scale=record.scale,
        frequency=record.frequency,
        observation=record.stock_flow,
        cumulative=record.cumulative,
        aggregation=record.aggregation.default,
        anchor=record.weekly_anchor,
    )
    semantics.require_resolved()
    return semantics


def _rows(observations: tuple[Observation, ...]) -> list[tuple[date, date, float | None]]:
    return [(item.period_start, item.period_end, item.value) for item in observations]


def _retrieved(
    lake: Lakehouse, request: WeeklyRequest, retrieve: Callable[[WeeklyRequest], FetchOutcome]
) -> tuple[tuple[Observation, ...], dict[str, JsonValue]]:
    try:
        outcome = retrieve(request)
        if isinstance(outcome, FetchFailure):
            raise ValueError("Retrieval failed")
        outcome = FetchSuccess.model_validate(outcome)
        if (
            outcome.source_ref != request.fetch_request().source_ref
            or outcome.media_type != "application/json"
            or len(outcome.content) > WEEKLY_LIMITS.max_decompressed_bytes
            or outcome.effective_locator is not None
        ):
            raise ValueError("Unexpected retrieval result")
    except Exception:  # Trusted transport boundary: never expose provider exception text.
        raise WeeklyLoadError(WeeklyLoadCode.RETRIEVAL_FAILED) from None
    now = datetime.now(UTC)
    artifact = lake.record_artifact(
        outcome.content,
        source=SourceRef(
            source_id=request.fetch_request().source_ref,
            source_type="http-json",
            locator=WEEKLY_ENDPOINT,
            retrieved_at=now,
            content_hash=hashlib.sha256(outcome.content).hexdigest(),
        ),
        media_type=outcome.media_type,
        recorded_at=now,
    )
    # Also verify content on a repeat, rather than trusting only file size.
    weeks = parse_weekly(lake.read_artifact(artifact.artifact_id), request)
    return weeks, {
        "asked": request.asked.isoformat(),
        "artifact_id": artifact.artifact_id,
        "request": request.fingerprint(),
        "source_id": request.fetch_request().source_ref,
    }


def ingest_weekly(
    lake: Lakehouse,
    selector: BddkSelector,
    today: date,
    *,
    retrieve: Callable[[WeeklyRequest], FetchOutcome] = fetch_weekly,
) -> WeeklyMaterialization:
    """One validated dataset or explicit refusal; identical repeats are no-ops.

    `retrieve` and `today` are trusted application/test injection, never a serialized tool
    argument. The request dated `today` is read first: its last week is the latest the
    source has published, and must not trail `today` by more than `MAX_LAG_DAYS`. A fixed
    window that ended on or before that week is complete, so it must hold thirteen weeks
    ending exactly on its grid Friday. No retry or fallback here; one immutable batch per
    selector, as for the monthly bulletin.
    """
    selector = BddkSelector.model_validate(selector)
    catalog = weekly_directory_catalog(selector)
    semantics = _semantics(selector)
    tail, tail_source = _retrieved(lake, WeeklyRequest(selector=selector, asked=today), retrieve)
    if (today - tail[-1].period_end).days > MAX_LAG_DAYS:
        raise WeeklyLoadError(WeeklyLoadCode.RESPONSE_INVALID)
    kept: list[Observation] = []
    sources: list[JsonValue] = []

    def complete(end: date) -> None:
        weeks, source = _retrieved(lake, WeeklyRequest(selector=selector, asked=end), retrieve)
        if len(weeks) != WEEKS_PER_ANSWER or weeks[-1].period_end != end:
            # A window whose last week is published is complete, or is another answer.
            raise WeeklyLoadError(WeeklyLoadCode.RESPONSE_INVALID)
        kept.extend(item for item in weeks if not kept or item.period_end > kept[-1].period_end)
        sources.append(source)

    for end in grid_windows(tail[-1].period_end):
        complete(end)
    step = timedelta(weeks=1)
    if tail[0].period_end - step >= FIRST_WEEK and (
        not kept or tail[0].period_end > kept[-1].period_end + step
    ):
        # Today's answer is shorter than thirteen weeks whenever today is not a published
        # Friday, so it may begin after the last fixed window ended.
        complete(tail[0].period_end - step)
    kept.extend(item for item in tail if not kept or item.period_end > kept[-1].period_end)
    sources.append(tail_source)
    observations = tuple(week for week in kept if week.period_end >= FIRST_WEEK)
    try:
        for before, after in zip(observations, observations[1:], strict=False):
            if after.period_end != before.period_end + timedelta(weeks=1):
                raise ValueError("Windows do not join into consecutive weeks")
        for week in observations:
            check_period(semantics, week.period_start, week.period_end)
    except ValueError:
        raise WeeklyLoadError(WeeklyLoadCode.RESPONSE_INVALID) from None
    manifest: dict[str, JsonValue] = {
        "schema": MANIFEST_VERSION,
        "selector": selector.canonical_selector(),
        "start": observations[0].period_end.isoformat(),
        "end": observations[-1].period_end.isoformat(),
        "sources": sources,
        "parser": PARSER_VERSION,
        "semantics": SEMANTIC_VERSION,
        "transformation": TRANSFORMATION,
        "observations_sha256": hashlib.sha256(
            _canonical(
                [
                    [o.period_start.isoformat(), o.period_end.isoformat(), o.value]
                    for o in observations
                ]
            )
        ).hexdigest(),
    }
    payload = _canonical(manifest)
    manifest_id = hashlib.sha256(payload).hexdigest()
    lake.record_artifact(
        payload,
        source=SourceRef(
            source_id="internal:weekly:" + manifest_id,
            source_type="internal-dataset-manifest",
            locator="internal:bddk-weekly-batch-v1",
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
            "SELECT artifact_id FROM silver_series WHERE series_id = ?", [catalog.series_id]
        ).fetchone()
        if existing is not None and existing[0] != manifest_id:
            raise WeeklyLoadError(WeeklyLoadCode.VERSION_CONFLICT)
        lake.register_series(
            catalog.series_id, title=catalog.title, semantics=semantics, artifact_id=manifest_id
        )
        if existing is None:
            lake.append_observations(catalog.series_id, observations)
        else:
            stored = connection.execute(
                "SELECT period_start, period_end, value FROM silver_observations"
                " WHERE series_id = ? ORDER BY period_end",
                [catalog.series_id],
            ).fetchall()
            if stored != _rows(observations):
                raise WeeklyLoadError(WeeklyLoadCode.VERSION_CONFLICT)
        raw_nodes = [
            (
                lake.lineage.record(
                    NodeKind.SOURCE_FILE,
                    "BDDK Weekly response",
                    attributes={
                        **cast(dict[str, str], item),
                        "locator": WEEKLY_ENDPOINT,
                        "parser": PARSER_VERSION,
                    },
                ),
                EdgeKind.DERIVES_FROM,
            )
            for item in sources
        ]
        batch_node = lake.lineage.record(
            NodeKind.TRANSFORM,
            "Internal Weekly batch manifest",
            attributes={"artifact_id": manifest_id, "transformation": TRANSFORMATION},
            upstream=raw_nodes,
        )
        lineage_id = lake.lineage.record(
            NodeKind.SERIES,
            "Normalized Weekly observations",
            attributes={
                "series_id": catalog.series_id,
                "artifact_id": manifest_id,
                "parser": PARSER_VERSION,
            },
            upstream=[(batch_node, EdgeKind.DERIVES_FROM)],
        )
        connection.execute("COMMIT")
    except BaseException as error:
        connection.execute("ROLLBACK")
        if not isinstance(error, Exception):
            raise
        if isinstance(error, WeeklyLoadError):
            raise
        raise WeeklyLoadError(WeeklyLoadCode.MATERIALIZATION_FAILED) from None
    return WeeklyMaterialization(
        catalog.series_id,
        manifest_id,
        lineage_id,
        len(observations),
        sum(o.value is None for o in observations),
        existing is not None,
        observations[0].period_end,
        observations[-1].period_end,
    )
