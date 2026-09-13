"""Producer execution bindings in the existing content-addressed lineage store.

Only the four trusted tool implementations call the private writer, after
reading their inputs and computing their outputs. It is NOT a validator that
turns arbitrary AnalyticalResult objects into evidence. The verifier only reads.

Input snapshots contain the actual buffers passed to the computation (including
nulls and their source identities); invocation arguments bind any selection.
The result snapshot includes all semantics, parameters and identities. This
proves correspondence to trusted execution, not independent recomputation or
external source correctness. Python code/database writers are trusted; model
output can neither invoke this writer nor write lineage through restricted SQL.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING

import duckdb

from kkb_agent.core import AnalyticalResult, ClaimKind, ResultStatus
from kkb_agent.lakehouse.lineage import EdgeKind, Lineage, LineageError, NodeKind, node_id

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

PREFIX = "execution:"
EXECUTION_LABEL = "analytical_execution_v1"
INPUT_LABEL = "analytical_input_v1"
PRODUCERS = frozenset({"lakehouse", "change_detection", "anomaly", "causality"})


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("Unsupported execution snapshot value")


def canonical(value: object) -> str:
    """Exact, deterministic snapshot encoding; no display rounding or coercion."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    )


def _output(result: AnalyticalResult) -> str:
    # Exclude only the self-reference to avoid a circular content address. Do
    # not change AnalyticalResult.digest(), result identity or workspace names.
    payload = result.model_dump(mode="json")
    if payload["evidence"] is not None:
        payload["evidence"]["evidence_ids"] = []
    return canonical(payload)


def _invocation_id(producer: str, arguments: str, inputs: Sequence[str]) -> str:
    """Bind the result back to its inputs even when another event has equal outputs."""
    return "producer:" + node_id(
        NodeKind.METRIC,
        "analytical_invocation_v1",
        {"producer": producer, "arguments": arguments},
        inputs,
    )


def _record_execution(
    connection: DuckDBPyConnection,
    *,
    producer: str,
    arguments: str,
    inputs: Sequence[str],
    result: AnalyticalResult,
) -> AnalyticalResult:
    """Persistence primitive for trusted producers, never a public admission API.

    Snapshots MUST come from the producer's read/computation, never from a
    subsequent reread or arbitrary caller declarations. No output is returned
    if evidence storage fails. Input nodes left by a failure grant no trust.
    """
    if result.status is not ResultStatus.COMPUTED:
        return result
    if (
        producer not in PRODUCERS
        or not inputs
        or result.claim_kind is not ClaimKind.ANALYTICAL_VALUE
        or result.evidence is None
        or result.evidence.evidence_ids
        or result.run_id is not None
    ):
        raise ValueError("Invalid producer execution binding")
    evidence = result.evidence
    graph = Lineage(connection)
    parents = [
        graph.record(NodeKind.SERIES, INPUT_LABEL, attributes={"snapshot": snapshot})
        for snapshot in inputs
    ]
    result = result.model_copy(update={"run_id": _invocation_id(producer, arguments, parents)})
    reference = graph.record(
        NodeKind.METRIC,
        EXECUTION_LABEL,
        attributes={
            "producer": producer,
            "arguments": arguments,
            "inputs": canonical(parents),
            "output": _output(result),
        },
        upstream=[(parent, EdgeKind.DERIVES_FROM) for parent in parents],
    )
    return result.model_copy(
        update={"evidence": evidence.model_copy(update={"evidence_ids": [PREFIX + reference]})}
    )


def execution_proof(result: AnalyticalResult, connection: DuckDBPyConnection | None) -> bool:
    """Resolve exact producer/input/output evidence; missing or broken is false."""
    evidence = result.evidence
    if (
        connection is None
        or result.status is not ResultStatus.COMPUTED
        or result.claim_kind is not ClaimKind.ANALYTICAL_VALUE
        or evidence is None
        or len(evidence.evidence_ids) != 1
        or not evidence.evidence_ids[0].startswith(PREFIX)
    ):
        return False
    try:
        # Only committed execution evidence may authorize trusted publication.
        # The reader owns no caller transaction and commits/rolls back none.
        with connection.cursor() as reader:
            graph = Lineage(reader)
            record = graph.node(evidence.evidence_ids[0][len(PREFIX) :])
            attributes = record.attributes
            if (
                record.kind is not NodeKind.METRIC
                or record.label != EXECUTION_LABEL
                or set(attributes) != {"producer", "arguments", "inputs", "output"}
                or attributes["producer"] not in PRODUCERS
                or attributes["output"] != _output(result)
                or not isinstance(json.loads(attributes["arguments"]), dict)
            ):
                return False
            inputs = json.loads(attributes["inputs"])
            if (
                not isinstance(inputs, list)
                or not inputs
                or not all(isinstance(i, str) for i in inputs)
            ):
                return False
            if result.run_id != _invocation_id(
                attributes["producer"], attributes["arguments"], inputs
            ):
                return False
            parents = graph.parents(record.node_id)
            if set(parents) != {(parent, EdgeKind.DERIVES_FROM) for parent in inputs}:
                return False
            if record.node_id != node_id(record.kind, record.label, attributes, inputs):
                return False
            for parent in inputs:
                snapshot = graph.node(parent)
                if (
                    snapshot.kind is not NodeKind.SERIES
                    or snapshot.label != INPUT_LABEL
                    or set(snapshot.attributes) != {"snapshot"}
                    or not isinstance(json.loads(snapshot.attributes["snapshot"]), dict)
                    or graph.parents(parent)
                    or parent != node_id(snapshot.kind, snapshot.label, snapshot.attributes)
                ):
                    return False
            return True
    except (
        duckdb.Error,
        LineageError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
    ):
        return False
