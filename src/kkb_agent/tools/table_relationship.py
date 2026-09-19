"""The table-input operation of change_detection, with verified reference boundaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
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
        description=(
            "Published table name from a previous turn, or the step_id of an earlier "
            "table-producing step of this plan (then list it in depends_on). Use this OR "
            "input_step."
        ),
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


def _continued_condition(
    source: AnalyticalResult, arguments: TableRelationshipArguments, question: str
) -> tuple[str, Direction] | None:
    """Carry one verified earlier predicate only for an explanatory continuation.

    A new two-column comparison is otherwise independent. In particular, merely
    selecting a table must not silently condition every subsequent calculation.
    """
    if arguments.when_column is not None:
        return None
    wording = question.casefold()
    if not any(cue in wording for cue in ("açıkl", "neden", "explain", "account for")):
        return None
    if any(
        cue in wording
        for cue in ("bağımsız", "sadece", "yalnızca", "hariç", "independent", "regardless", "only")
    ):
        return None
    previous = source.parameters.get("direction_comparison")
    if not isinstance(previous, Mapping):
        return None
    driver = previous.get("driver_column")
    target = previous.get("target_column")
    if not isinstance(driver, str) or not isinstance(target, str):
        return None
    if (
        previous.get("driver_direction") != "down"
        or previous.get("target_direction") != "non_increasing"
    ):
        return None
    names = source.parameters.get("series_names")
    reviewed = names if isinstance(names, Mapping) else {}

    def words(label: str) -> set[str]:
        display = reviewed.get(label)
        if not isinstance(display, str):
            display = next(
                (
                    name
                    for series_id, name in reviewed.items()
                    if isinstance(series_id, str)
                    and isinstance(name, str)
                    and label.startswith(f"{series_id} ")
                ),
                None,
            )
        text = f"{label} {display}" if isinstance(display, str) else label
        return {token[:4] for token in re.findall(r"[^\W\d_]{4,}", text.casefold())}

    counterpart = real_counterpart(source, target)
    if arguments.target_column in (
        target,
        counterpart,
    ) and arguments.target_direction == previous.get("target_direction"):
        other_column = arguments.driver_column
    elif arguments.driver_column in (
        target,
        counterpart,
    ) and arguments.driver_direction == previous.get("target_direction"):
        other_column = arguments.target_column
    else:
        return None
    # The question must refer to the previously analysed target, not just ask
    # why some other newly added series moved. Exclude words shared with the
    # other selected column so a broad topic word cannot manufacture that reference.
    target_words = words(target) - words(other_column)
    question_tokens = re.findall(r"[^\W\d_]{4,}", wording)
    question_words = {token[:4] for token in question_tokens}
    non_rise_mentioned = any(
        token.startswith(cue)
        for token in question_tokens
        for cue in (
            "artmad",
            "artmam",
            "artmıy",
            "artmay",
            "yükselmed",
            "yükselmem",
            "yükselmiy",
            "yükselmey",
        )
    ) or any(
        phrase in wording
        for phrase in (
            "not rise",
            "not rising",
            "not increase",
            "not increasing",
            "didn't rise",
            "didn't increase",
            "non-increasing",
        )
    )
    driver_words = words(driver) - words(target) - words(other_column)
    opposite_driver_mentioned = any(
        question_tokens[index][:4] in driver_words
        and any(
            token.startswith(("arttı", "artıy", "yüksel", "rose", "rising", "increas"))
            for token in question_tokens[index + 1 : index + 3]
        )
        for index in range(len(question_tokens))
    )
    if (
        driver in (arguments.driver_column, arguments.target_column)
        or real_counterpart(source, driver) in (arguments.driver_column, arguments.target_column)
        or not any(value.label == driver for value in source.values)
        or not target_words.intersection(question_words)
        or not non_rise_mentioned
        or opposite_driver_mentioned
    ):
        return None
    return driver, "down"


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
    elif arguments.source is not None:
        # A published table first; else an earlier step of this plan named the same
        # way table_transform accepts it (DEC-166: live E1c, 2026-09-19, chained two
        # co-movement counts and named the first step as `source`).
        if workspace is not None:
            try:
                source = workspace.value_of(arguments.source)
            except WorkspaceError:
                source = None
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
            step_id="",
            tool="change_detection",
            error_category="table_reference",
            warnings=("The referenced table is unavailable or cannot be verified",),
        )
    inherited = _continued_condition(source, arguments, context.question)
    effective = (
        arguments.model_copy(update={"when_column": inherited[0], "when_direction": inherited[1]})
        if inherited is not None
        else arguments
    )
    columns = _deflated_columns(source, effective)
    deflated = columns.moved
    try:
        result = compare_table_directions(
            source,
            driver_column=columns.driver,
            target_column=columns.target,
            driver_direction=effective.driver_direction,
            target_direction=effective.target_direction,
            when_column=columns.when,
            when_direction=effective.when_direction,
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
        if inherited is not None:
            extra["continued_prior_condition"] = {
                "source_result_id": source.result_id,
                "column": columns.when,
                "direction": inherited[1],
            }
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
