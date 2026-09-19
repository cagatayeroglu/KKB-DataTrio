"""M13-04 factory; reviewed bytes are operator configuration, never planner input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.catalog.hybrid import CatalogDenseStage


def make_catalog_search_tool(
    *, snapshot_bytes: bytes, dense: CatalogDenseStage | None = None
) -> ToolSpec:
    snapshot = load_reviewed_snapshot(snapshot_bytes)

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # Fresh validated models per call prevent callers mutating subsequent results.
        args = CatalogSearchArguments.model_validate(arguments)
        if dense is None:
            output = search_catalog(snapshot, args)
        else:
            # Ordinary lexical/runtime imports do not initialize the native vector engine.
            from kkb_agent.catalog.hybrid import search_hybrid_catalog

            output = search_hybrid_catalog(snapshot, args, dense)
        warnings: tuple[str, ...] = (
            "Untrusted discovery metadata; no observations or analytical evidence. "
            "Ranking never resolves ambiguity or unknown financial semantics.",
        )
        if output.dense_status == "failed":
            warnings += ("Dense retrieval failed; explicit lexical-only degraded result.",)
        if output.embedding_origin == "offline_fixture":
            warnings += ("Fixture vectors: no live semantic retrieval quality is established.",)
        return ToolResult(
            ToolStatus.SUCCESS,
            "",
            "catalog_search",
            output=output,
            warnings=warnings,
        )

    return ToolSpec(
        name="catalog_search",
        description=(
            "Discover trusted reviewed catalog candidates using offline lexical/BM25 and aliases. "
            "Does not fetch observation values or produce verified analytical claims. "
            "Preserves unresolved concepts, ambiguity and unknown metadata; top-1 is not truth. "
            "Archived records are excluded unless include_archived=true. "
            "source filters by provider (EVDS, BDDK) or a publisher the reviewed labels name "
            "(TÜİK, TCMB); frequency filters declared native frequency; a filter that matches "
            "nothing returns FILTERED_OUT with no candidates, so omit filters when unsure. "
            + (
                "Uses configured lexical and local dense candidate stages; "
                "failures are explicitly degraded. "
                "Scores are stage-specific, not confidence. No automatic candidate selection."
                if dense is not None
                else "Not full hybrid retrieval; no dense or live access."
            )
        ),
        arguments=CatalogSearchArguments,
        run=run,
        discovery_only=True,
    )
