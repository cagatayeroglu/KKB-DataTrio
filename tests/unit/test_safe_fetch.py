"""M7-01 contract oracles; no live source, DNS or HTTP access is permitted."""

import io
import socket

import pytest
from pydantic import TypeAdapter, ValidationError

from kkb_agent.ingest.safe_fetch import (
    DEFAULT_LIMITS,
    FetchCode,
    FetchFailure,
    FetchLimits,
    FetchOutcome,
    FetchRequest,
    FetchSuccess,
    safe_fetch,
)
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS as ADMISSION_LIMITS,
)
from kkb_agent.ingestion_policy import MIME_TYPES, FileKind, admit_upload


def request(url: str = "https://example.test/series.csv") -> FetchRequest:
    return FetchRequest(
        source_ref="source:synthetic-1", url=url, accepted_media_types=(MIME_TYPES[FileKind.CSV],)
    )


@pytest.mark.parametrize(
    "field",
    ["max_url_chars", "max_response_bytes", "max_decompressed_bytes"],
)
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "1024"])
def test_byte_and_locator_limits_require_positive_integers(field, value) -> None:
    with pytest.raises(ValidationError):
        FetchLimits(**{field: value})


@pytest.mark.parametrize("field", ["connect_seconds", "read_seconds", "total_seconds"])
@pytest.mark.parametrize("value", [0, -1, True, "5", float("nan"), float("inf")])
def test_deadlines_require_finite_positive_numbers(field, value) -> None:
    with pytest.raises(ValidationError):
        FetchLimits(**{field: value})


@pytest.mark.parametrize("value", [-1, True, 1.5, "3"])
def test_redirect_limit_rejects_invalid_counts(value) -> None:
    with pytest.raises(ValidationError):
        FetchLimits(max_redirects=value)


def test_limits_round_trip_and_zero_redirect_policy() -> None:
    limits = FetchLimits(max_redirects=0, connect_seconds=2, read_seconds=3, total_seconds=4)
    assert FetchLimits.model_validate_json(limits.model_dump_json()) == limits
    assert DEFAULT_LIMITS.max_decompressed_bytes == ADMISSION_LIMITS.max_bytes
    with pytest.raises(ValidationError):
        FetchLimits(read_seconds=6, total_seconds=5)
    with pytest.raises(ValidationError):
        limits.max_response_bytes = 0


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("https://example.test/series.csv", FetchCode.NETWORK_DISABLED),
        ("http://8.8.8.8/", FetchCode.NETWORK_DISABLED),
        ("https://[2606:4700:4700::1111]/", FetchCode.NETWORK_DISABLED),
        ("http://127.0.0.1/private", FetchCode.BLOCKED_DESTINATION),
        ("http://[::1]/private", FetchCode.BLOCKED_DESTINATION),
        ("http://169.254.169.254/latest/meta-data/", FetchCode.BLOCKED_DESTINATION),
        ("file:///private/synthetic", FetchCode.INVALID_REQUEST),
        (
            "https://name:synthetic-secret@example.test/data?key=synthetic-secret",
            FetchCode.INVALID_REQUEST,
        ),
        ("not a URL", FetchCode.INVALID_REQUEST),
    ],
)
def test_every_request_is_refused_before_dns_or_socket_use(monkeypatch, url, code) -> None:
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("The disabled fetch entry point attempted network I/O")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    result = safe_fetch(request(url))
    assert isinstance(result, FetchFailure)
    assert result.source_ref == "source:synthetic-1"
    assert result.code == code
    assert (result.target_reason is None) == (code is FetchCode.NETWORK_DISABLED)
    assert calls == []


def test_locator_budget_exact_boundary_and_one_over() -> None:
    candidate = request()
    limit = len(candidate.url.get_secret_value())
    assert safe_fetch(candidate, limits=FetchLimits(max_url_chars=limit)).code == (
        FetchCode.NETWORK_DISABLED
    )
    assert safe_fetch(candidate, limits=FetchLimits(max_url_chars=limit - 1)).code == (
        FetchCode.SIZE_LIMIT
    )


def test_boundary_revalidates_unchecked_model_copies() -> None:
    with pytest.raises(ValidationError):
        safe_fetch(request(), limits=DEFAULT_LIMITS.model_copy(update={"total_seconds": -1}))
    with pytest.raises(ValidationError):
        safe_fetch(request().model_copy(update={"accepted_media_types": ()}))


@pytest.mark.parametrize("types", [(), ("*/*",), ("text/csv; charset=utf-8",), ("TEXT/CSV",)])
def test_request_needs_explicit_canonical_media_types(types) -> None:
    with pytest.raises(ValidationError):
        FetchRequest(
            source_ref="source:fixture", url="https://example.test", accepted_media_types=types
        )


def test_request_and_failure_diagnostics_exclude_locators_and_secrets() -> None:
    candidate = request("https://name:synthetic-secret@example.test/data?key=synthetic-secret")
    failure = safe_fetch(candidate)
    for output in [
        repr(candidate),
        candidate.model_dump_json(),
        repr(failure),
        failure.model_dump_json(),
    ]:
        assert "synthetic-secret" not in output
        assert "example.test" not in output
    with pytest.raises(ValidationError) as invalid:
        FetchRequest(
            source_ref="https://private.invalid?key=synthetic-secret",
            url="x",
            accepted_media_types=("text/csv",),
        )
    assert "synthetic-secret" not in str(invalid.value)


@pytest.mark.parametrize("code", list(FetchCode))
def test_failure_categories_round_trip_without_payload(code) -> None:
    result = FetchFailure(source_ref="source:synthetic-1", code=code)
    assert TypeAdapter(FetchOutcome).validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        FetchFailure(source_ref="source:synthetic-1", code=code, body="remote exception")


def test_synthetic_success_requires_file_admission_and_excludes_body_from_exports() -> None:
    payload = b"date,value\n2026-01-01,12\n"
    result = FetchSuccess(
        source_ref="source:synthetic-1", content=payload, media_type="text/csv", http_status=200
    )
    assert result.content == payload
    assert "content" not in result.model_dump()
    assert "2026-01-01" not in repr(result)
    assert TypeAdapter(FetchOutcome).validate_python(result) == result
    admitted = admit_upload(
        io.BytesIO(result.content), filename="synthetic.csv", content_type=result.media_type
    )
    assert admitted.content == payload
    assert admitted.kind is FileKind.CSV


@pytest.mark.parametrize("status", [True, 199, 300, 404])
def test_success_cannot_represent_an_http_failure(status) -> None:
    with pytest.raises(ValidationError):
        FetchSuccess(
            source_ref="source:fixture", content=b"x", media_type="text/csv", http_status=status
        )
