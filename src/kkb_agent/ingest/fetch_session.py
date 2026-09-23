"""One turn's HTTPS session: what a page's own response set, returned to that page only.

Some public sources serve a document only to a visitor who has just opened the page
listing it. Measured 2026-09-23 on the ODMD market-report page: the listing sets one
cookie (`ASP.NET_SessionId`, `path=/; HttpOnly; SameSite=Lax`), and the same download
address answers with an empty shell without it and with a redirect to the PDF with
it. The redirect's target needs no cookie. A stateless fetcher therefore reads the
page and can never read what the page links to.

The session is the smallest thing that closes that gap, and nothing more:

- **one turn**, never persisted and never shared between conversations,
- **one origin**: scheme, host and port exactly, never a parent domain,
- **HTTPS only**, both where a cookie is set and where it is sent,
- taken from a **final** response only (a redirect's cookies are still refused), and
  sent on the **first** hop only (a redirect never carries it, to any origin),
- **name=value only**: attributes are not honoured beyond `Max-Age=0`, a deletion.

It widens how a site answers, never what may be asked: every request it rides on is
one the turn was already allowed to make. Values are secrets. They cross the fetch
boundary as `SecretStr`, and nothing here logs, traces or shows them to the model.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Final
from urllib.parse import urlsplit

#: Cookies kept for one origin in one turn.
MAX_COOKIES: Final = 16
#: The longest `Cookie` header a turn's session will send, and accept as a set.
MAX_COOKIE_BYTES: Final = 4096

#: RFC 6265 `cookie-name` (an HTTP token) and `cookie-octet`s. Anything else — a
#: control character, a space, a comma, a semicolon, a quote, a backslash — would
#: let a response write the next request's headers, and is dropped.
_NAME: Final = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]{1,128}")
_VALUE: Final = re.compile(r"[\x21\x23-\x2B\x2D-\x3A\x3C-\x5B\x5D-\x7E]{0,1024}")
_PAIR: Final = re.compile(
    r"[!#$%&'*+\-.^_`|~0-9A-Za-z]{1,128}=[\x21\x23-\x2B\x2D-\x3A\x3C-\x5B\x5D-\x7E]{0,1024}"
)


def session_origin(url: str) -> str | None:
    """The exact origin a session belongs to, or None where no session may exist."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return None
    port = parts.port or 443
    return f"https://{parts.hostname.lower()}:{port}"


def set_cookies(headers: Iterable[str]) -> dict[str, str | None]:
    """The name=value pairs a response set; None marks a deletion.

    Every attribute but `Max-Age=0` is ignored, because every one of them would
    widen the session: `Domain` to other hosts, `Path` to nothing useful, an expiry
    past the turn. A pair that is not a well-formed token and cookie value is dropped.
    """
    found: dict[str, str | None] = {}
    for header in headers:
        pair, _, attributes = header.partition(";")
        name, equals, value = pair.strip().partition("=")
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        if not equals or not _NAME.fullmatch(name) or not _VALUE.fullmatch(value):
            continue
        deleted = any(
            item.strip().lower().replace(" ", "") in ("max-age=0", "max-age=-1")
            for item in attributes.split(";")
        )
        found[name] = None if deleted else value
        if len(found) >= MAX_COOKIES:
            break
    return found


def cookie_header(jar: Mapping[str, str]) -> str | None:
    """A `Cookie` header for these pairs, or None when there is nothing to send."""
    header = "; ".join(f"{name}={value}" for name, value in list(jar.items())[:MAX_COOKIES])
    if not header or len(header.encode()) > MAX_COOKIE_BYTES:
        return None
    return header


def well_formed(header: str) -> bool:
    """Whether a `Cookie` value is only well-formed pairs, bounded, with nothing else."""
    if not header or len(header.encode()) > MAX_COOKIE_BYTES:
        return False
    pairs = header.split("; ")
    return len(pairs) <= MAX_COOKIES and all(_PAIR.fullmatch(pair) for pair in pairs)


__all__ = [
    "MAX_COOKIES",
    "MAX_COOKIE_BYTES",
    "cookie_header",
    "session_origin",
    "set_cookies",
    "well_formed",
]
