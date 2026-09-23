"""The editable knowledge base: what a person adds, changes or retires (DEC-157).

The reviewed catalog and the prepared pool are evidence: content-hashed, read
by the inspector, bound to the dense index. Editing them in place would make
every earlier answer's provenance point at something that changed underneath
it. So nothing here edits them. The knowledge base is a separate, append-only
record of two kinds of entry:

* **User datasets** — a series a person supplies (from an uploaded table or
  typed in) together with the meaning they *declare*: unit, scale, frequency,
  stock or flow, cumulative kind. Every change is a new version with its own
  series id (`USER:<slug>.v<N>`), because a stored batch is immutable and an
  earlier answer must keep pointing at the numbers it used.
* **Series notes** — for a reviewed series: archive or restore it, add search
  aliases, keep a note. The reviewed record itself is never rewritten.

"Delete" is archiving: the entry leaves discovery and computation, its history
stays, and it can be restored. Nothing is destroyed, because evidence that an
old answer used must still be readable.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final, Literal

from kkb_agent.catalog.records import MAX_CATALOG_SERIES
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow, WeeklyAnchor
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics, check_period

DATABASE_NAME: Final = "knowledge.sqlite"
PROVIDER: Final = "USER"
SLUG = re.compile(r"^[a-z][a-z0-9_]{2,39}\Z")
#: Words the reviewed-snapshot contract refuses in a real series identity.
FORBIDDEN_WORDS: Final = ("synth", "fixture", "example")
MAX_OBSERVATIONS: Final = 5000
MAX_ALIASES: Final = 10
MAX_TEXT: Final = 1000
#: Active datasets share the catalog's series bound with the reviewed series;
#: the half left to them is a guard, not a product limit.
MAX_ACTIVE_DATASETS: Final = MAX_CATALOG_SERIES // 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_datasets (
    slug        TEXT NOT NULL,
    version     INTEGER NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    author      TEXT,
    PRIMARY KEY (slug, version)
);
CREATE TABLE IF NOT EXISTS kb_series (
    series_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    archived    INTEGER NOT NULL,
    aliases     TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL,
    author      TEXT,
    PRIMARY KEY (series_id, version)
);
"""


class KnowledgeError(ValueError):
    """A refused edit; the message is a fixed, safe category."""


