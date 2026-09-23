"""The knowledge base over HTTP: see everything, add and change with versions (DEC-157).

Reading shows every entry the agent can reach — reviewed series (prepared,
fetchable on first use, or catalog only) and user datasets — with where each
one's meaning comes from. Writing never touches the reviewed catalog or the
prepared pool: it appends a version to the knowledge base, which the next turn
applies as its catalog. Every write names its author, the browser key's owner.
A note on a reviewed or listed entry applies to every key's catalogue, so it is
written only when the operator started the server with --allow-catalog-edits.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import ValidationError

from kkb_agent.api.contracts import (
    DatasetDetail,
    DatasetRequest,
    DatasetSource,
    DatasetVersionSummary,
    DirectoryRefreshResult,
    KnowledgeList,
    KnowledgeSeries,
    SearchHit,
    SearchTrial,
    SeriesNoteHistory,
    SeriesNoteRequest,
    SeriesNoteVersion,
    SeriesUse,
    SeriesUses,
    SeriesValues,
    StoredObservation,
    VectorIndexStatus,
)
from kkb_agent.api.service import ServiceError
from kkb_agent.api.store import ConversationStore
from kkb_agent.catalog.directory import SourceDirectory
from kkb_agent.catalog.directory import source_directory as build_source_directory
from kkb_agent.catalog.discovered import DiscoveredStore, listed_entry
from kkb_agent.catalog.expansion import expand_groups
from kkb_agent.catalog.hybrid import CatalogDenseStage, search_hybrid_catalog
from kkb_agent.catalog.lance_index import CatalogIndexError, LocalCatalogIndex
from kkb_agent.catalog.mappings import ReviewedSeries, ReviewedSnapshot, is_source_group
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.records import CatalogRecord, CatalogStatus
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog
from kkb_agent.catalog.vectors import catalog_documents
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
from kkb_agent.llm.provider import ConfigurationError, ProviderError, TransportError
from kkb_agent.tools.promotion import IndexState, PromotionProposal, PromotionReceipt

#: (session_id, document_ref, period_column, value_column, sheet, year) -> monthly
#: (period end, value) pairs and the document's content digest. Owned by the runner.
DocumentColumnReader = Callable[
    [str, str, str, str, str | None, int | None],
    tuple[tuple[tuple[date, float | None], ...], str],
]


def _stage(sources: tuple[str, ...]) -> Literal["lexical", "dense", "both"]:
    """Which retrieval stage offered this candidate, as the tool itself recorded it."""
    if "lexical" in sources and "dense" in sources:
        return "both"
    return "dense" if "dense" in sources else "lexical"


def _index_failure(error: Exception) -> str:
    """Stable status category only; exception text may contain provider or local secrets."""
    if isinstance(error, CatalogIndexError):
        code = str(error)
        return {
            "INDEX_CATALOG_DIGEST_MISMATCH": "catalog_digest_mismatch",
            "INDEX_SNAPSHOT_OR_IDENTITIES_MISMATCH": "catalog_digest_mismatch",
            "INDEX_PROFILE_MISMATCH": "profile_mismatch",
            "INDEX_QUERY_PROFILE_MISMATCH": "profile_mismatch",
            "INDEX_VECTOR_DIMENSION_MISMATCH": "vector_dimension_mismatch",
            "INDEX_EMBEDDING_COUNT_MISMATCH": "embedding_count_mismatch",
            "INDEX_MANIFEST_INVALID": "generation_corrupt_or_incomplete",
            "INDEX_CONTENT_INVALID": "generation_corrupt_or_incomplete",
            "INDEX_BUILD_INCOMPLETE": "generation_corrupt_or_incomplete",
            "INDEX_NEW_LOCAL_DIRECTORY_REQUIRED": "state_filesystem_failure",
            "INDEX_LOCAL_ABSOLUTE_PATH_REQUIRED": "state_filesystem_failure",
            "INDEX_CATALOG_CHANGED_DURING_BUILD": "concurrent_catalog_change",
        }.get(code, "generation_invalid")
    if isinstance(error, ConfigurationError):
        return "provider_auth_or_configuration"
    if isinstance(error, TransportError):
        return "provider_transient_failure"
    if isinstance(error, ProviderError):
        return "provider_failure"
    if isinstance(error, OSError):
        return "state_filesystem_failure"
    return "rebuild_failed"


#: The page's tabs, and the most entries one page of the list may carry.
KNOWLEDGE_TABS = (
    "all",
    "reviewed",
    "listed",
    "prepared",
    "fetchable",
    "catalog",
    "user",
    "archived",
)
MAX_KNOWLEDGE_PAGE = 100


def dataset_source(item: DatasetVersion) -> DatasetSource | None:
    """Where a version's numbers were read, for the page; None for one typed into the form.

    A conversation's save kept its source in the version (address, time read, bytes,
    place in the document) and the page showed none of it, so a saved series could not
    be told from one typed in, nor one version's address from another's.
    """
    if not item.provenance:
        return None
    where = dict(item.provenance)
    read = where.get("retrieved_at") or where.get("uploaded_at")

    def number(key: str) -> int | None:
        value = where.get(key, "")
        return int(value) if value.isdigit() else None

    try:
        return DatasetSource(
            kind="address" if where.get("source_url") else "upload",
            url=where.get("source_url"),
            read_at=datetime.fromisoformat(read) if read else None,
            sha256=where.get("sha256"),
            document=where.get("document"),
            page=number("location_page"),
            table=number("location_table"),
            sheet=where.get("location_sheet") or where.get("sheet"),
            period_column=where.get("period_column"),
            value_column=where.get("value_column"),
        )
    except (ValueError, ValidationError):
        # A version whose recorded source does not read as one is shown without it,
        # rather than making the whole record unreadable.
        return None


def _in_tab(item: KnowledgeSeries, tab: str) -> bool:
    """The same sorting the page did in the browser while the whole list still fitted."""
    if tab == "archived":
        return item.status == "archived"
    if item.status == "archived":
        return tab == "all"
    if tab == "reviewed":
        return item.origin == "reviewed"
    if tab == "listed":
        return item.origin == "listed"
    if tab == "prepared":
        return item.prepared
    if tab == "fetchable":
        return item.fetchable
    if tab == "catalog":
        return item.origin == "reviewed" and not item.prepared and not item.fetchable
    if tab == "user":
        return item.origin == "user"
    return True


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
        dense: CatalogDenseStage | None = None,
        rebuild_index: (
            Callable[[ReviewedSnapshot, LocalCatalogIndex | None], CatalogDenseStage] | None
        ) = None,
        install_index: Callable[[CatalogDenseStage], None] | None = None,
        reopen_index: Callable[[ReviewedSnapshot], CatalogDenseStage | None] | None = None,
        source_directory: SourceDirectory | None = None,
        discovered: DiscoveredStore | None = None,
        install_directory: Callable[[SourceDirectory], None] | None = None,
        catalog_edits: bool = False,
    ) -> None:
        self._knowledge = knowledge
        # Whether a browser key may note reviewed and listed entries: the operator's
        # --allow-catalog-edits. Off unless given, so a caller that forgets it fails closed.
        self._catalog_edits = catalog_edits
        self._install_directory = install_directory
        self._refreshing = threading.Lock()
        # The EVDS series lists opened so far; a trial search opens datagroups as a turn does.
        self._discovered = discovered
        self._dense = dense
        # Building a generation calls the embedding model for every entry the generation in
        # use does not already hold, so it runs on its own thread and one at a time; reading
        # never does.
        self._rebuild = rebuild_index
        self._install = install_index
        self._reopen = reopen_index
        self._directory = source_directory
        self._building = threading.Lock()
        #: A save arrived while a build was running from the catalogue before it.
        self._stale = False
        # Serialize catalog edits with the final digest check and installation.
        self._catalog_change = threading.RLock()
        self._build_thread: threading.Thread | None = None
        self._built_at: datetime | None = None
        self._build_error: str | None = None
        self._conversations = conversations
        self._reviewed = reviewed
        self._prepared = prepared
        self._acquisition = acquisition
        self._read_column = read_document_column
        # When each reviewed series was last fetched from its source (DEC-159).
        self._acquisitions = acquisitions
        # A prepared series' stored values, read-only from the verified seed.
        self._series_values = series_values
        # What a list request needs of the whole catalogue, kept until what it is made of
        # changes (see `_catalog_now`, `_search_texts`).
        self._effective_kept: tuple[tuple[Any, ...], ReviewedSnapshot] | None = None
        self._texts_kept: tuple[str, dict[str, str]] | None = None
        # A page asks for several things at once; after a restart they would each build
        # the same catalogue side by side and all be late. One builds, the others wait.
        self._keeping = threading.Lock()

    # -- authorization ---------------------------------------------------------

    def _author(self, owner_token: str) -> str:
        owner = self._conversations.owner_by_token(owner_token)
        if owner is None:
            raise ServiceError("not_found", 404)
        return owner

    # -- reading ---------------------------------------------------------------

    def search(self, owner_token: str, query: str) -> SearchTrial:
        """What discovery returns for a question, over this browser's own catalogue.

        The retrieval a turn runs, with no turn, no answer and nothing stored: the
        same two stages (reviewed lexical match and, when an index is configured,
        the meaning-based one) over the same effective catalogue. A trial reports
        which stages actually ran, so a catalogue whose vectors no longer cover it
        is visible here rather than silently lexical.
        """
        self._author(owner_token)
        catalog = self._effective()
        try:
            arguments = CatalogSearchArguments(query=query)
        except ValidationError:
            raise ServiceError("invalid_request", 422) from None
        found = (
            search_hybrid_catalog(catalog, arguments, self._dense)
            if self._dense is not None
            else search_catalog(catalog, arguments)
        )
        if self._directory is not None:
            found = expand_groups(query, found, self._discovered if self._acquisition else None)
        return SearchTrial(
            query=query,
            status=str(found.status),
            clarification_required=found.clarification_required,
            total_candidates=found.total_candidates,
            retrieval_mode=found.retrieval_mode,
            dense_status=found.dense_status,
            dense_failure=found.dense_failure,
            embedding_model=self._dense.index.profile.model if self._dense is not None else None,
            input_policy_id=found.input_policy_id,
            top_candidate=found.top_candidate,
            hits=tuple(
                SearchHit(
                    series_id=candidate.series.record.series_id,
                    title=candidate.series.record.title,
                    provider=candidate.series.record.provider,
                    unit=candidate.series.record.unit,
                    frequency=candidate.series.record.frequency.value,
                    stock_flow=candidate.series.record.stock_flow.value,
                    prepared=candidate.series.record.series_id in self._prepared,
                    archived=candidate.series.record.status is CatalogStatus.ARCHIVED,
                    stage=_stage(candidate.retrieval_sources),
                    concepts=tuple(candidate.concept_ids)[:20],
                )
                for candidate in found.candidates
            ),
        )

    def _effective(self) -> ReviewedSnapshot:
        """The catalogue a turn would search: reviewed, with this knowledge base applied."""
        datasets = self._knowledge.datasets(include_archived=True)
        notes = list({note.series_id: note for note in self._knowledge.notes()}.values())
        return self._catalog_now(datasets, notes)

    def _catalog_now(
        self, datasets: Sequence[DatasetVersion], notes: Sequence[SeriesNote]
    ) -> ReviewedSnapshot:
        """`effective_snapshot`, built again only when one of its inputs changed.

        With FinTürk and the whole monthly bulletin listed the catalogue is 8,374 series
        and building it is about a second; every list request built it, and then built the
        search text of all 8,374 to show fifty (3.5 s). The page asks for the list, the
        index state and the counters at once, so the list passed the client's 12 s and the
        reader saw "Bağlantı kesildi" under an empty list (live 2026-09-21). A dataset or a
        note is a new version when it changes, and a refreshed directory is a new object,
        so those identities are the whole key.
        """
        key = (
            self._directory,
            tuple((item.series_id, item.version, item.status) for item in datasets),
            tuple((note.series_id, note.version) for note in notes),
        )
        with self._keeping:
            kept = self._effective_kept
            if kept is not None and kept[0][0] is key[0] and kept[0][1:] == key[1:]:
                return kept[1]
            catalog = effective_snapshot(
                self._reviewed,
                [item for item in datasets if item.status == "active"],
                list(notes),
                self._directory,
            )
            self._effective_kept = (key, catalog)
            return catalog

    def _search_texts(self, catalog: ReviewedSnapshot) -> dict[str, str]:
        """What search reads for each series of `catalog`, built once per catalogue."""
        with self._keeping:
            kept = self._texts_kept
            if kept is not None and kept[0] == catalog.content_sha256:
                return kept[1]
            try:
                texts = {item.series_id: item.text for item in catalog_documents(catalog)}
            except ValueError:
                texts = {}
            self._texts_kept = (catalog.content_sha256, texts)
            return texts

    def uses(self, owner_token: str, series_id: str) -> SeriesUses:
        """Which of this browser's answers rest on the series (reverse lineage).

        Read from the rows the runner wrote out of each published answer's proof;
        an archived series or a superseded user version keeps its history here.
        """
        owner = self._author(owner_token)
        return SeriesUses(
            series_id=series_id,
            uses=tuple(
                SeriesUse(
                    conversation_id=row["conversation_id"],
                    title=row["title"],
                    turn_id=row["turn_id"],
                    question=row["question"][:500],
                    used_at=row["used_at"],
                )
                for row in self._conversations.series_uses(owner, series_id)
            ),
        )

    def index_status(self, owner_token: str) -> VectorIndexStatus:
        """What the meaning-based stage holds, against the catalogue in use now.

        Reading only: no vector is computed here and no model is called. Coverage is
        counted per identity, because that is what the second stage now searches by: a
        series is vectored when the text embedded for it is still its catalogue text, and
        the entries that are not are named.
        """
        self._author(owner_token)
        catalog = self._effective()
        identities = [item.record.series_id for item in catalog.series]
        building = self._build_thread is not None and self._build_thread.is_alive()
        if self._dense is None:
            return VectorIndexStatus(
                configured=False,
                catalog_sha256=catalog.content_sha256,
                catalog_version=catalog.snapshot_version,
                covers_catalog=False,
                series_total=len(identities),
                series_vectored=0,
                missing=tuple(identities[:50]),
                rebuilding=building,
                rebuildable=self._rebuild is not None,
                built_at=self._built_at,
                last_error=self._build_error,
            )
        index = self._dense.index
        profile = index.profile
        # Held under other text is not vectored for the catalogue in use now.
        held = index.covering(catalog)
        return VectorIndexStatus(
            configured=True,
            model=profile.model,
            input_policy_id=profile.input_policy_id,
            origin=profile.origin,
            dimension=profile.dimension,
            generation_sha256=index.snapshot_sha256,
            generation_version=index.snapshot_version,
            catalog_sha256=catalog.content_sha256,
            catalog_version=catalog.snapshot_version,
            covers_catalog=set(identities) <= held,
            series_total=len(identities),
            series_vectored=sum(sid in held for sid in identities),
            missing=tuple(sid for sid in identities if sid not in held)[:50],
            rebuilding=building,
            rebuildable=self._rebuild is not None,
            built_at=self._built_at,
            last_error=self._build_error,
        )

    def restore_generation(self) -> bool:
        """At startup: reuse the generation already built for the catalogue in use now.

        Generations are kept on disk by catalogue digest, yet a restart installed only
        the reviewed one. With any knowledge-base entry present, discovery then fell
        back to words alone until someone pressed the rebuild button again, although
        nothing needed building (live 2026-09-19, after both restarts of the day).
        Opening a generation calls no model; one that does not exist is never built
        here, and a generation that fails to open leaves the reviewed one in use.
        """
        if self._reopen is None:
            return False
        catalog = self._effective()
        if self._dense is not None and self._dense.index.snapshot_sha256 == catalog.content_sha256:
            return False
        try:
            stage = self._reopen(catalog)
        except Exception as error:
            self._build_error = _index_failure(error)
            return False
        if stage is None:
            return False
        if stage.index.snapshot_sha256 != catalog.content_sha256:
            self._build_error = "catalog_digest_mismatch"
            return False
        try:
            with self._catalog_change:
                if self._effective().content_sha256 != catalog.content_sha256:
                    return False
                if self._dense is not None and stage.index.profile != self._dense.index.profile:
                    raise CatalogIndexError("INDEX_PROFILE_MISMATCH")
                if self._install is not None:
                    self._install(stage)
                self._dense = stage
        except Exception as error:
            self._build_error = _index_failure(error)
            return False
        return True

    def rebuild(self, owner_token: str) -> VectorIndexStatus:
        """Build the vectors again for the catalogue in use now, with the same profile.

        Accepted, not finished: the build runs on its own thread, so the page polls the
        status. One build runs at a time. The generation in use lends the build every
        vector whose text and profile have not changed, so the embedding model is called
        only for new or changed entries, and it keeps answering searches and turns until
        its successor is installed. The model, the input policy and the dimension are the
        deployment's; nothing here selects them. A new generation is written and installed
        for later turns only after it verifies against the catalogue it was built for; on
        any failure the generation in use is left untouched.
        """
        self._author(owner_token)
        if self._rebuild is None:
            raise ServiceError("unavailable", 503)
        if not self._start_build():
            raise ServiceError("busy", 409)
        return self.index_status(owner_token)

    def _start_build(self, lender: LocalCatalogIndex | None = None) -> bool:
        """Start a build for the catalogue in use now; False when one is already running.

        Shared by the page's button and by a save from a conversation, which is the
        same need: an entry the vectors do not hold is found by words alone until they do.
        `lender` lends its vectors to the build in place of the generation in use.
        """
        if self._rebuild is None:
            return False
        if not self._building.acquire(blocking=False):
            return False
        try:
            catalog = self._effective()
        except BaseException:
            # Reading the effective catalogue can fail. The lock was already taken
            # here, and nothing released it: every later build answered 409 until
            # the process was restarted (finding F4-bt-11).
            self._building.release()
            raise
        if self._dense is not None and self._dense.index.snapshot_sha256 == catalog.content_sha256:
            self._building.release()
            return True
        build, install = self._rebuild, self._install
        previous = lender or (self._dense.index if self._dense is not None else None)

        def run() -> None:
            built: LocalCatalogIndex | None = None
            try:
                stage = build(catalog, previous)
                if stage.index.snapshot_sha256 != catalog.content_sha256:
                    raise CatalogIndexError("INDEX_CATALOG_DIGEST_MISMATCH")
                if self._dense is not None and stage.index.profile != self._dense.index.profile:
                    raise CatalogIndexError("INDEX_PROFILE_MISMATCH")
                built = stage.index
                with self._catalog_change:
                    if self._effective().content_sha256 != catalog.content_sha256:
                        raise CatalogIndexError("INDEX_CATALOG_CHANGED_DURING_BUILD")
                    if install is not None:
                        install(stage)
                    self._dense = stage
                self._built_at, self._build_error = datetime.now(UTC), None
            except Exception as error:
                # A category, never a path, a query or vector contents.
                self._build_error = _index_failure(error)
            finally:
                # Released before `_stale` is read, and a save sets `_stale` before it asks
                # again (`_refresh_after_save`): whichever way the two interleave, either
                # this build sees the flag or that second ask finds no build running and
                # starts one (QA-31).
                self._building.release()
            if self._stale:
                # A conversation saved a series while this ran from the catalogue before
                # it. What was built is never installed for a catalogue it was not built
                # for; one more build runs, borrowing the vectors just made, so only the
                # new entry is embedded again rather than every entry of a full build.
                self._stale = False
                try:
                    self._start_build(built)
                except Exception as error:  # noqa: BLE001 - recorded, never raised on a thread
                    self._build_error = _index_failure(error)

        thread = threading.Thread(target=run, name="catalog-index", daemon=True)
        self._build_thread = thread
        try:
            thread.start()
        except BaseException:
            self._build_thread = None
            self._building.release()
            raise
        return True

    def _refresh_after_save(self) -> IndexState:
        """Make a just-saved series findable by meaning, and say how that stands.

        A save left the vectors as they were and said so, so a series kept from a
        conversation was found by its words only until someone pressed the rebuild
        button. The build embeds only the new entry; while one is already running
        (it started before this save), one more runs when it ends.
        """
        if self._rebuild is None:
            return "lexical"
        try:
            if not self._start_build():
                # Busy: leave the refresh for the running build, then ask once more. A
                # build that ended between the busy answer and the flag never read it,
                # and nothing was left to build this save (QA-31); asking again after the
                # flag is set finds either that build still running - it will read the
                # flag - or no build, and starts one. The flag is left set: at worst the
                # build it causes finds the catalogue already covered and does nothing.
                self._stale = True
                self._start_build()
        except Exception as error:  # noqa: BLE001 - the save stands; the vectors are said
            self._build_error = _index_failure(error)
            return "unchanged"
        return "refreshing"

    def refresh_directory(self, owner_token: str) -> DirectoryRefreshResult:
        """Read the sources' own directories again: what is new becomes searchable.

        EVDS's live datagroup directory is compared with the pinned one (one request), and
        the series lists of the datagroups opened so far are read again (one request each),
        so a series or a datagroup the source added since is found by the next search. The
        BDDK bulletin's listing is pinned with measured behaviour and is refreshed by its
        harvest, not here. Nothing is fetched into a lakehouse and no model is called.
        """
        self._author(owner_token)
        if self._discovered is None or self._directory is None:
            raise ServiceError("unavailable", 503)
        if not self._refreshing.acquire(blocking=False):
            raise ServiceError("busy", 409)
        try:
            found = self._discovered.refresh()
            if found is None:
                raise ServiceError("unavailable", 503)
            directory = build_source_directory(self._discovered.supplement())
            changed = directory.digest != self._directory.digest
            if changed:
                with self._catalog_change:
                    self._directory = directory
                    if self._install_directory is not None:
                        self._install_directory(directory)
            return DirectoryRefreshResult(
                evds_listed=found.listed,
                added_total=len(found.added),
                added=tuple(group.title[:240] for group in found.added[:20] if group.title),
                withdrawn=found.withdrawn,
                series_lists_reread=found.reopened,
                series_lists_failed=found.failed,
                catalog_changed=changed,
            )
        finally:
            self._refreshing.release()

    def close(self) -> None:
        """Wait for a build in progress so a generation is never left half written."""
        thread = self._build_thread
        if thread is not None:
            thread.join(timeout=600)

    def listing(
        self,
        owner_token: str,
        *,
        tab: str = "all",
        province: str | None = None,
        query: str | None = None,
        page: int | None = None,
        page_size: int = 50,
    ) -> KnowledgeList:
        """The knowledge base, one page of it at a time.

        Without `page` this is the bounded list the page always had: reviewed entries,
        the reader's own datasets, and the listed entries a person touched or a turn
        fetched. With `page` every listed entry can be browsed: the filters run here and
        one page travels. Measured: the whole list is 1,930 bytes an entry, 3.6 MB for the
        1,869 entries of 2026-09-21 and about 16 MB with FinTürk and the full monthly
        bulletin, against the web bridge's 1 MiB response bound.
        """
        self._author(owner_token)
        datasets = self._knowledge.datasets(include_archived=True)
        notes = {note.series_id: note for note in self._knowledge.notes()}
        catalog = self._catalog_now(datasets, list(notes.values()))
        fetched = self._acquisitions() if self._acquisitions is not None else {}
        entries = [
            self._reviewed_entry(
                item.record,
                notes.get(item.record.series_id),
                fetched.get(item.record.series_id),
                geography=item.geography,
            )
            for item in self._reviewed.series
        ]
        listed = self._directory.series if self._directory is not None else ()
        known = {item.record.series_id for item in self._reviewed.series}
        everything = page is not None
        entries.extend(
            self._reviewed_entry(
                item.record,
                notes.get(item.record.series_id),
                fetched.get(item.record.series_id),
                origin="listed",
                geography=item.geography,
            )
            for item in listed
            if item.record.series_id not in known
            and not is_source_group(item)
            and (everything or item.record.series_id in fetched or item.record.series_id in notes)
        )
        # EVDS series a search opened (DEC-177); without `page`, the fetched ones only.
        entries.extend(
            self._reviewed_entry(
                item.record, None, fetched.get(item.record.series_id), origin="listed"
            )
            for item in self._opened()
            if item.record.series_id not in known
            and (everything or item.record.series_id in fetched)
        )
        entries.extend(self._dataset_entry(item) for item in datasets)
        listed_total = sum(
            item.record.series_id not in known and not is_source_group(item) for item in listed
        )
        if page is None:
            return KnowledgeList(
                catalog_digest=catalog.content_sha256,
                reviewed_digest=self._reviewed.content_sha256,
                series=tuple(self._with_search_text(entries, catalog)),
                listed_series=listed_total,
                catalog_editable=self._catalog_edits,
            )
        counts = {name: sum(_in_tab(item, name) for item in entries) for name in KNOWLEDGE_TABS}
        provinces = sorted(
            {item.geography for item in entries if item.geography and item.geography != "Türkiye"}
        )
        # Folded as the catalogue search folds it: "İHTİYAÇ" finds "İhtiyaç" and "ihtiyac".
        wanted = normalize_search_text(query or "")
        shown = [
            item
            for item in entries
            if _in_tab(item, tab if tab in KNOWLEDGE_TABS else "all")
            and (not province or item.geography == province)
            and (
                not wanted
                or wanted
                in normalize_search_text(
                    " ".join(
                        [
                            item.title,
                            item.series_id,
                            *item.aliases,
                            item.note or "",
                            item.geography or "",
                        ]
                    )
                )
            )
        ]
        size = max(1, min(page_size, MAX_KNOWLEDGE_PAGE))
        first = (max(1, page) - 1) * size
        return KnowledgeList(
            catalog_digest=catalog.content_sha256,
            reviewed_digest=self._reviewed.content_sha256,
            series=tuple(self._with_search_text(shown[first : first + size], catalog)),
            listed_series=listed_total,
            total=len(shown),
            page=max(1, page),
            page_size=size,
            counts=counts,
            provinces=tuple(provinces),
            catalog_editable=self._catalog_edits,
        )

    def _opened(self) -> tuple[ReviewedSeries, ...]:
        if self._discovered is None:
            return ()
        return tuple(listed_entry(series) for series in self._discovered.declared())

    def _with_search_text(
        self, entries: list[KnowledgeSeries], catalog: ReviewedSnapshot
    ) -> list[KnowledgeSeries]:
        """Each entry with what search reads for it, from the catalogue a turn searches now."""
        indexed = self._search_texts(catalog)
        reviewed = {item.record.series_id: item for item in self._reviewed.series}
        if self._directory is not None:
            for listed in self._directory.series:
                reviewed.setdefault(listed.record.series_id, listed)
        for opened in self._opened():
            reviewed.setdefault(opened.record.series_id, opened)
        aliases: dict[str, set[str]] = {}
        for concept in self._reviewed.concepts:
            for series_id in concept.candidate_series_ids:
                aliases.setdefault(series_id, set()).update(a.original for a in concept.aliases)
        enriched = []
        for entry in entries:
            item = reviewed.get(entry.series_id)
            enriched.append(
                entry.model_copy(
                    update={
                        "description": (
                            item.record.description if item is not None else entry.description
                        ),
                        "labels": item.record.labels if item is not None else (),
                        "reviewed_aliases": tuple(sorted(aliases.get(entry.series_id, ()))),
                        "reviewer_note": item.note if item is not None else None,
                        "search_text": indexed.get(entry.series_id),
                    }
                )
            )
        return enriched

    def _reviewed_entry(
        self,
        record: CatalogRecord,
        note: SeriesNote | None,
        fetched: dict[str, object] | None = None,
        *,
        origin: Literal["reviewed", "listed"] = "reviewed",
        geography: str | None = None,
    ) -> KnowledgeSeries:
        archived = note is not None and note.archived
        fetched_at = fetched.get("fetched_at") if fetched is not None else None
        return KnowledgeSeries(
            series_id=record.series_id,
            title=record.title,
            provider=record.provider,
            origin=origin,
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
            geography=geography,
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
            description=item.description,
        )

    def dataset(self, owner_token: str, slug: str) -> DatasetDetail:
        self._author(owner_token)
        return self._detail(slug)

    def _detail(self, slug: str) -> DatasetDetail:
        """One dataset as the page shows it; the caller has already been authorized."""
        latest = self._knowledge.dataset(slug)
        if latest is None:
            raise ServiceError("not_found", 404)
        return DatasetDetail(
            series=self._dataset_entry(latest),
            source_kind=latest.source_kind,
            description=latest.description,
            aggregation=latest.aggregation.value,
            weekly_anchor=latest.anchor.value if latest.anchor is not None else None,
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
                    source=dataset_source(item),
                )
                for item in self._knowledge.dataset_history(slug)
            ),
            source=dataset_source(latest),
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
        """Every version of a series' note, and whether the reading key wrote each one.

        The store kept each version's author, yet the history showed none, so an archive
        that came from another browser read like one's own (finding N43). Only the
        comparison travels: an owner id is never shown to another key.
        """
        reader = self._author(owner_token)
        return SeriesNoteHistory(
            series_id=series_id,
            history=tuple(
                SeriesNoteVersion(
                    version=note.version,
                    archived=note.archived,
                    aliases=note.aliases,
                    note=note.note,
                    created_at=note.created_at,
                    by_you=None if note.author is None else note.author == reader,
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
        return self._store_dataset(
            author,
            slug=request.slug,
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
            source_kind=source_kind,
            digest=digest,
            owner_token=owner_token,
        )

    def _store_dataset(
        self,
        author: str,
        *,
        slug: str,
        title: str,
        description: str | None,
        unit: str,
        scale: Scale,
        frequency: Frequency,
        stock_flow: StockFlow,
        cumulative: CumulativeKind,
        aggregation: Aggregation,
        base_year: int | None,
        anchor: WeeklyAnchor | None,
        aliases: tuple[str, ...],
        observations: tuple[Observation, ...],
        source_kind: str,
        digest: str | None,
        owner_token: str | None = None,
        provenance: tuple[tuple[str, str], ...] = (),
    ) -> DatasetDetail:
        """The one validated write, shared by the knowledge page and the agent.

        The promotion a conversation offers (DEC-183) saves exactly what this route
        saves, with the same store, the same refusals and the same versioning, rather
        than a second implementation or a call back into this application's own HTTP.
        """
        item = DatasetVersion(
            slug=slug,
            version=0,
            title=title,
            description=description,
            unit=unit,
            scale=scale,
            frequency=frequency,
            stock_flow=stock_flow,
            cumulative=cumulative,
            aggregation=aggregation,
            base_year=base_year,
            anchor=anchor,
            aliases=aliases,
            observations=observations,
            source_kind="upload" if source_kind == "upload" else "manual",
            source_sha256=digest,
            author=author,
            provenance=provenance,
        )
        try:
            with self._catalog_change:
                existing = self._knowledge.dataset(slug)
                if existing is not None and existing.status == "archived":
                    item = replace(item, status="archived")  # editing does not silently restore
                self._knowledge.save_dataset(item)
        except KnowledgeError:
            raise ServiceError("knowledge_rejected", 422) from None
        return self.dataset(owner_token, slug) if owner_token is not None else self._detail(slug)

    def promote(self, proposal: PromotionProposal) -> PromotionReceipt:
        """Save a proposal a conversation is holding, as that conversation's own owner.

        The owner is read from the conversation record, never from an argument: a model
        can name neither an owner nor a session token, and the proposal's session was
        fixed by the server when the offer was made. Nothing is fetched and nothing is
        parsed here - the observations were read when the offer was made, and only the
        document's digest is checked again, by the caller, before this is reached.
        """
        author = self._conversations.owner_of_conversation(proposal.session_id)
        if author is None:
            raise ServiceError("not_found", 404)
        try:
            observations = tuple(
                Observation(*period_bounds(Frequency.MONTHLY, end), value)
                for end, value in proposal.observations
            )
        except SemanticsError:
            raise ServiceError("knowledge_rejected", 422) from None
        detail = self._store_dataset(
            author,
            slug=proposal.slug,
            title=proposal.title,
            # What the model proposed for later searches; the store bounds and cleans it.
            description=proposal.description,
            unit=proposal.unit,
            scale=Scale(proposal.scale),
            frequency=Frequency.MONTHLY,
            stock_flow=StockFlow(proposal.stock_flow),
            cumulative=CumulativeKind(proposal.cumulative),
            aggregation=Aggregation(proposal.aggregation),
            base_year=proposal.base_year,
            anchor=None,
            aliases=proposal.aliases,
            observations=observations,
            source_kind="upload",
            digest=proposal.document_sha256,
            provenance=proposal.provenance,
        )
        return PromotionReceipt(
            series_id=detail.series.series_id,
            observations=len(detail.observations),
            index=self._refresh_after_save(),
        )

    def set_status(self, owner_token: str, slug: str, *, archived: bool) -> DatasetDetail:
        author = self._author(owner_token)
        try:
            with self._catalog_change:
                self._knowledge.set_dataset_status(
                    slug, "archived" if archived else "active", author=author
                )
        except KnowledgeError as error:
            if str(error) == "not_found":
                raise ServiceError("not_found", 404) from None
            raise ServiceError("knowledge_rejected", 422) from None
        return self.dataset(owner_token, slug)

    def _annotatable(self) -> set[str]:
        """Series a note may be attached to: reviewed records and the source directory's.

        `effective_snapshot` already applies notes, synonyms and archive flags to
        directory records - they are part of the catalogue it builds - but this
        route accepted reviewed records only, so "Düzenle" on a directory record
        answered 404 and the page did nothing (finding F4-bt-7).
        """
        known = {series.record.series_id for series in self._reviewed.series}
        if self._directory is not None:
            known |= self._directory.ids()
        return known

    def annotate(
        self, owner_token: str, series_id: str, request: SeriesNoteRequest
    ) -> SeriesNoteHistory:
        """Archive, alias or describe a reviewed or listed entry, when the operator allows it.

        A note is not the writer's own: `effective_snapshot` applies it to every key's
        searches and turns, and a reviewed series' description reaches every planner
        prompt. Any key from the unauthenticated `POST /v1/owner` archived the BDDK
        housing-loan TOTAL out of everyone's "konut kredisi bakiyesi" search, and one
        alias made TÜFE the single unambiguous candidate for "toplam konut kredisi"
        (finding N43, reproduced 2026-09-22). So these edits are the operator's authority
        (DEC-162): without --allow-catalog-edits nothing is written. The refusal comes after
        the key and series checks, so an unknown key or series still reads as not found.
        """
        author = self._author(owner_token)
        if series_id not in self._annotatable():
            raise ServiceError("not_found", 404)
        if not self._catalog_edits:
            raise ServiceError("catalog_read_only", 403)
        try:
            with self._catalog_change:
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
