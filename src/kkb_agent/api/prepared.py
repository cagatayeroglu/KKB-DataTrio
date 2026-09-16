"""Immutable local preparation snapshot and isolated, inspected API analysis runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import duckdb
from pydantic import Field

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.selection import SelectedTable, SelectionError
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.agent.workspace import WorkspaceError
from kkb_agent.api.contracts import MAX_SESSIONS, MAX_TURNS, Answer
from kkb_agent.api.projection import project_answer, safe_text
from kkb_agent.api.proof import build_proof
from kkb_agent.api.service import SelectedResult, ServiceError
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import MAX_SNAPSHOT_BYTES, ReviewedSnapshot, load_reviewed_snapshot
from kkb_agent.core import AnalyticalResult
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.lineage import Lineage
from kkb_agent.lakehouse.store import DATABASE_NAME, SANDBOX
from kkb_agent.llm.provider import LLMProvider
from kkb_agent.tools import (
    make_anomaly_tool,
    make_catalog_search_tool,
    make_causality_tool,
    make_change_detection_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
)

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.catalog.hybrid import CatalogDenseStage

MAX_POOL_BYTES = 1024 * 1024 * 1024
MAX_POOL_FILES = 10000
_IDENTIFIER = re.compile(r"[a-f0-9]{32}\Z")


class PreparedError(ValueError):
    """Fixed startup/runtime category, never the operator's path or content."""


@dataclass(frozen=True, slots=True)
class _Publication:
    selection: SelectedResult
    name: str
    artifact_id: str


@dataclass(frozen=True, slots=True)
class PendingClarification:
    original_question: str
    clarifications: tuple[str, ...] = ()
    selection: SelectedResult | None = None


_CANCELLATION_KEYWORDS = {"iptal", "vazgeç", "vazgeçtim", "cancel", "iptal et"}
_CANCELLATION_PREFIXES = ("iptal:", "vazgeç:", "cancel:")

_NEW_QUESTION_PREFIXES = (
    "yeni soru:",
    "yeni istek:",
    "bağımsız soru:",
    "farklı soru:",
    "yeni:",
    "new question:",
    "vazgeçip başka",
    "başka bir soru",
)


def _is_cancellation(question: str) -> bool:
    q = question.strip().lower()
    if q in _CANCELLATION_KEYWORDS:
        return True
    return any(q.startswith(prefix) for prefix in _CANCELLATION_PREFIXES)


def _is_new_question(
    question: str,
    selection: SelectedResult | None,
    pending: PendingClarification,
) -> bool:
    q = question.strip().lower()
    if any(q.startswith(prefix) for prefix in _NEW_QUESTION_PREFIXES):
        return True
    if selection is not None and pending.selection is not None and selection != pending.selection:
        return True
    return False


def _format_clarification_prompt(original: str, clarifications: tuple[str, ...]) -> str:
    lines = [f"Orijinal istek: {original}"]
    for c in clarifications:
        lines.append(f"Açıklama: {c}")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    """Freshly read workspace value; not an execution or verifier authorization."""

    name: str
    artifact_id: str
    value: AnalyticalResult


class PreparedSeries(ContractModel):
    series_id: str
    title: str
    observations: Annotated[int, Field(ge=0)]
    nonnull_observations: Annotated[int, Field(ge=0)]
    first_period: date | None
    last_period: date | None


class PreparedStatus(ContractModel):
    snapshot_id: str
    catalog_version: str
    catalog_identities: int
    prepared_identities: int
    observation_rows: int
    pool_bytes: int
    files: int
    series: tuple[PreparedSeries, ...]
    live_model_checked: bool = False


def _local(path: Path, *, exists: bool = True) -> Path:
    raw = str(path)
    if not path.is_absolute() or raw.startswith(("\\\\", "//")):
        raise PreparedError("local_absolute_path_required")
    # Check each existing ancestor before resolving so a symlink cannot disappear.
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise PreparedError("linked_path_refused")
    try:
        return path.resolve(strict=exists)
    except OSError:
        raise PreparedError("local_path_unavailable") from None


def _files(root: Path) -> Iterator[Path]:
    visited = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        visited += len(dirs) + len(names)
        if visited > MAX_POOL_FILES * 2 or len(Path(directory).relative_to(root).parts) > 12:
            raise PreparedError("prepared_pool_limit")
        for name in sorted([*dirs, *names]):
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                raise PreparedError("linked_path_refused")
            if not path.resolve().is_relative_to(root):
                raise PreparedError("path_escape_refused")
        for name in sorted(names):
            yield Path(directory) / name


