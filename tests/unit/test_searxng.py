"""web_search over SearXNG, and what the person sees of a search (DEC-158).

No network: the adapter is driven through a fake `safe_fetch`, and the served
turn uses a picklable fake backend in the tool's spawned worker.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, seed_prepared

from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.ingest.safe_fetch import FetchFailure, FetchSuccess, safe_fetch
from kkb_agent.llm import scripted
from kkb_agent.tools.searxng import MAX_BODY_BYTES, SearxngBackend, SearxngRefused
from kkb_agent.tools.web_search import BackendHit, SearchReply, SearchRequest

PAGE = {
    "query": "konut kredisi",
    "results": [
        {
            "title": "Konut kredisi istatistikleri  ",
            "url": "https://www.bddk.org.tr/BultenAylik?x=1",
            "content": "Aylık bülten  verileri",
            "publishedDate": "2026-09-01T00:00:00",
        },
        {"title": "", "url": "https://example.org/missing-title"},
        {"title": "No URL here"},
        {"title": "EVDS", "url": "https://evds3.tcmb.gov.tr/", "publishedDate": "yesterday"},
    ],
}


class FakeFetch:
    """Stands in for `safe_fetch`: records the request and returns a bounded outcome."""

    def __init__(self, body=None, failure=None, raw=None):
        self.body, self.failure, self.raw = body, failure, raw
        self.seen = []

    def __call__(self, request, *, limits):
        self.seen.append((request, limits))
        if self.failure:
            return FetchFailure(source_ref=request.source_ref, code=self.failure)
        content = (
            self.raw
            if self.raw is not None
            else json.dumps(PAGE if self.body is None else self.body).encode()
        )
        return FetchSuccess(
            source_ref=request.source_ref,
            content=content,
            media_type="application/json",
            http_status=200,
        )


def test_results_are_read_as_given_and_incomplete_ones_are_dropped():
    fetch = FakeFetch()
    reply = SearxngBackend("https://search.example.org/", fetch=fetch).search(
        SearchRequest(query="konut kredisi")
    )
    assert [hit.title for hit in reply.hits] == ["Konut kredisi istatistikleri", "EVDS"]
    first = reply.hits[0]
    assert first.snippet == "Aylık bülten verileri"
    assert first.published_at == date(2026, 9, 1)
    assert reply.hits[1].published_at is None  # "yesterday" is not a date
    ((request, limits),) = fetch.seen
    url = request.url.get_secret_value()
    assert url.startswith("https://search.example.org/search?")
    assert "format=json" in url and "q=konut+kredisi" in url
    # The supervised transport, with no redirects and a byte ceiling.
    assert limits.max_redirects == 0 and limits.max_response_bytes == MAX_BODY_BYTES
    assert "konut" not in request.source_ref  # the query is not an identifier


@pytest.mark.parametrize(
    "fetch",
    [
        FakeFetch(failure="BLOCKED_DESTINATION"),  # e.g. a loopback instance
        FakeFetch(failure="TIMEOUT"),
        FakeFetch(body={"no": "results"}),
        FakeFetch(raw=b"<html>"),
    ],
)
def test_anything_but_a_result_page_is_a_failure_not_an_empty_answer(fetch):
    with pytest.raises((RuntimeError, ValueError)):
        SearxngBackend("https://search.example.org", fetch=fetch).search(SearchRequest(query="x"))


def test_no_second_http_client_is_added():
    """DEC-002: the adapter reaches the network only through safe_fetch."""
    from kkb_agent.tools import searxng

    source = Path(searxng.__file__).read_text(encoding="utf-8")
    assert "import httpx" not in source and "urllib.request" not in source
    assert SearxngBackend("https://s.example.org").fetch is safe_fetch


@pytest.mark.parametrize(
    "address",
    ["ftp://h/", "http://user:pw@h/", "http://h/?engine=x", "http://h/#f", "not a url"],
)
def test_the_instance_address_is_plain_operator_configuration(address):
    with pytest.raises(SearxngRefused):
        SearxngBackend(address)


@dataclass(frozen=True)
class FixedBackend:
    """Picklable for the tool's spawned worker; returns fixed hits."""

    def search(self, request: SearchRequest) -> SearchReply:
        return SearchReply(
            hits=(
                BackendHit(title="BDDK aylık bülten", url="https://www.bddk.org.tr/BultenAylik"),
                BackendHit(
                    title="Konut kredileri 2026'da yüzde 45 arttı",
                    url="https://news.example.com/kredi",
                ),
                BackendHit(title="TCMB EVDS", url="https://evds3.tcmb.gov.tr/"),
            )
        )


