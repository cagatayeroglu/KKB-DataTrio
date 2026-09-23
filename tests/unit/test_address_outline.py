"""A script-driven page: its data endpoint is found from its own scripts; no network."""

import json
from datetime import date

import pytest

from kkb_agent.ingest.address_outline import TurnFetchCache, address_outline
from kkb_agent.ingest.json_table import JsonRejected, load_records
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchSuccess
from kkb_agent.tools._document_column import ColumnRefused
from kkb_agent.tools._document_table import daily_rule_in_question, read_daily_table
from kkb_agent.tools._document_value import Grid

PAGE_URL = "https://www.borsa.example.tr/endeks/xtumy"
PAGE = b"""<html><head><script src="/file/js/app.js?v=1"></script>
<script src="https://cdn.other.example/evil.js"></script></head>
<body><h1>BIST TUM-100</h1></body></html>"""
SCRIPT = (
    b"var a='/graphic.php?veriTuru=endeks-graphic&indexCode='+id;"
    b"var b='/graphic.php?veriTuru=current-before&indexCode='+id;"
)


def daily(start=date(2026, 5, 27), days=110, level=100.0):
    rows = []
    for offset in range(days):
        day = date.fromordinal(start.toordinal() + offset)
        rows.append({"indexName": "XTUMY", "clval": level + offset, "hisTs": day.isoformat()})
    return json.dumps({"status": "success", "data": rows}).encode()


class Site:
    def __init__(self, pages):
        self.pages, self.requests = pages, []

    def __call__(self, request):
        url = request.url.get_secret_value()
        self.requests.append(url)
        if url not in self.pages:
            return FetchFailure(source_ref=request.source_ref, code="HTTP_FAILURE")
        content, media_type = self.pages[url]
        if media_type not in request.accepted_media_types:
            return FetchFailure(source_ref=request.source_ref, code="CONTENT_TYPE")
        return FetchSuccess(
            source_ref=request.source_ref, content=content, media_type=media_type, http_status=200
        )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def site():
    base = "https://www.borsa.example.tr"
    return Site(
        {
            PAGE_URL: (PAGE, "text/html"),
            f"{base}/file/js/app.js?v=1": (SCRIPT, "application/javascript"),
            f"{base}/graphic.php?veriTuru=endeks-graphic&indexCode=XTUMY": (
                daily(),
                "application/json",
            ),
            f"{base}/graphic.php?veriTuru=current-before&indexCode=XTUMY": (
                b'{"data": {"value": "1"}}',
                "application/json",
            ),
        }
    )


def test_a_script_endpoint_is_outlined_with_keys_and_dates_but_no_values():
    served = site()
    cache = TurnFetchCache(served)
    note = address_outline((PAGE_URL,), cache)
    payload = json.loads(note[note.index("{") :])
    (endpoint,) = payload["pages"][0]["data_endpoints"]
    assert endpoint["name"] == "endpoint_1" and endpoint["keys"] == ["indexName", "clval", "hisTs"]
    assert endpoint["date_key"] == {"key": "hisTs", "first": "2026-05-27", "last": "2026-09-13"}
    assert "100.0" not in note and "evil" not in " ".join(served.requests)
    assert cache.endpoints == {
        "endpoint_1": "https://www.borsa.example.tr/graphic.php?veriTuru=endeks-graphic&indexCode=XTUMY"
    }
    # The same bytes are reused within the turn: a second outline makes no request.
    before = len(served.requests)
    address_outline((PAGE_URL,), cache)
    assert len(served.requests) == before


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"not json", "MALFORMED_DOCUMENT"),
        (b'{"a": [{"x": 1}, {"x": 2}], "b": [{"y": 1}, {"y": 2}]}', "AMBIGUOUS_TABLE"),
        (b'[{"x": {"nested": 1}}, {"x": 2}]', "UNSUPPORTED_TABLE"),
        (b'{"data": {"value": 1}}', "NO_RECORD_TABLE"),
        (b"[" * 20 + b"]" * 20, "LIMIT_EXCEEDED"),
    ],
)
def test_json_that_is_not_one_flat_record_table_is_refused(content, code):
    with pytest.raises(JsonRejected) as refused:
        load_records(content)
    assert refused.value.code == code


