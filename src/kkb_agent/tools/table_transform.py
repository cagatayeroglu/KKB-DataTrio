"""The `table_transform` tool: change a published table without rebuilding it (M5-20).

The organizer's second and third turns begin "without disturbing the table".
That is a statement about state: every follow-up starts from the result the user
already accepted and produces a new traceable result without mutating it. Column
operations keep every old value; row-shape operations may only select existing
period cells under an explicit policy. The tool reads a published workspace
result by name, never a table the model describes.

Only delivered operations are offered (DEC-135). `deflate` (M2-15) converts
one currency column in the prices of an explicit reference month, using a
registered monthly price index. `add_series` adds a registered monthly series
on the source table's exact periods. `rebase`, `align`, and `filter` are bounded
unary changes over cells already present in the published result; they do not
load another table, reduce a frequency, fill a gap, or accept arbitrary SQL.
`add_document_column` (M7-14) exists only when the operator enabled prompt
addresses: it reads one column of a table at an address the user wrote, through
the same boundary as `web_url`, and joins it on explicit months.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import TableInput, ToolSpec
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace, WorkspaceError
from kkb_agent.analytics.accumulation import FORMULA as TO_FLOW_FORMULA
from kkb_agent.analytics.accumulation import METHOD as TO_FLOW_METHOD
from kkb_agent.analytics.accumulation import AccumulationRefused, to_flow_column
from kkb_agent.analytics.deflation import FORMULA, METHOD, DeflationRefused, deflate
from kkb_agent.analytics.resample import METHOD as RESAMPLE_METHOD
from kkb_agent.analytics.resample import ResampleRefused, resample_column
from kkb_agent.analytics.table_series import (
    DOCUMENT_METHOD,
    JOIN_METHOD,
    SeriesAdditionRefused,
    add_document_column,
    add_monthly_series,
    join_monthly_table,
)
from kkb_agent.analytics.table_series import METHOD as ADD_SERIES_METHOD
from kkb_agent.analytics.table_shape import (
    ALIGN_METHOD,
    FILTER_METHOD,
    REBASE_FORMULA,
    REBASE_METHOD,
    ShapedTable,
    TableShapeRefused,
    align_periods,
    filter_periods,
    rebase_index,
)
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.core import (
    AnalyticalResult,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SeriesId,
    SourceRef,
    TransformationRecord,
)
from kkb_agent.ingest.attached import Attachment
from kkb_agent.ingest.fetched import source_id_for
from kkb_agent.lakehouse.alignment import WeekAssignment
from kkb_agent.lakehouse.lineage import Lineage, NodeKind
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.result_evidence import _record_execution, canonical
from kkb_agent.lakehouse.semantics import SeriesSemantics
from kkb_agent.pdf_ocr import OcrProvider
from kkb_agent.tools._document_column import (
    ColumnRefused,
    DocumentColumn,
    column_snapshot,
    measure_limitation,
    read_column,
)
from kkb_agent.tools._document_value import as_of, csv_parsing, grids, year_in_question
from kkb_agent.tools.change_detection import SeriesUnknown, read_series
from kkb_agent.tools.web_url import Fetcher, choose_document, read_attachment, read_document

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

INPUTS = ("silver_series", "silver_observations")
NOMINAL_LIMITATION = "Values are nominal; no inflation adjustment was applied"


#: Every table argument accepts a published result or a step of this plan (DEC-165).
_SOURCE = (
    "A published result from an earlier turn, or the step_id of an earlier step in this "
    "plan that produced a table (then list that step in depends_on)"
)
_SOURCE_UNCHANGED = _SOURCE + "; its rows stay unchanged"
_OTHER = (
    "Another published result, or an earlier step of this plan such as a fetched or "
    "uploaded table (then list that step in depends_on)"
)


class DeflateArguments(BaseModel):
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
        description=_SOURCE,
    )
    column: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "The column's exact label in that result. A table fetched by a lakehouse step of "
            "this plan labels each column by its series_id; a one-column table is used as is"
        ),
    )
    index_series_id: SeriesId = Field(
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


class ToFlowArguments(BaseModel):
    """Differencing a column the store declares cumulative; no other column qualifies."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["to_flow"] = Field(
        description=(
            "to_flow: add a per-period flow copy of one column the store records as a "
            "cumulative series (yearly_reset or since_inception), keeping every existing "
            "column unchanged. The store's declaration decides; a column that only looks "
            "cumulative is refused"
        )
    )
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_SOURCE_UNCHANGED,
    )
    column: str = Field(
        min_length=1,
        max_length=400,
        description="The cumulative column's exact label in that result; it is a series id",
    )


