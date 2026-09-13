"""Closed Monthly POST using the real HTTP parser and fake DNS/socket/TLS.

The shared GET tests own the exhaustive framing matrix. These regressions
exercise the added POST path itself, including worker protocol and supervision.
"""

import gzip
import io
import json
import ssl
import subprocess

import pytest
from pydantic import SecretStr
from test_bddk_monthly_load import encoded, request, response
from test_bounded_fetch import output_for, wire
from test_bounded_fetch import transport as transport

from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest.bddk_monthly_request import MONTHLY_LIMITS, fetch_monthly
from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchRequest, FetchSuccess


def fetch():
    req = request()
    return _fetch_worker.fetch_once(req.fetch_request(), MONTHLY_LIMITS, lambda: None, monthly=req)


def test_post_uses_fixed_fields_tls_host_and_no_credentials(transport):
    payload = encoded(response(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])
    result = fetch()
    assert isinstance(result, FetchSuccess) and result.content == payload
    assert transport.resolutions == [("www.bddk.org.tr", 443)]
    assert transport.tls == ["www.bddk.org.tr"]
    sent = b"".join(transport.sockets[0].sent)
    assert sent.startswith(b"POST /BultenAylik/tr/Home/BasitRaporGetir HTTP/1.1\r\n")
    assert b"Content-Type: application/x-www-form-urlencoded\r\n" in sent
    assert sent.endswith(request().form_body())
    assert b"Authorization:" not in sent and b"Cookie:" not in sent


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/x",
        "http://www.bddk.org.tr/",
        "https://www.bddk.org.tr/other",
        "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir?x=1",
    ],
)
def test_worker_rejects_changed_endpoint_before_dns(transport, url):
    req = request()
    altered = req.fetch_request().model_copy(update={"url": SecretStr(url)})
    result = _fetch_worker.fetch_once(altered, MONTHLY_LIMITS, lambda: None, monthly=req)
    assert result.code == FetchCode.INVALID_REQUEST and not transport.resolutions


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_post_redirects_never_follow_or_forward(transport, status):
    transport.wire = wire(
        b"ignored",
        status=status,
        headers=[("Location", "https://www.bddk.org.tr/next"), ("Set-Cookie", "session=untrusted")],
    )
    assert fetch().code == FetchCode.REDIRECT_LIMIT
    assert len(transport.sockets) == 1 and transport.sockets[0].closed


@pytest.mark.parametrize(
    "fault,code",
    [
        ("connect", FetchCode.TRANSPORT_FAILURE),
        ("tls", FetchCode.TRANSPORT_FAILURE),
        ("read", FetchCode.TIMEOUT),
        ("header", FetchCode.TIMEOUT),
    ],
)
def test_post_transport_errors_are_fixed(transport, fault, code):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    error = (
        ssl.SSLCertVerificationError("private certificate text")
        if fault == "tls"
        else (
            TimeoutError("secret address") if fault in ("read", "header") else OSError("private IP")
        )
    )
    setattr(transport, fault + "_error", error)
    outcome = fetch()
    assert outcome.code == code
    assert "private" not in repr(outcome) and "secret" not in outcome.model_dump_json()


@pytest.mark.parametrize("boundary", ["header", "compressed", "decompressed", "content_type"])
def test_post_resource_and_type_limits(transport, boundary):
    headers = [("Content-Type", "application/json")]
    body = b"{}"
    if boundary == "header":
        headers.append(("X-Padding", "x" * MONTHLY_LIMITS.max_header_bytes))
    elif boundary == "compressed":
        body = b"x" * (MONTHLY_LIMITS.max_response_bytes + 1)
    elif boundary == "decompressed":
        body = gzip.compress(b"x" * (MONTHLY_LIMITS.max_decompressed_bytes + 1))
        headers.append(("Content-Encoding", "gzip"))
    else:
        headers = [("Content-Type", "text/html")]
    transport.wire = wire(body, headers=headers)
    assert fetch().code == (
        FetchCode.CONTENT_TYPE if boundary == "content_type" else FetchCode.SIZE_LIMIT
    )


@pytest.mark.parametrize("failure", ["dns", "peer", "tls_bypass"])
def test_post_cannot_bypass_address_or_tls_policy(transport, monkeypatch, failure):
    if failure == "dns":
        transport.answers = ["8.8.8.8", "127.0.0.1"]
    elif failure == "peer":
        transport.peer = ("127.0.0.1", 443)
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        monkeypatch.setattr(ssl, "create_default_context", lambda: context)
    assert (
        fetch().code == FetchCode.BLOCKED_DESTINATION
        if failure != "tls_bypass"
        else fetch().code == FetchCode.TRANSPORT_FAILURE
    )
    assert all(not sock.sent for sock in transport.sockets)


def test_parent_dispatch_serializes_only_closed_monthly_contract(transport, monkeypatch):
    payload = encoded(response(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])

    class InlineWorker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, payload, *, timeout):
            data = json.loads(payload)
            assert set(data["monthly"]) == {"selector", "period"}
            assert "body" not in data and "method" not in data
            monthly = type(request()).model_validate(data["monthly"])
            result = _fetch_worker.fetch_once(
                FetchRequest.model_validate(data["request"]),
                FetchLimits.model_validate(data["limits"]),
                lambda: None,
                monthly=monthly,
            )
            return b"CONNECTED\n" + output_for(result), None

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: InlineWorker())
    assert fetch_monthly(request()).content == payload
    assert b"POST " in b"".join(transport.sockets[0].sent)


def test_worker_main_roundtrip_revalidates_monthly_descriptor(transport, monkeypatch):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    req = request()
    data = req.fetch_request().model_dump(mode="json")
    data["url"] = req.fetch_request().url.get_secret_value()
    message = {
        "request": data,
        "limits": MONTHLY_LIMITS.model_dump(mode="json"),
        "monthly": req.model_dump(mode="json"),
    }

    class Input:
        buffer = io.BytesIO(json.dumps(message).encode())

    class Output:
        buffer = io.BytesIO()

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    assert _fetch_worker.main() == 0
    assert Output.buffer.getvalue().startswith(b"CONNECTED\n")
    assert b"POST " in b"".join(transport.sockets[0].sent)
    message["monthly"]["body"] = "untrusted"
    Input.buffer = io.BytesIO(json.dumps(message).encode())
    Output.buffer = io.BytesIO()
    assert _fetch_worker.main() == 1 and Output.buffer.getvalue() == b""
    assert len(transport.sockets) == 1


@pytest.mark.parametrize("stage", ["dns", "body"])
def test_post_parent_kills_worker_on_deadline(monkeypatch, stage):
    clock = [0.0]

    class Worker:
        returncode = None
        stdin = stdout = None
        killed = waited = False

        def communicate(self, payload=None, *, timeout=None):
            clock[0] = 5 if stage == "dns" else 30
            raise subprocess.TimeoutExpired(
                "fixed-worker", timeout, output=b"" if stage == "dns" else b"CONNECTED\n"
            )

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
    assert fetch_monthly(request()).code == FetchCode.TIMEOUT
    assert worker.killed and worker.waited
