"""M7-04: real HTTP parser and fetch lifecycle, synthetic DNS/sockets only."""

import gzip
import io
import socket
import ssl
import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_bounded_fetch import PUBLIC, Transport, request, wire

from kkb_agent.agent import ExecutionContext, ToolStatus
from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest.fetched import source_id_for
from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchSuccess, safe_fetch
from kkb_agent.tools import WebUrlArguments, make_web_url_tool

START = "https://example.test/start"
CSV = b"date,value\n2026-01-01,42\n2026-02-01,50\n"


def redirect(location="/final", status=302, *, extra=(), body=b""):
    return wire(body, status=status, headers=[("Location", location), *extra])


class RedirectTransport(Transport):
    def __init__(self):
        super().__init__()
        self.responses = [redirect(), wire(CSV)]
        self.host_addresses = {}
        self.close_checks = []
        self.connect_clock = None

    def resolve(self, host, port, **kwargs):
        if self.sockets:
            self.close_checks.append(self.sockets[-1].closed and self.sockets[-1].stream.closed)
        self.answers = self.host_addresses.get(host, [PUBLIC])
        return super().resolve(host, port, **kwargs)

    def socket(self, family, *args):
        self.wire = self.responses[len(self.sockets)]
        if self.connect_clock is not None:
            self.connect_clock[0] += 2
        return super().socket(family, *args)

    def fetch(self, *, url=START, **limits):
        self.header_limit = limits.get("max_header_bytes", 32 * 1024)
        return _fetch_worker.fetch_once(request(url), FetchLimits(**limits), lambda: None)


@pytest.fixture
def network(monkeypatch):
    fake = RedirectTransport()
    monkeypatch.setattr(socket, "getaddrinfo", fake.resolve)
    monkeypatch.setattr(socket, "socket", fake.socket)

    def wrap(context, sock, *, server_hostname):
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        fake.tls.append(server_hostname)
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    return fake


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_public_relative_redirect_reaches_bounded_final_body(network, status):
    network.responses[0] = redirect("../final?token=synthetic-secret#part", status)
    outcome = network.fetch(url="https://example.test/folder/start")
    assert isinstance(outcome, FetchSuccess)
    assert outcome.content == CSV
    assert outcome.effective_locator.get_secret_value() == "https://example.test/final"
    assert network.resolutions == [("example.test", 443)] * 2
    assert network.tls == ["example.test"] * 2
    assert network.close_checks == [True]
    assert all(sock.closed and sock.stream.closed for sock in network.sockets)
    assert network.sockets[0].stream.sizes == []
    assert b"GET /final?token=synthetic-secret HTTP/1.1" in network.sockets[1].sent[0]
    assert "synthetic-secret" not in repr(outcome) + outcome.model_dump_json()


def test_chain_uses_fresh_dns_peer_tls_and_only_fixed_get_headers(network):
    network.responses = [
        redirect("https://other.test/next", extra=[("Set-Cookie", "private=synthetic-secret")]),
        redirect("/last"),
        wire(CSV),
    ]
    ipv6 = "2606:4700:4700::1111"
    network.host_addresses["other.test"] = [ipv6]
    assert network.fetch(max_redirects=2).content == CSV
    assert network.resolutions == [("example.test", 443), ("other.test", 443), ("other.test", 443)]
    assert network.connected == [(PUBLIC, 443), (ipv6, 443, 0, 0), (ipv6, 443, 0, 0)]
    assert network.tls == ["example.test", "other.test", "other.test"]
    assert network.close_checks == [True, True]
    for sock in network.sockets:
        sent = b"".join(sock.sent)
        assert sent.startswith(b"GET ")
        assert b"Cookie:" not in sent and b"Authorization:" not in sent and b"Referer:" not in sent
        assert b"synthetic-secret" not in sent
        fields = {line.split(b":", 1)[0].lower() for line in sent.split(b"\r\n")[1:] if line}
        assert fields == {b"host", b"accept", b"accept-encoding", b"connection"}


@pytest.mark.parametrize("location", [START, START + "#same", "https://EXAMPLE.test:443/start"])
def test_loop_is_rejected_before_reconnecting_to_an_already_visited_url(network, location):
    network.responses = [redirect("/next"), redirect(location)]
    assert network.fetch().code == FetchCode.REDIRECT_LOOP
    assert len(network.connected) == 2
    assert all(sock.closed and sock.stream.closed for sock in network.sockets)


@pytest.mark.parametrize("cap", [0, 1, 2])
def test_cap_rejects_before_connecting_to_the_excess_hop(network, cap):
    network.responses = [redirect(f"/hop-{i}") for i in range(4)]
    assert network.fetch(max_redirects=cap).code == FetchCode.REDIRECT_LIMIT
    assert len(network.connected) == cap + 1


