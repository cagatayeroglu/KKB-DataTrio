"""Fixed one-request worker, terminated by the parent for DNS/total deadlines.

Not a command runner: the executable/module are constant, input is validated
JSON on stdin, and the only operation is a bounded source GET. stdout contains
one fixed connection marker and one bounded JSON result; stderr is discarded.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import zlib
from collections.abc import Callable
from contextlib import suppress
from http.client import HTTPException
from urllib.parse import quote, urlsplit

from kkb_agent.ingest._bounded_response import BoundedResponse, ResponseRejected, read_response
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
    request: FetchRequest, limits: FetchLimits, connected: Callable[[], None]
) -> FetchOutcome:
    """Internal worker body; public callers must use safe_fetch's supervisor."""

    connection = None
    response = None
    try:
        connection = SourceConnection(request, limits=limits)

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
                    header_limit=limits.max_header_bytes,
                )

        connection.response_class = LimitedResponse
        connection.connect()
        connected()  # Parent can distinguish blocked DNS/connect from body work.
        parsed = urlsplit(connection.url.get_secret_value())
        path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            path += "?" + quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
        connection.request(
            "GET",
            path,
            headers={
                "Accept": ", ".join(request.accepted_media_types),
                "Accept-Encoding": "gzip, identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        return read_response(response, request, limits)
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

        def connected() -> None:
            sys.stdout.buffer.write(CONNECTED)
            sys.stdout.buffer.flush()

        result = fetch_once(request, limits, connected)
        encoded = result.model_dump(mode="json")
        if isinstance(result, FetchSuccess):
            encoded["content"] = base64.b64encode(result.content).decode("ascii")
        sys.stdout.buffer.write(json.dumps(encoded).encode("ascii"))
        sys.stdout.buffer.flush()
        return 0
    except Exception:  # Private boundary: never print raw tracebacks/input.
        return 1


if __name__ == "__main__":
    sys.exit(main())
