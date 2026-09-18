"""The `change_detection` tool: how a series moved between two periods (M6-22).

The brief asks this tool to detect changes in trend, level or behaviour, and
significant breakpoints. Those are two different jobs with two different
methods, so the tool names the one it is doing in an `operation` argument
rather than blurring them: `compare` answers "how did the level move between
these two dates", and breakpoint detection is **absent from the schema
entirely** until M6-05/06 implements it. A planner cannot ask for something
that does not work if the schema never offers it.

`co_movement` compares prepared series, and `table_co_movement` compares
columns of a verified prior table. Both are descriptive direction counts.
They remain operations of this registered tool under DEC-135's eight-tool target.

The tool reads the series' **declared** semantics from `silver_series` before
it computes anything, because whether a difference means new lending or a
change in an outstanding balance is not visible in the numbers. Everything
that decision implies — the stock warning, the cumulative refusal, points
rather than percent for a rate — comes from
[analytics.change](../analytics/change.py) and is not re-decided here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import TableInput, ToolSpec
from kkb_agent.agent.workspace import Workspace
from kkb_agent.analytics import compare_periods
from kkb_agent.analytics.breakpoint import detect_breakpoints
from kkb_agent.analytics.comovement import co_movement
from kkb_agent.catalog.inspection import InspectionRefused, PreparedSeriesInspector
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    ResultKind,
    ResultStatus,
    Scale,
    SeriesId,
    StockFlow,
    TransformationRecord,
)
from kkb_agent.core import WeeklyAnchor as Anchor
from kkb_agent.lakehouse.alignment import AlignmentError, WeekAssignment, to_monthly
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics
from kkb_agent.tools.table_relationship import TableRelationshipArguments, run_table_relationship

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: Tables this tool reads, and the input references its results carry.
INPUTS = ("silver_series", "silver_observations")


class SeriesUnknown(ValueError):
    """The named series is not registered. Safe to show the model."""


class SeriesChangeArguments(BaseModel):
    """What the planner may ask for.

    `operation` names what the tool does rather than letting its name imply
    more. `co_movement` (M6-25) compares month-over-month directions of two
    series; reducing a weekly series onto months is a policy the planner states.
    `breakpoint` (M6-05/06) searches for regime changes; its threshold and
    minimum segment are harness constants, never planner arguments.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["compare", "co_movement", "breakpoint"] = Field(
        description=(
            "compare: the level change of series_id between two published periods. "
            "co_movement: monthly levels and month-over-month changes of series_id (target) "
            "and driver_series_id over the window, and the months in which the driver fell "
            "while the target did not rise. "
            "breakpoint: the months after which series_id kept moving differently, over the "
            "window"
        )
    )
    series_id: SeriesId = Field(
        min_length=1, max_length=200, description="compare series or target"
    )
    start: date = Field(
        description=(
            "compare: period end of the first observation, exactly as published. "
            "co_movement: first day of the window"
        )
    )
    end: date = Field(
        description=(
            "compare: period end of the second observation, exactly as published. "
            "co_movement: last day of the window"
        )
    )
    driver_series_id: SeriesId | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="co_movement only: the series whose falls are examined, such as a rate",
    )
    week_assignment: Literal["by_end", "by_majority"] | None = Field(
        default=None,
        description=(
            "co_movement only, required when either series is weekly: by_end assigns a week "
            "to the month its period ends in; by_majority to the month holding most of its days"
        ),
    )

    @model_validator(mode="after")
    def operation_fields(self) -> Self:
        if self.operation in ("compare", "breakpoint") and (
            self.driver_series_id is not None or self.week_assignment is not None
        ):
            raise ValueError(f"{self.operation} takes no driver_series_id or week_assignment")
        if self.operation == "co_movement" and self.driver_series_id is None:
            raise ValueError("co_movement needs driver_series_id")
        if self.operation == "breakpoint" and self.start > self.end:
            raise ValueError("breakpoint needs a window whose start is on or before its end")
        return self


class ChangeDetectionArguments(
    RootModel[
        Annotated[
            SeriesChangeArguments | TableRelationshipArguments, Field(discriminator="operation")
        ]
    ]
):
    """Closed flat argument variants for stored-series and table-input operations."""


def _table_input(arguments: BaseModel) -> TableInput | None:
    if isinstance(arguments, ChangeDetectionArguments):
        selected = arguments.root
        if isinstance(selected, TableRelationshipArguments):
            return TableInput(source=selected.source, input_step=selected.input_step)
    return None


def _required_steps(arguments: BaseModel) -> tuple[str, ...]:
    if isinstance(arguments, ChangeDetectionArguments):
        selected = arguments.root
        if isinstance(selected, TableRelationshipArguments) and selected.input_step is not None:
            return (selected.input_step,)
    return ()


@dataclass(frozen=True, slots=True)
class _Series:
    semantics: SeriesSemantics
    observations: tuple[Observation, ...]
    snapshot: str


