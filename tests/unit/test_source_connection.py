"""M7-03 binding oracles. Only fake DNS, sockets and TLS handshake endpoints."""

import ipaddress
import socket
import ssl
import traceback

import pytest
from pydantic import ValidationError

from kkb_agent.ingest._source_connection import SourceConnection, SourceConnectionError
from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchRequest, safe_fetch
from kkb_agent.ingest.url_targets import TargetReason

PUBLIC = "8.8.8.8"
PUBLIC_V6 = "2606:4700:4700::1111"


def request(url="https://example.test/data"):
    return FetchRequest(source_ref="source:binding-1", url=url, accepted_media_types=("text/csv",))


class FakeSocket:
    def __init__(self, network, family):
        self.network = network
        self.family = family
        self.closed = False
        self.sent = []
        self.timeouts = []
        self.peer_reads = 0

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def connect(self, endpoint):
        address = ipaddress.ip_address(endpoint[0])  # Hostname here is a test failure.
        assert self.family == (socket.AF_INET if address.version == 4 else socket.AF_INET6)
        self.network.connected.append(endpoint)
        if self.network.connect_error:
            raise self.network.connect_error
        self.endpoint = endpoint

    def getpeername(self):
        self.peer_reads += 1
        if self.network.peer_error:
            raise self.network.peer_error
        if self.network.peer_after_tls is not None and self.peer_reads > 1:
            return self.network.peer_after_tls
        return self.network.peer if self.network.peer is not None else self.endpoint

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True
        if self.network.close_error:
            raise self.network.close_error


class FakeNetwork:
    def __init__(self):
        self.answers = [PUBLIC]
        self.answers_after_first = None
        self.dns_calls = []
        self.connected = []
        self.sockets = []
        self.tls = []
        self.dns_error = self.connect_error = self.peer_error = self.tls_error = None
        self.peer = self.peer_after_tls = None
        self.close_error = None

    def resolve(self, host, port, **kwargs):
        assert kwargs == dict(
            family=socket.AF_UNSPEC, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
        self.dns_calls.append((host, port))
        if self.dns_error:
            raise self.dns_error
        answers = self.answers_after_first if len(self.dns_calls) > 1 else None
        return [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (ip, port, 0, 0) if ":" in ip else (ip, port),
            )
            for ip in (answers if answers is not None else self.answers)
        ]

    def new_socket(self, family, kind, protocol):
        assert (kind, protocol) == (socket.SOCK_STREAM, socket.IPPROTO_TCP)
        sock = FakeSocket(self, family)
        self.sockets.append(sock)
        return sock


@pytest.fixture
def network(monkeypatch):
    fake = FakeNetwork()
    monkeypatch.setattr(socket, "getaddrinfo", fake.resolve)
    monkeypatch.setattr(socket, "socket", fake.new_socket)

    def forbidden(*args, **kwargs):
        pytest.fail("A second client/connector must not resolve the hostname")

    monkeypatch.setattr(socket, "create_connection", forbidden)

    def fake_wrap(context, sock, *, server_hostname):
        # Use the real default SSLContext; replace only its network handshake.
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        fake.tls.append((sock.endpoint, server_hostname))
        if fake.tls_error:
            raise fake.tls_error
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", fake_wrap)
    return fake


@pytest.mark.parametrize("address", [PUBLIC, PUBLIC_V6])
def test_public_dns_is_bound_to_numeric_socket_and_original_tls_hostname(network, address):
    network.answers = [address]
    connection = SourceConnection(request("HTTPS://Example.TEST.:443/data"))
    assert network.dns_calls == network.sockets == []  # Constructor has no network effects.
    connection.request("GET", "/data")  # Exercise the actual stdlib HTTP connect hook.
    expected = (address, 443, 0, 0) if ":" in address else (address, 443)
    assert network.dns_calls == [("example.test", 443)]
    assert network.connected == [expected]
    assert network.tls == [(expected, "example.test")]
    assert b"Host: example.test:443\r\n" in network.sockets[0].sent[0]
    assert network.sockets[0].peer_reads == 2
    assert network.sockets[0].timeouts == [5.0, 5.0]
    connection.close()
    assert network.sockets[0].closed


def test_rebinding_cannot_cause_a_second_resolution_between_validation_and_connect(network):
    network.answers_after_first = ["127.0.0.1"]
    connection = SourceConnection(request())
    connection.request("GET", "/data")
    assert network.dns_calls == [("example.test", 443)]
    assert network.connected == [(PUBLIC, 443)]
    connection.close()


