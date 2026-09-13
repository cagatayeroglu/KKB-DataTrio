"""The `change_detection` tool: how a series moved between two periods (M6-22).

The brief asks this tool to detect changes in trend, level or behaviour, and
significant breakpoints. Those are two different jobs with two different
methods, so the tool names the one it is doing in an `operation` argument
rather than blurring them: `compare` answers "how did the level move between
these two dates", and breakpoint detection is **absent from the schema
entirely** until M6-05/06 implements it. A planner cannot ask for something
that does not work if the schema never offers it.

No seventh tool is added. `ToolRegistry` refuses any name outside the six the
brief fixes, and a period comparison is a level change, which is squarely
inside what this name covers.

The tool reads the series' **declared** semantics from `silver_series` before
it computes anything, because whether a difference means new lending or a
change in an outstanding balance is not visible in the numbers. Everything
that decision implies — the stock warning, the cumulative refusal, points
rather than percent for a rate — comes from
[analytics.change](../analytics/change.py) and is not re-decided here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.analytics import compare_periods
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, ResultStatus, Scale, StockFlow
from kkb_agent.core import WeeklyAnchor as Anchor
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

#: Tables this tool reads, and the input references its results carry.
INPUTS = ("silver_series", "silver_observations")


class SeriesUnknown(ValueError):
    """The named series is not registered. Safe to show the model."""


class ChangeDetectionArguments(BaseModel):
    """What the planner may ask for.

    `operation` exists with one member on purpose. It tells the planner what
    this tool currently does, and it is where breakpoint detection joins once
    M6-05/06 gives it a method — rather than being implied by the tool's name
    and then failing.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["compare"] = Field(
        description="compare: the level change between two published periods"
    )
    series_id: str = Field(min_length=1, max_length=200)
    start: date = Field(
        description="Period end date of the first observation, exactly as published"
    )
    end: date = Field(description="Period end date of the second observation, exactly as published")


@dataclass(frozen=True, slots=True)
class _Series:
    semantics: SeriesSemantics
    observations: tuple[Observation, ...]
    snapshot: str


def read_series(connection: DuckDBPyConnection, series_id: str) -> _Series:
    """The declared semantics and every published observation, in period order.

    Semantics are read rather than inferred. A series whose stored declaration
    cannot be reconstructed is an error here, not a set of defaults: guessing a
    scale is how a million-TRY figure gets compared against a thousand-TRY one.
    """
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
            }
        ),
    )


def make_change_detection_tool(
    connection: DuckDBPyConnection, *, lineage: Lineage | None = None
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data.

    When a `lineage` is supplied, each computed comparison is recorded as a
    transform node and the result's evidence points at it, so the verifier can
    resolve the reference rather than take it on trust. A comparison that
    established nothing records no node: provenance for a non-result would be
    a link to nothing.
    """

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, ChangeDetectionArguments):  # pragma: no cover
            raise TypeError("change_detection received arguments it did not declare")
        try:
            series = read_series(connection, arguments.series_id)
        except SeriesUnknown as error:
            return ToolResult(
                ToolStatus.FAILURE,
                step_id="",
                tool="change_detection",
                error_category="series_unknown",
                warnings=(str(error),),
            )

        result = compare_periods(
            series.observations,
            series.semantics,
            start=arguments.start,
            end=arguments.end,
            series_id=arguments.series_id,
            input_refs=INPUTS,
        )
        node = _record(lineage, arguments, result.status)
        if node is not None and result.evidence is not None:
            result = result.model_copy(
                update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
            )

        result = _record_execution(
            connection,
            producer="change_detection",
            arguments=arguments.model_dump_json(),
            inputs=[series.snapshot],
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

    return ToolSpec(
        name="change_detection",
        description=(
            "Compare a registered series between two published period-end dates. "
            "Returns both levels, the absolute change in the series' own unit — or in "
            "points for a rate or index — and the relative change when its base admits "
            "one. Dates must match published periods exactly. Breakpoint and trend-break "
            "detection are not available yet."
        ),
        arguments=ChangeDetectionArguments,
        run=run,
    )


def _record(
    lineage: Lineage | None, arguments: ChangeDetectionArguments, status: ResultStatus
) -> str | None:
    if lineage is None or status is not ResultStatus.COMPUTED:
        return None
    return lineage.record(
        NodeKind.TRANSFORM,
        "change_detection_compare",
        attributes={
            "series": arguments.series_id,
            "from": arguments.start.isoformat(),
            "to": arguments.end.isoformat(),
            "operation": arguments.operation,
            "provenance": "series-level; the compared endpoints are named in the result",
        },
    )
