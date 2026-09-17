"""Bounded JSON record arrays as tables: the data behind a script-driven page.

A portal that draws its chart in the browser fetches a JSON array of records
(`[{"hisTs": "2026-09-17", "clval": 66502.43}, ...]`). This reads such an
array as a rectangular table and nothing else: no expression, template or
script is evaluated, only `json.loads` over bounded bytes.

Rules, each refusing with a fixed code rather than guessing:

- The payload is UTF-8 JSON within `MAX_BYTES`, nested no deeper than `MAX_DEPTH`.
- The table is the one array of objects reachable at the top level or under a
  single key path; several candidate arrays are ambiguous.
- Every record holds scalars only; headers are the union of keys in first-seen
  order, at most `MAX_COLUMNS`; a missing key is an empty cell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Final

MAX_BYTES: Final = 8 * 1024 * 1024
MAX_DEPTH: Final = 8
MAX_ROWS: Final = 50_000
MAX_COLUMNS: Final = 32
MAX_KEY_CHARS: Final = 128
MEDIA_TYPE: Final = "application/json"

Scalar = str | float | int | bool | None


class JsonRejected(ValueError):
    """A fixed refusal code; never payload text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RecordTable:
    """Records from one JSON array; `path` is the key path that held them."""

    path: tuple[str, ...]
    headers: tuple[str, ...] = field(repr=False)
    rows: tuple[tuple[Scalar, ...], ...] = field(repr=False)


def _depth(value: object) -> int:
    deepest, stack = 0, [(value, 1)]
    while stack:
        item, level = stack.pop()
        deepest = max(deepest, level)
        if deepest > MAX_DEPTH:
            return deepest
        if isinstance(item, dict):
            stack.extend((child, level + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, level + 1) for child in item)
    return deepest


def _arrays(value: object, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], list[object]]]:
    if isinstance(value, list):
        return [(path, value)] if value and all(isinstance(r, dict) for r in value) else []
    if isinstance(value, dict) and len(path) < 3:
        found = []
        for key, child in value.items():
            found.extend(_arrays(child, (*path, str(key))))
        return found
    return []


def _scalar(value: object) -> Scalar:
    if value is None or isinstance(value, (str, float, int, bool)):
        return value
    raise JsonRejected("UNSUPPORTED_TABLE")  # pragma: no cover - containers refused above


def load_records(content: bytes) -> RecordTable:
    """The one record array in a JSON payload, as headers and scalar rows."""
    if len(content) > MAX_BYTES:
        raise JsonRejected("LIMIT_EXCEEDED")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise JsonRejected("MALFORMED_DOCUMENT") from None
    if _depth(payload) > MAX_DEPTH:
        raise JsonRejected("LIMIT_EXCEEDED")
    candidates = [(path, rows) for path, rows in _arrays(payload, ()) if len(rows) >= 2]
    if not candidates:
        raise JsonRejected("NO_RECORD_TABLE")
    if len(candidates) > 1:
        raise JsonRejected("AMBIGUOUS_TABLE")
    path, records = candidates[0]
    if len(records) > MAX_ROWS:
        raise JsonRejected("LIMIT_EXCEEDED")
    headers: list[str] = []
    dicts: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):  # pragma: no cover - guaranteed by _arrays
            raise JsonRejected("UNSUPPORTED_TABLE")
        dicts.append(record)
        for key, cell in record.items():
            if isinstance(cell, (dict, list)):
                raise JsonRejected("UNSUPPORTED_TABLE")
            if key not in headers:
                if len(headers) >= MAX_COLUMNS or len(str(key)) > MAX_KEY_CHARS:
                    raise JsonRejected("LIMIT_EXCEEDED")
                headers.append(str(key))
    rows: tuple[tuple[Scalar, ...], ...] = tuple(
        tuple(_scalar(record.get(key)) for key in headers) for record in dicts
    )
    return RecordTable(path, tuple(headers), rows)
