"""M7-05 wire-level oracles: real HTTP parser, fake DNS/socket/TLS only."""

import base64
import gzip
import io
import json
import socket
import ssl
import subprocess
import sys
import time

import pytest

from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest._bounded_response import CHUNK_BYTES
from kkb_agent.ingest.safe_fetch import (
    FetchCode,
    FetchLimits,
    FetchRequest,
    FetchSuccess,
    safe_fetch,
)

PUBLIC = "8.8.8.8"


def request(url="https://example.test/data?private=synthetic-secret"):
    return FetchRequest(source_ref="source:bounded-1", url=url, accepted_media_types=("text/csv",))


def wire(body=b"date,value\n2026-01-01,42\n", *, headers=None, status=200, length=True):
    lines = [f"HTTP/1.1 {status} Synthetic\r\n".encode()]
    if headers is None:
        headers = [("Content-Type", "text/csv; charset=utf-8")]
    for name, value in headers:
        lines.append(f"{name}: {value}\r\n".encode())
    if length:
        lines.append(f"Content-Length: {len(body)}\r\n".encode())
    return b"".join(lines) + b"\r\n" + body


class Stream(io.BytesIO):
    def __init__(self, transport):
        super().__init__(transport.wire)
        self.transport = transport
        self.sizes = []
        self.body_position = transport.wire.find(b"\r\n\r\n") + 4

    def read1(self, size=-1):
        assert 0 < size <= CHUNK_BYTES  # Any unbounded body read is a test failure.
        self.sizes.append(size)
        if self.transport.read_error:
            raise self.transport.read_error
        return super().read(min(size, self.transport.fragment))

    def read(self, size=-1):
        # The stdlib chunk parser uses only fixed-size framing reads.
        assert 0 < size <= CHUNK_BYTES
        return super().read(size)

    def readline(self, size=-1):
        assert 0 < size <= self.transport.header_limit + 1
        if self.transport.header_error:
            raise self.transport.header_error
        return super().readline(size)


class Transport:
    def __init__(self):
        self.wire = wire()
        self.answers = [PUBLIC]
        self.connected = []
        self.resolutions = []
        self.sockets = []
        self.tls = []
        self.fragment = CHUNK_BYTES
        self.header_limit = 32 * 1024
        self.connect_error = self.read_error = self.header_error = self.tls_error = None
        self.peer = None

    def resolve(self, host, port, **kwargs):
        self.resolutions.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (x, port)) for x in self.answers]

    def socket(self, family, *args):
        owner = self

        class SyntheticSocket:
            def __init__(self):
                self.timeouts = []
                self.sent = []
                self.closed = False
                self.stream = Stream(owner)

            def connect(self, endpoint):
                owner.connected.append(endpoint)
                if owner.connect_error:
                    raise owner.connect_error
                self.endpoint = endpoint

            def settimeout(self, timeout):
                self.timeouts.append(timeout)

            def getpeername(self):
                return owner.peer or self.endpoint

            def sendall(self, content):
                self.sent.append(content)

            def makefile(self, mode):
                assert mode == "rb"
                return self.stream

            def close(self):
                self.closed = True

        result = SyntheticSocket()
        self.sockets.append(result)
        return result

    def fetch(self, **limits):
        if "max_header_bytes" in limits:
            self.header_limit = limits["max_header_bytes"]
        return _fetch_worker.fetch_once(request(), FetchLimits(**limits), lambda: None)


@pytest.fixture
def transport(monkeypatch):
    fake = Transport()
    monkeypatch.setattr(socket, "getaddrinfo", fake.resolve)
    monkeypatch.setattr(socket, "socket", fake.socket)

    def wrap(context, sock, *, server_hostname):
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        fake.tls.append(server_hostname)
        if fake.tls_error:
            raise fake.tls_error
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    return fake


