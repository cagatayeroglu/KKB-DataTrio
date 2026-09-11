"""Bounded HTTP/1 response framing and body decoding for the source worker.

Only identity/gzip content and identity/chunked transfer framing are supported.
Chunk extensions and trailers are rejected in this first direct-fetch path.
Nothing here parses files or assigns financial semantics to response bytes.
"""

from __future__ import annotations

import io
import re
import socket
import zlib
from http.client import HTTPResponse
from typing import cast

from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchRequest, FetchSuccess

CHUNK_BYTES = 16 * 1024


class ResponseRejected(Exception):
    def __init__(self, code: FetchCode) -> None:
        self.code = code
        super().__init__(code.value)


class _HeaderReader:
    """Charge aggregate framing bytes before the stdlib accumulates headers."""

    def __init__(self, stream: io.BufferedReader, remaining: int) -> None:
        self.stream = stream
        self.remaining = remaining

    def readline(self, size: int = -1) -> bytes:
        limit = self.remaining + 1
        line = self.stream.readline(min(size, limit) if size >= 0 else limit)
        self.charge(len(line))
        if not line.endswith(b"\r\n") or any(c < 32 and c not in (9, 10, 13) for c in line):
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        if b"\r" in line[:-2] or b"\n" in line[:-2] or b"\x7f" in line:
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        if line.startswith((b" ", b"\t")):  # No obsolete folded headers.
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        return line

    def charge(self, count: int) -> None:
        self.remaining -= count
        if self.remaining < 0:
            raise ResponseRejected(FetchCode.SIZE_LIMIT)

    def close(self) -> None:
        self.stream.close()


class BoundedResponse(HTTPResponse):
    """Use the stdlib parser with an aggregate header/chunk-framing budget."""

    def __init__(
        self,
        sock: socket.socket,
        debuglevel: int = 0,
        method: str | None = None,
        url: str | None = None,
        *,
        header_limit: int,
    ) -> None:
        super().__init__(sock, debuglevel=debuglevel, method=method, url=url)
        self._framing = _HeaderReader(self.fp, header_limit)

    @property
    def remaining_header_bytes(self) -> int:
        """Unused framing budget, shared with the next redirect response."""
        return self._framing.remaining

    def _read_status(self) -> tuple[str, int, str]:
        # CPython hook is absent from typeshed; wire tests exercise it directly.
        version, status, reason = super()._read_status()  # type: ignore[misc]
        if version not in ("HTTP/1.0", "HTTP/1.1") or status < 200:
            # A GET sends no Expect header; don't accept upgrades/interim loops.
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        return version, status, reason

    def begin(self) -> None:
        # begin/parse_headers use only readline/close; the stub insists on the
        # concrete BufferedReader although our bounded adapter provides both.
        self.fp = cast(io.BufferedReader, self._framing)
        try:
            super().begin()
        finally:
            self.fp = self._framing.stream
        if self.headers.defects:
            raise ResponseRejected(FetchCode.HTTP_FAILURE)

    def _read_next_chunk_size(self) -> int:
        line = self._framing.readline()
        # Explicitly reject extensions, signs and non-hex forms the stdlib int
        # parser would tolerate. A huge advertised chunk is still read bounded.
        if not re.fullmatch(rb"[0-9a-fA-F]{1,16}\r\n", line):
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        return int(line[:-2], 16)

    def _read_and_discard_trailer(self) -> None:
        if self._framing.readline() != b"\r\n":
            raise ResponseRejected(FetchCode.HTTP_FAILURE)

    def _get_chunk_left(self) -> int | None:
        if self.chunk_left == 0:
            self._framing.charge(2)
            if self._safe_read(2) != b"\r\n":  # type: ignore[attr-defined]
                raise ResponseRejected(FetchCode.HTTP_FAILURE)
            self.chunk_left = None
        # super handles the size, final trailer and closing the response. We
        # consumed the CRLF above so it cannot silently discard malformed bytes.
        return cast(int | None, super()._get_chunk_left())  # type: ignore[misc]


def _single_header(response: HTTPResponse, name: str) -> str | None:
    values = response.headers.get_all(name, [])
    if len(values) > 1:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    return values[0].strip() if values else None


def redirect_location(response: HTTPResponse) -> str | None:
    """Only the five GET redirect statuses may select one untrusted Location."""
    if not 300 <= response.status < 400:
        return None
    if response.status not in (301, 302, 303, 307, 308):
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    location = _single_header(response, "Location")
    if not location:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    return location


def read_response(
    response: HTTPResponse, request: FetchRequest, limits: FetchLimits
) -> FetchSuccess:
    """Assemble only bounded bytes, never trust a missing/claimed length."""

    if 300 <= response.status < 400:
        raise ResponseRejected(FetchCode.REDIRECT_LIMIT)
    if not 200 <= response.status < 300:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    content_type = _single_header(response, "Content-Type")
    media_type = content_type.split(";", 1)[0].strip().lower() if content_type else ""
    if media_type not in request.accepted_media_types:
        raise ResponseRejected(FetchCode.CONTENT_TYPE)
    if media_type == "text/html":
        # The normalized FetchSuccess omits parameters: refuse non-UTF-8 before
        # losing this declaration rather than silently decoding another charset.
        parameters = content_type.lower().split(";")[1:]
        if len(parameters) > 1:
            raise ResponseRejected(FetchCode.CONTENT_TYPE)
        for parameter in parameters:
            key, sep, value = parameter.strip().partition("=")
            if (
                key.strip() != "charset"
                or not sep
                or value.strip().strip('"') not in {"utf-8", "utf8"}
            ):
                raise ResponseRejected(FetchCode.CONTENT_TYPE)
    encoding = _single_header(response, "Content-Encoding")
    encoding = encoding.lower() if encoding is not None else None
    if encoding is not None and encoding not in ("identity", "gzip"):
        raise ResponseRejected(FetchCode.CONTENT_TYPE)
    transfer = _single_header(response, "Transfer-Encoding")
    length = _single_header(response, "Content-Length")
    if transfer is not None and (transfer.lower() != "chunked" or length is not None):
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    if _single_header(response, "Trailer") is not None:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    expected = None
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,20}", length):
            raise ResponseRejected(FetchCode.HTTP_FAILURE)
        expected = int(length)
        if expected > limits.max_response_bytes:
            raise ResponseRejected(FetchCode.SIZE_LIMIT)
    if response.status == 204 and (transfer is not None or expected not in (None, 0)):
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
    content = bytearray()
    received = 0
    while True:
        # The one-byte probe distinguishes exact-limit EOF from oversized data.
        block = response.read1(min(CHUNK_BYTES, limits.max_response_bytes - received + 1))
        if not block:
            break
        received += len(block)
        if received > limits.max_response_bytes:
            raise ResponseRejected(FetchCode.SIZE_LIMIT)
        if decoder is not None:
            block = decoder.decompress(block, limits.max_decompressed_bytes - len(content) + 1)
            if decoder.unused_data:  # No concatenated gzip members/trailing garbage.
                raise ResponseRejected(FetchCode.HTTP_FAILURE)
        if len(content) + len(block) > limits.max_decompressed_bytes:
            raise ResponseRejected(FetchCode.SIZE_LIMIT)
        content.extend(block)
    if expected is not None and expected != received:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    # Never call an unbounded decoder.flush(); EOF includes checksum validation.
    if decoder is not None and not decoder.eof:
        raise ResponseRejected(FetchCode.HTTP_FAILURE)
    return FetchSuccess(
        source_ref=request.source_ref,
        content=bytes(content),
        media_type=media_type,
        http_status=response.status,
    )
