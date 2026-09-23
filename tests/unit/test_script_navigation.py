"""Scripted navigation read statically, and the one-turn session that reaches its target.

The page shape here is the ODMD market-report page's own, rebuilt by hand rather
than copied: the whole body in one WebForms `<form>`, a report list whose rows
alternate three cells with a one-cell separator, each title a `<td onclick>` calling
`dRep` with a literal query, and `dRep` defined in the site's own script as a single
`window.open` of a literal path plus its argument plus a literal suffix. The
download address answers with an empty shell unless the listing's session cookie
comes with it, as measured live on 2026-09-23.
"""

from __future__ import annotations

import socket
import ssl

import pytest
from pydantic import SecretStr, ValidationError
from test_bounded_fetch import PUBLIC, wire
from test_safe_redirects import RedirectTransport, redirect

from kkb_agent.agent.executor import ExecutionContext, ToolStatus
from kkb_agent.ingest import _fetch_worker
from kkb_agent.ingest.address_outline import TurnFetchCache
from kkb_agent.ingest.fetch_session import cookie_header, session_origin, set_cookies
from kkb_agent.ingest.page_links import choose_link, page_links
from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchRequest,
    FetchSuccess,
)
from kkb_agent.ingest.script_navigation import (
    SCRIPT_MEDIA_TYPES,
    literal_call,
    script_links,
    templates,
)
from kkb_agent.tools import WebUrlArguments, make_web_url_tool

SITE = "https://reports.example.test"
PAGE = f"{SITE}/web_1/list.aspx?type=35"
SCRIPT = f"{SITE}/web_1/project.js?2"
DOWNLOAD = f"{SITE}/web_1/download.aspx"
TITLE = "2026 Ağustos Pazar Değerlendirme"


def listing(*, script_src: str = "../web_1/project.js?2", extra: str = "") -> bytes:
    rows = "".join(
        f'<tr class="rep"><td><input type="radio" onclick="sRep({number})"/></td>'
        f"<td onclick=\"return dRep('?primary_id={number}&type=35')\">{title}</td>"
        f"<td onclick=\"return dRep('?primary_id={number}&type=35')\"><img src=\"pdf.png\"/></td>"
        f'</tr><tr class="sep"><td></td></tr>'
        for number, title in ((6161, TITLE), (6145, "2026 Temmuz Pazar Değerlendirme"))
    )
    return (
        f'<html><head><script src="{script_src}"></script></head><body>'
        f'<form name="Form1" method="post"><div><a href="/web_1/about.aspx">Hakkımızda</a>'
        f'<table id="TableReports">{rows}</table>{extra}</div></form></body></html>'
    ).encode()


PROJECT_JS = b"""
function dRep(querystring) {
    window.open('download.aspx' + querystring + '&downloadfirst=yes', '', 'width=600');
    return false;
}
// window.open('decoy.aspx' + querystring)  -- a comment is not code
function sRep(reportId) {
    document.getElementById('selected').value = reportId;
    return false;
}
"""


class Site:
    """The measured behaviour: a session from the listing unlocks the download."""

    def __init__(self, script: bytes = PROJECT_JS, page: bytes | None = None):
        self.script = script
        self.page = page or listing()
        self.requests: list[tuple[str, str | None, bool]] = []

    def __call__(self, request: FetchRequest):
        url = request.url.get_secret_value()
        cookie = request.cookie.get_secret_value() if request.cookie is not None else None
        self.requests.append((url, cookie, request.stay_within_origin))
        if url == PAGE:
            return FetchSuccess(
                source_ref=request.source_ref,
                content=self.page,
                media_type="text/html",
                http_status=200,
                set_cookie=SecretStr("SessionId=synthetic-session-value"),
            )
        if url == SCRIPT and request.accepted_media_types == SCRIPT_MEDIA_TYPES:
            return FetchSuccess(
                source_ref=request.source_ref,
                content=self.script,
                media_type="application/javascript",
                http_status=200,
            )
        if url.startswith(DOWNLOAD):
            unlocked = cookie == "SessionId=synthetic-session-value"
            body = b"<html><body><p>REPORT-BODY 81.031</p></body></html>" if unlocked else b""
            return FetchSuccess(
                source_ref=request.source_ref,
                content=body or b"<html><body></body></html>",
                media_type="text/html",
                http_status=200,
            )
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.HTTP_FAILURE)


