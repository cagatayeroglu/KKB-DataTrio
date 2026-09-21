"""M13-04 factory; reviewed bytes are operator configuration, never planner input."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.catalog.search import (
    CatalogSearchArguments,
    CatalogSearchOutput,
    search_catalog,
)

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.catalog.hybrid import CatalogDenseStage


def make_catalog_search_tool(
    *,
    snapshot_bytes: bytes,
    dense: CatalogDenseStage | None = None,
    expand: Callable[[str, CatalogSearchOutput], CatalogSearchOutput] | None = None,
) -> ToolSpec:
    """`expand` is operator wiring (DEC-177): it opens a found source datagroup into the
    series the source lists under it, so the planner only ever sees readable identities."""
    snapshot = load_reviewed_snapshot(snapshot_bytes)

    def search(arguments: CatalogSearchArguments) -> CatalogSearchOutput:
        if dense is None:
            return search_catalog(snapshot, arguments)
        # Ordinary lexical/runtime imports do not initialize the native vector engine.
        from kkb_agent.catalog.hybrid import search_hybrid_catalog

        return search_hybrid_catalog(snapshot, arguments, dense)

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # Fresh validated models per call prevent callers mutating subsequent results.
        args = CatalogSearchArguments.model_validate(arguments)
        output = search(args)
        if not output.candidates and not output.groups and (args.source or args.frequency):
            # A filter narrows a search; it must never be the reason a search finds nothing.
            # Twice live (TÜİK 2026-09-19, TCMB 2026-09-21) a planner named the institution
            # it had in mind, the provider label differed, and the turn was lost to it.
            relaxed = args.model_copy(update={"source": None, "frequency": None})
            again = search(relaxed)
            if again.candidates or again.groups:
                output = again.model_copy(
                    update={
                        "relaxed_filters": tuple(
                            name for name in ("source", "frequency") if getattr(args, name)
                        )
                    }
                )
        # A datagroup is never shown as a candidate: it is opened into series, or dropped.
        output = (
            expand(args.query, output)
            if expand is not None
            else output.model_copy(update={"groups": ()})
        )
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
            "Find the catalogue ID of a measure: BDDK monthly and weekly bulletins, FinTürk "
            "province tables, TCMB/EVDS series, prices and indices, and datasets the reader "
            "saved. Returns up to ten candidates with title, kind (stock, flow, rate, "
            "index), unit, frequency and tier; it reads no values. Query with a few Turkish "
            "keywords for ONE measure ('konut kredisi bakiyesi', 'tüketici fiyat endeksi'); "
            "name a province or 'haftalık' in the query to reach province or weekly series. "
            "Leave source and frequency empty unless the person named one: a finer series "
            "can be reduced later, a filtered-out one cannot be found."
        ),
        arguments=CatalogSearchArguments,
        run=run,
        discovery_only=True,
    )