@pytest.mark.parametrize("blocked", ["10.0.0.1", "169.254.169.254", "::1", "fd00:ec2::254"])
@pytest.mark.parametrize("blocked_first", [True, False])
def test_every_dns_answer_is_checked_before_any_connection(network, blocked, blocked_first):
    network.answers = [blocked, PUBLIC] if blocked_first else [PUBLIC, blocked]
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.code is FetchCode.BLOCKED_DESTINATION
    assert error.value.failure.target_reason is TargetReason.NON_PUBLIC_IP
    assert network.connected == network.sockets == network.tls == []


@pytest.mark.parametrize("address", ["10.0.0.1", "::1", "1.1.1.1", PUBLIC_V6])
def test_actual_peer_must_equal_selected_ip_before_tls_or_http(network, address):
    network.peer = (address, 443)
    connection = SourceConnection(request())
    with pytest.raises(SourceConnectionError) as error:
        connection.request("GET", "/data")
    assert error.value.failure.target_reason is TargetReason.PEER_MISMATCH
    assert network.connected == [(PUBLIC, 443)]
    assert network.tls == network.sockets[0].sent == []
    assert connection.sock is None and network.sockets[0].closed


def test_ipv6_rebinding_mismatch_is_closed_before_handshake(network):
    network.answers = [PUBLIC_V6]
    network.peer = ("fd00:ec2::254", 443, 0, 0)
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.target_reason is TargetReason.PEER_MISMATCH
    assert network.connected == [(PUBLIC_V6, 443, 0, 0)]
    assert network.tls == [] and network.sockets[0].closed


@pytest.mark.parametrize("peer", [(PUBLIC, 80), (PUBLIC, 443, 0, 1), ("malformed",), ()])
def test_peer_port_scope_and_shape_are_checked(network, peer):
    network.peer = peer
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.target_reason is TargetReason.PEER_MISMATCH
    assert network.sockets[0].closed


def test_peer_is_also_checked_on_tls_socket(network):
    network.peer_after_tls = ("127.0.0.1", 443)
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.target_reason is TargetReason.PEER_MISMATCH
    assert len(network.tls) == 1 and network.sockets[0].closed


@pytest.mark.parametrize("blocked", ["127.0.0.1", "::1"])
def test_http_reconnect_does_fresh_resolution_and_refuses_rebinding(network, blocked):
    network.answers_after_first = [blocked]
    connection = SourceConnection(request())
    connection.request("GET", "/data")
    connection.close()
    with pytest.raises(SourceConnectionError) as error:
        connection.request("GET", "/next")
    assert error.value.failure.code is FetchCode.BLOCKED_DESTINATION
    assert network.dns_calls == [("example.test", 443)] * 2
    assert network.connected == [(PUBLIC, 443)]


@pytest.mark.parametrize("location", ["/next", "https://other.test/next"])
def test_redirect_gets_new_resolution_and_cannot_inherit_a_stale_pin(network, location):
    first = SourceConnection(request())
    first.connect()
    network.answers_after_first = ["::1"]
    next_connection = first.redirect_connection(location)
    assert next_connection is not first
    with pytest.raises(SourceConnectionError) as error:
        next_connection.connect()
    assert error.value.failure.code is FetchCode.BLOCKED_DESTINATION
    assert len(network.dns_calls) == 2
    assert network.connected == [(PUBLIC, 443)]
    first.close()


def test_public_redirect_uses_its_own_ip_and_tls_hostname(network):
    first = SourceConnection(request())
    first.connect()
    network.answers_after_first = [PUBLIC_V6]
    redirected = first.redirect_connection("https://other.test/next")
    redirected.connect()
    assert network.connected == [(PUBLIC, 443), (PUBLIC_V6, 443, 0, 0)]
    assert network.tls[-1] == ((PUBLIC_V6, 443, 0, 0), "other.test")
    first.close()
    redirected.close()


@pytest.mark.parametrize(
    ("location", "reason"),
    [
        ("http://example.test/", TargetReason.HTTPS_DOWNGRADE),
        ("https://[::1]/", TargetReason.NON_PUBLIC_IP),
        ("https://user:synthetic@other.test/", TargetReason.URL_CREDENTIALS),
    ],
)
def test_redirect_policy_fails_before_new_dns_or_socket(network, location, reason):
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).redirect_connection(location)
    assert error.value.failure.target_reason is reason
    assert network.dns_calls == network.sockets == []