# ---------------------------------------------------------------- reading handlers


@pytest.mark.parametrize(
    "code, expected",
    [
        ("return dRep('?id=1&t=2')", ("dRep", ("?id=1&t=2",))),
        ('openDoc("a.pdf"); return false;', ("openDoc", ("a.pdf",))),
        ("go('x', \"y\")", ("go", ("x", "y"))),
        ("go()", ("go", ())),
        ("go('it\\'s')", ("go", ("it's",))),
    ],
)
def test_a_literal_call_is_read(code, expected):
    assert literal_call(code) == expected


@pytest.mark.parametrize(
    "code",
    [
        "dRep(this.id)",  # an argument that is not a literal
        "dRep('a' + b)",  # an expression
        "dRep('\\x41')",  # an escape not decoded statically
        "a(); b()",  # more than one call
        "new Report('x')",
        "window.open('x')",  # a property call, not a named function
        "dRep('unterminated)",
    ],
)
def test_anything_but_one_literal_call_is_not_read(code):
    assert literal_call(code) is None


# ---------------------------------------------------------------- reading templates


def test_the_measured_shape_is_resolved_from_the_same_origin_script():
    site = Site()
    found = script_links(site.page, PAGE, site)
    assert [link.text for link in found.links] == [TITLE, "2026 Temmuz Pazar Değerlendirme"]
    first = found.links[0].url
    assert first == f"{DOWNLOAD}?primary_id=6161&type=35&downloadfirst=yes"
    # sRep is called with a number, not a string literal, so it is not read at all.
    assert found.unresolved == () and found.refused == 0
    # The script was asked for as a script, and bound to the page's origin.
    assert (SCRIPT, None, True) in site.requests
    # A person names the report by its title; exactly that row is chosen.
    chosen = choose_link((*page_links(site.page, PAGE), *found.links), TITLE)
    assert chosen.url == first


def test_an_inline_definition_needs_no_fetch():
    page = listing(extra="<script>" + PROJECT_JS.decode() + "</script>")
    asked: list[str] = []

    def fetch(request):
        asked.append(request.url.get_secret_value())
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.HTTP_FAILURE)

    found = script_links(page, PAGE, fetch)
    assert found.links and asked == []


@pytest.mark.parametrize(
    "body",
    [
        "location.href = '/docs/' + name + '.pdf';",
        "window.location = '/docs/' + name + '.pdf'",
        "document.location.href = '/docs/' + name + '.pdf'\n  track(name)",
        "location.assign('/docs/' + name + '.pdf');",
    ],
)
def test_every_plain_navigation_form_is_read(body):
    page = (
        b"<html><body><a href=\"javascript:openDoc('q1')\">Rapor Q1</a>"
        b"<script>function openDoc(name) { " + body.encode() + b" }</script></body></html>"
    )
    found = script_links(page, PAGE, None)
    assert [(link.text, link.url) for link in found.links] == [("Rapor Q1", f"{SITE}/docs/q1.pdf")]


@pytest.mark.parametrize(
    "definition",
    [
        # Built from a variable: its value is not in the text.
        "function dRep(q) { window.open(base + q); }",
        # Built by a call.
        "function dRep(q) { window.open(build(q)); }",
        # Two navigations: which one runs is not read.
        "function dRep(q) { if (x) window.open('a' + q); else location.href = 'b' + q; }",
        # No navigation at all.
        "function dRep(q) { return q; }",
        # A template literal with a substitution.
        "function dRep(q) { window.open(`download.aspx${q}`); }",
        # Defined twice.
        "function dRep(q) { window.open('a' + q); } function dRep(q) { window.open('b' + q); }",
    ],
)
def test_a_target_that_cannot_be_read_exactly_is_reported_by_name(definition):
    site = Site(script=definition.encode())
    found = script_links(site.page, PAGE, site)
    assert found.links == ()
    assert found.unresolved == ("dRep",)


