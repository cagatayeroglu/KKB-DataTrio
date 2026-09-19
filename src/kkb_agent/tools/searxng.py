"""A SearXNG `SearchBackend` for `web_search` (DEC-134, DEC-158).

SearXNG is a self-hosted metasearch service with a documented JSON output
(`/search?q=...&format=json`). It needs no account or API key, so no credential
enters this process, and the operator decides where it runs. This adapter is
operator configuration, not a planner argument: the planner supplies only the
query and a result count, exactly as the provider-neutral contract allows.

The request goes through `safe_fetch`, the same supervised transport as every
other outbound read (DEC-002 keeps a raw HTTP client in the Kloudeks module
only): fresh DNS and peer checks, no redirects here, a deadline and a byte
ceiling. One consequence is deliberate and stated: `safe_fetch` refuses
loopback and private addresses, so the instance must be reachable at a public
address. A loopback instance would need its own reviewed exception.

Only `title`, `url`, `content` and `publishedDate` are read from each result,
a result without a title or URL is dropped rather than completed, and the
instance's own text never reaches an error. The results stay untrusted
discovery metadata; they do not authorize `web_url` to fetch anything.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Final
from urllib.parse import urlencode, urlsplit

from pydantic import SecretStr

from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchOutcome,
    FetchRequest,
    FetchSuccess,
    safe_fetch,
)
from kkb_agent.tools.web_search import BackendHit, SearchReply, SearchRequest

MAX_BODY_BYTES: Final = 1024 * 1024
MAX_HITS: Final = 20
Fetch = Callable[..., FetchOutcome]


class SearxngRefused(ValueError):
    """The configured instance address is not one this adapter will call."""


#: The only hosts the loopback exception (DEC-180) will ever connect to.
LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "::1"})


def loopback_fetch(request: FetchRequest, *, limits: FetchLimits) -> FetchOutcome:
    """Read the operator's own SearXNG on this machine (DEC-180).

    `safe_fetch` refuses loopback for every address a question or a page can name, and
    that stays so. This function is not a general fetcher: it is wired only by the
    launcher's `--searxng-loopback`, it connects only to a literal loopback host over plain
    HTTP, follows no redirect, keeps the caller's deadline and byte ceiling, and accepts
    only a JSON answer. The planner never supplies the address; it supplies a query.
    """
    import http.client

    parts = urlsplit(request.url.get_secret_value())
    if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS or parts.port is None:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.BLOCKED_DESTINATION)
    connection = http.client.HTTPConnection(
        parts.hostname, parts.port, timeout=min(limits.connect_seconds, limits.total_seconds)
    )
    try:
        connection.request(
            "GET",
            parts.path + ("?" + parts.query if parts.query else ""),
            headers={"Accept": "application/json", "User-Agent": "kkb-agent-search"},
        )
        connection.sock.settimeout(min(limits.read_seconds, limits.total_seconds))
        response = connection.getresponse()
        if not 200 <= response.status <= 299:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.HTTP_FAILURE)
        media_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        if media_type not in request.accepted_media_types:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.CONTENT_TYPE)
        content = response.read(limits.max_response_bytes + 1)
        if len(content) > limits.max_response_bytes:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
        return FetchSuccess(
            source_ref=request.source_ref,
            content=content,
            media_type=media_type,
            http_status=response.status,
        )
    except TimeoutError:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
    except (OSError, http.client.HTTPException):
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.TRANSPORT_FAILURE)
    finally:
        connection.close()


def is_loopback_instance(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS and parts.port is not None


def _instance(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SearxngRefused("instance must be an http(s) address")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise SearxngRefused("instance address carries no credentials, query or fragment")
    return url.rstrip("/")


def _published(value: object) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _hits(payload: object) -> tuple[BackendHit, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("not a SearXNG JSON result page")
    found: list[BackendHit] = []
    for item in payload["results"]:
        if len(found) >= MAX_HITS:
            break
        if not isinstance(item, dict):
            continue
        title, url = item.get("title"), item.get("url")
        if not isinstance(title, str) or not title.strip() or not isinstance(url, str):
            continue  # Never complete a hit the instance did not give.
        content = item.get("content")
        found.append(
            BackendHit(
                title=" ".join(title.split())[:512],
                url=url[:4096],
                snippet=" ".join(content.split())[:2048]
                if isinstance(content, str) and content.strip()
                else None,
                published_at=_published(item.get("publishedDate")),
            )
        )
    return tuple(found)


@dataclass(frozen=True, slots=True)
class SearxngBackend:
    """Picklable operator configuration; the worker process does the fetch."""

    instance: str
    timeout_seconds: float = 8.0
    language: str = "tr-TR"
    #: Trusted injection for tests; production uses the supervised transport.
    fetch: Fetch = safe_fetch

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance", _instance(self.instance))
        if not 0 < self.timeout_seconds <= 25:
            raise SearxngRefused("deadline must be within the tool's own")

    def search(self, request: SearchRequest) -> SearchReply:
        request = SearchRequest.model_validate(request)
        query = urlencode(
            {
                "q": request.query,
                "format": "json",
                "language": self.language,
                "safesearch": "1",
            }
        )
        digest = hashlib.sha256(request.query.encode("utf-8")).hexdigest()[:24]
        outcome = self.fetch(
            FetchRequest(
                source_ref=f"search:searxng:{digest}",
                url=SecretStr(f"{self.instance}/search?{query}"),
                accepted_media_types=("application/json",),
            ),
            limits=FetchLimits(
                max_response_bytes=MAX_BODY_BYTES,
                max_decompressed_bytes=MAX_BODY_BYTES,
                max_redirects=0,
                connect_seconds=min(5.0, self.timeout_seconds),
                read_seconds=min(5.0, self.timeout_seconds),
                total_seconds=self.timeout_seconds,
            ),
        )
        if not isinstance(outcome, FetchSuccess):
            raise RuntimeError("search instance could not be read")
        return SearchReply(hits=_hits(json.loads(outcome.content)))
