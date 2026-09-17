"""A page the user gave authorizes its own same-site links, one hop; no network."""

import pytest
from pydantic import ValidationError

from kkb_agent.agent.executor import ExecutionContext
from kkb_agent.ingest.page_links import LinkRefused, choose_link, page_links, site_of
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.tools.web_url import WebUrlArguments, make_web_url_tool

PAGE_URL = "https://www.borsa.example.tr/veriler/piyasa-verileri"
PAGE = """<html><body>
<h2>Kıymetli Madenler Piyasası Verileri</h2>
<a href="/dosyalar/veriler/kmp_au.csv">Altın İşlemleri</a>
<a href="/dosyalar/veriler/kmp_ag.csv">Gümüş İşlemleri</a>
<a href="https://cdn.borsa.example.tr/files/rapor.csv">Aylık Rapor</a>
<a href="https://attacker.example.com/kmp_au.csv">Altın İşlemleri Yedek</a>
<a href="https://user:secret@www.borsa.example.tr/private.csv">Gizli</a>
<a href="javascript:alert(1)">Altın</a>
<a href="/dosyalar/veriler/arsiv.csv">Altın İşlemleri Arşivi</a>
</body></html>""".encode()
GOLD = "Ay;Altın (Kg)\n2026-04;100\n2026-05;120\n2026-06;90\n".encode()


class Site:
    """Serves the page and its files by exact address; records every request."""

    def __init__(self, pages):
        self.pages, self.requests = pages, []

    def __call__(self, request):
        url = request.url.get_secret_value()
        self.requests.append((url, request.accepted_media_types))
        content, media_type = self.pages[url]
        assert media_type in request.accepted_media_types
        return FetchSuccess(
            source_ref=request.source_ref, content=content, media_type=media_type, http_status=200
        )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def test_site_is_the_registrable_domain_without_a_suffix_list():
    assert site_of("www.borsaistanbul.com") == "borsaistanbul.com"
    assert site_of("evds2.cbrt.gov.tr") == "cbrt.gov.tr"
    assert site_of("www.borsa.example.tr") == "example.tr"
    assert site_of("data.bddk.org.tr") == "bddk.org.tr"
    assert site_of("10.0.0.1") == "10.0.0.1"


def test_only_same_site_credential_free_http_links_are_offered():
    urls = {link.url for link in page_links(PAGE, PAGE_URL)}
    assert "https://www.borsa.example.tr/dosyalar/veriler/kmp_au.csv" in urls
    assert "https://cdn.borsa.example.tr/files/rapor.csv" in urls
    assert not [u for u in urls if "attacker" in u or "secret" in u or u.startswith("javascript")]


@pytest.mark.parametrize(
    ("wanted", "path"),
    [
        ("Altın İşlemleri", "kmp_au.csv"),
        ("kmp_au.csv", "kmp_au.csv"),
        ("gumus islemleri", "kmp_ag.csv"),
    ],
)
def test_a_link_is_chosen_by_its_exact_text_or_file_name(wanted, path):
    assert choose_link(page_links(PAGE, PAGE_URL), wanted).url.endswith(path)


@pytest.mark.parametrize(
    ("wanted", "code"), [("Altın", "LINK_AMBIGUOUS"), ("Platin", "LINK_NOT_FOUND")]
)
def test_an_ambiguous_or_absent_link_is_refused_not_picked(wanted, code):
    with pytest.raises(LinkRefused) as refused:
        choose_link(page_links(PAGE, PAGE_URL), wanted)
    assert refused.value.code == code


@pytest.fixture
def tool(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        yield lambda site: make_web_url_tool(fetch=site, lineage=lake.lineage)


def test_web_url_follows_a_named_link_and_builds_a_table_from_it(tool):
    site = Site(
        {
            PAGE_URL: (PAGE, "text/html"),
            "https://www.borsa.example.tr/dosyalar/veriler/kmp_au.csv": (GOLD, "text/csv"),
        }
    )
    arguments = WebUrlArguments(
        url=PAGE_URL, follow="Altın İşlemleri", period_column="Ay", value_columns=["Altın"]
    )
    result = tool(site).run(arguments, ExecutionContext(f"{PAGE_URL} altın verisi"))
    assert result.status.value == "success", result.warnings
    table = result.output.result
    assert [v.value for v in table.values] == [100, 120, 90]
    assert table.evidence.sources[0].locator.endswith("/kmp_au.csv")
    # One page read for links (HTML only), then the one followed document.
    assert [url for url, _ in site.requests] == [
        PAGE_URL,
        "https://www.borsa.example.tr/dosyalar/veriler/kmp_au.csv",
    ]
    assert site.requests[0][1] == ("text/html",)


def test_a_link_off_the_page_or_off_the_site_is_never_requested(tool):
    site = Site({PAGE_URL: (PAGE, "text/html")})
    arguments = WebUrlArguments(url=PAGE_URL, follow="Altın İşlemleri Yedek")
    result = tool(site).run(arguments, ExecutionContext(f"{PAGE_URL} bak"))
    assert result.status.value == "failure" and "LINK_NOT_FOUND" in result.warnings
    assert [url for url, _ in site.requests] == [PAGE_URL]


def test_the_page_itself_must_still_be_an_address_the_user_wrote(tool):
    site = Site({PAGE_URL: (PAGE, "text/html")})
    arguments = WebUrlArguments(url=PAGE_URL, follow="Altın İşlemleri")
    result = tool(site).run(arguments, ExecutionContext("altın verisini getir"))
    assert result.status.value == "failure" and site.requests == []


def test_follow_needs_a_page_address():
    with pytest.raises(ValidationError):
        WebUrlArguments(attached=True, follow="Altın İşlemleri")
