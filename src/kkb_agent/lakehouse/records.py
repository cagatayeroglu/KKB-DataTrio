"""Value types shared across the lakehouse layers.

Kept free of dependencies on the store, the graph or any layer, so modules that
all speak in observations do not have to import each other to say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Observation:
    """One published value for one period.

    `value` is None for a genuinely missing observation. It is never a stand-in
    for zero, and nothing in this package fills it forward.
    """

    period_start: date
    period_end: date
    value: float | None