@pytest.mark.parametrize(
    "location",
    [
        "https://10.0.0.1/",
        "https://127.0.0.1/",
        "https://localhost/",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/",
        "https://[::1]/",
        "https://[fd00::1]/",
        "https://[fe80::1]/",
    ],
)
def test_forbidden_redirect_is_never_resolved_or_contacted(network, location):
    network.responses[0] = redirect(location)
    assert network.fetch().code == FetchCode.BLOCKED_DESTINATION
    assert network.resolutions == [("example.test", 443)]
    assert network.connected == [(PUBLIC, 443)]
    assert network.sockets[0].closed


@pytest.mark.parametrize("answers", [["10.0.0.1"], ["::1"], [PUBLIC, "fd00::1"]])
def test_new_host_dns_is_checked_in_full_before_any_redirect_socket(network, answers):
    network.responses[0] = redirect("https://other.test/final")
    network.host_addresses["other.test"] = answers
    assert network.fetch().code == FetchCode.BLOCKED_DESTINATION
    assert network.resolutions == [("example.test", 443), ("other.test", 443)]
    assert network.connected == [(PUBLIC, 443)]
    assert len(network.sockets) == 1


def test_redirect_peer_mismatch_is_rejected_before_tls_or_http(network, monkeypatch):
    original = network.socket

    def socket_with_changed_peer(*args):
        sock = original(*args)
        if len(network.sockets) == 2:
            network.peer = ("127.0.0.1", 443)
        return sock

    monkeypatch.setattr(socket, "socket", socket_with_changed_peer)
    assert network.fetch().code == FetchCode.BLOCKED_DESTINATION
    assert network.tls == ["example.test"]
    assert network.sockets[1].sent == [] and network.sockets[1].closed


def test_redirect_certificate_failure_does_not_retry_or_downgrade(network, monkeypatch):
    calls = []

    def handshake(context, sock, *, server_hostname):
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        calls.append(server_hostname)
        if len(calls) == 2:
            raise ssl.SSLCertVerificationError("synthetic certificate failure")
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", handshake)
    assert network.fetch().code == FetchCode.TRANSPORT_FAILURE
    assert len(network.connected) == 2 and network.sockets[1].sent == []


@pytest.mark.parametrize(
    "location",
    [
        "http://other.test/",
        "https://user:synthetic-secret@other.test/",
        "ftp://other.test/",
        "https:///broken",
        "https:relative",
        "//",
        "/bad path",
        "\\\\localhost",
    ],
)
def test_downgrade_credentials_and_malformed_locations_fail_closed(network, location):
    network.responses[0] = redirect(location)
    assert network.fetch().code == FetchCode.INVALID_REQUEST
    assert network.connected == [(PUBLIC, 443)]


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("Location", "")],
        [("Location", "   ")],
        [("Location", "/one"), ("Location", "/two")],
        [("Location", "/same"), ("location", "/same")],
    ],
)
def test_exactly_one_nonempty_location_is_required(network, headers):
    network.responses[0] = wire(status=302, headers=headers)
    assert network.fetch().code == FetchCode.HTTP_FAILURE
    assert len(network.connected) == 1


@pytest.mark.parametrize("status", [300, 304, 305, 306, 399])
def test_other_3xx_statuses_do_not_authorize_following(network, status):
    network.responses[0] = redirect(status=status)
    assert network.fetch().code == FetchCode.HTTP_FAILURE
    assert len(network.connected) == 1


def test_header_budget_is_shared_across_hops_including_final_headers(network):
    budget = sum(response.index(b"\r\n\r\n") + 4 for response in network.responses)
    assert network.fetch(max_header_bytes=budget - 1).code == FetchCode.SIZE_LIMIT
    assert all(sock.stream.sizes == [] for sock in network.sockets)


def test_shared_header_budget_accepts_exact_limit(network):
    budget = sum(response.index(b"\r\n\r\n") + 4 for response in network.responses)
    assert network.fetch(max_header_bytes=budget).content == CSV


def test_redirect_body_is_never_buffered_or_decompressed(network):
    network.responses[0] = redirect(body=b"do-not-read" * 1000, extra=[("Content-Encoding", "br")])
    outcome = network.fetch(max_response_bytes=len(CSV), max_decompressed_bytes=len(CSV))
    assert outcome.content == CSV
    assert network.sockets[0].stream.sizes == []


@pytest.mark.parametrize("field", ["max_response_bytes", "max_decompressed_bytes"])
def test_final_body_keeps_original_byte_limits(network, field):
    assert network.fetch(**{field: len(CSV) - 1}).code == FetchCode.SIZE_LIMIT


def test_final_gzip_expansion_keeps_the_decompression_limit(network):
    network.responses[-1] = wire(
        gzip.compress(b"x" * 10000, mtime=0),
        headers=[("Content-Type", "text/csv"), ("Content-Encoding", "gzip")],
    )
    assert network.fetch(max_decompressed_bytes=100).code == FetchCode.SIZE_LIMIT


