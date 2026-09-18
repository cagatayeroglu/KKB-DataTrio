"""Conversations that survive a restart: a small owned SQLite store beside the lakehouse.

Until now a conversation lived in memory and under a per-process directory, so
restarting the API lost every chat, upload and published table. Analytical state
does not belong here: tables, lineage and evidence stay in the conversation's own
DuckDB lakehouse, and this store keeps only what points at them — who owns a
conversation, its messages, its uploads, and which published result a turn
produced. The two are joined by ids, never by copying rows or table values.

SQLite (stdlib) rather than the lakehouse: this is small, transactional,
frequently updated metadata written while analyses read their DuckDB snapshot.

Ownership is deliberately small and local. A conversation is reachable with the
owner key the browser keeps, or with that conversation's own token; knowing a
conversation id is never enough. Digests are stored, never the keys themselves.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal
from uuid import uuid4

from pydantic import JsonValue

from kkb_agent.agent.observer import TraceEvent

DATABASE_NAME: Final = "conversations.sqlite"
MAX_TITLE_CHARS: Final = 120
MAX_TEXT_CHARS: Final = 8192
MAX_SEARCH_CHARS: Final = 120
MAX_LISTED: Final = 200
#: A settings record is a handful of flags and numbers, never free text.
MAX_SETTINGS_CHARS: Final = 2000
#: A conversation is named by its first question until the user renames it.
DEFAULT_TITLE: Final = "Yeni sohbet"

SCHEMA: Final = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS owners (
    owner_id      TEXT PRIMARY KEY,
    token_digest  BLOB NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS owner_settings (
    owner_id   TEXT PRIMARY KEY REFERENCES owners(owner_id),
    settings   TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES owners(owner_id),
    token_digest    BLOB NOT NULL,
    title           TEXT NOT NULL,
    archived        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    sequence        INTEGER NOT NULL,
    turn_id         TEXT NOT NULL,
    role            TEXT NOT NULL,
    text            TEXT NOT NULL,
    status          TEXT,
    result_ref      TEXT,
    result_version  TEXT,
    document_ref    TEXT,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, sequence)
);

CREATE TABLE IF NOT EXISTS documents (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    document_ref    TEXT NOT NULL,
    name            TEXT NOT NULL,
    document_format TEXT NOT NULL,
    media_type      TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    byte_count      INTEGER NOT NULL,
    path            TEXT NOT NULL,
    admitted_at     TEXT NOT NULL,
    PRIMARY KEY (conversation_id, document_ref)
);

CREATE TABLE IF NOT EXISTS publications (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    turn_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    artifact_id     TEXT NOT NULL,
    result_ref      TEXT NOT NULL,
    result_version  TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, turn_id)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    turn_id         TEXT NOT NULL,
    question        TEXT NOT NULL,
    status          TEXT NOT NULL,
    answer_status   TEXT,
    error           TEXT,
    result_ref      TEXT,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT NOT NULL,
    ended_at        TEXT
);

CREATE TABLE IF NOT EXISTS trace_events (
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    sequence    INTEGER NOT NULL,
    stage       TEXT NOT NULL,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_ms  INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    attributes  TEXT NOT NULL,
    detail      TEXT,
    parent      INTEGER,
    PRIMARY KEY (run_id, sequence)
);

CREATE TABLE IF NOT EXISTS feedback (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    turn_id         TEXT NOT NULL,
    answer_digest   TEXT NOT NULL,
    run_id          TEXT,
    result_version  TEXT,
    rating          TEXT NOT NULL,
    comment         TEXT,
    reasons         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    score           INTEGER CHECK (score IS NULL OR score BETWEEN 1 AND 5),
    PRIMARY KEY (conversation_id, turn_id, answer_digest)
);

CREATE TABLE IF NOT EXISTS result_series (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    turn_id         TEXT NOT NULL,
    series_id       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, turn_id, series_id)
);

CREATE INDEX IF NOT EXISTS result_series_by_series ON result_series(series_id, created_at DESC);
CREATE INDEX IF NOT EXISTS runs_by_conversation ON runs(conversation_id, started_at DESC);
CREATE INDEX IF NOT EXISTS conversations_by_owner
    ON conversations(owner_id, archived, updated_at DESC);
CREATE INDEX IF NOT EXISTS messages_by_turn ON messages(conversation_id, turn_id);
"""


