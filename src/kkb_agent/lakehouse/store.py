"""The medallion store: an immutable bronze layer and a semantics-gated silver.

Layout under a caller-owned root:

    kkb.duckdb          catalog and observations
    bronze/<sha256>     retrieved payloads, verbatim, never rewritten
    silver/             Parquet exports of the silver tables

Bronze holds what a source actually returned, addressed by the hash of its
bytes, so "what did we receive" is answerable months later. Silver holds series
whose meaning is fully recorded. Gold is not created here; joins and alignment
belong to the tasks that follow.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.lineage import Lineage
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics, check_period

if TYPE_CHECKING:  # pragma: no cover - import cost only
    from duckdb import DuckDBPyConnection

LAYERS = ("bronze", "silver", "gold")
DATABASE_NAME = "kkb.duckdb"

#: The engine capabilities this database never has. DuckDB applies configuration
#: per database rather than per connection, so this is set once at open time and
#: covers model-supplied SQL as well as our own. The pipeline reads and writes
#: files through Python instead, which is why nothing here needs it back.
SANDBOX = {
    "enable_external_access": "false",
    "allow_community_extensions": "false",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze_artifacts (
    artifact_id   TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    locator       TEXT NOT NULL,
    retrieved_at  TIMESTAMPTZ,
    media_type    TEXT NOT NULL,
    byte_count    BIGINT NOT NULL,
    payload_path  TEXT NOT NULL,
    recorded_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS silver_series (
    series_id     TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    artifact_id   TEXT NOT NULL REFERENCES bronze_artifacts(artifact_id),
    unit          TEXT NOT NULL,
    scale         TEXT NOT NULL,
    frequency     TEXT NOT NULL,
    anchor        TEXT,
    observation   TEXT NOT NULL,
    cumulative    TEXT NOT NULL,
    aggregation   TEXT NOT NULL,
    base_year     INTEGER
);

CREATE TABLE IF NOT EXISTS silver_observations (
    series_id     TEXT NOT NULL REFERENCES silver_series(series_id),
    period_start  DATE NOT NULL,
    period_end    DATE NOT NULL,
    value         DOUBLE,
    PRIMARY KEY (series_id, period_end)
);
"""


class LakehouseError(RuntimeError):
    """The store refused an operation that would lose or corrupt provenance."""


@dataclass(frozen=True, slots=True)
class BronzeArtifact:
    artifact_id: str
    payload_path: Path
    byte_count: int
    already_present: bool