def grid(payload):
    table = load_records(payload)
    return Grid({"endpoint": 1}, table.headers, table.rows)


def test_daily_rows_become_complete_months_by_the_rule_the_user_asked_for():
    rows = grid(daily())
    table = read_daily_table([rows], "hisTs", ["clval"], rule="last", as_of=date(2026, 9, 14))
    # May 27 .. Sep 13: May is incomplete at its start but ended; September has not ended.
    assert table.months == (
        date(2026, 5, 31),
        date(2026, 6, 30),
        date(2026, 7, 31),
        date(2026, 8, 31),
    )
    values = [value for _, value, _ in table.columns[0].cells]
    assert values == [104.0, 134.0, 165.0, 196.0]  # last day of each month
    assert table.aggregation["incomplete_months_left_out"] == ["2026-09-30"]
    assert table.aggregation["days_per_month"]["2026-06-30"] == 30
    mean = read_daily_table([rows], "hisTs", ["clval"], rule="mean", as_of=date(2026, 9, 14))
    assert [value for _, value, _ in mean.columns[0].cells][1] == pytest.approx(119.5)


@pytest.mark.parametrize(
    ("rule", "question", "asked"),
    [
        ("last", "XTUMY ay sonu değerlerini al", True),
        ("mean", "aylık ortalamasını hesapla", True),
        ("sum", "toplam konut kredisi ile karşılaştır", False),
        ("sum", "aylık toplamını al", True),
        ("last", "aylık değerleri al", False),
    ],
)
def test_the_monthly_rule_must_be_written_in_the_question(rule, question, asked):
    assert daily_rule_in_question(rule, question) is asked


def test_duplicate_or_unreadable_days_refuse_the_table():
    doubled = json.dumps(
        {"data": [{"d": "2026-06-01", "v": 1}, {"d": "2026-06-01", "v": 2}, {"d": "x", "v": 3}]}
    ).encode()
    with pytest.raises(ColumnRefused):
        read_daily_table([grid(doubled)], "d", ["v"], rule="last", as_of=date(2026, 9, 1))


def test_a_script_or_endpoint_on_another_subdomain_is_never_read():
    """DEC-150 amendment: the page delegates to its own origin, not to its domain."""
    page = (
        b'<html><head><script src="https://cdn.borsa.example.tr/app.js"></script>'
        b'<script src="/file/js/app.js?v=1"></script></head><body></body></html>'
    )
    base = "https://www.borsa.example.tr"
    served = site()
    served.pages[PAGE_URL] = (page, "text/html")
    served.pages["https://cdn.borsa.example.tr/app.js"] = (SCRIPT, "application/javascript")
    cache = TurnFetchCache(served)

    outline = address_outline((PAGE_URL,), cache)

    assert outline is not None and "endpoint_1" in outline
    assert "cdn.borsa.example.tr" not in " ".join(served.requests)
    # Its own script is read, and only same-origin endpoint addresses are fetched.
    assert f"{base}/file/js/app.js?v=1" in served.requests


def test_every_delegated_fetch_is_bound_to_the_page_origin():
    """A script or endpoint request may not be redirected out of the origin."""
    delegated: list[tuple[str, bool]] = []

    class Recording(Site):
        def __call__(self, request):
            delegated.append((request.url.get_secret_value(), request.stay_within_origin))
            return super().__call__(request)

    served = Recording(site().pages)
    address_outline((PAGE_URL,), TurnFetchCache(served))

    bound = dict(delegated)
    assert bound[PAGE_URL] is False  # the address a person wrote is not delegated
    assert all(value for url, value in bound.items() if url != PAGE_URL)


class Flaky(Site):
    """The first read of chosen addresses times out; the second succeeds."""

    def __init__(self, pages, flaky, code="TIMEOUT"):
        super().__init__(pages)
        self.flaky, self.code = set(flaky), code

    def __call__(self, request):
        url = request.url.get_secret_value()
        if url in self.flaky:
            self.flaky.discard(url)
            self.requests.append(url)
            return FetchFailure(source_ref=request.source_ref, code=self.code)
        return super().__call__(request)