def test_a_function_defined_nowhere_reachable_is_reported():
    site = Site(script=b"function other() {}")
    assert script_links(site.page, PAGE, site).unresolved == ("dRep",)


def test_an_address_leaving_the_page_origin_is_refused_and_counted():
    site = Site(script=b"function dRep(q) { window.open('https://elsewhere.test/d' + q); }")
    found = script_links(site.page, PAGE, site)
    assert found.links == () and found.refused == 4 and found.unresolved == ()


def test_a_script_from_another_origin_is_never_fetched():
    site = Site()
    site.page = listing(script_src="https://cdn.elsewhere.test/project.js")
    found = script_links(site.page, PAGE, site)
    assert found.unresolved == ("dRep",)
    assert all(url.startswith(SITE) for url, _, _ in site.requests)
    assert site.requests == []


def test_a_navigation_in_a_comment_or_string_is_not_code():
    found = templates([PROJECT_JS.decode()], {"dRep"})
    parts = found["dRep"].parts if found["dRep"] is not None else ()
    assert parts == ("download.aspx", 0, "&downloadfirst=yes")


# ---------------------------------------------------------------- the one-turn session


def test_a_session_set_by_a_page_returns_only_to_that_origin():
    site = Site()
    cache = TurnFetchCache(site, pause=lambda _: None)
    cache.get(PAGE, ("text/html",))
    cache.get(f"{DOWNLOAD}?primary_id=6161", ("text/html",), stay_within_origin=True)
    cache.get("https://other.example.test/x", ("text/html",))
    sent = {url: cookie for url, cookie, _ in site.requests}
    assert sent[PAGE] is None
    assert sent[f"{DOWNLOAD}?primary_id=6161"] == "SessionId=synthetic-session-value"
    assert sent["https://other.example.test/x"] is None
    # The log says a session was used, never what it held.
    assert [entry["session"] for entry in cache.log] == [False, True, False]
    assert "synthetic-session-value" not in repr(cache.log) + repr(cache)


def test_no_session_exists_over_http():
    assert session_origin("http://reports.example.test/a") is None
    with pytest.raises(ValidationError):
        FetchRequest(
            source_ref="s",
            url=SecretStr("http://reports.example.test/a"),
            accepted_media_types=("text/html",),
            cookie=SecretStr("a=b"),
        )


def test_origin_is_exact_host_and_port():
    assert session_origin("https://A.example.test/x") == "https://a.example.test:443"
    assert session_origin("https://a.example.test:8443/x") != session_origin(
        "https://a.example.test/x"
    )
    assert session_origin("https://sub.a.example.test/x") != session_origin(
        "https://a.example.test/x"
    )


@pytest.mark.parametrize(
    "header",
    [
        "a=b\r\nX-Injected: 1",
        "a=b; c",
        'a="b c"',
        "a=b,c",
        "=b",
        "a b=c",
    ],
)
def test_a_malformed_cookie_is_dropped_or_refused(header):
    assert set_cookies([header]) in ({}, {"a": "b"})
    with pytest.raises(ValidationError):
        FetchRequest(
            source_ref="s",
            url=SecretStr("https://a.example.test/"),
            accepted_media_types=("text/html",),
            cookie=SecretStr(header),
        )


def test_attributes_do_not_widen_the_session_and_max_age_zero_deletes():
    pairs = set_cookies(
        ["s=1; Domain=example.test; Path=/; Secure; HttpOnly", "t=2", "t=; Max-Age=0"]
    )
    assert pairs == {"s": "1", "t": None}
    assert cookie_header({"s": "1"}) == "s=1"


