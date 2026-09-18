"""The `causality` tool: what it can honestly say (M6-07..M6-11, DEC-120).

The name is the brief's. What the tool does is narrower than the name, and
every result it returns says so in mandatory limitations — the M6-01 contract
refuses a relational result that omits them, so this is enforced by the type
rather than by a reviewer noticing.

Three operations, none of them a causal finding:

- `association` — how closely two series moved together over the periods both
  published.
- `lag` — the same at each offset in a bounded window, with the sign
  convention stated in the label, the parameters and a warning.
- `granger` — whether one series' past improved a prediction of the other's
  beyond its own past, at each order up to the window, in both directions.
  That is predictive precedence, and the result never calls it more.

The `max_lag` window *is* a planner argument, unlike the anomaly threshold: how
far a relationship might lag is a question about the domain, not a knob for
making a number look better. It is capped, and the result says how many
offsets or orders were searched, because the strongest of many is inflated by
the search.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.analytics import (
    DEFAULT_MAX_LAG,
    LAG_CAP,
    associate,
    granger_precedence,
    lagged_association,
)
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.core import AnalyticalResult, ResultStatus, SeriesId
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution
from kkb_agent.tools.change_detection import SeriesUnknown, read_series

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

INPUTS = ("silver_series", "silver_observations")


class CausalityArguments(BaseModel):
    """What the planner may ask for.

    `left` and `right` are ordered, and the order is what the lag sign is
    stated against — swapping them inverts every reported offset.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["association", "lag", "granger"] = Field(
        description=(
            "association: correlation over the periods both series published. "
            "lag: the same at each offset within max_lag. "
            "granger: whether each series' past improved predictions of the other's, "
            "at every order up to max_lag, in both directions."
        )
    )
    left_series_id: SeriesId = Field(min_length=1, max_length=200)
    right_series_id: SeriesId = Field(min_length=1, max_length=200)
    max_lag: int = Field(
        default=DEFAULT_MAX_LAG,
        ge=0,
        le=LAG_CAP,
        description=(
            "Offsets to search on each side for lag, or the highest order for granger "
            "(at least 1); ignored by the association operation"
        ),
    )
    start: date | None = Field(default=None, description="Earliest period end to include")
    end: date | None = Field(default=None, description="Latest period end to include")


def make_causality_tool(
    connection: DuckDBPyConnection,
    *,
    lineage: Lineage | None = None,
    inspector: PreparedSeriesInspector | None = None,
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, CausalityArguments):  # pragma: no cover
            raise TypeError("causality received arguments it did not declare")
        try:
            left = read_series(connection, arguments.left_series_id, inspector=inspector)
            right = read_series(connection, arguments.right_series_id, inspector=inspector)
        except SeriesUnknown as error:
            return ToolResult(
                ToolStatus.FAILURE,
                step_id="",
                tool="causality",
                error_category="series_unknown",
                warnings=(str(error),),
            )

        shared = {
            "left_id": arguments.left_series_id,
            "right_id": arguments.right_series_id,
            "start": arguments.start,
            "end": arguments.end,
            "input_refs": INPUTS,
        }
        if arguments.operation == "association":
            result = associate(
                left.observations,
                left.semantics,
                right.observations,
                right.semantics,
                **shared,  # type: ignore[arg-type]
            )
        elif arguments.operation == "lag":
            result = lagged_association(
                left.observations,
                left.semantics,
                right.observations,
                right.semantics,
                max_lag=arguments.max_lag,
                **shared,  # type: ignore[arg-type]
            )
        else:
            result = granger_precedence(
                left.observations,
                left.semantics,
                right.observations,
                right.semantics,
                max_order=arguments.max_lag,
                **shared,  # type: ignore[arg-type]
            )

        node = _record(lineage, arguments, result)
        if node is not None and result.evidence is not None:
            result = result.model_copy(
                update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
            )

        result = _record_execution(
            connection,
            producer="causality",
            arguments=arguments.model_dump_json(),
            inputs=[left.snapshot, right.snapshot],
            result=result,
        )

        warnings = tuple(result.warnings) + tuple(result.limitations)
        if result.status is not ResultStatus.COMPUTED and result.reason is not None:
            warnings = (*warnings, result.reason)
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="causality",
            output=result,
            warnings=warnings,
            evidence=node,
        )

    return ToolSpec(
        name="causality",
        description=(
            "Measure whether two registered series moved together, optionally at a lag, "
            "or whether one series' past improved predictions of the other's (Granger). "
            "This reports ASSOCIATION ONLY — Granger gives predictive precedence at most — "
            "and cannot establish that one series moves the other; every result carries "
            "that limitation and a third factor moving both would produce the same number. "
            "Series must share a frequency and are compared only on periods both "
            "published. Needs about two years of aligned observations."
        ),
        arguments=CausalityArguments,
        run=run,
    )


def _record(
    lineage: Lineage | None, arguments: CausalityArguments, result: AnalyticalResult
) -> str | None:
    if lineage is None or result.status is not ResultStatus.COMPUTED:
        return None
    return lineage.record(
        NodeKind.TRANSFORM,
        f"causality_{arguments.operation}",
        attributes={
            "left": arguments.left_series_id,
            "right": arguments.right_series_id,
            "max_lag": str(arguments.max_lag),
            "claim": (
                "predictive precedence only; not a causal finding"
                if arguments.operation == "granger"
                else "association only; not a causal finding"
            ),
            "provenance": "series-level; the compared periods are named in the result",
        },
    )
