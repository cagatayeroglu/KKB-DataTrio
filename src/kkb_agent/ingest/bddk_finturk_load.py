"""Strict FinTürk ingestion into the existing bronze/silver/lineage.

No planner registration, user URLs, free-form semantics or analytical results. Every quarter
is fetched and parsed before the short publication transaction; raw bronze may survive a
failed attempt, no partial silver dataset is published.

The source answers a quarter it has not published with an error page, so the newest quarter
that has ended is asked for and left out when the source has no answer for it; any other
quarter that fails refuses the whole series.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Final, cast

from pydantic import JsonValue

from kkb_agent.core import SourceRef
from kkb_agent.ingest.bddk_finturk import (
    PROVINCES,
    finturk_directory_catalog,
    listed_finturk,
)
from kkb_agent.ingest.bddk_finturk_directory import DIRECTORY
from kkb_agent.ingest.bddk_finturk_request import (
    FINTURK_ENDPOINT,
    FINTURK_LIMITS,
    FinturkRequest,
    Quarter,
    fetch_finturk,
    newest_quarter,
    quarters_until,
)
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure, FetchOutcome, FetchSuccess
from kkb_agent.lakehouse.lineage import EdgeKind, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics, check_period
from kkb_agent.lakehouse.store import Lakehouse

PARSER_VERSION: Final = "bddk-finturk-json-v1"
SEMANTIC_VERSION: Final = "bddk-finturk-listed-v1"
MANIFEST_VERSION: Final = "bddk-finturk-batch-v1"
TRANSFORMATION: Final = "native-quarterly;json-number-to-double;null-preserved;no-fill-or-rescale"
IDENTITY_COLUMNS: Final = 5
MAX_ROWS: Final = 200
SIDE: Final = "SEKTÖR"


class FinturkLoadCode(StrEnum):
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"


class FinturkLoadError(ValueError):
    """Fixed diagnostics only, never remote text, numbers, body or headers."""

    def __init__(self, code: FinturkLoadCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class FinturkMaterialization:
    series_id: str
    manifest_id: str
    lineage_id: str
    quarters: int
    missing_values: int
    already_present: bool
    first_quarter: date
    last_quarter: date


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


def parse_finturk(payload: bytes, request: FinturkRequest) -> Observation:
    """Validate the whole table before one cell is used.

    The columns must be the listed ones in the listed order, every row must be the asked
    side and quarter with a province the listing knows, no province may appear twice, and
    the asked province must be there. A renamed or reordered column therefore fails closed
    instead of storing another measure under this identity.
    """
    request = FinturkRequest.model_validate(request)
    selector, column, province = listed_finturk(request.selector)
    listed = DIRECTORY["tables"][str(selector.table)]
    try:
        if not isinstance(payload, bytes) or len(payload) > FINTURK_LIMITS.max_decompressed_bytes:
            raise ValueError("Response budget")
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_json_constant,
        )
        if not isinstance(root, dict) or root.get("success") is not True:
            raise ValueError("Unsuccessful response")
        report = root["Json"]
        if not isinstance(report, dict):
            raise ValueError("Unexpected envelope")
        names = report["colNames"]
        if names != [*listed["identity"], *listed["columns"]]:
            raise ValueError("Another table, or its columns changed")
        rows = report["data"]["rows"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
            raise ValueError("Invalid rows")
        known = set(PROVINCES[selector.table].values())
        seen: set[str] = set()
        selected: list[JsonValue] | None = None
        for raw in rows:
            cell = raw["cell"] if isinstance(raw, dict) else None
            if not isinstance(cell, list) or len(cell) != len(names):
                raise ValueError("Invalid row shape")
            side, year, month, place, group = cell[:IDENTITY_COLUMNS]
            if (
                side != selector.bank_group
                or (year, month) != (request.quarter.year, request.quarter.month)
                or group != SIDE
                or not isinstance(place, str)
                or place not in known
                or place in seen
            ):
                raise ValueError("A row of another side, quarter or province")
            seen.add(place)
            if place == province:
                selected = cell
        if selected is None:
            raise ValueError("Missing selected province")
        end = request.quarter.end()
        return Observation(
            date(end.year, end.month - 2, 1),
            end,
            _number(selected[IDENTITY_COLUMNS + column.column - 1]),
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise FinturkLoadError(FinturkLoadCode.RESPONSE_INVALID) from None


def _semantics(selector: BddkSelector) -> SeriesSemantics:
    record = finturk_directory_catalog(selector)
    if record.unit is None:  # pragma: no cover - the listing declares every unit
        raise ValueError("Unresolved listed unit")
    semantics = SeriesSemantics(
        unit=record.unit,
        scale=record.scale,
        frequency=record.frequency,
        observation=record.stock_flow,
        cumulative=record.cumulative,
        aggregation=record.aggregation.default,
    )
    semantics.require_resolved()
    return semantics


def _rows(observations: tuple[Observation, ...]) -> list[tuple[date, date, float | None]]:
    return [(item.period_start, item.period_end, item.value) for item in observations]


def ingest_finturk(
    lake: Lakehouse,
    selector: BddkSelector,
    today: date,
    *,
    retrieve: Callable[[FinturkRequest], FetchOutcome] = fetch_finturk,
) -> FinturkMaterialization:
    """One validated dataset or explicit refusal; identical repeats are no-ops.

    `retrieve` and `today` are trusted application/test injection, never a serialized tool
    argument. One request a quarter from `FIRST_QUARTER`; no retry or fallback here; one
    immutable batch per selector, as for the bulletins.
    """
    selector, _, _ = listed_finturk(selector)
    catalog = finturk_directory_catalog(selector)
    semantics = _semantics(selector)
    newest = newest_quarter(today)
    parsed: list[Observation] = []
    sources: list[JsonValue] = []
    for quarter in quarters_until(newest):
        request = FinturkRequest(selector=selector, quarter=quarter)
        try:
            outcome = retrieve(request)
            if isinstance(outcome, FetchFailure):
                if quarter == newest and outcome.code is FetchCode.HTTP_FAILURE and parsed:
                    # The source answers an unpublished quarter with an error page.
                    break
                raise ValueError("Retrieval failed")
            outcome = FetchSuccess.model_validate(outcome)
            if (
                outcome.source_ref != request.fetch_request().source_ref
                or outcome.media_type != "application/json"
                or len(outcome.content) > FINTURK_LIMITS.max_decompressed_bytes
                or outcome.effective_locator is not None
            ):
                raise ValueError("Unexpected retrieval result")
        except Exception:  # Trusted transport boundary: never expose provider exception text.
            raise FinturkLoadError(FinturkLoadCode.RETRIEVAL_FAILED) from None
        now = datetime.now(UTC)
        artifact = lake.record_artifact(
            outcome.content,
            source=SourceRef(
                source_id=request.fetch_request().source_ref,
                source_type="http-json",
                locator=FINTURK_ENDPOINT,
                retrieved_at=now,
                content_hash=hashlib.sha256(outcome.content).hexdigest(),
            ),
            media_type=outcome.media_type,
            recorded_at=now,
        )
        observation = parse_finturk(lake.read_artifact(artifact.artifact_id), request)
        try:
            check_period(semantics, observation.period_start, observation.period_end)
        except ValueError:
            raise FinturkLoadError(FinturkLoadCode.RESPONSE_INVALID) from None
        parsed.append(observation)
        sources.append(
            {
                "quarter": quarter.key(),
                "artifact_id": artifact.artifact_id,
                "request": request.fingerprint(),
                "source_id": request.fetch_request().source_ref,
            }
        )
    observations = tuple(parsed)
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
            source_id="internal:finturk:" + manifest_id,
            source_type="internal-dataset-manifest",
            locator="internal:bddk-finturk-batch-v1",
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
            raise FinturkLoadError(FinturkLoadCode.VERSION_CONFLICT)
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
                raise FinturkLoadError(FinturkLoadCode.VERSION_CONFLICT)
        raw_nodes = [
            (
                lake.lineage.record(
                    NodeKind.SOURCE_FILE,
                    "BDDK FinTürk response",
                    attributes={
                        **cast(dict[str, str], item),
                        "locator": FINTURK_ENDPOINT,
                        "parser": PARSER_VERSION,
                    },
                ),
                EdgeKind.DERIVES_FROM,
            )
            for item in sources
        ]
        batch_node = lake.lineage.record(
            NodeKind.TRANSFORM,
            "Internal FinTürk batch manifest",
            attributes={"artifact_id": manifest_id, "transformation": TRANSFORMATION},
            upstream=raw_nodes,
        )
        lineage_id = lake.lineage.record(
            NodeKind.SERIES,
            "Normalized FinTürk observations",
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
        if isinstance(error, FinturkLoadError):
            raise
        raise FinturkLoadError(FinturkLoadCode.MATERIALIZATION_FAILED) from None
    return FinturkMaterialization(
        catalog.series_id,
        manifest_id,
        lineage_id,
        len(observations),
        sum(o.value is None for o in observations),
        existing is not None,
        observations[0].period_end,
        observations[-1].period_end,
    )


__all__ = [
    "FinturkLoadCode",
    "FinturkLoadError",
    "FinturkMaterialization",
    "Quarter",
    "ingest_finturk",
    "parse_finturk",
]
