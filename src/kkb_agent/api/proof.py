"""Bounded result-level proof chain read from one session's own lakehouse (M10-08).

The chain starts only at an execution record the verifier's own check accepts
(`execution_proof`), then follows the input snapshots that record binds, nested
published results, and the recorded lineage from each prepared series back to its
raw source responses. Every database read has a row limit. Nothing here reruns a
numeric matcher, grants verification, or serializes locators, request bodies,
SQL, tool arguments or observation values. Recorded coverage is not correctness.

A literal document cell (DEC-132) has no producer execution; its chain starts at
the gate's own exact-cell check (`literal_proof`) and names only fixed facts about
the fetched document, never its address path, sheet name or cell text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

import duckdb
from pydantic import ValidationError

from kkb_agent.agent.literal import literal_proof
from kkb_agent.api.contracts import (
    MAX_PROOF_DOCUMENTS,
    MAX_PROOF_SOURCES,
    MAX_PROOF_STEPS,
    MAX_STEP_INPUTS,
    Proof,
    ProofDocument,
    ProofGap,
    ProofInput,
    ProofSource,
    ProofStep,
    unavailable_proof,
)
from kkb_agent.api.projection import safe_text
from kkb_agent.core import AnalyticalResult, ClaimKind
from kkb_agent.ingestion_policy import MIME_TYPES
from kkb_agent.lakehouse.lineage import Lineage, LineageError, NodeKind
from kkb_agent.lakehouse.result_evidence import PREFIX, execution_proof
from kkb_agent.tools._document_column import SNAPSHOT_KIND as DOCUMENT_COLUMN
from kkb_agent.tools._document_table import SNAPSHOT_KIND as DOCUMENT_TABLE

MAX_RAW_RESPONSES = 512
MAX_SOURCE_DEPTH = 3
MAX_UPSTREAM_TRANSFORMS = 4
RECEIPT = "prepared_series_inspection_v1"
PROJECTION = "silver_projection"
_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:;+-]{0,119}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_PUBLICATION = re.compile(r"analiz_[1-9][0-9]{0,2}\Z")
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST = re.compile(rf"{_LABEL}(?:\.{_LABEL})+\Z")
_SEMANTICS = ("scale", "frequency", "measure", "cumulative", "aggregation")
_DOCUMENT_FORMATS = {media_type: kind.value for kind, media_type in MIME_TYPES.items()}

Binding = Literal["execution_snapshot", "series_record"]


def _code(value: object) -> str | None:
    return value if isinstance(value, str) and _CODE.fullmatch(value) else None


def _host(locator: object) -> str | None:
    """An https hostname only; credentials, odd ports or syntax drop the host."""
    if not isinstance(locator, str) or len(locator) > 2048:
        return None
    try:
        parts = urlsplit(locator)
        host = parts.hostname
        if parts.scheme != "https" or parts.username or parts.password or host is None:
            return None
        _ = parts.port  # Raises ValueError for an invalid port.
    except ValueError:
        return None
    if len(host) > 240 or not _HOST.fullmatch(host) or host.rsplit(".", 1)[-1].isdigit():
        return None  # Also drops literal IPv4 addresses; IPv6 never matches.
    return host


def _date(value: object) -> date | None:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


@dataclass
class _Observed:
    """What one execution snapshot recorded about a series it read."""

    artifact: str
    unit: object = None
    semantics: dict[str, object] = field(default_factory=dict)
    observations: int | None = None
    missing: int | None = None
    first: date | None = None
    last: date | None = None


@dataclass
class _Builder:
    connection: duckdb.DuckDBPyConnection
    secrets: tuple[str, ...]
    steps: list[ProofStep] = field(default_factory=list)
    sources: list[ProofSource] = field(default_factory=list)
    documents: list[ProofDocument] = field(default_factory=list)
    source_index: dict[tuple[str, str, Binding], int] = field(default_factory=dict)
    step_index: dict[str, int] = field(default_factory=dict)
    gaps: list[ProofGap] = field(default_factory=list)

    def text(self, value: object, limit: int = 240) -> str | None:
        if not isinstance(value, str):
            return None
        return safe_text(value[:limit], limit=limit, secrets=self.secrets).strip() or None

    def gap(self, code: ProofGap) -> None:
        if code not in self.gaps:
            self.gaps.append(code)

    def step(self, result: AnalyticalResult, workspace_name: str | None) -> int | None:
        """Record a verified execution step; None when it cannot be recorded."""
        version = result.digest()
        if version in self.step_index:
            return self.step_index[version]
        if len(self.steps) >= MAX_PROOF_STEPS:
            self.gap("step_limit")
            return None
        if not execution_proof(result, self.connection) or result.evidence is None:
            return None
        graph = Lineage(self.connection)
        record = graph.node(result.evidence.evidence_ids[0][len(PREFIX) :])
        nodes = json.loads(record.attributes["inputs"])
        operation = None
        if result.evidence.lineage_node is not None:
            try:
                transform = graph.node(result.evidence.lineage_node)
                if transform.kind is NodeKind.TRANSFORM:
                    operation = _code(transform.label)
            except LineageError:
                operation = None
        index = len(self.steps)
        self.step_index[version] = index
        self.steps.append(
            ProofStep(
                producer=record.attributes["producer"],
                operation=operation,
                kind=result.kind,
                method=_code(result.method),
                execution="verified",
                result_version=version,
                workspace_name=workspace_name,
                coverage=result.coverage,
                samples=result.samples,
                inputs=(),
            )
        )
        if len(nodes) > MAX_STEP_INPUTS:
            self.gap("input_not_recognized")
        snapshots = [self._snapshot(graph, node) for node in nodes[:MAX_STEP_INPUTS]]
        # Receipts only annotate series a data snapshot already named, so read them last.
        ordered = [s for s in snapshots if s is not None and s.get("kind") != RECEIPT]
        ordered += [s for s in snapshots if s is not None and s.get("kind") == RECEIPT]
        inputs: list[ProofInput] = []
        for snapshot in ordered:
            for item in self._inputs(snapshot):
                if item not in inputs and len(inputs) < MAX_STEP_INPUTS:
                    inputs.append(item)
        self.steps[index] = self.steps[index].model_copy(update={"inputs": tuple(inputs)})
        return index

    def _snapshot(self, graph: Lineage, node: object) -> dict[str, Any] | None:
        try:
            snapshot = json.loads(graph.node(str(node)).attributes["snapshot"])
        except (LineageError, KeyError, ValueError):
            snapshot = None
        if not isinstance(snapshot, dict):
            self.gap("input_not_recognized")
            return None
        return snapshot

    def _inputs(self, snapshot: dict[str, Any]) -> list[ProofInput]:
        if "result" in snapshot:
            return self._nested(snapshot)
        if snapshot.get("kind") == PROJECTION:
            return self._projection(snapshot.get("rows"))
        if snapshot.get("kind") in (DOCUMENT_COLUMN, DOCUMENT_TABLE):
            return self._document_column(snapshot)
        series_id = snapshot.get("series_id")
        if isinstance(series_id, str) and 1 <= len(series_id) <= 200:
            if snapshot.get("kind") == RECEIPT:
                return self._receipt(series_id, snapshot)
            if "observations" in snapshot:
                return self._series(series_id, snapshot)
        self.gap("input_not_recognized")
        return []

    def document(self, document: ProofDocument) -> list[ProofInput]:
        if document in self.documents:
            return [ProofInput(kind="document", index=self.documents.index(document))]
        if len(self.documents) >= MAX_PROOF_DOCUMENTS:
            self.gap("source_limit")
            return []
        self.documents.append(document)
        return [ProofInput(kind="document", index=len(self.documents) - 1)]

    def _document_column(self, snapshot: dict[str, Any]) -> list[ProofInput]:
        """A column or table an execution read from a document; fixed facts only."""
        table = snapshot.get("kind") == DOCUMENT_TABLE
        columns = snapshot.get("columns")
        rows: object = snapshot.get("rows")
        if table and isinstance(columns, list) and all(isinstance(c, dict) for c in columns):
            rows = [cell for column in columns for cell in column.get("cells") or ()]
        location = snapshot.get("location")
        content_hash, media_type = snapshot.get("content_hash"), snapshot.get("media_type")
        if not (
            isinstance(location, dict)
            and isinstance(rows, list)
            and isinstance(content_hash, str)
            and isinstance(media_type, str)
            and media_type in _DOCUMENT_FORMATS
            and all(isinstance(row, list) and len(row) == 3 for row in rows)
        ):
            self.gap("input_not_recognized")
            return []
        try:
            document = ProofDocument.model_validate(
                {
                    "source_type": snapshot.get("source_type"),
                    "document_format": _DOCUMENT_FORMATS[media_type],
                    "host": _host(snapshot.get("locator")),
                    "content_sha256": content_hash.removeprefix("sha256:"),
                    "retrieved_at": snapshot.get("retrieved_at"),
                    "page": location.get("page"),
                    "table": location.get("table"),
                    "row": None,
                    "column": None if table else location.get("column_index"),
                    "sheet_selected": "sheet" in location,
                    "values_read": sum(1 for row in rows if row[1] is not None),
                }
            )
        except ValidationError:
            self.gap("input_not_recognized")
            return []
        return self.document(document)

    def _nested(self, snapshot: dict[str, Any]) -> list[ProofInput]:
        try:
            nested = AnalyticalResult.model_validate(snapshot["result"])
        except ValidationError:
            self.gap("input_not_recognized")
            return []
        name = snapshot.get("workspace")
        workspace_name = name if isinstance(name, str) and _PUBLICATION.fullmatch(name) else None
        before = len(self.gaps)
        index = self.step(nested, workspace_name)
        if index is None:
            if len(self.gaps) == before:
                self.gap("input_result_not_verified")
            return []
        return [ProofInput(kind="result", index=index)]

    def _series(self, series_id: str, snapshot: dict[str, Any]) -> list[ProofInput]:
        artifact, rows = snapshot.get("artifact_id"), snapshot.get("observations")
        columns, values = snapshot.get("semantic_columns"), snapshot.get("semantics")
        if not (
            isinstance(artifact, str)
            and isinstance(rows, list)
            and isinstance(columns, list)
            and isinstance(values, list)
            and len(columns) == len(values)
            and all(isinstance(row, list) and len(row) == 3 for row in rows)
        ):
            self.gap("input_not_recognized")
            return []
        declared = dict(zip(columns, values, strict=True))
        declared["measure"] = declared.get("observation")
        starts = [d for row in rows if (d := _date(row[0])) is not None]
        ends = [d for row in rows if (d := _date(row[1])) is not None]
        observed = _Observed(
            artifact,
            unit=declared.get("unit"),
            semantics=declared,
            observations=len(rows),
            missing=sum(1 for row in rows if row[2] is None),
            first=min(starts, default=None),
            last=max(ends, default=None),
        )
        status = None
        inspection = snapshot.get("catalog_inspection")
        if isinstance(inspection, str):
            try:
                status = _code(json.loads(inspection).get("catalog_status"))
            except (ValueError, AttributeError):
                status = None
        return self._source(series_id, "execution_snapshot", observed, status)

    def _projection(self, rows: object) -> list[ProofInput]:
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            self.gap("input_not_recognized")
            return []
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            series_id, artifact = row.get("series_id"), row.get("artifact_id")
            if not isinstance(series_id, str) or not isinstance(artifact, str):
                self.gap("input_not_recognized")
                return []
            groups.setdefault((series_id, artifact), []).append(row)
        inputs: list[ProofInput] = []
        for (series_id, artifact), group in groups.items():
            first = group[0]
            starts = [d for row in group if (d := _date(row.get("period_start"))) is not None]
            ends = [d for row in group if (d := _date(row.get("period_end"))) is not None]
            observed = _Observed(
                artifact,
                unit=first.get("unit"),
                semantics={
                    "scale": first.get("scale"),
                    "frequency": first.get("frequency"),
                    "measure": first.get("observation"),
                },
                observations=len(group),
                missing=sum(1 for row in group if row.get("value") is None),
                first=min(starts, default=None),
                last=max(ends, default=None),
            )
            inputs += self._source(series_id, "execution_snapshot", observed, None)
        return inputs

    def _receipt(self, series_id: str, receipt: dict[str, Any]) -> list[ProofInput]:
        status = _code(receipt.get("catalog_status"))
        for (sid, _artifact, _binding), index in self.source_index.items():
            if sid == series_id:
                if self.sources[index].catalog_status is None and status is not None:
                    self.sources[index] = self.sources[index].model_copy(
                        update={"catalog_status": status}
                    )
                return [ProofInput(kind="series", index=index)]
        row = self.connection.execute(
            "SELECT artifact_id, unit, scale, frequency, observation, cumulative, aggregation"
            " FROM silver_series WHERE series_id = ? LIMIT 1",
            [series_id],
        ).fetchone()
        if row is None:
            self.gap("dataset_record_missing")
            return []
        observed = _Observed(
            str(row[0]),
            unit=row[1],
            semantics=dict(zip(_SEMANTICS, row[2:], strict=True)),
        )
        return self._source(series_id, "series_record", observed, status)

    def _source(
        self, series_id: str, binding: Binding, observed: _Observed, status: str | None
    ) -> list[ProofInput]:
        key = (series_id, observed.artifact, binding)
        if key in self.source_index:
            return [ProofInput(kind="series", index=self.source_index[key])]
        if len(self.sources) >= MAX_PROOF_SOURCES:
            self.gap("source_limit")
            return []
        title = self.connection.execute(
            "SELECT title FROM silver_series WHERE series_id = ? LIMIT 1", [series_id]
        ).fetchone()
        dataset = self.connection.execute(
            "SELECT source_type FROM bronze_artifacts WHERE artifact_id = ? LIMIT 1",
            [observed.artifact],
        ).fetchone()
        if dataset is None:
            self.gap("dataset_record_missing")
        label = self.text(series_id)
        if label is None:
            self.gap("input_not_recognized")
            return []
        source = ProofSource.model_validate(
            {
                "series_id": label,
                "title": self.text(title[0]) if title else None,
                "binding": binding,
                "dataset_sha256": (
                    observed.artifact if _DIGEST.fullmatch(observed.artifact) else None
                ),
                "dataset_source_type": _code(dataset[0]) if dataset else None,
                "unit": self.text(observed.unit),
                "catalog_status": status,
                "observations": observed.observations,
                "missing_values": observed.missing,
                "first_period": observed.first,
                "last_period": observed.last,
                **{name: _code(observed.semantics.get(name)) for name in _SEMANTICS},
                **self._origin(series_id, observed.artifact),
            }
        )
        self.source_index[key] = len(self.sources)
        self.sources.append(source)
        return [ProofInput(kind="series", index=len(self.sources) - 1)]

    def _origin(self, series_id: str, artifact: str) -> dict[str, Any]:
        """Series lineage node -> bounded upstream transforms -> raw source_file responses."""
        origin: dict[str, Any] = {
            "parser": None,
            "normalization": None,
            "raw_responses": 0,
            "raw_response_types": (),
            "hosts": (),
            "first_retrieved": None,
            "last_retrieved": None,
        }
        rows = self.connection.execute(
            "SELECT node_id, attributes FROM lineage_nodes WHERE kind = 'series'"
            " AND json_extract_string(attributes, '$.series_id') = ?"
            " AND json_extract_string(attributes, '$.artifact_id') = ?"
            " ORDER BY node_id LIMIT 2",
            [series_id, artifact],
        ).fetchall()
        if len(rows) != 1:
            self.gap("source_lineage_missing")
            return origin
        origin["parser"] = _code(json.loads(rows[0][1]).get("parser"))
        frontier, seen = [str(rows[0][0])], {str(rows[0][0])}
        responses: set[str] = set()
        limit = MAX_RAW_RESPONSES + MAX_UPSTREAM_TRANSFORMS + 1
        for _depth in range(MAX_SOURCE_DEPTH):
            if not frontier:
                break
            upstream = self.connection.execute(
                "SELECT n.node_id, n.kind, n.attributes FROM lineage_edges e"
                " JOIN lineage_nodes n ON n.node_id = e.upstream_id"
                " WHERE list_contains(?, e.downstream_id)"
                " ORDER BY n.kind, n.node_id LIMIT ?",
                [frontier, limit],
            ).fetchall()
            if len(upstream) >= limit:
                self.gap("raw_response_limit")
            frontier = []
            for node, kind, attributes in upstream:
                if node in seen:
                    continue
                seen.add(node)
                values = json.loads(attributes)
                if kind == NodeKind.SOURCE_FILE.value:
                    if isinstance(values.get("artifact_id"), str):
                        responses.add(values["artifact_id"])
                elif kind == NodeKind.TRANSFORM.value:
                    if len(frontier) >= MAX_UPSTREAM_TRANSFORMS:
                        self.gap("raw_response_limit")
                        continue
                    frontier.append(str(node))
                    if origin["normalization"] is None:
                        origin["normalization"] = self.text(values.get("transformation"))
        if frontier:
            self.gap("raw_response_limit")
        if not responses:
            self.gap("source_lineage_missing")
            return origin
        if len(responses) > MAX_RAW_RESPONSES:
            self.gap("raw_response_limit")
        artifacts = sorted(responses)[:MAX_RAW_RESPONSES]
        records = self.connection.execute(
            "SELECT source_type, locator, retrieved_at FROM bronze_artifacts"
            " WHERE list_contains(?, artifact_id) LIMIT ?",
            [artifacts, MAX_RAW_RESPONSES],
        ).fetchall()
        if len(records) != len(artifacts):
            self.gap("dataset_record_missing")
        retrieved = [row[2] for row in records if isinstance(row[2], datetime)]
        origin.update(
            raw_responses=len(records),
            raw_response_types=tuple(sorted({c for r in records if (c := _code(r[0]))})[:4]),
            hosts=tuple(sorted({h for r in records if (h := _host(r[1]))})[:4]),
            first_retrieved=min(retrieved, default=None),
            last_retrieved=max(retrieved, default=None),
        )
        return origin


def build_proof(
    connection: duckdb.DuckDBPyConnection,
    published: AnalyticalResult,
    *,
    secrets: tuple[str, ...] = (),
) -> Proof:
    """Read-only; any storage/shape failure yields unavailable, never a fabricated chain."""
    try:
        with connection.cursor() as reader:
            builder = _Builder(reader, secrets)

            if published.claim_kind is ClaimKind.LITERAL_SOURCE_VALUE:
                document = _document(reader, published)
                if document is None:
                    return unavailable_proof("execution_not_verified")
                builder.documents.append(document)
                builder.steps.append(
                    ProofStep(
                        producer="web_url",
                        operation=None,
                        kind=published.kind,
                        method=_code(published.method),
                        execution="verified",
                        result_version=published.digest(),
                        workspace_name=None,
                        coverage=published.coverage,
                        samples=published.samples,
                        inputs=(ProofInput(kind="document", index=0),),
                    )
                )
            elif builder.step(published, None) != 0:
                return unavailable_proof("execution_not_verified")

            def texts(items: list[str]) -> tuple[str, ...]:
                return tuple(t for item in items[:16] if (t := builder.text(item, 2048)))

            return Proof(
                availability="partial" if builder.gaps else "available",
                steps=tuple(builder.steps),
                sources=tuple(builder.sources),
                documents=tuple(builder.documents),
                warnings=texts(published.warnings),
                limitations=texts(published.limitations),
                unresolved_semantics=texts(published.unresolved_semantics),
                gaps=tuple(builder.gaps[:8]),
            )
    except (
        duckdb.Error,
        LineageError,
        ValidationError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        return unavailable_proof("proof_unreadable")


def _document(
    connection: duckdb.DuckDBPyConnection, published: AnalyticalResult
) -> ProofDocument | None:
    """Fixed facts about a verified literal cell's document; None when the cell fails.

    The same check the answer gate applied re-reads the cell snapshot, its single
    source edge, content hash and location first. The retrieval time is the one
    recorded in the published, digest-bound result.
    """
    evidence = published.evidence
    if not literal_proof(published, connection) or evidence is None or not evidence.lineage_node:
        return None
    graph = Lineage(connection)
    cell = graph.node(evidence.lineage_node)
    source = graph.node(evidence.input_refs[0])
    location = json.loads(cell.attributes["location"])
    # Validated rather than trusted: an unexpected source type or format refuses.
    return ProofDocument.model_validate(
        {
            "source_type": source.attributes["source_type"],
            "document_format": _DOCUMENT_FORMATS[source.attributes["media_type"]],
            "host": _host(source.attributes["locator"]),
            "content_sha256": source.attributes["content_hash"].removeprefix("sha256:"),
            "retrieved_at": evidence.sources[0].retrieved_at,
            "page": location.get("page"),
            "table": location.get("table"),
            "row": location["row_index"],
            "column": location["column_index"],
            "sheet_selected": "sheet" in location,
        }
    )