def manifest(root: Path) -> dict[str, tuple[int, str]]:
    """Bounded file hashing; original pool must be closed/quiescent by its owner."""
    root = _local(root)
    if not root.is_dir() or not (root / DATABASE_NAME).is_file():
        raise PreparedError("prepared_pool_missing")
    entries: dict[str, tuple[int, str]] = {}
    total = 0
    for path in _files(root):
        relative = path.relative_to(root)
        if relative.parts[0] not in (DATABASE_NAME, "bronze", "silver", "gold"):
            raise PreparedError("unexpected_prepared_file")
        size = path.stat().st_size
        total += size
        if total > MAX_POOL_BYTES or len(entries) >= MAX_POOL_FILES:
            raise PreparedError("prepared_pool_limit")
        digest = hashlib.sha256()
        seen = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                seen += len(chunk)
                if seen > size:
                    raise PreparedError("prepared_pool_changed")
                digest.update(chunk)
        if seen != size:
            raise PreparedError("prepared_pool_changed")
        entries[relative.as_posix()] = (size, digest.hexdigest())
    return entries


def read_catalog(path: Path) -> bytes:
    path = _local(path)
    with path.open("rb") as stream:
        data = stream.read(MAX_SNAPSHOT_BYTES + 1)
    load_reviewed_snapshot(data)
    return data


def inspect_pool(root: Path, catalog: ReviewedSnapshot) -> PreparedStatus:
    root = _local(root)
    before = manifest(root)
    inspector = PreparedSeriesInspector(catalog)
    reviewed = {s.record.series_id: s.record for s in catalog.series}
    connection = duckdb.connect(str(root / DATABASE_NAME), read_only=True, config=dict(SANDBOX))
    try:
        tables = {r[0] for r in connection.execute("SHOW TABLES").fetchall()}
        # A prepared seed is not another user's active analysis database.
        for table, query in (
            ("workspace_artifacts", "SELECT 1 FROM workspace_artifacts LIMIT 1"),
            ("workspace_bindings", "SELECT 1 FROM workspace_bindings LIMIT 1"),
            ("workspace_history", "SELECT 1 FROM workspace_history LIMIT 1"),
            ("workspace_results", "SELECT 1 FROM workspace_results LIMIT 1"),
        ):
            if table in tables and connection.execute(query).fetchone():
                raise PreparedError("prepared_pool_contains_workspace")
        rows = connection.execute(
            "SELECT s.series_id, count(o.series_id), count(o.value), "
            "min(o.period_start), max(o.period_end) FROM silver_series s "
            "LEFT JOIN silver_observations o ON s.series_id=o.series_id "
            "GROUP BY s.series_id ORDER BY s.series_id LIMIT ?",
            [len(reviewed) + 1],
        ).fetchall()
        if not rows or len(rows) > len(reviewed):
            raise PreparedError("prepared_series_limit")
        series = []
        names = prepared_series_names(connection)
        for sid, count, nonnull, first, last in rows:
            inspection = inspector.inspect(connection, sid)
            if inspection.status != "consistent":
                raise PreparedError("prepared_semantics_refused")
            series.append(
                PreparedSeries(
                    series_id=sid,
                    title=safe_text(names.get(sid, reviewed[sid].title), limit=240),
                    observations=count,
                    nonnull_observations=nonnull,
                    first_period=first,
                    last_period=last,
                )
            )
    finally:
        connection.close()
    if manifest(root) != before:
        raise PreparedError("prepared_pool_changed")
    fingerprint = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    return PreparedStatus(
        snapshot_id=fingerprint,
        catalog_version=catalog.content_sha256,
        catalog_identities=len(catalog.series),
        prepared_identities=len(series),
        observation_rows=sum(s.observations for s in series),
        pool_bytes=sum(size for size, _ in before.values()),
        files=len(before),
        series=tuple(series),
    )


def _copy(root: Path, destination: Path, expected: dict[str, tuple[int, str]]) -> None:
    """Exclusive bounded copy, then rehash; never overwrite, move or delete data."""
    if destination.exists() or manifest(root) != expected:
        raise PreparedError("prepared_copy_refused")
    destination.mkdir(parents=True, exist_ok=False)
    for relative, (size, _digest) in expected.items():
        source, target = root / relative, destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as src, target.open("xb") as dst:
            remaining = size
            while remaining:
                chunk = src.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise PreparedError("prepared_pool_changed")
                dst.write(chunk)
                remaining -= len(chunk)
            if src.read(1):
                raise PreparedError("prepared_pool_changed")
    if manifest(root) != expected or manifest(destination) != expected:
        raise PreparedError("prepared_pool_changed")