Status = Literal["active", "archived"]
SourceKind = Literal["upload", "manual"]


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """One version of a user dataset: declared meaning plus the numbers it carries."""

    slug: str
    version: int
    title: str
    unit: str
    scale: Scale
    frequency: Frequency
    stock_flow: StockFlow
    cumulative: CumulativeKind
    aggregation: Aggregation
    observations: tuple[Observation, ...]
    source_kind: SourceKind
    status: Status = "active"
    description: str | None = None
    base_year: int | None = None
    aliases: tuple[str, ...] = ()
    source_sha256: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    author: str | None = None
    #: The weekday a weekly period ends on; required for, and only for, weekly data.
    anchor: WeeklyAnchor | None = None
    #: Where the numbers were read, as pairs: the address (scheme, host and path) and
    #: when it was read, the document's media type, the sheet, page and table, and the
    #: period and value columns. Empty for a dataset typed into the form. Part of what
    #: a version says, so it is versioned with the numbers it describes.
    provenance: tuple[tuple[str, str], ...] = ()

    @property
    def series_id(self) -> str:
        return f"{PROVIDER}:{self.slug}.v{self.version}"

    def semantics(self) -> SeriesSemantics:
        return SeriesSemantics(
            unit=self.unit,
            scale=self.scale,
            frequency=self.frequency,
            observation=self.stock_flow,
            cumulative=self.cumulative,
            aggregation=self.aggregation,
            base_year=self.base_year,
            anchor=self.anchor,
        )

    def content_sha256(self) -> str:
        """Identity of what this version says, independent of when it was said."""
        return hashlib.sha256(
            json.dumps(_body(self), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class SeriesNote:
    """One version of what a person said about a reviewed series."""

    series_id: str
    version: int
    archived: bool
    aliases: tuple[str, ...] = ()
    note: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    author: str | None = None


def _body(item: DatasetVersion) -> dict[str, object]:
    return {
        "title": item.title,
        "description": item.description,
        "unit": item.unit,
        "scale": item.scale.value,
        "frequency": item.frequency.value,
        "stock_flow": item.stock_flow.value,
        "cumulative": item.cumulative.value,
        "aggregation": item.aggregation.value,
        "base_year": item.base_year,
        **({"anchor": item.anchor.value} if item.anchor is not None else {}),
        "aliases": list(item.aliases),
        "source_kind": item.source_kind,
        "source_sha256": item.source_sha256,
        # Only when there is one, so every version written before this field existed
        # keeps the identity (`content_sha256`) it was stored and cited under.
        **({"provenance": dict(item.provenance)} if item.provenance else {}),
        "status": item.status,
        "observations": [
            [o.period_start.isoformat(), o.period_end.isoformat(), o.value]
            for o in item.observations
        ],
    }


def _from_body(
    slug: str, version: int, body: dict[str, Any], created: str, author: str | None
) -> DatasetVersion:
    rows = body["observations"]
    base_year = body.get("base_year")
    return DatasetVersion(
        slug=slug,
        version=version,
        title=str(body["title"]),
        description=None if body.get("description") is None else str(body["description"]),
        unit=str(body["unit"]),
        scale=Scale(body["scale"]),
        frequency=Frequency(body["frequency"]),
        stock_flow=StockFlow(body["stock_flow"]),
        cumulative=CumulativeKind(body["cumulative"]),
        aggregation=Aggregation(body["aggregation"]),
        base_year=int(base_year) if isinstance(base_year, int) else None,
        anchor=WeeklyAnchor(body["anchor"]) if body.get("anchor") else None,
        aliases=tuple(str(item) for item in body.get("aliases") or []),
        source_kind="upload" if body.get("source_kind") == "upload" else "manual",
        source_sha256=None if body.get("source_sha256") is None else str(body["source_sha256"]),
        provenance=tuple(
            (str(key), str(value)) for key, value in (body.get("provenance") or {}).items()
        ),
        status="archived" if body.get("status") == "archived" else "active",
        observations=tuple(
            Observation(date.fromisoformat(start), date.fromisoformat(end), value)
            for start, end, value in rows
        ),
        created_at=datetime.fromisoformat(created),
        author=author,
    )


def _clean_aliases(aliases: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for alias in aliases:
        text = " ".join(str(alias).split())
        if not text:
            continue
        if len(text) > 120:
            raise KnowledgeError("alias_too_long")
        if text.casefold() not in {item.casefold() for item in cleaned}:
            cleaned.append(text)
    if len(cleaned) > MAX_ALIASES:
        raise KnowledgeError("too_many_aliases")
    return tuple(cleaned)


def validate_dataset(item: DatasetVersion) -> DatasetVersion:
    """Refuse a dataset whose declared meaning or numbers cannot be stored honestly."""
    if not SLUG.fullmatch(item.slug) or any(word in item.slug for word in FORBIDDEN_WORDS):
        raise KnowledgeError("invalid_slug")
    if not item.title.strip() or len(item.title) > 200:
        raise KnowledgeError("invalid_title")
    if item.description is not None and len(item.description) > MAX_TEXT:
        raise KnowledgeError("description_too_long")
    try:
        semantics = item.semantics()
        semantics.require_resolved()
    except (SemanticsError, ValueError):
        raise KnowledgeError("unresolved_semantics") from None
    if not item.observations:
        raise KnowledgeError("no_observations")
    if len(item.observations) > MAX_OBSERVATIONS:
        raise KnowledgeError("too_many_observations")
    seen: set[date] = set()
    for observation in item.observations:
        if item.source_kind == "manual" and observation.period_end > datetime.now(UTC).date():
            raise KnowledgeError("future_period")
        try:
            check_period(semantics, observation.period_start, observation.period_end)
        except SemanticsError:
            raise KnowledgeError("period_does_not_match_frequency") from None
        if observation.period_end in seen:
            raise KnowledgeError("duplicate_period")
        seen.add(observation.period_end)
        if observation.value is not None and observation.value != observation.value:
            raise KnowledgeError("not_a_number")
    ordered = tuple(sorted(item.observations, key=lambda o: o.period_end))
    return replace(item, aliases=_clean_aliases(item.aliases), observations=ordered)


class KnowledgeStore:
    """Append-only versions in one SQLite file under the state root."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self._path), check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    # -- datasets -------------------------------------------------------------

    def _latest(self, connection: sqlite3.Connection, slug: str) -> DatasetVersion | None:
        row = connection.execute(
            "SELECT * FROM kb_datasets WHERE slug = ? ORDER BY version DESC LIMIT 1", [slug]
        ).fetchone()
        if row is None:
            return None
        return _from_body(
            row["slug"], row["version"], json.loads(row["body"]), row["created_at"], row["author"]
        )

    def save_dataset(self, item: DatasetVersion) -> DatasetVersion:
        """Store `item` as the next version of its slug; the caller's version is ignored."""
        item = validate_dataset(item)
        with self._write() as connection:
            latest = self._latest(connection, item.slug)
            if latest is None and item.status == "active":
                active = sum(
                    1 for entry in self._latest_all(connection) if entry.status == "active"
                )
                if active >= MAX_ACTIVE_DATASETS:
                    raise KnowledgeError("too_many_datasets")
            stored = replace(
                item,
                version=(latest.version if latest is not None else 0) + 1,
                created_at=datetime.now(UTC),
            )
            if latest is not None and latest.content_sha256() == stored.content_sha256():
                return latest  # Saying the same thing again is not a new version.
            connection.execute(
                "INSERT INTO kb_datasets VALUES (?, ?, ?, ?, ?)",
                [
                    stored.slug,
                    stored.version,
                    json.dumps(_body(stored), ensure_ascii=False),
                    stored.created_at.isoformat(),
                    stored.author,
                ],
            )
        return stored

    def set_dataset_status(self, slug: str, status: Status, author: str | None) -> DatasetVersion:
        """Archive ("delete") or restore: a new version, never a removed row."""
        with self._lock:
            latest = self._latest(self._connection, slug)
        if latest is None:
            raise KnowledgeError("not_found")
        if latest.status == status:
            return latest
        return self.save_dataset(replace(latest, status=status, author=author))

    def _latest_all(self, connection: sqlite3.Connection) -> list[DatasetVersion]:
        rows = connection.execute(
            "SELECT d.* FROM kb_datasets d JOIN (SELECT slug, max(version) AS version"
            " FROM kb_datasets GROUP BY slug) m ON d.slug = m.slug AND d.version = m.version"
            " ORDER BY d.slug"
        ).fetchall()
        return [
            _from_body(r["slug"], r["version"], json.loads(r["body"]), r["created_at"], r["author"])
            for r in rows
        ]

    def datasets(self, *, include_archived: bool = True) -> list[DatasetVersion]:
        with self._lock:
            found = self._latest_all(self._connection)
        return [item for item in found if include_archived or item.status == "active"]

    def dataset(self, slug: str, version: int | None = None) -> DatasetVersion | None:
        with self._lock:
            if version is None:
                return self._latest(self._connection, slug)
            row = self._connection.execute(
                "SELECT * FROM kb_datasets WHERE slug = ? AND version = ?", [slug, version]
            ).fetchone()
        if row is None:
            return None
        return _from_body(
            row["slug"], row["version"], json.loads(row["body"]), row["created_at"], row["author"]
        )

    def dataset_history(self, slug: str) -> list[DatasetVersion]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM kb_datasets WHERE slug = ? ORDER BY version", [slug]
            ).fetchall()
        return [
            _from_body(r["slug"], r["version"], json.loads(r["body"]), r["created_at"], r["author"])
            for r in rows
        ]

    # -- notes on reviewed series --------------------------------------------

    def annotate(
        self,
        series_id: str,
        *,
        archived: bool,
        aliases: Sequence[str] = (),
        note: str | None = None,
        author: str | None = None,
    ) -> SeriesNote:
        if not 1 <= len(series_id) <= 200 or series_id.startswith(f"{PROVIDER}:"):
            raise KnowledgeError("invalid_series")
        if note is not None and len(note) > MAX_TEXT:
            raise KnowledgeError("note_too_long")
        cleaned = _clean_aliases(aliases)
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM kb_series WHERE series_id = ? ORDER BY version DESC LIMIT 1",
                [series_id],
            ).fetchone()
            if row is not None and (
                bool(row["archived"]),
                tuple(json.loads(row["aliases"])),
                row["note"],
            ) == (archived, cleaned, note or None):
                return _note(row)
            stored = SeriesNote(
                series_id,
                (row["version"] if row is not None else 0) + 1,
                archived,
                cleaned,
                note or None,
                datetime.now(UTC),
                author,
            )
            connection.execute(
                "INSERT INTO kb_series VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    stored.series_id,
                    stored.version,
                    int(stored.archived),
                    json.dumps(list(stored.aliases), ensure_ascii=False),
                    stored.note,
                    stored.created_at.isoformat(),
                    stored.author,
                ],
            )
        return stored

    def notes(self) -> list[SeriesNote]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT s.* FROM kb_series s JOIN (SELECT series_id, max(version) AS version"
                " FROM kb_series GROUP BY series_id) m"
                " ON s.series_id = m.series_id AND s.version = m.version ORDER BY s.series_id"
            ).fetchall()
        return [_note(row) for row in rows]

    def note_history(self, series_id: str) -> list[SeriesNote]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM kb_series WHERE series_id = ? ORDER BY version", [series_id]
            ).fetchall()
        return [_note(row) for row in rows]


def _note(row: sqlite3.Row) -> SeriesNote:
    return SeriesNote(
        row["series_id"],
        row["version"],
        bool(row["archived"]),
        tuple(json.loads(row["aliases"])),
        row["note"],
        datetime.fromisoformat(row["created_at"]),
        row["author"],
    )
