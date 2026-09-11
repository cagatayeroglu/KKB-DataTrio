"""The lineage graph (M12-14, DEC-118).

Provenance is a typed graph rather than a set of notes, because "where did this
number come from" then has an answer a machine can produce and a reader can
check. Node kinds run `SourceFile -> Series -> Transform -> Column -> Metric ->
Claim`, and every numeric claim carries an id whose ancestors are exactly the
evidence panel.

Node ids are **content-addressed**: the same transformation over the same inputs
is the same node, so replaying a pipeline does not duplicate the graph, and two
nodes with the same id are the same derivation by construction. A cell without
lineage is a defect, not a missing feature.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cost only
    from duckdb import DuckDBPyConnection

LINEAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS lineage_nodes (
    node_id     TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    attributes  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lineage_edges (
    upstream_id    TEXT NOT NULL,
    downstream_id  TEXT NOT NULL,
    kind           TEXT NOT NULL,
    PRIMARY KEY (upstream_id, downstream_id, kind)
);
"""


class NodeKind(StrEnum):
    SOURCE_FILE = "source_file"
    SERIES = "series"
    TRANSFORM = "transform"
    COLUMN = "column"
    METRIC = "metric"
    CLAIM = "claim"


class EdgeKind(StrEnum):
    DERIVES_FROM = "derives_from"
    AGGREGATES = "aggregates"
    DEFLATES_BY = "deflates_by"
    CITES = "cites"


class LineageError(ValueError):
    """The graph refused an operation that would make provenance unreadable."""


@dataclass(frozen=True, slots=True)
class LineageNode:
    node_id: str
    kind: NodeKind
    label: str
    attributes: Mapping[str, str] = field(default_factory=dict)


def node_id(
    kind: NodeKind, label: str, attributes: Mapping[str, str], upstream: Sequence[str] = ()
) -> str:
    """Deterministic id over what the node *is* and what it was derived from.

    Sorting keys and upstream ids makes the id independent of insertion order,
    so the same derivation reached by two code paths lands on one node.
    """
    payload = json.dumps(
        {
            "kind": kind.value,
            "label": label,
            "attributes": dict(sorted(attributes.items())),
            "upstream": sorted(upstream),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Lineage:
    """Reader and writer over the lineage tables of one lakehouse connection."""

    connection: DuckDBPyConnection

    def record(
        self,
        kind: NodeKind,
        label: str,
        *,
        attributes: Mapping[str, str] | None = None,
        upstream: Sequence[tuple[str, EdgeKind]] = (),
    ) -> str:
        """Add a node and its inbound edges, returning the node's id.

        Recording the same node twice is a no-op rather than an error, because a
        pipeline that runs again should converge on the same graph. Every
        upstream id must already exist: an edge to nothing is worse than no
        edge, since it looks like provenance and leads nowhere.
        """
        if not label.strip():
            raise LineageError("A lineage node needs a label")
        attributes = dict(attributes or {})
        upstream_ids = [identifier for identifier, _ in upstream]
        for identifier in upstream_ids:
            if not self.exists(identifier):
                raise LineageError(f"Upstream node {identifier[:12]} does not exist")

        identifier = node_id(kind, label, attributes, upstream_ids)
        if not self.exists(identifier):
            self.connection.execute(
                "INSERT INTO lineage_nodes VALUES (?, ?, ?, ?)",
                [
                    identifier,
                    kind.value,
                    label,
                    json.dumps(attributes, ensure_ascii=False, sort_keys=True),
                ],
            )
        for upstream_id, edge_kind in upstream:
            self.connection.execute(
                "INSERT OR IGNORE INTO lineage_edges VALUES (?, ?, ?)",
                [upstream_id, identifier, edge_kind.value],
            )
        return identifier

    def exists(self, identifier: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM lineage_nodes WHERE node_id = ?", [identifier]
            ).fetchone()
            is not None
        )

    def node(self, identifier: str) -> LineageNode:
        row = self.connection.execute(
            "SELECT node_id, kind, label, attributes FROM lineage_nodes WHERE node_id = ?",
            [identifier],
        ).fetchone()
        if row is None:
            raise LineageError(f"No lineage node {identifier[:12]}")
        return LineageNode(str(row[0]), NodeKind(row[1]), str(row[2]), json.loads(row[3]))

    def parents(self, identifier: str) -> list[tuple[str, EdgeKind]]:
        rows = self.connection.execute(
            "SELECT upstream_id, kind FROM lineage_edges WHERE downstream_id = ?"
            " ORDER BY upstream_id",
            [identifier],
        ).fetchall()
        return [(str(row[0]), EdgeKind(row[1])) for row in rows]

    def trace(self, identifier: str) -> list[LineageNode]:
        """Every ancestor of a node, nearest first.

        This is what the evidence panel draws for a claim, and what answers
        "which bytes is this number standing on".
        """
        if not self.exists(identifier):
            raise LineageError(f"No lineage node {identifier[:12]}")
        seen = {identifier}
        order: list[LineageNode] = []
        queue = deque(parent for parent, _ in self.parents(identifier))
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            order.append(self.node(current))
            queue.extend(parent for parent, _ in self.parents(current))
        return order

    def sources_of(self, identifier: str) -> list[LineageNode]:
        """The bronze artifacts a node ultimately rests on."""
        return [node for node in self.trace(identifier) if node.kind is NodeKind.SOURCE_FILE]

    def has_provenance(self, identifier: str) -> bool:
        """Whether a node reaches at least one source file. A cell that does not is a bug."""
        return bool(self.sources_of(identifier))

    # DEC-118 also names a networkx export for graph layout. It is not written
    # here because nothing consumes it yet: `trace` answers every question the
    # pipeline currently asks, and networkx would be an undeclared dependency
    # serving dead code. It arrives with the UI task that needs a layout.


def missing_provenance(lineage: Lineage, identifiers: Iterable[str]) -> list[str]:
    """Nodes that do not reach a source file. Intended to fail a build, not warn."""
    return [identifier for identifier in identifiers if not lineage.has_provenance(identifier)]