class ResampleArguments(BaseModel):
    """Reducing a weekly column onto months by the series' declared aggregation."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["resample"] = Field(
        description=(
            "resample: add a monthly copy of one weekly column, reduced by the aggregation the "
            "store declares for that series (a rate averaged, a flow summed, a stock at its "
            "last week), keeping every existing column unchanged; then join_table can put it "
            "beside monthly tables"
        )
    )
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_SOURCE_UNCHANGED,
    )
    column: str = Field(
        min_length=1,
        max_length=400,
        description="The weekly column's exact label in that result; it is a series id",
    )
    week_assignment: Literal["by_end", "by_majority"] = Field(
        description=(
            "Which month a week spanning two months belongs to: by_end, the month its last "
            "day falls in (how sources label a week), or by_majority, where most of its days fell"
        )
    )


class AddSeriesArguments(BaseModel):
    """Adding a column requires no deflation parameters or model-supplied data."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["add_series"]
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_SOURCE_UNCHANGED,
    )
    series_id: SeriesId = Field(
        min_length=1, max_length=200, description="Registered monthly series to add as a column"
    )


class AddDocumentColumnArguments(BaseModel):
    """One column of a table at a web address the user wrote; no values from the model."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["add_document_column"]
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_SOURCE_UNCHANGED,
    )
    url: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        pattern=r"^https?://\S+$",
        description="The address exactly as the user wrote it in the question",
    )
    attached: bool = Field(
        default=False,
        description="true to read a document uploaded in this conversation instead of a url",
    )
    document: str | None = Field(
        default=None,
        pattern=r"^belge_[0-9]{1,2}$",
        description="With attached=true: which uploaded document (belge_1, belge_2, ...)",
    )
    delimiter: Literal[",", ";", "\t", "|"] | None = Field(
        default=None,
        description=(
            "Column separator of a CSV file, only when the user states it; otherwise it is "
            "detected from the file"
        ),
    )
    sheet: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Worksheet to read when a workbook has several",
    )
    year: int | None = Field(
        default=None,
        ge=1900,
        le=2100,
        description=(
            "Only when the user wrote a year and the document's month labels may carry none: "
            "that year; a year the document states takes precedence"
        ),
    )
    period_column: str = Field(
        min_length=1,
        max_length=256,
        description="Header of the column holding the months, as the user named it",
    )
    value_column: str = Field(
        min_length=1,
        max_length=256,
        description="Header of the column to add, as the user named it; also its label",
    )

    @model_validator(mode="after")
    def one_document(self) -> Self:
        if (self.url is None) == (not self.attached):
            raise ValueError("give either url or attached=true, not both or neither")
        if self.document is not None and not self.attached:
            raise ValueError("document names an upload; it needs attached=true")
        return self


class JoinTableArguments(BaseModel):
    """Join monthly columns of another published result onto the source's months."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["join_table"]
    source: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_SOURCE_UNCHANGED + " (the selected table)",
    )
    other: str = Field(
        pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
        description=_OTHER,
    )
    columns: tuple[Annotated[str, Field(min_length=1, max_length=400)], ...] | None = Field(
        default=None,
        min_length=1,
        max_length=12,
        description="Exact column labels of the other result; omit to join all its monthly columns",
    )

    @model_validator(mode="after")
    def two_tables(self) -> Self:
        if self.source == self.other:
            raise ValueError("join two different published results")
        return self


class RebaseArguments(BaseModel):
    """Rebase one index column already present in the published table."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["rebase"]
    source: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$", description=_SOURCE_UNCHANGED)
    column: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "The index column's exact label (a fetched series' label is its series_id); a "
            "one-column table is used as is"
        ),
    )
    reference_period: date = Field(description="Existing period end that becomes the new base")
    new_base: float = Field(strict=True, gt=0, description="Explicit new index level, usually 100")


class AlignArguments(BaseModel):
    """Select an exact shared or anchored period spine from existing cells."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["align"]
    source: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$", description=_SOURCE_UNCHANGED)
    columns: tuple[str, ...] = Field(min_length=2, max_length=32)
    join: Literal["inner", "left"]
    anchor_column: str | None = None

    @model_validator(mode="after")
    def policy_fields(self) -> Self:
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("columns must be distinct")
        if self.join == "inner" and self.anchor_column is not None:
            raise ValueError("inner alignment does not take anchor_column")
        if self.join == "left" and self.anchor_column not in self.columns:
            raise ValueError("left alignment needs anchor_column listed in columns")
        return self