@pytest.mark.parametrize("url", [f"https://{PUBLIC}/", f"https://[{PUBLIC_V6}]/"])
def test_literal_targets_never_use_dns_but_still_verify_tls_identity(network, url):
    connection = SourceConnection(request(url))
    connection.connect()
    assert network.dns_calls == []
    assert network.tls[0][1] == ipaddress.ip_address(network.connected[0][0]).compressed
    connection.close()


@pytest.mark.parametrize(
    ("stage", "failure", "code"),
    [
        ("dns", socket.gaierror("synthetic-secret"), FetchCode.DNS_FAILURE),
        ("dns", TimeoutError("synthetic-secret"), FetchCode.TIMEOUT),
        ("connect", TimeoutError("synthetic-secret"), FetchCode.TIMEOUT),
        ("connect", OSError("synthetic-secret"), FetchCode.TRANSPORT_FAILURE),
        ("peer", OSError("synthetic-secret"), FetchCode.TRANSPORT_FAILURE),
        ("tls", ssl.SSLCertVerificationError("synthetic-secret"), FetchCode.TRANSPORT_FAILURE),
    ],
)
def test_failures_close_sockets_and_expose_only_structured_diagnostics(
    network, stage, failure, code
):
    setattr(network, f"{stage}_error", failure)
    connection = SourceConnection(request("https://example.test/private?key=synthetic-secret"))
    with pytest.raises(SourceConnectionError) as error:
        connection.connect()
    assert error.value.failure.code is code
    assert error.value.failure.source_ref == "source:binding-1"
    assert all(sock.closed for sock in network.sockets) and connection.sock is None
    for output in (
        str(error.value),
        repr(error.value),
        error.value.failure.model_dump_json(),
        "".join(traceback.format_exception(error.value)),
    ):
        assert "synthetic-secret" not in output


@pytest.mark.parametrize("answers", [[], ["not-an-ip"], ["8.8.8.8%scope"], [PUBLIC, "bad"]])
def test_invalid_dns_results_fail_closed(network, answers):
    network.answers = answers
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.code is FetchCode.DNS_FAILURE
    assert network.sockets == []


@pytest.mark.parametrize("flag", ["check_hostname", "verify_mode"])
def test_insecure_tls_context_is_rejected_without_handshake(network, monkeypatch, flag):
    context = ssl.create_default_context()
    context.check_hostname = False
    if flag == "verify_mode":
        context.verify_mode = ssl.CERT_NONE
    monkeypatch.setattr(ssl, "create_default_context", lambda: context)
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.code is FetchCode.TRANSPORT_FAILURE
    assert network.tls == [] and network.sockets[0].closed


def test_proxy_environment_is_ignored_and_tunnel_mutation_is_rejected(network, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    monkeypatch.setenv("ALL_PROXY", "http://[::1]:8080")
    connection = SourceConnection(request())
    with pytest.raises(SourceConnectionError):
        connection.set_tunnel("proxy.test")
    connection.connect()
    assert network.connected == [(PUBLIC, 443)]
    connection.close()
    connection.host = "127.0.0.1"
    with pytest.raises(SourceConnectionError):
        connection.connect()
    assert network.connected == [(PUBLIC, 443)]


def test_http_has_no_tls_and_config_is_validated(network):
    connection = SourceConnection(
        request("http://example.test/"), limits=FetchLimits(read_seconds=3)
    )
    connection.connect()
    assert network.connected == [(PUBLIC, 80)] and network.tls == []
    assert network.sockets[0].timeouts == [5, 3]
    connection.close()
    with pytest.raises(ValidationError):
        SourceConnection(request(), limits=FetchLimits().model_copy(update={"connect_seconds": -1}))


def test_public_fetch_entry_point_stays_disabled_without_using_connection_primitive(network):
    assert safe_fetch(request()).code is FetchCode.NETWORK_DISABLED
    assert network.dns_calls == network.sockets == []


def test_cleanup_error_cannot_replace_the_structured_rejection(network):
    network.peer = ("127.0.0.1", 443)
    network.close_error = OSError("synthetic-close-secret")
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(request()).connect()
    assert error.value.failure.target_reason is TargetReason.PEER_MISMATCH
    assert network.sockets[0].closed
    assert "synthetic-close-secret" not in "".join(traceback.format_exception(error.value))
