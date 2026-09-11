"""Deterministic M7-02 SSRF policy oracles; no DNS or HTTP is performed."""

import socket

import pytest

from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure, FetchRequest, safe_fetch
from kkb_agent.ingest.url_targets import (
    TargetReason,
    TargetRejection,
    URLTarget,
    validate_redirect_target,
    validate_url_target,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("URL policy must not resolve DNS or open sockets")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)


@pytest.mark.parametrize(
    ("url", "canonical", "host", "port", "addresses"),
    [
        (
            "HTTPS://Example.TEST.:443/a?q=1#view",
            "https://example.test/a?q=1",
            "example.test",
            443,
            None,
        ),
        ("http://example.test:80/data", "http://example.test/data", "example.test", 80, None),
        (
            "https://xn--rnek-4qa.test/",
            "https://xn--rnek-4qa.test/",
            "xn--rnek-4qa.test",
            443,
            None,
        ),
        ("http://8.8.8.8/", "http://8.8.8.8/", "8.8.8.8", 80, ("8.8.8.8",)),
        (
            "https://[2606:4700:4700::1111]:443/data",
            "https://[2606:4700:4700::1111]/data",
            "2606:4700:4700::1111",
            443,
            ("2606:4700:4700::1111",),
        ),
    ],
)
def test_public_target_canonicalization_does_not_claim_dns_checked(
    url, canonical, host, port, addresses
) -> None:
    target = validate_url_target(url)
    assert isinstance(target, URLTarget)
    assert target.url.get_secret_value() == canonical
    assert (target.hostname, target.port, target.addresses) == (host, port, addresses)


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("", TargetReason.MALFORMED_URL),
        (" https://example.test", TargetReason.MALFORMED_URL),
        ("https://exa\nmple.test", TargetReason.MALFORMED_URL),
        ("https://example.test/\x00", TargetReason.MALFORMED_URL),
        ("https://example.test/\x7f", TargetReason.MALFORMED_URL),
        ("https://example.test/\u00a0", TargetReason.MALFORMED_URL),
        ("http://example.test\\@127.0.0.1", TargetReason.MALFORMED_URL),
        ("https://[::1", TargetReason.MALFORMED_URL),
        ("https://example.test／private", TargetReason.MALFORMED_URL),
        ("https://", TargetReason.INVALID_HOST),
        ("https:///example.test", TargetReason.INVALID_HOST),
        ("//example.test/data", TargetReason.UNSUPPORTED_SCHEME),
        ("file:///private/synthetic", TargetReason.UNSUPPORTED_SCHEME),
        ("ftp://example.test", TargetReason.UNSUPPORTED_SCHEME),
        ("gopher://example.test", TargetReason.UNSUPPORTED_SCHEME),
        ("data:text/plain,synthetic", TargetReason.UNSUPPORTED_SCHEME),
        ("https://user:synthetic@example.test", TargetReason.URL_CREDENTIALS),
        ("https://user@example.test", TargetReason.URL_CREDENTIALS),
        ("https://@example.test", TargetReason.URL_CREDENTIALS),
        ("https://user%40name@example.test", TargetReason.URL_CREDENTIALS),
        ("https://example.test:8080", TargetReason.UNSAFE_PORT),
        ("http://example.test:443", TargetReason.UNSAFE_PORT),
        ("https://example.test:80", TargetReason.UNSAFE_PORT),
        ("https://example.test:", TargetReason.UNSAFE_PORT),
        ("https://example.test:+443", TargetReason.UNSAFE_PORT),
        ("https://example.test:0443", TargetReason.UNSAFE_PORT),
        ("https://example.test:443:80", TargetReason.UNSAFE_PORT),
        ("https://example.test:65536", TargetReason.UNSAFE_PORT),
        ("https://[2606:4700::1111]ignored", TargetReason.MALFORMED_URL),
        ("https://%31%32%37.0.0.1", TargetReason.INVALID_HOST),
        ("https://example.test%40127.0.0.1", TargetReason.INVALID_HOST),
        ("https://[fe80::1%25eth0]", TargetReason.INVALID_HOST),
        ("https://örnek.test", TargetReason.INVALID_HOST),
        ("https://example。test", TargetReason.INVALID_HOST),
        ("https://example..test", TargetReason.INVALID_HOST),
        ("https://example.test..", TargetReason.INVALID_HOST),
        ("https://-example.test", TargetReason.INVALID_HOST),
        ("https://example_.test", TargetReason.INVALID_HOST),
        ("https://singlelabel", TargetReason.INVALID_HOST),
        ("https://" + "a" * 64 + ".test", TargetReason.INVALID_HOST),
        ("https://" + ".".join(["a" * 63] * 4), TargetReason.INVALID_HOST),
    ],
)
def test_invalid_urls_have_fixed_rejection_reasons(url, reason) -> None:
    assert validate_url_target(url) == TargetRejection(reason)


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST.",
        "service.localhost",
        "service.local",
        "metadata.google.internal",
        "metadata",
        "instance-data",
        "ip6-localhost",
        "ip6-loopback",
        "service.localdomain",
        "router.home.arpa",
    ],
)
def test_local_and_metadata_names_cannot_be_rescued_by_public_dns(host) -> None:
    assert validate_url_target(
        f"https://{host}/", resolved_addresses=("8.8.8.8",)
    ) == TargetRejection(TargetReason.LOCAL_HOST)