@pytest.mark.parametrize("framing", ["length", "eof", "chunked"])
@pytest.mark.parametrize("compressed", [False, True])
def test_bounded_success_and_original_host_tls_identity(transport, framing, compressed):
    content = "date,value\n2026-01-01,İstanbul\n".encode()
    body = gzip.compress(content, mtime=0) if compressed else content
    encoded_size = len(body)
    headers = [("Content-Type", "Text/CSV; charset=utf-8")]
    if compressed:
        headers.append(("Content-Encoding", "GZip"))
    if framing == "chunked":
        headers.append(("Transfer-Encoding", "chunked"))
        body = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
    transport.wire = wire(body, headers=headers, length=framing == "length")
    transport.fragment = 3
    result = transport.fetch(max_response_bytes=encoded_size, max_decompressed_bytes=len(content))
    assert isinstance(result, FetchSuccess)
    assert result.content == content and result.media_type == "text/csv"
    assert transport.resolutions == [("example.test", 443)]
    assert transport.connected == [(PUBLIC, 443)]
    assert transport.tls == ["example.test"]
    sock = transport.sockets[0]
    assert sock.timeouts == [5, 5]
    assert b"GET /data?private=synthetic-secret HTTP/1.1" in sock.sent[0]
    assert b"Host: example.test:443" in sock.sent[0]
    assert b"Connection: close" in sock.sent[0]
    assert sock.closed and sock.stream.closed
    assert "synthetic-secret" not in repr(result) + result.model_dump_json()


@pytest.mark.parametrize("length", [False, True])
@pytest.mark.parametrize("limit", [7, 8, 9])
def test_body_exact_limit_and_one_over(transport, length, limit):
    transport.wire = wire(b"12345678", length=length)
    result = transport.fetch(max_response_bytes=limit)
    if limit < 8:
        assert result.code == FetchCode.SIZE_LIMIT
    else:
        assert result.content == b"12345678"
    assert transport.sockets[0].closed


@pytest.mark.parametrize("body", [b"", b"one", b"x" * 40_000])
def test_missing_length_is_bounded_and_can_finish_at_eof(transport, body):
    transport.wire = wire(body, length=False)
    assert transport.fetch(max_response_bytes=max(1, len(body))).content == body


@pytest.mark.parametrize("compressed", [False, True])
def test_decompressed_budget_applies_to_identity_and_gzip(transport, compressed):
    plain = b"x" * 100_000
    headers = [("Content-Type", "text/csv")]
    if compressed:
        headers.append(("Content-Encoding", "gzip"))
    body = gzip.compress(plain, mtime=0) if compressed else plain
    transport.wire = wire(body, headers=headers)
    assert transport.fetch(max_decompressed_bytes=100).code == FetchCode.SIZE_LIMIT


@pytest.mark.parametrize("kind", ["status", "single", "aggregate"])
def test_oversized_header_fails_before_body(transport, kind):
    if kind == "status":
        transport.wire = b"HTTP/1.1 200 " + b"x" * 200 + b"\r\n\r\n"
    elif kind == "single":
        transport.wire = wire(headers=[("X-Fill", "x" * 200)])
    else:
        transport.wire = wire(headers=[(f"X-{n}", "value") for n in range(20)])
    assert transport.fetch(max_header_bytes=100).code == FetchCode.SIZE_LIMIT
    assert transport.sockets[0].stream.sizes == []
    assert transport.sockets[0].closed


def test_header_budget_exact_boundary(transport):
    transport.wire = wire(b"ok")
    size = transport.wire.index(b"\r\n\r\n") + 4
    assert transport.fetch(max_header_bytes=size).content == b"ok"
    assert transport.fetch(max_header_bytes=size - 1).code == FetchCode.SIZE_LIMIT


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ([], FetchCode.CONTENT_TYPE),
        ([("Content-Type", "application/json")], FetchCode.CONTENT_TYPE),
        ([("Content-Type", "")], FetchCode.CONTENT_TYPE),
        ([("Content-Type", "text/csv"), ("Content-Type", "text/html")], FetchCode.HTTP_FAILURE),
        ([("Content-Length", "-1")], FetchCode.HTTP_FAILURE),
        ([("Content-Length", "1, 2")], FetchCode.HTTP_FAILURE),
        ([("Content-Length", "1"), ("Content-Length", "1")], FetchCode.HTTP_FAILURE),
        ([("Content-Length", "999999999999999999999999999")], FetchCode.HTTP_FAILURE),
        ([("Content-Length", "999999999")], FetchCode.SIZE_LIMIT),
        ([("Transfer-Encoding", "chunked"), ("Content-Length", "1")], FetchCode.HTTP_FAILURE),
        ([("Transfer-Encoding", "gzip")], FetchCode.HTTP_FAILURE),
        ([("Transfer-Encoding", "identity")], FetchCode.HTTP_FAILURE),
        ([("Transfer-Encoding", "gzip, chunked")], FetchCode.HTTP_FAILURE),
        ([("Transfer-Encoding", "")], FetchCode.HTTP_FAILURE),
        ([("Content-Encoding", "br")], FetchCode.CONTENT_TYPE),
        ([("Content-Encoding", "gzip, gzip")], FetchCode.CONTENT_TYPE),
        ([("Content-Encoding", "")], FetchCode.CONTENT_TYPE),
        ([("Trailer", "X-Checksum")], FetchCode.HTTP_FAILURE),
    ],
)
def test_malformed_or_unsupported_metadata_rejected_before_body(transport, headers, code):
    if headers and not any(k == "Content-Type" for k, _ in headers):
        headers = [("Content-Type", "text/csv"), *headers]
    transport.wire = wire(b"synthetic-private-body", headers=headers, length=False)
    result = transport.fetch()
    assert result.code == code
    assert transport.sockets[0].stream.sizes == []
    assert "synthetic-private-body" not in repr(result)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirects_never_follow_or_resolve_location(transport, status):
    transport.wire = wire(
        headers=[("Location", "http://169.254.169.254/latest/meta-data/")], status=status
    )
    assert transport.fetch(max_redirects=3).code == FetchCode.REDIRECT_LIMIT
    assert transport.resolutions == [("example.test", 443)]
    assert transport.connected == [(PUBLIC, 443)]
    assert transport.sockets[0].stream.sizes == []


