"""Bounded two-stage candidate union; no score arithmetic or automatic selection."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, get_args

from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import ReviewedSnapshot, is_source_group
from kkb_agent.catalog.normalization import normalize_query_text
from kkb_agent.catalog.ranking import rerank_by_reviewed_intent, rerank_widened
from kkb_agent.catalog.search import (
    MAX_GROUPS,
    CatalogCandidate,
    CatalogSearchArguments,
    CatalogSearchOutput,
    eligible_catalog_series,
    named_calendar_first,
    one_per_listed_row,
    scoped_to_named_calendar,
    search_catalog,
    top_candidate_signal,
)
from kkb_agent.catalog.vectors import QueryVector

#: DEC-142 order first; the M13-09 alternating baseline stays measurable.
CombinationPolicy = Literal["reviewed-match-order-v1", "alternating-archive-tier-v1"]


@dataclass(frozen=True, slots=True)
class CatalogDenseStage:
    """Operator injection; embedding transport/input policy is owned by the caller.

    No endpoint, credential, prefix or external fallback is selected here. The
    embedding callback must follow its declared policy for normalized query text
    and return a QueryVector whose profile matches the checked local index.
    `reviewed-match-order-v1` (DEC-142) interleaves lexical-first only when a
    reviewed alias or phrase matched, and dense-first otherwise.
    """

    index: LocalCatalogIndex
    embed_query: Callable[[str], QueryVector]
    combination_policy: CombinationPolicy = "reviewed-match-order-v1"

    def __post_init__(self) -> None:
        if self.combination_policy not in get_args(CombinationPolicy):
            raise ValueError("unknown catalog combination policy")


def search_hybrid_catalog(
    snapshot: ReviewedSnapshot,
    arguments: CatalogSearchArguments,
    dense: CatalogDenseStage,
    *,
    bounded: bool = True,
) -> CatalogSearchOutput:
    """`bounded` as in `search_catalog`: unbounded, a reviewed match does not close either stage."""
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    args = CatalogSearchArguments.model_validate(arguments)
    # The same series for both stages: a question naming a finer calendar than its reviewed
    # concept has is searched among series of that calendar (DEC-182).
    args, _ = scoped_to_named_calendar(snapshot, args)
    # Equal fixed stage budgets; max_results only truncates the final union.
    stage_args = CatalogSearchArguments.model_validate({**args.model_dump(), "max_results": 10})
    lexical = search_catalog(snapshot, stage_args, bounded=bounded)
    profile = dense.index.profile
    metadata = {
        "retrieval_version": "m13-05-combined-v1",
        "combination_policy": dense.combination_policy,
        "embedding_origin": profile.origin,
        "input_policy_id": profile.input_policy_id,
        "profile_sha256": profile.fingerprint(),
        "lexical_total_candidates": lexical.total_candidates,
    }

    def lexical_result(
        status: Literal["skipped_no_eligible", "failed"],
        failure: Literal["snapshot_mismatch", "embedding_failed", "index_failed"] | None = None,
    ) -> CatalogSearchOutput:
        return CatalogSearchOutput.model_validate(
            {
                **lexical.model_dump(),
                **metadata,
                "candidates": [
                    {**c.model_dump(), "lexical_rank": c.rank}
                    for c in lexical.candidates[: args.max_results]
                ],
                "truncated": lexical.total_candidates > args.max_results,
                "retrieval_mode": "lexical_degraded" if failure else "lexical_only",
                "dense_status": status,
                "dense_failure": failure,
            }
        )

    eligible = {s.record.series_id: s for s in eligible_catalog_series(snapshot, args)}
    matched = {c.concept_id for c in lexical.concepts}
    mapped = {
        sid for c in snapshot.concepts if c.concept_id in matched for sid in c.candidate_series_ids
    }
    if lexical.concepts and bounded:
        # Exact/longest reviewed phrases cannot expand into a merely nearby concept.
        eligible = {sid: item for sid, item in eligible.items() if sid in mapped}
    # Datagroups are searched by meaning in their own lane (DEC-177), never among series.
    containers = {sid: item for sid, item in eligible.items() if is_source_group(item)}
    eligible = {sid: item for sid, item in eligible.items() if sid not in containers}
    if not eligible:
        return lexical_result("skipped_no_eligible")
    # A vector answers for the text it was made from. An entry added to the catalogue leaves
    # every other entry's vector exactly as sound as it was, so meaning-based search keeps
    # the identities this generation still covers instead of turning itself off (N27).
    covered = dense.index.covering(snapshot)
    dense_ids = frozenset(eligible) & covered
    dense_groups_ids = frozenset(containers) & covered
    if not dense_ids:
        return lexical_result("failed", "snapshot_mismatch")
    try:
        query = QueryVector.model_validate(dense.embed_query(normalize_query_text(args.query)))
        if query.profile != profile:
            raise ValueError("query profile mismatch")
    except Exception:
        return lexical_result("failed", "embedding_failed")
    try:
        hits = dense.index.search(query, eligible_ids=dense_ids, limit=10)
        # Recheck the public stage boundary even if an injected implementation fails.
        if (
            len(hits) != min(len(dense_ids), 10)
            or len({hit.series_id for hit in hits}) != len(hits)
            or any(
                hit.series_id not in dense_ids
                or type(hit.rank) is not int
                or hit.rank != i + 1
                or not isinstance(hit.cosine_distance, float)
                or not math.isfinite(hit.cosine_distance)
                or not -0.000001 <= hit.cosine_distance <= 2.000001
                for i, hit in enumerate(hits)
            )
        ):
            raise ValueError("invalid dense identities or ranks")
        group_hits = (
            dense.index.search(query, eligible_ids=dense_groups_ids, limit=MAX_GROUPS)
            if dense_groups_ids
            else []
        )
        if any(hit.series_id not in containers for hit in group_hits):
            raise ValueError("invalid dense group identities")
    except Exception:
        return lexical_result("failed", "index_failed")
    # Meaning first, then words: a datagroup title rarely shares the question's inflection.
    group_order: list[str] = []
    for group_id in [h.series_id for h in group_hits] + [
        c.series.record.series_id for c in lexical.groups
    ]:
        if group_id not in group_order:
            group_order.append(group_id)
    lexical_groups = {c.series.record.series_id: c for c in lexical.groups}
    dense_groups = {h.series_id: h for h in group_hits}
    groups = [
        CatalogCandidate(
            series=containers[gid],
            concept_ids=(),
            family_ids=(),
            rank=rank,
            bm25_score=lexical_groups[gid].bm25_score if gid in lexical_groups else None,
            matched_terms=lexical_groups[gid].matched_terms if gid in lexical_groups else (),
            method=lexical_groups[gid].method if gid in lexical_groups else "dense",
            retrieval_sources=("lexical", "dense")
            if gid in lexical_groups and gid in dense_groups
            else (("lexical",) if gid in lexical_groups else ("dense",)),
            lexical_rank=lexical_groups[gid].rank if gid in lexical_groups else None,
            dense_rank=dense_groups[gid].rank if gid in dense_groups else None,
            cosine_distance=dense_groups[gid].cosine_distance if gid in dense_groups else None,
        )
        for rank, gid in enumerate(group_order[:MAX_GROUPS], start=1)
        if gid in containers
    ]
    lexical_by_id = {c.series.record.series_id: c for c in lexical.candidates}
    dense_by_id = {h.series_id: h for h in hits}
    lexical_ids = [c.series.record.series_id for c in lexical.candidates]
    ranked_ids = [h.series_id for h in hits]
    # A reviewed alias/phrase match already bounded eligibility to its concepts;
    # without one, BM25 overlap is weaker evidence than the dense rank (M13-09).
    lexical_first = dense.combination_policy == "alternating-archive-tier-v1" or bool(
        lexical.concepts
    )
    first, second = (lexical_ids, ranked_ids) if lexical_first else (ranked_ids, lexical_ids)
    order: list[str] = []
    for i in range(max(len(first), len(second))):
        for sid in (
            first[i] if i < len(first) else None,
            second[i] if i < len(second) else None,
        ):
            if sid is not None and sid not in order:
                order.append(sid)
    # Explicit qualifiers may refine stage order, but not candidate membership or
    # retrieval status. Without archive intent, archived candidates remain last.
    if lexical.concepts and not bounded:
        order = rerank_widened(
            args.query,
            order,
            reviewed_series=lambda series_id: eligible[series_id],
            reviewed=lambda series_id: series_id in mapped,
        )
    else:
        order = rerank_by_reviewed_intent(
            args.query, order, reviewed_series=lambda series_id: eligible[series_id]
        )
    if not lexical.concepts:
        order = named_calendar_first(
            args.query, order, reviewed_series=lambda series_id: eligible[series_id]
        )
    order = one_per_listed_row(
        order, reviewed_series=lambda series_id: eligible[series_id], query=args.query
    )
    candidates = []
    for rank, sid in enumerate(order[: args.max_results], start=1):
        lex = lexical_by_id.get(sid)
        hit = dense_by_id.get(sid)
        item = eligible[sid]  # Always the reviewed record, never metadata from the vector table.
        concepts = [c for c in snapshot.concepts if sid in c.candidate_series_ids]
        candidates.append(
            CatalogCandidate(
                series=item,
                concept_ids=tuple(sorted(c.concept_id for c in concepts)),
                family_ids=tuple(sorted({f for c in concepts for f in c.family_ids})),
                rank=rank,
                bm25_score=lex.bm25_score if lex else None,
                matched_terms=lex.matched_terms if lex else (),
                method=lex.method if lex else "dense",
                retrieval_sources=("lexical", "dense")
                if lex and hit
                else (("lexical",) if lex else ("dense",)),
                lexical_rank=lex.rank if lex else None,
                dense_rank=hit.rank if hit else None,
                cosine_distance=hit.cosine_distance if hit else None,
            )
        )
    return CatalogSearchOutput.model_validate(
        {
            **lexical.model_dump(),
            **metadata,
            "candidates": [c.model_dump() for c in candidates],
            "groups": [c.model_dump() for c in groups],
            "top_candidate": top_candidate_signal(
                args.query,
                candidates,
                reviewed_match=bool(lexical.concepts),
                available_kinds=frozenset(eligible[sid].record.stock_flow for sid in order),
                runner_up=eligible[order[1]] if len(order) > 1 else None,
            ),
            # Dense/BM25 proximity without a reviewed concept is a candidate for
            # clarification, not evidence that the requested intent is mapped.
            "status": "PARTIAL"
            if not lexical.concepts or any(c.unresolved for c in lexical.concepts)
            else "MATCH",
            "total_candidates": len(order),
            "truncated": len(order) > args.max_results or lexical.truncated or len(eligible) > 10,
            "clarification_required": True,
            "retrieval_mode": "hybrid",
            "dense_status": "success",
            # What the second stage actually ranked, which is not every eligible series when
            # the catalogue has moved on since the vectors were built.
            "dense_total_candidates": len(dense_ids),
        }
    )
