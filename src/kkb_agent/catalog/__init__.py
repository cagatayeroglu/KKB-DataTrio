"""Offline catalog contracts; retrieval and source adapters are separate tasks."""

from kkb_agent.catalog.normalization import (
    normalize_index_text,
    normalize_query_text,
    normalize_search_text,
)
from kkb_agent.catalog.records import (
    AggregationPolicy,
    CatalogRecord,
    CatalogStatus,
    CoverageRange,
    SourceGroup,
)

__all__ = [
    "AggregationPolicy",
    "CatalogRecord",
    "CatalogStatus",
    "CoverageRange",
    "SourceGroup",
    "normalize_index_text",
    "normalize_query_text",
    "normalize_search_text",
]
