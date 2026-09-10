"""Deterministic analytics over typed results (ARCHITECTURE component 9)."""

from kkb_agent.analytics.anomaly import (
    DEFAULT_MINIMUM_CHANGES,
    DEFAULT_THRESHOLD,
    MAD_TO_SIGMA,
    detect_anomalies,
)
from kkb_agent.analytics.change import (
    INDEX_POINT,
    PERCENT,
    PERCENTAGE_POINT,
    absolute_change,
    compare_periods,
    relative_change,
)

__all__ = [
    "DEFAULT_MINIMUM_CHANGES",
    "DEFAULT_THRESHOLD",
    "INDEX_POINT",
    "MAD_TO_SIGMA",
    "PERCENT",
    "PERCENTAGE_POINT",
    "absolute_change",
    "detect_anomalies",
    "compare_periods",
    "relative_change",
]
