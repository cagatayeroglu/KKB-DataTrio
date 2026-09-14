"""Closed, code-reviewed issuer certificates for origins that omit their chain.

`www.bddk.org.tr` serves only its leaf certificate (M3-02; rechecked live on
2026-09-14). Browsers fetch the missing issuer through AIA; OpenSSL does not, so
verification fails. This registry adds exactly that reviewed intermediate to one
TLS context for one hostname. It is chain-building material, never an anchor:
system roots must still verify the intermediate, and partial-chain acceptance is
switched off so the intermediate cannot terminate a chain by itself.

Review evidence for the single entry: subject `GlobalSign RSA OV SSL CA 2018`,
issuer `GlobalSign Root CA - R3`, valid 2018-11-21 to 2028-11-21, CA:TRUE with
pathlen 0. Retrieved from the leaf's AIA issuer URL at GlobalSign on 2026-09-14;
it verified against the system roots and verified the BDDK leaf. The DER SHA-256
is pinned and rechecked on every use. No input, environment variable or response
can add or replace an entry.
"""

from __future__ import annotations

import hashlib
import ssl
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

_GLOBALSIGN_RSA_OV_SSL_CA_2018: Final = """\
-----BEGIN CERTIFICATE-----
MIIETjCCAzagAwIBAgINAe5fIh38YjvUMzqFVzANBgkqhkiG9w0BAQsFADBMMSAw
HgYDVQQLExdHbG9iYWxTaWduIFJvb3QgQ0EgLSBSMzETMBEGA1UEChMKR2xvYmFs
U2lnbjETMBEGA1UEAxMKR2xvYmFsU2lnbjAeFw0xODExMjEwMDAwMDBaFw0yODEx
MjEwMDAwMDBaMFAxCzAJBgNVBAYTAkJFMRkwFwYDVQQKExBHbG9iYWxTaWduIG52
LXNhMSYwJAYDVQQDEx1HbG9iYWxTaWduIFJTQSBPViBTU0wgQ0EgMjAxODCCASIw
DQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKdaydUMGCEAI9WXD+uu3Vxoa2uP
UGATeoHLl+6OimGUSyZ59gSnKvuk2la77qCk8HuKf1UfR5NhDW5xUTolJAgvjOH3
idaSz6+zpz8w7bXfIa7+9UQX/dhj2S/TgVprX9NHsKzyqzskeU8fxy7quRU6fBhM
abO1IFkJXinDY+YuRluqlJBJDrnw9UqhCS98NE3QvADFBlV5Bs6i0BDxSEPouVq1
lVW9MdIbPYa+oewNEtssmSStR8JvA+Z6cLVwzM0nLKWMjsIYPJLJLnNvBhBWk0Cq
o8VS++XFBdZpaFwGue5RieGKDkFNm5KQConpFmvv73W+eka440eKHRwup08CAwEA
AaOCASkwggElMA4GA1UdDwEB/wQEAwIBhjASBgNVHRMBAf8ECDAGAQH/AgEAMB0G
A1UdDgQWBBT473/yzXhnqN5vjySNiPGHAwKz6zAfBgNVHSMEGDAWgBSP8Et/qC5F
JK5NUPpjmove4t0bvDA+BggrBgEFBQcBAQQyMDAwLgYIKwYBBQUHMAGGImh0dHA6
Ly9vY3NwMi5nbG9iYWxzaWduLmNvbS9yb290cjMwNgYDVR0fBC8wLTAroCmgJ4Yl
aHR0cDovL2NybC5nbG9iYWxzaWduLmNvbS9yb290LXIzLmNybDBHBgNVHSAEQDA+
MDwGBFUdIAAwNDAyBggrBgEFBQcCARYmaHR0cHM6Ly93d3cuZ2xvYmFsc2lnbi5j
b20vcmVwb3NpdG9yeS8wDQYJKoZIhvcNAQELBQADggEBAJmQyC1fQorUC2bbmANz
EdSIhlIoU4r7rd/9c446ZwTbw1MUcBQJfMPg+NccmBqixD7b6QDjynCy8SIwIVbb
0615XoFYC20UgDX1b10d65pHBf9ZjQCxQNqQmJYaumxtf4z1s4DfjGRzNpZ5eWl0
6r/4ngGPoJVpjemEuunl1Ig423g7mNA2eymw0lIYkN5SQwCuaifIFJ6GlazhgDEw
fpolu4usBCOmmQDo8dIm7A9+O4orkjgTHY+GzYZSR+Y0fFukAj6KYXwidlNalFMz
hriSqHKvoflShx8xpfywgVcvzfTO3PYkz6fiNJBonf6q8amaEsybwMbDqKWwIX7e
SPY=
-----END CERTIFICATE-----
"""

#: Hostname -> (issuer PEM, SHA-256 of its DER). Closed and code-reviewed.
REVIEWED_ISSUERS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "www.bddk.org.tr": (
            _GLOBALSIGN_RSA_OV_SSL_CA_2018,
            "b676ffa3179e8812093a1b5eafee876ae7a6aaf231078dad1bfb21cd2893764a",
        ),
    }
)


class ReviewedTrustError(ValueError):
    """Fixed diagnostic: an unknown host or a certificate that fails its pin."""


def has_reviewed_issuer(hostname: str) -> bool:
    return hostname in REVIEWED_ISSUERS


def add_reviewed_issuer(context: ssl.SSLContext, hostname: str) -> None:
    """Add one pinned intermediate to a verifying context; never weaken it.

    The caller's context must already require certificates and hostnames.
    Partial chains are disabled explicitly, because newer Python defaults
    enable them and that would let the intermediate act as a trust anchor.
    """
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ReviewedTrustError("Context does not verify certificates")
    try:
        pem, pin = REVIEWED_ISSUERS[hostname]
        der = ssl.PEM_cert_to_DER_cert(pem)
    except (KeyError, ValueError):
        raise ReviewedTrustError("No reviewed issuer") from None
    if hashlib.sha256(der).hexdigest() != pin:
        raise ReviewedTrustError("Reviewed issuer does not match its pin")
    context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context.load_verify_locations(cadata=der)