def test_a_cookie_never_appears_in_a_repr_or_an_export():
    request = FetchRequest(
        source_ref="s",
        url=SecretStr("https://a.example.test/"),
        accepted_media_types=("text/html",),
        cookie=SecretStr("s=secret-value"),
    )
    success = FetchSuccess(
        source_ref="s",
        content=b"",
        media_type="text/html",
        http_status=200,
        set_cookie=SecretStr("s=secret-value"),
    )
    for item in (request, success):
        assert "secret-value" not in repr(item)
        assert "secret-value" not in item.model_dump_json()


# ---------------------------------------------------------------- the product path


def test_the_listed_report_is_followed_by_its_title_with_the_turn_session():
    """The whole A3 path at tool level: read the page, name the row, get the document."""
    site = Site()
    tool = make_web_url_tool(fetch=TurnFetchCache(site, pause=lambda _: None))
    context = ExecutionContext(PAGE)
    page = tool.run(WebUrlArguments(url=PAGE), context)
    assert page.status is ToolStatus.SUCCESS
    assert TITLE in [link.text for link in page.output.links]
    context.outputs["a1"] = page.output
    report = tool.run(WebUrlArguments(read_from="a1", follow=TITLE), context)
    assert report.status is ToolStatus.SUCCESS, report
    assert "REPORT-BODY 81.031" in report.output.document.text
    assert report.output.followed_text == TITLE
    download = [item for item in site.requests if item[0].startswith(DOWNLOAD)]
    assert download == [
        (
            f"{DOWNLOAD}?primary_id=6161&type=35&downloadfirst=yes",
            "SessionId=synthetic-session-value",
            True,
        )
    ]


def test_the_same_path_in_one_call_with_the_address_and_follow():
    site = Site()
    tool = make_web_url_tool(fetch=TurnFetchCache(site, pause=lambda _: None))
    report = tool.run(WebUrlArguments(url=PAGE, follow=TITLE), ExecutionContext(PAGE))
    assert report.status is ToolStatus.SUCCESS, report
    assert "REPORT-BODY" in report.output.document.text


def test_without_the_session_the_download_is_the_empty_shell():
    """What a stateless fetcher got: the product fails openly rather than inventing."""
    site = Site()
    tool = make_web_url_tool(fetch=site)
    report = tool.run(WebUrlArguments(url=PAGE, follow=TITLE), ExecutionContext(PAGE))
    assert report.status is ToolStatus.FAILURE
    assert report.output.code == "NO_STATIC_CONTENT"


def test_an_unreadable_script_is_said_on_the_page_output():
    site = Site(script=b"function dRep(q) { window.open(base + q); }")
    tool = make_web_url_tool(fetch=TurnFetchCache(site, pause=lambda _: None))
    page = tool.run(WebUrlArguments(url=PAGE), ExecutionContext(PAGE))
    assert page.output.unresolved_navigation == ("dRep",)
    assert TITLE not in [link.text for link in page.output.links]


# ---------------------------------------------------------------- the wire


@pytest.fixture
def network(monkeypatch):
    fake = RedirectTransport()
    monkeypatch.setattr(socket, "getaddrinfo", fake.resolve)
    monkeypatch.setattr(socket, "socket", fake.socket)

    def wrap(context, sock, *, server_hostname):
        fake.tls.append(server_hostname)
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    return fake


def cookie_request(url: str) -> FetchRequest:
    return FetchRequest(
        source_ref="source:cookie-1",
        url=SecretStr(url),
        accepted_media_types=("text/csv",),
        cookie=SecretStr("SessionId=synthetic-session-value"),
    )