@pytest.mark.parametrize(
    "host",
    [
        "127.1",
        "2130706433",
        "0177.0.0.1",
        "0x7f000001",
        "0x7f.0.0.1",
        "127.0.00.1",
        "999.1.1.1",
        "0",
    ],
)
def test_alternate_numeric_hosts_are_never_delegated_to_dns(host) -> None:
    assert validate_url_target(f"http://{host}/") == TargetRejection(TargetReason.AMBIGUOUS_IP)


UNSAFE_IPS = [
    "0.0.0.0",
    "0.1.2.3",
    "10.2.3.4",
    "127.0.0.1",
    "127.255.255.254",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.1.1",
    "169.254.169.254",
    "169.254.170.2",
    "100.100.100.200",
    "100.64.0.1",
    "168.63.129.16",
    "192.0.0.9",
    "192.88.99.1",
    "192.0.2.1",
    "198.18.0.1",
    "198.51.100.1",
    "203.0.113.1",
    "224.0.0.1",
    "240.0.0.1",
    "255.255.255.255",
    "::",
    "::1",
    "fc00::1",
    "fd00:ec2::254",
    "fe80::1",
    "ff02::1",
    "::ffff:127.0.0.1",
    "::ffff:8.8.8.8",
    "::127.0.0.1",
    "64:ff9b::7f00:1",
    "64:ff9b:1::1",
    "2001::1",
    "2001:db8::1",
    "2002:7f00:1::",
    "3fff::1",
]


@pytest.mark.parametrize("address", UNSAFE_IPS)
def test_unsafe_literal_and_dns_addresses_are_rejected(address) -> None:
    host = f"[{address}]" if ":" in address else address
    rejected = TargetRejection(TargetReason.NON_PUBLIC_IP)
    assert validate_url_target(f"https://{host}/") == rejected
    assert validate_url_target("https://example.test/", resolved_addresses=(address,)) == rejected


@pytest.mark.parametrize(
    "answers",
    [(), ("not-an-ip",), ("127.1",), ("8.8.8.8%scope",), ("8.8.8.8", "bad"), (123,), ["8.8.8.8"]],
)
def test_missing_or_malformed_dns_answers_fail_closed(answers) -> None:
    assert validate_url_target(
        "https://example.test/", resolved_addresses=answers
    ) == TargetRejection(TargetReason.INVALID_RESOLUTION)


@pytest.mark.parametrize("answers", [("8.8.8.8", "10.0.0.1"), ("::1", "8.8.8.8")])
def test_mixed_dns_results_are_rejected_as_a_whole(answers) -> None:
    assert validate_url_target(
        "https://example.test", resolved_addresses=answers
    ) == TargetRejection(TargetReason.NON_PUBLIC_IP)


