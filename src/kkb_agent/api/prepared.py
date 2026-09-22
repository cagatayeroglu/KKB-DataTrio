"""Immutable local preparation snapshot and isolated, inspected API analysis runner."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal
from uuid import uuid4

import duckdb
from pydantic import Field, JsonValue, SecretStr

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.cancellation import TurnCancelled
from kkb_agent.agent.loop import MAX_HISTORY_TURNS, PlanningFailed
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.selection import SelectedTable, SelectionError
from kkb_agent.agent.trust_adapter import as_answered
from kkb_agent.agent.trust_session import TrustSession
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.agent.workspace import WorkspaceError
from kkb_agent.api.contracts import (
    MAX_DOCUMENT_BYTES,
    MAX_DOCUMENTS,
    MAX_SESSIONS,
    MAX_TURNS,
    Answer,
    DocumentAdmitted,
    Result,
)
from kkb_agent.api.projection import OutputRefused, project_answer, project_result, safe_text
from kkb_agent.api.proof import build_proof
from kkb_agent.api.service import SelectedResult, ServiceError, TurnSettings
from kkb_agent.api.store import DEFAULT_TITLE, ConversationStore
from kkb_agent.catalog.directory import SourceDirectory
from kkb_agent.catalog.discovered import DiscoveredStore
from kkb_agent.catalog.expansion import expand_groups
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import (
    MAX_SNAPSHOT_BYTES,
    ReviewedSnapshot,
    is_source_group,
    load_reviewed_snapshot,
    series_display_names,
)
from kkb_agent.core import AnalyticalResult, SourceRef
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionCode,
    OfficialSources,
    TurnAcquirer,
)
from kkb_agent.ingest.address_outline import TurnFetchCache, address_outline
from kkb_agent.ingest.attached import SOURCE_TYPE as UPLOAD
from kkb_agent.ingest.attached import Attachment
from kkb_agent.ingest.evds_load import EvdsLoadCode
from kkb_agent.ingest.fetched import TABLE_MEDIA_TYPES, source_id_for
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchRequest, FetchSuccess
from kkb_agent.ingestion_policy import MIME_TYPES, AdmissionError, FileKind, admit_upload
from kkb_agent.knowledge import KnowledgeStore, effective_snapshot
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.gold import GoldError, gold_from_result, persist_gold
from kkb_agent.lakehouse.lineage import Lineage, LineageError
from kkb_agent.lakehouse.semantics import SemanticsError
from kkb_agent.lakehouse.store import DATABASE_NAME, SANDBOX, Lakehouse
from kkb_agent.llm.provider import LLMProvider, ProviderError
from kkb_agent.pdf_ocr import CachedOcr, OcrProvider
from kkb_agent.tools import (
    make_anomaly_tool,
    make_catalog_search_tool,
    make_causality_tool,
    make_change_detection_tool,
    make_document_read_tool,
    make_lakehouse_tool,
    make_table_transform_tool,
    make_web_search_tool,
    make_web_url_tool,
)
from kkb_agent.tools._document_column import ColumnRefused, read_month_values
from kkb_agent.tools._document_library import describe_document, document_name, document_outline
from kkb_agent.tools._document_value import as_of, grids
from kkb_agent.tools.promotion import (
    PromotionProposal,
    PromotionReceipt,
    make_promote_series_tool,
)
from kkb_agent.tools.web_search import SearchBackend
from kkb_agent.tools.web_url import Fetcher, addresses_in, read_attachment

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.catalog.hybrid import CatalogDenseStage

MAX_POOL_BYTES = 1024 * 1024 * 1024
MAX_POOL_FILES = 10000
_IDENTIFIER = re.compile(r"[a-f0-9]{32}\Z")
#: How long a stored table's read waits for another read before it answers "busy".
STORED_READ_WAIT_SECONDS = 5.0


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
    #: Titles of the catalogue entries the clarification offered; a message naming one of
    #: them answers it.
    offered: tuple[str, ...] = ()


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
#: What a stored document can be. A picture is stored as the page it was wrapped into.
_STORED_FORMATS: dict[FileKind, Literal["csv", "xlsx", "pdf", "html"]] = {
    FileKind.CSV: "csv",
    FileKind.XLSX: "xlsx",
    FileKind.PDF: "pdf",
    FileKind.HTML: "html",
}
#: A user-written https address; the bound keeps a stray field out of the fetcher.
_WEB_ADDRESS = re.compile(r"https://[^\s<>\"'`]{1,2000}")


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
    "şimdi de ",
)
#: Shown with an abstention when a read of the question's address was lost after every attempt.
#: Shown with an abstention when an official series could not be fetched after every attempt.
SOURCE_UNREACHED_NOTICE = (
    "İstenen seri resmî kaynağında var, ancak kaynak bu turda yanıt vermedi (zaman aşımı ya da "
    "bağlantı hatası). Aynı soruyu yeniden sormak sonucu değiştirebilir; alınan aylar saklandı."
)
#: Shown with an abstention when the source lists the series and publishes nothing for it.
SOURCE_EMPTY_NOTICE = (
    "İstenen seri resmî kaynağın dizininde var, ancak kaynak bu seri için çekilen yıllarda "
    "hiç gözlem yayımlamıyor (ör. yayını durdurulmuş bir seri). Aşağıdaki yakın kayıtlardan "
    "birini seçebilir ya da başka bir dönem/kaynak belirtebilirsiniz."
)
ADDRESS_UNREAD_NOTICE = (
    "Sorudaki adresin bazı kaynakları bu turda okunamadı (zaman aşımı ya da bağlantı hatası). "
    "Aynı soruyu yeniden sormak sonucu değiştirebilir."
)
#: A short message that answers a held save offer with yes. Deliberately a small
#: closed set rather than a parser: anything else is treated as a new question, so a
#: message the server cannot read plainly never writes to the knowledge base.
_CONFIRMATIONS: Final = frozenset(
    {
        "evet",
        "evet.",
        "tamam",
        "tamam.",
        "onaylıyorum",
        "onaylıyorum.",
        "onayliyorum",
        "kaydet",
        "kaydet.",
        "olur",
        "olur.",
        "yes",
        "ok",
        "okay",
    }
)


def _discovery_of(dense: CatalogDenseStage | None, catalog: ReviewedSnapshot) -> str:
    """What the trace records discovery ran as, for this catalogue and this generation."""
    if dense is None:
        return "lexical"
    covered = dense.index.covering(catalog)
    if not covered:
        return "lexical"
    if len(covered) == len(catalog.series):
        return "hybrid"
    return f"hybrid over {len(covered)} of {len(catalog.series)}"


def _confirms(question: str) -> bool:
    """Whether this message is the person saying yes to the offer they were shown."""
    return " ".join(question.strip().lower().split()) in _CONFIRMATIONS


_STANDALONE_QUESTION = re.compile(r"\b(?:ne kadar|nasıl|kaç|nedir|hangi)\b")
_MULTISTEP_REQUEST = re.compile(r"\b(?:getir|göster|hesapla|arındır|ekle|karşılaştır)\b")


def _refused_save(code: str) -> Answer:
    """A save that could not happen, said plainly and without writing anything."""
    return Answer(
        status=AnswerStatus.ABSTAINED,
        text="Kayıt yapılmadı.",
        omitted_claims=0,
        notices=(code,),
    )


def _offer_payload(proposal: PromotionProposal) -> dict[str, object]:
    """A held offer as plain JSON, so a restart answers the same offer it made."""
    return {
        **{
            field: getattr(proposal, field)
            for field in (
                "slug",
                "title",
                "unit",
                "scale",
                "stock_flow",
                "aggregation",
                "cumulative",
                "base_year",
                "session_id",
                "document_ref",
                "document_sha256",
                "period_column",
                "value_column",
                "sheet",
                "year",
                "summary",
            )
        },
        "observations": [[end.isoformat(), value] for end, value in proposal.observations],
    }


def _offer_from_payload(payload: Mapping[str, object]) -> PromotionProposal | None:
    """The offer a restart found, or None when the row cannot be read as one."""
    try:
        rows = payload["observations"]
        if not isinstance(rows, list):
            return None
        observations = tuple(
            (date.fromisoformat(str(row[0])), None if row[1] is None else float(row[1]))
            for row in rows
            if isinstance(row, list) and len(row) == 2
        )
        if len(observations) != len(rows):
            return None
        return PromotionProposal(
            slug=str(payload["slug"]),
            title=str(payload["title"]),
            unit=str(payload["unit"]),
            scale=str(payload["scale"]),
            stock_flow=str(payload["stock_flow"]),
            aggregation=str(payload["aggregation"]),
            cumulative=str(payload["cumulative"]),
            base_year=None if payload["base_year"] is None else int(str(payload["base_year"])),
            session_id=str(payload["session_id"]),
            document_ref=str(payload["document_ref"]),
            document_sha256=str(payload["document_sha256"]),
            period_column=str(payload["period_column"]),
            value_column=str(payload["value_column"]),
            sheet=None if payload["sheet"] is None else str(payload["sheet"]),
            year=None if payload["year"] is None else int(str(payload["year"])),
            observations=observations,
            summary=str(payload["summary"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


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

    A long explanation of a chosen series is still an answer. Only an explicit
    new-question marker or a standalone question/multi-action request replaces
    the pending question. The request's explicit continuation flag takes priority.
    """
    q = question.strip().lower()
    # A teammate's trace and live E1b (2026-09-19): the entry picked from the offered list
    # ("Konut Kredisi (TL, Akım, %) (Kredi Faiz Oranları (Akım), EVDS/..., haftalık, ...)")
    # is long and full of commas, so the length rule below called it a new question and
    # the pending request was dropped. Naming an offered entry is the answer, at any length.
    named = " ".join(q.split())
    if any(" ".join(title.lower().split()) in named for title in pending.offered if title):
        return False
    if any(q.startswith(prefix) for prefix in _NEW_QUESTION_PREFIXES):
        return True
    if selection is not None and pending.selection is not None and selection != pending.selection:
        return True
    if q.endswith("?") and _STANDALONE_QUESTION.search(q):
        return True
    return len(_MULTISTEP_REQUEST.findall(q)) >= 2 and not any(
        word in q for word in ("kullan", "olsun", "seç")
    )


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
        document_vision: bool = False,
        store: ConversationStore | None = None,
        official: OfficialSources | None = None,
        clock: Callable[[], date] = lambda: datetime.now(UTC).date(),
        knowledge: KnowledgeStore | None = None,
        search_backend: SearchBackend | None = None,
        source_directory: SourceDirectory | None = None,
        discovered: DiscoveredStore | None = None,
        trust_loop: bool = False,
    ):
        #: Run the question as one model-driven loop instead of the planned turn.
        self._trust_loop = trust_loop
        self._catalog = load_reviewed_snapshot(catalog_bytes)
        # Operator switch (DEC-176): the sources' own listings as a second catalogue tier.
        self._directory = source_directory
        # The EVDS series lists opened so far (DEC-177); without it datagroups stay hidden.
        self._discovered = discovered
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
        self._document_ocr = CachedOcr(document_ocr) if document_ocr is not None else None
        # Operator switch for fetching a reviewed official series on first use (DEC-155).
        self._official = (
            replace(official, listed_evds=discovered.lookup)
            if official is not None and discovered is not None
            else official
        )
        self._clock = clock
        # The editable knowledge base layered over the reviewed catalog (DEC-157).
        self._knowledge = knowledge
        # Operator-configured discovery backend (DEC-134, DEC-158); absent means no tool.
        self._search_backend = search_backend
        self._documents: dict[tuple[str, str], _Document] = {}
        self._documents_lock = threading.Lock()
        self._provider = provider
        # Operator switch for reading a page that has no text layer with the vision
        # model (DEC-129). Without it such a page is reported unreadable, never guessed.
        self._vision = document_vision
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
        #: One held save offer per conversation, made by a turn and answered by the
        #: next message. Never a write: the write happens when the person says yes.
        self._pending_promotions: dict[str, PromotionProposal] = {}
        self._promote: Callable[[PromotionProposal], PromotionReceipt] | None = None
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

    def _restore(self, session_id: str, current_turn_id: str | None = None) -> None:
        """Bring one conversation's persisted references back into this process."""
        with self._lock:
            self._restore_locked(session_id, current_turn_id)

    def _restore_locked(self, session_id: str, current_turn_id: str | None = None) -> None:
        if self._store is None or session_id in self._turns:
            return
        if len(self._turns) >= MAX_SESSIONS:
            # The runner is single-turn under _lock. Drop the oldest idle in-memory
            # handle only; DuckDB, messages and pending intent remain on disk.
            oldest = next(iter(self._turns))
            del self._turns[oldest]
            self._pending_clarifications.pop(oldest, None)
            self._history.pop(oldest, None)
            self._proven.pop(oldest, None)
            for key in tuple(self._publications):
                if key[0] == oldest:
                    del self._publications[key]
            with self._documents_lock:
                for key in tuple(self._documents):
                    if key[0] == oldest:
                        del self._documents[key]
        self._turns[session_id] = self._store.turn_count(session_id, current_turn_id)
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
        # The catalog vouched for these in an earlier turn of this conversation; without
        # them a reopened chat pays a planning round trip to prove them again (H4).
        restored_proven = self._store.proven_series(session_id)
        if restored_proven:
            self._proven.setdefault(session_id, set()).update(restored_proven)
        held = self._store.pending_promotion(session_id)
        if held is not None:
            restored = _offer_from_payload(held)
            if restored is not None:
                self._pending_promotions[session_id] = restored
        saved = self._store.pending_clarification(session_id)
        if saved is not None:
            try:
                selected = saved.get("selection")
                selection = SelectedResult(**selected) if isinstance(selected, dict) else None
                original = saved["original_question"]
                clarifications = saved["clarifications"]
                offered = saved["offered"]
                document_ref = saved.get("document_ref")
                if (
                    isinstance(original, str)
                    and isinstance(clarifications, list)
                    and all(isinstance(item, str) for item in clarifications)
                    and isinstance(offered, list)
                    and all(isinstance(item, str) for item in offered)
                    and (document_ref is None or isinstance(document_ref, str))
                ):
                    self._pending_clarifications[session_id] = PendingClarification(
                        original, tuple(clarifications), selection, document_ref, tuple(offered)
                    )
            except (KeyError, TypeError, ValueError):
                pass

    def delete_session(self, session_id: str) -> None:
        """Remove only one server-issued session's files after its turn has stopped.

        The prepared seed and shared acquisition/directory roots are never targets.
        The caller must have authorized the deletion and ensured no turn uses this
        session; the runner lock also refuses a concurrent execution.
        """
        if not _IDENTIFIER.fullmatch(session_id):
            raise PreparedError("invalid_runtime_identity")
        if not self._lock.acquire(blocking=False):
            raise PreparedError("concurrent_runtime_refused")
        try:
            target = self.run_root / session_id
            if target.is_symlink() or not target.resolve().is_relative_to(self.run_root):
                raise PreparedError("linked_path_refused")
            if target.exists():
                if not target.is_dir():
                    raise PreparedError("session_path_invalid")
                shutil.rmtree(target)
            with self._documents_lock:
                for key in tuple(self._documents):
                    if key[0] == session_id:
                        del self._documents[key]
            self._turns.pop(session_id, None)
            self._pending_clarifications.pop(session_id, None)
            self._pending_promotions.pop(session_id, None)
            if self._store is not None:
                self._store.set_pending_clarification(session_id, None)
                self._store.set_pending_promotion(session_id, None)
            self._history.pop(session_id, None)
            self._proven.pop(session_id, None)
            for key in tuple(self._publications):
                if key[0] == session_id:
                    del self._publications[key]
        finally:
            self._lock.release()

    def admit_document_from_url(self, session_id: str, url: str) -> DocumentAdmitted:
        """Fetch a tabular document at a user-written address and admit it like an upload.

        The address is the person's own request, typed in the knowledge-base form,
        so it plays the same role the question does for `web_url`: only an https
        table is fetched, through the operator's `safe_fetch` (GET-only, no cookie,
        DNS/TLS/redirect/byte/time bounds), and the bytes then meet the exact upload
        admission rules. No new download or parsing code is introduced, and the
        planner is not involved. Persisting the numbers into the knowledge base is
        a second, explicit step over the admitted document, with a human-confirmed
        declaration - nothing is stored to the catalogue from here.
        """
        if self._web_url_fetch is None or not self._document_uploads:
            raise ServiceError("unavailable", 503)
        if not isinstance(url, str) or not _WEB_ADDRESS.fullmatch(url):
            raise ServiceError("document_rejected", 422)
        outcome = self._web_url_fetch(
            FetchRequest(
                source_ref=source_id_for(url),
                url=SecretStr(url),
                accepted_media_types=TABLE_MEDIA_TYPES,
            )
        )
        if isinstance(outcome, FetchFailure):
            raise ServiceError("document_rejected", 422)
        if not isinstance(outcome, FetchSuccess):  # pragma: no cover - FetchOutcome is closed
            raise TypeError("fetch returned neither a success nor a failure")
        return self.admit_document(session_id, outcome.media_type, outcome.content)

    def admit_document(self, session_id: str, media_type: str, content: bytes) -> DocumentAdmitted:
        """Admit through the upload checks and store by opaque reference; no filename is kept."""
        if not self._document_uploads:
            raise ServiceError("unavailable", 503)
        if not _IDENTIFIER.fullmatch(session_id):
            raise ServiceError("not_found", 404)
        self._restore(session_id)
        return self._admit_locked(session_id, media_type, content)

    def _admit_locked(self, session_id: str, media_type: str, content: bytes) -> DocumentAdmitted:
        """The admission itself, for a caller that has already restored the session.

        A turn holds the runner's lock, and `_restore` takes it: calling the public
        method from inside a turn would wait for a lock the turn itself owns. The
        checks below are the same ones either way; only the restore is the caller's.
        """
        if not self._document_uploads:
            raise ServiceError("unavailable", 503)
        kind = _UPLOAD_KINDS.get(media_type)
        if kind is None or not content or len(content) > MAX_DOCUMENT_BYTES:
            raise ServiceError("document_rejected", 422)
        try:
            admitted = admit_upload(
                io.BytesIO(content), filename=f"upload.{kind.value}", content_type=media_type
            )
        except AdmissionError:
            raise ServiceError("document_rejected", 422) from None
        # A picture is admitted as the one-page document it was wrapped into (DEC-179).
        kind, media_type = admitted.kind, MIME_TYPES[admitted.kind]
        digest = hashlib.sha256(admitted.content).hexdigest()
        with self._documents_lock:
            # The same bytes are the same document. A client timeout that the server
            # completed anyway, a retried address and re-attaching a file that was
            # taken off the question all used to spend one of `MAX_DOCUMENTS`, so
            # four tries at one table refused the fifth (findings F2-upl-5, F4-bt-3).
            # Returning the reference already admitted keeps every receipt that cites
            # it valid, because what it points at is byte-identical.
            for (owner, known), stored in self._documents.items():
                if owner == session_id and stored.sha256 == digest and stored.kind == kind.value:
                    return DocumentAdmitted(
                        document_ref=known,
                        document_format=_STORED_FORMATS[kind],
                        bytes=stored.size,
                        sha256=digest,
                    )
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
            document_format=_STORED_FORMATS[kind],
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

    @property
    def dense(self) -> CatalogDenseStage | None:
        """The vector generation discovery may use, whichever catalogue it covers."""
        return self._dense

    def _dense_for(self, catalog: ReviewedSnapshot) -> CatalogDenseStage | None:
        """The generation this turn may search, whatever the catalogue has gained since.

        A generation used to be dropped whenever the catalogue digest had moved, so one
        knowledge-base entry made every turn's discovery lexical until someone rebuilt all
        8,374 vectors. The generation is kept and the index decides per identity which
        series its vectors can still answer for (N27).
        """
        return self._dense

    def _keep_read(self, session_id: str, media_type: str, content: bytes) -> None:
        """Admit the bytes a turn just read from an address, without reading them again.

        Taking an address into the conversation is not keeping it: this is the same
        admission an upload meets - media type, size, hash, the conversation's document
        capacity - and the same sha256 dedup, so the same table read twice is one
        document. Persisting it into the knowledge base still needs the person's word.
        A refusal here is not the turn's problem: the answer was already read.
        """
        try:
            self._admit_locked(session_id, media_type, content)
        except (ServiceError, PreparedError):
            return

    def _offer(self, session_id: str, proposal: PromotionProposal) -> None:
        """Hold what a turn offered to save, in memory and on disk. No write happens."""
        self._pending_promotions[session_id] = proposal
        if self._store is not None:
            self._store.set_pending_promotion(session_id, _offer_payload(proposal))

    def _drop_offer(self, session_id: str) -> None:
        self._pending_promotions.pop(session_id, None)
        if self._store is not None:
            self._store.set_pending_promotion(session_id, None)

    def use_promotion(self, save: Callable[[PromotionProposal], PromotionReceipt]) -> None:
        """Bind the knowledge base's own validated write, late, like the dense stage.

        The service is built after this runner because it reads from it; this is the
        one direction back, and it carries no owner or session token - the proposal
        already names its conversation and the service resolves its owner itself.
        """
        self._promote = save

    def use_directory(self, directory: SourceDirectory) -> None:
        """Install a refreshed source directory for later turns (DEC-177).

        The running turn keeps the catalogue it started with. The vectors cover the new
        catalogue only after they are built again; until then discovery says it is lexical.
        """
        self._directory = directory

    def use_dense(self, stage: CatalogDenseStage) -> None:
        """Install a newly built generation for later turns; the profile may not change.

        The running turn keeps the stage it started with: a registry is built once
        per turn. A generation is never edited in place, so the one replaced here
        stays readable on disk.
        """
        if self._dense is not None and stage.index.profile != self._dense.index.profile:
            raise PreparedError("catalog_index_mismatch")
        self._dense = stage

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
            self._restore_locked(session_id, turn_id)
            if session_id in self._turns:
                self._turns[session_id] = self._turns.pop(session_id)
            held = self._pending_promotions.get(session_id)
            if held is not None:
                if _confirms(question):
                    return self._save_offer(session_id, turn_id, held)
                # Anything but a plain yes leaves the offer behind and is answered as
                # the question it is. Nothing is written on a message nobody can read.
                self._drop_offer(session_id)
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
                    if self._store is not None:
                        self._store.set_pending_clarification(session_id, None)
                    effective_question = question
                    effective_selection = selection
                elif is_continuation is not True and _is_new_question(question, selection, pending):
                    is_new_q = True
                    self._pending_clarifications.pop(session_id, None)
                    if self._store is not None:
                        self._store.set_pending_clarification(session_id, None)
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
                # The outline reads a page without a text layer with the same OCR the tools
                # use (cached, so the model is asked once per page), unless the turn disabled it.
                outline_ocr = None if "document_ocr" in chosen.disabled else self._document_ocr
                addresses = addresses_in(question)
                address_note = (
                    address_outline(
                        addresses, turn_fetch, partial(describe_document, ocr=outline_ocr)
                    )
                    if turn_fetch is not None and addresses
                    else None
                )
                document_note = document_outline(library, current, outline_ocr)
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
                    session_id=session_id,
                    references={name: ref for name, (ref, _) in named.items()},
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
                        discovery=_discovery_of(self._dense_for(catalog), catalog),
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
                    address_reads=list(turn_fetch.log) if turn_fetch is not None else [],
                    document_outline=document_note is not None,
                )
                started = time.monotonic()
                session = Session(
                    self._provider,
                    registry,
                    model=chosen.model,
                    catalog_continuation=True,
                    selection=selected_table,
                    require_series_discovery=self._dense is not None,
                    proven_series=frozenset(self._proven.get(session_id, ())),
                    # What the catalogue lists is a known identity; the inspector still
                    # checks each one against its declaration when it is read.
                    known_series=frozenset(
                        item.record.series_id
                        for item in catalog.series
                        if not is_source_group(item)
                    ),
                    repair_period_wording=True,
                    repair_unmatched_numbers=True,
                    # The jury values the reading beside the figures; one more writer call.
                    commentary=True,
                    repair_runtime_refusals=True,
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
                    today=self._clock(),
                    acquisition_notes=lambda: (
                        tuple(
                            f"{item.series_id}: "
                            + (
                                "önceden edinilmiş resmi kaynak önbelleğinden bu turda yüklendi."
                                if item.from_store
                                else "resmi kaynaktan bu turda edinildi."
                            )
                            for item in acquirer.attempts
                            if item.code is AcquisitionCode.ACQUIRED
                        )
                        if acquirer is not None
                        else ()
                    ),
                )
                try:
                    if self._trust_loop:
                        # One model-driven loop in place of the planned turn. The
                        # answer is translated into the same shape the projection
                        # already reads, so nothing downstream changes.
                        turn = TrustSession(
                            provider=self._provider,
                            registry=registry,
                            model=chosen.model,
                            connection=lake.connection,
                        ).answer(effective_question)
                        answered = as_answered(effective_question, turn.outcome, turn.answer)
                    else:
                        answered = session.answer(
                            effective_question, lake.connection, workspace=workspace, remember=name
                        )
                except Exception as failure:
                    # The catalog vouched for whatever it returned, even if the turn
                    # failed afterwards, so the next turn need not ask again.
                    self._remember_proven(session_id, session.newly_proven)
                    self._fail_run(run_id, failure, started=started, tracer=tracer)
                    raise
                try:
                    self._remember_proven(session_id, session.newly_proven)
                    published = workspace.value_of(name) if name in workspace.names() else None
                    related = (
                        workspace.related_results(workspace.resolve(name)) if published else {}
                    )
                    answer = project_answer(
                        answered,
                        turn_id=turn_id,
                        published=published,
                        related=tuple(
                            (item, build_proof(lake.connection, item, secrets=self._redactions))
                            for item in related.values()
                        ),
                        secrets=self._redactions,
                        proof=(
                            build_proof(lake.connection, published, secrets=self._redactions)
                            if published is not None
                            else None
                        ),
                    )
                    if (
                        answer.status is AnswerStatus.ABSTAINED
                        and acquirer is not None
                        and any(
                            item.code is AcquisitionCode.RETRIEVAL_FAILED
                            for item in acquirer.attempts
                        )
                    ):
                        # The series exists and has a route; the source did not answer this time.
                        answer = answer.model_copy(
                            update={"notices": (*answer.notices, SOURCE_UNREACHED_NOTICE)}
                        )
                    if (
                        answer.status is AnswerStatus.ABSTAINED
                        and acquirer is not None
                        and any(
                            item.detail == EvdsLoadCode.NO_OBSERVATIONS.value
                            for item in acquirer.attempts
                        )
                    ):
                        # "Not found" would be untrue: the series is listed, the source is silent.
                        answer = answer.model_copy(
                            update={"notices": (*answer.notices, SOURCE_EMPTY_NOTICE)}
                        )
                    if (
                        answer.status is AnswerStatus.ABSTAINED
                        and turn_fetch is not None
                        and turn_fetch.transient_failures()
                    ):
                        # "Check the data coverage" is the wrong advice when the page's own
                        # script or data did not arrive; asking again may simply work.
                        answer = answer.model_copy(
                            update={"notices": (*answer.notices, ADDRESS_UNREAD_NOTICE)}
                        )
                    # How the turn ended, in the trace itself: an abstention or a
                    # clarification never reaches the answer gate, so without this the
                    # record stops at the last plan and never says what was shown.
                    tracer.event(
                        "answer",
                        f"turn.{answer.status.value}",
                        omitted_claims=answer.omitted_claims,
                        published=answer.result is not None,
                        clarification=answered.planned.plan.clarification,
                        detail=answer.text,
                    )
                    # Only retain references that survived publication AND projection.
                    # Bounded by the existing session/turn limits; never rebuild this
                    # ownership map by scanning arbitrary stored result digests.
                    if answer.result is not None:
                        self._materialize_gold(lake, name, published, tracer)
                        for related_name, item in related.items():
                            self._materialize_gold(lake, related_name, item, tracer)
                        artifact = workspace.resolve(name).artifact_id
                        self._publications[session_id, turn_id] = _Publication(
                            SelectedResult(
                                turn_id, answer.result.result_ref, answer.result.version
                            ),
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
                    # A turn that answered is not waiting for anything, whatever the gate
                    # said about its prose: a withheld sentence leaves a QUALIFIED status
                    # and that used to keep the old clarification armed, so the composer
                    # went on offering "bekleyen netleştirmeyi bırak" under a finished
                    # answer and the next free question was merged into the old prompt
                    # (live 2026-09-21).
                    if not answer.needs_clarification:
                        self._pending_clarifications.pop(session_id, None)
                        if self._store is not None:
                            self._store.set_pending_clarification(session_id, None)
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
                            offered=tuple(
                                item.title
                                for item in (answer.selection.others if answer.selection else ())
                            ),
                        )
                        if self._store is not None:
                            active = self._pending_clarifications[session_id]
                            self._store.set_pending_clarification(
                                session_id,
                                {
                                    "original_question": active.original_question,
                                    "clarifications": list(active.clarifications),
                                    "selection": (
                                        {
                                            "turn_id": active.selection.turn_id,
                                            "result_ref": active.selection.result_ref,
                                            "version": active.selection.version,
                                        }
                                        if active.selection is not None
                                        else None
                                    ),
                                    "document_ref": active.document_ref,
                                    "offered": list(active.offered),
                                },
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
                except Exception as failure:
                    # Publication, proof and gold writing come after a good answer, but
                    # a failure here still ends the run: without this the row stayed
                    # 'running' until the next start-up sweep (finding A3b).
                    self._fail_run(run_id, failure, started=started, tracer=tracer)
                    raise

        finally:
            self._lock.release()

    def _save_offer(self, session_id: str, turn_id: str, held: PromotionProposal) -> Answer:
        """Write the offer the person just approved. Deterministic, start to finish.

        No planner and no writer run, nothing is fetched, and the document is not
        parsed again: the months were read when the offer was made. What is checked
        again is the one thing that could have changed underneath it - the document
        this conversation holds under that reference, and its digest. A save is
        recorded as a receipt, never as an `AnalyticalResult`: nothing was computed.
        """
        self._drop_offer(session_id)
        # "evet" answered the offer, not whatever clarification an earlier turn left
        # waiting. Kept, it was prepended to the next free question as "Orijinal istek:"
        # and the reader's new request was answered as the old one (live 2026-09-22).
        self._pending_clarifications.pop(session_id, None)
        if self._store is not None:
            self._store.set_pending_clarification(session_id, None)
        if self._promote is None:  # pragma: no cover - the tool is not offered without it
            raise ServiceError("unavailable", 503)
        try:
            attachment = self._attachment(session_id, held.document_ref)
        except ServiceError:
            return _refused_save("BELGE_BULUNAMADI")
        digest = (attachment.source.content_hash or "").removeprefix("sha256:")
        if not digest or digest != held.document_sha256:
            return _refused_save("BELGE_DEĞİŞTİ")
        try:
            receipt = self._promote(held)
        except ServiceError:
            return _refused_save("KAYDEDİLEMEDİ")
        self._turns[session_id] = self._turns.get(session_id, 0) + 1
        if self._store is not None:
            self._store.append_message(
                session_id, turn_id=turn_id, role="assistant", text=receipt.said()
            )
        return Answer(status=AnswerStatus.ACCEPTED, text=receipt.said(), omitted_claims=0)

    def _remember_proven(self, session_id: str, identities: Iterable[str]) -> None:
        """Keep this conversation's proven identities in memory and in the store."""
        found = {item for item in identities if item}
        if not found:
            return
        self._proven.setdefault(session_id, set()).update(found)
        if self._store is not None:
            self._store.add_proven_series(session_id, found)

    def _fail_run(
        self, run_id: str, failure: BaseException, *, started: float, tracer: Tracer
    ) -> None:
        """Close a run that ended badly: a failed or cancelled turn is still readable.

        Run summaries are a strict public contract, so only fixed categories are
        stored here, never provider or exception prose (a free-text error once made
        the whole run list unreadable).
        """
        cancelled = isinstance(failure, TurnCancelled)
        if cancelled:
            tracer.event("request", "turn.cancelled", at=str(failure))
        if self._store is None:
            return
        self._store.finish_run(
            run_id,
            status="cancelled" if cancelled else "failed",
            duration_ms=max(0, round((time.monotonic() - started) * 1000)),
            error=(
                "cancelled"
                if cancelled
                else "provider_failed"
                if isinstance(failure, ProviderError)
                else "planning_failed"
                if isinstance(failure, PlanningFailed)
                else "output_limit"
                if isinstance(failure, OutputRefused)
                else failure.code
                if isinstance(failure, ServiceError)
                else "internal_error"
            ),
            events=tracer.events,
        )

    def _apply_knowledge(self, lake: Lakehouse) -> tuple[ReviewedSnapshot, list[str]]:
        """This turn's catalog, and the user datasets newly loaded into this session's lake.

        A user dataset enters the session's own lakehouse — never the prepared seed —
        through the same bronze/silver path as any series: its declared content as
        the bronze artifact, its declaration as the silver series, its numbers as
        observations. A version already present is left as it is.
        """
        if self._knowledge is None:
            return effective_snapshot(self._catalog, [], [], self._directory), []
        datasets = self._knowledge.datasets(include_archived=False)
        catalog = effective_snapshot(
            self._catalog, datasets, self._knowledge.notes(), self._directory
        )
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
            session_id,
            turn_id=turn_id,
            role="user",
            text=question,
            status="completed",
            document_ref=document_ref,
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
        if answer.result is not None:
            # Reverse lineage: which answers rest on which series, from the proof.
            self._store.record_result_series(
                session_id,
                turn_id,
                [source.series_id for source in answer.result.proof.sources],
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

    def published_result(self, session_id: str, turn_id: str) -> Result:
        """The table a turn published, rebuilt from its receipt after any restart.

        The receipt (`publications`) names the workspace artifact and the exact
        version; the artifact is checked against both before anything is shown,
        the proof is rebuilt from the same lineage, and the projection is the
        one publication used, so the reference and version match the stored
        messages. While a turn is running the runner's lock is held, and this
        read says so (busy) instead of opening the lake beside a writer.
        """
        if not _IDENTIFIER.fullmatch(session_id) or not _IDENTIFIER.fullmatch(turn_id):
            raise ServiceError("not_found", 404)
        # Waits a moment for another read: a reopened chat asks for each of its tables, and
        # refusing the second because the first was being read made a table look lost. A
        # running turn holds the lock for minutes, and that is still answered "busy".
        if not self._lock.acquire(timeout=STORED_READ_WAIT_SECONDS):
            raise ServiceError("busy", 409)
        try:
            self._restore_locked(session_id)
            publication = self._publications.get((session_id, turn_id))
            if publication is None:
                raise ServiceError("not_found", 404)
            target = self.run_root / session_id / "lake" / DATABASE_NAME
            try:
                connection = duckdb.connect(str(target), read_only=True, config=dict(SANDBOX))
            except duckdb.Error:
                raise ServiceError("not_found", 404) from None
            try:
                value = SelectedTable(
                    Workspace(connection, session_id),
                    publication.name,
                    publication.artifact_id,
                    publication.selection.version,
                ).check()
                proof = build_proof(connection, value, secrets=self._redactions)
                workspace = Workspace(connection, session_id)
                related = tuple(
                    (item, build_proof(connection, item, secrets=self._redactions))
                    for item in workspace.related_results(
                        workspace.artifact(publication.artifact_id)
                    ).values()
                )
            except (SelectionError, WorkspaceError, ValueError, duckdb.Error):
                raise ServiceError("not_found", 404) from None
            finally:
                connection.close()
            try:
                return project_result(
                    value, turn_id=turn_id, secrets=self._redactions, proof=proof, related=related
                )
            except OutputRefused:
                raise ServiceError("not_found", 404) from None
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
        session_id: str | None = None,
        references: Mapping[str, str] | None = None,
    ) -> ToolRegistry:
        fetch = turn_fetch if turn_fetch is not None else self._web_url_fetch
        catalog = catalog if catalog is not None else self._catalog
        # A datagroup is opened only when its series could then be fetched this turn.
        opened = self._discovered if acquirer is not None else None
        inspector = PreparedSeriesInspector(
            catalog, late=opened.entry if opened is not None else None
        )
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
                # A generation answers for the identities whose text it embedded, so a
                # catalogue that has gained an entry keeps meaning-based discovery for
                # everything else in it.
                dense=self._dense_for(catalog),
                expand=(
                    (lambda query, output: expand_groups(query, output, opened))
                    if self._directory is not None
                    else None
                ),
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
        registry.register(
            make_anomaly_tool(connection, lineage=lineage, inspector=inspector, workspace=workspace)
        )
        registry.register(
            make_causality_tool(
                connection,
                lineage=lineage,
                series_names=names,
                inspector=inspector,
                workspace=workspace,
            )
        )
        if self._search_backend is not None and "web_search" not in disabled:
            # Measured 2026-09-21: a search is 1 to 3.3 s and the worker process another
            # second to start, so the 5 s default left no room for the one retry of an
            # empty page; twenty seconds is still far below a planner call.
            registry.register(
                make_web_search_tool(backend=self._search_backend, timeout_seconds=20.0)
            )
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
                    keep=(
                        (
                            lambda media_type, content: self._keep_read(
                                session_id, media_type, content
                            )
                        )
                        if session_id is not None and self._document_uploads
                        else None
                    ),
                )
            )
        if (
            (attachment is not None or library)
            and self._promote is not None
            and self._knowledge is not None
            and session_id is not None
            and "document_upload" not in disabled
            and "knowledge_base" not in disabled
        ):
            # Offered only where there is something to keep and somewhere to keep it:
            # a turn with no document, or a deployment with no knowledge base, never
            # sees this tool at all.
            registry.register(
                make_promote_series_tool(
                    session_id=session_id,
                    attachment=attachment,
                    library=library or {},
                    references=references or {},
                    propose=lambda proposal: self._offer(session_id, proposal),
                    ocr=None if "document_ocr" in disabled else self._document_ocr,
                )
            )
        if (attachment is not None or library) and "document_upload" not in disabled:
            # Meaning from a document that holds no table to compute from: a chart, a
            # scanned page, a passage. Its output is a reading, never a result, so it
            # is bound to the same admitted bytes and to nothing else.
            registry.register(
                make_document_read_tool(
                    provider=self._provider,
                    attachment=attachment,
                    library=library,
                    ocr=None if "document_ocr" in disabled else self._document_ocr,
                    vision=self._vision,
                )
            )
        return registry