def test_the_cookie_goes_on_the_first_hop_and_never_on_a_redirect(network):
    network.responses = [redirect("/final"), wire(b"date,value\n2026-01-01,1\n")]
    outcome = _fetch_worker.fetch_once(
        cookie_request("https://example.test/start"), FetchLimits(), lambda: None
    )
    assert isinstance(outcome, FetchSuccess)
    first, second = network.sockets[0].sent[0], network.sockets[1].sent[0]
    assert b"Cookie: SessionId=synthetic-session-value" in first
    assert b"Cookie" not in second


def test_only_the_final_response_cookies_are_kept(network):
    network.responses = [
        redirect("/final", extra=[("Set-Cookie", "hop=from-redirect; Path=/")]),
        wire(
            b"date,value\n2026-01-01,1\n",
            headers=[
                ("Content-Type", "text/csv"),
                ("Set-Cookie", "SessionId=fresh; path=/; HttpOnly; SameSite=Lax"),
            ],
        ),
    ]
    outcome = _fetch_worker.fetch_once(
        FetchRequest(
            source_ref="source:cookie-2",
            url=SecretStr("https://example.test/start"),
            accepted_media_types=("text/csv",),
        ),
        FetchLimits(),
        lambda: None,
    )
    assert isinstance(outcome, FetchSuccess)
    assert outcome.set_cookie is not None
    assert outcome.set_cookie.get_secret_value() == "SessionId=fresh"
    assert PUBLIC  # the harness resolves every host to one public address


# ---------------------------------------------------------------- Codex QA, draft 03:30


def test_simple_literal_parameter_navigation_is_discovered():
    html = b"""<script>function openDoc(q){window.open('/docs/'+q);}</script>
    <button onclick="openDoc('report.pdf')">Report</button>"""
    result = script_links(html, "https://example.com/list", None)
    assert [link.url for link in result.links] == ["https://example.com/docs/report.pdf"]


def test_reassigned_parameter_is_not_reported_as_exact_original_target():
    html = b"""<script>function openDoc(q){q='actual.pdf'; window.open('/docs/'+q);}</script>
    <button onclick="openDoc('wrong.pdf')">Report</button>"""
    result = script_links(html, "https://example.com/list", None)
    assert not result.links, result
    assert "openDoc" in result.unresolved


@pytest.mark.parametrize(
    "body",
    [
        "q += '.pdf'; window.open('/docs/' + q);",
        "q = q.trim(); window.open('/docs/' + q);",
        "q++; window.open('/docs/' + q);",
        "var q = 'x'; window.open('/docs/' + q);",
        "let a = 1, q = 'x'; window.open('/docs/' + q);",
        "arguments[0] = 'x'; window.open('/docs/' + q);",
        "var f = function () { q = 'x'; }; f(); window.open('/docs/' + q);",
        "[1].forEach(() => { q = 'x'; }); window.open('/docs/' + q);",
        "with (o) { window.open('/docs/' + q); }",
        "eval(\"q='x'\"); window.open('/docs/' + q);",
    ],
)
def test_any_way_a_body_may_rebind_its_parameter_is_not_read(body):
    html = (
        "<script>function openDoc(q){" + body + "}</script>"
        "<button onclick=\"openDoc('wrong.pdf')\">Report</button>"
    ).encode()
    result = script_links(html, "https://example.com/list", None)
    assert result.links == () and result.unresolved == ("openDoc",)


@pytest.mark.parametrize(
    "body",
    [
        # A property of the same name is not the parameter.
        "o.q = 1; window.open('/docs/' + q);",
        # A comparison is not an assignment.
        "if (q == '') { return; } window.open('/docs/' + q);",
        # A string that says so is not code.
        "log('q = changed'); window.open('/docs/' + q);",
    ],
)
def test_what_only_looks_like_a_rebinding_is_still_read(body):
    html = (
        "<script>function openDoc(q){" + body + "}</script>"
        "<button onclick=\"openDoc('report.pdf')\">Report</button>"
    ).encode()
    result = script_links(html, "https://example.com/list", None)
    assert [link.url for link in result.links] == ["https://example.com/docs/report.pdf"]
