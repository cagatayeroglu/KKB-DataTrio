"""The table-input operation of change_detection, with verified reference boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics.table_relationship import (
    METHOD,
    Direction,
    TableComparisonRefused,
    compare_table_directions,
)
from kkb_agent.core import AnalyticalResult, ResultKind, ResultStatus
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


class TableRelationshipArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["table_co_movement"]
    input_step: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description="Earlier table-producing step; also list it in depends_on. Use this OR source.",
    )
    source: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description="Published table name from a previous turn. Use this OR input_step.",
    )
    driver_column: str = Field(min_length=1, max_length=400, description="Exact column label")
    target_column: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "Exact column label. When the table carries a "
            "'<column> real, <month> prices (<index>)' counterpart, that inflation-adjusted "
            "column is the one a question about real change needs; the nominal column "
            "answers only a nominal question"
        ),
    )
    driver_direction: Direction
    target_direction: Direction
    when_column: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
        description="Optional column defining a direction condition, e.g. the monthly rate column",
    )
    when_direction: Direction | None = None

    @model_validator(mode="after")
    def references_and_condition(self) -> Self:
        if (self.input_step is None) == (self.source is None):
            raise ValueError("Choose exactly one input_step or published source")
        if (self.when_column is None) != (self.when_direction is None):
            raise ValueError("when_column and when_direction must be supplied together")
        if self.driver_column == self.target_column:
            raise ValueError("Choose different driver and target columns")
        return self


def run_table_relationship(
    arguments: TableRelationshipArguments,
    context: ExecutionContext,
    connection: DuckDBPyConnection,
    *,
    workspace: Workspace | None,
    lineage: Lineage | None,
) -> ToolResult:
    source: object = None
    if arguments.input_step is not None:
        source = context.outputs.get(arguments.input_step)
    elif workspace is not None and arguments.source is not None:
        try:
            source = workspace.value_of(arguments.source)
        except WorkspaceError:
            pass
    if (
        not isinstance(source, AnalyticalResult)
        or source.status is not ResultStatus.COMPUTED
        or result_faults({"input": source}, connection)
    ):
        return ToolResult(
            ToolStatus.FAILURE,
            step_id="",
            tool="change_detection",
            error_category="table_reference",
            warnings=("The referenced table is unavailable or cannot be verified",),
        )
    try:
        result = compare_table_directions(
            source,
            driver_column=arguments.driver_column,
            target_column=arguments.target_column,
            driver_direction=arguments.driver_direction,
            target_direction=arguments.target_direction,
            when_column=arguments.when_column,
            when_direction=arguments.when_direction,
        )
    except TableComparisonRefused as error:
        result = AnalyticalResult(
            result_id="table_co_movement:refused",
            kind=ResultKind.COMPARISON,
            status=ResultStatus.ABSTAINED,
            tool="change_detection",
            method=METHOD,
            reason=str(error),
        )
    node = None
    if result.status is ResultStatus.COMPUTED:
        if arguments.source is not None:
            result = result.model_copy(
                update={"parameters": {**result.parameters, "source": arguments.source}}
            )
        if lineage is not None:
            node = lineage.record(
                NodeKind.TRANSFORM,
                "table_co_movement",
                attributes=arguments.model_dump(mode="json"),
            )
            if result.evidence is not None:
                result = result.model_copy(
                    update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
                )
        result = _record_execution(
            connection,
            producer="change_detection",
            arguments=arguments.model_dump_json(),
            inputs=[
                canonical(
                    {
                        "workspace": arguments.source,
                        "input_step": arguments.input_step,
                        "result": source.model_dump(mode="json"),
                    }
                )
            ],
            result=result,
        )
    warnings = tuple(result.warnings)
    if result.reason:
        warnings = (*warnings, result.reason)
    return ToolResult(
        ToolStatus.SUCCESS,
        step_id="",
        tool="change_detection",
        output=result,
        evidence=node,
        warnings=warnings,
    )