def test_public_dns_answers_are_canonical_and_literal_cannot_change_address() -> None:
    target = validate_url_target(
        "https://example.test", resolved_addresses=("8.8.8.8", "2606:4700:4700:0::1111", "8.8.8.8")
    )
    assert isinstance(target, URLTarget)
    assert target.addresses == ("8.8.8.8", "2606:4700:4700::1111")
    assert isinstance(
        validate_url_target("https://8.8.8.8", resolved_addresses=("8.8.8.8",)), URLTarget
    )
    assert validate_url_target(
        "https://8.8.8.8", resolved_addresses=("1.1.1.1",)
    ) == TargetRejection(TargetReason.INVALID_RESOLUTION)


@pytest.mark.parametrize(
    ("location", "reason"),
    [
        ("http://example.test/data", TargetReason.HTTPS_DOWNGRADE),
        ("//127.0.0.1/data", TargetReason.NON_PUBLIC_IP),
        ("https://[::1]/data", TargetReason.NON_PUBLIC_IP),
        ("//metadata.google.internal/", TargetReason.LOCAL_HOST),
        ("https://user:synthetic@other.test/", TargetReason.URL_CREDENTIALS),
        ("ftp://other.test/", TargetReason.UNSUPPORTED_SCHEME),
        ("https:///127.0.0.1/", TargetReason.MALFORMED_URL),
        ("https:relative", TargetReason.MALFORMED_URL),
        ("////127.0.0.1/", TargetReason.MALFORMED_URL),
        (" https://other.test", TargetReason.MALFORMED_URL),
        ("\\\\127.0.0.1", TargetReason.MALFORMED_URL),
        ("", TargetReason.MALFORMED_URL),
    ],
)
def test_redirect_targets_are_revalidated_and_cannot_downgrade(location, reason) -> None:
    assert validate_redirect_target("https://example.test/data", location) == TargetRejection(
        reason
    )


def test_relative_redirect_new_dns_and_every_destination_are_checked() -> None:
    target = validate_redirect_target("https://example.test/a/b", "../data?year=2026")
    assert isinstance(target, URLTarget)
    assert target.url.get_secret_value() == "https://example.test/data?year=2026"
    assert target.addresses is None  # No cached/resolved addresses silently inherited.
    assert isinstance(
        validate_redirect_target("http://example.test/", "https://other.test/"), URLTarget
    )
    assert validate_redirect_target(
        target.url.get_secret_value(), "https://other.test/", resolved_addresses=("8.8.8.8", "::1")
    ) == TargetRejection(TargetReason.NON_PUBLIC_IP)
    assert validate_redirect_target(
        "https://localhost/", "https://example.test/"
    ) == TargetRejection(TargetReason.LOCAL_HOST)


def test_url_and_joined_redirect_budgets_are_enforced() -> None:
    url = "https://example.test/a"
    assert isinstance(validate_url_target(url, max_url_chars=len(url)), URLTarget)
    assert validate_url_target(url, max_url_chars=len(url) - 1) == TargetRejection(
        TargetReason.URL_TOO_LONG
    )
    assert validate_redirect_target(url, "x" * 30, max_url_chars=29) == TargetRejection(
        TargetReason.URL_TOO_LONG
    )
    assert validate_redirect_target(url, "longer-path", max_url_chars=len(url)) == TargetRejection(
        TargetReason.URL_TOO_LONG
    )


def test_policy_reasons_survive_fetch_serialization_without_sensitive_locators() -> None:
    request = FetchRequest(
        source_ref="source:policy-1",
        url="https://user:synthetic-secret@example.test?x=private-query",
        accepted_media_types=("text/csv",),
    )
    failure = safe_fetch(request)
    assert isinstance(failure, FetchFailure)
    assert failure.code is FetchCode.INVALID_REQUEST
    assert failure.target_reason is TargetReason.URL_CREDENTIALS
    assert FetchFailure.model_validate_json(failure.model_dump_json()) == failure
    target = validate_url_target("https://example.test/private-path?x=private-query")
    for diagnostic in (repr(failure), failure.model_dump_json(), repr(target)):
        for sensitive in ("synthetic-secret", "example.test", "private-path", "private-query"):
            assert sensitive not in diagnostic
