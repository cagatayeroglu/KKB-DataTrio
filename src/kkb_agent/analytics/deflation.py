"""Deflation of a currency column by a price index (M2-15, organizer Turn 2).

`real_t = nominal_t × index[reference] / index[t]` expresses every nominal amount
in the prices of one explicit reference period. Different base years or
reference periods give different real figures that all look plausible, so
nothing here is defaulted:

- the reference period is a required argument and must be published by the
  index with a value;
- the index must declare itself an INDEX with a base year, on the same monthly
  calendar as the column (rebasing between bases is M2-14, not done here);
- the column must be a currency-denominated stock or flow — a rate or an index
  is not deflated;
- a month without an index value, or without a nominal value, has no real
  value: nothing is filled, carried or interpolated.

The output keeps the column's currency and scale; its label names the index and
reference month, because "real TRY" without them is not a statement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from kkb_agent.core import Frequency, ResultValue, StockFlow, TransformationRecord
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics

METHOD: Final = "deflate-v1"
FORMULA: Final = "real = nominal * index[reference] / index[period]"
CURRENCIES: Final = frozenset({"TRY", "USD", "EUR"})


class DeflationRefused(ValueError):
    """The inputs cannot be deflated as asked. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Deflated:
    values: tuple[ResultValue, ...]
    missing_periods: tuple[date, ...]
    transformation: TransformationRecord
    label: str


def deflate(
    column: Sequence[ResultValue],
    index: Sequence[Observation],
    index_semantics: SeriesSemantics,
    *,
    column_label: str,
    index_id: str,
    reference_end: date,
) -> Deflated:
    """Real values for every monthly value in `column`, in reference-month prices.

    A currency column becomes an amount in the reference month's money. A price index
    becomes a **real index**: the same division, and what it measures is the index's
    movement net of general prices. The organizer's third reference question asks exactly
    that of the housing price index, and until now it was refused as "not a
    currency-denominated stock or flow" with no other operation able to produce it (live
    2026-09-22). Anything else - a rate, a count, a ratio - is still refused: dividing a
    per-cent by a price level measures nothing.
    """
    if not column:
        raise DeflationRefused(f"No values are labelled {column_label!r}")
    if index_semantics.observation is not StockFlow.INDEX or index_semantics.base_year is None:
        raise DeflationRefused(f"{index_id} is not a price index with a recorded base year")
    if index_semantics.frequency is not Frequency.MONTHLY:
        raise DeflationRefused(f"{index_id} is not monthly; rebasing/alignment is not supported")
    dated: dict[date, ResultValue] = {}
    for value in column:
        if value.period is None or value.period.frequency is not Frequency.MONTHLY:
            raise DeflationRefused(f"{column_label} is not a monthly column")
        currency = value.unit in CURRENCIES and value.measure in (StockFlow.STOCK, StockFlow.FLOW)
        if not currency and value.measure is not StockFlow.INDEX:
            raise DeflationRefused(
                f"{column_label} is neither a currency-denominated stock or flow nor an "
                "index; it is not deflated"
            )
        if value.period.end in dated:
            raise DeflationRefused(f"{column_label} has duplicate periods")
        dated[value.period.end] = value
    levels: dict[date, float] = {}
    for item in index:
        if item.value is not None:
            if item.value <= 0:
                raise DeflationRefused(f"{index_id} holds a non-positive index value")
            levels[item.period_end] = item.value
    reference = levels.get(reference_end)
    if reference is None:
        raise DeflationRefused(
            f"{index_id} publishes no value for the reference period {reference_end.isoformat()}"
        )

    indexed = column[0].measure is StockFlow.INDEX
    label = (
        f"{column_label} real, deflated by {index_id} ({reference_end:%Y-%m} = base)"
        if indexed
        else f"{column_label} real, {reference_end:%Y-%m} prices ({index_id})"
    )
    real: list[ResultValue] = []
    missing: list[date] = []
    for end, value in sorted(dated.items()):
        level = levels.get(end)
        if level is None:
            missing.append(end)
            continue
        real.append(
            value.model_copy(
                update={"label": label, "value": value.value * reference / level, "lag": None}
            )
        )
    transformation = TransformationRecord(
        operation="deflate",
        parameters={
            "formula": FORMULA,
            "index": index_id,
            "index_base_year": index_semantics.base_year,
            "reference_period": reference_end.isoformat(),
            "reference_index": reference,
            "missing_index_periods": [item.isoformat() for item in missing],
        },
        input_refs=[column_label, index_id],
        output_ref=label,
    )
    return Deflated(tuple(real), tuple(missing), transformation, label)
