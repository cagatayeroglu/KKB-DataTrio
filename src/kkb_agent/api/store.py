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
import secrets
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal
from uuid import uuid4

DATABASE_NAME: Final = "conversations.sqlite"
MAX_TITLE_CHARS: Final = 120
MAX_TEXT_CHARS: Final = 8192
MAX_SEARCH_CHARS: Final = 120
MAX_LISTED: Final = 200
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
