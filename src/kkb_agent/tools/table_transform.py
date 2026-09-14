"""The `table_transform` tool: change a published table without rebuilding it (M5-20).

The organizer's second and third turns begin "without disturbing the table".
That is a statement about state: the follow-up must start from the result the
user already accepted, keep every value in it exactly, and add what was asked
for as a new, traceable column. So this tool reads a published workspace result
by name — never a table the model describes — and returns that result's values
unchanged plus the new ones.

Only delivered operations are offered (DEC-135). `deflate` (M2-15) is the first:
one currency column in the prices of an explicit reference month, using a
registered monthly price index. Rebase, add_series, align and filters join the
schema only when they exist.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics.deflation import FORMULA, METHOD, DeflationRefused, deflate
from kkb_agent.core import AnalyticalResult, ResultEvidence, ResultKind, ResultStatus
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.lakehouse.semantics import SeriesSemantics
from kkb_agent.tools.change_detection import SeriesUnknown, read_series

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

INPUTS = ("silver_series", "silver_observations")
NOMINAL_LIMITATION = "Values are nominal; no inflation adjustment was applied"


class TableTransformArguments(BaseModel):
    """What the planner may ask for; references only, never table contents."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["deflate"] = Field(
        description=(
            "deflate: add an inflation-adjusted copy of one currency column, in the prices of "
            "reference_period, keeping every existing column unchanged"
        )
    )
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description="Name of a published result from an earlier turn",
    )
    column: str = Field(
        min_length=1,
        max_length=400,
        description="The column's exact label in that result",
    )
    index_series_id: str = Field(
        min_length=1, max_length=200, description="A registered monthly price index series"
    )
    reference_period: date = Field(
        description=(
            "Last day of the month whose prices the real values are expressed in, "
            "for example the table's last month"
        )
    )

    @model_validator(mode="after")
    def month_end(self) -> Self:
        following = date.fromordinal(self.reference_period.toordinal() + 1)
        if following.day != 1:
            raise ValueError("reference_period must be the last day of a month")
        return self


def make_table_transform_tool(
    connection: DuckDBPyConnection,
    workspace: Workspace,
    *,
    lineage: Lineage | None = None,
    series_names: Mapping[str, str] | None = None,
) -> ToolSpec:
    """Bind the tool to one database and one workspace."""
    names = dict(series_names or {})

    def failure(category: str, message: str) -> ToolResult:
        return ToolResult(
            ToolStatus.FAILURE,
            step_id="",
            tool="table_transform",
            error_category=category,
            warnings=(message,),
        )

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(arguments, TableTransformArguments):  # pragma: no cover
            raise TypeError("table_transform received arguments it did not declare")
        try:
            source = workspace.value_of(arguments.source)
        except WorkspaceError:
            return failure(
                "workspace_reference",
                f"No current published result is named {arguments.source!r}",
            )
        if source.status is not ResultStatus.COMPUTED:
            return failure("workspace_reference", f"{arguments.source!r} holds no computed values")
        try:
            index = read_series(connection, arguments.index_series_id)
        except SeriesUnknown as error:
            return failure("series_unknown", str(error))

        result = _deflated(arguments, source, index.observations, index.semantics, names)
        node = None
        if lineage is not None and result.status is ResultStatus.COMPUTED:
            node = lineage.record(
                NodeKind.TRANSFORM,
                "table_transform_deflate",
                attributes={
                    "source": arguments.source,
                    "column": arguments.column,
                    "index": arguments.index_series_id,
                    "reference_period": arguments.reference_period.isoformat(),
                },
            )
            if result.evidence is not None:
                result = result.model_copy(
                    update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
                )
        result = _record_execution(
            connection,
            producer="table_transform",
            arguments=arguments.model_dump_json(),
            inputs=[
                canonical(
                    {"workspace": arguments.source, "result": source.model_dump(mode="json")}
                ),
                index.snapshot,
            ],
            result=result,
        )
        warnings = tuple(result.warnings)
        if result.status is not ResultStatus.COMPUTED and result.reason is not None:
            warnings = (*warnings, result.reason)
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="table_transform",
            output=result,
            warnings=warnings,
            evidence=node,
        )

    return ToolSpec(
        name="table_transform",
        description=(
            "Change a table published in an earlier turn without disturbing it: every existing "
            "value is kept exactly and the requested column is added. deflate adds an "
            "inflation-adjusted copy of one currency column (for example a credit balance) in "
            "the prices of reference_period, using a registered monthly price index such as a "
            "consumer price index. Refer to the published result by its name and to the column "
            "by its exact label."
        ),
        arguments=TableTransformArguments,
        run=run,
    )


def _deflated(
    arguments: TableTransformArguments,
    source: AnalyticalResult,
    index_observations: Sequence[Observation],
    index_semantics: SeriesSemantics,
    names: Mapping[str, str],
) -> AnalyticalResult:
    result_id = (
        f"table_transform:deflate:{arguments.source}:{arguments.index_series_id}:"
        f"{arguments.reference_period.isoformat()}"
    )
    column = [value for value in source.values if value.label == arguments.column]
    try:
        deflated = deflate(
            column,
            index_observations,
            index_semantics,
            column_label=arguments.column,
            index_id=arguments.index_series_id,
            reference_end=arguments.reference_period,
        )
    except DeflationRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=METHOD,
            reason=str(error),
        )
    if any(value.label == deflated.label for value in source.values):
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=METHOD,
            reason=f"{arguments.source!r} already holds that real column",
        )
    known = source.parameters.get("series_names")
    series_names = dict(known) if isinstance(known, dict) else {}
    if arguments.index_series_id in names:
        series_names[arguments.index_series_id] = names[arguments.index_series_id]
    parameters = dict(source.parameters)
    parameters.update(
        {
            "series_names": series_names,
            "source": arguments.source,
            "deflation": deflated.transformation.parameters,
        }
    )
    warnings = list(source.warnings)
    if deflated.missing_periods:
        warnings.append(
            f"{len(deflated.missing_periods)} period(s) have no index value and no real value"
        )
    previous = source.evidence.transformations if source.evidence is not None else []
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=METHOD,
        values=[*source.values, *deflated.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            # The published result's own lineage node, so the chain resolves.
            input_refs=[
                *(
                    [source.evidence.lineage_node]
                    if source.evidence is not None and source.evidence.lineage_node
                    else []
                ),
                *INPUTS,
            ],
            transformations=[*previous, deflated.transformation],
        ),
        warnings=warnings,
        limitations=[
            *(item for item in source.limitations if item != NOMINAL_LIMITATION),
            f"Only {deflated.label} is inflation-adjusted ({FORMULA}); every other column is "
            "unchanged and nominal",
            "A consumer-price deflator gives purchasing-power terms, not a volume measure",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )
