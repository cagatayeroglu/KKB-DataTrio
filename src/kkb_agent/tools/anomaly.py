"""The `anomaly` tool: periods that moved unlike the others (M6-06).

Same shape as `change_detection`: read the series' declared semantics from the
lakehouse, hand them to the analytics package, return a typed result and
record lineage for a computed one.

The threshold and the minimum sample are **not** arguments. A planner that can
move a threshold will move it until something looks interesting, and a flag
produced that way is indistinguishable in the output from one that was not.
The defaults are recorded in every result's `parameters` instead, so a reader
can see what produced the flags without the model being able to choose them.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.analytics import detect_anomalies
from kkb_agent.core import AnalyticalResult, ResultStatus
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.tools.change_detection import SeriesUnknown, read_series

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

INPUTS = ("silver_series", "silver_observations")


class AnomalyArguments(BaseModel):
    """What the planner may ask for.

    A window, and nothing that changes how the judgement is made.
    """

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1, max_length=200)
    start: date | None = Field(
        default=None, description="Earliest period end to examine; omit for the whole series"
    )
    end: date | None = Field(
        default=None, description="Latest period end to examine; omit for the whole series"
    )


def make_anomaly_tool(
    connection: DuckDBPyConnection, *, lineage: Lineage | None = None
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, AnomalyArguments):  # pragma: no cover
            raise TypeError("anomaly received arguments it did not declare")
        try:
            series = read_series(connection, arguments.series_id)
        except SeriesUnknown as error:
            return ToolResult(
                ToolStatus.FAILURE,
                step_id="",
                tool="anomaly",
                error_category="series_unknown",
                warnings=(str(error),),
            )

        result = detect_anomalies(
            series.observations,
            series.semantics,
            series_id=arguments.series_id,
            start=arguments.start,
            end=arguments.end,
            input_refs=INPUTS,
        )
        node = _record(lineage, arguments, result)
        if node is not None and result.evidence is not None:
            result = result.model_copy(
                update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
            )

        warnings = tuple(result.warnings)
        if result.status is not ResultStatus.COMPUTED and result.reason is not None:
            warnings = (*warnings, result.reason)
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="anomaly",
            output=result,
            warnings=warnings,
            evidence=node,
        )

    return ToolSpec(
        name="anomaly",
        description=(
            "Find periods whose change stands apart from the rest of the series. "
            "Examines period-over-period changes rather than levels, so a steadily "
            "rising series does not flag its own present. Scored by median absolute "
            "deviation, which a few extreme points cannot inflate. Returns the count "
            "of unusual periods and each one's change; the count is zero when nothing "
            "stands out. Needs at least a year of changes."
        ),
        arguments=AnomalyArguments,
        run=run,
    )


def _record(
    lineage: Lineage | None, arguments: AnomalyArguments, result: AnalyticalResult
) -> str | None:
    if lineage is None or result.status is not ResultStatus.COMPUTED:
        return None
    return lineage.record(
        NodeKind.TRANSFORM,
        "anomaly_mad_zscore",
        attributes={
            "series": arguments.series_id,
            "from": arguments.start.isoformat() if arguments.start else "",
            "to": arguments.end.isoformat() if arguments.end else "",
            "provenance": "series-level; the flagged periods are named in the result",
        },
    )
