"""M13-04: bounded offline lexical discovery, not observation/claim evidence.

An operator supplies reviewed bytes. No SQL, FTS extension, network, model or
filesystem operation occurs. Small-corpus BM25 uses k1=1.2, b=.75 and positive
log(1+(N-df+.5)/(df+.5)) IDF; no stemming/stopwords or holdout tuning.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from math import log
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator

from kkb_agent.catalog.mappings import (
    Concept,
    ReviewedSeries,
    ReviewedSnapshot,
    is_listed_series,
    is_source_group,
)
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.ranking import intent_key, rerank_by_reviewed_intent
from kkb_agent.catalog.records import MAX_CATALOG_CONCEPTS, MAX_CATALOG_SERIES, CatalogStatus
from kkb_agent.core import Frequency
from kkb_agent.core.models import ContractModel

SearchMethod = Literal["reviewed_alias", "reviewed_phrase", "bm25", "dense"]
SearchStatus = Literal["MATCH", "PARTIAL", "UNRESOLVED", "NO_MATCH", "FILTERED_OUT"]
#: Whether the first candidate is the default the request leaves. "unambiguous":
#: the reviewed-intent order puts it strictly first (the aggregate over TP/YP
#: components, the national series over regions, the current over the archived)
#: and every shown candidate shares a reviewed concept or family with it;
#: "ambiguous": candidates tie on an axis the request did not name, or span
#: unrelated concepts; "unconfirmed": no reviewed concept matched the wording, so
#: every candidate is only a neighbour by shared words or by meaning and the
#: catalogue may not hold the requested measure at all (DEC-172: "dolar kuru" found
#: one USD loan-rate series and called it the unambiguous default); "none": nothing
#: was found. Deterministic, from reviewed metadata only; the planner still checks
#: declared semantics against the question.
TopCandidate = Literal["unambiguous", "ambiguous", "unconfirmed", "none"]


class CatalogSearchArguments(ContractModel):
    query: StrictStr = Field(min_length=1, max_length=512, repr=False)
    max_results: StrictInt = Field(default=10, ge=1, le=10)
    source: StrictStr | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description=(
            "Provider (EVDS, BDDK) or a publisher the reviewed title/labels name (TÜİK, "
            "TCMB). Omit when unsure: a filter that matches nothing returns FILTERED_OUT "
            "with no candidates"
        ),
    )
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


#: Datagroups one search carries for expansion (each unopened one costs one source read).
MAX_GROUPS = 3


class CatalogSearchOutput(ContractModel):
    status: SearchStatus
    candidates: tuple[CatalogCandidate, ...] = Field(default=(), max_length=10)
    #: Source datagroups found for the query (DEC-177). They are containers, not series: no
    #: plan can read one, so they never sit among `candidates`. `catalog.expansion` replaces
    #: them by their series, or drops them, before a planner sees the result.
    groups: tuple[CatalogCandidate, ...] = Field(default=(), max_length=MAX_GROUPS)
    concepts: tuple[ConceptMatch, ...] = Field(default=(), max_length=MAX_CATALOG_CONCEPTS)
    total_candidates: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    truncated: bool
    clarification_required: bool
    excluded_archived_count: int = Field(ge=0, le=MAX_CATALOG_SERIES)
    snapshot_version: str
    snapshot_sha256: str
    retrieval_version: Literal["m13-04-lexical-v1", "m13-05-combined-v1"] = "m13-04-lexical-v1"
    top_candidate: TopCandidate = "none"
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
    lexical_total_candidates: int | None = Field(default=None, ge=0, le=MAX_CATALOG_SERIES)
    dense_total_candidates: int | None = Field(default=None, ge=0, le=MAX_CATALOG_SERIES)
    untrusted_metadata: Literal[True] = True
    observation_fetch_authorized: Literal[False] = False
    analytical_evidence: Literal[False] = False


#: Shortest final alias word that may carry a suffix: "tufe" + "yi", never "tl" + "ref".
_MIN_SUFFIXED_STEM = 4


def _phrase_in(alias: str, words: list[str]) -> bool:
    """A reviewed alias as whole words of the query; its last word may carry suffixes.

    Turkish inflects the head of a noun phrase, which is its last word: "konut kredisi
    faizi" is asked as "konut kredisi faizini göster" or "... faizinin seyri". Whole-word
    matching alone missed every such question, so a request the catalogue holds looked
    no different from one it does not (DEC-172). Earlier words stay exact.
    """
    wanted = alias.split()
    last = wanted[-1]
    for start in range(len(words) - len(wanted) + 1):
        window = words[start : start + len(wanted)]
        if window[:-1] == wanted[:-1] and (
            window[-1] == last or (len(last) >= _MIN_SUFFIXED_STEM and window[-1].startswith(last))
        ):
            return True
    return False


def _concept_matches(snapshot: ReviewedSnapshot, key: str) -> tuple[list[Concept], SearchMethod]:
    exact = [c for c in snapshot.concepts if any(a.normalized == key for a in c.aliases)]
    if exact:
        return exact, "reviewed_alias"
    # Longest contained phrase wins over its generic substring; identical alias
    # collisions and disjoint concepts remain sets, not last-write-wins entries.
    words = key.split()
    phrases = {
        a.normalized
        for c in snapshot.concepts
        for a in c.aliases
        if a.normalized and _phrase_in(a.normalized, words)
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


def source_matches(item: ReviewedSeries, source: str) -> bool:
    """`source` names the provider (EVDS, BDDK) or a publisher the reviewed text names.

    A CPI series is provided by EVDS and published by TÜİK, and the reviewed
    labels say so; a planner that filters by the publisher it read in a title
    must not empty the result (live R2, 2026-09-19: `source="TÜİK"` returned
    FILTERED_OUT and the planner fell back to the cross-check series).
    """
    wanted = normalize_search_text(source)
    record = item.record
    if normalize_search_text(record.provider) == wanted:
        return True
    named = normalize_search_text(" ".join([record.title, *record.labels]))
    return f" {wanted} " in f" {named} "


def eligible_catalog_series(
    snapshot: ReviewedSnapshot, args: CatalogSearchArguments
) -> tuple[ReviewedSeries, ...]:
    """Shared declared metadata filtering, independent of ranking method."""
    return tuple(
        s
        for s in snapshot.series
        if (args.include_archived or s.record.status is not CatalogStatus.ARCHIVED)
        and (args.source is None or source_matches(s, args.source))
        and (args.frequency is None or s.record.frequency is args.frequency)
    )


def one_per_listed_row[T](
    ordered: Sequence[T], *, reviewed_series: Callable[[T], ReviewedSeries]
) -> list[T]:
    """Keep the first component of each listed row; reviewed entries are all kept.

    A listed BDDK row exists as TP, YP and Toplam, three entries with one title. Ten
    results would otherwise be three rows, three times each. The reviewed-intent order
    has already put first the component the question names, or the total when it names
    none, so the first of each row is the one to show. Reviewed series are untouched:
    their components are told apart by reviewed concepts and defaults (DEC-165).
    """
    seen: set[tuple[str, str | None, str]] = set()
    kept: list[T] = []
    for item in ordered:
        series = reviewed_series(item)
        if is_listed_series(series):
            record = series.record
            row = (record.provider, record.group.group_id if record.group else None, record.title)
            if row in seen:
                continue
            seen.add(row)
        kept.append(item)
    return kept


def top_candidate_signal(
    query: str, candidates: Sequence[CatalogCandidate], *, reviewed_match: bool
) -> TopCandidate:
    """See `TopCandidate`: strictly first by reviewed intent, within one concept or family.

    `reviewed_match` says a reviewed alias or phrase matched the query. Without one the
    candidates are neighbours, however few or however near, and none is a default.
    """
    if not candidates:
        return "none"
    if not reviewed_match:
        return "unconfirmed"
    if len(candidates) == 1:
        return "unambiguous"
    first, second = (intent_key(query, c.series) for c in candidates[:2])
    if not first < second:
        return "ambiguous"
    groups = [set(c.concept_ids) | set(c.family_ids) for c in candidates]
    return "unambiguous" if set.intersection(*groups) else "ambiguous"


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
    # Datagroups declare no kind, unit or currency, so the reviewed-intent order would push
    # every one of them below any series that does. They keep their own relevance order.
    found_groups = [s for s in ranked if is_source_group(s)][:MAX_GROUPS]
    ranked = [s for s in ranked if not is_source_group(s)]
    ranked = rerank_by_reviewed_intent(args.query, ranked, reviewed_series=lambda item: item)
    ranked = one_per_listed_row(ranked, reviewed_series=lambda item: item)
    unresolved = any(c.unresolved for c in matches)
    status: SearchStatus
    if ranked or found_groups:
        # Token overlap can surface useful candidates, but only a reviewed
        # alias/phrase establishes that the requested concept is represented.
        status = "PARTIAL" if unresolved or not matches else "MATCH"
    elif matches and not mapped:
        status = "UNRESOLVED"
    elif matches and mapped:
        status = "FILTERED_OUT"
    else:
        status = "NO_MATCH"
    candidates = tuple(
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
    )
    return CatalogSearchOutput(
        status=status,
        candidates=candidates,
        groups=tuple(
            CatalogCandidate(
                series=s,
                concept_ids=(),
                family_ids=(),
                rank=i + 1,
                bm25_score=scores[s.record.series_id],
                matched_terms=tuple(sorted(query_terms & documents[s.record.series_id].keys())),
                method=method,
            )
            for i, s in enumerate(found_groups)
        ),
        top_candidate=top_candidate_signal(args.query, candidates, reviewed_match=bool(matches)),
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