def test_a_transient_read_is_asked_once_more_and_the_log_says_so():
    """Live BIST turn (2026-09-19): one failed read emptied the outline without a trace."""
    base = "https://www.borsa.example.tr"
    script = f"{base}/file/js/app.js?v=1"
    served = Flaky(site().pages, {script})
    cache = TurnFetchCache(served, pause=lambda _: None)
    note = address_outline((PAGE_URL,), cache)
    payload = json.loads(note[note.index("{") :])
    assert payload["pages"][0]["data_endpoints"][0]["name"] == "endpoint_1"
    assert "unread_resources" not in payload["pages"][0] and cache.transient_failures() == 0
    assert served.requests.count(script) == 2
    retried = [entry for entry in cache.log if entry["attempts"] == 2]
    assert retried == [
        {
            "source": retried[0]["source"],
            "kind": "script",
            "status": "ok",
            "code": None,
            "attempts": 2,
            "bytes": len(SCRIPT),
            # Whether the turn's session rode on the request; never its value.
            "session": False,
        }
    ]
    assert {entry["kind"] for entry in cache.log} == {"page", "script", "data"}
    assert not any("borsa" in str(value) for entry in cache.log for value in entry.values())


def test_a_refused_type_is_not_retried_and_an_empty_outline_says_nothing_is_listed():
    base = "https://www.borsa.example.tr"
    script = f"{base}/file/js/app.js?v=1"
    pages = dict(site().pages)
    pages[script] = (SCRIPT, "text/plain")  # not a script type: CONTENT_TYPE, permanent
    served = Site(pages)
    cache = TurnFetchCache(served)
    note = address_outline((PAGE_URL,), cache)
    payload = json.loads(note[note.index("{") :])
    assert payload["pages"][0] == {"address": "as written in the question", "nothing_listed": True}
    assert "never guess column names" in note
    assert served.requests.count(script) == 1
    failed = [entry for entry in cache.log if entry["status"] == "failed"]
    assert [(entry["kind"], entry["code"], entry["attempts"]) for entry in failed] == [
        ("script", "CONTENT_TYPE", 1)
    ]


def test_a_document_address_is_outlined_with_its_table_headers_like_an_upload():
    """Live J1 (2026-09-19): a PDF address was read bare because no header was ever shown."""
    from kkb_agent.tools._document_library import describe_document

    url = "https://www.borsa.example.tr/veriler/altin.csv"
    content = b"Ay;Hacim (TL);Miktar (KG)\n2026-01;93824;13.8\n2026-02;90534;12.6\n"
    served = Site({url: (content, "text/csv")})
    note = address_outline((url,), TurnFetchCache(served), describe_document)
    payload = json.loads(note[note.index("{") :])
    (page,) = payload["pages"]
    assert page["media_type"] == "text/csv"
    (table,) = page["tables"]
    assert table["headers"] == ["Ay", "Hacim (TL)", "Miktar (KG)"] and table["rows"] == 2
    assert "93824" not in note  # headers and counts only, never a value
    # Without a describer the outline is what it was.
    bare = address_outline((url,), TurnFetchCache(served))
    assert "tables" not in json.loads(bare[bare.index("{") :])["pages"][0]


class Down(Site):
    """Chosen addresses time out on every read."""

    def __init__(self, pages, down):
        super().__init__(pages)
        self.down = set(down)

    def __call__(self, request):
        url = request.url.get_secret_value()
        if url in self.down:
            self.requests.append(url)
            return FetchFailure(source_ref=request.source_ref, code="TIMEOUT")
        return super().__call__(request)


def test_a_read_lost_after_every_attempt_is_said_in_the_outline():
    """Live J2 (2026-09-19): the endpoint script timed out twice; the outline looked complete."""
    base = "https://www.borsa.example.tr"
    script = f"{base}/file/js/app.js?v=1"
    served = Down(site().pages, {script})
    waits = []
    cache = TurnFetchCache(served, pause=waits.append)
    note = address_outline((PAGE_URL,), cache)
    payload = json.loads(note[note.index("{") :])
    assert payload["pages"][0] == {
        "address": "as written in the question",
        "nothing_listed": True,
        "unread_resources": 1,
    }
    assert served.requests.count(script) == 3 and waits == [0.5, 1.0]
    assert cache.transient_failures() == 1
    assert "the listing may be incomplete" in note
    assert "inspected once more" in note and "recorded link" in note


