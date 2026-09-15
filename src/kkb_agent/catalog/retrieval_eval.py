"""M13-09 question-to-series retrieval evaluation over reviewed cases.

Lexical-only, dense-only and combined hybrid candidates are scored on the same
cases with the same filters. `hybrid` uses the DEC-142 reviewed-match order and
`hybrid_alternating` the M13-09 baseline, so both combinations stay comparable.
Relevance comes from a separately reviewed case file, never from the function
under test. Holdout cases are reported separately and are
not a tuning set. Dense modes need an operator-built index and query embedder;
the lexical mode makes no model or network call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from statistics import median
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from kkb_agent.catalog.hybrid import CatalogDenseStage, CombinationPolicy, search_hybrid_catalog
from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import ReviewedSnapshot, load_reviewed_snapshot
from kkb_agent.catalog.normalization import normalize_query_text
from kkb_agent.catalog.records import CatalogStatus
from kkb_agent.catalog.search import (
    CatalogSearchArguments,
    SearchStatus,
    eligible_catalog_series,
    search_catalog,
)
from kkb_agent.catalog.vectors import QueryVector
from kkb_agent.core.models import ContractModel

Mode = Literal["lexical", "dense", "hybrid", "hybrid_alternating"]
COMBINATIONS: dict[str, CombinationPolicy] = {
    "hybrid": "reviewed-match-order-v1",
    "hybrid_alternating": "alternating-archive-tier-v1",
}
SeriesId = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1024)]
MAX_CASES = 200


class RetrievalCase(ContractModel):
    case_id: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_-]{1,32}$")]
    split: Literal["development", "holdout"]
    category: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z_]{1,32}$")]
    query: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
    include_archived: StrictBool = False
    relevant_series_ids: tuple[SeriesId, ...] = ()
    primary_series_id: SeriesId | None = None
    expected_statuses: tuple[SearchStatus, ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if len(set(self.relevant_series_ids)) != len(self.relevant_series_ids):
            raise ValueError("duplicate relevant series")
        if self.primary_series_id and self.primary_series_id not in self.relevant_series_ids:
            raise ValueError("primary series must be relevant")
        if bool(self.relevant_series_ids) == bool(self.expected_statuses):
            raise ValueError("use relevance or expected statuses, not both or neither")
        return self


class CaseSet(ContractModel):
    schema_: Literal["m13-09-retrieval-cases-v1"] = Field(alias="schema")
    snapshot_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    authored: str
    relevance: str
    cases: tuple[RetrievalCase, ...] = Field(min_length=1, max_length=MAX_CASES)


def load_cases(data: bytes, snapshot: ReviewedSnapshot) -> CaseSet:
    cases = CaseSet.model_validate_json(data)
    if cases.snapshot_sha256 != snapshot.content_sha256:
        raise ValueError("case set was reviewed against another catalog snapshot")
    known = {item.record.series_id for item in snapshot.series}
    ids = [case.case_id for case in cases.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")
    if any(sid not in known for case in cases.cases for sid in case.relevant_series_ids):
        raise ValueError("case references a series outside the snapshot")
    if {case.split for case in cases.cases} != {"development", "holdout"}:
        raise ValueError("case set needs development and holdout splits")
    return cases


def _metrics(ranked: Sequence[str], case: RetrievalCase) -> dict[str, object]:
    relevant = set(case.relevant_series_ids)
    first = next((i + 1 for i, sid in enumerate(ranked) if sid in relevant), None)
    return {
        "hit_at_1": bool(ranked) and ranked[0] in relevant,
        "hit_at_5": first is not None and first <= 5,
        "hit_at_10": first is not None and first <= 10,
        "recall_at_5": len(relevant & set(ranked[:5])) / len(relevant),
        "recall_at_10": len(relevant & set(ranked[:10])) / len(relevant),
        "reciprocal_rank": 0.0 if first is None else 1.0 / first,
        "primary_at_1": None
        if case.primary_series_id is None
        else bool(ranked) and ranked[0] == case.primary_series_id,
    }


def evaluate(
    cases: CaseSet,
    snapshot: ReviewedSnapshot,
    modes: Sequence[Mode],
    *,
    dense: CatalogDenseStage | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, object]:
    if any(mode != "lexical" for mode in modes) and dense is None:
        raise ValueError("dense and hybrid modes need an index and query embedder")
    archived = {
        s.record.series_id for s in snapshot.series if s.record.status is CatalogStatus.ARCHIVED
    }
    outcomes: list[dict[str, object]] = []
    for case in cases.cases:
        args = CatalogSearchArguments(
            query=case.query, max_results=10, include_archived=case.include_archived
        )
        for mode in modes:
            began = clock()
            status: str | None
            if mode == "lexical":
                output = search_catalog(snapshot, args)
                ranked = [c.series.record.series_id for c in output.candidates]
                status, degraded = output.status, None
            elif dense is None:
                raise ValueError("dense and hybrid modes need an index and query embedder")
            elif mode in COMBINATIONS:
                stage = replace(dense, combination_policy=COMBINATIONS[mode])
                output = search_hybrid_catalog(snapshot, args, stage)
                ranked = [c.series.record.series_id for c in output.candidates]
                status = output.status
                degraded = output.dense_failure
            else:
                eligible = frozenset(
                    s.record.series_id for s in eligible_catalog_series(snapshot, args)
                )
                query: QueryVector = dense.embed_query(normalize_query_text(case.query))
                hits = dense.index.search(query, eligible_ids=eligible, limit=10)
                ranked = [hit.series_id for hit in hits]
                status, degraded = None, None
            elapsed = (clock() - began) * 1000
            row: dict[str, object] = {
                "case_id": case.case_id,
                "split": case.split,
                "category": case.category,
                "mode": mode,
                "ranked": ranked,
                "status": status,
                "dense_failure": degraded,
                "archived_leak": not case.include_archived and bool(archived & set(ranked)),
                "ms": round(elapsed, 3),
            }
            if case.relevant_series_ids:
                row.update(_metrics(ranked, case))
            else:
                # Dense-only has no abstention; its top candidate is reported, not scored.
                row["status_ok"] = None if status is None else status in case.expected_statuses
                row["top_candidate_without_answer"] = ranked[0] if ranked else None
            outcomes.append(row)
    return {
        "report": "m13-09-retrieval-evaluation-v1",
        "snapshot_sha256": snapshot.content_sha256,
        "cases_sha256": hashlib.sha256(
            cases.model_dump_json(by_alias=True).encode("utf-8")
        ).hexdigest(),
        "modes": list(modes),
        "input_policy_id": None if dense is None else dense.index.profile.input_policy_id,
        "embedding_origin": None if dense is None else dense.index.profile.origin,
        "summary": summarize(outcomes),
        "cases": outcomes,
    }


def top1_changes(
    outcomes: Sequence[dict[str, object]], base: str, other: str
) -> dict[str, dict[str, list[str]]]:
    """Scored cases whose top-1 relevance differs between two modes, per split."""
    rows = {(o["case_id"], o["mode"]): o for o in outcomes if "hit_at_1" in o}
    changes: dict[str, dict[str, list[str]]] = {}
    for split in ("development", "holdout"):
        won, lost = [], []
        for (case_id, mode), row in rows.items():
            paired = rows.get((case_id, base))
            if mode != other or row["split"] != split or paired is None:
                continue
            if row["hit_at_1"] and not paired["hit_at_1"]:
                won.append(str(case_id))
            elif paired["hit_at_1"] and not row["hit_at_1"]:
                lost.append(str(case_id))
        changes[split] = {"won": won, "lost": lost}
    return changes


def summarize(outcomes: Sequence[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for split in ("development", "holdout", "all"):
        for mode in sorted({str(o["mode"]) for o in outcomes}):
            rows = [o for o in outcomes if o["mode"] == mode and split in ("all", o["split"])]
            scored = [o for o in rows if "hit_at_1" in o]
            abstain = [o for o in rows if o.get("status_ok") is not None]
            primary = [o for o in scored if o.get("primary_at_1") is not None]

            def mean(key: str, items: Sequence[dict[str, object]]) -> float | None:
                values = [float(o[key]) for o in items]  # type: ignore[arg-type]
                return round(sum(values) / len(values), 4) if values else None

            summary[f"{split}/{mode}"] = {
                "cases": len(rows),
                "scored": len(scored),
                "hit_at_1": mean("hit_at_1", scored),
                "hit_at_5": mean("hit_at_5", scored),
                "recall_at_5": mean("recall_at_5", scored),
                "recall_at_10": mean("recall_at_10", scored),
                "mrr": mean("reciprocal_rank", scored),
                "primary_at_1": mean("primary_at_1", primary),
                "no_answer_cases": len([o for o in rows if "status_ok" in o]),
                "no_answer_status_ok": mean("status_ok", abstain),
                "archived_leaks": sum(bool(o["archived_leak"]) for o in rows),
                "dense_failures": sum(o.get("dense_failure") is not None for o in rows),
                "median_ms": round(median(float(o["ms"]) for o in rows), 3) if rows else None,  # type: ignore[arg-type]
            }
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M13-09 catalog retrieval evaluation")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--index", type=Path, help="Built catalog index generation for dense modes")
    parser.add_argument("--policy", help="Input policy of the index")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--enable-embedding-requests", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = load_reviewed_snapshot(args.catalog.absolute().read_bytes())
    cases = load_cases(args.cases.absolute().read_bytes(), snapshot)
    if args.index is None:
        report = evaluate(cases, snapshot, ["lexical"])
    else:
        if not args.enable_embedding_requests or args.policy is None:
            parser.error("dense modes need --policy and --enable-embedding-requests")
        from kkb_agent.api.__main__ import literal_config
        from kkb_agent.catalog.embedding import (
            EmbeddingStats,
            profile_for,
            query_embedder,
            require_model,
        )
        from kkb_agent.llm import KloudeksProvider, approved_base_url

        config = literal_config(args.env_file)
        approved_base_url(config.base_url)
        require_model(config.embedding_model)
        index = LocalCatalogIndex.open(
            args.index.absolute(), snapshot, profile_for(args.policy, "kloudeks")
        )
        stats = EmbeddingStats()
        with KloudeksProvider(config) as provider:
            dense = CatalogDenseStage(
                index, query_embedder(provider, args.policy, origin="kloudeks", stats=stats)
            )
            report = evaluate(
                cases, snapshot, ["lexical", "dense", "hybrid", "hybrid_alternating"], dense=dense
            )
        report["top1_changes"] = {
            f"{other}_vs_{base}": top1_changes(report["cases"], base, other)  # type: ignore[arg-type]
            for base, other in (
                ("lexical", "dense"),
                ("lexical", "hybrid"),
                ("hybrid_alternating", "hybrid"),
                ("dense", "hybrid"),
            )
        }
        report["query_embedding_requests"] = stats.requests
        report["query_embedding_seconds"] = round(stats.seconds, 3)
    args.out.absolute().parent.mkdir(parents=True, exist_ok=True)
    args.out.absolute().write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
