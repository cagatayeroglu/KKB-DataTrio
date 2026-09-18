"""M13-01: source-neutral catalog declarations for future retrieval consumers.

Records describe candidates, not loaded silver series or permission to calculate.
Unknown semantics are valid here. Source text/locators are untrusted metadata,
never interpreted, fetched, normalized or used as an execution instruction.
"""

from datetime import date
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.core.models import ContractModel, NonEmptyText

#: Catalog size bounds. They guard memory against a malformed file, not the
#: catalog's size: a reviewed catalog and a knowledge base grow together, and a
#: bound near today's count (it was 40 with 37 reviewed series) made a fourth
#: added dataset invalidate every turn's catalog.
MAX_CATALOG_SERIES: Final = 10_000
MAX_CATALOG_CONCEPTS: Final = 10_000
MAX_CATALOG_GROUPS: Final = 1_000


class CatalogStatus(StrEnum):
    """Source-declared status; a missing archive label does not imply ACTIVE."""

    UNKNOWN = "unknown"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CoverageRange(ContractModel):
    """Inclusive source coverage, allowing either endpoint to remain unknown."""

    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("Coverage end precedes start")
        return self


class AggregationPolicy(ContractModel):
    """Per-operation source permissions, not an inferred resampling policy.

    None means unknown; False explicitly forbids an operation. A default method
    does not silently grant permission, and missing flags are never filled in.
    """

    default: Aggregation = Aggregation.UNKNOWN
    sum: StrictBool | None = None
    average: StrictBool | None = None
    first: StrictBool | None = None
    last: StrictBool | None = None
    min: StrictBool | None = None
    max: StrictBool | None = None

    @model_validator(mode="after")
    def default_not_forbidden(self) -> Self:
        if self.default is not Aggregation.UNKNOWN and getattr(self, self.default.value) is False:
            raise ValueError("Default aggregation is explicitly forbidden")
        return self


class SourceGroup(ContractModel):
    """Optional discovery context shared by categories, datagroups and bulletins.

    These are original IDs/titles, not source-specific wire keys or inferred
    classifications. Provider and publisher may differ (e.g. a data distributor).
    """

    group_id: NonEmptyText | None = None
    group_title: NonEmptyText | None = None
    category_id: NonEmptyText | None = None
    category_title: NonEmptyText | None = None
    publisher: NonEmptyText | None = None


class CatalogRecord(ContractModel):
    """One identifiable series, with explicit unknowns and no raw payload bag.

    `series_id` is a caller-assigned stable catalog ID, never derived from title.
    `provider` + `source_series_id` preserve the original source identity; for a
    source without one series code, its adapter must supply a documented stable
    composite selector. This model neither creates IDs nor enforces catalog-wide
    uniqueness. `source` traces the metadata/fragment supporting the declaration.

    `labels` retain captions/display metadata; they are not reviewed aliases.
    `sample_values` is a bounded preview (at most 20 scalar values), retaining raw
    strings and missing None without numeric/financial inference. Empty means no
    samples supplied, not an empty source. Consumers use model_dump(mode="json")
    or model_dump_json() for deterministic field order and JSON round-tripping;
    list order, original text and explicit null/unknown fields are preserved.
    """

    series_id: NonEmptyText
    provider: NonEmptyText
    source_series_id: NonEmptyText
    title: NonEmptyText
    source: SourceRef
    description: NonEmptyText | None = None
    labels: tuple[NonEmptyText, ...] = ()
    group: SourceGroup = Field(default_factory=SourceGroup)
    status: CatalogStatus = CatalogStatus.UNKNOWN
    unit: NonEmptyText | None = None
    scale: Scale = Scale.UNKNOWN
    frequency: Frequency = Frequency.UNKNOWN
    weekly_anchor: WeeklyAnchor | None = None
    stock_flow: StockFlow = StockFlow.UNKNOWN
    cumulative: CumulativeKind = CumulativeKind.UNKNOWN
    aggregation: AggregationPolicy = Field(default_factory=AggregationPolicy)
    base_year: StrictInt | None = Field(default=None, ge=1900, le=2100)
    coverage: CoverageRange = Field(default_factory=CoverageRange)
    sample_values: tuple[StrictStr | StrictInt | StrictFloat | None, ...] = Field(
        default=(), max_length=20
    )

    @model_validator(mode="after")
    def anchor_matches_frequency(self) -> Self:
        if self.weekly_anchor is not None and self.frequency not in (
            Frequency.UNKNOWN,
            Frequency.WEEKLY,
        ):
            raise ValueError("A weekly anchor contradicts the declared frequency")
        return self
