"""M13-08 reviewed, repository-backed declarations; no retrieval or execution.

A content digest detects changes, not truth or permission. The owning PR reviews
identity/evidence. Callers inject the selected artifact bytes; no URL/path is
opened from aliases or source metadata. M13-09 holdout data is not accepted here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.records import (
    MAX_CATALOG_CONCEPTS,
    MAX_CATALOG_GROUPS,
    MAX_CATALOG_SERIES,
    CatalogRecord,
    CatalogStatus,
)
from kkb_agent.core.models import ContractModel

Text = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1024)]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{40}$")]
#: A memory bound on catalogue bytes, not a catalogue size: the series ceiling is
#: MAX_CATALOG_SERIES. An entry serializes to about two kilobytes. With FinTürk's province
#: cells (DEC-184) the served catalogue measured 16.7 MB against a 16 MiB bound, so one
#: dataset saved by a reader would have refused every turn; the bound now covers
#: MAX_CATALOG_SERIES entries of that size with room to spare.
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


class Evidence(ContractModel):
    evidence_id: Text
    path: Text
    revision: Revision
    file_sha256: Digest
    section: Text


#: Evidence ids of entries a source's own directory lists start with this (DEC-176): such an
#: entry is found and fetched like any other, and was never reviewed one by one.
DIRECTORY_EVIDENCE_PREFIX = "directory:"
SOURCE_GROUP_INFIX = ":group:"


class ReviewedSeries(ContractModel):
    record: CatalogRecord
    evidence_ids: tuple[Text, ...] = Field(min_length=1, max_length=10)
    title_basis: Literal["documented_title", "inventory_description"]
    # RATE alone cannot distinguish new-credit from outstanding-portfolio rates.
    rate_basis: Literal["new_credit", "outstanding_portfolio", "unknown"] = "unknown"
    geography: Text | None = None
    note: Text


class SourceContext(ContractModel):
    """Documented selectors/groups without claiming a resolved series identity."""

    context_id: Text
    evidence_ids: tuple[Text, ...] = Field(min_length=1, max_length=10)
    facts: tuple[Text, ...] = Field(min_length=1, max_length=30)
    unresolved: Text


class Alias(ContractModel):
    original: Text
    normalized: Text

    @model_validator(mode="after")
    def shared_normalization(self) -> Self:
        if not self.normalized.strip() or self.normalized != normalize_search_text(self.original):
            raise ValueError("alias must use the shared nonempty search representation")
        return self


class Concept(ContractModel):
    concept_id: Text
    definition: Text
    aliases: tuple[Alias, ...] = Field(min_length=1, max_length=20)
    candidate_series_ids: tuple[Text, ...] = Field(default=(), max_length=MAX_CATALOG_SERIES)
    resolution: Literal["MAPPED", "PARTIAL", "UNRESOLVED"]
    clarification_required: StrictBool
    conditions: tuple[Text, ...] = Field(min_length=1, max_length=20)
    family_ids: tuple[Text, ...] = Field(default=(), max_length=10)
    evidence_ids: tuple[Text, ...] = Field(min_length=1, max_length=10)
    context_ids: tuple[Text, ...] = Field(default=(), max_length=10)
    exclusions: tuple[Text, ...] = Field(min_length=1, max_length=20)
    unresolved: tuple[Text, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def resolution_is_honest(self) -> Self:
        if bool(self.candidate_series_ids) != (self.resolution != "UNRESOLVED"):
            raise ValueError("resolution contradicts candidate identities")
        if bool(self.unresolved) != (self.resolution != "MAPPED"):
            raise ValueError("unresolved mappings must retain their missing information")
        if (
            len(self.candidate_series_ids) != 1 or self.unresolved
        ) and not self.clarification_required:
            raise ValueError("ambiguous or unresolved concept requires clarification")
        return self


class ConceptFamily(ContractModel):
    family_id: Text
    label: Text
    rationale: Text
    evidence_ids: tuple[Text, ...] = Field(min_length=1, max_length=10)
    excluded_series_ids: tuple[Text, ...] = Field(default=(), max_length=MAX_CATALOG_SERIES)
    exclusions: tuple[Text, ...] = Field(min_length=1, max_length=20)


def _unique(values: list[str]) -> set[str]:
    if len(values) != len(set(values)):
        raise ValueError("duplicate snapshot identity/reference")
    return set(values)


class ReviewedSnapshot(ContractModel):
    schema_version: Literal[1]
    snapshot_version: Text
    purpose: Literal["demo_development"]
    review_owner: Text
    review_date: date
    review_revision: Text
    review_pr: Text
    review_note: Text
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=MAX_CATALOG_GROUPS)
    series: tuple[ReviewedSeries, ...] = Field(min_length=1, max_length=MAX_CATALOG_SERIES)
    contexts: tuple[SourceContext, ...] = Field(default=(), max_length=MAX_CATALOG_GROUPS)
    concepts: tuple[Concept, ...] = Field(min_length=1, max_length=MAX_CATALOG_CONCEPTS)
    families: tuple[ConceptFamily, ...] = Field(min_length=1, max_length=MAX_CATALOG_GROUPS)
    content_sha256: Digest

    def canonical_bytes(self) -> bytes:
        """Hash all declarations/review metadata, excluding only the digest itself."""
        return json.dumps(
            self.model_dump(mode="json", exclude={"content_sha256"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    @model_validator(mode="after")
    def references_and_digest(self) -> Self:
        evidence = _unique([e.evidence_id for e in self.evidence])
        series = _unique([s.record.series_id for s in self.series])
        pairs = [(s.record.provider, s.record.source_series_id) for s in self.series]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate original source identity")
        contexts = _unique([c.context_id for c in self.contexts])
        _unique([c.concept_id for c in self.concepts])
        families = _unique([f.family_id for f in self.families])
        referenced: tuple[ReviewedSeries | SourceContext | Concept | ConceptFamily, ...] = (
            *self.series,
            *self.contexts,
            *self.concepts,
            *self.families,
        )
        for item in referenced:
            if not _unique(list(item.evidence_ids)) <= evidence:
                raise ValueError("unknown evidence reference")
        for concept in self.concepts:
            if not _unique(list(concept.candidate_series_ids)) <= series:
                raise ValueError("unknown candidate identity")
            if not _unique(list(concept.context_ids)) <= contexts:
                raise ValueError("unknown context reference")
            if not _unique(list(concept.family_ids)) <= families:
                raise ValueError("unknown concept family")
            _unique([a.original for a in concept.aliases])
        for family in self.families:
            excluded = _unique(list(family.excluded_series_ids))
            if not excluded <= series:
                raise ValueError("unknown excluded identity")
            members = [c for c in self.concepts if family.family_id in c.family_ids]
            if not members or any(excluded.intersection(c.candidate_series_ids) for c in members):
                raise ValueError("empty family or excluded identity in family membership")
        for item in self.series:
            identity = " ".join(
                (item.record.series_id, item.record.provider, item.record.source_series_id)
            )
            if any(marker in identity.casefold() for marker in ("synth", "fixture", "example")):
                raise ValueError("synthetic identity is not a reviewed real series")
        if hashlib.sha256(self.canonical_bytes()).hexdigest() != self.content_sha256:
            raise ValueError("snapshot digest mismatch")
        return self


class AliasMatch(ContractModel):
    """Exact reviewed alias lookup only; not catalog_search/ranking/selection."""

    status: Literal["MATCH", "NO_MATCH"]
    concept_ids: tuple[str, ...]
    candidate_series_ids: tuple[str, ...]
    unresolved_concept_ids: tuple[str, ...]
    clarification_required: bool
    excluded_archived_ids: tuple[str, ...]


def lookup_alias(
    snapshot: ReviewedSnapshot, query: str, *, include_archived: bool = False
) -> AliasMatch:
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    if not isinstance(query, str) or len(query) > 512:
        raise ValueError("alias query must be bounded text")
    if type(include_archived) is not bool:
        raise ValueError("archive inclusion must be an explicit boolean")
    key = normalize_search_text(query)
    matches = [c for c in snapshot.concepts if any(a.normalized == key for a in c.aliases)]
    candidates = {s for c in matches for s in c.candidate_series_ids}
    archived = {
        s.record.series_id for s in snapshot.series if s.record.status is CatalogStatus.ARCHIVED
    }
    excluded = candidates & archived if not include_archived else set()
    return AliasMatch(
        status="MATCH" if matches else "NO_MATCH",
        concept_ids=tuple(sorted(c.concept_id for c in matches)),
        candidate_series_ids=tuple(sorted(candidates - excluded)),
        unresolved_concept_ids=tuple(sorted(c.concept_id for c in matches if c.unresolved)),
        clarification_required=bool(matches)
        and (len(matches) > 1 or any(c.clarification_required for c in matches) or bool(excluded)),
        excluded_archived_ids=tuple(sorted(excluded)),
    )


def is_listed_series(series: ReviewedSeries) -> bool:
    """True for an entry of the sources' own directory, false for a reviewed or user entry."""
    return any(item.startswith(DIRECTORY_EVIDENCE_PREFIX) for item in series.evidence_ids)