def read_series(
    connection: DuckDBPyConnection,
    series_id: str,
    *,
    inspector: PreparedSeriesInspector | None = None,
) -> _Series:
    """The declared semantics and every published observation, in period order.

    Semantics are read rather than inferred. A series whose stored declaration
    cannot be reconstructed is an error here, not a set of defaults: guessing a
    scale is how a million-TRY figure gets compared against a thousand-TRY one.
    """
    receipt = None
    if inspector is not None:
        try:
            receipt = inspector.inspect(connection, series_id).evidence()
        except InspectionRefused as error:
            raise SeriesUnknown(str(error)) from error
    row = connection.execute(
        "SELECT unit, scale, frequency, anchor, observation, cumulative, aggregation, "
        "base_year, artifact_id"
        " FROM silver_series WHERE series_id = ?",
        [series_id],
    ).fetchone()
    if row is None:
        raise SeriesUnknown(f"No series {series_id!r} is registered")
    unit, scale, frequency, anchor, observation, cumulative, aggregation, base_year, artifact = row
    try:
        semantics = SeriesSemantics(
            unit=str(unit),
            scale=Scale(scale),
            frequency=Frequency(frequency),
            anchor=Anchor(anchor) if anchor else None,
            observation=StockFlow(observation),
            cumulative=CumulativeKind(cumulative),
            aggregation=Aggregation(aggregation),
            base_year=base_year,
        )
    except (ValueError, SemanticsError) as error:
        raise SeriesUnknown(
            f"Series {series_id!r} has an unreadable declaration: {error}"
        ) from error

    rows = connection.execute(
        "SELECT period_start, period_end, value FROM silver_observations"
        " WHERE series_id = ? ORDER BY period_end",
        [series_id],
    ).fetchall()
    return _Series(
        semantics,
        tuple(Observation(item[0], item[1], item[2]) for item in rows),
        canonical(
            {
                "series_id": series_id,
                "artifact_id": artifact,
                "semantic_columns": [
                    "unit",
                    "scale",
                    "frequency",
                    "anchor",
                    "observation",
                    "cumulative",
                    "aggregation",
                    "base_year",
                ],
                "semantics": row[:-1],
                "observation_columns": ["period_start", "period_end", "value"],
                "observations": rows,
                **({"catalog_inspection": receipt} if receipt is not None else {}),
            }
        ),
    )


