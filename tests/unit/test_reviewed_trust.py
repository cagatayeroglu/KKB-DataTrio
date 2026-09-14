"""Pinned BDDK issuer: a closed registry scoped to the fixed Monthly POST.

Offline only, with fake DNS/sockets and the real SSLContext. The live chain
acceptance against www.bddk.org.tr is recorded separately in ROADMAP.
"""

import hashlib
import ssl

import pytest
from pydantic import SecretStr
from test_bddk_monthly_load import encoded, request, response
from test_bounded_fetch import transport as transport
from test_bounded_fetch import wire

from kkb_agent.ingest import _fetch_worker, _reviewed_trust
from kkb_agent.ingest._reviewed_trust import (
    REVIEWED_ISSUERS,
    ReviewedTrustError,
    add_reviewed_issuer,
)
from kkb_agent.ingest._source_connection import SourceConnection, SourceConnectionError
from kkb_agent.ingest.bddk_monthly_request import MONTHLY_LIMITS
from kkb_agent.ingest.safe_fetch import DEFAULT_LIMITS, FetchCode, FetchRequest, FetchSuccess

HOST = "www.bddk.org.tr"
ISSUER_CN = "GlobalSign RSA OV SSL CA 2018"


def names(certificate, field):
    return {key: value for rdn in certificate[field] for key, value in rdn}


def reviewed_in(context):
    return [c for c in context.get_ca_certs() if names(c, "subject").get("commonName") == ISSUER_CN]


def client_context():
    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


@pytest.fixture
def contexts(monkeypatch):
    made = []
    real = ssl.create_default_context

    def recording():
        made.append(real())
        return made[-1]

    monkeypatch.setattr(ssl, "create_default_context", recording)
    return made


def test_registry_is_closed_immutable_and_pin_matches_reviewed_intermediate():
    assert set(REVIEWED_ISSUERS) == {HOST}
    pem, pin = REVIEWED_ISSUERS[HOST]
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() == pin
    with pytest.raises(TypeError):
        REVIEWED_ISSUERS["evil.test"] = (pem, pin)  # type: ignore[index]
    context = client_context()
    add_reviewed_issuer(context, HOST)
    (certificate,) = context.get_ca_certs()
    assert names(certificate, "subject") == {
        "countryName": "BE",
        "organizationName": "GlobalSign nv-sa",
        "commonName": ISSUER_CN,
    }
    # An intermediate, not a self-signed root: system roots must still anchor it.
    assert names(certificate, "issuer")["organizationalUnitName"] == "GlobalSign Root CA - R3"
    assert certificate["notAfter"] == "Nov 21 00:00:00 2028 GMT"


def test_partial_chain_is_disabled_even_when_a_default_enables_it():
    context = client_context()
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    add_reviewed_issuer(context, HOST)
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


@pytest.mark.parametrize("case", ["weak_context", "unknown_host", "pin_mismatch", "not_pem"])
def test_refusals_load_nothing(monkeypatch, case):
    context, host = client_context(), HOST
    pem, pin = REVIEWED_ISSUERS[HOST]
    if case == "weak_context":
        context.check_hostname = False
    elif case == "unknown_host":
        host = "evil.test"
    elif case == "pin_mismatch":
        monkeypatch.setattr(_reviewed_trust, "REVIEWED_ISSUERS", {HOST: (pem, "0" * 64)})
    else:
        monkeypatch.setattr(_reviewed_trust, "REVIEWED_ISSUERS", {HOST: ("not a pem", pin)})
    with pytest.raises(ReviewedTrustError):
        add_reviewed_issuer(context, host)
    assert context.get_ca_certs() == []


def monthly_fetch():
    req = request()
    return _fetch_worker.fetch_once(req.fetch_request(), MONTHLY_LIMITS, lambda: None, monthly=req)


def test_monthly_post_context_gets_pinned_issuer_without_partial_chain(transport, contexts):
    payload = encoded(response(request()))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])
    result = monthly_fetch()
    assert isinstance(result, FetchSuccess) and transport.tls == [HOST]
    (context,) = contexts
    assert len(reviewed_in(context)) == 1
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


def test_generic_get_to_the_same_host_does_not_receive_it(transport, contexts):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    plain = FetchRequest(
        source_ref="generic",
        url=SecretStr(f"https://{HOST}/BultenAylik"),
        accepted_media_types=("application/json",),
    )
    assert isinstance(_fetch_worker.fetch_once(plain, DEFAULT_LIMITS, lambda: None), FetchSuccess)
    (context,) = contexts
    assert reviewed_in(context) == []


def test_pin_mismatch_fails_closed_before_handshake_or_request(transport, monkeypatch):
    pem, _ = REVIEWED_ISSUERS[HOST]
    monkeypatch.setattr(_reviewed_trust, "REVIEWED_ISSUERS", {HOST: (pem, "f" * 64)})
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    assert monthly_fetch().code == FetchCode.TRANSPORT_FAILURE
    assert transport.tls == []
    assert all(not sock.sent for sock in transport.sockets)


@pytest.mark.parametrize("url", ["https://evil.test/x", f"http://{HOST}/x"])
def test_reviewed_issuer_requires_registered_https_host_before_dns(transport, url):
    target = FetchRequest(source_ref="x", url=SecretStr(url), accepted_media_types=("text/csv",))
    with pytest.raises(SourceConnectionError) as error:
        SourceConnection(target, reviewed_issuer=True)
    assert error.value.failure.code is FetchCode.INVALID_REQUEST
    assert transport.resolutions == []


def test_redirect_hop_never_inherits_reviewed_issuer(transport, contexts):
    connection = SourceConnection(request().fetch_request(), reviewed_issuer=True)
    hop = connection.redirect_connection(f"https://{HOST}/next")
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    hop.connect()
    hop.close()
    (context,) = contexts
    assert reviewed_in(context) == []
