"""Links a page declares in its markup and spells out in its own same-origin script.

Many listing pages link nothing. A report row there is a table cell with
`onclick="return dRep('?primary_id=6161&type=35')"`, and the address is written in
the site's own script: `function dRep(q) { window.open('wf_docudownload.aspx' + q +
'&downloadfirst=yes') }`. The page names the document by its title and the script
spells out where it lives, yet `page_links` sees no anchor, so a person's own page
offered nothing to follow (live 2026-09-23, the ODMD market-report page).

This module reads that — statically, and only in the one shape where reading is
exact. Nothing is evaluated or executed:

- a handler is read only when it is one call of a named function with **string
  literal** arguments (`onclick` on any element, or an `href="javascript:..."`);
- the function is read only from the page's inline scripts or its **same-origin**
  scripts, at most `MAX_SCRIPTS`, each through the turn's fetcher;
- its body must hold **exactly one** navigation — `window.open(...)`, an assignment
  to `location` or `location.href`, `location.assign(...)`/`replace(...)` — and the
  address must be built from nothing but the function's own string literals and
  parameters joined by `+`;
- and nothing in the body may give a parameter another value first: no assignment,
  increment or re-declaration of it, no `arguments`, no nested function, no `with`,
  no `eval`. Otherwise the call's literal is not what the page opens.

The address is then the literals and the call's arguments in that order, resolved
against the page, and kept only when it is http(s), same-origin and free of
credentials — the same authority an anchor on the page has (`ingest.page_links`).
A function a literal call names but that cannot be read in that shape — defined
nowhere reachable, defined twice, or building its address from anything else — is
reported by name as unresolved. It is never guessed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Final
from urllib.parse import urljoin, urlsplit, urlunsplit

from pydantic import SecretStr

from kkb_agent.ingest.fetched import source_id_for
from kkb_agent.ingest.page_links import MAX_LINKS, MAX_PAGE_BYTES, MAX_TEXT_CHARS, PageLink
from kkb_agent.ingest.safe_fetch import FetchOutcome, FetchRequest, FetchSuccess
from kkb_agent.ingest.url_targets import same_origin

type Fetcher = Callable[[FetchRequest], FetchOutcome]

#: Same-origin scripts read for one page.
MAX_SCRIPTS: Final = 4
SCRIPT_MEDIA_TYPES: Final = ("application/javascript", "text/javascript")
#: Characters of one script read; a larger one is read no further.
MAX_SCRIPT_CHARS: Final = 1_000_000
#: A function body longer than this is not read.
MAX_BODY_CHARS: Final = 20_000

_VOID: Final = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_KEYWORDS: Final = frozenset({"function", "new", "return", "typeof", "void", "delete", "if"})
#: The escapes a string literal may carry and still be read exactly.
_ESCAPES: Final = {"\\": "\\", "'": "'", '"': '"', "/": "/"}
_DEFINITION = re.compile(
    r"\bfunction\s+(?P<a>[A-Za-z_$][A-Za-z0-9_$]*)\s*\((?P<pa>[^)]*)\)\s*\{"
    r"|\b(?P<b>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function\s*\((?P<pb>[^)]*)\)\s*\{"
)
_HOLDER = r"(?:(?:window|self|top|parent|document)\s*\.\s*)?"
_OPEN = re.compile(r"\b(?:window|self|top|parent)\s*\.\s*open\s*\(")
_CALL = re.compile(r"\b" + _HOLDER + r"location\s*\.\s*(?:assign|replace)\s*\(")
_ASSIGN = re.compile(r"\b" + _HOLDER + r"location(?:\s*\.\s*href)?\s*=(?!=)")


@dataclass(frozen=True, slots=True)
class Handler:
    """One literal call a page's markup makes, and the text of the element making it."""

    function: str
    arguments: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class Template:
    """An address as a function builds it: literal text and its own parameters, in order."""

    parts: tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class ScriptedLinks:
    links: tuple[PageLink, ...] = ()
    #: Functions a page calls with literal arguments whose address could not be read.
    unresolved: tuple[str, ...] = ()
    #: Calls whose address was read and then refused: another origin, another scheme,
    #: credentials, or an argument the function needs that the call does not give.
    refused: int = 0


