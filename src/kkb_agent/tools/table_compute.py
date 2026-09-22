"""`table_compute`: a new column from the ones a table already has.

The transform surface could reshape a table and summarise a column, and it could
not put two columns together. So a question that asks for a group — "TP
mevduatları açılış vadelerine göre 3 aya kadar ve 3 aydan fazla olacak şekilde
iki grupta topla" — had no operation to reach for, and neither did a ratio, a
share or a difference between two series. Freeing the model to plan its own work
does not help if the arithmetic it plans has nowhere to run.

Two operations, both bounded and both recorded:

* `combine` puts several columns into one with sum, mean, min or max. The
  columns must agree on what they measure, because adding a rate to a stock is
  not a group, and the result inherits that agreement.
* `arithmetic` is one column against another column or a constant: add,
  subtract, multiply, divide, share (a/b as a percent) or change (a/b-1 as a
  percent). A ratio of like units is dimensionless; a ratio of unlike units
  keeps neither and says so.

Every cell is computed here, from values that came from a tool. Nothing asks the
model for a number and nothing takes one from its prose.
"""

from __future__ import annotations

from math import fsum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    ResultEvidence,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
    TransformationRecord,
)

METHOD = "typed-column-arithmetic-v1"

Combine = Literal["sum", "mean", "min", "max"]
Arithmetic = Literal["add", "subtract", "multiply", "divide", "share", "change"]

#: What a ratio of like quantities is: a number, not a currency or an index.
_RATIO_UNIT = DIMENSIONLESS


