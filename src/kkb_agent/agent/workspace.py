"""The analysis workspace as an artifact DAG (M5-10/11/12, DEC-117).

The organizer's scenario is three turns, and the second and third both begin
"without disturbing the table". That is a requirement about *state*, not about
prose: adding a column must add a node, not rebuild everything, because a table
rebuilt each turn is how a value silently changes between two answers the user
believes are the same table.

So artifacts are immutable and content-addressed, exactly like lineage nodes. A
name points at one artifact; redefining that name mints a new artifact and marks
everything downstream **stale** rather than recomputing it eagerly or, worse,
leaving it looking current. Old artifacts are never deleted, so the history of
what the analysis used to say remains answerable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

WORKSPACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_artifacts (
    artifact_id   TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    name          TEXT NOT NULL,
    parameters    TEXT NOT NULL,
    inputs        TEXT NOT NULL,
    value_ref     TEXT,
    lineage_node  TEXT
);

CREATE TABLE IF NOT EXISTS workspace_bindings (
    workspace_id  TEXT NOT NULL,
    name          TEXT NOT NULL,
    artifact_id   TEXT NOT NULL,
    stale         BOOLEAN NOT NULL,
    revision      INTEGER NOT NULL,
    PRIMARY KEY (workspace_id, name)
);

CREATE TABLE IF NOT EXISTS workspace_history (
    workspace_id  TEXT NOT NULL,
    name          TEXT NOT NULL,
    revision      INTEGER NOT NULL,
    artifact_id   TEXT NOT NULL,
    PRIMARY KEY (workspace_id, name, revision)
);
"""


class ArtifactKind(StrEnum):
    SOURCE = "source"
    COLUMN = "column"
    TABLE = "table"
    CHART = "chart"
    VALUE = "value"
    ASSUMPTION = "assumption"


class WorkspaceError(ValueError):
    """The workspace refused a change that would lose or misrepresent state."""


@dataclass(frozen=True, slots=True)
class Artifact:
    """An immutable derivation. Its id is a hash of what defines it."""

    artifact_id: str
    kind: ArtifactKind
    name: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()
    value_ref: str | None = None
    lineage_node: str | None = None