def string_literal(text: str, at: int) -> tuple[str | None, int]:
    """A quoted string starting at `at`, decoded, or None when it cannot be read exactly."""
    if at >= len(text) or text[at] not in "'\"":
        return None, at
    quote, at = text[at], at + 1
    out: list[str] = []
    while at < len(text):
        char = text[at]
        if char == quote:
            return "".join(out), at + 1
        if char == "\\":
            if at + 1 < len(text) and text[at + 1] in _ESCAPES:
                out.append(_ESCAPES[text[at + 1]])
                at += 2
                continue
            return None, at
        if char in "\r\n":
            return None, at
        out.append(char)
        at += 1
    return None, at


def literal_call(code: str) -> tuple[str, tuple[str, ...]] | None:
    """`[return] name('a', "b")[;] [return false;]`, or None for anything else."""
    text = code.strip()
    at = 0

    def skip(position: int) -> int:
        while position < len(text) and text[position] in " \t\r\n":
            position += 1
        return position

    if text.startswith("return") and (len(text) == 6 or not _IDENT.match(text[6])):
        at = 6
    at = skip(at)
    name = _IDENT.match(text, at)
    if name is None or name.group() in _KEYWORDS:
        return None
    at = skip(name.end())
    if at >= len(text) or text[at] != "(":
        return None
    at = skip(at + 1)
    arguments: list[str] = []
    if at < len(text) and text[at] == ")":
        at += 1
    else:
        while True:
            literal, at = string_literal(text, at)
            if literal is None:
                return None
            arguments.append(literal)
            at = skip(at)
            if at < len(text) and text[at] == ",":
                at = skip(at + 1)
                continue
            if at < len(text) and text[at] == ")":
                at += 1
                break
            return None
    rest = " ".join(text[at:].replace(";", " ").split())
    if rest not in ("", "return false", "return true"):
        return None
    return name.group(), tuple(arguments)