@dataclass(frozen=True, slots=True)
class Lakehouse:
    """An open medallion store. Not thread-safe; one connection, one caller."""

    root: Path
    connection: DuckDBPyConnection

    @property
    def bronze(self) -> Path:
        return self.root / "bronze"

    @property
    def silver(self) -> Path:
        return self.root / "silver"

    @property
    def gold(self) -> Path:
        return self.root / "gold"

    @property
    def lineage(self) -> Lineage:
        """Provenance graph over this connection."""
        return Lineage(self.connection)

    # -- bronze ---------------------------------------------------------------

    def record_artifact(
        self,
        payload: bytes,
        *,
        source: SourceRef,
        media_type: str,
        recorded_at: datetime,
    ) -> BronzeArtifact:
        """Store a retrieved payload verbatim under the hash of its bytes.

        Recording the same bytes twice is a no-op that returns the existing
        artifact, so a re-fetch cannot silently change history. Two different
        payloads can never collide on one id, because the id *is* the content.
        """
        if not isinstance(payload, bytes):
            raise TypeError("Bronze stores bytes, not decoded text")
        if recorded_at.tzinfo is None:
            raise LakehouseError("recorded_at must be timezone-aware")
        artifact_id = hashlib.sha256(payload).hexdigest()
        path = self.bronze / artifact_id

        existing = self.connection.execute(
            "SELECT byte_count FROM bronze_artifacts WHERE artifact_id = ?", [artifact_id]
        ).fetchone()
        if existing is not None:
            if not path.exists() or path.stat().st_size != existing[0]:
                raise LakehouseError(f"Bronze payload for {artifact_id[:12]} is missing or altered")
            return BronzeArtifact(artifact_id, path, existing[0], already_present=True)

        self.bronze.mkdir(parents=True, exist_ok=True)
        # Exclusive create: never overwrite an object already in bronze.
        with path.open("xb") as handle:
            handle.write(payload)
        self.connection.execute(
            "INSERT INTO bronze_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                artifact_id,
                source.source_id,
                source.source_type,
                source.locator,
                source.retrieved_at,
                media_type,
                len(payload),
                str(path.relative_to(self.root)),
                recorded_at,
            ],
        )
        return BronzeArtifact(artifact_id, path, len(payload), already_present=False)

    def read_artifact(self, artifact_id: str) -> bytes:
        """Return the stored bytes, verifying they still hash to their id."""
        row = self.connection.execute(
            "SELECT payload_path FROM bronze_artifacts WHERE artifact_id = ?", [artifact_id]
        ).fetchone()
        if row is None:
            raise LakehouseError(f"No bronze artifact {artifact_id[:12]}")
        payload: bytes = (self.root / str(row[0])).read_bytes()
        if hashlib.sha256(payload).hexdigest() != artifact_id:
            raise LakehouseError(
                f"Bronze payload for {artifact_id[:12]} no longer matches its hash"
            )
        return payload

    # -- silver ---------------------------------------------------------------

    def register_series(
        self, series_id: str, *, title: str, semantics: SeriesSemantics, artifact_id: str
    ) -> None:
        """Admit a series to silver, or refuse it for unresolved semantics.

        Re-registering the same series with different semantics is refused: a
        value already stored was validated against the old declaration, and
        changing it underneath would leave rows meaning something else.
        """
        semantics.require_resolved()
        if not series_id.strip() or not title.strip():
            raise LakehouseError("Series id and title must be non-blank")
        if (
            self.connection.execute(
                "SELECT 1 FROM bronze_artifacts WHERE artifact_id = ?", [artifact_id]
            ).fetchone()
            is None
        ):
            raise LakehouseError("A silver series must cite a bronze artifact")

        row = [
            series_id,
            title,
            artifact_id,
            semantics.unit,
            semantics.scale.value,
            semantics.frequency.value,
            semantics.anchor.value if semantics.anchor else None,
            semantics.observation.value,
            semantics.cumulative.value,
            semantics.aggregation.value,
            semantics.base_year,
        ]
        existing = self.connection.execute(
            "SELECT * FROM silver_series WHERE series_id = ?", [series_id]
        ).fetchone()
        if existing is not None:
            if list(existing) != row:
                raise LakehouseError(
                    f"Series {series_id} is already registered with different semantics"
                )
            return
        self.connection.execute(
            "INSERT INTO silver_series VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row
        )

    def semantics_of(self, series_id: str) -> SeriesSemantics:
        row = self.connection.execute(
            "SELECT unit, scale, frequency, anchor, observation, cumulative, aggregation, base_year"
            " FROM silver_series WHERE series_id = ?",
            [series_id],
        ).fetchone()
        if row is None:
            raise LakehouseError(f"No silver series {series_id}")
        unit, scale, frequency, anchor, observation, cumulative, aggregation, base_year = row
        return SeriesSemantics(
            unit=unit,
            scale=Scale(scale),
            frequency=Frequency(frequency),
            anchor=WeeklyAnchor(anchor) if anchor else None,
            observation=StockFlow(observation),
            cumulative=CumulativeKind(cumulative),
            aggregation=Aggregation(aggregation),
            base_year=base_year,
        )

    def append_observations(self, series_id: str, observations: Iterable[Observation]) -> int:
        """Write observations after checking each period against the calendar.

        Nothing is written unless every observation passes, so a rejected batch
        cannot leave a half-loaded series behind.
        """
        semantics = self.semantics_of(series_id)
        rows = []
        seen: set[date] = set()
        for observation in observations:
            check_period(semantics, observation.period_start, observation.period_end)
            if observation.period_end in seen:
                raise LakehouseError(
                    f"{series_id} has two observations for the period ending "
                    f"{observation.period_end.isoformat()}"
                )
            seen.add(observation.period_end)
            rows.append(
                [series_id, observation.period_start, observation.period_end, observation.value]
            )
        if not rows:
            return 0
        self.connection.executemany("INSERT INTO silver_observations VALUES (?, ?, ?, ?)", rows)
        return len(rows)

    def export_silver(self) -> list[Path]:
        """Write the silver tables to Parquet for handover and inspection.

        Written through PyArrow rather than `COPY ... TO`, because the database
        is opened with external access switched off — see `SANDBOX`. Our own
        file I/O goes through Python, so SQL never needs the capability.
        """
        import pyarrow.parquet  # type: ignore[import-untyped]

        self.silver.mkdir(parents=True, exist_ok=True)
        written = []
        # Literal statements rather than an interpolated table name: nothing
        # here comes from outside, and it stays that way by construction.
        exports = {
            "silver_series": "SELECT * FROM silver_series",
            "silver_observations": "SELECT * FROM silver_observations",
        }
        for table, query in exports.items():
            target = self.silver / f"{table}.parquet"
            pyarrow.parquet.write_table(self.connection.execute(query).to_arrow_table(), target)
            written.append(target)
        return written


@contextmanager
def open_lakehouse(root: Path) -> Iterator[Lakehouse]:
    """Open, creating the layout and schema if absent. The root must be a directory."""
    import duckdb

    root = Path(root)
    if root.exists() and not root.is_dir():
        raise LakehouseError(f"Lakehouse root is not a directory: {root}")
    for layer in LAYERS:
        (root / layer).mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(root / DATABASE_NAME), config=dict(SANDBOX))
    try:
        # Imported here because the registry imports this module's schema back.
        from kkb_agent.database import apply_schema

        apply_schema(connection)
        yield Lakehouse(root=root, connection=connection)
    finally:
        connection.close()
