"""The knowledge base over HTTP: see everything, add and change with versions (DEC-157).

Reading shows every entry the agent can reach — reviewed series (prepared,
fetchable on first use, or catalog only) and user datasets — with where each
one's meaning comes from. Writing never touches the reviewed catalog or the
prepared pool: it appends a version to the knowledge base, which the next turn
applies as its catalog. Every write names its author, the browser key's owner.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime

from kkb_agent.api.contracts import (
    DatasetDetail,
    DatasetRequest,
    DatasetVersionSummary,
    KnowledgeList,
    KnowledgeSeries,
    SeriesNoteHistory,
    SeriesNoteRequest,
    SeriesNoteVersion,
    SeriesValues,
    StoredObservation,
)
from kkb_agent.api.service import ServiceError
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.mappings import ReviewedSnapshot
from kkb_agent.catalog.records import CatalogRecord, CatalogStatus
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.ingest.acquisition import has_reviewed_route
from kkb_agent.knowledge import (
    DatasetVersion,
    KnowledgeError,
    KnowledgeStore,
    SeriesNote,
    effective_snapshot,
)
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, period_bounds

#: (session_id, document_ref, period_column, value_column, sheet, year) -> monthly
#: (period end, value) pairs and the document's content digest. Owned by the runner.
DocumentColumnReader = Callable[
    [str, str, str, str, str | None, int | None],
    tuple[tuple[tuple[date, float | None], ...], str],
]


class KnowledgeService:
    def __init__(
        self,
        knowledge: KnowledgeStore,
        conversations: ConversationStore,
        reviewed: ReviewedSnapshot,
        *,
        prepared: frozenset[str],
        acquisition: bool = False,
        read_document_column: DocumentColumnReader | None = None,
        acquisitions: Callable[[], dict[str, dict[str, object]]] | None = None,
        series_values: Callable[[str], tuple[tuple[date, date, float | None], ...]] | None = None,
    ) -> None:
        self._knowledge = knowledge
        self._conversations = conversations
        self._reviewed = reviewed
        self._prepared = prepared
        self._acquisition = acquisition
        self._read_column = read_document_column
        # When each reviewed series was last fetched from its source (DEC-159).
        self._acquisitions = acquisitions
        # A prepared series' stored values, read-only from the verified seed.
        self._series_values = series_values

    # -- authorization ---------------------------------------------------------

    def _author(self, owner_token: str) -> str:
        owner = self._conversations.owner_by_token(owner_token)
        if owner is None:
            raise ServiceError("not_found", 404)
        return owner

    # -- reading ---------------------------------------------------------------

    def listing(self, owner_token: str) -> KnowledgeList:
        self._author(owner_token)
        datasets = self._knowledge.datasets(include_archived=True)
        notes = {note.series_id: note for note in self._knowledge.notes()}
        catalog = effective_snapshot(
            self._reviewed, [d for d in datasets if d.status == "active"], list(notes.values())
        )
        fetched = self._acquisitions() if self._acquisitions is not None else {}
        entries = [
            self._reviewed_entry(
                item.record, notes.get(item.record.series_id), fetched.get(item.record.series_id)
            )
            for item in self._reviewed.series
        ]
        entries.extend(self._dataset_entry(item) for item in datasets)
        return KnowledgeList(
            catalog_digest=catalog.content_sha256,
            reviewed_digest=self._reviewed.content_sha256,
            series=tuple(entries),
        )

    def _reviewed_entry(
        self,
        record: CatalogRecord,
        note: SeriesNote | None,
        fetched: dict[str, object] | None = None,
    ) -> KnowledgeSeries:
        archived = note is not None and note.archived
        fetched_at = fetched.get("fetched_at") if fetched is not None else None
        return KnowledgeSeries(
            series_id=record.series_id,
            title=record.title,
            provider=record.provider,
            origin="reviewed",
            status=(
                "archived"
                if archived or record.status is CatalogStatus.ARCHIVED
                else "active"
                if record.status is CatalogStatus.ACTIVE
                else "unknown"
            ),
            prepared=record.series_id in self._prepared,
            fetchable=(
                self._acquisition
                and record.series_id not in self._prepared
                and has_reviewed_route(record.series_id)
            ),
            unit=record.unit,
            scale=record.scale.value,
            frequency=record.frequency.value,
            stock_flow=record.stock_flow.value,
            cumulative=record.cumulative.value,
            base_year=record.base_year,
            coverage_start=record.coverage.start,
            coverage_end=record.coverage.end,
            aliases=note.aliases if note is not None else (),
            note=note.note if note is not None else None,
            version=note.version if note is not None else None,
            updated_at=note.created_at if note is not None else None,
            acquired_at=datetime.fromisoformat(fetched_at) if isinstance(fetched_at, str) else None,
        )

    @staticmethod
    def _dataset_entry(item: DatasetVersion) -> KnowledgeSeries:
        ends = [o.period_end for o in item.observations]
        return KnowledgeSeries(
            series_id=item.series_id,
            title=item.title,
            provider="USER",
            origin="user",
            status=item.status,
            prepared=False,
            fetchable=False,
            unit=item.unit,
            scale=item.scale.value,
            frequency=item.frequency.value,
            stock_flow=item.stock_flow.value,
            cumulative=item.cumulative.value,
            base_year=item.base_year,
            coverage_start=min(ends),
            coverage_end=max(ends),
            observations=len(item.observations),
            aliases=item.aliases,
            version=item.version,
            slug=item.slug,
            updated_at=item.created_at,
        )

    def dataset(self, owner_token: str, slug: str) -> DatasetDetail:
        self._author(owner_token)
        latest = self._knowledge.dataset(slug)
        if latest is None:
            raise ServiceError("not_found", 404)
        return DatasetDetail(
            series=self._dataset_entry(latest),
            source_kind=latest.source_kind,
            description=latest.description,
            aggregation=latest.aggregation.value,
            observations=tuple(
                StoredObservation(
                    period_start=o.period_start, period_end=o.period_end, value=o.value
                )
                for o in latest.observations
            ),
            history=tuple(
                DatasetVersionSummary(
                    version=item.version,
                    status=item.status,
                    observations=len(item.observations),
                    content_sha256=item.content_sha256(),
                    created_at=item.created_at,
                )
                for item in self._knowledge.dataset_history(slug)
            ),
        )

    def values(self, owner_token: str, series_id: str) -> SeriesValues:
        self._author(owner_token)
        if self._series_values is None or series_id not in self._prepared:
            raise ServiceError("not_found", 404)
        return SeriesValues(
            series_id=series_id,
            observations=tuple(
                StoredObservation(period_start=start, period_end=end, value=value)
                for start, end, value in self._series_values(series_id)
            ),
        )

    def note_history(self, owner_token: str, series_id: str) -> SeriesNoteHistory:
        self._author(owner_token)
        return SeriesNoteHistory(
            series_id=series_id,
            history=tuple(
                SeriesNoteVersion(
                    version=note.version,
                    archived=note.archived,
                    aliases=note.aliases,
                    note=note.note,
                    created_at=note.created_at,
                )
                for note in self._knowledge.note_history(series_id)
            ),
        )

    # -- writing ---------------------------------------------------------------

    def save_dataset(self, owner_token: str, request: DatasetRequest) -> DatasetDetail:
        author = self._author(owner_token)
        frequency = Frequency(request.frequency)
        source_kind: str = "manual"
        digest: str | None = None
        if request.document is not None:
            if self._read_column is None:
                raise ServiceError("unavailable", 503)
            ref = request.document
            if not self._conversations.opens(ref.session_id, token=None, owner_token=owner_token):
                raise ServiceError("invalid_document", 422)
            pairs, digest = self._read_column(
                ref.session_id,
                ref.document_ref,
                ref.period_column,
                ref.value_column,
                ref.sheet,
                ref.year,
            )
            source_kind = "upload"
        else:
            pairs = tuple((item.period_end, item.value) for item in request.observations)
        anchor = WeeklyAnchor(request.weekly_anchor) if request.weekly_anchor else None
        try:
            observations = tuple(
                Observation(*period_bounds(frequency, end, anchor=anchor), value)
                for end, value in pairs
            )
        except SemanticsError:
            raise ServiceError("knowledge_rejected", 422) from None
        item = DatasetVersion(
            slug=request.slug,
            version=0,
            title=request.title,
            description=request.description,
            unit=request.unit,
            scale=Scale(request.scale),
            frequency=frequency,
            stock_flow=StockFlow(request.stock_flow),
            cumulative=CumulativeKind(request.cumulative),
            aggregation=Aggregation(request.aggregation),
            base_year=request.base_year,
            anchor=anchor,
            aliases=request.aliases,
            observations=observations,
            source_kind="upload" if source_kind == "upload" else "manual",
            source_sha256=digest,
            author=author,
        )
        existing = self._knowledge.dataset(request.slug)
        if existing is not None and existing.status == "archived":
            item = replace(item, status="archived")  # editing does not silently restore
        try:
            self._knowledge.save_dataset(item)
        except KnowledgeError:
            raise ServiceError("knowledge_rejected", 422) from None
        return self.dataset(owner_token, request.slug)

    def set_status(self, owner_token: str, slug: str, *, archived: bool) -> DatasetDetail:
        author = self._author(owner_token)
        try:
            self._knowledge.set_dataset_status(
                slug, "archived" if archived else "active", author=author
            )
        except KnowledgeError as error:
            if str(error) == "not_found":
                raise ServiceError("not_found", 404) from None
            raise ServiceError("knowledge_rejected", 422) from None
        return self.dataset(owner_token, slug)

    def annotate(
        self, owner_token: str, series_id: str, request: SeriesNoteRequest
    ) -> SeriesNoteHistory:
        author = self._author(owner_token)
        if series_id not in {s.record.series_id for s in self._reviewed.series}:
            raise ServiceError("not_found", 404)
        try:
            self._knowledge.annotate(
                series_id,
                archived=request.archived,
                aliases=request.aliases,
                note=request.note,
                author=author,
            )
        except KnowledgeError:
            raise ServiceError("knowledge_rejected", 422) from None
        return self.note_history(owner_token, series_id)
