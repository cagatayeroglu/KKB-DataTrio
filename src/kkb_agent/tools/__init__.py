"""Six brief-named tool factories; web_search requires an explicitly injected backend.

No production search adapter or default fake is included (DEC-134).
"""

from kkb_agent.tools.anomaly import AnomalyArguments, make_anomaly_tool
from kkb_agent.tools.causality import CausalityArguments, make_causality_tool
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
from kkb_agent.tools.web_search import (
    BackendHit,
    SearchBackend,
    SearchCandidate,
    SearchCode,
    SearchReply,
    SearchRequest,
    WebSearchOutput,
    make_web_search_tool,
)
from kkb_agent.tools.web_url import (
    WebUrlArguments,
    WebUrlOutput,
    addresses_in,
    make_web_url_tool,
)

__all__ = [
    "BackendHit",
    "SearchBackend",
    "SearchCandidate",
    "SearchCode",
    "SearchReply",
    "SearchRequest",
    "WebSearchOutput",
    "make_web_search_tool",
    "DEFAULT_MAX_ROWS",
    "AnomalyArguments",
    "CausalityArguments",
    "ChangeDetectionArguments",
    "DEFAULT_READABLE",
    "LakehouseArguments",
    "LakehouseOutput",
    "QueryResult",
    "SeriesUnknown",
    "SqlRejected",
    "WebUrlArguments",
    "WebUrlOutput",
    "addresses_in",
    "check_sql",
    "make_anomaly_tool",
    "make_causality_tool",
    "make_change_detection_tool",
    "make_lakehouse_tool",
    "make_web_url_tool",
    "read_series",
    "referenced_tables",
    "run_query",
]
