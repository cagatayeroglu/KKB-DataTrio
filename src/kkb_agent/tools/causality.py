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

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import TableInput, ToolSpec
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics import (
    DEFAULT_MAX_LAG,
    LAG_CAP,
    associate,
    granger_precedence,
    lagged_association,
)
from kkb_agent.analytics.table_relationship import resolve_label
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    ResultStatus,
    SeriesId,
)
from kkb_agent.ingest.prepared_series import prepared_series_coverage
from kkb_agent.lakehouse import Observation, SeriesSemantics
from kkb_agent.lakehouse.column_contract import decode
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.lakehouse.semantics import SemanticsError
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
    left_series_id: SeriesId | None = Field(default=None, min_length=1, max_length=200)
    right_series_id: SeriesId | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=(
            "Instead of two series IDs: a published table's name, or the step_id of an "
            "earlier step of this plan that returns a table (then list it in depends_on). "
            "Name the two columns with left_column and right_column. Use this when the "
            "series are published at different frequencies: read each, bring the faster "
            "one onto the slower one's periods with table_transform resample, join them, "
            "and measure the columns of that table"
        ),
    )
    left_column: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
        description="With source: the exact label of the first column, ordered as left",
    )
    right_column: str | None = Field(
        default=None,
        min_length=1,
        max_length=400,
        description="With source: the exact label of the second column",
    )
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

    @model_validator(mode="after")
    def _one_pair_of_inputs(self) -> CausalityArguments:
        identities = (self.left_series_id, self.right_series_id)
        columns = (self.source, self.left_column, self.right_column)
        if all(identities) and not any(columns):
            return self
        if all(columns) and not any(identities):
            if self.left_column == self.right_column:
                raise ValueError("name two different columns")
            return self
        raise ValueError(
            "give either left_series_id and right_series_id, or source with "
            "left_column and right_column"
        )


#: What a column of a published table looks like to this tool: the observations it holds
#: and the semantics its cells declare.
class _ReadColumn(NamedTuple):
    semantics: SeriesSemantics
    observations: tuple[Observation, ...]
    snapshot: str


def _column_of(source: AnalyticalResult, label: str) -> _ReadColumn | str:
    """One column of a table as a series, or why it cannot be read as one.

    The prepared interest rates are weekly and the BDDK balances monthly, so an
    association between them can only be measured on a table that already brought them
    onto one calendar (`table_transform resample` then `join_table`). Until this existed
    the planner was told to "align them explicitly" and had no way to do it: the tool took
    registered series only, and no registered series is the resampled column (live
    2026-09-22, and Eray's audit before it).
    """
    label = resolve_label(source, label)
    selected = [value for value in source.values if value.label == label]
    if not selected:
        present = list(dict.fromkeys(value.label for value in source.values))
        return f"No column {label[:160]!r} in that table; its columns are: " + "; ".join(
            repr(name[:160]) for name in present[:16]
        )
    first = selected[0]
    if first.semantics_are_unresolved or first.unit == DIMENSIONLESS:
        return f"Column {label[:160]!r} has no unit and scale to measure with"
    if len({(value.unit, value.scale, value.measure) for value in selected}) != 1:
        return f"Column {label[:160]!r} changes unit, scale or measurement kind"
    observations: list[Observation] = []
    for value in selected:
        period = value.period
        if period is None:
            return f"Column {label[:160]!r} has a value outside any period"
        observations.append(Observation(period.start, period.end, value.value))
    frequencies = {value.period.frequency for value in selected if value.period is not None}
    if len(frequencies) != 1:
        return f"Column {label[:160]!r} mixes frequencies"
    try:
        semantics = decode(source, label)
    except SemanticsError as error:
        return f"Column {label[:160]!r}: {error}"
    if (semantics.unit, semantics.scale, semantics.observation, semantics.frequency) != (
        first.unit,
        first.scale,
        first.measure,
        next(iter(frequencies)),
    ):
        return f"Column {label[:160]!r} disagrees with its semantic carrier"
    if any(
        value.period is not None and value.period.weekly_anchor != semantics.anchor
        for value in selected
    ):
        return f"Column {label[:160]!r} disagrees with its calendar anchor"
    return _ReadColumn(
        semantics,
        tuple(sorted(observations, key=lambda item: item.period_end)),
        canonical(
            {
                "kind": "table_column",
                "column": label,
                "result_version": source.digest(),
                "result": source.model_dump(mode="json"),
            }
        ),
    )


