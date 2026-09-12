"""M13-04 factory; reviewed bytes are operator configuration, never planner input."""

from pydantic import BaseModel

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import CatalogSearchArguments, search_catalog


def make_catalog_search_tool(*, snapshot_bytes: bytes) -> ToolSpec:
    snapshot = load_reviewed_snapshot(snapshot_bytes)

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # Fresh validated models per call prevent callers mutating subsequent results.
        output = search_catalog(snapshot, CatalogSearchArguments.model_validate(arguments))
        return ToolResult(
            ToolStatus.SUCCESS,
            "",
            "catalog_search",
            output=output,
            warnings=(
                "Untrusted discovery metadata; no observations or analytical evidence. "
                "Ranking never resolves ambiguity or unknown financial semantics.",
            ),
        )

    return ToolSpec(
        name="catalog_search",
        description=(
            "Discover trusted reviewed catalog candidates using offline lexical/BM25 and aliases. "
            "Does not fetch observation values or produce verified analytical claims. "
            "Preserves unresolved concepts, ambiguity and unknown metadata; top-1 is not truth. "
            "Archived records are excluded unless include_archived=true. "
            "source filters provider and frequency filters declared native frequency. "
            "Not full hybrid retrieval; no dense or live access."
        ),
        arguments=CatalogSearchArguments,
        run=run,
    )