ANNOUNCEMENTS = "https://www.tcmb.example.tr/wps/wcm/connect/TR/Main+Menu/Duyurular/Basin/2024"
LISTING = f"""<html><body><nav>
<a href="/wps/wcm/connect/TR/Main+Menu/Kurumsal">Kurumsal</a>
<a href="/">Ana Sayfa</a>
</nav><ul>
<li><a href="{ANNOUNCEMENTS}/DUY2024-14">21 Mart 2024 Para Politikası Kurulu Kararı</a></li>
<li><a href="/wps/wcm/connect/TR/Main+Menu/Duyurular/Basin/2024/DUY2024-13?lang=tr&amp;k=SECRET">
Faiz Oranlarına İlişkin Basın Duyurusu</a></li>
<li><a href="https://evil.example.test/DUY2024-12">21 Mart 2024 Kararı (kopya)</a></li>
<li><a href="https://user:pw@www.tcmb.example.tr/private">Gizli</a></li>
<li><a href="#top">Başa dön</a></li>
</ul></body></html>""".encode()


def outlined(page, url=ANNOUNCEMENTS):
    note = address_outline((url,), TurnFetchCache(Site({url: (page, "text/html")})))
    return note, json.loads(note[note.index("{") :])["pages"][0]


def test_a_page_without_document_links_lists_its_other_same_site_links():
    """Live 2026-09-22 (N46): press releases linked by suffix-less paths read as nothing."""
    note, page = outlined(LISTING)
    assert "nothing_listed" not in page and "more_page_links" not in page
    # The listing's own items, below the page's path, come before its site menu.
    assert page["page_links"] == [
        {"text": "21 Mart 2024 Para Politikası Kurulu Kararı", "last_segment": "DUY2024-14"},
        {"text": "Faiz Oranlarına İlişkin Basın Duyurusu", "last_segment": "DUY2024-13"},
        {"text": "Kurumsal", "last_segment": "Kurumsal"},
        {"text": "Ana Sayfa", "last_segment": ""},
    ]
    # Same origin only, credential-free, and never a query string; the page's link back to
    # itself is left out.
    for absent in ("evil", "kopya", "Gizli", "SECRET", "lang=tr", "Başa dön"):
        assert absent not in note
    assert "follow=<its text or last_segment>" in note
    assert "can be followed by its visible text even when it is not listed" in note


def test_the_other_links_are_bounded_in_number_and_length():
    items = "".join(
        f'<a href="{ANNOUNCEMENTS}/DUY2024-{number:02d}">{"Basın Duyurusu " * 8}{number}</a>'
        for number in range(30)
    )
    _, page = outlined(f"<html><body>{items}</body></html>".encode())
    assert len(page["page_links"]) == 20 and page["more_page_links"] == 10
    assert all(len(entry["text"]) <= 80 for entry in page["page_links"])
    assert page["page_links"][0]["last_segment"] == "DUY2024-00"


def test_a_page_with_no_link_follow_could_name_still_says_nothing_is_listed():
    # Another origin, another scheme, a picture with no text or file name, and the page itself.
    page = (
        b'<html><body><a href="https://evil.example.test/x">Elsewhere</a>'
        b'<a href="javascript:alert(1)">Script</a><a href="/"><img src="/logo.png"></a>'
        b'<a href="#top">Top</a></body></html>'
    )
    note, outline = outlined(page)
    assert outline == {"address": "as written in the question", "nothing_listed": True}
    assert "read it only for a table in its own HTML" in note


def test_a_page_with_document_links_keeps_its_listing_unchanged():
    page = (
        f'<html><body><a href="{ANNOUNCEMENTS}/rapor.pdf">Rapor</a>'
        f'<a href="{ANNOUNCEMENTS}/DUY2024-14">21 Mart 2024</a></body></html>'
    ).encode()
    _, outline = outlined(page)
    assert outline["document_links"] == [{"text": "Rapor", "file": "rapor.pdf"}]
    assert "page_links" not in outline and "nothing_listed" not in outline
