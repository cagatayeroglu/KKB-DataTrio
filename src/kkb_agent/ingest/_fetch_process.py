"""Supervise one fixed fetch worker; never leave a timed-out DNS call running."""

from __future__ import annotations

import base64
import json

# Fixed interpreter/module only; no shell or user command.
import subprocess  # nosec B404
import sys
import time
from contextlib import suppress

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


def fetch_in_process(request: FetchRequest, limits: FetchLimits) -> FetchOutcome:
    """Bound DNS/connect first, then the whole operation including worker IPC.

    communicate may be resumed after TimeoutExpired. A fixed marker is emitted
    only after DNS, numeric connect, peer and verified TLS checks succeed. Until
    it arrives, connect_seconds also bounds blocking resolver/TLS work and worker
    startup. The total deadline never restarts. On timeout kill and reap the
    worker, which owns every socket; no abandoned resolver thread remains.
    """

    started = time.monotonic()
    failure = FetchFailure(source_ref=request.source_ref, code=FetchCode.TRANSPORT_FAILURE)
    data = request.model_dump(mode="json")
    data["url"] = request.url.get_secret_value()
    payload = json.dumps({"request": data, "limits": limits.model_dump(mode="json")}).encode()
    if len(payload) > MAX_INPUT_BYTES:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
    process = None
    try:
        # Module and executable are trusted constants, never locator/model text.
        # Isolated Python ignores PYTHONPATH/current-directory module shadowing.
        process = subprocess.Popen(  # nosec B603
            [sys.executable, "-I", "-m", "kkb_agent.ingest._fetch_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        remaining = limits.total_seconds - (time.monotonic() - started)
        connect_remaining = limits.connect_seconds - (time.monotonic() - started)
        if min(remaining, connect_remaining) <= 0:
            raise subprocess.TimeoutExpired("source-fetch", 0)
        try:
            output, _ = process.communicate(payload, timeout=min(remaining, connect_remaining))
        except subprocess.TimeoutExpired as error:
            if not (error.output or b"").startswith(CONNECTED):
                raise
            remaining = limits.total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise
            output, _ = process.communicate(timeout=remaining)
        if time.monotonic() - started >= limits.total_seconds:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
        if process.returncode != 0:
            return failure
        # The trusted worker emits one bounded payload; independently validate
        # its size, identity, accepted type and decoded bytes before returning.
        if len(output) > 4 * ((limits.max_decompressed_bytes + 2) // 3) + 4096:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
        result = json.loads(output.removeprefix(CONNECTED))
        if not isinstance(result, dict):
            return failure
        if result.get("source_ref") != request.source_ref:
            return failure
        if result.get("status") == "failure":
            return FetchFailure.model_validate(result)
        if not output.startswith(CONNECTED):
            return failure
        result["content"] = base64.b64decode(result["content"], validate=True)
        success = FetchSuccess.model_validate(result)
        if len(success.content) > limits.max_decompressed_bytes:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
        if success.media_type not in request.accepted_media_types:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.CONTENT_TYPE)
        if time.monotonic() - started >= limits.total_seconds:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
        return success
    except subprocess.TimeoutExpired:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
    except (OSError, ValueError, TypeError, KeyError):
        return failure
    finally:
        if process is not None:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    process.kill()
            # Reap even on interrupted callers or broken worker output. Closing
            # pipes after kill avoids a second buffered read of the result.
            process.wait()
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    with suppress(OSError):
                        stream.close()
