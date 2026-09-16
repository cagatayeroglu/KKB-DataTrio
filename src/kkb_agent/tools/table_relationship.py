"""The table-input operation of change_detection, with verified reference boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics.table_relationship import (
    METHOD,
    Direction,
    TableComparisonRefused,
    compare_table_directions,
    real_counterpart,
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


class _Columns(NamedTuple):
    driver: str
    target: str
    when: str | None
    moved: dict[str, str]


def _deflated_columns(source: AnalyticalResult, arguments: TableRelationshipArguments) -> _Columns:
    """Move each selected column to its deflated counterpart when one exists.

    A real column is only in the table because an earlier turn was asked to
    remove inflation, so a later question about change means that column. This
    is not a preference the plan can decline: a planner-facing opt-out was tried
    and the planner set it on a question that never asked for nominal terms, so
    the substitution is unconditional here. A nominal reading stays reachable by
    comparing a table that carries no real counterpart, such as the one from
    before the deflation turn.

    A substitution that would collide with another selected column is skipped,
    so a plan comparing a column against its own real counterpart still works.
    """
    driver, target = arguments.driver_column, arguments.target_column
    when: str | None = arguments.when_column
    moved: dict[str, str] = {}
    counterpart = real_counterpart(source, driver)
    if counterpart is not None and counterpart not in {target, when}:
        moved["driver_column"], driver = driver, counterpart
    counterpart = real_counterpart(source, target)
    if counterpart is not None and counterpart not in {driver, when}:
        moved["target_column"], target = target, counterpart
    if when is not None:
        counterpart = real_counterpart(source, when)
        if counterpart is not None and counterpart not in {driver, target}:
            moved["when_column"], when = when, counterpart
    return _Columns(driver, target, when, moved)


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
    columns = _deflated_columns(source, arguments)
    deflated = columns.moved
    try:
        result = compare_table_directions(
            source,
            driver_column=columns.driver,
            target_column=columns.target,
            driver_direction=arguments.driver_direction,
            target_direction=arguments.target_direction,
            when_column=columns.when,
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
        extra: dict[str, object] = {}
        if arguments.source is not None:
            extra["source"] = arguments.source
        if deflated:
            # The answer must be able to say the comparison moved to real terms.
            extra["compared_in_real_terms_instead_of"] = deflated
        if extra:
            result = result.model_copy(update={"parameters": {**result.parameters, **extra}})
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
