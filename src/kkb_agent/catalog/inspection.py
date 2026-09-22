"""Exact reviewed identity and prepared declarations; no observation retrieval."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from kkb_agent.catalog.mappings import (
    Digest,
    ReviewedSeries,
    ReviewedSnapshot,
    series_display_name,
)
from kkb_agent.catalog.records import CatalogRecord, CatalogStatus, CoverageRange
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow, WeeklyAnchor
from kkb_agent.core.models import ContractModel
from kkb_agent.lakehouse.result_evidence import canonical
from kkb_agent.lakehouse.semantics import SeriesSemantics

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

InspectionStatus = Literal[
    "consistent",
    "unknown_identity",
    "not_prepared",
    "archived",
    "unresolved_catalog",
    "invalid_prepared_metadata",
    "metadata_mismatch",
]


class InspectionRefused(ValueError):
    """Safe category/field names, no source text, values or locators."""


def unresolved_read_fields(record: CatalogRecord) -> tuple[str, ...]:
    """Required read semantics; completeness is not identity or availability evidence."""
    unknown = [
        name
        for name, value in (
            ("unit", record.unit),
            ("scale", record.scale.value),
            ("frequency", record.frequency.value),
            ("observation", record.stock_flow.value),
            ("cumulative", record.cumulative.value),
        )
        if value is None or value == "unknown"
    ]
    if record.frequency is Frequency.WEEKLY and record.weekly_anchor is None:
        unknown.append("anchor")
    if record.stock_flow is StockFlow.INDEX and record.base_year is None:
        unknown.append("base_year")
    return tuple(unknown)


class SeriesInspection(ContractModel):
    series_id: str = Field(min_length=1, max_length=200)
    status: InspectionStatus
    snapshot_sha256: Digest
    record_sha256: Digest | None = None
    prepared_metadata_sha256: Digest | None = None
    source_artifact_id: Digest | None = None
    catalog_status: CatalogStatus = CatalogStatus.UNKNOWN
    declared_coverage: CoverageRange = Field(default_factory=CoverageRange)
    unknown_fields: tuple[str, ...] = ()
    optional_unknown_fields: tuple[str, ...] = ()
    mismatch_fields: tuple[str, ...] = ()
    # Metadata consistency is only one prerequisite, never calculation permission.
    calculation_authorized: Literal[False] = False

    def require_consistent(self) -> None:
        if self.status != "consistent":
            # The identity is named: this text is what a refused step hands back to the
            # planner, and "Series inspection refused: unresolved_catalog (cumulative)"
            # told it neither which series had been refused nor that another catalogue
            # candidate would do (live 2026-09-21, nine minutes and no recovery).
            raise InspectionRefused(
                f"Series inspection refused for {self.series_id!r}: "
                + self.status
                + (
                    " (" + ", ".join(self.unknown_fields or self.mismatch_fields) + ")"
                    if self.unknown_fields or self.mismatch_fields
                    else ""
                )
            )

    def evidence(self) -> str:
        """Local receipt, no description/locator/observations and no inferred facts."""
        self.require_consistent()
        return canonical({"kind": "prepared_series_inspection_v1", **self.model_dump(mode="json")})


class PreparedSeriesInspector:
    """Operator-owned immutable reviewed snapshot, checked against the actual connection.

    Construction takes reviewed configuration, never model-supplied metadata.
    Each lookup re-reads declarations; no stale success cache or network fallback.
    Lakehouse's single-owner connection requirement remains in force.
    """

    def __init__(
        self,
        snapshot: ReviewedSnapshot,
        *,
        allow_archived: bool = False,
        late: Callable[[str], ReviewedSeries | None] | None = None,
    ):
        if type(allow_archived) is not bool:
            raise TypeError("allow_archived must be an operator boolean")
        self._snapshot = ReviewedSnapshot.model_validate(snapshot.model_dump(mode="json"))
        self._series = {s.record.series_id: s for s in self._snapshot.series}
        self._allow_archived = allow_archived
        # Operator wiring (DEC-177): entries a source's own directory listed after this
        # snapshot was built, in this very turn. Never model-supplied metadata.
        self._late = late

    def why_unread(self, series_id: str) -> str | None:
        """Why a series this inspector refused has no stored values; nothing is fetched here."""
        return None

    def name_of(self, series_id: str) -> str | None:
        """What a series is, from its catalogue entry alone; None for an unknown identity."""
        selected = self._series.get(series_id)
        if selected is None and self._late is not None:
            selected = self._late(series_id)
        return series_display_name(selected) if selected is not None else None

    def inspect(self, connection: DuckDBPyConnection, series_id: str) -> SeriesInspection:
        if (
            not isinstance(series_id, str)
            or not 1 <= len(series_id) <= 200
            or any(ord(c) < 32 or ord(c) == 127 for c in series_id)
        ):
            raise InspectionRefused("Series inspection refused: invalid_identity")
        result = SeriesInspection(
            series_id=series_id,
            status="unknown_identity",
            snapshot_sha256=self._snapshot.content_sha256,
        )
        selected = self._series.get(series_id)
        if selected is None and self._late is not None:
            selected = self._late(series_id)
        if selected is None:
            return result
        record = selected.record
        result.record_sha256 = hashlib.sha256(
            canonical(selected.model_dump(mode="json")).encode()
        ).hexdigest()
        result.catalog_status = record.status
        result.declared_coverage = record.coverage.model_copy(deep=True)
        result.optional_unknown_fields = tuple(
            name
            for name, unknown in (
                ("aggregation", record.aggregation.default is Aggregation.UNKNOWN),
                ("archive_status", record.status is CatalogStatus.UNKNOWN),
                ("coverage_start", record.coverage.start is None),
                ("coverage_end", record.coverage.end is None),
            )
            if unknown
        )
        if record.status is CatalogStatus.ARCHIVED and not self._allow_archived:
            result.status = "archived"
            return result
        expected = {
            "unit": record.unit,
            "scale": record.scale.value,
            "frequency": record.frequency.value,
            "observation": record.stock_flow.value,
            "cumulative": record.cumulative.value,
        }
        unknown = unresolved_read_fields(record)
        if unknown:
            result.status = "unresolved_catalog"
            result.unknown_fields = tuple(unknown)
            return result
        row = connection.execute(
            "SELECT s.unit, s.scale, s.frequency, s.observation, s.cumulative, "
            "s.anchor, s.aggregation, s.base_year, s.artifact_id, b.artifact_id "
            "FROM silver_series s LEFT JOIN bronze_artifacts b ON s.artifact_id=b.artifact_id "
            "WHERE s.series_id = ?",
            [series_id],
        ).fetchone()
        if row is None:
            result.status = "not_prepared"
            return result
        try:
            semantics = SeriesSemantics(
                unit=row[0],
                scale=Scale(row[1]),
                frequency=Frequency(row[2]),
                observation=StockFlow(row[3]),
                cumulative=CumulativeKind(row[4]),
                anchor=WeeklyAnchor(row[5]) if row[5] is not None else None,
                aggregation=Aggregation(row[6]),
                base_year=row[7],
            )
            semantics.require_resolved()
            if row[8] != row[9] or row[9] is None:
                raise ValueError("source artifact missing")
            result.source_artifact_id = row[8]
            result.prepared_metadata_sha256 = hashlib.sha256(canonical(row).encode()).hexdigest()
        except (ValueError, TypeError):
            result.status = "invalid_prepared_metadata"
            return result
        actual = dict(zip(expected, row[:5], strict=True))
        mismatch = [name for name, value in expected.items() if value != actual[name]]
        if (record.weekly_anchor.value if record.weekly_anchor is not None else None) != row[5]:
            mismatch.append("anchor")
        if record.base_year is not None and record.base_year != row[7]:
            mismatch.append("base_year")
        if (
            record.aggregation.default is not Aggregation.UNKNOWN
            and record.aggregation.default.value != row[6]
        ) or (row[6] != "unknown" and getattr(record.aggregation, row[6]) is False):
            mismatch.append("aggregation")
        result.mismatch_fields = tuple(mismatch)
        result.status = "metadata_mismatch" if mismatch else "consistent"
        return result