def is_source_group(series: ReviewedSeries) -> bool:
    """True for a directory entry that stands for a source's datagroup, not for a series.

    Any source may list such containers as `<PROVIDER>:group:<code>`. Search finds them by
    meaning and ranks them apart from series; `catalog.expansion` opens them into series.
    """
    return is_listed_series(series) and SOURCE_GROUP_INFIX in series.record.series_id


def load_reviewed_snapshot(data: bytes) -> ReviewedSnapshot:
    if not isinstance(data, bytes) or len(data) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot must be bounded bytes")
    return ReviewedSnapshot.model_validate_json(data)


def series_display_name(series: ReviewedSeries) -> str:
    """What a series is, in one line, from its catalog record alone.

    Every series a turn can compute on has a catalog record — reviewed, or a
    knowledge-base entry the overlay turned into one — so this one function
    names prepared, fetched and user-declared series alike, with no list kept
    by hand. Labels carry what a title leaves out (the three BDDK housing
    components share one source title and differ only by their TP/YP/TOTAL
    label).
    """
    record = series.record
    labels = f" [{', '.join(record.labels)}]" if record.labels else ""
    place = f", {series.geography}" if series.geography else ""
    return (
        f"{record.provider}: {record.title}{labels}{place}; "
        f"{record.unit or 'unknown unit'} {record.scale.value}, "
        f"{record.frequency.value}, {record.stock_flow.value}"
    )


def series_display_names(snapshot: ReviewedSnapshot) -> dict[str, str]:
    """`series_display_name` for every series of a (possibly overlaid) catalog."""
    return {item.record.series_id: series_display_name(item) for item in snapshot.series}
