"""The `anomaly` tool: periods that moved unlike the others (M6-06).

Same shape as `change_detection`: read the series' declared semantics from the
lakehouse, hand them to the analytics package, return a typed result and
record lineage for a computed one.

The threshold and the minimum sample are optional arguments with the analytics
package's defaults. They were withheld from the planner on the reasoning that a
model able to move a threshold would move it until something looked interesting.
What actually answers that worry is the record, not the refusal: every result
carries the values it was scored with in `parameters`, alongside
`threshold_status: "PROPOSED; no benchmark has measured it"`, so a flag produced
at a loosened threshold is not indistinguishable from one produced at the
default — it says so. Withholding them only meant a reader asking for finer or
coarser sensitivity could not be served at all.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import TableInput, ToolSpec
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics import detect_anomalies
from kkb_agent.analytics.anomaly import DEFAULT_MINIMUM_CHANGES, DEFAULT_THRESHOLD
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.core import AnalyticalResult, ResultStatus, SeriesId
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution
from kkb_agent.tools.causality import _column_of, _ReadColumn
from kkb_agent.tools.change_detection import SeriesUnknown, read_series

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

INPUTS = ("silver_series", "silver_observations")


class AnomalyArguments(BaseModel):
    """What the planner may ask for.

    A raw series or explicit table quantity, a window, and optionally the scoring
    sensitivity. Whatever is used is recorded in the result's `parameters`.
    """

    model_config = ConfigDict(extra="forbid")

    series_id: SeriesId | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description="Published table name or prior step_id; list the step in depends_on. "
        "Scores the selected column VALUES directly, never their differences. "
        "For anomalies in percentage changes, first derive that column with table_transform.",
    )
    column: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
        description="Exact label of the quantity to analyze in source",
    )

    @model_validator(mode="after")
    def one_input(self) -> AnomalyArguments:
        if self.series_id and not self.source and not self.column:
            return self
        if self.source and self.column and not self.series_id:
            return self
        raise ValueError("Give series_id OR source and column, never both")

    start: date | None = Field(
        default=None, description="Earliest period end to examine; omit for the whole series"
    )
    end: date | None = Field(
        default=None, description="Latest period end to examine; omit for the whole series"
    )
    threshold: float | None = Field(
        default=None,
        gt=0,
        le=20,
        description="Robust score above which a period is flagged; omit for the default "
        f"({DEFAULT_THRESHOLD}). Lower it when the reader asks for milder deviations too, "
        "raise it when they want only the starkest. The value used is reported.",
    )
    minimum_changes: int | None = Field(
        default=None,
        ge=3,
        le=240,
        description="Fewest observations the window must hold before anything is scored; "
        f"omit for the default ({DEFAULT_MINIMUM_CHANGES}). Below it the tool reports an "
        "insufficient sample instead of flags.",
    )


def make_anomaly_tool(
    connection: DuckDBPyConnection,
    *,
    lineage: Lineage | None = None,
    inspector: PreparedSeriesInspector | None = None,
    workspace: Workspace | None = None,
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, AnomalyArguments):  # pragma: no cover
            raise TypeError("anomaly received arguments it did not declare")
        try:
            if arguments.source is not None:
                source: object = None
                if workspace is not None:
                    try:
                        source = workspace.value_of(arguments.source)
                    except WorkspaceError:
                        pass
                if source is None:
                    produced = context.outputs.get(arguments.source)
                    source = getattr(produced, "result", produced)
                if (
                    not isinstance(source, AnalyticalResult)
                    or source.status is not ResultStatus.COMPUTED
                    or result_faults({"input": source}, connection)
                ):
                    return ToolResult(
                        ToolStatus.FAILURE,
                        "",
                        "anomaly",
                        error_category="table_reference",
                        warnings=("The referenced table is unavailable or cannot be verified",),
                    )
                column = _column_of(source, arguments.column or "")
                if isinstance(column, str):
                    return ToolResult(
                        ToolStatus.FAILURE,
                        "",
                        "anomaly",
                        error_category="needs_input",
                        warnings=(column,),
                    )
                series = column
            else:
                found = read_series(connection, arguments.series_id or "", inspector=inspector)
                series = _ReadColumn(found.semantics, found.observations, found.snapshot)
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
            series_id=arguments.series_id or arguments.column or "",
            basis="values" if arguments.source is not None else "changes",
            start=arguments.start,
            end=arguments.end,
            input_refs=INPUTS,
            threshold=(DEFAULT_THRESHOLD if arguments.threshold is None else arguments.threshold),
            minimum_changes=(
                DEFAULT_MINIMUM_CHANGES
                if arguments.minimum_changes is None
                else arguments.minimum_changes
            ),
        )
        node = _record(lineage, arguments, result)
        if node is not None and result.evidence is not None:
            result = result.model_copy(
                update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
            )

        result = _record_execution(
            connection,
            producer="anomaly",
            arguments=arguments.model_dump_json(),
            inputs=[series.snapshot],
            result=result,
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
            "stands out. Needs at least twelve samples. Raw positive levels are scored "
            "on log ratios (rates on differences), NOT simple percentage changes. "
            "With source and column, score the supplied values directly instead; use this "
            "for a requested derived quantity. Never substitute raw levels for a derived column."
        ),
        arguments=AnomalyArguments,
        run=run,
        table_input=lambda args: (
            TableInput(source=args.source)
            if isinstance(args, AnomalyArguments) and args.source is not None
            else None
        ),
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
            "series": arguments.series_id or arguments.column or "",
            "source": arguments.source or "",
            "from": arguments.start.isoformat() if arguments.start else "",
            "to": arguments.end.isoformat() if arguments.end else "",
            "provenance": "series-level; the flagged periods are named in the result",
        },
    )
