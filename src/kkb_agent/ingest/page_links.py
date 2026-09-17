"""Links on a page the user gave: the one widening of prompt-address authority.

The organizer's demo pages publish their data behind a link ("Altın İşlemleri"
opens a PDF) or behind a script endpoint, never at the address a user types. An
address the user wrote therefore also authorizes, and only authorizes:

- a link present in the **bytes of that page**, and
- only on the **same site** (registrable domain) as the page the fetch ended on,
- one hop deep: a followed document's own links are never followed.

The model never supplies an address. It names a link by its visible text or its
file name; this module finds exactly one matching link in the page and builds
the absolute address from the page itself. Every resulting request still goes
through `safe_fetch` with its public-destination, redirect and size rules.
Credentials, fragments and other schemes in a link are refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Final
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from kkb_agent.catalog.normalization import normalize_search_text

#: Enough for a large portal page; a page beyond it offers no links rather than a partial list.
MAX_PAGE_BYTES: Final = 4 * 1024 * 1024
MAX_LINKS: Final = 2000
MAX_TEXT_CHARS: Final = 200
#: Second-level labels under which a registrable domain has three labels.
_SECOND_LEVEL: Final = frozenset(
    {"com", "net", "org", "gov", "edu", "gen", "bel", "k12", "av", "bbs", "co", "ac", "or", "go"}
)


class LinkRefused(ValueError):
    """No single same-site link matches; `code` is fixed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PageLink:
    url: str
    text: str


def site_of(host: str) -> str:
    """The registrable domain of a host, conservatively, without a suffix list.

    `www.borsaistanbul.com` -> `borsaistanbul.com`; `evds2.cbrt.gov.tr` ->
    `cbrt.gov.tr`. An IP address or a single-label host is its own site.
    """
    host = host.lower().rstrip(".")
    labels = host.split(".")
    if len(labels) < 2 or re.fullmatch(r"[0-9.]+|\[.*\]", host):
        return host
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, list[str]]] = []
        self.open: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a" and len(self.links) < MAX_LINKS:
            href = dict(attrs).get("href")
            if href:
                self.open = (href, [])

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.open is not None:
            self.links.append(self.open)
            self.open = None

    def handle_data(self, data: str) -> None:
        if self.open is not None and sum(len(part) for part in self.open[1]) < MAX_TEXT_CHARS:
            self.open[1].append(data)


def page_links(content: bytes, page_url: str) -> tuple[PageLink, ...]:
    """Same-site http(s) links of a page, absolute, credential- and fragment-free."""
    if len(content) > MAX_PAGE_BYTES:
        return ()
    page = urlsplit(page_url)
    if page.scheme not in ("http", "https") or not page.hostname:
        return ()
    parser = _Anchors()
    parser.feed(content.decode("utf-8", "replace"))
    parser.close()
    found: dict[str, PageLink] = {}
    for href, parts in parser.links:
        absolute = urljoin(page_url, href.strip())
        target = urlsplit(absolute)
        if (
            target.scheme not in ("http", "https")
            or not target.hostname
            or target.username is not None
            or target.password is not None
            or site_of(target.hostname) != site_of(page.hostname)
        ):
            continue
        clean = urlunsplit((target.scheme, target.netloc, target.path or "/", target.query, ""))
        text = " ".join("".join(parts).split())[:MAX_TEXT_CHARS]
        found.setdefault(clean, PageLink(clean, text))
    return tuple(found.values())


def choose_link(links: tuple[PageLink, ...], wanted: str) -> PageLink:
    """The one link whose visible text or file name matches `wanted`.

    An exact match of the folded text or file name wins over containment, so
    "Altın İşlemleri" does not also pick "Altın İşlemleri Arşivi". Several
    equally good links, or none, refuse rather than pick.
    """
    folded = normalize_search_text(wanted)
    if not folded:
        raise LinkRefused("LINK_NOT_NAMED")

    def names(link: PageLink) -> tuple[str, str]:
        basename = unquote(urlsplit(link.url).path.rsplit("/", 1)[-1])
        return normalize_search_text(link.text), normalize_search_text(basename)

    exact = [link for link in links if folded in names(link)]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise LinkRefused("LINK_AMBIGUOUS")
    partial = [link for link in links if any(folded in name for name in names(link) if name)]
    if len(partial) == 1:
        return partial[0]
    raise LinkRefused("LINK_AMBIGUOUS" if partial else "LINK_NOT_FOUND")
