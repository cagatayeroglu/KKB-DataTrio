"""M7-01 source-fetch contract, with live I/O deliberately disabled.

Adapters will call ``safe_fetch`` with an opaque SourceRef.source_id, a locator
and explicit accepted media types. Success means retrieved bytes, not admitted
files, parsed observations or verified financial semantics. CSV/XLSX still pass
through M1 admission/loader checks; other parser routes remain separate tasks.

Limits below are local operator budgets, not organizer/platform guarantees.
M7-02..06 must implement destination/DNS/connection validation, redirects and
stream/decompression/deadline enforcement before this entry point can fetch.
Constructing a request or success record does not perform those controls.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, SecretStr, StringConstraints, model_validator

from kkb_agent.core.models import ContractModel
from kkb_agent.ingestion_policy import DEFAULT_LIMITS as ADMISSION_LIMITS

SourceId = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
]
MediaType = Annotated[
    str,
    StringConstraints(
        strict=True, max_length=128, pattern=r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$"
    ),
]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
PositiveSeconds = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class FetchLimits(ContractModel):
    """Budgets the future transport must enforce, including across redirects.

    Response bytes count the encoded HTTP body; decompressed bytes count the
    decoded HTTP body, independently of XLSX archive expansion in M1. Read time
    limits a stalled read; total time bounds the entire operation. No retries
    or automatic proxy/cookie/credential behavior are authorized by this type.
    """

    model_config = ConfigDict(frozen=True)

    max_url_chars: PositiveInt = 4096
    max_response_bytes: PositiveInt = ADMISSION_LIMITS.max_bytes
    max_decompressed_bytes: PositiveInt = ADMISSION_LIMITS.max_bytes
    max_redirects: Annotated[int, Field(strict=True, ge=0)] = 3
    connect_seconds: PositiveSeconds = 5.0
    read_seconds: PositiveSeconds = 5.0
    total_seconds: PositiveSeconds = 30.0

    @model_validator(mode="after")
    def coherent_deadlines(self) -> Self:
        if max(self.connect_seconds, self.read_seconds) > self.total_seconds:
            raise ValueError("connect/read deadlines must not exceed the total deadline")
        return self


DEFAULT_LIMITS = FetchLimits()


class FetchRequest(ContractModel):
    """Untrusted locator plus caller-owned identity; never a network permission.

    Only the opaque source ID crosses into diagnostics. The locator is masked
    in repr and excluded from ordinary model exports; a future transport must
    explicitly unwrap it. Credentials/URL schemes/hosts are not validated here:
    every request is currently refused before any resolution or connection.
    """

    model_config = ConfigDict(frozen=True)

    source_ref: SourceId
    url: SecretStr = Field(min_length=1, repr=False, exclude=True)
    accepted_media_types: Annotated[tuple[MediaType, ...], Field(min_length=1, max_length=8)]


class FetchCode(StrEnum):
    """Fixed categories, without response text, URLs or raw exception messages."""

    NETWORK_DISABLED = "NETWORK_DISABLED"
    INVALID_REQUEST = "INVALID_REQUEST"
    BLOCKED_DESTINATION = "BLOCKED_DESTINATION"
    DNS_FAILURE = "DNS_FAILURE"
    REDIRECT_LIMIT = "REDIRECT_LIMIT"
    TIMEOUT = "TIMEOUT"
    SIZE_LIMIT = "SIZE_LIMIT"
    CONTENT_TYPE = "CONTENT_TYPE"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    HTTP_FAILURE = "HTTP_FAILURE"


class FetchFailure(ContractModel):
    """Safe outcome for callers/logs; never includes a remote body or locator."""

    model_config = ConfigDict(frozen=True)

    status: Literal["failure"] = "failure"
    source_ref: SourceId
    code: FetchCode


class FetchSuccess(ContractModel):
    """Future transport result; metadata is not proof of content validity.

    A transport must enforce the request's limits before assembling this
    in-memory record. Raw content is excluded from repr/ordinary model exports;
    a parser receives it explicitly. No redirect URL, headers or inferred
    financial meaning is exposed. The source ID links back to caller provenance.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["success"] = "success"
    source_ref: SourceId
    content: bytes = Field(strict=True, repr=False, exclude=True)
    media_type: MediaType
    http_status: Annotated[int, Field(strict=True, ge=200, le=299)]


FetchOutcome = Annotated[FetchSuccess | FetchFailure, Field(discriminator="status")]


def safe_fetch(request: FetchRequest, *, limits: FetchLimits = DEFAULT_LIMITS) -> FetchOutcome:
    """The single source-fetch entry point; always refuses live I/O for now.

    Revalidate at this boundary so an unchecked model_copy/model_construct
    cannot silently supply an invalid budget. Invalid contracts raise sanitized
    Pydantic ValidationError text. The only runtime outcomes currently emitted
    are SIZE_LIMIT (locator budget) and NETWORK_DISABLED; other categories and
    success are contracts for subsequent controlled-transport tasks.
    """

    request = FetchRequest.model_validate(request)
    limits = FetchLimits.model_validate(limits)
    if len(request.url.get_secret_value()) > limits.max_url_chars:
        return FetchFailure(source_ref=request.source_ref, code=FetchCode.SIZE_LIMIT)
    return FetchFailure(source_ref=request.source_ref, code=FetchCode.NETWORK_DISABLED)