class FilterArguments(BaseModel):
    """Keep cells in an inclusive period-end range; no free-form predicate."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["filter"]
    source: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$", description=_SOURCE_UNCHANGED)
    start_period: date | None = None
    end_period: date | None = None

    @model_validator(mode="after")
    def bounded_range(self) -> Self:
        if self.start_period is None and self.end_period is None:
            raise ValueError("filter needs start_period or end_period")
        if (
            self.start_period is not None
            and self.end_period is not None
            and self.start_period > self.end_period
        ):
            raise ValueError("start_period must not be after end_period")
        return self


class TableTransformArguments(
    RootModel[
        Annotated[
            DeflateArguments
            | AddSeriesArguments
            | ToFlowArguments
            | ResampleArguments
            | JoinTableArguments
            | RebaseArguments
            | AlignArguments
            | FilterArguments,
            Field(discriminator="operation"),
        ]
    ]
):
    """One tool with closed, operation-specific flat JSON argument objects."""


class DocumentTableTransformArguments(
    RootModel[
        Annotated[
            DeflateArguments
            | AddSeriesArguments
            | ToFlowArguments
            | ResampleArguments
            | AddDocumentColumnArguments
            | JoinTableArguments
            | RebaseArguments
            | AlignArguments
            | FilterArguments,
            Field(discriminator="operation"),
        ]
    ]
):
    """The same operations plus `add_document_column`, offered only with a fetch boundary."""


_METHODS = {
    "deflate": METHOD,
    "resample": RESAMPLE_METHOD,
    "to_flow": TO_FLOW_METHOD,
    "rebase": REBASE_METHOD,
}


class ColumnUnknown(ValueError):
    """The requested column is not in the table and the table has several."""


def _column_of(source: AnalyticalResult, requested: str) -> tuple[str, str | None]:
    """The label the request names, or a one-column table's only label.

    A same-plan step's table has labels the planner could not read when it planned:
    a lakehouse fetch labels each column by series_id, and the live E1 turn
    (2026-09-19) asked to deflate column 'value'. With one column there is nothing
    to choose, so it is used and the resolution is recorded on the result. Several
    columns must be named exactly; the refusal lists them.
    """
    labels = list(dict.fromkeys(value.label for value in source.values))
    if requested in labels:
        return requested, None
    if len(labels) == 1:
        return labels[0], (
            f"Column {requested!r} is not in the table; its only column {labels[0]!r} was used"
        )
    raise ColumnUnknown(
        f"No values are labelled {requested!r}; the table's columns are: " + "; ".join(labels)
    )


def _table_input(arguments: BaseModel) -> TableInput | None:
    if isinstance(arguments, (TableTransformArguments, DocumentTableTransformArguments)):
        selected = arguments.root
        others = (selected.other,) if isinstance(selected, JoinTableArguments) else ()
        return TableInput(source=selected.source, others=others)
    return None


def make_table_transform_tool(
    connection: DuckDBPyConnection,
    workspace: Workspace,
    *,
    lineage: Lineage | None = None,
    series_names: Mapping[str, str] | None = None,
    inspector: PreparedSeriesInspector | None = None,
    document_fetch: Fetcher | None = None,
    attachment: Attachment | None = None,
    document_ocr: OcrProvider | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    library: Mapping[str, Attachment] | None = None,
) -> ToolSpec:
    """Bind the tool to one database and one workspace.

    `document_fetch` is the operator's prompt-address switch: without it the
    `add_document_column` operation is not part of the schema at all.
    `document_ocr` reads PDF pages without text (DEC-149 column-total check).
    """
    names = dict(series_names or {})
    documents = dict(library or {})
    readable = attachment is not None or bool(documents)

    def failure(category: str, message: str) -> ToolResult:
        return ToolResult(
            ToolStatus.FAILURE,
            step_id="",
            tool="table_transform",
            error_category=category,
            warnings=(message,),
        )

    def resolve(
        name: str, context: ExecutionContext, role: str
    ) -> tuple[AnalyticalResult, str] | ToolResult:
        """A table by name: a current published result, else an earlier step of this plan.

        The validator required a same-plan step to be declared in depends_on, so
        the executor ran it first and its result is in the context (E1, DEC-165).
        """
        try:
            table: AnalyticalResult = workspace.value_of(name)
            origin = "workspace"
        except WorkspaceError:
            produced = context.outputs.get(name)
            candidate = getattr(produced, "result", produced)
            if not isinstance(candidate, AnalyticalResult):
                return failure(
                    "workspace_reference",
                    f"No current published result or earlier step of this plan is named {name!r}",
                )
            table, origin = candidate, "step"
        if table.status is not ResultStatus.COMPUTED:
            return failure("workspace_reference", f"{name!r} holds no computed values")
        if result_faults({name: table}, connection):
            return failure("workspace_evidence", f"The {role} table cannot be verified")
        return table, origin

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(
            arguments, (TableTransformArguments, DocumentTableTransformArguments)
        ):  # pragma: no cover
            raise TypeError("table_transform received arguments it did not declare")
        selected = arguments.root
        resolved = resolve(selected.source, context, "source")
        if isinstance(resolved, ToolResult):
            return resolved
        source, origin = resolved
        inputs = [canonical({origin: selected.source, "result": source.model_dump(mode="json")})]
        resolution: str | None = None
        requested_column: str | None = None
        refusal: AnalyticalResult | None = None
        if isinstance(
            selected, (DeflateArguments, ResampleArguments, ToFlowArguments, RebaseArguments)
        ):
            try:
                label, resolution = _column_of(source, selected.column)
            except ColumnUnknown as error:
                refusal = AnalyticalResult(
                    result_id=f"table_transform:{selected.operation}:{selected.source}",
                    kind=ResultKind.SERIES,
                    status=ResultStatus.ABSTAINED,
                    tool="table_transform",
                    method=_METHODS[selected.operation],
                    reason=str(error),
                )
            else:
                if label != selected.column:
                    requested_column = selected.column
                    selected = selected.model_copy(update={"column": label})
        if refusal is not None:
            result = refusal
        elif isinstance(selected, (DeflateArguments, AddSeriesArguments)):
            series_id = (
                selected.series_id
                if isinstance(selected, AddSeriesArguments)
                else selected.index_series_id
            )
            try:
                series = read_series(connection, series_id, inspector=inspector)
            except SeriesUnknown as error:
                return failure("series_unknown", str(error))
            inputs.append(series.snapshot)
            result = (
                _augmented(selected, source, series.observations, series.semantics, names)
                if isinstance(selected, AddSeriesArguments)
                else _deflated(selected, source, series.observations, series.semantics, names)
            )
        elif isinstance(selected, ResampleArguments):
            try:
                series = read_series(connection, selected.column, inspector=inspector)
            except SeriesUnknown as error:
                return failure("series_unknown", str(error))
            inputs.append(series.snapshot)
            result = _resampled(selected, source, series.semantics)
        elif isinstance(selected, ToFlowArguments):
            try:
                series = read_series(connection, selected.column, inspector=inspector)
            except SeriesUnknown as error:
                return failure("series_unknown", str(error))
            inputs.append(series.snapshot)
            result = _flowed(selected, source, series.semantics)
        elif isinstance(selected, JoinTableArguments):
            resolved_other = resolve(selected.other, context, "other")
            if isinstance(resolved_other, ToolResult):
                return resolved_other
            other, other_origin = resolved_other
            inputs.append(
                canonical({other_origin: selected.other, "result": other.model_dump(mode="json")})
            )
            result = _joined(selected, source, other)
        elif isinstance(selected, AddDocumentColumnArguments):
            if selected.year is not None and not year_in_question(selected.year, context.question):
                return failure("needs_input", "YEAR_NOT_IN_QUESTION")
            if selected.attached:
                chosen = choose_document(selected.document, attachment, documents)
                if isinstance(chosen, str):
                    return failure("no_attachment", chosen)
                read = read_attachment(
                    chosen,
                    delimiter=selected.delimiter,
                    sheet=selected.sheet,
                    ocr=document_ocr,
                )
            elif document_fetch is None or selected.url is None:
                return failure("document_disabled", "Reading a web address is not enabled")
            else:
                read = read_document(
                    selected.url,
                    context.question,
                    fetch=document_fetch,
                    delimiter=selected.delimiter,
                    sheet=selected.sheet,
                    ocr=document_ocr,
                    clock=clock,
                )
            document, media_type = read.output.source, read.output.media_type
            if read.failure is not None or document is None or media_type is None:
                return failure(read.failure or "not_admitted", read.output.code or "NOT_LOADED")
            try:
                column = read_column(
                    grids(read.output.table, read.output.document),
                    selected.period_column,
                    selected.value_column,
                    year=selected.year,
                    as_of=as_of(document),
                )
                if connection.execute(
                    "SELECT 1 FROM silver_series WHERE series_id = ? LIMIT 1",
                    [selected.value_column],
                ).fetchone():
                    raise ColumnRefused("LABEL_IS_A_SERIES")
            except ColumnRefused as error:
                result = _document_refused(selected, error.code)
            else:
                csv = csv_parsing(read.output.table)
                inputs.append(column_snapshot(column, document, media_type, csv=csv))
                source_node = (
                    lineage.record(
                        NodeKind.SOURCE_FILE,
                        document.source_id,
                        attributes={
                            "source_type": document.source_type,
                            "locator": document.locator,
                            "content_hash": document.content_hash or "",
                            "media_type": media_type,
                        },
                    )
                    if lineage is not None
                    else None
                )
                result = _documented(selected, source, column, document, source_node, csv)
        else:
            result = _closed_transform(selected, source)
        if resolution is not None and result.status is ResultStatus.COMPUTED:
            result = result.model_copy(
                update={
                    "warnings": [*result.warnings, resolution],
                    "parameters": {
                        **result.parameters,
                        "column_resolution": {
                            "requested": requested_column,
                            "used": getattr(selected, "column", None),
                        },
                    },
                }
            )
        recorded = _recorded_arguments(selected)
        node = None
        if lineage is not None and result.status is ResultStatus.COMPUTED:
            node = lineage.record(
                NodeKind.TRANSFORM,
                f"table_transform_{selected.operation}",
                attributes=recorded,
            )
            if result.evidence is not None:
                result = result.model_copy(
                    update={"evidence": result.evidence.model_copy(update={"lineage_node": node})}
                )
        result = _record_execution(
            connection,
            producer="table_transform",
            arguments=(
                canonical(recorded)
                if isinstance(selected, AddDocumentColumnArguments)
                else arguments.model_dump_json()
            ),
            inputs=inputs,
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
            "Change a table published in an earlier turn by producing a new result without "
            "mutating the published source. deflate adds an "
            "inflation-adjusted copy of one currency column (for example a credit balance) in "
            "the prices of reference_period, using a registered monthly price index such as a "
            "consumer price index. Refer to the published result by its name and to the column "
            "by its exact label. add_series adds a registered monthly series (for example a "
            "housing price index) on the table's exact months. Use source and series_id only "
            "for add_series. It preserves every old column, records missing months without "
            "filling them, and does not calculate a relationship or establish a cause. "
            "to_flow adds a per-period flow copy of a column the store records as cumulative "
            "(yearly_reset or since_inception), which is what comparison, breakpoint and "
            "table direction comparison can use; series-based tools still read original series. "
            "A column the store does "
            "not declare cumulative is refused rather than differenced. "
            "resample adds a monthly copy of a weekly column by the series' declared "
            "aggregation (state week_assignment), so a weekly rate can then be joined with "
            "monthly tables. "
            "rebase adds an explicitly based copy of an existing index column. align selects "
            "existing exact periods using inner or explicitly anchored-left policy. join_table "
            "adds the monthly columns of another published result (for example a table built "
            "from an uploaded document, or an official-series table) onto the source table's "
            "exact months, keeping each column's own unit. filter "
            "selects an inclusive period-end range. These unary operations never fill cells, "
            "convert frequency, or accept SQL."
            + (
                " add_document_column adds one column from a CSV, Excel, PDF or HTML table "
                + (
                    "at a web address written in the question (give the address exactly as url)"
                    if document_fetch is not None
                    else ""
                )
                + (" or " if document_fetch is not None and readable else "")
                + (
                    "in a document uploaded in this conversation (attached=true, and "
                    "document=<name> when there are several)"
                    if readable
                    else ""
                )
                + ", with the header of its month column and of the value column. Months must "
                "be explicit, one row per month; the value header must state its unit in "
                "parentheses. It needs no catalog_search and does not convert frequency."
                if document_fetch is not None or readable
                else ""
            )
        ),
        arguments=(
            DocumentTableTransformArguments
            if document_fetch is not None or readable
            else TableTransformArguments
        ),
        run=run,
        table_input=_table_input,
    )


def _closed_transform(
    arguments: RebaseArguments | AlignArguments | FilterArguments,
    source: AnalyticalResult,
) -> AnalyticalResult:
    """Apply one no-I/O operation and preserve the source as a separate artifact."""
    try:
        if isinstance(arguments, RebaseArguments):
            rebased = rebase_index(
                source,
                column_label=arguments.column,
                reference_period=arguments.reference_period,
                new_base=arguments.new_base,
            )
            return _rebased(
                arguments,
                source,
                rebased.values,
                rebased.transformation,
                rebased.label,
            )
        if isinstance(arguments, AlignArguments):
            shaped = align_periods(
                source,
                columns=arguments.columns,
                join=arguments.join,
                anchor_column=arguments.anchor_column,
            )
            return _shaped(arguments, source, shaped, method=ALIGN_METHOD)
        shaped = filter_periods(
            source,
            start_period=arguments.start_period,
            end_period=arguments.end_period,
        )
        return _shaped(arguments, source, shaped, method=FILTER_METHOD)
    except TableShapeRefused as error:
        return AnalyticalResult(
            result_id=f"table_transform:{arguments.operation}:{arguments.source}",
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method={
                "rebase": REBASE_METHOD,
                "align": ALIGN_METHOD,
                "filter": FILTER_METHOD,
            }[arguments.operation],
            reason=str(error),
        )


def _prior_evidence(source: AnalyticalResult) -> tuple[list[str], list[TransformationRecord]]:
    if source.evidence is None:
        return [], []
    refs = (
        [source.evidence.lineage_node]
        if source.evidence.lineage_node is not None
        else list(source.evidence.input_refs)
    )
    return refs, list(source.evidence.transformations)


def _rebased(
    arguments: RebaseArguments,
    source: AnalyticalResult,
    values: Sequence[ResultValue],
    transformation: TransformationRecord,
    label: str,
) -> AnalyticalResult:
    refs, previous = _prior_evidence(source)
    parameters = dict(source.parameters)
    parameters.update({"source": arguments.source, "rebasing": transformation.parameters})
    return AnalyticalResult(
        result_id=(
            f"table_transform:rebase:{arguments.source}:{arguments.column}:"
            f"{arguments.reference_period.isoformat()}:{arguments.new_base}"
        ),
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=REBASE_METHOD,
        values=[*source.values, *values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=refs,
            transformations=[*previous, transformation],
            sources=list(source.evidence.sources) if source.evidence is not None else [],
        ),
        warnings=list(source.warnings),
        limitations=[
            *source.limitations,
            f"Only {label} is rebased ({REBASE_FORMULA}); existing columns are unchanged",
            "Index rebasing changes the index reference scale; it is not inflation adjustment",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )


def _shaped(
    arguments: AlignArguments | FilterArguments,
    source: AnalyticalResult,
    shaped: ShapedTable,
    *,
    method: str,
) -> AnalyticalResult:
    refs, previous = _prior_evidence(source)
    parameters: dict[str, JsonValue] = {}
    series_names = source.parameters.get("series_names")
    if isinstance(series_names, dict):
        parameters["series_names"] = dict(series_names)
    key = "alignment" if isinstance(arguments, AlignArguments) else "filter"
    parameters.update({"source": arguments.source, key: shaped.transformation.parameters})
    warning = (
        f"{shaped.dropped_non_period_values} non-period summary value(s) were removed because "
        "they described the source row set"
    )
    if isinstance(arguments, AlignArguments):
        identity = (
            f"{arguments.join}:{arguments.anchor_column or '-'}:{'|'.join(arguments.columns)}"
        )
    else:
        identity = (
            f"{arguments.start_period.isoformat() if arguments.start_period else '-'}:"
            f"{arguments.end_period.isoformat() if arguments.end_period else '-'}"
        )
    return AnalyticalResult(
        result_id=f"table_transform:{arguments.operation}:{arguments.source}:{identity}",
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=method,
        values=list(shaped.values),
        coverage=shaped.coverage,
        parameters=parameters,
        samples=None,
        evidence=ResultEvidence(
            input_refs=refs,
            transformations=[*previous, shaped.transformation],
            sources=list(source.evidence.sources) if source.evidence is not None else [],
        ),
        warnings=[*source.warnings, *([warning] if shaped.dropped_non_period_values else [])],
        limitations=[
            *source.limitations,
            "Rows were selected by exact existing periods; no value was filled, interpolated, "
            "resampled, converted, or recomputed",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )


def _deflated(
    arguments: DeflateArguments,
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


def _augmented(
    arguments: AddSeriesArguments,
    source: AnalyticalResult,
    observations: Sequence[Observation],
    semantics: SeriesSemantics,
    names: Mapping[str, str],
) -> AnalyticalResult:
    result_id = f"table_transform:add_series:{arguments.source}:{arguments.series_id}"
    try:
        added = add_monthly_series(source, observations, semantics, series_id=arguments.series_id)
    except SeriesAdditionRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=ADD_SERIES_METHOD,
            reason=str(error),
        )
    known = source.parameters.get("series_names")
    series_names = dict(known) if isinstance(known, dict) else {}
    if arguments.series_id in names:
        series_names[arguments.series_id] = names[arguments.series_id]
    parameters = dict(source.parameters)
    parameters.update(
        {
            "series_names": series_names,
            "source": arguments.source,
            "added_series": added.transformation.parameters,
        }
    )
    warnings = list(source.warnings)
    if added.missing_periods:
        warnings.append(
            f"{len(added.missing_periods)} table period(s) have no value for "
            f"{arguments.series_id}; those cells are empty, never filled"
        )
    previous = source.evidence.transformations if source.evidence is not None else []
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=ADD_SERIES_METHOD,
        values=[*source.values, *added.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=[
                *(
                    [source.evidence.lineage_node]
                    if source.evidence is not None and source.evidence.lineage_node
                    else []
                ),
                *INPUTS,
            ],
            transformations=[*previous, added.transformation],
        ),
        warnings=warnings,
        limitations=[
            *source.limitations,
            "The added column is aligned by exact monthly periods only; no resampling, "
            "filling, currency conversion, inflation adjustment or rebasing was applied to it",
            "Existing comparison metrics still concern their original columns; adding a "
            "column does not compute a relationship with it",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )


def _resampled(
    arguments: ResampleArguments,
    source: AnalyticalResult,
    semantics: SeriesSemantics,
) -> AnalyticalResult:
    """The source table with a monthly copy of one weekly column."""
    result_id = f"table_transform:resample:{arguments.source}:{arguments.column}"
    column = [value for value in source.values if value.label == arguments.column]
    try:
        reduced = resample_column(
            column,
            semantics,
            column_label=arguments.column,
            assignment=WeekAssignment(arguments.week_assignment),
        )
    except ResampleRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=RESAMPLE_METHOD,
            reason=str(error),
        )
    parameters = dict(source.parameters)
    parameters.update({"source": arguments.source, "resampled": arguments.column})
    warnings = list(source.warnings)
    if reduced.incomplete:
        warnings.append(
            f"{len(reduced.incomplete)} month(s) did not see every week they expected; "
            "their monthly value rests on fewer weeks and the coverage is recorded"
        )
    previous = source.evidence.transformations if source.evidence is not None else []
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=RESAMPLE_METHOD,
        values=[*source.values, *reduced.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=[
                *(
                    [source.evidence.lineage_node]
                    if source.evidence is not None and source.evidence.lineage_node
                    else []
                ),
                *INPUTS,
            ],
            transformations=[*previous, reduced.transformation],
        ),
        warnings=warnings,
        limitations=[
            *source.limitations,
            f"{reduced.label} is a monthly reduction by the series' declared aggregation; "
            "the weekly column it came from is unchanged beside it",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )


def _flowed(
    arguments: ToFlowArguments,
    source: AnalyticalResult,
    semantics: SeriesSemantics,
) -> AnalyticalResult:
    """The source table with a per-period flow copy of one declared cumulative column."""
    result_id = f"table_transform:to_flow:{arguments.source}:{arguments.column}"
    column = [value for value in source.values if value.label == arguments.column]
    try:
        flowed = to_flow_column(column, semantics, column_label=arguments.column)
        if any(value.label == flowed.label for value in source.values):
            raise AccumulationRefused("This table already contains the converted flow column")
        if not flowed.values:
            raise AccumulationRefused("No period has a usable predecessor or yearly reset")
    except AccumulationRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=TO_FLOW_METHOD,
            reason=str(error),
        )
    parameters = dict(source.parameters)
    parameters.update({"source": arguments.source, "flow_of": arguments.column})
    warnings = list(source.warnings)
    if flowed.empty_periods:
        warnings.append(
            f"{len(flowed.empty_periods)} period(s) have no usable predecessor, so their flow "
            "is empty rather than a figure spanning two periods"
        )
    previous = source.evidence.transformations if source.evidence is not None else []
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=TO_FLOW_METHOD,
        values=[*source.values, *flowed.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=[
                *(
                    [source.evidence.lineage_node]
                    if source.evidence is not None and source.evidence.lineage_node
                    else []
                ),
                *INPUTS,
            ],
            transformations=[*previous, flowed.transformation],
        ),
        warnings=warnings,
        limitations=[
            *source.limitations,
            f"Only {flowed.label} is a per-period flow ({TO_FLOW_FORMULA}); every other column "
            "keeps its original cumulative or level meaning",
            "The conversion follows the store's declared cumulative kind; it is not inferred "
            "from the values and it does not restate the source",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )


def _joined(
    arguments: JoinTableArguments, source: AnalyticalResult, other: AnalyticalResult
) -> AnalyticalResult:
    result_id = f"table_transform:join_table:{arguments.source}:{arguments.other}"
    try:
        joined = join_monthly_table(
            source, other, other_name=arguments.other, columns=arguments.columns
        )
    except SeriesAdditionRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=JOIN_METHOD,
            reason=str(error),
        )
    series_names: dict[str, JsonValue] = {}
    for table in (source, other):
        known = table.parameters.get("series_names")
        if isinstance(known, dict):
            series_names.update(known)
    parameters = dict(source.parameters)
    parameters.update(
        {
            "series_names": series_names,
            "source": arguments.source,
            "joined_table": joined.transformation.parameters,
        }
    )
    refs: list[str] = []
    for table in (source, other):
        if table.evidence is not None:
            refs.extend(
                [table.evidence.lineage_node]
                if table.evidence.lineage_node is not None
                else table.evidence.input_refs
            )
    sources = [
        *(source.evidence.sources if source.evidence is not None else []),
        *(other.evidence.sources if other.evidence is not None else []),
    ]
    carried = [
        note
        for note in other.unresolved_semantics
        if ":" not in note or any(note.startswith(f"{label}:") for label in joined.columns)
    ]
    missing = joined.transformation.parameters["missing_periods"]
    gaps = (
        sum(len(ends) for ends in missing.values() if isinstance(ends, list))
        if isinstance(missing, dict)
        else 0
    )
    previous = source.evidence.transformations if source.evidence is not None else []
    gap_warning = f"{gaps} joined cell(s) have no value in {arguments.other!r}; never filled"
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=JOIN_METHOD,
        values=[*source.values, *joined.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=list(dict.fromkeys(refs)) or [source.result_id],
            transformations=[*previous, joined.transformation],
            sources=list({ref.source_id: ref for ref in sources}.values()),
        ),
        warnings=[*source.warnings, *([gap_warning] if gaps else [])],
        limitations=list(
            dict.fromkeys(
                [
                    *source.limitations,
                    *other.limitations,
                    "Joined columns are aligned by exact monthly periods only; the source "
                    "table's rows define the months and nothing was resampled, filled or "
                    "converted",
                ]
            )
        ),
        unresolved_semantics=list(dict.fromkeys([*source.unresolved_semantics, *carried])),
    )


def _recorded_arguments(selected: BaseModel) -> dict[str, Any]:
    """Arguments as lineage keeps them; an address is kept only as its opaque identity."""
    recorded: dict[str, Any] = selected.model_dump(mode="json")
    if isinstance(selected, AddDocumentColumnArguments):
        recorded.pop("url")
        if selected.url is not None:
            recorded["document_source_id"] = source_id_for(selected.url)
    return recorded


def _document_refused(arguments: AddDocumentColumnArguments, code: str) -> AnalyticalResult:
    return AnalyticalResult(
        result_id=f"table_transform:add_document_column:{arguments.source}",
        kind=ResultKind.SERIES,
        status=ResultStatus.ABSTAINED,
        tool="table_transform",
        method=DOCUMENT_METHOD,
        reason=f"The document column cannot be added ({code})",
    )


def _documented(
    arguments: AddDocumentColumnArguments,
    source: AnalyticalResult,
    column: DocumentColumn,
    document: SourceRef,
    source_node: str | None,
    csv: dict[str, str] | None = None,
) -> AnalyticalResult:
    result_id = (
        f"table_transform:add_document_column:{arguments.source}:{document.source_id}:"
        f"{column.location['column_index']}"
    )
    try:
        added = add_document_column(
            source,
            column.levels,
            label=arguments.value_column,
            unit=column.unit,
            scale=column.scale,
            document_rows=len(column.rows),
            content_hash=document.content_hash or "",
            measure=column.measure,
        )
    except SeriesAdditionRefused as error:
        return AnalyticalResult(
            result_id=result_id,
            kind=ResultKind.SERIES,
            status=ResultStatus.ABSTAINED,
            tool="table_transform",
            method=DOCUMENT_METHOD,
            reason=str(error),
        )
    transformation = added.transformation
    decided = column.rules.evidence() if column.rules is not None else {}
    if csv is not None or decided:
        transformation = transformation.model_copy(
            update={
                "parameters": {
                    **transformation.parameters,
                    **({"csv": csv} if csv is not None else {}),
                    **decided,
                }
            }
        )
    parameters = dict(source.parameters)
    parameters.update(
        {"source": arguments.source, "added_document_column": transformation.parameters}
    )
    warnings = list(source.warnings)
    if column.rules is not None:
        warnings.extend(column.rules.warnings())
    if added.missing_periods:
        warnings.append(
            f"{len(added.missing_periods)} table period(s) have no value in the document "
            "column; those cells are empty, never filled"
        )
    previous = source.evidence.transformations if source.evidence is not None else []
    prior = (
        [source.evidence.lineage_node]
        if source.evidence is not None and source.evidence.lineage_node
        else []
    )
    return AnalyticalResult(
        result_id=result_id,
        kind=source.kind,
        status=ResultStatus.COMPUTED,
        tool="table_transform",
        method=DOCUMENT_METHOD,
        values=[*source.values, *added.values],
        coverage=source.coverage,
        parameters=parameters,
        samples=source.samples,
        evidence=ResultEvidence(
            input_refs=[*prior, source_node or document.source_id],
            transformations=[*previous, transformation],
            sources=[document],
        ),
        warnings=warnings,
        limitations=[
            *source.limitations,
            "The added column was read from a fetched document on explicit months only; no "
            "resampling, filling, currency conversion, inflation adjustment or rebasing was "
            "applied to it",
            measure_limitation(column.measure),
            *(column.rules.limitations() if column.rules is not None else ()),
            "Existing comparison metrics still concern their original columns; adding a "
            "column does not compute a relationship with it",
        ],
        unresolved_semantics=list(source.unresolved_semantics),
    )
