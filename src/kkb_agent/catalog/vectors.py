"""Versioned catalog representations; no embedding calls or inferred input policy."""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StringConstraints, model_validator

from kkb_agent.catalog.mappings import ReviewedSnapshot
from kkb_agent.catalog.normalization import normalize_index_text
from kkb_agent.core.models import ContractModel

DIMENSION = 4096
TEXT_RECIPE: Literal["catalog-description-alias-semantics-v1"] = (
    "catalog-description-alias-semantics-v1"
)
MAX_TEXT_BYTES = 8192
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
PolicyId = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
]
Vector = Annotated[
    tuple[StrictFloat, ...], Field(min_length=DIMENSION, max_length=DIMENSION, repr=False)
]


class VectorProfile(ContractModel):
    """Operator declaration, not proof that a policy has passed live acceptance.

    No default query/passage prefix is assumed. The later embedding boundary must
    implement and review this explicit policy identifier for both kinds of input.
    Fixture vectors cannot be presented as measured Kloudeks retrieval quality.
    """

    model: Literal["kkbhackathon2026/Qwen3-Embedding-8B"]
    dimension: Literal[4096]
    input_policy_id: PolicyId
    origin: Literal["offline_fixture", "kloudeks"]
    text_recipe: Literal["catalog-description-alias-semantics-v1"] = TEXT_RECIPE

    def fingerprint(self) -> str:
        checked = VectorProfile.model_validate(self)
        return hashlib.sha256(checked.model_dump_json().encode()).hexdigest()


class SeriesVector(ContractModel):
    series_id: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1024)]
    text_sha256: Digest
    values: Vector

    @model_validator(mode="after")
    def finite_nonzero(self) -> Self:
        normalized_vector(self.values)
        return self


class CatalogVectors(ContractModel):
    snapshot_sha256: Digest
    profile: VectorProfile
    vectors: tuple[SeriesVector, ...] = Field(min_length=1, max_length=40, repr=False)

    @model_validator(mode="after")
    def unique_identities(self) -> Self:
        ids = [v.series_id for v in self.vectors]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate catalog vector identity")
        return self


class QueryVector(ContractModel):
    profile: VectorProfile
    values: Vector

    @model_validator(mode="after")
    def finite_nonzero(self) -> Self:
        normalized_vector(self.values)
        return self


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    series_id: str
    text: str
    text_sha256: str
    concept_ids: tuple[str, ...]
    family_ids: tuple[str, ...]


def catalog_documents(snapshot: ReviewedSnapshot) -> tuple[CatalogDocument, ...]:
    """Only reviewed candidate text and declared semantics, never observations.

    UNRESOLVED-only aliases and exclusion notes are not positive catalog records.
    Oversized text is refused instead of silently dropping distinguishing facts.
    """
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    documents = []
    for item in sorted(snapshot.series, key=lambda s: s.record.series_id):
        record = item.record
        concepts = [c for c in snapshot.concepts if record.series_id in c.candidate_series_ids]
        parts = [
            record.title,
            record.description or "",
            *record.labels,
            record.group.group_title or "",
            f"provider {record.provider}; frequency {record.frequency.value}; "
            f"stock_flow {record.stock_flow.value}; rate_basis {item.rate_basis}; "
            f"unit {record.unit or 'unknown'}; scale {record.scale.value}; "
            f"base_year {record.base_year if record.base_year is not None else 'unknown'}; "
            f"geography {item.geography or 'unknown'}; cumulative {record.cumulative.value}",
            *sorted({a.original for c in concepts for a in c.aliases}),
        ]
        text = normalize_index_text("\n".join(parts))
        if not text or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("catalog representation exceeds text budget")
        documents.append(
            CatalogDocument(
                record.series_id,
                text,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                tuple(sorted(c.concept_id for c in concepts)),
                tuple(sorted({f for c in concepts for f in c.family_ids})),
            )
        )
    return tuple(documents)


def normalized_vector(values: tuple[float, ...]) -> tuple[float, ...]:
    """Stable unit length then float32, matching the persisted Arrow vector type."""
    if len(values) != DIMENSION or any(not math.isfinite(v) for v in values):
        raise ValueError("catalog vector must have 4096 finite components")
    largest = max(abs(v) for v in values)
    if largest == 0:
        raise ValueError("zero vector has no cosine direction")
    scaled = [v / largest for v in values]
    norm = math.hypot(*scaled)
    return struct.unpack(
        f"<{DIMENSION}f", struct.pack(f"<{DIMENSION}f", *(v / norm for v in scaled))
    )


def vector_digest(values: tuple[float, ...]) -> str:
    return hashlib.sha256(struct.pack(f"<{DIMENSION}f", *values)).hexdigest()
