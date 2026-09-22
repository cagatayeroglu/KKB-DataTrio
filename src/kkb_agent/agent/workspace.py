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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from kkb_agent.core import AnalyticalResult

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: Recompute one artifact from the current values of its inputs.
#:
#: The workspace never invents this. It knows a name went stale and which
#: values it now rests on; what a column *means* lives in the tool that
#: produced it, so refreshing a value requires the caller to supply the work.
Recomputer = Callable[["Artifact", Mapping[str, AnalyticalResult]], AnalyticalResult]

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

CREATE TABLE IF NOT EXISTS workspace_results (
    result_digest TEXT PRIMARY KEY,
    result_id     TEXT NOT NULL,
    payload       TEXT NOT NULL
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
    value_ref: str | None = None,
) -> str:
    """Content address over what defines this artifact.

    For a pure definition that is kind, name, parameters and inputs — not the
    data underneath, so re-deriving the same column converges on one node.

    A **recorded value** additionally includes its own content address, and it
    has to. Without it, recording a new result under an unchanged definition
    would produce the same id, be treated as a no-op, and leave the previous
    number bound while every dependent stayed unmarked — a value that changed
    with nothing downstream noticing. A definition with no value hashes exactly
    as it did before this argument existed.

    Inputs are kept in order because argument position can matter — a ratio of
    A to B is not the ratio of B to A.
    """
    definition: dict[str, object] = {
        "kind": kind.value,
        "name": name,
        "parameters": dict(sorted(parameters.items())),
        "inputs": list(inputs),
    }
    if value_ref is not None:
        definition["value"] = value_ref
    payload = json.dumps(definition, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    artifact_id: str
    stale: bool
    revision: int


@dataclass(frozen=True, slots=True)
class PublicationPreview:
    """An in-memory candidate and the exact workspace view reviewed by the gate.

    JSON snapshots keep mutable result models from changing the staged payload.
    This is not verification evidence; Session owns publication eligibility.
    """

    workspace_id: str
    name: str
    candidate_json: str
    state_token: str
    named_json: tuple[tuple[str, str], ...]
    inputs: tuple[str, ...] = ()
    related: tuple[tuple[str, str], ...] = ()

    def values(self) -> dict[str, AnalyticalResult]:
        return {
            name: AnalyticalResult.model_validate_json(payload) for name, payload in self.named_json
        }


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
        definition = self._definition(name, kind, parameters, inputs, value_ref, lineage_node)
        identifier = definition.artifact_id
        parameters = definition.parameters
        resolved = definition.inputs
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

    def _definition(
        self,
        name: str,
        kind: ArtifactKind,
        parameters: Mapping[str, str] | None,
        inputs: Sequence[str],
        value_ref: str | None,
        lineage_node: str | None,
    ) -> Artifact:
        """Resolve a definition without writing; shared by define and preview."""
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

        identifier = artifact_id(kind, name, parameters, resolved, value_ref)
        return Artifact(
            identifier, kind, name, parameters, tuple(resolved), value_ref, lineage_node
        )

    # -- reading -------------------------------------------------------------

    def names(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM workspace_bindings WHERE workspace_id = ? ORDER BY name",
            [self.workspace_id],
        ).fetchall()
        return [str(row[0]) for row in rows]

    def resolve(self, name: str, *, allow_stale: bool = False) -> Artifact:
        """The artifact currently bound to `name`, refusing a stale read.

        A stale artifact is one whose inputs have moved underneath it, so its
        value describes an analysis nobody asked for any more. Returning it and
        hoping the caller checks `is_stale` is how a superseded number reaches
        an answer; the default is therefore to refuse. `allow_stale` exists for
        inspection — showing what went stale, or ordering a refresh — not for
        reading a value.
        """
        binding = self._binding(name)
        if binding is None:
            raise WorkspaceError(f"No artifact named {name!r}")
        if binding.stale and not allow_stale:
            raise WorkspaceError(
                f"{name!r} is stale: its inputs changed. Refresh it, or pass "
                "allow_stale=True to inspect the superseded definition"
            )
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

    def refresh(self, name: str, recompute: Recomputer | None = None) -> Artifact:
        """Rebind a stale name to its inputs' current artifacts.

        The definition is unchanged; only the inputs moved. Refreshing a name
        whose own inputs are still stale is refused, so a recomputation cannot
        quietly rest on a value that is itself out of date.

        A name that holds a **value** additionally requires `recompute`.
        Rebinding a valued artifact without recomputing would clear the stale
        flag while leaving the old number in place, which is the precise shape
        of the failure this whole mechanism exists to prevent: a figure that
        looks current and describes a selection nobody made any more.
        """
        binding = self._binding(name)
        if binding is None:
            raise WorkspaceError(f"No artifact named {name!r}")
        current = self.artifact(binding.artifact_id)
        input_names = self._input_names(current)
        blocked = sorted(item for item in input_names if self.is_stale(item))
        if blocked:
            raise WorkspaceError(f"Refresh {name!r} after its stale inputs: {', '.join(blocked)}")

        value_ref = current.value_ref
        if recompute is not None:
            inputs = {
                item: self.value_of(item)
                for item in input_names
                if self.resolve(item).value_ref is not None
            }
            value_ref = self.store_result(recompute(current, inputs))
        elif current.value_ref is not None:
            raise WorkspaceError(
                f"{name!r} holds a value; refreshing it without recomputing would "
                "present an old number as current. Supply a recomputer"
            )
        return self.define(
            name,
            current.kind,
            parameters=current.parameters,
            inputs=input_names,
            value_ref=value_ref,
            lineage_node=current.lineage_node,
        )

    # -- values --------------------------------------------------------------

    def store_result(self, result: AnalyticalResult) -> str:
        """Persist a typed result and return its content address.

        Keyed by `digest()`, so storing identical content twice is one row and
        differing content can never overwrite what an earlier turn recorded.
        That immutability is what makes an old answer still answerable after
        the analysis has moved on.
        """
        digest = result.digest()
        self.connection.execute(
            "INSERT OR IGNORE INTO workspace_results VALUES (?, ?, ?)",
            [digest, result.result_id, result.model_dump_json()],
        )
        return digest

    def read_result(self, digest: str) -> AnalyticalResult:
        """Read a stored result back, refusing one that no longer hashes true.

        The check is cheap and it is the only thing standing between a mutated
        row and an answer that cites it as evidence.
        """
        row = self.connection.execute(
            "SELECT payload FROM workspace_results WHERE result_digest = ?", [digest]
        ).fetchone()
        if row is None:
            raise WorkspaceError(f"No stored result {digest[:12]}")
        result = AnalyticalResult.model_validate_json(str(row[0]))
        if result.digest() != digest:
            raise WorkspaceError(
                f"Stored result {digest[:12]} no longer matches its content address"
            )
        return result

    def record(
        self,
        name: str,
        kind: ArtifactKind,
        result: AnalyticalResult,
        *,
        parameters: Mapping[str, str] | None = None,
        inputs: Sequence[str] = (),
    ) -> Artifact:
        """Define `name` and give it the value a tool actually produced."""
        return self.define(
            name,
            kind,
            parameters=parameters,
            inputs=inputs,
            value_ref=self.store_result(result),
            lineage_node=result.evidence.lineage_node if result.evidence else None,
        )

    def _publication_state(self) -> str:
        """Version the bound workspace, including stale flags and stored payloads.

        Revisions detect change-and-change-back; definitions/payloads also detect
        mutation underneath an unchanged binding. Other workspaces are excluded.
        """
        rows = self.connection.execute(
            "SELECT b.name, b.artifact_id, b.stale, b.revision, "
            "a.kind, a.name, a.parameters, a.inputs, a.value_ref, a.lineage_node, "
            "r.result_id, r.payload FROM workspace_bindings b "
            "LEFT JOIN workspace_artifacts a ON a.artifact_id = b.artifact_id "
            "LEFT JOIN workspace_results r ON r.result_digest = a.value_ref "
            "WHERE b.workspace_id = ? ORDER BY b.name",
            [self.workspace_id],
        ).fetchall()
        return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()

    def preview(
        self, name: str, result: AnalyticalResult, *, inputs: tuple[str, ...] = ()
    ) -> PublicationPreview:
        """Preview Session's VALUE publication with define's existing semantics."""
        token = self._publication_state()
        for dependency in inputs:
            self.resolve(dependency)  # Refuse stale or missing publication inputs.
        definition = self._definition(
            name,
            ArtifactKind.VALUE,
            None,
            inputs,
            result.digest(),
            result.evidence.lineage_node if result.evidence else None,
        )
        existing = self._binding(name)
        invalidated = (
            self.dependents(name)
            if existing is not None and existing.artifact_id != definition.artifact_id
            else set()
        )
        # Read only values that survive the proposed transition. In particular,
        # do not revive a stale dependent or reread the superseded target value.
        values = {}
        for current in self.names():
            if current == name or current in invalidated or self.is_stale(current):
                continue
            if self.resolve(current).value_ref is not None:
                values[current] = self.value_of(current)
        values[name] = result
        if self._publication_state() != token:
            raise WorkspaceError("Workspace changed while preparing publication")
        return PublicationPreview(
            self.workspace_id,
            name,
            result.model_dump_json(),
            token,
            tuple((key, value.model_dump_json()) for key, value in sorted(values.items())),
            inputs,
        )

    def publish(self, preview: PublicationPreview) -> Artifact:
        """Commit an eligible preview in a short, independently owned transaction.

        A DuckDB cursor is a separate connection/transaction to the same database.
        Never begin/commit/rollback on the caller's connection. Uncommitted caller
        workspace edits cannot match the committed state checked here. Provider
        and verifier work has already finished before this method is entered.
        """
        if preview.workspace_id != self.workspace_id:
            raise WorkspaceError("Publication belongs to another workspace")
        result = AnalyticalResult.model_validate_json(preview.candidate_json)
        connection = self.connection.cursor()
        try:
            connection.execute("BEGIN TRANSACTION")
            try:
                current = Workspace(connection, self.workspace_id)
                if current._publication_state() != preview.state_token:
                    raise WorkspaceError("Workspace changed since publication preview")
                related = {}
                for name, payload in preview.related:
                    if name == preview.name or name in related or name in current.names():
                        raise WorkspaceError("Related publication would overwrite a binding")
                    child = current.record(
                        name,
                        ArtifactKind.VALUE,
                        AnalyticalResult.model_validate_json(payload),
                        inputs=preview.inputs,
                    )
                    related[name] = child.artifact_id
                artifact = current.record(
                    preview.name,
                    ArtifactKind.VALUE,
                    result,
                    inputs=preview.inputs,
                    parameters={"related_results": json.dumps(related)} if related else None,
                )
                # A fresh reader also catches commits made during our short
                # write transaction, whose own reads use a snapshot.
                observer = self.connection.cursor()
                try:
                    if (
                        Workspace(observer, self.workspace_id)._publication_state()
                        != preview.state_token
                    ):
                        raise WorkspaceError("Workspace changed during publication")
                finally:
                    observer.close()
                connection.execute("COMMIT")
                return artifact
            except BaseException:
                connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    def value_of(self, name: str, *, allow_stale: bool = False) -> AnalyticalResult:
        """The result bound to `name`. Stale names are refused, as in `resolve`."""
        artifact = self.resolve(name, allow_stale=allow_stale)
        if artifact.value_ref is None:
            raise WorkspaceError(f"{name!r} is a definition and holds no value")
        return self.read_result(artifact.value_ref)

    def related_results(self, artifact: Artifact) -> dict[str, AnalyticalResult]:
        """Read companion artifacts by their immutable identities, also after restart."""
        refs = json.loads(artifact.parameters.get("related_results", "{}"))
        if not isinstance(refs, dict) or len(refs) > 11:
            raise WorkspaceError("Invalid related publication references")
        results = {}
        for name, identifier in refs.items():
            related = self.artifact(identifier)
            if (
                related.name != name
                or related.value_ref is None
                or artifact_id(
                    related.kind,
                    related.name,
                    related.parameters,
                    related.inputs,
                    related.value_ref,
                )
                != identifier
            ):
                raise WorkspaceError("Related publication does not match its receipt")
            results[name] = self.read_result(related.value_ref)
        return results

    def values(self) -> dict[str, AnalyticalResult]:
        """Every current, non-stale value, for an answer that spans several."""
        found: dict[str, AnalyticalResult] = {}
        for name in self.names():
            binding = self._binding(name)
            if binding is None or binding.stale:  # pragma: no cover - names() is bindings
                continue
            artifact = self.artifact(binding.artifact_id)
            if artifact.value_ref is not None:
                found[name] = self.read_result(artifact.value_ref)
        return found

    def refresh_order(self) -> list[str]:
        """Stale names in an order where each one's inputs come first."""
        order: list[str] = []
        remaining = self.stale()
        while remaining:
            ready = sorted(
                name
                for name in remaining
                if not (set(self._input_names(self.resolve(name, allow_stale=True))) & remaining)
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
            for parent in self._input_names(self.resolve(name, allow_stale=True)):
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