@pytest.mark.parametrize("header", [("Content-Encoding", "br"), ("Content-Type", "text/html")])
def test_final_media_and_encoding_policy_is_unchanged(network, header):
    headers = [("Content-Type", "text/csv"), header] if header[0] != "Content-Type" else [header]
    network.responses[-1] = wire(CSV, headers=headers)
    assert network.fetch().code == FetchCode.CONTENT_TYPE


def test_worker_does_not_reset_total_time_on_next_hop(network, monkeypatch):
    clock = [0.0]
    network.connect_clock = clock
    monkeypatch.setattr(_fetch_worker.time, "monotonic", lambda: clock[0])
    assert (
        network.fetch(connect_seconds=1, read_seconds=1, total_seconds=3).code == FetchCode.TIMEOUT
    )
    assert network.sockets[1].sent == []
    assert all(sock.closed for sock in network.sockets)


def inline_process(monkeypatch):
    """Run the real worker protocol in-process; only process launch is substituted."""
    launches = []

    class Worker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, payload=None, *, timeout=None):
            output = io.BytesIO()
            with monkeypatch.context() as patch:
                patch.setattr(
                    _fetch_worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload))
                )
                patch.setattr(_fetch_worker.sys, "stdout", SimpleNamespace(buffer=output))
                self.returncode = _fetch_worker.main()
            self.output = output.getvalue()
            return self.output, None

        def poll(self):
            return self.returncode

        def wait(self):
            return self.returncode

    def launch(argv, **kwargs):
        assert argv == [sys.executable, "-I", "-m", "kkb_agent.ingest._fetch_worker"]
        result = Worker()
        launches.append(result)
        return result

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", launch)
    return launches


def test_public_fetch_preserves_one_worker_and_redacted_effective_locator(network, monkeypatch):
    launches = inline_process(monkeypatch)
    network.responses[0] = redirect("https://other.test/final?token=synthetic-secret#part")
    outcome = safe_fetch(request(START))
    assert outcome.content == CSV
    assert outcome.effective_locator.get_secret_value() == "https://other.test/final"
    assert outcome.source_ref == request(START).source_ref
    assert len(launches) == 1
    assert b"synthetic-secret" not in launches[0].output
    assert launches[0].output.count(b"CONNECTED\n") == 2


def test_web_url_fetches_redirected_csv_with_final_locator_and_original_request_identity(
    network, monkeypatch
):
    inline_process(monkeypatch)
    network.responses[0] = redirect("https://other.test/final.csv?token=synthetic-secret")
    tool = make_web_url_tool()
    outcome = tool.run(
        WebUrlArguments(url=START, delimiter=","),
        ExecutionContext(question=f"{START} adresindeki tabloyu oku."),
    )
    assert outcome.status is ToolStatus.SUCCESS
    assert outcome.output.table.rows == (("2026-01-01", "42"), ("2026-02-01", "50"))
    assert outcome.output.source.locator == "https://other.test/final.csv"
    assert outcome.output.source.source_id == source_id_for(START)
    assert outcome.output.table.contract.source == outcome.output.source
    assert "synthetic-secret" not in repr(outcome)


@pytest.mark.parametrize("phase", ["total", "redirect-dns"])
def test_supervisor_never_restarts_total_or_redirect_connect_deadlines(monkeypatch, phase):
    clock = [0.0]

    class Worker:
        returncode = None
        stdin = stdout = None
        waited = False

        def __init__(self):
            self.calls = []

        def communicate(self, payload=None, *, timeout=None):
            self.calls.append((payload, timeout))
            if len(self.calls) == 1:
                clock[0] = 2
            else:
                clock[0] = 6 if phase == "total" else 3
            output = b"CONNECTED\nCONNECTING 3.000000000\n"
            if phase == "total":
                output += b"CONNECTED\nCONNECTING 3.500000000\nCONNECTED\n"
            raise subprocess.TimeoutExpired("source-fetch", timeout, output=output)

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self):
            self.waited = True
            return self.returncode

    worker = Worker()
    monkeypatch.setattr(_fetch_process.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: worker)
    limits = FetchLimits(connect_seconds=2, read_seconds=2, total_seconds=6)
    assert safe_fetch(request(START), limits=limits).code == FetchCode.TIMEOUT
    assert worker.calls[0][0] is not None and worker.calls[1][0] is None
    assert worker.calls[1][1] == (0.1 if phase == "total" else 1)
    assert worker.returncode == -9 and worker.waited


@pytest.mark.parametrize(
    "locator",
    [
        "https://other.test/path?secret=x",
        "https://other.test/#x",
        "https://user:secret@other.test/",
        "https://127.0.0.1/",
        "not a URL",
    ],
)
def test_effective_locator_contract_refuses_sensitive_or_invalid_metadata(locator):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FetchSuccess(
            source_ref="source:one",
            content=CSV,
            media_type="text/csv",
            http_status=200,
            effective_locator=locator,
        )