@pytest.mark.parametrize("status", [100, 101, 400, 401, 404, 500])
def test_unsupported_or_error_http_status(transport, status):
    transport.wire = wire(status=status)
    assert transport.fetch().code == FetchCode.HTTP_FAILURE


@pytest.mark.parametrize("kind", ["length", "gzip", "gzip-trailing", "gzip-checksum", "chunks"])
def test_truncated_or_corrupt_payload_is_never_success(transport, kind):
    if kind == "length":
        transport.wire = wire(
            b"xx", headers=[("Content-Type", "text/csv"), ("Content-Length", "3")], length=False
        )
    elif kind.startswith("gzip"):
        body = gzip.compress(b"hello", mtime=0)
        if kind == "gzip":
            body = body[:-1]
        elif kind == "gzip-trailing":
            body += gzip.compress(b"another member", mtime=0)
        else:
            body = body[:-8] + b"BAD!" + body[-4:]
        transport.wire = wire(
            body, headers=[("Content-Type", "text/csv"), ("Content-Encoding", "gzip")]
        )
    else:
        transport.wire = wire(
            b"5\r\nabc",
            headers=[("Content-Type", "text/csv"), ("Transfer-Encoding", "chunked")],
            length=False,
        )
    assert transport.fetch().code == FetchCode.HTTP_FAILURE
    assert transport.sockets[0].closed


@pytest.mark.parametrize(
    "body",
    [
        b"-1\r\n",
        b"1;ext=x\r\na\r\n0\r\n\r\n",
        b"1\r\naXX0\r\n\r\n",
        b"0\r\nX: trailer\r\n\r\n",
        b"0\r\n",
        b"Z\r\n",
    ],
)
def test_invalid_or_unsupported_chunk_framing(transport, body):
    transport.wire = wire(
        body, headers=[("Content-Type", "text/csv"), ("Transfer-Encoding", "chunked")], length=False
    )
    assert transport.fetch().code == FetchCode.HTTP_FAILURE


def test_chunk_framing_uses_aggregate_header_budget(transport):
    body = b"1\r\na\r\n" * 30 + b"0\r\n\r\n"
    transport.wire = wire(
        body, headers=[("Content-Type", "text/csv"), ("Transfer-Encoding", "chunked")], length=False
    )
    assert transport.fetch(max_header_bytes=100).code == FetchCode.SIZE_LIMIT


@pytest.mark.parametrize(
    "raw",
    [
        b"HTTP/1.1 200 OK\n\n",
        b"HTTP/1.1 200 OK\r\n Bad: fold\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nMalformed\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nX: bad\x00value\r\n\r\n",
    ],
)
def test_malformed_headers_fail_closed(transport, raw):
    transport.wire = raw
    assert transport.fetch().code == FetchCode.HTTP_FAILURE


@pytest.mark.parametrize("stage", ["connect_error", "header_error", "read_error", "tls_error"])
def test_timeouts_return_fixed_outcomes_and_close_resources(transport, stage):
    setattr(transport, stage, TimeoutError("synthetic-secret"))
    result = transport.fetch(connect_seconds=1, read_seconds=2, total_seconds=3)
    assert result.code == FetchCode.TIMEOUT
    assert "synthetic-secret" not in repr(result)
    assert transport.sockets[0].closed


