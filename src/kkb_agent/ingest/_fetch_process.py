"""Supervise one fixed fetch worker; never leave a timed-out DNS call running."""

from __future__ import annotations

import base64
import io
import json
import math

# Fixed interpreter/module only; no shell or user command.
import subprocess  # nosec B404
import sys
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, BinaryIO, cast

if TYPE_CHECKING:
    from kkb_agent.ingest.bddk_monthly_request import MonthlyRequest
    from kkb_agent.ingest.evds_request import EvdsRequest

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
PROGRESS_POLL_SECONDS = 0.1


class _ProgressReader(io.BufferedIOBase):
    """Expose a bounded phase prefix while Windows communicate waits for EOF.

    On Windows, TimeoutExpired.output omits bytes already read by communicate's
    reader thread. Keep just the phase prefix separately so the supervisor can
    enforce the same connect/total deadlines as on POSIX. The final bytes still
    go through the normal complete-output validation.
    """

    def __init__(self, stream: io.BufferedReader, prefix_limit: int):
        self._stream = stream
        self._prefix_limit = prefix_limit
        self._prefix = bytearray()
        self._lock = threading.Lock()

    def read(self, size: int | None = -1) -> bytes:
        if size not in (-1, None):  # communicate only requests the complete stream.
            raise ValueError("progress reader requires an unbounded read")
        chunks = []
        while chunk := self._stream.read1(64 * 1024):
            with self._lock:
                remaining = self._prefix_limit - len(self._prefix)
                self._prefix.extend(chunk[:remaining])
            chunks.append(chunk)
        return b"".join(chunks)

    def progress(self) -> bytes:
        with self._lock:
            return bytes(self._prefix)

    def close(self) -> None:
        self._stream.close()
        super().close()


def _progress(output: bytes, started: float, limits: FetchLimits) -> tuple[bytes, float | None]:
    """Separate bounded phase markers from JSON; a redirect never resets total time."""
    deadline: float | None = started + limits.connect_seconds
    connections = 0
    while b"\n" in output:
        line, _, rest = output.partition(b"\n")
        if line == b"CONNECTED":
            if deadline is None:
                raise ValueError("unexpected connection marker")
            connections += 1
            if connections > limits.max_redirects + 1:
                raise ValueError("too many connection markers")
            deadline = None
        elif line.startswith(b"CONNECTING "):
            if deadline is not None or not connections or len(line) > 64:
                raise ValueError("unexpected redirect marker")
            deadline = float(line.removeprefix(b"CONNECTING "))
            if not math.isfinite(deadline) or deadline < started:
                raise ValueError("invalid connection deadline")
        else:
            break
        output = rest
    return output, deadline


def fetch_in_process(
    request: FetchRequest,
    limits: FetchLimits,
    *,
    monthly: MonthlyRequest | None = None,
    evds: EvdsRequest | None = None,
) -> FetchOutcome:
    """Bound DNS/connect first, then the whole operation including worker IPC.

    Phase markers distinguish DNS/connect from body work, including later hops.
    Poll while reading so a later DNS phase cannot hide behind the total timeout.
    Its absolute connect deadline and the one total deadline never restart on
    polling. Kill/reap the same worker on timeout; no abandoned DNS thread remains.
    """

    started = time.monotonic()
    failure = FetchFailure(source_ref=request.source_ref, code=FetchCode.TRANSPORT_FAILURE)
    data = request.model_dump(mode="json")
    data["url"] = request.url.get_secret_value()
    message = {"request": data, "limits": limits.model_dump(mode="json")}
    if monthly is not None:
        from kkb_agent.ingest.bddk_monthly_request import MONTHLY_LIMITS, MonthlyRequest

        monthly = MonthlyRequest.model_validate(monthly)
        if request != monthly.fetch_request() or limits != MONTHLY_LIMITS:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
        message["monthly"] = monthly.model_dump(mode="json")
    if evds is not None:
        from kkb_agent.ingest.evds_request import EVDS_LIMITS, EvdsRequest

        evds = EvdsRequest.model_validate(evds)
        if monthly is not None or request != evds.fetch_request() or limits != EVDS_LIMITS:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.INVALID_REQUEST)
        # A reviewed request stays the closed {code, window} pair on the wire to the worker;
        # only a listed series (DEC-177) carries its calendar.
        message["evds"] = evds.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(message).encode()
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
        reader = None
        if sys.platform == "win32" and isinstance(process.stdout, io.BufferedReader):
            reader = _ProgressReader(process.stdout, 64 * (2 * limits.max_redirects + 1))
            process.stdout = cast(BinaryIO, reader)
        remaining = limits.total_seconds - (time.monotonic() - started)
        connect_remaining = limits.connect_seconds - (time.monotonic() - started)
        if min(remaining, connect_remaining) <= 0:
            raise subprocess.TimeoutExpired("source-fetch", 0)
        wait = min(remaining, connect_remaining)
        pending: bytes | None = payload
        while True:
            try:
                output, _ = process.communicate(pending, timeout=wait)
                break
            except subprocess.TimeoutExpired as error:
                pending = None
                progress = error.output or (reader.progress() if reader is not None else b"")
                _, connect_deadline = _progress(progress, started, limits)
                now = time.monotonic()
                remaining = started + limits.total_seconds - now
                if remaining <= 0 or (connect_deadline is not None and now >= connect_deadline):
                    raise
                wait = min(
                    remaining,
                    PROGRESS_POLL_SECONDS if connect_deadline is None else connect_deadline - now,
                )
        if time.monotonic() - started >= limits.total_seconds:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.TIMEOUT)
        if process.returncode != 0:
            return failure
        # The trusted worker emits one bounded payload; independently validate
        # its size, identity, accepted type and decoded bytes before returning.
        overhead = 4096 + 6 * limits.max_url_chars + 64 * (2 * limits.max_redirects + 1)
        if len(output) > 4 * ((limits.max_decompressed_bytes + 2) // 3) + overhead:
            return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
        body, connect_deadline = _progress(output, started, limits)
        result = json.loads(body)
        if not isinstance(result, dict):
            return failure
        if result.get("source_ref") != request.source_ref:
            return failure
        if result.get("status") == "failure":
            return FetchFailure.model_validate(result)
        if not output.startswith(CONNECTED) or connect_deadline is not None:
            return failure
        result["content"] = base64.b64decode(result["content"], validate=True)
        success = FetchSuccess.model_validate(result)
        if success.effective_locator is not None:
            if len(success.effective_locator.get_secret_value()) > limits.max_url_chars:
                return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
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
