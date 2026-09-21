"""Fixed one-request worker, terminated by the parent for DNS/total deadlines.

Not a command runner: the executable/module are constant, input is validated
JSON on stdin: bounded source GET, the closed reviewed Monthly POST, the closed Weekly
POST, the closed FinTürk POST or the closed EVDS `fe` POST. stdout contains bounded
connection-phase markers and one bounded JSON result; stderr is discarded.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import time
import zlib
from collections.abc import Callable
from contextlib import suppress
from http.client import HTTPException
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit, urlunsplit

if TYPE_CHECKING:
    from kkb_agent.ingest.bddk_finturk_request import FinturkRequest
    from kkb_agent.ingest.bddk_monthly_request import MonthlyRequest
    from kkb_agent.ingest.bddk_weekly_request import WeeklyRequest
    from kkb_agent.ingest.evds_request import EvdsRequest

from pydantic import SecretStr

from kkb_agent.ingest._bounded_response import (
    BoundedResponse,
    ResponseRejected,
    read_response,
    redirect_location,
)
from kkb_agent.ingest._source_connection import SourceConnection, SourceConnectionError
from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchOutcome,
    FetchRequest,
    FetchSuccess,
)

CONNECTED = b"CONNECTED\n"
MAX_INPUT_BYTES = 64 * 1024


def fetch_once(
    request: FetchRequest,
    limits: FetchLimits,
    connected: Callable[[], None],
    *,
    connecting: Callable[[], None] = lambda: None,
    monthly: MonthlyRequest | None = None,
    evds: EvdsRequest | None = None,
    weekly: WeeklyRequest | None = None,
    finturk: FinturkRequest | None = None,
) -> FetchOutcome:
    """One supervised request lifecycle, including explicitly checked GET hops."""

    connection = None
    response = None
    deadline = time.monotonic() + limits.total_seconds
    header_remaining = limits.max_header_bytes
    try:
        body = None
        content_type = "application/x-www-form-urlencoded"
        fixed_headers: tuple[tuple[str, str], ...] = ()
        if sum(item is not None for item in (monthly, evds, weekly, finturk)) > 1:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
        if monthly is not None:
            from kkb_agent.ingest.bddk_monthly_request import MONTHLY_LIMITS, MonthlyRequest

            monthly = MonthlyRequest.model_validate(monthly)
            if request != monthly.fetch_request() or limits != MONTHLY_LIMITS:
                return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
            body = monthly.form_body()
        if evds is not None:
            from kkb_agent.ingest.evds_request import CLIENT_HEADERS, EVDS_LIMITS, EvdsRequest

            evds = EvdsRequest.model_validate(evds)
            if request != evds.fetch_request() or limits != EVDS_LIMITS:
                return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
            body, content_type, fixed_headers = evds.json_body(), "application/json", CLIENT_HEADERS
        if weekly is not None:
            from kkb_agent.ingest.bddk_weekly_request import WEEKLY_LIMITS, WeeklyRequest

            weekly = WeeklyRequest.model_validate(weekly)
            if request != weekly.fetch_request() or limits != WEEKLY_LIMITS:
                return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
            body = weekly.form_body()
        if finturk is not None:
            from kkb_agent.ingest.bddk_finturk_request import FINTURK_LIMITS, FinturkRequest

            finturk = FinturkRequest.model_validate(finturk)
            if request != finturk.fetch_request() or limits != FINTURK_LIMITS:
                return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
            body = finturk.form_body()
        # Only the revalidated fixed BDDK POSTs get the pinned BDDK issuer.
        connection = SourceConnection(
            request,
            limits=limits,
            reviewed_issuer=any(item is not None for item in (monthly, weekly, finturk)),
        )
        visited = {connection.url.get_secret_value()}
        hops = 0

        class LimitedResponse(BoundedResponse):
            def __init__(
                self,
                sock: socket.socket,
                debuglevel: int = 0,
                method: str | None = None,
                url: str | None = None,
            ) -> None:
                super().__init__(
                    sock,
                    debuglevel=debuglevel,
                    method=method,
                    url=url,
                    header_limit=header_remaining,
                )

        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError
            connection.response_class = LimitedResponse
            if hops:
                connecting()  # Parent also bounds each subsequent DNS/TLS phase.
            connection.connect()
            connected()
            if time.monotonic() >= deadline:
                raise TimeoutError
            parsed = urlsplit(connection.url.get_secret_value())
            path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
            if parsed.query:
                path += "?" + quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
            headers = {
                "Accept": ", ".join(request.accepted_media_types),
                "Accept-Encoding": "gzip, identity",
                "Connection": "close",
            }
            if body is not None:
                headers["Content-Type"] = content_type
                headers.update(fixed_headers)
            connection.request(
                "POST" if body is not None else "GET", path, body=body, headers=headers
            )
            response = connection.getresponse()
            if not isinstance(response, BoundedResponse):  # Internal factory invariant.
                raise ResponseRejected(FetchCode.HTTP_FAILURE)
            header_remaining = response.remaining_header_bytes
            location = redirect_location(response)
            if location is None:
                result = read_response(response, request, limits)
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if hops:
                    result = result.model_copy(
                        update={
                            "effective_locator": SecretStr(
                                urlunsplit(
                                    (parsed.scheme, parsed.netloc, parsed.path or "/", "", "")
                                )
                            )
                        }
                    )
                return result
            # Never drain/decompress a redirect body or accept any of its cookies.
            response.close()
            response = None
            connection.close()
            if hops >= limits.max_redirects:
                raise ResponseRejected(FetchCode.REDIRECT_LIMIT)
            next_connection = connection.redirect_connection(location)
            destination = next_connection.url.get_secret_value()
            if destination in visited:
                raise ResponseRejected(FetchCode.REDIRECT_LOOP)
            visited.add(destination)
            connection = next_connection
            hops += 1
    except SourceConnectionError as error:
        return error.failure
    except ResponseRejected as error:
        return FetchFailure(source_ref=request.source_ref, code=error.code)
    except TimeoutError:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
    except (HTTPException, zlib.error):
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.HTTP_FAILURE)
    except (OSError, ValueError):
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.TRANSPORT_FAILURE)
    finally:
        if response is not None:
            with suppress(OSError):
                response.close()
        if connection is not None:
            with suppress(OSError):
                connection.close()


def main() -> int:
    # Bound even the private protocol. No URLs or exception text in diagnostics.
    payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    try:
        if len(payload) > MAX_INPUT_BYTES:
            return 1
        data = json.loads(payload)
        request = FetchRequest.model_validate(data["request"])
        limits = FetchLimits.model_validate(data["limits"])
        monthly = None
        if "monthly" in data:
            from kkb_agent.ingest.bddk_monthly_request import MonthlyRequest

            monthly = MonthlyRequest.model_validate(data["monthly"])
        evds = None
        if "evds" in data:
            from kkb_agent.ingest.evds_request import EvdsRequest

            evds = EvdsRequest.model_validate(data["evds"])
        weekly = None
        if "weekly" in data:
            from kkb_agent.ingest.bddk_weekly_request import WeeklyRequest

            weekly = WeeklyRequest.model_validate(data["weekly"])
        finturk = None
        if "finturk" in data:
            from kkb_agent.ingest.bddk_finturk_request import FinturkRequest

            finturk = FinturkRequest.model_validate(data["finturk"])

        def connected() -> None:
            sys.stdout.buffer.write(CONNECTED)
            sys.stdout.buffer.flush()

        def connecting() -> None:
            # A timestamp, not a locator. Same-host monotonic clock as the parent.
            message = f"CONNECTING {time.monotonic() + limits.connect_seconds:.9f}\n"
            sys.stdout.buffer.write(message.encode("ascii"))
            sys.stdout.buffer.flush()

        result = fetch_once(
            request,
            limits,
            connected,
            connecting=connecting,
            monthly=monthly,
            evds=evds,
            weekly=weekly,
            finturk=finturk,
        )
        encoded = result.model_dump(mode="json")
        if isinstance(result, FetchSuccess):
            encoded["content"] = base64.b64encode(result.content).decode("ascii")
            if result.effective_locator is not None:
                encoded["effective_locator"] = result.effective_locator.get_secret_value()
        sys.stdout.buffer.write(json.dumps(encoded).encode("ascii"))
        sys.stdout.buffer.flush()
        return 0
    except Exception:  # Private boundary: never print raw tracebacks/input.
        return 1


if __name__ == "__main__":
    sys.exit(main())
