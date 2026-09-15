"""Immutable local LanceDB catalog generations; no source/model/network routing.

Only operator-owned directories produced here are supported. These are not an
upload format. Hashes detect mismatches, not a malicious operator rewriting both
data and manifest. Retrieval never confers financial correctness or authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

import pyarrow as pa  # type: ignore[import-untyped]  # Arrow data validated below.
from lancedb.db import LanceDBConnection
from lancedb.query import LanceVectorQueryBuilder
from lancedb.table import LanceTable
from pydantic import Field, StrictInt, StrictStr

from kkb_agent.catalog.mappings import ReviewedSnapshot
from kkb_agent.catalog.vectors import (
    DIMENSION,
    CatalogVectors,
    Digest,
    QueryVector,
    Vector,
    VectorProfile,
    catalog_documents,
    normalized_vector,
    vector_digest,
)
from kkb_agent.core.models import ContractModel

MANIFEST = "catalog-manifest.json"
MAX_MANIFEST_BYTES = 16 * 1024
TIMEOUT = timedelta(seconds=10)


class CatalogIndexError(ValueError):
    """A fixed category, without local paths, queries or vector contents."""


class _Manifest(ContractModel):
    schema_version: Literal[1] = 1
    snapshot_sha256: Digest
    snapshot_version: StrictStr
    profile: VectorProfile
    row_count: Annotated[StrictInt, Field(ge=1, le=40)]
    rows_sha256: Digest


class _Row(ContractModel):
    catalog_ordinal: Annotated[StrictInt, Field(ge=0, lt=40)]
    series_id: StrictStr
    catalog_text: StrictStr
    text_sha256: Digest
    concept_ids: tuple[StrictStr, ...]
    family_ids: tuple[StrictStr, ...]
    vector_sha256: Digest
    vector: Vector


@dataclass(frozen=True, slots=True)
class DenseHit:
    series_id: str
    rank: int
    cosine_distance: float


def _local_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise CatalogIndexError("INDEX_LOCAL_ABSOLUTE_PATH_REQUIRED")
    # UNC shares and URI-like paths must never become remote object-store input.
    if root.as_posix().startswith("//") or root.is_symlink():
        raise CatalogIndexError("INDEX_LOCAL_ABSOLUTE_PATH_REQUIRED")
    resolved = root.resolve()
    if resolved.as_posix().startswith("//"):
        raise CatalogIndexError("INDEX_LOCAL_ABSOLUTE_PATH_REQUIRED")
    return resolved


def _schema() -> pa.Schema:
    return pa.schema(
        [
            ("catalog_ordinal", pa.int32()),
            ("series_id", pa.string()),
            ("catalog_text", pa.string()),
            ("text_sha256", pa.string()),
            ("concept_ids", pa.list_(pa.string())),
            ("family_ids", pa.list_(pa.string())),
            ("vector_sha256", pa.string()),
            ("vector", pa.list_(pa.float32(), DIMENSION)),
        ]
    )


def _rows_digest(rows: list[_Row]) -> str:
    # Vector byte digests are included, avoiding large JSON float serialization.
    payload = [row.model_dump(mode="json", exclude={"vector"}) for row in rows]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_catalog_index(root: Path, snapshot: ReviewedSnapshot, vectors: CatalogVectors) -> None:
    """Write a fresh generation; manifest is published last, existing roots refused.

    A failed build can leave an incomplete operator directory. It cannot be opened
    by this API; retry into another fresh directory after investigating the error.
    Never overwrite an earlier generation or delete a caller's data on failure.
    """
    root = _local_root(root)
    snapshot = ReviewedSnapshot.model_validate(snapshot)
    vectors = CatalogVectors.model_validate(vectors)
    documents = catalog_documents(snapshot)
    by_id = {v.series_id: v for v in vectors.vectors}
    if vectors.snapshot_sha256 != snapshot.content_sha256 or set(by_id) != {
        d.series_id for d in documents
    }:
        raise CatalogIndexError("INDEX_SNAPSHOT_OR_IDENTITIES_MISMATCH")
    rows = []
    for ordinal, doc in enumerate(documents):
        supplied = by_id[doc.series_id]
        if supplied.text_sha256 != doc.text_sha256:
            raise CatalogIndexError("INDEX_TEXT_MISMATCH")
        normalized = normalized_vector(supplied.values)
        rows.append(
            _Row(
                catalog_ordinal=ordinal,
                series_id=doc.series_id,
                catalog_text=doc.text,
                text_sha256=doc.text_sha256,
                concept_ids=doc.concept_ids,
                family_ids=doc.family_ids,
                vector_sha256=vector_digest(normalized),
                vector=normalized,
            )
        )
    manifest = _Manifest(
        snapshot_sha256=snapshot.content_sha256,
        snapshot_version=snapshot.snapshot_version,
        profile=vectors.profile,
        row_count=len(rows),
        rows_sha256=_rows_digest(rows),
    )
    try:
        root.mkdir(parents=True, exist_ok=False)
    except OSError:
        raise CatalogIndexError("INDEX_NEW_LOCAL_DIRECTORY_REQUIRED") from None
    try:
        # Direct local connection class; never lancedb.connect's remote dispatch.
        db = LanceDBConnection(root)
        table = db.create_table(
            "catalog",
            data=pa.Table.from_pylist([r.model_dump() for r in rows], schema=_schema()),
            mode="create",
            on_bad_vectors="error",
        )
        if table.count_rows() != len(rows):
            raise CatalogIndexError("INDEX_BUILD_INCOMPLETE")
        # Exclusive file creation: readers reject missing, partial or invalid JSON.
        with (root / MANIFEST).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(manifest.model_dump_json())
    except Exception:
        raise CatalogIndexError("INDEX_BUILD_INCOMPLETE") from None


@dataclass(frozen=True, slots=True)
class LocalCatalogIndex:
    """A checked version-1 table, with immutable operator-selected eligibility IDs."""

    _table: LanceTable
    _snapshot: ReviewedSnapshot
    _profile: VectorProfile
    _ordinals: dict[str, int]

    @property
    def snapshot_sha256(self) -> str:
        return self._snapshot.content_sha256

    @property
    def profile(self) -> VectorProfile:
        return VectorProfile.model_validate(self._profile)

    @classmethod
    def open(
        cls, root: Path, snapshot: ReviewedSnapshot, profile: VectorProfile
    ) -> LocalCatalogIndex:
        root = _local_root(root)
        snapshot = ReviewedSnapshot.model_validate(snapshot)
        profile = VectorProfile.model_validate(profile)
        try:
            with (root / MANIFEST).open("rb") as stream:
                raw = stream.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise CatalogIndexError("INDEX_MANIFEST_INVALID")
            manifest = _Manifest.model_validate_json(raw)
        except Exception:
            raise CatalogIndexError("INDEX_MANIFEST_INVALID") from None
        if (
            manifest.snapshot_sha256 != snapshot.content_sha256
            or manifest.snapshot_version != snapshot.snapshot_version
            or manifest.profile != profile
        ):
            raise CatalogIndexError("INDEX_SNAPSHOT_OR_PROFILE_MISMATCH")
        try:
            db = LanceDBConnection(root)
            table = db.open_table("catalog", version=1)
            if table.count_rows() != manifest.row_count or not table.schema.equals(
                _schema(), check_metadata=True
            ):
                raise CatalogIndexError("INDEX_CONTENT_INVALID")
            # At most 40 records. Bounded materialization detects changes before search.
            rows = [
                _Row.model_validate(row)
                for row in table.search().limit(41).to_list(timeout=TIMEOUT)
            ]
            rows.sort(key=lambda r: r.catalog_ordinal)
            if len(rows) != manifest.row_count or _rows_digest(rows) != manifest.rows_sha256:
                raise CatalogIndexError("INDEX_CONTENT_INVALID")
            documents = catalog_documents(snapshot)
            if len(documents) != len(rows):
                raise CatalogIndexError("INDEX_CONTENT_INVALID")
            for ordinal, (row, doc) in enumerate(zip(rows, documents, strict=True)):
                if (
                    row.catalog_ordinal != ordinal
                    or row.series_id != doc.series_id
                    or row.catalog_text != doc.text
                    or row.text_sha256 != doc.text_sha256
                    or row.concept_ids != doc.concept_ids
                    or row.family_ids != doc.family_ids
                    or vector_digest(row.vector) != row.vector_sha256
                    or not all(math.isfinite(v) for v in row.vector)
                    or not math.isclose(math.hypot(*row.vector), 1.0, abs_tol=1e-6)
                ):
                    raise CatalogIndexError("INDEX_CONTENT_INVALID")
        except Exception:
            raise CatalogIndexError("INDEX_CONTENT_INVALID") from None
        return cls(table, snapshot, profile, {r.series_id: r.catalog_ordinal for r in rows})

    def search(
        self, query: QueryVector, *, eligible_ids: frozenset[str], limit: int = 10
    ) -> tuple[DenseHit, ...]:
        """Search only caller-reviewed eligibility, before top-k; no SQL text input.

        Eligibility must be resolved outside the index (archive, provider, native
        frequency, alias/family policy). This API cannot select meaning or invent
        a no-match threshold. Even the closest vector is only a candidate.
        """
        query = QueryVector.model_validate(query)
        if query.profile != self._profile:
            raise CatalogIndexError("INDEX_QUERY_PROFILE_MISMATCH")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise CatalogIndexError("INDEX_RESULT_LIMIT_INVALID")
        if not isinstance(eligible_ids, frozenset) or not eligible_ids <= self._ordinals.keys():
            raise CatalogIndexError("INDEX_ELIGIBILITY_INVALID")
        if not eligible_ids:
            return ()
        # Numeric ordinals come from the checked table, never interpolated user text.
        ordinals = ",".join(str(self._ordinals[sid]) for sid in sorted(eligible_ids))
        try:
            builder = self._table.search(
                list(normalized_vector(query.values)),
                vector_column_name="vector",
                query_type="vector",
            )
            if not isinstance(builder, LanceVectorQueryBuilder):
                raise CatalogIndexError("INDEX_SEARCH_FAILED")
            found = (
                builder.distance_type("cosine")
                .bypass_vector_index()
                .where(f"catalog_ordinal IN ({ordinals})", prefilter=True)
                .select(["series_id", "_distance"])
                .limit(len(eligible_ids))
                .to_list(timeout=TIMEOUT)
            )
            ranked: list[tuple[str, float]] = []
            for row in found:
                sid, distance = row["series_id"], row["_distance"]
                if (
                    not isinstance(sid, str)
                    or sid not in eligible_ids
                    or not isinstance(distance, float)
                    or not math.isfinite(distance)
                    or not -1e-6 <= distance <= 2.000001
                ):
                    raise CatalogIndexError("INDEX_SEARCH_FAILED")
                ranked.append((sid, distance))
            if len(ranked) != len(eligible_ids) or len({sid for sid, _ in ranked}) != len(ranked):
                raise CatalogIndexError("INDEX_SEARCH_FAILED")
        except Exception:
            raise CatalogIndexError("INDEX_SEARCH_FAILED") from None
        ranked.sort(key=lambda item: (item[1], item[0]))
        return tuple(
            DenseHit(sid, rank + 1, distance) for rank, (sid, distance) in enumerate(ranked[:limit])
        )
