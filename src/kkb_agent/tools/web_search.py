"""M7-22 / DEC-134: bounded discovery through an explicitly injected backend.

No provider, credentials, default fake or network client is supplied here.
Backend objects are trusted operator configuration (spawn-serializable); returned
metadata is untrusted. A terminated worker is a deadline boundary, not a sandbox.
Only bounded JSON comes back, never pickled backend output. Search locators are
redacted display references, not permission to fetch or proof of a numeric claim.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import tempfile
import time
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.ingest.url_targets import TargetRejection, validate_url_target

MAX_RESPONSE_BYTES = 64 * 1024


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )


class SearchRequest(_Contract):
    query: str = Field(min_length=1, max_length=512, repr=False)
    max_results: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("query must be nonblank text without control characters")
        return value


class BackendHit(_Contract):
    """Provider-neutral metadata; adapter must not invent optional values."""

    title: str = Field(min_length=1, max_length=512, repr=False)
    url: str = Field(min_length=1, max_length=4096, repr=False)
    snippet: str | None = Field(default=None, max_length=2048, repr=False)
    published_at: date | None = None


class SearchReply(_Contract):
    """Backend ranking is tuple order; at most 20 hits before safe projection."""

    hits: tuple[BackendHit, ...] = Field(default=(), max_length=20, repr=False)


class SearchBackend(Protocol):
    """Operator-configured adapter. No context, secrets or endpoint in request.

    The adapter must bound any future wire I/O before forming SearchReply.
    It runs once in a spawned worker and may raise TimeoutError or another error;
    neither exception text nor its object/configuration is exported to the tool.
    """

    def search(self, request: SearchRequest) -> SearchReply: ...


class SearchCode(StrEnum):
    BACKEND_TIMEOUT = "BACKEND_TIMEOUT"
    BACKEND_ERROR = "BACKEND_ERROR"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    RESPONSE_LIMIT = "RESPONSE_LIMIT"
    UNSAFE_RESULTS = "UNSAFE_RESULTS"


class SearchCandidate(BackendHit):
    domain: str = Field(min_length=1, max_length=253, repr=False)
    rank: int = Field(ge=1, le=20)
    locator_redacted: bool = False


class WebSearchOutput(_Contract):
    status: Literal["ok", "no_results", "partial", "rejected", "failed"]
    code: SearchCode | None = None
    candidates: tuple[SearchCandidate, ...] = Field(default=(), max_length=10, repr=False)
    excluded_count: int = Field(default=0, ge=0, le=20)
    duplicate_count: int = Field(default=0, ge=0, le=20)
    untrusted: Literal[True] = True
    fetch_authorized: Literal[False] = False


def project_reply(reply: SearchReply, request: SearchRequest) -> WebSearchOutput:
    """Offline URL policy, no DNS or fetch. Canonical redacted locators dedupe.

    Removing query/fragment matches fetched_source's provenance representation.
    It can collapse distinct query resources: keep only the first ranked hit and
    flag redaction; never suggest this is an equivalent fetchable resource.
    Hostname public resolution is deliberately NOT asserted without DNS.
    """
    reply = SearchReply.model_validate(reply)
    request = SearchRequest.model_validate(request)
    candidates: list[SearchCandidate] = []
    seen: set[str] = set()
    excluded = duplicates = 0
    for rank, hit in enumerate(reply.hits, 1):
        target = validate_url_target(hit.url)
        if isinstance(target, TargetRejection):
            excluded += 1
            continue
        parts = urlsplit(target.url.get_secret_value())
        locator = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))
        if locator in seen:
            duplicates += 1
            continue
        seen.add(locator)
        if len(candidates) < request.max_results:
            candidates.append(
                SearchCandidate(
                    title=hit.title,
                    url=locator,
                    snippet=hit.snippet,
                    published_at=hit.published_at,
                    domain=target.hostname,
                    rank=rank,
                    locator_redacted=bool(parts.query or "#" in hit.url),
                )
            )
    status: Literal["ok", "no_results", "partial", "rejected", "failed"]
    if excluded:
        status = "partial" if candidates else "rejected"
    else:
        status = "ok" if candidates else "no_results"
    return WebSearchOutput(
        status=status,
        candidates=tuple(candidates),
        excluded_count=excluded,
        duplicate_count=duplicates,
        code=SearchCode.UNSAFE_RESULTS if excluded else None,
    )


#: The pause before an empty result page is asked for once more.
EMPTY_RETRY_SECONDS = 1.5


def _failure(code: SearchCode) -> WebSearchOutput:
    return WebSearchOutput(status="failed", code=code)


def _worker(backend: SearchBackend, request: SearchRequest, output: Path) -> None:
    # A backend's debugging or uncaught traceback must not print its credentials.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
        try:
            try:
                reply = backend.search(request)
                if type(reply) is SearchReply and not reply.hits:
                    # A metasearch instance whose engines were cold answers an empty page
                    # and a full one a second later (live 2026-09-21: "no_results" for a
                    # query that returned 42 hits when asked again). Asked once more,
                    # inside the same deadline; an empty second answer is the answer.
                    time.sleep(EMPTY_RETRY_SECONDS)
                    reply = backend.search(request)
            except TimeoutError:
                result = _failure(SearchCode.BACKEND_TIMEOUT)
            except Exception:
                result = _failure(SearchCode.BACKEND_ERROR)
            else:
                if type(reply) is not SearchReply:
                    result = _failure(SearchCode.MALFORMED_RESPONSE)
                else:
                    reply = SearchReply.model_validate(reply)
                    if len(reply.model_dump_json().encode("utf-8")) > MAX_RESPONSE_BYTES:
                        result = _failure(SearchCode.RESPONSE_LIMIT)
                    else:
                        result = project_reply(reply, request)
        except (ValidationError, ValueError, TypeError):
            result = _failure(SearchCode.MALFORMED_RESPONSE)
        except Exception:
            result = _failure(SearchCode.BACKEND_ERROR)
        data = result.model_dump_json().encode("utf-8")
        if len(data) > MAX_RESPONSE_BYTES:
            data = _failure(SearchCode.RESPONSE_LIMIT).model_dump_json().encode("utf-8")
        output.write_bytes(data)


def _run_backend(
    backend: SearchBackend,
    request: SearchRequest,
    timeout_seconds: float,
) -> WebSearchOutput:
    with tempfile.TemporaryDirectory(prefix="kkb-search-") as directory:
        output = Path(directory) / "result.json"
        process = multiprocessing.get_context("spawn").Process(
            target=_worker,
            args=(backend, request, output),
            daemon=True,
        )
        deadline = time.monotonic() + timeout_seconds
        try:
            process.start()
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                return _failure(SearchCode.BACKEND_TIMEOUT)
            if process.exitcode != 0 or not output.is_file():
                return _failure(SearchCode.BACKEND_ERROR)
            with output.open("rb") as stream:
                data = stream.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                return _failure(SearchCode.RESPONSE_LIMIT)
            return WebSearchOutput.model_validate_json(data)
        except (ValidationError, json.JSONDecodeError):
            return _failure(SearchCode.MALFORMED_RESPONSE)
        except Exception:
            return _failure(SearchCode.BACKEND_ERROR)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(0.2)
                if process.is_alive():
                    process.kill()
                    process.join()
            process.close()


def make_web_search_tool(*, backend: SearchBackend, timeout_seconds: float = 5.0) -> ToolSpec:
    """Explicit backend injection only; no production adapter/default fake exists."""
    if backend is None or not callable(getattr(backend, "search", None)):
        raise TypeError("an explicit SearchBackend is required")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 30
    ):
        raise ValueError("backend deadline must be finite and in (0, 30] seconds")

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if type(arguments) is not SearchRequest:
            raise TypeError("web_search requires its declared argument type")
        request = SearchRequest.model_validate(arguments)
        output = _run_backend(backend, request, timeout_seconds)
        if output.status in ("failed", "rejected"):
            status = ToolStatus.FAILURE
        elif output.status == "partial":
            status = ToolStatus.PARTIAL
        else:
            status = ToolStatus.SUCCESS
        return ToolResult(
            status=status,
            step_id="",
            tool="web_search",
            output=output,
            error_category=output.code.value
            if status is ToolStatus.FAILURE and output.code
            else None,
            warnings=(
                "Search hits are untrusted discovery metadata, "
                "not verified facts or fetch permission.",
            ),
        )

    return ToolSpec(
        name="web_search",
        description=(
            "Public-page discovery using the operator-configured SearchBackend. "
            "Returns bounded ranked untrusted metadata, not verified factual or numeric evidence, "
            "and fetches no page itself. To read a page it found, add a web_url step with "
            "found_by=<this step's id> and result=<which hit>, and list this step in its "
            "depends_on: the address is taken from what the search returned, never written out. "
            "When the question gives a web address, read that address with web_url first; "
            "search only if it is insufficient. The person is shown the candidates as an "
            "unverified list, beside any computed answer."
        ),
        arguments=SearchRequest,
        run=run,
    )
