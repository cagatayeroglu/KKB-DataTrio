"""Immutable local preparation snapshot and isolated, inspected API analysis runner."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import duckdb
from pydantic import Field, JsonValue

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.cancellation import TurnCancelled
from kkb_agent.agent.loop import MAX_HISTORY_TURNS
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.selection import SelectedTable, SelectionError
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.agent.workspace import WorkspaceError
from kkb_agent.api.contracts import (
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENTS,
    MAX_SESSIONS,
    MAX_TURNS,
    Answer,
    DocumentAdmitted,
)
from kkb_agent.api.projection import project_answer, safe_text
from kkb_agent.api.proof import build_proof
from kkb_agent.api.service import SelectedResult, ServiceError, TurnSettings
from kkb_agent.api.store import DEFAULT_TITLE, ConversationStore
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import (
    MAX_SNAPSHOT_BYTES,
    ReviewedSnapshot,
    load_reviewed_snapshot,
    series_display_names,
)
from kkb_agent.core import AnalyticalResult, SourceRef
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.acquisition import AcquiringInspector, OfficialSources, TurnAcquirer
from kkb_agent.ingest.address_outline import TurnFetchCache, address_outline
from kkb_agent.ingest.attached import SOURCE_TYPE as UPLOAD
from kkb_agent.ingest.attached import Attachment
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.ingestion_policy import MIME_TYPES, AdmissionError, admit_upload
from kkb_agent.knowledge import KnowledgeStore, effective_snapshot
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.gold import GoldError, gold_from_result, persist_gold
from kkb_agent.lakehouse.lineage import Lineage, LineageError
from kkb_agent.lakehouse.semantics import SemanticsError
from kkb_agent.lakehouse.store import DATABASE_NAME, SANDBOX, Lakehouse
from kkb_agent.llm.provider import LLMProvider
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.tools import (
    make_anomaly_tool,
    make_catalog_search_tool,
    make_causality_tool,
    make_change_detection_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
    make_web_search_tool,
    make_web_url_tool,
)
from kkb_agent.tools._document_column import ColumnRefused, read_month_values
from kkb_agent.tools._document_library import document_name, document_outline
from kkb_agent.tools._document_value import as_of, grids
from kkb_agent.tools.web_search import SearchBackend
from kkb_agent.tools.web_url import Fetcher, addresses_in, read_attachment

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
    document_ref: str | None = None


@dataclass(frozen=True, slots=True)
class _Document:
    """An admitted upload: where its bytes are and what they must hash to."""

    kind: str
    media_type: str
    sha256: str
    size: int
    path: Path
    admitted_at: datetime


_UPLOAD_KINDS = {media_type: kind for kind, media_type in MIME_TYPES.items()}


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
#: Words a message must reach, while asking something of its own, before it reads
#: as a new request rather than an answer to the pending clarification.
_NEW_QUESTION_WORDS = 6


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
    """Decide, without asking the person, whether this message answers the clarification.

    An answer to a clarification is short and declarative ("aylık olsun", "TCMB
    verisi"). A message that asks something of its own, at the length of a real
    request, is a new question however the previous turn ended. A caller may still
    state `is_continuation`; this decides only when it did not, and the decision
    is recorded in the turn's trace rather than left to a control the person has
    to operate.
    """
    q = question.strip().lower()
    if any(q.startswith(prefix) for prefix in _NEW_QUESTION_PREFIXES):
        return True
    if selection is not None and pending.selection is not None and selection != pending.selection:
        return True
    return q.endswith("?") and len(q.split()) >= _NEW_QUESTION_WORDS


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


def _recent(history: Sequence[tuple[str, str]], turns: int | None) -> tuple[tuple[str, str], ...]:
    """The earlier turns a planner is shown: the owner's count, or every kept turn."""
    if turns is None:
        return tuple(history)
    return tuple(history)[-turns:] if turns > 0 else ()


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
        web_url_fetch: Fetcher | None = None,
        document_uploads: bool = False,
        document_ocr: OcrProvider | None = None,
        store: ConversationStore | None = None,
        official: OfficialSources | None = None,
        clock: Callable[[], date] = lambda: datetime.now(UTC).date(),
        knowledge: KnowledgeStore | None = None,
        search_backend: SearchBackend | None = None,
    ):
        self._catalog = load_reviewed_snapshot(catalog_bytes)
        self._catalog_bytes = catalog_bytes
        # Optional operator-built index generation; without it discovery stays lexical.
        if catalog_dense is not None and (
            catalog_dense.index.snapshot_sha256 != self._catalog.content_sha256
        ):
            raise PreparedError("catalog_index_mismatch")
        self._dense = catalog_dense
        # Operator switch for prompt addresses (DEC-131); absent while Q-NET-02 is open.
        self._web_url_fetch = web_url_fetch
        # Operator switch for uploads (M10-04); documents live under this process's state.
        self._document_uploads = document_uploads
        # Operator switch for OCR of PDF pages without text (M7-11, DEC-149).
        self._document_ocr = document_ocr
        # Operator switch for fetching a reviewed official series on first use (DEC-155).
        self._official = official
        self._clock = clock
        # The editable knowledge base layered over the reviewed catalog (DEC-157).
        self._knowledge = knowledge
        # Operator-configured discovery backend (DEC-134, DEC-158); absent means no tool.
        self._search_backend = search_backend
        self._documents: dict[tuple[str, str], _Document] = {}
        self._documents_lock = threading.Lock()
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
        # A fixed root, so a conversation's lakehouse is where it was before the
        # restart. The seed is copied once and verified afterwards: a prepared
        # pool that changed underneath must not be reused silently.
        self.run_root = state_root
        self.seed = self.run_root / "seed"
        if (self.seed / DATABASE_NAME).is_file():
            if manifest(self.seed) != expected:
                raise PreparedError("prepared_pool_changed")
        else:
            _copy(root, self.seed, expected)
        self._store = store
        self._manifest = expected
        self._turns: dict[str, int] = {}
        self._publications: dict[tuple[str, str], _Publication] = {}
        self._pending_clarifications: dict[str, PendingClarification] = {}
        # Bounded (question, shown answer) pairs so a planner can resolve "bu",
        # "önceki cevap" after an unrelated message; analytical state stays in
        # the workspace, never here.
        self._history: dict[str, list[tuple[str, str]]] = {}
        # Series identities the catalog returned earlier in each conversation. A plan
        # naming only these may skip the discovery phase, which otherwise costs a
        # planner round trip per turn for an identity already proven. Bounded by the
        # catalog itself. Held in memory: after a restart it starts empty, so the turn
        # simply searches again, which is the previous behaviour and never less safe.
        self._proven: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def __call__(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        *,
        is_continuation: bool | None = None,
        document_ref: str | None = None,
        settings: TurnSettings | None = None,
    ) -> Answer:
        return self._run(
            session_id,
            turn_id,
            question,
            is_continuation=is_continuation,
            document_ref=document_ref,
            settings=settings,
        )

    def _restore(self, session_id: str) -> None:
        """Bring one conversation's persisted references back into this process."""
        if self._store is None or session_id in self._turns:
            return
        self._turns[session_id] = self._store.turn_count(session_id)
        for item in self._store.publications(session_id):
            self._publications[session_id, item.turn_id] = _Publication(
                SelectedResult(item.turn_id, item.result_ref, item.result_version),
                item.name,
                item.artifact_id,
            )
        with self._documents_lock:
            for document in self._store.documents(session_id):
                self._documents[session_id, document.document_ref] = _Document(
                    document.document_format,
                    document.media_type,
                    document.sha256,
                    document.byte_count,
                    document.path,
                    document.admitted_at,
                )
        self._history[session_id] = list(self._store.history(session_id, MAX_HISTORY_TURNS))

    def admit_document(self, session_id: str, media_type: str, content: bytes) -> DocumentAdmitted:
        """Admit through the upload checks and store by opaque reference; no filename is kept."""
        if not self._document_uploads:
            raise ServiceError("unavailable", 503)
        if not _IDENTIFIER.fullmatch(session_id):
            raise ServiceError("not_found", 404)
        self._restore(session_id)
        kind = _UPLOAD_KINDS.get(media_type)
        if kind is None or not content or len(content) > MAX_DOCUMENT_BYTES:
            raise ServiceError("document_rejected", 422)
        try:
            admitted = admit_upload(
                io.BytesIO(content), filename=f"upload.{kind.value}", content_type=media_type
            )
        except AdmissionError:
            raise ServiceError("document_rejected", 422) from None
        digest = hashlib.sha256(admitted.content).hexdigest()
        with self._documents_lock:
            if sum(1 for owner, _ in self._documents if owner == session_id) >= MAX_DOCUMENTS:
                raise ServiceError("capacity", 429)
            reference = uuid4().hex
            directory = self.run_root / session_id / "documents"
            try:
                directory.mkdir(parents=True, exist_ok=True)
                if directory.is_symlink() or not directory.resolve().is_relative_to(self.run_root):
                    raise OSError("document directory escaped the runtime root")
                path = directory / f"{reference}.{kind.value}"
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(admitted.content)
            except OSError:
                raise ServiceError("unavailable", 503) from None
            admitted_at = datetime.now(UTC)
            self._documents[session_id, reference] = _Document(
                kind.value,
                media_type,
                digest,
                len(admitted.content),
                path,
                admitted_at,
            )
            position = sum(1 for owner, _ in self._documents if owner == session_id)
        if self._store is not None:
            self._store.add_document(
                session_id,
                document_ref=reference,
                name=document_name(position),
                document_format=kind.value,
                media_type=media_type,
                sha256=digest,
                byte_count=len(admitted.content),
                path=path,
                admitted_at=admitted_at,
            )
        return DocumentAdmitted(
            document_ref=reference,
            document_format=kind.value,
            bytes=len(admitted.content),
            sha256=digest,
        )

    def _attachment(self, session_id: str, reference: str) -> Attachment:
        """Re-read a stored upload and require its admitted hash before any tool sees it."""
        with self._documents_lock:
            stored = self._documents.get((session_id, reference))
        if stored is None:
            raise ServiceError("invalid_document", 422)
        try:
            with stored.path.open("rb") as stream:
                content = stream.read(stored.size + 1)
        except OSError:
            raise ServiceError("invalid_document", 422) from None
        if len(content) != stored.size or hashlib.sha256(content).hexdigest() != stored.sha256:
            raise ServiceError("invalid_document", 422)
        return Attachment(
            content,
            stored.media_type,
            SourceRef(
                source_id=f"upload:{stored.sha256[:32]}",
                source_type=UPLOAD,
                locator=f"upload:{reference}",
                retrieved_at=stored.admitted_at,
                content_hash=f"sha256:{stored.sha256}",
            ),
        )

    def series_values(self, series_id: str) -> tuple[tuple[date, date, float | None], ...]:
        """A prepared series' stored observations, read-only from the verified seed.

        The seed is checked against its manifest at every start; it is opened
        read-only so that looking at it can never change what later sessions copy.
        """
        if not 1 <= len(series_id) <= 200:
            raise ServiceError("not_found", 404)
        connection = duckdb.connect(
            str(self.seed / DATABASE_NAME), read_only=True, config=dict(SANDBOX)
        )
        try:
            rows = connection.execute(
                "SELECT period_start, period_end, value FROM silver_observations"
                " WHERE series_id = ? ORDER BY period_end LIMIT 5000",
                [series_id],
            ).fetchall()
        finally:
            connection.close()
        if not rows:
            raise ServiceError("not_found", 404)
        return tuple((row[0], row[1], None if row[2] is None else float(row[2])) for row in rows)

    @property
    def catalog(self) -> ReviewedSnapshot:
        """The reviewed catalog this runner was started with; never the knowledge overlay."""
        return self._catalog

    def document_column(
        self,
        session_id: str,
        document_ref: str,
        period_column: str,
        value_column: str,
        sheet: str | None = None,
        year: int | None = None,
    ) -> tuple[tuple[tuple[date, float | None], ...], str]:
        """One monthly column of an upload, for the knowledge base (DEC-157).

        The same path a turn uses: the stored bytes are rehashed, loaded by the
        strict loaders and read by `read_column`, which refuses rather than
        guesses. Only (month end, value) pairs and the document digest leave here;
        the person declares what the numbers mean.
        """
        if not _IDENTIFIER.fullmatch(session_id) or not _IDENTIFIER.fullmatch(document_ref):
            raise ServiceError("invalid_document", 422)
        self._restore(session_id)
        attachment = self._attachment(session_id, document_ref)
        read = read_attachment(attachment, sheet=sheet, ocr=self._document_ocr)
        if read.failure is not None or read.output.source is None:
            raise ServiceError("document_rejected", 422)
        try:
            rows = read_month_values(
                grids(read.output.table, read.output.document),
                period_column,
                value_column,
                year=year,
                as_of=as_of(read.output.source),
            )
        except ColumnRefused:
            raise ServiceError("document_rejected", 422) from None
        digest = (attachment.source.content_hash or "").removeprefix("sha256:")
        return tuple((end, value) for end, value, _ in rows), digest

    def _library(self, session_id: str) -> dict[str, tuple[str, Attachment]]:
        """This conversation's documents by server-owned name, each rehashed on read."""
        with self._documents_lock:
            references = [ref for owner, ref in self._documents if owner == session_id]
        return {
            document_name(position): (reference, self._attachment(session_id, reference))
            for position, reference in enumerate(references, 1)
        }

    def selected(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        selection: SelectedResult,
        *,
        is_continuation: bool | None = None,
        document_ref: str | None = None,
        settings: TurnSettings | None = None,
    ) -> Answer:
        """Service worker entry; resolve and execute under the same runner lock."""
        try:
            return self._run(
                session_id,
                turn_id,
                question,
                selection,
                is_continuation=is_continuation,
                document_ref=document_ref,
                settings=settings,
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
        document_ref: str | None = None,
        settings: TurnSettings | None = None,
    ) -> Answer:
        # The owner's own narrowing, applied to this turn only; never a widening.
        chosen = settings or TurnSettings()
        if not _IDENTIFIER.fullmatch(session_id) or not _IDENTIFIER.fullmatch(turn_id):
            raise PreparedError("invalid_runtime_identity")
        if not self._lock.acquire(blocking=False):
            raise PreparedError("concurrent_runtime_refused")
        try:
            self._restore(session_id)
            pending = self._pending_clarifications.get(session_id)
            effective_question = question
            effective_selection = selection
            effective_document = document_ref
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
                    if effective_document is None:
                        effective_document = pending.document_ref
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
            if not (target / DATABASE_NAME).is_file():
                # First turn of this conversation, in this process or an earlier one.
                _copy(self.seed, target, self._manifest)
            if not (target / DATABASE_NAME).is_file():
                raise PreparedError("session_pool_missing")
            attachment = (
                None
                if effective_document is None
                else self._attachment(session_id, effective_document)
            )
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
                named = self._library(session_id)
                library = {name: item for name, (_, item) in named.items()}
                current = next(
                    (name for name, (ref, _) in named.items() if ref == effective_document), None
                )
                # One page read per written address; tools reuse exactly these bytes.
                turn_fetch = (
                    TurnFetchCache(self._web_url_fetch)
                    if self._web_url_fetch is not None and "web_url" not in chosen.disabled
                    else None
                )
                addresses = addresses_in(question)
                address_note = (
                    address_outline(addresses, turn_fetch)
                    if turn_fetch is not None and addresses
                    else None
                )
                document_note = document_outline(library, current)
                # A reviewed official series the pool lacks is fetched on first use,
                # and every attempt is shown in this turn's trace (DEC-155).
                acquirer = (
                    TurnAcquirer(
                        lake,
                        self._clock(),
                        sources=self._official,
                        observe=lambda item: tracer.event(
                            "acquisition",
                            f"acquisition.{item.code.value}",
                            series=item.series_id,
                            observations=item.observations,
                            missing_values=item.missing_values,
                            window_start=(
                                item.window_start.isoformat() if item.window_start else None
                            ),
                            window_end=item.window_end.isoformat() if item.window_end else None,
                            detail=item.detail,
                            from_store=item.from_store,
                        ),
                    )
                    if self._official is not None and "official_acquisition" not in chosen.disabled
                    else None
                )
                catalog, knowledge_loaded = self._apply_knowledge(lake)
                registry = self._registry(
                    lake.connection,
                    workspace,
                    lake.lineage,
                    attachment,
                    library,
                    turn_fetch,
                    acquirer=acquirer,
                    catalog=catalog,
                    disabled=chosen.disabled,
                )
                # One run per turn: what ran, with which context, and for how long.
                run_id = uuid4().hex
                store = self._store
                if store is not None:
                    # The run row exists before its first event, so everything this
                    # turn records can be stored as it happens rather than at the end.
                    store.start_run(session_id, run_id=run_id, turn_id=turn_id, question=question)
                tracer = Tracer(
                    redactions=self._redactions,
                    sink=(
                        (lambda event: store.add_event(run_id, event))
                        if store is not None
                        else None
                    ),
                )
                if self._knowledge is not None:
                    tracer.event(
                        "context",
                        "knowledge.applied",
                        catalog_digest=catalog.content_sha256,
                        reviewed=catalog is self._catalog,
                        loaded_datasets=list[JsonValue](knowledge_loaded),
                        discovery="hybrid"
                        if self._dense is not None and catalog is self._catalog
                        else "lexical",
                    )
                tracer.event(
                    "request",
                    "turn.received",
                    question_bytes=len(question.encode()),
                    is_continuation=is_continuation,
                    attached_document=effective_document is not None,
                    pending_clarification=pending is not None,
                    # How the pending clarification was read, and by whom: the
                    # person states it only when they pass is_continuation.
                    clarification=(
                        None
                        if pending is None
                        else "cancelled"
                        if is_cancel
                        else "replaced"
                        if is_new_q
                        else "merged"
                    ),
                    clarification_decided_by=(
                        None
                        if pending is None
                        else "request"
                        if is_continuation is not None
                        else "agent"
                    ),
                )
                tracer.event(
                    "context",
                    "context.assembled",
                    selected_result=(
                        effective_selection.result_ref if effective_selection is not None else None
                    ),
                    selected_version=(
                        effective_selection.version if effective_selection is not None else None
                    ),
                    workspace_results=len(workspace.names()),
                    conversation_documents=len(library),
                    history_turns=len(self._history.get(session_id, ())),
                    addresses=len(addresses),
                    address_outline_bytes=len(address_note.encode()) if address_note else 0,
                    document_outline=document_note is not None,
                )
                started = time.monotonic()
                session = Session(
                    self._provider,
                    registry,
                    catalog_continuation=True,
                    selection=selected_table,
                    require_series_discovery=self._dense is not None,
                    proven_series=frozenset(self._proven.get(session_id, ())),
                    repair_period_wording=True,
                    repair_unmatched_numbers=True,
                    documents_note=document_note,
                    address_note=address_note,
                    tracer=tracer,
                    # A clarification merge already restates the original request, and
                    # the owner may ask for fewer earlier turns than the built-in ceiling.
                    history=(
                        _recent(self._history.get(session_id, ()), chosen.history_turns)
                        if pending is None or is_cancel or is_new_q
                        else ()
                    ),
                    tools_required=bool(addresses_in(question)) or document_ref is not None,
                    # Named from this turn's catalog, knowledge-base entries included.
                    series_names=series_display_names(catalog),
                )
                try:
                    answered = session.answer(
                        effective_question, lake.connection, workspace=workspace, remember=name
                    )
                except Exception as failure:
                    # The catalog vouched for whatever it returned, even if the turn
                    # failed afterwards, so the next turn need not ask again.
                    self._proven.setdefault(session_id, set()).update(session.newly_proven)
                    # A failed or cancelled turn is still a run someone can open and read.
                    cancelled = isinstance(failure, TurnCancelled)
                    if cancelled:
                        tracer.event("request", "turn.cancelled", at=str(failure))
                    if self._store is not None:
                        self._store.finish_run(
                            run_id,
                            status="cancelled" if cancelled else "failed",
                            duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                            error=type(failure).__name__,
                            events=tracer.events,
                        )
                    raise
                self._proven.setdefault(session_id, set()).update(session.newly_proven)
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
                    self._materialize_gold(lake, name, published, tracer)
                    artifact = workspace.resolve(name).artifact_id
                    self._publications[session_id, turn_id] = _Publication(
                        SelectedResult(turn_id, answer.result.result_ref, answer.result.version),
                        name,
                        artifact,
                    )
                    if self._store is not None:
                        self._store.add_publication(
                            session_id,
                            turn_id=turn_id,
                            name=name,
                            artifact_id=artifact,
                            result_ref=answer.result.result_ref,
                            result_version=answer.result.version,
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
                        document_ref=effective_document,
                    )
                if self._store is not None:
                    self._store.finish_run(
                        run_id,
                        status="completed",
                        duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                        answer_status=answer.status.value,
                        result_ref=answer.result.result_ref if answer.result else None,
                        events=tracer.events,
                    )
                turns = self._history.setdefault(session_id, [])
                turns.append((question, answer.text))
                del turns[:-MAX_HISTORY_TURNS]
                self._remember(session_id, turn_id, question, answer, effective_document)
                return answer

        finally:
            self._lock.release()

    def _apply_knowledge(self, lake: Lakehouse) -> tuple[ReviewedSnapshot, list[str]]:
        """This turn's catalog, and the user datasets newly loaded into this session's lake.

        A user dataset enters the session's own lakehouse — never the prepared seed —
        through the same bronze/silver path as any series: its declared content as
        the bronze artifact, its declaration as the silver series, its numbers as
        observations. A version already present is left as it is.
        """
        if self._knowledge is None:
            return self._catalog, []
        datasets = self._knowledge.datasets(include_archived=False)
        catalog = effective_snapshot(self._catalog, datasets, self._knowledge.notes())
        loaded: list[str] = []
        for item in datasets:
            present = lake.connection.execute(
                "SELECT 1 FROM silver_series WHERE series_id = ?", [item.series_id]
            ).fetchone()
            if present is not None:
                continue
            content = json.dumps(
                {"series_id": item.series_id, "sha256": item.content_sha256()}, sort_keys=True
            ).encode()
            artifact = lake.record_artifact(
                content,
                source=SourceRef(
                    source_id=f"knowledge:{item.slug}",
                    source_type="user-declared",
                    locator=f"knowledge:{item.slug}.v{item.version}",
                    content_hash=f"sha256:{item.content_sha256()}",
                ),
                media_type="application/json",
                recorded_at=item.created_at,
            )
            lake.register_series(
                item.series_id,
                title=item.title,
                semantics=item.semantics(),
                artifact_id=artifact.artifact_id,
            )
            lake.append_observations(item.series_id, list(item.observations))
            loaded.append(item.series_id)
        return catalog, loaded

    def _materialize_gold(
        self,
        lake: Lakehouse,
        name: str,
        published: AnalyticalResult | None,
        tracer: Tracer,
    ) -> None:
        """Write a published period table into gold, so the store holds it too.

        This runs after the turn's answer was gated, so nothing in this answer was
        checked against a cell this turn wrote. Later turns read the table by
        identity — through SQL over `gold_cells` or the verifier's store recheck —
        and each column carries the lineage node of the result that produced it.
        A table that cannot be written traceably is simply not written: the
        workspace remains its record, and the trace says which it was.
        """
        if published is None:
            return
        try:
            table = gold_from_result(published, table_id=name, lineage=lake.lineage)
            rows = persist_gold(lake.connection, table) if table is not None else 0
        except (GoldError, LineageError, SemanticsError) as refused:
            # Writing gold is a copy for later reads; it never costs the turn its answer.
            tracer.event("store", "gold.refused", table=name, reason=type(refused).__name__)
            return
        tracer.event(
            "store",
            "gold.materialized" if rows else "gold.skipped",
            table=name,
            columns=len(table.columns) if table is not None else 0,
            rows=rows,
            incomplete=list(table.incomplete_columns()) if table is not None else [],
        )

    def _remember(
        self,
        session_id: str,
        turn_id: str,
        question: str,
        answer: Answer,
        document_ref: str | None,
    ) -> None:
        """Persist the turn's two messages, so reopening shows the conversation."""
        if self._store is None:
            return
        self._store.append_message(
            session_id, turn_id=turn_id, role="user", text=question, document_ref=document_ref
        )
        self._store.append_message(
            session_id,
            turn_id=turn_id,
            role="assistant",
            text=answer.text,
            status=answer.status.value,
            result_ref=answer.result.result_ref if answer.result is not None else None,
            result_version=answer.result.version if answer.result is not None else None,
        )
        found = self._store.conversation(session_id)
        if found is not None and found.title == DEFAULT_TITLE:
            # The first question names the conversation until the user renames it.
            self._store.update_conversation(session_id, title=" ".join(question.split())[:60])

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
        self,
        connection: duckdb.DuckDBPyConnection,
        workspace: Workspace,
        lineage: Lineage,
        attachment: Attachment | None = None,
        library: dict[str, Attachment] | None = None,
        turn_fetch: TurnFetchCache | None = None,
        *,
        acquirer: TurnAcquirer | None = None,
        catalog: ReviewedSnapshot | None = None,
        disabled: frozenset[str] = frozenset(),
    ) -> ToolRegistry:
        fetch = turn_fetch if turn_fetch is not None else self._web_url_fetch
        catalog = catalog if catalog is not None else self._catalog
        inspector = PreparedSeriesInspector(catalog)
        if acquirer is not None:
            inspector = AcquiringInspector(inspector, acquirer)
        # Existing code-reviewed names only. Free catalog/source metadata belongs
        # in catalog continuation's USER data, never a SYSTEM tool description.
        names = prepared_series_names(connection)
        registry = ToolRegistry()
        registry.register(
            make_catalog_search_tool(
                snapshot_bytes=(
                    self._catalog_bytes
                    if catalog is self._catalog
                    else catalog.model_dump_json().encode("utf-8")
                ),
                # The dense index is bound to the reviewed digest; with knowledge-base
                # entries applied, discovery is lexical for this turn.
                dense=self._dense if catalog is self._catalog else None,
            )
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
                document_fetch=fetch,
                attachment=attachment,
                document_ocr=None if "document_ocr" in disabled else self._document_ocr,
                library=library,
            )
        )
        for make in (make_anomaly_tool, make_causality_tool):
            registry.register(make(connection, lineage=lineage, inspector=inspector))
        if self._search_backend is not None and "web_search" not in disabled:
            registry.register(make_web_search_tool(backend=self._search_backend))
        if self._web_url_fetch is not None or attachment is not None or library:
            # The cell proof lives in this session's own lineage, where the gate
            # and the proof builder re-read it; the document itself is not kept.
            registry.register(
                make_web_url_tool(
                    fetch=fetch,
                    attachment=attachment,
                    lineage=lineage,
                    ocr=None if "document_ocr" in disabled else self._document_ocr,
                    library=library,
                    endpoints=turn_fetch.endpoints if turn_fetch is not None else None,
                )
            )
        return registry