def test_a_served_search_is_shown_as_a_list_and_an_unverified_figure_is_withheld(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    plan = json.dumps(
        {
            "question": "q",
            "steps": [
                {
                    "step_id": "s",
                    "tool": "web_search",
                    "arguments": {"query": "konut kredisi verisi", "max_results": 5},
                }
            ],
        }
    )
    runner = PreparedRunner(
        scripted(plan),
        root,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        search_backend=FixedBackend(),
    )

    answer = runner(uuid4().hex, uuid4().hex, "Konut kredisi verisi nerede yayımlanıyor?")

    assert answer.status.value in ("accepted", "qualified"), answer
    assert answer.result is None  # discovery publishes no table
    assert "BDDK aylık bülten — www.bddk.org.tr" in answer.text
    assert "TCMB EVDS — evds3.tcmb.gov.tr" in answer.text
    assert "yüzde 45" not in answer.text and "45" not in answer.text
    assert answer.omitted_claims >= 1
    assert "adresini sorunda yaz" in answer.text


def test_without_a_backend_there_is_no_web_search_tool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    runner = PreparedRunner(
        scripted(), root, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    from kkb_agent.agent import Workspace
    from kkb_agent.lakehouse import open_lakehouse

    with open_lakehouse(tmp_path / "lake") as lake:
        workspace = Workspace.open(lake.connection, "s")
        assert "web_search" not in runner._registry(lake.connection, workspace, lake.lineage)
        runner._search_backend = FixedBackend()
        assert "web_search" in runner._registry(lake.connection, workspace, lake.lineage)


@pytest.mark.parametrize("configured", [True, False])
def test_readiness_reports_web_search_only_when_an_instance_is_named(
    tmp_path, monkeypatch, capsys, configured
):
    from test_prepared_api import set_config

    from kkb_agent.api import __main__ as api_cli

    set_config(monkeypatch)
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    command = ["--check", "--prepared-root", str(root), "--catalog", str(CATALOG)]
    if configured:
        command += ["--searxng-url", "https://search.example.org"]
    assert api_cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)["web_search"] is configured


# --- DEC-180: the operator's own instance on this machine ----------------------------------------


def _serve(handler):
    import threading
    from http.server import HTTPServer

    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_the_loopback_exception_reads_only_the_operators_own_instance():
    import json as _json
    from http.server import BaseHTTPRequestHandler

    from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure, FetchLimits, FetchRequest
    from kkb_agent.tools.searxng import SearxngBackend, is_loopback_instance, loopback_fetch
    from kkb_agent.tools.web_search import SearchRequest

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - the stdlib's name
            body = _json.dumps(
                {"results": [{"title": "TCMB faiz kararı", "url": "https://www.tcmb.gov.tr/x"}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = _serve(Handler)
    try:
        instance = f"http://127.0.0.1:{server.server_address[1]}"
        assert is_loopback_instance(instance)
        reply = SearxngBackend(instance, fetch=loopback_fetch).search(
            SearchRequest(query="politika faizi", max_results=5)
        )
        assert [hit.title for hit in reply.hits] == ["TCMB faiz kararı"]
    finally:
        server.shutdown()
    # Anything but a literal loopback host over plain http is refused before a connection.
    from pydantic import SecretStr

    for address in ("http://example.org:8080/search", "https://127.0.0.1:8888/search"):
        refused = loopback_fetch(
            FetchRequest(
                source_ref="search:test",
                url=SecretStr(address),
                accepted_media_types=("application/json",),
            ),
            limits=FetchLimits(),
        )
        assert isinstance(refused, FetchFailure) and refused.code is FetchCode.BLOCKED_DESTINATION
    assert not is_loopback_instance("https://search.example.org")
    assert not is_loopback_instance("http://127.0.0.1")  # a port is part of the exception
