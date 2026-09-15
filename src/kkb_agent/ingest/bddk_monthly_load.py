"""Reusable reviewed Monthly ingestion into existing bronze/silver/lineage.

No planner registration, user URLs, free-form semantics or analytical results.
Fetch/parse all months before the short trusted-publication transaction. Raw
bronze may survive a failed attempt; no partial silver dataset is published.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import cast

from pydantic import JsonValue

from kkb_agent.core import SourceRef
from kkb_agent.ingest.bddk_monthly import (
    BddkSelector,
    MonthlyHousingMetadata,
    reviewed_monthly_catalog,
    validate_reviewed_monthly_metadata,
)
from kkb_agent.ingest.bddk_monthly_request import (
    MONTHLY_ENDPOINT,
    MONTHLY_LIMITS,
    MonthlyRange,
    MonthlyRequest,
    fetch_monthly,
    period_key,
)
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchOutcome, FetchSuccess
from kkb_agent.lakehouse.lineage import EdgeKind, NodeKind, node_id
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics, check_period
from kkb_agent.lakehouse.store import Lakehouse

PARSER_VERSION = "bddk-monthly-json-v1"
SEMANTIC_VERSION = "bddk-monthly-reviewed-v1"
MANIFEST_VERSION = "bddk-monthly-batch-v1"
TRANSFORMATION = "native-monthly;json-number-to-double;null-preserved;no-fill-or-rescale"
MAX_ROWS = 10000
_DIMENSION_INDEX = {"TP": 4, "YP": 5, "TOTAL": 6}


class MonthlyLoadCode(StrEnum):
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"


class MonthlyLoadError(ValueError):
    """Fixed diagnostics only, never remote text, numbers, body or headers."""

    def __init__(self, code: MonthlyLoadCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class MonthlyMaterialization:
    series_id: str
    manifest_id: str
    lineage_id: str
    months: int
    missing_values: int
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


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("Expected object")
    return value


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


def parse_monthly(payload: bytes, request: MonthlyRequest) -> Observation:
    """Validate the full selected-row envelope before extracting any value.

    Unknown colModels fields/font hints/other labels are inert source data.
    All rows have the documented seven cells and unique (bank,row) identity.
    The selected row must also agree with the reviewed metadata, not just id.
    """
    request = MonthlyRequest.model_validate(request)
    try:
        if not isinstance(payload, bytes) or len(payload) > MONTHLY_LIMITS.max_decompressed_bytes:
            raise ValueError("Response budget")
        root = _object(
            json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_invalid_json_constant,
            )
        )
        if root.get("success") is not True:
            raise ValueError("Unsuccessful response")
        report = _object(root["Json"])
        data = _object(report["data"])
        # The documented complete-report envelope; no implicit pagination fetch.
        if data.get("page") != "1" or data.get("total") != "1":
            raise ValueError("Unsupported pagination")
        rows = data["rows"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
            raise ValueError("Invalid rows")
        selected: list[JsonValue] | None = None
        seen: set[tuple[str, int]] = set()
        for raw in rows:
            row = _object(raw)
            cell = row["cell"]
            if not isinstance(cell, list) or len(cell) != 7:
                raise ValueError("Invalid row shape")
            bank, number = cell[0], cell[1]
            if not isinstance(bank, str) or type(number) is not int:
                raise ValueError("Invalid row identity")
            if not 1 <= number <= 99999 or row.get("id") != str(number):
                raise ValueError("Inconsistent row id")
            if (bank, number) in seen:
                raise ValueError("Duplicate row")
            seen.add((bank, number))
            if number == request.selector.row:
                if selected is not None:
                    raise ValueError("Ambiguous selected row")
                selected = cell
        if selected is None:
            raise ValueError("Missing selected row")
        metadata = MonthlyHousingMetadata.model_validate(
            {
                "success": root["success"],
                "caption": report["caption"],
                "column_headers": report["colNames"],
                "row_number": selected[1],
                "row_label": selected[2],
                "bank_group_label": selected[0],
            }
        )
        validate_reviewed_monthly_metadata(
            request.selector, metadata, requested_period=request.period
        )
        period = request.period
        return Observation(
            date(period.year, period.month, 1),
            date(period.year, period.month, calendar.monthrange(period.year, period.month)[1]),
            _number(selected[_DIMENSION_INDEX[request.selector.value_dimension]]),
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise MonthlyLoadError(MonthlyLoadCode.RESPONSE_INVALID) from None


def _semantics(selector: BddkSelector) -> SeriesSemantics:
    record = reviewed_monthly_catalog(selector)
    if record.unit is None:
        raise ValueError("Unresolved reviewed unit")
    semantics = SeriesSemantics(
        unit=record.unit,
        scale=record.scale,
        frequency=record.frequency,
        observation=record.stock_flow,
        cumulative=record.cumulative,
    )
    semantics.require_resolved()
    return semantics


def _rows(observations: tuple[Observation, ...]) -> list[tuple[date, date, float | None]]:
    return [(item.period_start, item.period_end, item.value) for item in observations]


def _series_attributes(series_id: str, manifest_id: str) -> dict[str, str]:
    return {"series_id": series_id, "artifact_id": manifest_id, "parser": PARSER_VERSION}


def _manifest_lineage_attributes(manifest_id: str) -> dict[str, str]:
    return {"artifact_id": manifest_id, "transformation": TRANSFORMATION}


def _record_lineage(
    lake: Lakehouse, manifest: dict[str, JsonValue], manifest_id: str, series_id: str
) -> str:
    raw_nodes = []
    for item in cast(list[dict[str, str]], manifest["sources"]):
        identifier = lake.lineage.record(
            NodeKind.SOURCE_FILE,
            "BDDK Monthly response",
            attributes={**item, "locator": MONTHLY_ENDPOINT, "parser": PARSER_VERSION},
        )
        raw_nodes.append((identifier, EdgeKind.DERIVES_FROM))
    batch_node = lake.lineage.record(
        NodeKind.TRANSFORM,
        "Internal Monthly batch manifest",
        attributes=_manifest_lineage_attributes(manifest_id),
        upstream=raw_nodes,
    )
    return lake.lineage.record(
        NodeKind.SERIES,
        "Normalized Monthly observations",
        attributes=_series_attributes(series_id, manifest_id),
        upstream=[(batch_node, EdgeKind.DERIVES_FROM)],
    )


def ingest_monthly(
    lake: Lakehouse,
    selector: BddkSelector,
    window: MonthlyRange,
    *,
    retrieve: Callable[[MonthlyRequest], FetchOutcome] = fetch_monthly,
) -> MonthlyMaterialization:
    """One validated dataset or explicit refusal; identical repeats are no-ops.

    retrieve is trusted application/test injection, never a serialized tool arg.
    There is one request per month (at most 120), no retry or fallback. Each
    process has a 30-second whole-request deadline including DNS/connect; the
    batch therefore has at most 3600 seconds of network work, never a DB lock.
    Current silver permits one immutable batch per selector. A different range,
    response hash or parser/semantic contract needs explicit later version work.
    """
    selector = BddkSelector.model_validate(selector)
    window = MonthlyRange.model_validate(window)
    catalog = reviewed_monthly_catalog(selector)
    semantics = _semantics(selector)
    parsed = []
    sources: list[JsonValue] = []
    for period in window.periods():
        request = MonthlyRequest(selector=selector, period=period)
        try:
            outcome = retrieve(request)
            if isinstance(outcome, FetchFailure):
                raise ValueError("Retrieval failed")
            outcome = FetchSuccess.model_validate(outcome)
            if (
                outcome.source_ref != request.fetch_request().source_ref
                or outcome.media_type != "application/json"
                or len(outcome.content) > MONTHLY_LIMITS.max_decompressed_bytes
                or outcome.effective_locator is not None
            ):
                raise ValueError("Unexpected retrieval result")
        except Exception:  # Trusted transport boundary: never expose provider exception text.
            raise MonthlyLoadError(MonthlyLoadCode.RETRIEVAL_FAILED) from None
        now = datetime.now(UTC)
        artifact = lake.record_artifact(
            outcome.content,
            source=SourceRef(
                source_id=request.fetch_request().source_ref,
                source_type="http-json",
                locator=MONTHLY_ENDPOINT,
                retrieved_at=now,
                content_hash=hashlib.sha256(outcome.content).hexdigest(),
            ),
            media_type=outcome.media_type,
            recorded_at=now,
        )
        # Also verify content on a repeat, rather than trusting only file size.
        observation = parse_monthly(lake.read_artifact(artifact.artifact_id), request)
        check_period(semantics, observation.period_start, observation.period_end)
        parsed.append(observation)
        sources.append(
            {
                "period": period_key(period),
                "artifact_id": artifact.artifact_id,
                "request": request.fingerprint(),
                "source_id": request.fetch_request().source_ref,
            }
        )
    observations = tuple(parsed)
    manifest: dict[str, JsonValue] = {
        "schema": MANIFEST_VERSION,
        "selector": selector.canonical_selector(),
        "start": period_key(window.start),
        "end": period_key(window.end),
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
            source_id="internal:monthly:" + manifest_id,
            source_type="internal-dataset-manifest",
            locator="internal:bddk-monthly-batch-v1",
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
            raise MonthlyLoadError(MonthlyLoadCode.VERSION_CONFLICT)
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
                raise MonthlyLoadError(MonthlyLoadCode.VERSION_CONFLICT)
        lineage_id = _record_lineage(lake, manifest, manifest_id, catalog.series_id)
        connection.execute("COMMIT")
    except BaseException as error:
        connection.execute("ROLLBACK")
        if not isinstance(error, Exception):
            raise
        if isinstance(error, MonthlyLoadError):
            raise
        raise MonthlyLoadError(MonthlyLoadCode.MATERIALIZATION_FAILED) from None
    return MonthlyMaterialization(
        catalog.series_id,
        manifest_id,
        lineage_id,
        len(observations),
        sum(o.value is None for o in observations),
        existing is not None,
    )


def materialized_monthly(
    lake: Lakehouse, selector: BddkSelector, window: MonthlyRange
) -> MonthlyMaterialization | None:
    """Offline exact-window check, not a general availability or quality claim.

    Revalidate source bytes against the current contract and compare stored
    observations. Nulls are counted explicitly; materialized does not mean all
    values are present. No network, filling, catalog promotion or writes.
    """
    selector = BddkSelector.model_validate(selector)
    window = MonthlyRange.model_validate(window)
    catalog = reviewed_monthly_catalog(selector)
    row = lake.connection.execute(
        "SELECT artifact_id FROM silver_series WHERE series_id = ?", [catalog.series_id]
    ).fetchone()
    if row is None:
        return None
    try:
        manifest_id = str(row[0])
        manifest = _object(json.loads(lake.read_artifact(manifest_id)))
        if any(
            manifest.get(k) != v
            for k, v in {
                "schema": MANIFEST_VERSION,
                "selector": selector.canonical_selector(),
                "start": period_key(window.start),
                "end": period_key(window.end),
                "parser": PARSER_VERSION,
                "semantics": SEMANTIC_VERSION,
                "transformation": TRANSFORMATION,
            }.items()
        ):
            return None
        sources = manifest["sources"]
        periods = window.periods()
        if not isinstance(sources, list) or len(sources) != len(periods):
            return None
        observations = []
        raw_ids = []
        for raw, period in zip(sources, periods, strict=True):
            item = _object(raw)
            request = MonthlyRequest(selector=selector, period=period)
            if (
                item.get("period") != period_key(period)
                or item.get("request") != request.fingerprint()
                or item.get("source_id") != request.fetch_request().source_ref
                or not isinstance(item.get("artifact_id"), str)
            ):
                return None
            observations.append(
                parse_monthly(lake.read_artifact(str(item["artifact_id"])), request)
            )
            raw_ids.append(
                node_id(
                    NodeKind.SOURCE_FILE,
                    "BDDK Monthly response",
                    {
                        **cast(dict[str, str], item),
                        "locator": MONTHLY_ENDPOINT,
                        "parser": PARSER_VERSION,
                    },
                )
            )
        batch_id = node_id(
            NodeKind.TRANSFORM,
            "Internal Monthly batch manifest",
            _manifest_lineage_attributes(manifest_id),
            raw_ids,
        )
        series_node = node_id(
            NodeKind.SERIES,
            "Normalized Monthly observations",
            _series_attributes(catalog.series_id, manifest_id),
            [batch_id],
        )
        if (
            not lake.lineage.exists(series_node)
            or {node.node_id for node in lake.lineage.sources_of(series_node)} != set(raw_ids)
            or lake.semantics_of(catalog.series_id) != _semantics(selector)
        ):
            return None
        expected_hash = hashlib.sha256(
            _canonical(
                [
                    [o.period_start.isoformat(), o.period_end.isoformat(), o.value]
                    for o in observations
                ]
            )
        ).hexdigest()
        stored = lake.connection.execute(
            "SELECT period_start, period_end, value FROM silver_observations"
            " WHERE series_id = ? ORDER BY period_end",
            [catalog.series_id],
        ).fetchall()
        if (
            stored != _rows(tuple(observations))
            or manifest.get("observations_sha256") != expected_hash
        ):
            return None
        return MonthlyMaterialization(
            catalog.series_id,
            manifest_id,
            series_node,
            len(observations),
            sum(o.value is None for o in observations),
            True,
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        return None
