"""Offline catalog contracts; retrieval and source adapters are separate tasks."""

from kkb_agent.catalog.records import (
    AggregationPolicy,
    CatalogRecord,
    CatalogStatus,
    CoverageRange,
    SourceGroup,
)

__all__ = ["AggregationPolicy", "CatalogRecord", "CatalogStatus", "CoverageRange", "SourceGroup"]
