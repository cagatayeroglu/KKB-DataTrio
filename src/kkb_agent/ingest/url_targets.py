"""Offline M7-02 destination policy, not permission to open a connection.

Only HTTP:80 and HTTPS:443 are approved. DNS names must be ASCII (IDNs must
already use their ASCII form). IPv6 must be native public unicast in 2000::/3;
legacy numeric IP spellings and transition addresses are refused rather than
delegated to a permissive resolver.

Supplied DNS answers are checked as data, never looked up here. M7-03 must bind
resolution to the actual connection and check its peer; M7-04 must call the
redirect validator for every hop and enforce redirect budgets. No live I/O.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urljoin, urlsplit, urlunsplit

from pydantic import SecretStr


class TargetReason(StrEnum):
    """Fixed safe diagnostics; no locator, address or exception text."""

    URL_TOO_LONG = "URL_TOO_LONG"
    MALFORMED_URL = "MALFORMED_URL"
    UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
    URL_CREDENTIALS = "URL_CREDENTIALS"
    INVALID_HOST = "INVALID_HOST"
    UNSAFE_PORT = "UNSAFE_PORT"
    LOCAL_HOST = "LOCAL_HOST"
    AMBIGUOUS_IP = "AMBIGUOUS_IP"
    NON_PUBLIC_IP = "NON_PUBLIC_IP"
    INVALID_RESOLUTION = "INVALID_RESOLUTION"
    HTTPS_DOWNGRADE = "HTTPS_DOWNGRADE"


@dataclass(frozen=True)
class TargetRejection:
    reason: TargetReason


@dataclass(frozen=True)
class URLTarget:
    """Parsed target only; even checked supplied addresses are not a DNS pin.

    None means a DNS name has not had its answers checked. A literal IP has
    a one-address tuple. Locators/hosts/addresses stay out of ordinary repr.
    """

    url: SecretStr = field(repr=False)
    scheme: str
    hostname: str = field(repr=False)
    port: int
    addresses: tuple[str, ...] | None = field(repr=False)


TargetOutcome = URLTarget | TargetRejection
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_NUMERIC_LABEL = re.compile(r"(?:[0-9]+|0x[0-9a-f]+)\Z")
_LOCAL_SUFFIXES = ("localhost", "local", "localdomain", "internal", "home.arpa")
_METADATA_HOSTS = {"metadata", "instance-data", "ip6-localhost", "ip6-loopback"}
_V6_UNICAST = ipaddress.IPv6Network("2000::/3")
# Exclude protocol assignments, 6to4 and documentation independently of the
# Python minor version's special-address table. NAT64/mapped/local IPv6 also
# fall outside the approved global-unicast range.
_V6_SPECIAL = tuple(ipaddress.IPv6Network(cidr) for cidr in ("2001::/23", "2002::/16", "3fff::/20"))
_V4_SPECIAL = tuple(
    ipaddress.IPv4Network(cidr) for cidr in ("192.0.0.0/24", "192.88.99.0/24", "168.63.129.16/32")
)


def _public_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if not address.is_global or any(
        (address.is_multicast, address.is_reserved, address.is_loopback, address.is_link_local)
    ):
        return False
    if isinstance(address, ipaddress.IPv6Address):
        return address in _V6_UNICAST and not any(address in net for net in _V6_SPECIAL)
    return not any(address in net for net in _V4_SPECIAL)


def _bad_url_characters(value: str) -> bool:
    return any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\" for char in value
    )


def validate_url_target(
    url: str,
    *,
    max_url_chars: int = 4096,
    resolved_addresses: tuple[str, ...] | None = None,
) -> TargetOutcome:
    """Validate one URL and, optionally, *all* supplied resolver answers.

    This never calls DNS. Empty, malformed or non-public answer sets fail
    closed; mixed public/private answers cannot be filtered into acceptance.
    The caller must use the returned canonical authority, not reparse the raw
    input using a more permissive network client. Live fetch remains disabled.
    """

    if type(max_url_chars) is not int or max_url_chars <= 0:
        raise ValueError("max_url_chars must be a positive integer")
    if not isinstance(url, str) or not url:
        return TargetRejection(TargetReason.MALFORMED_URL)
    if len(url) > max_url_chars:
        return TargetRejection(TargetReason.URL_TOO_LONG)
    if _bad_url_characters(url):
        return TargetRejection(TargetReason.MALFORMED_URL)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return TargetRejection(TargetReason.MALFORMED_URL)
    if parsed.scheme not in ("http", "https"):
        return TargetRejection(TargetReason.UNSUPPORTED_SCHEME)
    authority = parsed.netloc
    if "@" in authority:
        return TargetRejection(TargetReason.URL_CREDENTIALS)
    if not authority or not authority.isascii() or "%" in authority:
        return TargetRejection(TargetReason.INVALID_HOST)

    bracketed = authority.startswith("[")
    if bracketed:
        host, closing, tail = authority[1:].partition("]")
        if not closing or (tail and not tail.startswith(":")):
            # Match newer urlsplit versions that already reject this syntax.
            return TargetRejection(TargetReason.MALFORMED_URL)
        explicit_port, port_text = bool(tail), tail[1:]
    else:
        host, separator, port_text = authority.partition(":")
        explicit_port = bool(separator)
    port = 443 if parsed.scheme == "https" else 80
    if explicit_port and (not port_text.isascii() or not port_text.isdecimal()):
        return TargetRejection(TargetReason.UNSAFE_PORT)
    # Exact spelling avoids integer parsing limits and alternate-port syntax.
    if explicit_port and port_text != str(port):
        return TargetRejection(TargetReason.UNSAFE_PORT)

    host = host.lower()
    # A single DNS root dot is canonicalized; repeated dots remain malformed.
    if not bracketed and host.endswith("."):
        host = host[:-1]
    if not host:
        return TargetRejection(TargetReason.INVALID_HOST)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if bracketed != isinstance(literal, ipaddress.IPv6Address):
        return TargetRejection(TargetReason.INVALID_HOST)
    if literal is not None:
        if not _public_ip(literal):
            return TargetRejection(TargetReason.NON_PUBLIC_IP)
        host = str(literal)
    else:
        if host in _METADATA_HOSTS or any(
            host == suffix or host.endswith("." + suffix) for suffix in _LOCAL_SUFFIXES
        ):
            return TargetRejection(TargetReason.LOCAL_HOST)
        labels = host.split(".")
        if all(_NUMERIC_LABEL.fullmatch(label) for label in labels):
            return TargetRejection(TargetReason.AMBIGUOUS_IP)
        if len(host) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(x) for x in labels):
            return TargetRejection(TargetReason.INVALID_HOST)
        # Numeric final labels can invoke legacy IPv4 parsing in URL clients.
        if _NUMERIC_LABEL.fullmatch(labels[-1]):
            return TargetRejection(TargetReason.AMBIGUOUS_IP)

    addresses = (str(literal),) if literal is not None else None
    if resolved_addresses is not None:
        if not isinstance(resolved_addresses, tuple) or not resolved_addresses:
            return TargetRejection(TargetReason.INVALID_RESOLUTION)
        checked = []
        for answer in resolved_addresses:
            if not isinstance(answer, str) or "%" in answer:
                return TargetRejection(TargetReason.INVALID_RESOLUTION)
            try:
                address = ipaddress.ip_address(answer)
            except ValueError:
                return TargetRejection(TargetReason.INVALID_RESOLUTION)
            if not _public_ip(address):
                return TargetRejection(TargetReason.NON_PUBLIC_IP)
            if literal is not None and address != literal:
                return TargetRejection(TargetReason.INVALID_RESOLUTION)
            checked.append(str(address))
        addresses = tuple(dict.fromkeys(checked))

    canonical_host = f"[{host}]" if bracketed else host
    canonical_url = urlunsplit((parsed.scheme, canonical_host, parsed.path, parsed.query, ""))
    return URLTarget(SecretStr(canonical_url), parsed.scheme, host, port, addresses)


def validate_redirect_target(
    current_url: str,
    location: str,
    *,
    max_url_chars: int = 4096,
    resolved_addresses: tuple[str, ...] | None = None,
) -> TargetOutcome:
    """Resolve a Location as data and revalidate it, without following it.

    Supplied addresses belong to the *new* destination. Hop/loop budgets,
    credential/header handling and connection checks remain M7-03/04 work.
    """

    current = validate_url_target(current_url, max_url_chars=max_url_chars)
    if isinstance(current, TargetRejection):
        return current
    if not isinstance(location, str) or not location:
        return TargetRejection(TargetReason.MALFORMED_URL)
    if len(location) > max_url_chars:
        return TargetRejection(TargetReason.URL_TOO_LONG)
    if _bad_url_characters(location):
        return TargetRejection(TargetReason.MALFORMED_URL)
    # Do not let urljoin reinterpret a malformed absolute URL as a relative one.
    try:
        relative = urlsplit(location)
        if (relative.scheme or location.startswith("//")) and not relative.netloc:
            return TargetRejection(TargetReason.MALFORMED_URL)
        destination = urljoin(current.url.get_secret_value(), location)
    except ValueError:
        return TargetRejection(TargetReason.MALFORMED_URL)
    target = validate_url_target(
        destination, max_url_chars=max_url_chars, resolved_addresses=resolved_addresses
    )
    if isinstance(target, URLTarget) and current.scheme == "https" and target.scheme != "https":
        return TargetRejection(TargetReason.HTTPS_DOWNGRADE)
    return target
