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
from kkb_agent.analytics.granger import (
    GRANGER_LIMITATIONS,
    ROWS_PER_COEFFICIENT,
    granger_precedence,
)

__all__ = [
    "BASE_LIMITATIONS",
    "DEFAULT_MAX_LAG",
    "DEFAULT_MINIMUM_CHANGES",
    "DEFAULT_MINIMUM_PAIRS",
    "DEFAULT_THRESHOLD",
    "GRANGER_LIMITATIONS",
    "INDEX_POINT",
    "LAG_CAP",
    "MAD_TO_SIGMA",
    "PERCENT",
    "PERCENTAGE_POINT",
    "ROWS_PER_COEFFICIENT",
    "absolute_change",
    "associate",
    "detect_anomalies",
    "granger_precedence",
    "lagged_association",
    "compare_periods",
    "relative_change",
]
