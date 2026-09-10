"""Deterministic analytics over typed results (ARCHITECTURE component 9)."""

from kkb_agent.analytics.anomaly import (
    DEFAULT_MINIMUM_CHANGES,
    DEFAULT_THRESHOLD,
    MAD_TO_SIGMA,
    detect_anomalies,
)
from kkb_agent.analytics.association import (
    BASE_LIMITATIONS,
    DEFAULT_MAX_LAG,
    DEFAULT_MINIMUM_PAIRS,
    LAG_CAP,
    associate,
    lagged_association,
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
    "BASE_LIMITATIONS",
    "DEFAULT_MAX_LAG",
    "DEFAULT_MINIMUM_CHANGES",
    "DEFAULT_MINIMUM_PAIRS",
    "DEFAULT_THRESHOLD",
    "INDEX_POINT",
    "LAG_CAP",
    "MAD_TO_SIGMA",
    "PERCENT",
    "PERCENTAGE_POINT",
    "absolute_change",
    "associate",
    "detect_anomalies",
    "lagged_association",
    "compare_periods",
    "relative_change",
]
