"""Closed, evidence-friendly scalar aggregation over one typed period column."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import fsum
from typing import Literal

from kkb_agent.core import (
    DIMENSIONLESS,
    AnalyticalResult,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    StockFlow,
    TransformationRecord,
)

SummaryKind = Literal["mean", "sum", "min", "max", "first", "last", "count"]
METHOD = "typed-period-summary-v1"


class SummaryRefused(ValueError):
    """The requested aggregate would invent a meaning or has no input."""


@dataclass(frozen=True, slots=True)
class Summarized:
    values: tuple[ResultValue, ...]
    coverage: Period
    samples: SampleCounts
    transformation: TransformationRecord


def summarize_column(
    source: AnalyticalResult,
    *,
    column_label: str,
    aggregation: SummaryKind,
    start_period: date | None = None,
    end_period: date | None = None,
) -> Summarized:
    if source.status is not ResultStatus.COMPUTED:
        raise SummaryRefused("The source result is not computed")
    column = [value for value in source.values if value.label == column_label]
    if not column or any(value.period is None for value in column):
        raise SummaryRefused("The selected column is not a typed period column")
    if any(value.period.frequency is Frequency.UNKNOWN for value in column if value.period):
        raise SummaryRefused("The selected column has no known frequency")
    kinds = {
        (value.unit, value.scale, value.measure, value.period.frequency)
        for value in column
        if value.period
    }
    if len(kinds) != 1:
        raise SummaryRefused("The selected column mixes units, scales, measures or frequencies")
    periods = [value.period.end for value in column if value.period is not None]
    if len(periods) != len(set(periods)):
        raise SummaryRefused("The selected column repeats a period")
    selected = sorted(
        (
            value
            for value in column
            if value.period is not None
            and (start_period is None or value.period.end >= start_period)
            and (end_period is None or value.period.end <= end_period)
        ),
        key=lambda value: value.period.end if value.period is not None else date.min,
    )
    if not selected:
        raise SummaryRefused("The requested period range contains no observations")
    template = selected[0]
    if aggregation != "count" and (template.unit is None or template.scale is Scale.UNKNOWN):
        raise SummaryRefused("The column's unit or scale is unresolved")
    if aggregation == "sum" and template.measure is not StockFlow.FLOW:
        raise SummaryRefused("Summing a stock, rate or index level over periods is not meaningful")
    first_period = selected[0].period
    last_period = selected[-1].period
    if first_period is None or last_period is None:
        raise SummaryRefused("The selected column is not a typed period column")
    coverage = Period(
        start=first_period.start,
        end=last_period.end,
        frequency=first_period.frequency,
        weekly_anchor=first_period.weekly_anchor,
    )
    if aggregation == "mean":
        answer: Sequence[ResultValue] = [
            template.model_copy(
                update={
                    "label": f"{column_label} mean",
                    "value": fsum(v.value for v in selected) / len(selected),
                    "period": coverage,
                }
            )
        ]
    elif aggregation == "sum":
        answer = [
            template.model_copy(
                update={
                    "label": f"{column_label} sum",
                    "value": fsum(v.value for v in selected),
                    "period": coverage,
                }
            )
        ]
    elif aggregation in ("min", "max"):
        extreme = (
            min(v.value for v in selected)
            if aggregation == "min"
            else max(v.value for v in selected)
        )
        answer = [
            value.model_copy(update={"label": f"{column_label} {aggregation}"})
            for value in selected
            if value.value == extreme
        ]
    elif aggregation == "first":
        answer = [selected[0].model_copy(update={"label": f"{column_label} first"})]
    elif aggregation == "last":
        answer = [selected[-1].model_copy(update={"label": f"{column_label} last"})]
    else:
        answer = [
            ResultValue(
                label=f"{column_label} period count",
                value=float(len(selected)),
                unit=DIMENSIONLESS,
                scale=Scale.ONE,
            )
        ]
    transformation = TransformationRecord(
        operation="summarize",
        parameters={
            "aggregation": aggregation,
            "column": column_label,
            "start_period": start_period.isoformat() if start_period else None,
            "end_period": end_period.isoformat() if end_period else None,
            "first_used": first_period.end.isoformat(),
            "last_used": last_period.end.isoformat(),
            "used": len(selected),
        },
        input_refs=[source.result_id, column_label],
        output_ref=f"{column_label} {aggregation}",
    )
    return Summarized(tuple(answer), coverage, SampleCounts(used=len(selected)), transformation)
