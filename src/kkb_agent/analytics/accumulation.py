"""Turning a declared cumulative column into per-period flow (M2-16 at runtime).

`lakehouse.cumulative.to_flow` has always known how to difference a cumulative
series, and every analytic refuses a cumulative one with "convert it to flow
first". Nothing could perform that conversion on a published table, so the
refusal had no exit. This module is that exit, and it keeps the same rule the
converter was written under: **the declared kind decides**, never the shape of
the values. A series whose cumulative kind is unknown is refused rather than
differenced on a guess, because a stock that never falls and a since-inception
cumulative look identical.

A converted period that has no usable predecessor stays empty. January of a
yearly-reset series is the month itself; the first period of a since-inception
series needs the level before it, which the caller supplies as `baseline` or the
period comes back empty.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Final

from kkb_agent.core import CumulativeKind, Frequency, ResultValue, StockFlow, TransformationRecord
from kkb_agent.lakehouse.cumulative import CumulativeError, to_flow
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, period_bounds

METHOD: Final = "to-flow-v1"
FORMULA: Final = (
    "flow[period] = cumulative[period] - cumulative[previous period]; "
    "yearly_reset January uses the current value; unusable predecessors stay empty"
)
CONVERTIBLE: Final = (CumulativeKind.YEARLY_RESET, CumulativeKind.SINCE_INCEPTION)


class AccumulationRefused(ValueError):
    """The column cannot be converted as asked. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Flowed:
    values: tuple[ResultValue, ...]
    empty_periods: tuple[date, ...]
    transformation: TransformationRecord
    label: str


def to_flow_column(
    column: Sequence[ResultValue],
    semantics: SeriesSemantics,
    *,
    column_label: str,
    baseline: float | None = None,
) -> Flowed:
    """Per-period flow for a declared cumulative column of a published table."""
    if not column:
        raise AccumulationRefused(f"No values are labelled {column_label!r}")
    if semantics.cumulative not in CONVERTIBLE:
        raise AccumulationRefused(
            f"{column_label} is declared {semantics.cumulative.value}; only a series recorded as "
            "yearly_reset or since_inception may be converted, and the declaration decides, "
            "not the shape of the values"
        )
    if semantics.frequency is not Frequency.MONTHLY:
        raise AccumulationRefused(f"{column_label} is not monthly; no other frequency is converted")
    if baseline is not None and not isfinite(baseline):
        raise AccumulationRefused("The explicit baseline must be finite")
    dated: dict[date, ResultValue] = {}
    for value in column:
        if value.period is None or value.period.frequency is not Frequency.MONTHLY:
            raise AccumulationRefused(f"{column_label} is not a monthly column")
        try:
            valid = (value.period.start, value.period.end) == period_bounds(
                Frequency.MONTHLY, value.period.end
            )
        except SemanticsError:
            valid = False
        if not valid or not isfinite(value.value):
            raise AccumulationRefused(f"{column_label} has invalid periods or values")
        if value.label != column_label or (value.unit, value.scale, value.measure) != (
            semantics.unit,
            semantics.scale,
            semantics.observation,
        ):
            raise AccumulationRefused(f"{column_label} disagrees with its stored semantics")
        if value.period.end in dated:
            raise AccumulationRefused(f"{column_label} has duplicate periods")
        dated[value.period.end] = value
    ordered = sorted(dated.items())
    try:
        flows = to_flow(
            [Observation(value.period.start, end, value.value) for end, value in ordered],  # type: ignore[union-attr]
            semantics.cumulative,
            frequency=Frequency.MONTHLY,
            baseline=baseline,
        )
    except CumulativeError as error:  # pragma: no cover - guarded above
        raise AccumulationRefused(str(error)) from error

    label = f"{column_label} flow ({semantics.cumulative.value})"
    values: list[ResultValue] = []
    empty: list[date] = []
    for (end, original), flow in zip(ordered, flows, strict=True):
        if flow.value is None:
            empty.append(end)
            continue
        values.append(
            original.model_copy(
                update={
                    "label": label,
                    "value": flow.value,
                    "measure": StockFlow.FLOW,
                    "lag": None,
                }
            )
        )
    transformation = TransformationRecord(
        operation="to_flow",
        parameters={
            "formula": FORMULA,
            "declared_cumulative": semantics.cumulative.value,
            "baseline": baseline,
            "empty_periods": [item.isoformat() for item in empty],
        },
        input_refs=[column_label],
        output_ref=label,
    )
    return Flowed(tuple(values), tuple(empty), transformation, label)
