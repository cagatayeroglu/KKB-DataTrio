"""Version-bound column declarations, carried by producer-signed table results.

Cells alone cannot declare cumulative behaviour, aggregation, base year or origin.
A consumer must read this declaration, never manufacture absent semantics.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import cast

from pydantic import JsonValue

from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics

KEY = "column_contracts"


def encode(
    semantics: SeriesSemantics, *, column_id: str, artifact_id: str | None = None
) -> dict[str, JsonValue]:
    return {
        "column_id": column_id,
        "artifact_id": artifact_id,
        "semantics": cast(dict[str, JsonValue], asdict(semantics)),
    }


def declarations(result: AnalyticalResult) -> dict[str, JsonValue]:
    value = result.parameters.get(KEY)
    return dict(value) if isinstance(value, dict) else {}


def decode(result: AnalyticalResult, label: str) -> SeriesSemantics:
    contract = declarations(result).get(label)
    if not isinstance(contract, dict) or not isinstance(contract.get("column_id"), str):
        raise SemanticsError("Column has no recorded semantic carrier")
    raw = contract.get("semantics")
    if not isinstance(raw, dict):
        raise SemanticsError("Column has no recorded semantics")
    try:
        semantic = SeriesSemantics(
            unit=str(raw["unit"]),
            scale=Scale(raw["scale"]),
            frequency=Frequency(raw["frequency"]),
            observation=StockFlow(raw["observation"]),
            cumulative=CumulativeKind(raw["cumulative"]),
            aggregation=Aggregation(raw["aggregation"]),
            anchor=WeeklyAnchor(raw["anchor"]) if raw["anchor"] is not None else None,
            base_year=int(raw["base_year"]) if isinstance(raw["base_year"], int) else None,
        )
        semantic.require_resolved()
        return semantic
    except (KeyError, ValueError, TypeError) as error:
        raise SemanticsError("Column semantic carrier is incomplete or inconsistent") from error