class _Scan(HTMLParser):
    """Literal-call handlers with their element text, inline scripts and script sources."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.handlers: list[Handler] = []
        self.inline: list[str] = []
        self.sources: list[str] = []
        self.open: list[tuple[str, str, tuple[str, ...], list[str]]] = []
        self.script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            source = attributes.get("src")
            if source:
                self.sources.append(source)
            else:
                self.script = []
            return
        code = attributes.get("onclick")
        if code is None and tag == "a":
            href = (attributes.get("href") or "").strip()
            if href[:11].lower() == "javascript:":
                code = href[11:]
        if code is None or len(self.handlers) + len(self.open) >= MAX_LINKS:
            return
        call = literal_call(code)
        if call is None:
            return
        if tag in _VOID:
            label = attributes.get("value") or attributes.get("alt") or attributes.get("title")
            self.handlers.append(Handler(call[0], call[1], label or ""))
            return
        self.open.append((tag, call[0], call[1], []))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            if self.script is not None:
                self.inline.append("".join(self.script))
            self.script = None
            return
        if not any(entry[0] == tag for entry in self.open):
            return
        while self.open:
            entry = self.open.pop()
            self._close(entry)
            if entry[0] == tag:
                return

    def handle_data(self, data: str) -> None:
        if self.script is not None:
            self.script.append(data)
            return
        for entry in self.open:
            if sum(len(part) for part in entry[3]) < MAX_TEXT_CHARS:
                entry[3].append(data)

    def _close(self, entry: tuple[str, str, tuple[str, ...], list[str]]) -> None:
        _, function, arguments, parts = entry
        self.handlers.append(Handler(function, arguments, " ".join("".join(parts).split())))

    def close(self) -> None:
        super().close()
        while self.open:
            self._close(self.open.pop())


def _masked(text: str) -> str:
    """The text with string contents and comments blanked, positions kept.

    Definitions and navigations are looked for in this copy, so a quoted
    `"function f() {"` or a commented-out `// window.open(...)` is never taken for code.
    """
    out = list(text)
    at = 0
    while at < len(text):
        char = text[at]
        if char in "'\"`":
            end = at + 1
            while end < len(text) and text[end] != char:
                end += 2 if text[end] == "\\" else 1
            for index in range(at + 1, min(end, len(text))):
                out[index] = " " if text[index] not in "\r\n" else text[index]
            at = end + 1
        elif text.startswith("//", at):
            end = text.find("\n", at)
            end = len(text) if end < 0 else end
            for index in range(at, end):
                out[index] = " "
            at = end
        elif text.startswith("/*", at):
            end = text.find("*/", at + 2)
            end = len(text) if end < 0 else end + 2
            for index in range(at, end):
                out[index] = " " if text[index] not in "\r\n" else text[index]
            at = end
        else:
            at += 1
    return "".join(out)


def _body(masked: str, opening: int) -> tuple[int, int] | None:
    """The span of a function body from its opening brace, or None when it does not close."""
    depth = 0
    for index in range(opening, min(len(masked), opening + MAX_BODY_CHARS)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return opening + 1, index
    return None


def _address(text: str, at: int, parameters: list[str], stops: str) -> tuple[str | int, ...] | None:
    """Literals and parameters joined by `+`, up to a top-level stop, or None."""
    parts: list[str | int] = []
    term = True
    while at < len(text):
        char = text[at]
        if char in "\r\n":
            if not term and ";" in stops:
                break
            at += 1
            continue
        if char in " \t":
            at += 1
            continue
        if not term and char in stops:
            break
        if term:
            if char in "'\"":
                literal, at = string_literal(text, at)
                if literal is None:
                    return None
                parts.append(literal)
                term = False
                continue
            name = _IDENT.match(text, at)
            if name is not None and name.group() in parameters:
                parts.append(parameters.index(name.group()))
                at = name.end()
                term = False
                continue
            return None
        if char == "+":
            term = True
            at += 1
            continue
        return None
    return tuple(parts) if parts and not term else None


#: What in a body could change the value a parameter holds by the time it is used,
#: or make "the parameter" mean something else. Reading the address as the call's
#: literal would then state a target the page never opens: `function openDoc(q) {
#: q = 'actual.pdf'; window.open('/docs/' + q) }` called with 'wrong.pdf' opens
#: /docs/actual.pdf (Codex QA, 2026-09-23). Nothing here is evaluated; a body that
#: does any of these is simply not read.
_OPAQUE: Final = re.compile(r"\b(?:function|arguments|with|eval)\b|=>")


def _rebinds(body: str, parameters: list[str]) -> bool:
    """Whether a (masked) body may give a parameter a value other than the argument."""
    if _OPAQUE.search(body):
        return True
    for name in parameters:
        quoted = re.escape(name)
        if re.search(
            rf"(?<![\w$.]){quoted}\s*(?:\*\*|<<|>>>?|&&|\|\||\?\?|[-+*/%&|^])?=(?!=)"
            rf"|(?:\+\+|--)\s*{quoted}\b|(?<![\w$.]){quoted}\s*(?:\+\+|--)"
            rf"|\b(?:var|let|const)\b[^;]*?(?<![\w$.]){quoted}\b",
            body,
        ):
            return True
    return False


def _template(
    original: str, masked: str, parameters: list[str], span: tuple[int, int]
) -> Template | None:
    """The one navigation in a body as an address template, or None."""
    start, end = span
    body = masked[start:end]
    if _rebinds(body, parameters):
        return None
    found = [
        (match, stops)
        for pattern, stops in ((_OPEN, ",)"), (_CALL, ",)"), (_ASSIGN, ";}"))
        for match in pattern.finditer(body)
    ]
    if len(found) != 1:
        return None
    match, stops = found[0]
    parts = _address(original[start:end], match.end(), parameters, stops)
    return Template(parts) if parts is not None else None


def templates(scripts: Iterable[str], wanted: set[str]) -> dict[str, Template | None]:
    """Each wanted function's address template; None where it cannot be read exactly."""
    found: dict[str, Template | None] = {}
    seen: set[str] = set()
    for script in scripts:
        text = script[:MAX_SCRIPT_CHARS]
        masked = _masked(text)
        for match in _DEFINITION.finditer(masked):
            name = match.group("a") or match.group("b")
            if name not in wanted:
                continue
            listed = (match.group("pa") if match.group("a") else match.group("pb")) or ""
            parameters = [item.strip() for item in listed.split(",") if item.strip()]
            span = _body(masked, match.end() - 1)
            template = (
                _template(text, masked, parameters, span)
                if span is not None and all(_IDENT.fullmatch(item) for item in parameters)
                else None
            )
            # Defined twice is not read: which definition a browser would use depends on
            # load order and scope, and that is exactly what is not being evaluated.
            found[name] = None if name in seen else template
            seen.add(name)
    return found