def _table_columns(
    arguments: CausalityArguments,
    context: ExecutionContext,
    workspace: Workspace | None,
    connection: DuckDBPyConnection,
) -> tuple[_ReadColumn, _ReadColumn, str, str] | ToolResult:
    """Both columns of the table this step names, or the refusal that says why not."""

    def refused(category: str, reason: str) -> ToolResult:
        return ToolResult(
            ToolStatus.FAILURE,
            step_id="",
            tool="causality",
            error_category=category,
            warnings=(reason,),
        )

    named = arguments.source or ""
    source: object = None
    if workspace is not None:
        try:
            source = workspace.value_of(named)
        except WorkspaceError:
            source = None
    if source is None:
        produced = context.outputs.get(named)
        source = getattr(produced, "result", produced)
    if (
        not isinstance(source, AnalyticalResult)
        or source.status is not ResultStatus.COMPUTED
        or result_faults({"input": source}, connection)
    ):
        return refused(
            "table_reference", "The referenced table is unavailable or cannot be verified"
        )
    read = [
        _column_of(source, arguments.left_column or ""),
        _column_of(source, arguments.right_column or ""),
    ]
    for item in read:
        if isinstance(item, str):
            return refused("needs_input", item)
    left, right = read
    if not isinstance(left, _ReadColumn) or not isinstance(right, _ReadColumn):  # pragma: no cover
        return refused("needs_input", "A column could not be read")
    return left, right, arguments.left_column or "", arguments.right_column or ""


def make_causality_tool(
    connection: DuckDBPyConnection,
    *,
    lineage: Lineage | None = None,
    series_names: Mapping[str, str] | None = None,
    inspector: PreparedSeriesInspector | None = None,
    workspace: Workspace | None = None,
) -> ToolSpec:
    """Bind the tool to one database. The registry holds the closure, not the data."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        # The registry parses arguments before dispatch, so this is a contract
        # check rather than validation. Not an assert: asserts vanish under -O.
        if not isinstance(arguments, CausalityArguments):  # pragma: no cover
            raise TypeError("causality received arguments it did not declare")
        left: _ReadColumn
        right: _ReadColumn
        if arguments.source is not None:
            read = _table_columns(arguments, context, workspace, connection)
            if isinstance(read, ToolResult):
                return read
            left, right, left_id, right_id = read
        else:
            try:
                found = read_series(connection, arguments.left_series_id or "", inspector=inspector)
                other = read_series(
                    connection, arguments.right_series_id or "", inspector=inspector
                )
                left = _ReadColumn(found.semantics, found.observations, found.snapshot)
                right = _ReadColumn(other.semantics, other.observations, other.snapshot)
            except SeriesUnknown as error:
                return ToolResult(
                    ToolStatus.FAILURE,
                    step_id="",
                    tool="causality",
                    error_category="series_unknown",
                    warnings=(str(error),),
                )
            left_id = arguments.left_series_id or ""
            right_id = arguments.right_series_id or ""

        shared = {
            "left_id": left_id,
            "right_id": right_id,
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

    description = (
        "Measure whether two registered series moved together, optionally at a lag, "
        "or whether one series' past improved predictions of the other's (Granger). "
        "This reports ASSOCIATION ONLY — Granger gives predictive precedence at most — "
        "and cannot establish that one series moves the other; every result carries "
        "that limitation and a third factor moving both would produce the same number. "
        "Series must share a frequency and are compared only on periods both "
        "published. Needs about two years of aligned observations."
    )
    # The same list change_detection carries. Without it the planner configured this tool
    # from memory: asked for the housing-loan rate it wrote EVDS:TP.BKR.TRY.18, the rate on
    # the outstanding portfolio, which no list here had offered; the read refused it and
    # nine minutes went on trying to recover (live 2026-09-21).
    if series_names:
        coverage = prepared_series_coverage(connection)
        description += " Prepared series (series_id: meaning [stored window]): " + "; ".join(
            f"{sid}: {name}" + (f" [{coverage[sid]}]" if sid in coverage else "")
            for sid, name in series_names.items()
        )
    return ToolSpec(
        name="causality",
        description=description,
        arguments=CausalityArguments,
        run=run,
        table_input=_causality_table,
    )


def _causality_table(arguments: BaseModel) -> TableInput | None:
    if isinstance(arguments, CausalityArguments) and arguments.source is not None:
        return TableInput(source=arguments.source)
    return None


def _record(
    lineage: Lineage | None, arguments: CausalityArguments, result: AnalyticalResult
) -> str | None:
    if lineage is None or result.status is not ResultStatus.COMPUTED:
        return None
    return lineage.record(
        NodeKind.TRANSFORM,
        f"causality_{arguments.operation}",
        attributes={
            "left": arguments.left_series_id or arguments.left_column or "",
            "right": arguments.right_series_id or arguments.right_column or "",
            "max_lag": str(arguments.max_lag),
            "claim": (
                "predictive precedence only; not a causal finding"
                if arguments.operation == "granger"
                else "association only; not a causal finding"
            ),
            "provenance": "series-level; the compared periods are named in the result",
        },
    )