class PreparedRunner:
    """Only the service's one worker invokes this runner; no caller paths/settings."""

    def __init__(
        self,
        provider: LLMProvider,
        root: Path,
        state_root: Path,
        *,
        catalog_bytes: bytes,
        redactions: tuple[str, ...] = (),
        catalog_dense: CatalogDenseStage | None = None,
    ):
        self._catalog = load_reviewed_snapshot(catalog_bytes)
        self._catalog_bytes = catalog_bytes
        # Optional operator-built index generation; without it discovery stays lexical.
        if catalog_dense is not None and (
            catalog_dense.index.snapshot_sha256 != self._catalog.content_sha256
        ):
            raise PreparedError("catalog_index_mismatch")
        self._dense = catalog_dense
        self._provider = provider
        self._redactions = redactions
        root, state_root = _local(root), _local(state_root, exists=False)
        if state_root.is_relative_to(root) or root.is_relative_to(state_root):
            raise PreparedError("overlapping_roots_refused")
        self.status = inspect_pool(root, self._catalog)
        expected = manifest(root)
        if (
            hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
            != self.status.snapshot_id
        ):
            raise PreparedError("prepared_pool_changed")
        self.run_root = state_root / uuid4().hex
        self.seed = self.run_root / "seed"
        _copy(root, self.seed, expected)
        self._manifest = expected
        self._turns: dict[str, int] = {}
        self._publications: dict[tuple[str, str], _Publication] = {}
        self._pending_clarifications: dict[str, PendingClarification] = {}
        self._lock = threading.Lock()

    def __call__(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        *,
        is_continuation: bool | None = None,
    ) -> Answer:
        return self._run(session_id, turn_id, question, is_continuation=is_continuation)

    def selected(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selection: SelectedResult,
        *,
        is_continuation: bool | None = None,
    ) -> Answer:
        """Service worker entry; resolve and execute under the same runner lock."""
        try:
            return self._run(
                session_id,
                turn_id,
                question,
                selection,
                is_continuation=is_continuation,
            )
        except (SelectionError, WorkspaceError):
            raise ServiceError("invalid_result", 422) from None

    def _run(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selection: SelectedResult | None = None,
        is_continuation: bool | None = None,
    ) -> Answer:
        if not _IDENTIFIER.fullmatch(session_id) or not _IDENTIFIER.fullmatch(turn_id):
            raise PreparedError("invalid_runtime_identity")
        if not self._lock.acquire(blocking=False):
            raise PreparedError("concurrent_runtime_refused")
        try:
            pending = self._pending_clarifications.get(session_id)
            effective_question = question
            effective_selection = selection
            is_cancel = False
            is_new_q = False
            if pending is not None:
                if is_continuation is False or _is_cancellation(question):
                    is_cancel = True
                    self._pending_clarifications.pop(session_id, None)
                    effective_question = question
                    effective_selection = selection
                elif _is_new_question(question, selection, pending):
                    is_new_q = True
                    self._pending_clarifications.pop(session_id, None)
                    effective_question = question
                    effective_selection = selection
                else:
                    if effective_selection is None and pending.selection is not None:
                        if (session_id, pending.selection.turn_id) in self._publications:
                            effective_selection = pending.selection
                    effective_question = _format_clarification_prompt(
                        pending.original_question, pending.clarifications + (question,)
                    )

            if (
                effective_selection is not None
                and (session_id, effective_selection.turn_id) not in self._publications
            ):
                raise ServiceError("invalid_result", 422)
            if (session_id, turn_id) in self._publications:
                raise PreparedError("duplicate_publication_turn")
            if session_id not in self._turns and len(self._turns) >= MAX_SESSIONS:
                raise PreparedError("runtime_session_limit")
            previous = self._turns.get(session_id, 0)
            if previous >= MAX_TURNS:
                raise PreparedError("runtime_turn_limit")
            self._turns.setdefault(session_id, 0)
            target = self.run_root / session_id / "lake"
            if previous == 0:
                _copy(self.seed, target, self._manifest)
            if not (target / DATABASE_NAME).is_file():
                raise PreparedError("session_pool_missing")
            self._turns[session_id] = previous + 1
            name = f"analiz_{previous + 1}"
            with open_lakehouse(target) as lake:
                workspace = Workspace.open(lake.connection, session_id)
                selected_table = None
                if effective_selection is not None:
                    try:
                        resolved = self._resolve_selection(workspace, effective_selection)
                    except (ValueError, duckdb.Error):
                        raise ServiceError("invalid_result", 422) from None
                    selected_table = SelectedTable(
                        workspace,
                        resolved.name,
                        resolved.artifact_id,
                        effective_selection.version,
                    )
                registry = self._registry(lake.connection, workspace, lake.lineage)
                answered = Session(
                    self._provider,
                    registry,
                    catalog_continuation=True,
                    selection=selected_table,
                    require_series_discovery=self._dense is not None,
                    repair_period_wording=True,
                    repair_unmatched_numbers=True,
                ).answer(effective_question, lake.connection, workspace=workspace, remember=name)
                published = workspace.value_of(name) if name in workspace.names() else None
                answer = project_answer(
                    answered,
                    turn_id=turn_id,
                    published=published,
                    secrets=self._redactions,
                    proof=(
                        build_proof(lake.connection, published, secrets=self._redactions)
                        if published is not None
                        else None
                    ),
                )
                # Only retain references that survived publication AND projection.
                # Bounded by the existing session/turn limits; never rebuild this
                # ownership map by scanning arbitrary stored result digests.
                if answer.result is not None:
                    self._publications[session_id, turn_id] = _Publication(
                        SelectedResult(turn_id, answer.result.result_ref, answer.result.version),
                        name,
                        workspace.resolve(name).artifact_id,
                    )
                clarification_reason = answered.planned.plan.clarification
                if answer.status == AnswerStatus.ACCEPTED:
                    self._pending_clarifications.pop(session_id, None)
                elif clarification_reason in (
                    "ambiguous_series",
                    "missing_series",
                    "unresolved_semantics",
                ):
                    if pending is not None and not is_cancel and not is_new_q:
                        orig_q = pending.original_question
                        accumulated = pending.clarifications + (question,)
                        sel = effective_selection
                    else:
                        orig_q = question
                        accumulated = ()
                        sel = selection
                    self._pending_clarifications[session_id] = PendingClarification(
                        original_question=orig_q,
                        clarifications=accumulated,
                        selection=sel,
                    )
                return answer

        finally:
            self._lock.release()

    def resolve_selection(self, session_id: str, selection: SelectedResult) -> ResolvedSelection:
        """Worker-side resolution only; never an HTTP endpoint or selected runner.

        The next execution slice must re-resolve inside its locked execution
        scope. This read is a snapshot, not a lease on future workspace state.
        """
        if not _IDENTIFIER.fullmatch(session_id):
            raise PreparedError("invalid_result")
        if not self._lock.acquire(blocking=False):
            raise PreparedError("concurrent_runtime_refused")
        try:
            if (session_id, selection.turn_id) not in self._publications:
                raise PreparedError("invalid_result")
            target = self.run_root / session_id / "lake" / DATABASE_NAME
            try:
                connection = duckdb.connect(str(target), read_only=True, config=dict(SANDBOX))
                try:
                    return self._resolve_selection(Workspace(connection, session_id), selection)
                finally:
                    connection.close()
            except (ValueError, duckdb.Error):
                raise PreparedError("invalid_result") from None
        finally:
            self._lock.release()

    def _resolve_selection(
        self, workspace: Workspace, selection: SelectedResult
    ) -> ResolvedSelection:
        publication = self._publications.get((workspace.workspace_id, selection.turn_id))
        if publication is None or publication.selection != selection:
            raise PreparedError("invalid_result")
        value = SelectedTable(
            workspace, publication.name, publication.artifact_id, selection.version
        ).check()
        return ResolvedSelection(publication.name, publication.artifact_id, value)

    def _registry(
        self, connection: duckdb.DuckDBPyConnection, workspace: Workspace, lineage: Lineage
    ) -> ToolRegistry:
        inspector = PreparedSeriesInspector(self._catalog)
        # Existing code-reviewed names only. Free catalog/source metadata belongs
        # in catalog continuation's USER data, never a SYSTEM tool description.
        names = prepared_series_names(connection)
        registry = ToolRegistry()
        registry.register(
            make_catalog_search_tool(snapshot_bytes=self._catalog_bytes, dense=self._dense)
        )
        registry.register(make_lakehouse_tool(connection, lineage=lineage, inspector=inspector))
        registry.register(
            make_change_detection_tool(
                connection,
                lineage=lineage,
                workspace=workspace,
                series_names=names,
                inspector=inspector,
            )
        )
        registry.register(
            make_table_transform_tool(
                connection,
                workspace,
                lineage=lineage,
                series_names=names,
                inspector=inspector,
            )
        )
        for make in (make_anomaly_tool, make_causality_tool):
            registry.register(make(connection, lineage=lineage, inspector=inspector))
        return registry