def artifact_id(
    kind: ArtifactKind,
    name: str,
    parameters: Mapping[str, str],
    inputs: Sequence[str],
) -> str:
    """Content address over the definition, not over the computed value.

    Inputs are kept in order because argument position can matter — a ratio of
    A to B is not the ratio of B to A.
    """
    payload = json.dumps(
        {
            "kind": kind.value,
            "name": name,
            "parameters": dict(sorted(parameters.items())),
            "inputs": list(inputs),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    artifact_id: str
    stale: bool
    revision: int


class Workspace:
    """Named analysis state over one DuckDB connection.

    A name is a slot; an artifact is what currently fills it. Turn two rebinds a
    slot and marks its dependents stale, and turn three adds a slot without
    touching anything already there.
    """

    def __init__(self, connection: DuckDBPyConnection, workspace_id: str = "default") -> None:
        if not workspace_id.strip():
            raise WorkspaceError("A workspace needs an id")
        self.connection = connection
        self.workspace_id = workspace_id

    @classmethod
    def open(cls, connection: DuckDBPyConnection, workspace_id: str = "default") -> Workspace:
        """Open over any DuckDB connection, creating the tables if absent.

        `open_lakehouse` already applies every schema through
        `kkb_agent.database.apply_schema`, so this is a no-op there. It exists
        so a workspace can also be opened over a bare connection.
        """
        connection.execute(WORKSPACE_SCHEMA)
        return cls(connection, workspace_id)

    # -- definition ----------------------------------------------------------

    def define(
        self,
        name: str,
        kind: ArtifactKind,
        *,
        parameters: Mapping[str, str] | None = None,
        inputs: Sequence[str] = (),
        value_ref: str | None = None,
        lineage_node: str | None = None,
    ) -> Artifact:
        """Bind `name` to an artifact derived from the named `inputs`.

        Redefining a name with an identical definition is a no-op that returns
        the existing artifact. Redefining it differently mints a new artifact,
        bumps the revision, and marks every dependent stale — the dependents are
        not recomputed here, because whether they *should* be recomputed is the
        caller's decision and doing it silently is how stale results hide.
        """
        if not name.strip():
            raise WorkspaceError("An artifact needs a name")
        parameters = dict(parameters or {})
        resolved: list[str] = []
        for dependency in inputs:
            if dependency == name:
                raise WorkspaceError(f"{name!r} cannot depend on itself")
            binding = self._binding(dependency)
            if binding is None:
                raise WorkspaceError(f"{name!r} depends on undefined {dependency!r}")
            resolved.append(binding.artifact_id)
        if self._would_cycle(name, inputs):
            raise WorkspaceError(f"Defining {name!r} would create a dependency cycle")

        identifier = artifact_id(kind, name, parameters, resolved)
        existing = self._binding(name)
        if existing is not None and existing.artifact_id == identifier and not existing.stale:
            return self.artifact(identifier)

        self.connection.execute(
            "INSERT OR IGNORE INTO workspace_artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                identifier,
                kind.value,
                name,
                json.dumps(parameters, ensure_ascii=False, sort_keys=True),
                json.dumps(resolved, ensure_ascii=False),
                value_ref,
                lineage_node,
            ],
        )
        revision = (existing.revision + 1) if existing else 1
        self.connection.execute(
            "INSERT OR REPLACE INTO workspace_bindings VALUES (?, ?, ?, ?, ?)",
            [self.workspace_id, name, identifier, False, revision],
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO workspace_history VALUES (?, ?, ?, ?)",
            [self.workspace_id, name, revision, identifier],
        )
        if existing is not None and existing.artifact_id != identifier:
            self._mark_stale(self.dependents(name))
        return self.artifact(identifier)

    # -- reading -------------------------------------------------------------

    def names(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM workspace_bindings WHERE workspace_id = ? ORDER BY name",
            [self.workspace_id],
        ).fetchall()
        return [str(row[0]) for row in rows]

    def resolve(self, name: str) -> Artifact:
        binding = self._binding(name)
        if binding is None:
            raise WorkspaceError(f"No artifact named {name!r}")
        return self.artifact(binding.artifact_id)

    def artifact(self, identifier: str) -> Artifact:
        row = self.connection.execute(
            "SELECT artifact_id, kind, name, parameters, inputs, value_ref, lineage_node"
            " FROM workspace_artifacts WHERE artifact_id = ?",
            [identifier],
        ).fetchone()
        if row is None:
            raise WorkspaceError(f"No artifact {identifier[:12]}")
        return Artifact(
            artifact_id=str(row[0]),
            kind=ArtifactKind(row[1]),
            name=str(row[2]),
            parameters=json.loads(row[3]),
            inputs=tuple(json.loads(row[4])),
            value_ref=row[5],
            lineage_node=row[6],
        )

    def history(self, name: str) -> list[Artifact]:
        """Every artifact this name has held, oldest first. Nothing is deleted."""
        rows = self.connection.execute(
            "SELECT artifact_id FROM workspace_history WHERE workspace_id = ? AND name = ?"
            " ORDER BY revision",
            [self.workspace_id, name],
        ).fetchall()
        return [self.artifact(str(row[0])) for row in rows]

    # -- dependency and staleness -------------------------------------------

    def dependents(self, name: str) -> set[str]:
        """Every name that transitively depends on `name`."""
        direct = self._direct_dependents()
        found: set[str] = set()
        queue = list(direct.get(name, ()))
        while queue:
            current = queue.pop()
            if current in found:
                continue
            found.add(current)
            queue.extend(direct.get(current, ()))
        return found

    def stale(self) -> set[str]:
        rows = self.connection.execute(
            "SELECT name FROM workspace_bindings WHERE workspace_id = ? AND stale",
            [self.workspace_id],
        ).fetchall()
        return {str(row[0]) for row in rows}

    def is_stale(self, name: str) -> bool:
        binding = self._binding(name)
        if binding is None:
            raise WorkspaceError(f"No artifact named {name!r}")
        return binding.stale

    def refresh(self, name: str) -> Artifact:
        """Recompute a stale name from its inputs' current artifacts.

        The definition is unchanged; only the inputs moved. Refreshing a name
        whose own inputs are still stale is refused, so a recomputation cannot
        quietly rest on a value that is itself out of date.
        """
        binding = self._binding(name)
        if binding is None:
            raise WorkspaceError(f"No artifact named {name!r}")
        current = self.artifact(binding.artifact_id)
        input_names = self._input_names(current)
        blocked = sorted(item for item in input_names if self.is_stale(item))
        if blocked:
            raise WorkspaceError(f"Refresh {name!r} after its stale inputs: {', '.join(blocked)}")
        return self.define(
            name,
            current.kind,
            parameters=current.parameters,
            inputs=input_names,
            value_ref=current.value_ref,
            lineage_node=current.lineage_node,
        )

    def refresh_order(self) -> list[str]:
        """Stale names in an order where each one's inputs come first."""
        order: list[str] = []
        remaining = self.stale()
        while remaining:
            ready = sorted(
                name
                for name in remaining
                if not (set(self._input_names(self.resolve(name))) & remaining)
            )
            if not ready:  # pragma: no cover - define() refuses cycles
                raise WorkspaceError("Stale set contains a cycle")
            order.extend(ready)
            remaining.difference_update(ready)
        return order

    # -- internals -----------------------------------------------------------

    def _binding(self, name: str) -> Binding | None:
        row = self.connection.execute(
            "SELECT name, artifact_id, stale, revision FROM workspace_bindings"
            " WHERE workspace_id = ? AND name = ?",
            [self.workspace_id, name],
        ).fetchone()
        if row is None:
            return None
        return Binding(str(row[0]), str(row[1]), bool(row[2]), int(row[3]))

    def _input_names(self, artifact: Artifact) -> list[str]:
        return [self.artifact(identifier).name for identifier in artifact.inputs]

    def _direct_dependents(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for name in self.names():
            for parent in self._input_names(self.resolve(name)):
                mapping.setdefault(parent, set()).add(name)
        return mapping

    def _would_cycle(self, name: str, inputs: Iterable[str]) -> bool:
        downstream = self.dependents(name)
        return any(dependency in downstream for dependency in inputs)

    def _mark_stale(self, names: Iterable[str]) -> None:
        for name in sorted(names):
            self.connection.execute(
                "UPDATE workspace_bindings SET stale = TRUE WHERE workspace_id = ? AND name = ?",
                [self.workspace_id, name],
            )
