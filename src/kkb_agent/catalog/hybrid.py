"""Bounded two-stage candidate union; no score arithmetic or automatic selection."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import ReviewedSnapshot
from kkb_agent.catalog.normalization import normalize_query_text
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.catalog.search import (
    CatalogCandidate,
    CatalogSearchArguments,
    CatalogSearchOutput,
    eligible_catalog_series,
    search_catalog,
)
from kkb_agent.catalog.vectors import QueryVector


@dataclass(frozen=True, slots=True)
class CatalogDenseStage:
    """Operator injection; embedding transport/input policy is owned by the caller.

    No endpoint, credential, prefix or external fallback is selected here. The
    embedding callback must follow its declared policy for normalized query text
    and return a QueryVector whose profile matches the checked local index.
    """

    index: LocalCatalogIndex
    embed_query: Callable[[str], QueryVector]


def search_hybrid_catalog(
    snapshot: ReviewedSnapshot, arguments: CatalogSearchArguments, dense: CatalogDenseStage
) -> CatalogSearchOutput:
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    args = CatalogSearchArguments.model_validate(arguments)
    # Equal fixed stage budgets; max_results only truncates the final union.
    stage_args = CatalogSearchArguments.model_validate({**args.model_dump(), "max_results": 10})
    lexical = search_catalog(snapshot, stage_args)
    profile = dense.index.profile
    metadata = {
        "retrieval_version": "m13-05-combined-v1",
        "combination_policy": "alternating-archive-tier-v1",
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

    if dense.index.snapshot_sha256 != snapshot.content_sha256:
        return lexical_result("failed", "snapshot_mismatch")
    eligible = {s.record.series_id: s for s in eligible_catalog_series(snapshot, args)}
    if lexical.concepts:
        matched = {c.concept_id for c in lexical.concepts}
        mapped = {
            sid
            for c in snapshot.concepts
            if c.concept_id in matched
            for sid in c.candidate_series_ids
        }
        # Exact/longest reviewed phrases cannot expand into a merely nearby concept.
        eligible = {sid: item for sid, item in eligible.items() if sid in mapped}
    if not eligible:
        return lexical_result("skipped_no_eligible")
    try:
        query = QueryVector.model_validate(dense.embed_query(normalize_query_text(args.query)))
        if query.profile != profile:
            raise ValueError("query profile mismatch")
    except Exception:
        return lexical_result("failed", "embedding_failed")
    try:
        hits = dense.index.search(query, eligible_ids=frozenset(eligible), limit=10)
        # Recheck the public stage boundary even if an injected implementation fails.
        if (
            len(hits) != min(len(eligible), 10)
            or len({hit.series_id for hit in hits}) != len(hits)
            or any(
                hit.series_id not in eligible
                or type(hit.rank) is not int
                or hit.rank != i + 1
                or not isinstance(hit.cosine_distance, float)
                or not math.isfinite(hit.cosine_distance)
                or not -0.000001 <= hit.cosine_distance <= 2.000001
                for i, hit in enumerate(hits)
            )
        ):
            raise ValueError("invalid dense identities or ranks")
    except Exception:
        return lexical_result("failed", "index_failed")
    lexical_by_id = {c.series.record.series_id: c for c in lexical.candidates}
    dense_by_id = {h.series_id: h for h in hits}
    order: list[str] = []
    for i in range(max(len(lexical.candidates), len(hits))):
        for sid in (
            lexical.candidates[i].series.record.series_id if i < len(lexical.candidates) else None,
            hits[i].series_id if i < len(hits) else None,
        ):
            if sid is not None and sid not in order:
                order.append(sid)
    # Explicit archive opt-in permits archived candidates, not silent preference.
    order.sort(key=lambda sid: eligible[sid].record.status is CatalogStatus.ARCHIVED)
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
            "status": "PARTIAL" if any(c.unresolved for c in lexical.concepts) else "MATCH",
            "total_candidates": len(order),
            "truncated": len(order) > args.max_results or lexical.truncated or len(eligible) > 10,
            "clarification_required": True,
            "retrieval_mode": "hybrid",
            "dense_status": "success",
            "dense_total_candidates": len(eligible),
        }
    )