class ComputeArguments(BaseModel):
    """A new column, named, from columns this table already holds."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(min_length=1, max_length=64, description="Action id or table name")
    label: str = Field(min_length=1, max_length=200, description="Label for the new column")
    operation: Combine | Arithmetic = Field(description="How the new column is produced")
    columns: list[str] = Field(
        default_factory=list,
        max_length=24,
        description="Exact labels to combine (sum, mean, min, max)",
    )
    left: str | None = Field(default=None, max_length=200, description="First column")
    right: str | None = Field(default=None, max_length=200, description="Second column")
    constant: float | None = Field(default=None, description="Use instead of right")

    @model_validator(mode="after")
    def enough_to_compute(self) -> ComputeArguments:
        if self.operation in ("sum", "mean", "min", "max"):
            if len(self.columns) < 2:
                raise ValueError("combine needs at least two columns")
            return self
        if not self.left or (self.right is None and self.constant is None):
            raise ValueError("this operation needs left and either right or constant")
        return self


def _periods(result: AnalyticalResult, label: str) -> dict[str, ResultValue]:
    """One cell per period for a column, keyed by the period it belongs to."""
    return {
        value.period.end.isoformat(): value
        for value in result.values
        if value.label == label and value.period is not None
    }


def _same(cells: list[ResultValue]) -> tuple[str | None, Scale, StockFlow] | None:
    """What the columns agree on, or None when they do not agree."""
    kinds = {(cell.unit, cell.scale, cell.measure) for cell in cells}
    return kinds.pop() if len(kinds) == 1 else None


def _combined(
    source: AnalyticalResult, arguments: ComputeArguments
) -> tuple[list[ResultValue], list[str]]:
    """Several columns into one, period by period, where every one of them has a cell."""
    columns = {label: _periods(source, label) for label in arguments.columns}
    missing = [label for label, cells in columns.items() if not cells]
    if missing:
        raise _Refused(f"bu sütunlar tabloda yok: {', '.join(missing)}")
    shared = sorted(set.intersection(*(set(cells) for cells in columns.values())))
    if not shared:
        raise _Refused("bu sütunların ortak bir dönemi yok")
    made: list[ResultValue] = []
    cautions: list[str] = []
    for period in shared:
        cells = [columns[label][period] for label in arguments.columns]
        agreed = _same(cells)
        if agreed is None:
            raise _Refused(
                "bu sütunlar aynı şeyi ölçmüyor (birim, ölçek ya da tür farklı); "
                "toplamak bir grup üretmez"
            )
        numbers = [cell.value for cell in cells]
        if arguments.operation == "sum":
            amount = fsum(numbers)
        elif arguments.operation == "mean":
            amount = fsum(numbers) / len(numbers)
        elif arguments.operation == "min":
            amount = min(numbers)
        else:
            amount = max(numbers)
        unit, scale, measure = agreed
        if arguments.operation == "sum" and measure in (StockFlow.RATE, StockFlow.INDEX):
            cautions.append(
                f"{arguments.label}: bir {measure.value} toplandı; bu genellikle "
                "anlamlı bir büyüklük vermez"
            )
        made.append(
            cells[0].model_copy(
                update={
                    "label": arguments.label,
                    "value": amount,
                    "unit": unit,
                    "scale": scale,
                    "measure": measure,
                }
            )
        )
    return made, sorted(set(cautions))


def _arithmetic(
    source: AnalyticalResult, arguments: ComputeArguments
) -> tuple[list[ResultValue], list[str]]:
    """One column against another column or a constant."""
    left = _periods(source, arguments.left or "")
    if not left:
        raise _Refused(f"{arguments.left!r} bu tabloda yok")
    right = _periods(source, arguments.right) if arguments.right else {}
    if arguments.right and not right:
        raise _Refused(f"{arguments.right!r} bu tabloda yok")
    shared = sorted(set(left) & set(right)) if right else sorted(left)
    if not shared:
        raise _Refused("iki sütunun ortak bir dönemi yok")
    made: list[ResultValue] = []
    cautions: list[str] = []
    for period in shared:
        a = left[period]
        b = right[period].value if right else float(arguments.constant or 0.0)
        other = right[period] if right else None
        try:
            amount, unit, scale, measure = _apply(arguments.operation, a, b, other, cautions)
        except ZeroDivisionError:
            continue
        made.append(
            a.model_copy(
                update={
                    "label": arguments.label,
                    "value": amount,
                    "unit": unit,
                    "scale": scale,
                    "measure": measure,
                }
            )
        )
    if not made:
        raise _Refused("hiçbir dönemde hesaplanabilir bir değer çıkmadı")
    return made, sorted(set(cautions))


def _apply(
    operation: str, a: ResultValue, b: float, other: ResultValue | None, cautions: list[str]
) -> tuple[float, str | None, Scale, StockFlow]:
    """The arithmetic, and what the answer is measured in."""
    alike = other is None or (a.unit, a.scale, a.measure) == (
        other.unit,
        other.scale,
        other.measure,
    )
    if operation in ("add", "subtract"):
        if not alike:
            raise _Refused("farklı birimdeki iki sütun toplanıp çıkarılamaz")
        return (a.value + b if operation == "add" else a.value - b), a.unit, a.scale, a.measure
    if operation == "multiply":
        return a.value * b, a.unit, a.scale, a.measure
    if b == 0:
        raise ZeroDivisionError
    if operation == "divide":
        if other is None:
            # Dividing by a plain number scales the quantity; it does not turn it into
            # a ratio. Twelve million lira halved is six million lira, and calling that
            # a dimensionless rate loses both the currency and the scale.
            return a.value / b, a.unit, a.scale, a.measure
        if not alike:
            cautions.append("farklı birimlerin oranı: sonucun birimi taşınmadı")
        return a.value / b, _RATIO_UNIT, Scale.ONE, StockFlow.RATE
    if operation == "share":
        if not alike:
            cautions.append("farklı birimlerin payı: sonucun birimi taşınmadı")
        return (a.value / b) * 100.0, "percent", Scale.ONE, StockFlow.RATE
    return (a.value / b - 1.0) * 100.0, "percent", Scale.ONE, StockFlow.RATE


class _Refused(ValueError):
    """Why this column cannot be computed, in words the model can act on."""


def make_table_compute_tool() -> ToolSpec:
    """Bind the tool. It reads a table the turn already has and writes one column."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(arguments, ComputeArguments):  # pragma: no cover - contract
            raise TypeError("table_compute received arguments it did not declare")
        found = context.outputs.get(arguments.source)
        if not isinstance(found, AnalyticalResult) or found.status is not ResultStatus.COMPUTED:
            known = ", ".join(sorted(context.outputs)) or "yok"
            return ToolResult(
                ToolStatus.FAILURE,
                arguments.source,
                "table_compute",
                error_category="table_reference",
                warnings=(f"{arguments.source!r} hesaplanmış bir tablo değil. Elde: {known}",),
            )
        try:
            if arguments.operation in ("sum", "mean", "min", "max"):
                made, cautions = _combined(found, arguments)
            else:
                made, cautions = _arithmetic(found, arguments)
        except _Refused as refusal:
            return ToolResult(
                ToolStatus.FAILURE,
                arguments.source,
                "table_compute",
                error_category="needs_input",
                warnings=(str(refusal),),
            )
        record = TransformationRecord(
            operation=f"compute:{arguments.operation}",
            parameters={
                "label": arguments.label,
                "columns": list(arguments.columns) or None,
                "left": arguments.left,
                "right": arguments.right,
                "constant": arguments.constant,
            },
            input_refs=[arguments.source],
            output_ref=arguments.label,
        )
        refs = list(found.evidence.input_refs) if found.evidence is not None else [arguments.source]
        previous = list(found.evidence.transformations) if found.evidence is not None else []
        return ToolResult(
            ToolStatus.SUCCESS,
            arguments.source,
            "table_compute",
            output=found.model_copy(
                update={
                    "result_id": f"table_compute:{arguments.source}:{arguments.label}",
                    "values": [*found.values, *made],
                    "evidence": ResultEvidence(
                        input_refs=refs,
                        transformations=[*previous, record],
                        sources=list(found.evidence.sources) if found.evidence else [],
                    ),
                    "limitations": [*found.limitations, *cautions],
                }
            ),
            warnings=tuple(cautions),
        )

    return ToolSpec(
        name="table_compute",
        description=(
            "Add one computed column to a table you already have, keeping every column "
            "it holds. combine (sum, mean, min, max) puts several columns into one and "
            "needs them to measure the same thing — this is how a group is built, such "
            "as maturities added into one bucket. The rest take left with either right "
            "or constant: add, subtract, multiply, divide, share (left/right as a "
            "percent) and change (left/right-1 as a percent). Give source=<action id or "
            "table name> and label=<the new column's name>."
        ),
        arguments=ComputeArguments,
        run=run,
    )


__all__ = ["METHOD", "ComputeArguments", "make_table_compute_tool"]
