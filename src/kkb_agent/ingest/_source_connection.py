"""DNS-bound connection primitive used by the bounded source-fetch worker.

Own the stdlib HTTP client's connect hook so neither its initial connection nor
an automatic reconnect can resolve a hostname independently of validation. All
DNS answers are checked, then a numeric address is passed directly to a socket.
TLS still authenticates the original URL hostname, not the resolved IP.

No proxy/environment routing, DNS cache, address retries or redirect following.
M7-05 supervises DNS/connect/total deadlines and bounded responses. M7-04
owns redirect following; the current public fetch path rejects every redirect.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Mapping
from contextlib import suppress
from http.client import HTTPConnection
from typing import NoReturn

from pydantic import SecretStr

from kkb_agent.ingest.safe_fetch import (
    DEFAULT_LIMITS,
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchRequest,
)
from kkb_agent.ingest.url_targets import (
    TargetReason,
    TargetRejection,
    URLTarget,
    validate_redirect_target,
    validate_url_target,
)


class SourceConnectionError(OSError):
    """Connection failure with a safe structured outcome, never raw diagnostics."""

    def __init__(self, failure: FetchFailure) -> None:
        self.failure = failure
        super().__init__(failure.code.value)


class SourceConnection(HTTPConnection):
    """One canonical origin; construction does not perform I/O.

    This is an internal building block for the bounded fetch worker.
    Calling connect does DNS/TCP/TLS but does not send an HTTP request. Callers
    must close the connection and supervise its blocking DNS/total deadline.
    """

    def __init__(self, request: FetchRequest, *, limits: FetchLimits = DEFAULT_LIMITS) -> None:
        self._request = FetchRequest.model_validate(request)
        self._limits = FetchLimits.model_validate(limits)
        target = validate_url_target(
            self._request.url.get_secret_value(), max_url_chars=self._limits.max_url_chars
        )
        self._target = self._checked_target(target)
        super().__init__(
            self._target.hostname, port=self._target.port, timeout=self._limits.connect_seconds
        )

    @property
    def url(self) -> SecretStr:
        return self._target.url

    def _reject(self, code: FetchCode, reason: TargetReason | None = None) -> NoReturn:
        raise SourceConnectionError(
            FetchFailure(source_ref=self._request.source_ref, code=code, target_reason=reason)
        ) from None

    def _checked_target(self, target: URLTarget | TargetRejection) -> URLTarget:
        if isinstance(target, TargetRejection):
            code = FetchCode.INVALID_REQUEST
            if target.reason is TargetReason.URL_TOO_LONG:
                code = FetchCode.SIZE_LIMIT
            elif target.reason in (TargetReason.LOCAL_HOST, TargetReason.NON_PUBLIC_IP):
                code = FetchCode.BLOCKED_DESTINATION
            elif target.reason is TargetReason.INVALID_RESOLUTION:
                code = FetchCode.DNS_FAILURE
            self._reject(code, target.reason)
        return target

    def _resolve(self) -> tuple[str, ...]:
        if self._target.addresses is not None:  # Already checked numeric URL.
            return self._target.addresses
        try:
            records = socket.getaddrinfo(
                self._target.hostname,
                self._target.port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            # Do not reuse resolver-provided ports, scopes or address families.
            # The checked numeric IP will determine the socket family below.
            addresses = tuple(record[4][0] for record in records)
        except TimeoutError:
            self._reject(FetchCode.TIMEOUT)
        except (OSError, ValueError, TypeError, IndexError):
            self._reject(FetchCode.DNS_FAILURE)
        target = self._checked_target(
            validate_url_target(
                self.url.get_secret_value(),
                max_url_chars=self._limits.max_url_chars,
                resolved_addresses=addresses,
            )
        )
        if target.addresses is None:
            self._reject(FetchCode.DNS_FAILURE)
        return target.addresses

    def _check_peer(self, connection: socket.socket, expected: str) -> None:
        peer = connection.getpeername()
        # Exact numeric identity includes the port. No reverse DNS or new lookup.
        try:
            matches = (
                ipaddress.ip_address(peer[0]) == ipaddress.ip_address(expected)
                and peer[1] == self._target.port
                and (len(peer) == 2 or peer[3] == 0)
            )
        except (ValueError, TypeError, IndexError):
            matches = False
        if not matches:
            self._reject(FetchCode.BLOCKED_DESTINATION, TargetReason.PEER_MISMATCH)

    def connect(self) -> None:
        if self.sock is not None:
            return
        # Never delegate to HTTPConnection.connect/create_connection: it would
        # resolve self.host again. Also reject mutated authority/tunnel settings.
        if (
            self.host != self._target.hostname
            or self.port != self._target.port
            # HTTPConnection.__init__ always sets it; typeshed omits private
            # attributes. Read directly so a missing one still fails loudly.
            or self._tunnel_host  # type: ignore[attr-defined]
        ):
            self._reject(FetchCode.INVALID_REQUEST)
        addresses = self._resolve()  # Every answer passes before any socket exists.
        selected = addresses[0]  # No hidden retry/fallback; future driver owns retries.
        ipv6 = ipaddress.ip_address(selected).version == 6
        active: socket.socket | None = None
        try:
            active = socket.socket(
                socket.AF_INET6 if ipv6 else socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP
            )
            active.settimeout(self._limits.connect_seconds)
            endpoint = (
                (selected, self._target.port, 0, 0) if ipv6 else (selected, self._target.port)
            )
            active.connect(endpoint)
            self._check_peer(active, selected)  # Before TLS or any HTTP bytes.
            if self._target.scheme == "https":
                context = ssl.create_default_context()
                if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
                    self._reject(FetchCode.TRANSPORT_FAILURE)
                active = context.wrap_socket(active, server_hostname=self._target.hostname)
                self._check_peer(active, selected)
            active.settimeout(self._limits.read_seconds)
            self.sock = active
        except SourceConnectionError:
            raise
        except TimeoutError:
            self._reject(FetchCode.TIMEOUT)
        except OSError:  # Includes DNS-independent TCP and TLS verification failure.
            self._reject(FetchCode.TRANSPORT_FAILURE)
        finally:
            if self.sock is None and active is not None:
                # Preserve the sanitized failure if the OS also reports a close error.
                with suppress(OSError):
                    active.close()

    def set_tunnel(
        self, host: str, port: int | None = None, headers: Mapping[str, str] | None = None
    ) -> None:
        self._reject(FetchCode.INVALID_REQUEST)

    def redirect_connection(self, location: str) -> SourceConnection:
        """Prepare a fresh destination; M7-04 owns following and hop/loop limits."""

        target = self._checked_target(
            validate_redirect_target(
                self.url.get_secret_value(), location, max_url_chars=self._limits.max_url_chars
            )
        )
        return SourceConnection(
            FetchRequest(
                source_ref=self._request.source_ref,
                url=target.url,
                accepted_media_types=self._request.accepted_media_types,
            ),
            limits=self._limits,
        )
