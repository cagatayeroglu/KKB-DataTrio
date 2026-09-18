"""M13-04: bounded offline lexical discovery, not observation/claim evidence.

An operator supplies reviewed bytes. No SQL, FTS extension, network, model or
filesystem operation occurs. Small-corpus BM25 uses k1=1.2, b=.75 and positive
log(1+(N-df+.5)/(df+.5)) IDF; no stemming/stopwords or holdout tuning.
"""

from collections import Counter
from math import log
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator

from kkb_agent.catalog.mappings import Concept, ReviewedSeries, ReviewedSnapshot
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.ranking import rerank_by_reviewed_intent
from kkb_agent.catalog.records import MAX_CATALOG_CONCEPTS, MAX_CATALOG_SERIES, CatalogStatus
from kkb_agent.core import Frequency
from kkb_agent.core.models import ContractModel

SearchMethod = Literal["reviewed_alias", "reviewed_phrase", "bm25", "dense"]
SearchStatus = Literal["MATCH", "PARTIAL", "UNRESOLVED", "NO_MATCH", "FILTERED_OUT"]


class CatalogSearchArguments(ContractModel):
    query: StrictStr = Field(min_length=1, max_length=512, repr=False)
    max_results: StrictInt = Field(default=10, ge=1, le=10)
    source: StrictStr | None = Field(default=None, min_length=1, max_length=64)
    frequency: Frequency | None = None
    include_archived: StrictBool = False

    @field_validator("query", "source")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and (
            not normalize_search_text(value) or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("expected nonblank text without controls")
        return value


class ConceptMatch(ContractModel):
    concept_id: str
    family_ids: tuple[str, ...]
    resolution: Literal["MAPPED", "PARTIAL", "UNRESOLVED"]
    unresolved: tuple[str, ...]
    conditions: tuple[str, ...]


class CatalogCandidate(ContractModel):
    series: ReviewedSeries
    concept_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    observation_kind: Literal["unknown"] = "unknown"  # absent from CatalogRecord
    rank: int = Field(ge=1, le=10)
    bm25_score: float | None = Field(ge=0)
    matched_terms: tuple[str, ...]
    method: SearchMethod
    retrieval_sources: tuple[Literal["lexical", "dense"], ...] = ("lexical",)
    lexical_rank: int | None = Field(default=None, ge=1, le=10)
    dense_rank: int | None = Field(default=None, ge=1, le=10)
    cosine_distance: float | None = Field(default=None, ge=-0.000001, le=2.000001)


class CatalogSearchOutput(ContractModel):
    status: SearchStatus
    candidates: tuple[CatalogCandidate, ...] = Field(default=(), max_length=10)
    concepts: tuple[ConceptMatch, ...] = Field(default=(), max_length=MAX_CATALOG_CONCEPTS)
    total_candidates: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    truncated: bool
    clarification_required: bool
    excluded_archived_count: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    snapshot_version: str
    snapshot_sha256: str
    retrieval_version: Literal["m13-04-lexical-v1", "m13-05-combined-v1"] = "m13-04-lexical-v1"
    retrieval_mode: Literal["lexical_only", "hybrid", "lexical_degraded"] = "lexical_only"
    combination_policy: Literal[
        "lexical-v1", "reviewed-match-order-v1", "alternating-archive-tier-v1"
    ] = "lexical-v1"
    dense_status: Literal["not_configured", "skipped_no_eligible", "success", "failed"] = (
        "not_configured"
    )
    dense_failure: Literal["snapshot_mismatch", "embedding_failed", "index_failed"] | None = None
    embedding_origin: Literal["offline_fixture", "kloudeks"] | None = None
    input_policy_id: str | None = None
    profile_sha256: str | None = None
    lexical_total_candidates: int | None = Field(default=None, ge=0, le=40)
    dense_total_candidates: int | None = Field(default=None, ge=0, le=40)
    untrusted_metadata: Literal[True] = True
    observation_fetch_authorized: Literal[False] = False
    analytical_evidence: Literal[False] = False


def _concept_matches(snapshot: ReviewedSnapshot, key: str) -> tuple[list[Concept], SearchMethod]:
    exact = [c for c in snapshot.concepts if any(a.normalized == key for a in c.aliases)]
    if exact:
        return exact, "reviewed_alias"
    # Longest contained phrase wins over its generic substring; identical alias
    # collisions and disjoint concepts remain sets, not last-write-wins entries.
    phrases = {
        a.normalized
        for c in snapshot.concepts
        for a in c.aliases
        if f" {a.normalized} " in f" {key} "
    }
    maximal = {p for p in phrases if not any(p != q and f" {p} " in f" {q} " for q in phrases)}
    return [c for c in snapshot.concepts if any(a.normalized in maximal for a in c.aliases)], (
        "reviewed_phrase" if maximal else "bm25"
    )


def _terms(item: ReviewedSeries, concepts: list[Concept]) -> Counter[str]:
    record = item.record
    # Only positive reviewed aliases and canonical/display text are indexed.
    # Exclusion notes/UNRESOLVED contexts are not positive retrieval evidence.
    text = " ".join(
        [record.title, record.description or "", *record.labels]
        + [a.original for c in concepts for a in c.aliases]
    )
    return Counter(normalize_search_text(text).split())


def eligible_catalog_series(
    snapshot: ReviewedSnapshot, args: CatalogSearchArguments
) -> tuple[ReviewedSeries, ...]:
    """Shared declared metadata filtering, independent of ranking method."""
    return tuple(
        s
        for s in snapshot.series
        if (args.include_archived or s.record.status is not CatalogStatus.ARCHIVED)
        and (
            args.source is None
            or normalize_search_text(s.record.provider) == normalize_search_text(args.source)
        )
        and (args.frequency is None or s.record.frequency is args.frequency)
    )


def search_catalog(
    snapshot: ReviewedSnapshot, arguments: CatalogSearchArguments
) -> CatalogSearchOutput:
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    args = CatalogSearchArguments.model_validate(arguments)
    key = normalize_search_text(args.query)
    matches, method = _concept_matches(snapshot, key)
    mapped = {sid for c in matches for sid in c.candidate_series_ids}
    excluded = (
        sum(
            s.record.status is CatalogStatus.ARCHIVED
            and (not matches or s.record.series_id in mapped)
            for s in snapshot.series
        )
        if not args.include_archived
        else 0
    )
    eligible = eligible_catalog_series(snapshot, args)
    concepts_by_id = {
        s.record.series_id: [
            c for c in snapshot.concepts if s.record.series_id in c.candidate_series_ids
        ]
        for s in eligible
    }
    documents = {
        s.record.series_id: _terms(s, concepts_by_id[s.record.series_id]) for s in eligible
    }
    query_terms = set(key.split())
    count = len(documents)
    average = sum(sum(d.values()) for d in documents.values()) / count if count else 1.0
    scores: dict[str, float] = {}
    for sid, doc in documents.items():
        score = 0.0
        for term in sorted(query_terms & doc.keys()):
            df = sum(term in other for other in documents.values())
            idf = log(1 + (count - df + 0.5) / (df + 0.5))
            tf = doc[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * sum(doc.values()) / average))
        scores[sid] = round(score, 12)
    ranked = [
        s
        for s in eligible
        if (s.record.series_id in mapped if matches else scores[s.record.series_id] > 0)
    ]
    ranked.sort(
        key=lambda s: (
            s.record.status is CatalogStatus.ARCHIVED,
            -scores[s.record.series_id],
            s.record.series_id,
        )
    )
    ranked = rerank_by_reviewed_intent(args.query, ranked, reviewed_series=lambda item: item)
    unresolved = any(c.unresolved for c in matches)
    status: SearchStatus
    if ranked:
        # Token overlap can surface useful candidates, but only a reviewed
        # alias/phrase establishes that the requested concept is represented.
        status = "PARTIAL" if unresolved or not matches else "MATCH"
    elif matches and not mapped:
        status = "UNRESOLVED"
    elif matches and mapped:
        status = "FILTERED_OUT"
    else:
        status = "NO_MATCH"
    return CatalogSearchOutput(
        status=status,
        candidates=tuple(
            CatalogCandidate(
                series=s,
                concept_ids=tuple(sorted(c.concept_id for c in concepts_by_id[s.record.series_id])),
                family_ids=tuple(
                    sorted({f for c in concepts_by_id[s.record.series_id] for f in c.family_ids})
                ),
                rank=i + 1,
                bm25_score=scores[s.record.series_id],
                matched_terms=tuple(sorted(query_terms & documents[s.record.series_id].keys())),
                method=method,
            )
            for i, s in enumerate(ranked[: args.max_results])
        ),
        concepts=tuple(
            ConceptMatch(
                concept_id=c.concept_id,
                family_ids=tuple(sorted(c.family_ids)),
                resolution=c.resolution,
                unresolved=c.unresolved,
                conditions=c.conditions,
            )
            for c in sorted(matches, key=lambda c: c.concept_id)
        ),
        total_candidates=len(ranked),
        truncated=len(ranked) > args.max_results,
        # Even one title match is only a candidate, never a verified selection.
        clarification_required=bool(ranked or matches),
        excluded_archived_count=excluded,
        snapshot_version=snapshot.snapshot_version,
        snapshot_sha256=snapshot.content_sha256,
    )
