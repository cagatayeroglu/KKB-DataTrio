"""Narrow source-quotation eligibility; no analytical semantic exemption.

A tag alone proves nothing. Re-read the exact selected-cell snapshot and its
source edge from the same store before permitting the fixed literal sentence.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from kkb_agent.agent.presentation import format_number
from kkb_agent.core import AnalyticalResult, ClaimKind, ResultKind, ResultStatus, StockFlow
from kkb_agent.lakehouse.lineage import EdgeKind, Lineage, LineageError, NodeKind, node_id

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


def literal_text(result: AnalyticalResult) -> str | None:
    """Bounded display, not permission: verification still requires the store.

    Only unresolved literal results use this path. No document/model labels or
    IDs enter the sentence. Exact fixed prose excludes inferred interpretations.
    """
    if result.claim_kind is not ClaimKind.LITERAL_SOURCE_VALUE or len(result.values) != 1:
        return None
    value = result.values[0]
    if not value.semantics_are_unresolved:
        return None
    return (
        f"Kaynak hücredeki değer: {format_number(value.value)}. "
        "Kaynak birim veya ölçek belirtmiyor."
    )


def literal_proof(result: AnalyticalResult, connection: DuckDBPyConnection | None) -> bool:
    """Fail closed on missing, changed, transformed or merely source-cited data."""
    evidence = result.evidence
    if (
        connection is None
        or result.claim_kind is not ClaimKind.LITERAL_SOURCE_VALUE
        or result.kind is not ResultKind.LEVEL
        or result.status is not ResultStatus.COMPUTED
        or result.tool != "web_url"
        or result.method != "document_cell"
        or len(result.values) != 1
        or evidence is None
        or evidence.transformations
        or not evidence.lineage_node
        or len(evidence.input_refs) != 1
        or len(evidence.sources) != 1
    ):
        return False
    graph = Lineage(connection)
    try:
        cell = graph.node(evidence.lineage_node)
        parents = graph.parents(cell.node_id)
        if cell.kind is not NodeKind.TRANSFORM or cell.label != "web_url_cell" or len(parents) != 1:
            return False
        parent, edge = parents[0]
        source = graph.node(parent)
        if (
            edge is not EdgeKind.DERIVES_FROM
            or evidence.input_refs != [parent]
            or source.kind is not NodeKind.SOURCE_FILE
            or graph.parents(parent)
            or not source.attributes.get("content_hash")
            or cell.node_id != node_id(cell.kind, cell.label, cell.attributes, [parent])
            or source.node_id != node_id(source.kind, source.label, source.attributes)
        ):
            return False
        location = json.loads(cell.attributes["location"])
        if any(result.parameters.get(k) != v for k, v in location.items()):
            return False
        if {
            k
            for k in result.parameters
            if k in {"table", "row_index", "column_index", "page", "sheet"}
        } != set(location):
            return False
        for key in ("header", "row_label"):
            if result.parameters.get(key) != cell.attributes[key]:
                return False
        if (
            hashlib.sha256(str(result.parameters.get("cell_text")).encode()).hexdigest()
            != cell.attributes["cell_digest"]
        ):
            return False
        value = result.values[0]
        if (
            value.measure is not StockFlow.UNKNOWN
            or value.lag is not None
            or value.samples is not None
            or result.coverage is not None
            or result.samples is not None
            or set(result.parameters)
            != set(location) | {"header", "row_label", "cell_text", "unit_source", "period_source"}
        ):
            return False
        snapshot = {
            "value": value.value,
            "unit": value.unit,
            "scale": value.scale.value,
            "period": value.period.model_dump(mode="json") if value.period else None,
        }
        if snapshot != json.loads(cell.attributes["reading"]):
            return False
        fragment = evidence.sources[0]
        if (
            fragment.content_hash != source.attributes["content_hash"]
            or json.loads(fragment.source_id) != [source.label, location]
            or json.loads(fragment.locator) != [source.attributes["locator"], location]
        ):
            return False
        return result.result_id == f"web_url:{source.label}:{cell.attributes['location']}"
    except (LineageError, ValueError, KeyError, TypeError):
        return False


def exposes_literal_identity(text: str, results: list[AnalyticalResult]) -> bool:
    """Internal proof handles are not user-facing citations."""
    for result in results:
        if result.claim_kind is not ClaimKind.LITERAL_SOURCE_VALUE:
            continue
        evidence = result.evidence
        handles = [result.result_id]
        if evidence is not None:
            handles.extend(evidence.input_refs)
            handles.extend(evidence.evidence_ids)
            if evidence.lineage_node:
                handles.append(evidence.lineage_node)
        if any(handle and handle in text for handle in handles):
            return True
    return False