def _link(handler: Handler, template: Template, page_url: str) -> PageLink | None:
    pieces: list[str] = []
    for part in template.parts:
        if isinstance(part, int):
            if part >= len(handler.arguments):
                return None
            pieces.append(handler.arguments[part])
        else:
            pieces.append(part)
    address = "".join(pieces).strip()
    if not address:
        return None
    absolute = urljoin(page_url, address)
    target = urlsplit(absolute)
    if (
        target.scheme not in ("http", "https")
        or not target.hostname
        or target.username is not None
        or target.password is not None
        or not same_origin(absolute, page_url)
    ):
        return None
    clean = urlunsplit((target.scheme, target.netloc, target.path or "/", target.query, ""))
    return PageLink(clean, handler.text[:MAX_TEXT_CHARS])


def script_links(content: bytes, page_url: str, fetch: Fetcher | None) -> ScriptedLinks:
    """The page's scripted navigation read statically, what was refused and what was not read."""
    if len(content) > MAX_PAGE_BYTES:
        return ScriptedLinks()
    page = urlsplit(page_url)
    if page.scheme not in ("http", "https") or not page.hostname:
        return ScriptedLinks()
    scan = _Scan()
    scan.feed(content.decode("utf-8", "replace"))
    scan.close()
    if not scan.handlers:
        return ScriptedLinks()
    wanted = {handler.function for handler in scan.handlers}
    scripts = list(scan.inline)
    if fetch is not None and not wanted <= set(templates(scripts, wanted)):
        sources = [urljoin(page_url, source.strip()) for source in scan.sources]
        for source in list(dict.fromkeys(s for s in sources if same_origin(s, page_url)))[
            :MAX_SCRIPTS
        ]:
            outcome = fetch(
                FetchRequest(
                    source_ref=source_id_for(source),
                    url=SecretStr(source),
                    accepted_media_types=SCRIPT_MEDIA_TYPES,
                    stay_within_origin=True,
                )
            )
            if isinstance(outcome, FetchSuccess):
                scripts.append(outcome.content[: MAX_SCRIPT_CHARS * 4].decode("utf-8", "replace"))
    read = templates(scripts, wanted)
    links: dict[str, PageLink] = {}
    unresolved: set[str] = set()
    refused = 0
    for handler in scan.handlers:
        template = read.get(handler.function)
        if template is None:
            unresolved.add(handler.function)
            continue
        link = _link(handler, template, page_url)
        if link is None:
            refused += 1
            continue
        kept = links.get(link.url)
        if kept is None or (not kept.text and link.text):
            links[link.url] = link
    return ScriptedLinks(tuple(links.values()), tuple(sorted(unresolved)), refused)


__all__ = [
    "MAX_SCRIPTS",
    "SCRIPT_MEDIA_TYPES",
    "Handler",
    "ScriptedLinks",
    "Template",
    "literal_call",
    "script_links",
    "string_literal",
    "templates",
]