class StoreError(RuntimeError):
    """The store refused an operation; the message is a fixed category."""


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: str
    owner_id: str
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    sequence: int
    turn_id: str
    role: Literal["user", "assistant"]
    text: str
    status: str | None
    result_ref: str | None
    result_version: str | None
    document_ref: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredDocument:
    document_ref: str
    name: str
    document_format: str
    media_type: str
    sha256: str
    byte_count: int
    path: Path
    admitted_at: datetime


@dataclass(frozen=True, slots=True)
class StoredPublication:
    turn_id: str
    name: str
    artifact_id: str
    result_ref: str
    result_version: str


@dataclass(frozen=True, slots=True)
class StoredFeedback:
    """One rating of one exact answer; a re-answered turn keeps its own rating."""

    turn_id: str
    answer_digest: str
    run_id: str | None
    result_version: str | None
    rating: str
    comment: str | None
    reasons: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    score: int | None = None


@dataclass(frozen=True, slots=True)
class StoredRun:
    """One executed turn: what was asked, how it ended, how long it took."""

    run_id: str
    turn_id: str
    question: str
    status: str
    answer_status: str | None
    error: str | None
    result_ref: str | None
    duration_ms: int
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    stage: str
    name: str
    status: str
    started_ms: int
    duration_ms: int
    attributes: dict[str, JsonValue]
    detail: str | None
    parent: int | None


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _moment(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ConversationStore:
    """One SQLite file, one process, many threads; every write is a transaction."""

    def __init__(self, path: Path, *, clock: object = None) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self._path), check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.executescript(SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Bring a store created by an earlier version up to this schema, in place."""
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(feedback)")}
        if "score" not in columns:
            # Earlier ratings keep no score; nothing is invented for them.
            self._connection.execute(
                "ALTER TABLE feedback ADD COLUMN score INTEGER"
                " CHECK (score IS NULL OR score BETWEEN 1 AND 5)"
            )

    @property
    def path(self) -> Path:
        return self._path

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

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    # -- owners ---------------------------------------------------------------

    def create_owner(self) -> tuple[str, str]:
        """A new owner key for this browser; only its digest is stored."""
        owner_id, token = uuid4().hex, secrets.token_urlsafe(32)
        with self._write() as connection:
            connection.execute(
                "INSERT INTO owners VALUES (?, ?, ?)", [owner_id, _digest(token), self._now()]
            )
        return owner_id, token

    def owner_by_token(self, token: str) -> str | None:
        """The owner this key belongs to, compared in constant time; None otherwise."""
        wanted = _digest(token)
        with self._lock:
            rows = self._connection.execute("SELECT owner_id, token_digest FROM owners").fetchall()
        for row in rows:
            if secrets.compare_digest(wanted, bytes(row["token_digest"])):
                return str(row["owner_id"])
        return None

    def settings_of(self, owner_id: str) -> dict[str, object]:
        """What this browser chose, as stored; an owner who chose nothing has none."""
        with self._lock:
            row = self._connection.execute(
                "SELECT settings FROM owner_settings WHERE owner_id = ?", [owner_id]
            ).fetchone()
        if row is None:
            return {}
        try:
            stored = json.loads(str(row["settings"]))
        except json.JSONDecodeError:  # pragma: no cover - a hand-edited file
            return {}
        return stored if isinstance(stored, dict) else {}

    def save_settings(self, owner_id: str, settings: dict[str, object]) -> None:
        """Replace this owner's choices. The caller owns what a choice may say."""
        payload = json.dumps(settings, ensure_ascii=False, sort_keys=True)
        if len(payload) > MAX_SETTINGS_CHARS:
            raise StoreError("settings_too_large")
        with self._write() as connection:
            connection.execute(
                "INSERT INTO owner_settings VALUES (?, ?, ?) ON CONFLICT(owner_id) DO UPDATE "
                "SET settings = excluded.settings, updated_at = excluded.updated_at",
                [owner_id, payload, self._now()],
            )

    def owner_of_conversation(self, conversation_id: str) -> str | None:
        """Whose conversation this is, so a turn can read that owner's settings."""
        with self._lock:
            row = self._connection.execute(
                "SELECT owner_id FROM conversations WHERE conversation_id = ?", [conversation_id]
            ).fetchone()
        return str(row["owner_id"]) if row is not None else None

    def owner_of(self, owner_id: str, token: str) -> bool:
        """Whether this owner key is the one recorded, compared in constant time."""
        with self._lock:
            row = self._connection.execute(
                "SELECT token_digest FROM owners WHERE owner_id = ?", [owner_id]
            ).fetchone()
        expected = bytes(row["token_digest"]) if row is not None else bytes(32)
        return secrets.compare_digest(_digest(token), expected) and row is not None

    # -- conversations --------------------------------------------------------

    def create_conversation(
        self, *, owner_id: str, conversation_id: str, token: str, title: str
    ) -> Conversation:
        moment = self._now()
        with self._write() as connection:
            if (
                connection.execute("SELECT 1 FROM owners WHERE owner_id = ?", [owner_id]).fetchone()
                is None
            ):
                raise StoreError("unknown_owner")
            connection.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, 0, ?, ?)",
                [
                    conversation_id,
                    owner_id,
                    _digest(token),
                    title[:MAX_TITLE_CHARS],
                    moment,
                    moment,
                ],
            )
        return Conversation(
            conversation_id,
            owner_id,
            title[:MAX_TITLE_CHARS],
            False,
            _moment(moment),
            _moment(moment),
        )

    def conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?", [conversation_id]
            ).fetchone()
        return None if row is None else self._conversation(row)

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            row["conversation_id"],
            row["owner_id"],
            row["title"],
            bool(row["archived"]),
            _moment(row["created_at"]),
            _moment(row["updated_at"]),
        )

    def opens(self, conversation_id: str, *, token: str | None, owner_token: str | None) -> bool:
        """Whether this request may open the conversation.

        Either the conversation's own token or its owner's key opens it; a
        conversation id alone never does.
        """
        found = self.conversation(conversation_id)
        if found is None:
            return False
        if owner_token is not None and self.owner_of(found.owner_id, owner_token):
            return True
        if token is None:
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT token_digest FROM conversations WHERE conversation_id = ?",
                [conversation_id],
            ).fetchone()
        return secrets.compare_digest(_digest(token), bytes(row["token_digest"]))

    def list_conversations(
        self, owner_id: str, *, archived: bool = False, search: str | None = None
    ) -> list[Conversation]:
        query = (
            "SELECT * FROM conversations WHERE owner_id = ? AND archived = ? "
            "ORDER BY updated_at DESC LIMIT ?"
        )
        parameters: list[object] = [owner_id, int(archived), MAX_LISTED]
        if search:
            needle = f"%{search[:MAX_SEARCH_CHARS].lower()}%"
            query = (
                "SELECT c.* FROM conversations c WHERE c.owner_id = ? AND c.archived = ? AND ("
                "lower(c.title) LIKE ? OR EXISTS (SELECT 1 FROM messages m WHERE "
                "m.conversation_id = c.conversation_id AND lower(m.text) LIKE ?)) "
                "ORDER BY c.updated_at DESC LIMIT ?"
            )
            parameters = [owner_id, int(archived), needle, needle, MAX_LISTED]
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [self._conversation(row) for row in rows]

    def update_conversation(
        self, conversation_id: str, *, title: str | None = None, archived: bool | None = None
    ) -> Conversation:
        with self._write() as connection:
            if title is not None:
                connection.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                    [title[:MAX_TITLE_CHARS], self._now(), conversation_id],
                )
            if archived is not None:
                connection.execute(
                    "UPDATE conversations SET archived = ?, updated_at = ? "
                    "WHERE conversation_id = ?",
                    [int(archived), self._now(), conversation_id],
                )
        found = self.conversation(conversation_id)
        if found is None:
            raise StoreError("unknown_conversation")
        return found

    # -- which answers rest on which series (reverse lineage) ------------------

    def record_result_series(
        self, conversation_id: str, turn_id: str, series_ids: Sequence[str]
    ) -> None:
        """The series a published answer's proof actually read, one row each.

        Written where the answer's messages are written, from the proof's own
        sources - never from the question's wording or the planner's intent.
        """
        now = self._now()
        with self._lock, self._connection:
            for series_id in sorted(set(series_ids)):
                self._connection.execute(
                    "INSERT OR IGNORE INTO result_series VALUES (?, ?, ?, ?)",
                    [conversation_id, turn_id, series_id[:200], now],
                )

    def series_uses(self, owner_id: str, series_id: str) -> list[dict[str, str]]:
        """This owner's answers whose proof read the series, newest first."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT r.conversation_id, c.title, r.turn_id, r.created_at,
                       (SELECT m.text FROM messages m
                         WHERE m.conversation_id = r.conversation_id
                           AND m.turn_id = r.turn_id AND m.role = 'user'
                         ORDER BY m.sequence LIMIT 1) AS question
                  FROM result_series r
                  JOIN conversations c ON c.conversation_id = r.conversation_id
                 WHERE r.series_id = ? AND c.owner_id = ?
                 ORDER BY r.created_at DESC LIMIT ?
                """,
                [series_id, owner_id, MAX_LISTED],
            ).fetchall()
        return [
            {
                "conversation_id": row["conversation_id"],
                "title": row["title"],
                "turn_id": row["turn_id"],
                "question": row["question"] or "",
                "used_at": row["created_at"],
            }
            for row in rows
        ]

    # -- messages -------------------------------------------------------------

    def append_message(
        self,
        conversation_id: str,
        *,
        turn_id: str,
        role: Literal["user", "assistant"],
        text: str,
        status: str | None = None,
        result_ref: str | None = None,
        result_version: str | None = None,
        document_ref: str | None = None,
    ) -> int:
        """Append one message and touch the conversation; returns its sequence.

        Replaying the same (turn, role) is not a second message: a retried
        request or a reconnected client must not duplicate the history.
        """
        moment = self._now()
        with self._write() as connection:
            existing = connection.execute(
                "SELECT sequence FROM messages WHERE conversation_id = ? AND turn_id = ? "
                "AND role = ?",
                [conversation_id, turn_id, role],
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "UPDATE messages SET text = ?, status = ?, result_ref = ?, result_version = ?"
                    " WHERE conversation_id = ? AND sequence = ?",
                    [
                        text[:MAX_TEXT_CHARS],
                        status,
                        result_ref,
                        result_version,
                        conversation_id,
                        existing["sequence"],
                    ],
                )
                sequence = int(existing["sequence"])
            else:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM messages "
                    "WHERE conversation_id = ?",
                    [conversation_id],
                ).fetchone()
                sequence = int(row["next"])
                connection.execute(
                    "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        conversation_id,
                        sequence,
                        turn_id,
                        role,
                        text[:MAX_TEXT_CHARS],
                        status,
                        result_ref,
                        result_version,
                        document_ref,
                        moment,
                    ],
                )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                [moment, conversation_id],
            )
        return sequence

    def messages(self, conversation_id: str) -> list[Message]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sequence",
                [conversation_id],
            ).fetchall()
        return [
            Message(
                int(row["sequence"]),
                row["turn_id"],
                row["role"],
                row["text"],
                row["status"],
                row["result_ref"],
                row["result_version"],
                row["document_ref"],
                _moment(row["created_at"]),
            )
            for row in rows
        ]

    def history(self, conversation_id: str, limit: int) -> list[tuple[str, str]]:
        """The last (question, shown answer) pairs, oldest first, for the planner."""
        pairs: list[tuple[str, str]] = []
        question: str | None = None
        for message in self.messages(conversation_id):
            if message.role == "user":
                question = message.text
            elif question is not None:
                pairs.append((question, message.text))
                question = None
        return pairs[-limit:]

    def turn_count(self, conversation_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(DISTINCT turn_id) AS turns FROM messages WHERE conversation_id = ?",
                [conversation_id],
            ).fetchone()
        return int(row["turns"])

    # -- documents and publications -------------------------------------------

    def add_document(
        self,
        conversation_id: str,
        *,
        document_ref: str,
        name: str,
        document_format: str,
        media_type: str,
        sha256: str,
        byte_count: int,
        path: Path,
        admitted_at: datetime,
    ) -> None:
        with self._write() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    conversation_id,
                    document_ref,
                    name,
                    document_format,
                    media_type,
                    sha256,
                    byte_count,
                    str(path),
                    admitted_at.isoformat(),
                ],
            )

    def documents(self, conversation_id: str) -> list[StoredDocument]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM documents WHERE conversation_id = ? ORDER BY admitted_at, name",
                [conversation_id],
            ).fetchall()
        return [
            StoredDocument(
                row["document_ref"],
                row["name"],
                row["document_format"],
                row["media_type"],
                row["sha256"],
                int(row["byte_count"]),
                Path(row["path"]),
                _moment(row["admitted_at"]),
            )
            for row in rows
        ]

    def add_publication(
        self,
        conversation_id: str,
        *,
        turn_id: str,
        name: str,
        artifact_id: str,
        result_ref: str,
        result_version: str,
    ) -> None:
        with self._write() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO publications VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    conversation_id,
                    turn_id,
                    name,
                    artifact_id,
                    result_ref,
                    result_version,
                    self._now(),
                ],
            )

    def publications(self, conversation_id: str) -> list[StoredPublication]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM publications WHERE conversation_id = ? ORDER BY created_at",
                [conversation_id],
            ).fetchall()
        return [
            StoredPublication(
                row["turn_id"],
                row["name"],
                row["artifact_id"],
                row["result_ref"],
                row["result_version"],
            )
            for row in rows
        ]

    # -- runs and trace events ------------------------------------------------

    def start_run(self, conversation_id: str, *, run_id: str, turn_id: str, question: str) -> None:
        """Record a run as soon as it starts, so a crash leaves a visible attempt."""
        with self._write() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, 'running', NULL, NULL, NULL,"
                " 0, ?, NULL)",
                [run_id, conversation_id, turn_id, question[:MAX_TEXT_CHARS], self._now()],
            )

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        duration_ms: int,
        answer_status: str | None = None,
        error: str | None = None,
        result_ref: str | None = None,
        events: Sequence[TraceEvent] = (),
    ) -> None:
        """Close a run and store its events; a run is written once, never edited."""
        with self._write() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, answer_status = ?, error = ?, result_ref = ?,"
                " duration_ms = ?, ended_at = ? WHERE run_id = ?",
                [status, answer_status, error, result_ref, duration_ms, self._now(), run_id],
            )
            for event in events:
                connection.execute(
                    "INSERT OR REPLACE INTO trace_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        run_id,
                        event.sequence,
                        event.stage,
                        event.name,
                        event.status,
                        event.started_ms,
                        event.duration_ms,
                        json.dumps(event.attributes, ensure_ascii=False),
                        event.detail,
                        event.parent,
                    ],
                )

    def add_event(self, run_id: str, event: TraceEvent) -> None:
        """Persist one event as it happens, so a running turn can be followed."""
        with self._write() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO trace_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    run_id,
                    event.sequence,
                    event.stage,
                    event.name,
                    event.status,
                    event.started_ms,
                    event.duration_ms,
                    json.dumps(event.attributes, ensure_ascii=False),
                    event.detail,
                    event.parent,
                ],
            )

    def runs(self, conversation_id: str, limit: int = 100) -> list[StoredRun]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM runs WHERE conversation_id = ? ORDER BY started_at DESC LIMIT ?",
                [conversation_id, limit],
            ).fetchall()
        return [
            StoredRun(
                row["run_id"],
                row["turn_id"],
                row["question"],
                row["status"],
                row["answer_status"],
                row["error"],
                row["result_ref"],
                int(row["duration_ms"]),
                _moment(row["started_at"]),
                _moment(row["ended_at"]) if row["ended_at"] else None,
            )
            for row in rows
        ]

    def run_of(self, conversation_id: str, run_id: str) -> StoredRun | None:
        """One run, only when it belongs to this conversation."""
        return next(
            (
                item
                for item in self.runs(conversation_id, limit=MAX_LISTED)
                if item.run_id == run_id
            ),
            None,
        )

    def events(self, run_id: str) -> list[StoredEvent]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM trace_events WHERE run_id = ? ORDER BY sequence", [run_id]
            ).fetchall()
        return [
            StoredEvent(
                int(row["sequence"]),
                row["stage"],
                row["name"],
                row["status"],
                int(row["started_ms"]),
                int(row["duration_ms"]),
                json.loads(row["attributes"]),
                row["detail"],
                int(row["parent"]) if row["parent"] is not None else None,
            )
            for row in rows
        ]

    # -- feedback -------------------------------------------------------------

    def rate(
        self,
        conversation_id: str,
        *,
        turn_id: str,
        answer_digest: str,
        rating: str,
        comment: str | None = None,
        reasons: Sequence[str] = (),
        run_id: str | None = None,
        result_version: str | None = None,
        score: int | None = None,
    ) -> StoredFeedback:
        """Record or change the rating of one exact answer.

        Keyed by the answer's own digest: rating the same answer again edits that
        rating, while an answer produced again (a new digest) starts unrated
        rather than inheriting what was said about the previous one.
        """
        moment = self._now()
        with self._write() as connection:
            existing = connection.execute(
                "SELECT created_at FROM feedback WHERE conversation_id = ? AND turn_id = ?"
                " AND answer_digest = ?",
                [conversation_id, turn_id, answer_digest],
            ).fetchone()
            if score is not None and not 1 <= score <= 5:
                raise StoreError("invalid_score")
            connection.execute(
                "INSERT OR REPLACE INTO feedback (conversation_id, turn_id, answer_digest,"
                " run_id, result_version, rating, comment, reasons, created_at, updated_at,"
                " score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    conversation_id,
                    turn_id,
                    answer_digest,
                    run_id,
                    result_version,
                    rating,
                    (comment or None) and comment[:MAX_TEXT_CHARS],
                    json.dumps(list(reasons)[:8], ensure_ascii=False),
                    existing["created_at"] if existing is not None else moment,
                    moment,
                    score,
                ],
            )
        found = self.feedback(conversation_id, turn_id=turn_id, answer_digest=answer_digest)
        if found is None:  # pragma: no cover - just written above
            raise StoreError("feedback_missing")
        return found

    def feedback(
        self, conversation_id: str, *, turn_id: str, answer_digest: str
    ) -> StoredFeedback | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM feedback WHERE conversation_id = ? AND turn_id = ?"
                " AND answer_digest = ?",
                [conversation_id, turn_id, answer_digest],
            ).fetchone()
        return None if row is None else self._feedback(row)

    def ratings(self, conversation_id: str) -> list[StoredFeedback]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM feedback WHERE conversation_id = ? ORDER BY updated_at DESC",
                [conversation_id],
            ).fetchall()
        return [self._feedback(row) for row in rows]

    @staticmethod
    def _feedback(row: sqlite3.Row) -> StoredFeedback:
        return StoredFeedback(
            row["turn_id"],
            row["answer_digest"],
            row["run_id"],
            row["result_version"],
            row["rating"],
            row["comment"],
            tuple(json.loads(row["reasons"])),
            _moment(row["created_at"]),
            _moment(row["updated_at"]),
            row["score"],
        )
