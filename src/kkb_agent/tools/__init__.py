"""The six brief-named tools. `lakehouse`, `change_detection` and `anomaly` exist."""

from kkb_agent.tools.anomaly import AnomalyArguments, make_anomaly_tool
from kkb_agent.tools.change_detection import (
    ChangeDetectionArguments,
    SeriesUnknown,
    make_change_detection_tool,
    read_series,
)
from kkb_agent.tools.lakehouse import (
    DEFAULT_MAX_ROWS,
    DEFAULT_READABLE,
    LakehouseArguments,
    LakehouseOutput,
    QueryResult,
    SqlRejected,
    check_sql,
    make_lakehouse_tool,
    referenced_tables,
    run_query,
)

__all__ = [
    "DEFAULT_MAX_ROWS",
    "AnomalyArguments",
    "ChangeDetectionArguments",
    "DEFAULT_READABLE",
    "LakehouseArguments",
    "LakehouseOutput",
    "QueryResult",
    "SeriesUnknown",
    "SqlRejected",
    "check_sql",
    "make_anomaly_tool",
    "make_change_detection_tool",
    "make_lakehouse_tool",
    "read_series",
    "referenced_tables",
    "run_query",
]