def make_change_detection_tool(
    connection: DuckDBPyConnection,
    *,
    lineage: Lineage | None = None,
    series_names: Mapping[str, str] | None = None,
    workspace: Workspace | None = None,
    inspector: PreparedSeriesInspector | None = None,
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data.

    When a `lineage` is supplied, each computed result is recorded as a
    transform node and the result's evidence points at it, so the verifier can
    resolve the reference rather than take it on trust. A result that
    established nothing records no node: provenance for a non-result would be
    a link to nothing.

    `series_names` are reviewed display names (see ingest.prepared_series) shown
    to the planner so it can name a prepared series it cannot otherwise guess.
    """
    names = dict(series_names or {})

    def failure(error: SeriesUnknown) -> ToolResult:
        return ToolResult(
            ToolStatus.FAILURE,
            step_id="",
            tool="change_detection",
            error_category="series_unknown",
            warnings=(str(error),),
        )

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, ChangeDetectionArguments):  # pragma: no cover
            raise TypeError("change_detection received arguments it did not declare")
        selected = arguments.root
        if isinstance(selected, TableRelationshipArguments):
            return run_table_relationship(
                selected, context, connection, workspace=workspace, lineage=lineage
            )
        arguments = selected
        try:
            series = read_series(connection, arguments.series_id, inspector=inspector)
            driver = (
                read_series(connection, arguments.driver_series_id, inspector=inspector)
                if arguments.driver_series_id is not None
                else None
            )
        except SeriesUnknown as error:
            return failure(error)

        if arguments.operation == "breakpoint":
            result = detect_breakpoints(
                series.observations,
                series.semantics,
                series_id=arguments.series_id,
                start=arguments.start,
                end=arguments.end,
                input_refs=INPUTS,
            )
            inputs = [series.snapshot]
        elif driver is None:
            result = compare_periods(
                series.observations,
                series.semantics,
                start=arguments.start,
                end=arguments.end,
                series_id=arguments.series_id,
                input_refs=INPUTS,
            )
            inputs = [series.snapshot]
        else:
            result = _co_movement(arguments, series, driver, names)
            inputs = [series.snapshot, driver.snapshot]
        node = _record(lineage, arguments, result.status)
        if node is not None and result.evidence is not None:
            result = result.model_copy(
                update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
            )

        result = _record_execution(
            connection,
            producer="change_detection",
            arguments=arguments.model_dump_json(),
            inputs=inputs,
            result=result,
        )

        warnings = tuple(result.warnings)
        if result.status is not ResultStatus.COMPUTED and result.reason is not None:
            # The tool ran and refused to produce a number. That is a success
            # whose answer is "no", and the model has to be told which.
            warnings = (*warnings, result.reason)
        return ToolResult(
            ToolStatus.SUCCESS,
            step_id="",
            tool="change_detection",
            output=result,
            warnings=warnings,
            evidence=node,
        )

    description = (
        "compare: a registered series between two published period-end dates, returning "
        "both levels, the absolute change in the series' own unit — or in points for a rate "
        "or index — and the relative change when its base admits one. co_movement: over a "
        "window, monthly levels and month-over-month changes of a target and a driver series "
        "(a weekly series is reduced onto months with its declared aggregation and the stated "
        "week_assignment), plus the months in which the driver fell while the target did not "
        "rise; values are nominal and co-movement is not causation. breakpoint: over a window, "
        "the months after which the average period-over-period change shifts, with how many "
        "were found, the shift at each one and the observations behind it; it names no event "
        "and establishes no cause, and its threshold is fixed by the harness. "
        "table_co_movement compares monthly directions of "
        "two stock/rate/index columns already in a table, optionally only in months when a "
        "third column moves in the selected direction. It keeps all table values and adds "
        "explicit counts, without identifying a causal effect. Use exact column labels and "
        "explicit driver_direction/target_direction. For a table made by an earlier step "
        "(such as table_transform add_series), use input_step and declare that step in "
        "depends_on. Otherwise use a published source name. No new series is fetched."
    )
    if names:
        description += " Prepared series (series_id: meaning): " + "; ".join(
            f"{sid}: {name}" for sid, name in names.items()
        )
    return ToolSpec(
        name="change_detection",
        description=description,
        arguments=ChangeDetectionArguments,
        run=run,
        required_steps=_required_steps,
        table_input=_table_input,
    )


def _monthly(
    series: _Series, series_id: str, arguments: SeriesChangeArguments
) -> tuple[tuple[Observation, ...], SeriesSemantics, str, list[TransformationRecord]] | str:
    """The series on months, with its reduction recorded, or why that is refused."""
    semantics = series.semantics
    if semantics.frequency is not Frequency.WEEKLY:
        return series.observations, semantics, series_id, []
    if arguments.week_assignment is None:
        return f"{series_id} is weekly; state week_assignment to reduce it onto months"
    try:
        alignment = to_monthly(
            series.observations,
            requested_start=arguments.start,
            requested_end=arguments.end,
            frequency=semantics.frequency,
            aggregation=semantics.aggregation,
            anchor=semantics.anchor,
            assignment=WeekAssignment(arguments.week_assignment),
        )
    except AlignmentError as error:
        return f"{series_id} cannot be reduced onto months: {error}"
    incomplete = set(alignment.incomplete_periods())
    label = f"{series_id} monthly {semantics.aggregation.value} ({arguments.week_assignment})"
    record = TransformationRecord(
        operation="align_weekly_to_monthly",
        parameters={**alignment.method, "incomplete_months_excluded": len(incomplete)},
        input_refs=[series_id],
        output_ref=label,
    )
    kept = tuple(item for item in alignment.observations if item.period_end not in incomplete)
    monthly = replace(semantics, frequency=Frequency.MONTHLY, anchor=None)
    return kept, monthly, label, [record]


def _co_movement(
    arguments: SeriesChangeArguments,
    target: _Series,
    driver: _Series,
    names: Mapping[str, str],
) -> AnalyticalResult:
    driver_id = arguments.driver_series_id or ""
    prepared = []
    for series, series_id in ((target, arguments.series_id), (driver, driver_id)):
        monthly = _monthly(series, series_id, arguments)
        if isinstance(monthly, str):
            return AnalyticalResult(
                result_id=f"co_movement:{driver_id}:{arguments.series_id}",
                kind=ResultKind.COMPARISON,
                status=ResultStatus.ABSTAINED,
                tool="analytics",
                method="monthly-direction-v1",
                reason=monthly,
            )
        prepared.append(monthly)
    (target_obs, target_sem, target_label, target_steps) = prepared[0]
    (driver_obs, driver_sem, driver_label, driver_steps) = prepared[1]
    return co_movement(
        driver_obs,
        driver_sem,
        target_obs,
        target_sem,
        start=arguments.start,
        end=arguments.end,
        driver_label=driver_label,
        target_label=target_label,
        input_refs=INPUTS,
        transformations=[*target_steps, *driver_steps],
        parameters={
            "week_assignment": arguments.week_assignment,
            "series_names": {
                sid: names[sid] for sid in (arguments.series_id, driver_id) if sid in names
            },
        },
    )


def _record(
    lineage: Lineage | None, arguments: SeriesChangeArguments, status: ResultStatus
) -> str | None:
    if lineage is None or status is not ResultStatus.COMPUTED:
        return None
    attributes = {
        "series": arguments.series_id,
        "from": arguments.start.isoformat(),
        "to": arguments.end.isoformat(),
        "operation": arguments.operation,
        "provenance": "series-level; the compared endpoints are named in the result",
    }
    if arguments.operation == "co_movement":
        attributes["driver"] = arguments.driver_series_id or ""
        attributes["week_assignment"] = arguments.week_assignment or ""
    return lineage.record(
        NodeKind.TRANSFORM, f"change_detection_{arguments.operation}", attributes=attributes
    )