def test_tls_failure_cannot_trigger_downgrade_or_retry(transport):
    transport.tls_error = ssl.SSLCertVerificationError("synthetic private diagnostic")
    assert transport.fetch().code == FetchCode.TRANSPORT_FAILURE
    assert transport.connected == [(PUBLIC, 443)]
    assert transport.sockets[0].sent == []


@pytest.mark.parametrize("blocked", ["10.0.0.1", "::1"])
def test_worker_reuses_all_address_validation_before_sending(transport, blocked):
    transport.answers.append(blocked)
    assert transport.fetch().code == FetchCode.BLOCKED_DESTINATION
    assert transport.sockets == []


def test_worker_reuses_peer_binding_before_any_http_bytes(transport):
    transport.peer = ("127.0.0.1", 443)
    assert transport.fetch().code == FetchCode.BLOCKED_DESTINATION
    assert transport.sockets[0].sent == []


def output_for(result):
    data = result.model_dump(mode="json")
    if isinstance(result, FetchSuccess):
        data["content"] = base64.b64encode(result.content).decode()
    return json.dumps(data).encode()


def test_public_entry_dispatches_fixed_worker_and_validates_result(transport, monkeypatch):
    class InlineWorker:
        returncode = 0
        stdin = stdout = None

        def wait(self):
            return self.returncode

        def communicate(self, payload=None, *, timeout=None):
            if payload:
                data = json.loads(payload)
                result = _fetch_worker.fetch_once(
                    FetchRequest.model_validate(data["request"]),
                    FetchLimits.model_validate(data["limits"]),
                    lambda: None,
                )
                self.output = _fetch_process.CONNECTED + output_for(result)
            return self.output, None

        def poll(self):
            return self.returncode

    def popen(argv, **kwargs):
        assert argv == [sys.executable, "-I", "-m", "kkb_agent.ingest._fetch_worker"]
        assert kwargs == dict(
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        assert all("synthetic-secret" not in arg for arg in argv)
        return InlineWorker()

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", popen)
    assert safe_fetch(request()).content == b"date,value\n2026-01-01,42\n"
    assert transport.connected == [(PUBLIC, 443)]


@pytest.mark.parametrize("stage", ["dns", "body"])
def test_real_child_is_killed_and_reaped_at_deadline_without_network(tmp_path, monkeypatch, stage):
    # Substitute only the fixed child launch with a controlled local test worker.
    # It invokes the real worker; DNS/body deliberately stall, with no live socket.
    script = tmp_path / "slow_fetch.py"
    script.write_text("""
import socket, time
from kkb_agent.ingest import _fetch_worker as worker
from kkb_agent.ingest.safe_fetch import FetchRequest, FetchLimits
import sys
stage = sys.argv[1]
if stage == "dns":
    socket.getaddrinfo = lambda *a, **k: time.sleep(30)
    sys.exit(worker.main())
else:
    sys.stdin.buffer.read(65537)
    sys.stdout.buffer.write(worker.CONNECTED)
    sys.stdout.buffer.flush()
    time.sleep(30)
""")
    real_popen = subprocess.Popen
    children = []

    def launch(argv, **kwargs):
        process = real_popen([sys.executable, "-I", str(script), stage], **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", launch)
    start = time.monotonic()
    result = safe_fetch(
        request(), limits=FetchLimits(connect_seconds=1.5, read_seconds=0.5, total_seconds=2)
    )
    elapsed = time.monotonic() - start
    assert result.code == FetchCode.TIMEOUT
    assert elapsed < 5  # Generous CI scheduling margin, not a product deadline.
    assert elapsed >= (1.5 if stage == "dns" else 2)
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (b"not-json synthetic-secret", FetchCode.TRANSPORT_FAILURE),
        (b"[]", FetchCode.TRANSPORT_FAILURE),
        (b'{"source_ref":"different"}', FetchCode.TRANSPORT_FAILURE),
        (
            b'{"source_ref":"source:bounded-1","status":"success","content":"!"}',
            FetchCode.TRANSPORT_FAILURE,
        ),
        (b"x" * 4101, FetchCode.SIZE_LIMIT),
    ],
)
def test_worker_output_is_bounded_validated_and_diagnostics_stay_fixed(monkeypatch, result, code):
    class Worker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, *args, **kwargs):
            return result, None

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: Worker())
    outcome = safe_fetch(request(), limits=FetchLimits(max_decompressed_bytes=1))
    assert outcome.code == code
    assert "synthetic-secret" not in repr(outcome) + outcome.model_dump_json()


def test_deadline_does_not_restart_after_connected_marker(monkeypatch):
    clock = [0.0]

    class Worker:
        returncode = None
        stdin = stdout = None
        timeouts = []
        killed = False
        waited = False

        def communicate(self, payload=None, *, timeout=None):
            self.timeouts.append(timeout)
            if payload:
                clock[0] = 5.0
                raise subprocess.TimeoutExpired("fixed-worker", timeout, output=b"CONNECTED\n")
            clock[0] = 8.0
            raise subprocess.TimeoutExpired("fixed-worker", timeout)

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

        def wait(self):
            self.waited = True
            return self.returncode

    worker = Worker()
    monkeypatch.setattr(_fetch_process.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: worker)
    assert safe_fetch(request(), limits=FetchLimits(total_seconds=8)).code == FetchCode.TIMEOUT
    assert worker.timeouts == [5.0, 3.0]
    assert worker.killed and worker.waited


@pytest.mark.parametrize("bad_peer", [False, True])
def test_worker_private_protocol_round_trip_uses_real_parser(transport, monkeypatch, bad_peer):
    data = request().model_dump(mode="json")
    data["url"] = request().url.get_secret_value()
    payload = json.dumps(
        {"request": data, "limits": FetchLimits().model_dump(mode="json")}
    ).encode()
    output = io.BytesIO()

    class Input:
        buffer = io.BytesIO(payload)

    class Output:
        buffer = output

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    if bad_peer:
        transport.peer = ("127.0.0.1", 443)
    assert _fetch_worker.main() == 0
    raw = output.getvalue()
    assert raw.startswith(b"CONNECTED\n") is (not bad_peer)
    result = json.loads(raw.removeprefix(b"CONNECTED\n"))
    if bad_peer:
        assert result["code"] == "BLOCKED_DESTINATION"
    else:
        assert base64.b64decode(result["content"]) == b"date,value\n2026-01-01,42\n"
    assert b"synthetic-secret" not in raw


@pytest.mark.parametrize("payload", [b"not-json synthetic-secret", b"x" * 65537, b"{}"])
def test_worker_rejects_bad_private_input_without_logging(transport, monkeypatch, payload):
    output = io.BytesIO()

    class Input:
        buffer = io.BytesIO(payload)

    class Output:
        buffer = output

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    assert _fetch_worker.main() == 1
    assert output.getvalue() == b""
    assert transport.resolutions == transport.sockets == []


def test_no_content_response_does_not_accept_a_hidden_declared_body(transport):
    transport.wire = wire(b"hidden", status=204)
    assert transport.fetch().code == FetchCode.HTTP_FAILURE


def test_chunked_body_over_limit(transport):
    transport.wire = wire(
        b"3\r\nabc\r\n0\r\n\r\n",
        headers=[("Content-Type", "text/csv"), ("Transfer-Encoding", "chunked")],
        length=False,
    )
    assert transport.fetch(max_response_bytes=2).code == FetchCode.SIZE_LIMIT


def test_gzip_encoded_size_is_enforced_separately(transport):
    body = gzip.compress(b"x", mtime=0)
    transport.wire = wire(
        body, headers=[("Content-Type", "text/csv"), ("Content-Encoding", "gzip")], length=False
    )
    assert transport.fetch(max_response_bytes=len(body) - 1).code == FetchCode.SIZE_LIMIT


def test_valid_direct_fetch_does_not_normalize_ambiguous_semantics(transport):
    body = b'date,value,unit\n2026-01-01,"1.234,56",\n'
    transport.wire = wire(body)
    assert transport.fetch().content == body


def test_installed_worker_entrypoint_rejects_unsafe_input_without_network():
    candidate = request("file:///synthetic/private")
    data = candidate.model_dump(mode="json")
    data["url"] = candidate.url.get_secret_value()
    payload = json.dumps(
        {"request": data, "limits": FetchLimits().model_dump(mode="json")}
    ).encode()
    result = subprocess.run(
        [sys.executable, "-I", "-m", "kkb_agent.ingest._fetch_worker"],
        input=payload,
        capture_output=True,
        timeout=5,
        check=True,
    )
    assert json.loads(result.stdout)["code"] == "INVALID_REQUEST"
    assert result.stderr == b""
