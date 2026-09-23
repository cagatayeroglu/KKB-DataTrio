"""Single bounded source GET boundary, with explicitly validated redirects.

Explicit accepted media types route bounded bytes; success is not file admission,
parsed observations, source permission or verified financial semantics. CSV/XLSX
must still pass M1 guards. Budgets are operator limits, not provider guarantees.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, SecretStr, StrictBool, StringConstraints, model_validator

from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.url_targets import TargetReason, TargetRejection, validate_url_target
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
    """Budgets enforced by the direct-fetch worker and its deadline supervisor.

    Response bytes count the encoded HTTP body; decompressed bytes count the
    decoded HTTP body, independently of XLSX archive expansion in M1. Read time
    limits a stalled read; total time bounds the entire operation. No retries
    or automatic proxy/cookie/credential behavior are authorized by this type: a
    cookie is only ever sent because a caller put one in the request.
    """

    model_config = ConfigDict(frozen=True)

    max_url_chars: PositiveInt = 4096
    max_header_bytes: PositiveInt = 32 * 1024
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
    in repr and excluded from ordinary model exports; the transport must
    explicitly unwrap it. Construction alone does not validate the destination;
    safe_fetch validates it before the worker resolves and pins the connection.
    """

    model_config = ConfigDict(frozen=True)

    source_ref: SourceId
    url: SecretStr = Field(min_length=1, repr=False, exclude=True)
    accepted_media_types: Annotated[tuple[MediaType, ...], Field(min_length=1, max_length=8)]
    #: A fetch a page delegated (its own link, script or data endpoint) may not be
    #: redirected out of that page's origin (DEC-150 amendment). A person's own
    #: address is not delegated: its site may redirect as it likes, and the page
    #: the fetch ends on is the origin every later hop is measured against.
    stay_within_origin: StrictBool = False
    #: A `Cookie` header the caller's turn session holds for this exact origin
    #: (`ingest.fetch_session`). Sent on the first hop only and never on a redirect;
    #: a secret, so it is masked, excluded from exports and never logged.
    cookie: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @model_validator(mode="after")
    def cookie_is_pairs(self) -> Self:
        if self.cookie is not None:
            from kkb_agent.ingest.fetch_session import session_origin, well_formed

            if not well_formed(self.cookie.get_secret_value()):
                raise ValueError("cookie must be bounded name=value pairs")
            if session_origin(self.url.get_secret_value()) is None:
                raise ValueError("a cookie is only sent over https")
        return self


class FetchCode(StrEnum):
    """Fixed categories, without response text, URLs or raw exception messages."""

    NETWORK_DISABLED = "NETWORK_DISABLED"
    INVALID_REQUEST = "INVALID_REQUEST"
    BLOCKED_DESTINATION = "BLOCKED_DESTINATION"
    DNS_FAILURE = "DNS_FAILURE"
    REDIRECT_LIMIT = "REDIRECT_LIMIT"
    REDIRECT_LOOP = "REDIRECT_LOOP"
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
    target_reason: TargetReason | None = None


class FetchSuccess(ContractModel):
    """Bounded transport result; metadata is not proof of content validity.

    A transport must enforce the request's limits before assembling this
    in-memory record. Raw content is excluded from repr/ordinary model exports;
    a parser receives it explicitly. Redirect provenance contains only a masked,
    query/fragment-free final locator, never headers or financial meaning. The
    source ID still identifies the caller's original request.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["success"] = "success"
    source_ref: SourceId
    content: bytes = Field(strict=True, repr=False, exclude=True)
    media_type: MediaType
    http_status: Annotated[int, Field(strict=True, ge=200, le=299)]
    effective_locator: SecretStr | None = Field(default=None, repr=False, exclude=True)
    #: The name=value pairs the final response set over https, as one `Cookie`
    #: value, with `name=` alone marking a deletion. Never from a redirect. A
    #: secret: masked, excluded from exports, for the caller's turn session only.
    set_cookie: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @model_validator(mode="after")
    def set_cookie_is_pairs(self) -> Self:
        if self.set_cookie is not None:
            from kkb_agent.ingest.fetch_session import well_formed

            if not well_formed(self.set_cookie.get_secret_value()):
                raise ValueError("set_cookie must be bounded name=value pairs")
        return self

    @model_validator(mode="after")
    def safe_effective_locator(self) -> Self:
        if self.effective_locator is not None:
            from urllib.parse import urlsplit

            value = self.effective_locator.get_secret_value()
            target = validate_url_target(value)
            if isinstance(target, TargetRejection) or urlsplit(value).query or "#" in value:
                raise ValueError("effective locator must be a valid redacted public URL")
        return self


FetchOutcome = Annotated[FetchSuccess | FetchFailure, Field(discriminator="status")]


def safe_fetch(request: FetchRequest, *, limits: FetchLimits = DEFAULT_LIMITS) -> FetchOutcome:
    """Perform bounded GETs with fresh DNS/peer/TLS checks for every redirect.

    A fixed child process makes blocking OS DNS cancellable without abandoning
    threads. Redirects share the total deadline and framing budget; only the
    final response's body is read. Unsupported encodings/framing fail closed.
    Invalid contracts still raise sanitized ValidationError text. Callers own
    source/network authorization; no adapter/tool is enabled by this function.
    """

    request = FetchRequest.model_validate(request)
    limits = FetchLimits.model_validate(limits)
    target = validate_url_target(request.url.get_secret_value(), max_url_chars=limits.max_url_chars)
    if isinstance(target, TargetRejection):
        code = FetchCode.INVALID_REQUEST
        if target.reason is TargetReason.URL_TOO_LONG:
            code = FetchCode.SIZE_LIMIT
        elif target.reason in (TargetReason.LOCAL_HOST, TargetReason.NON_PUBLIC_IP):
            code = FetchCode.BLOCKED_DESTINATION
        return FetchFailure(source_ref=request.source_ref, code=code, target_reason=target.reason)
    from kkb_agent.ingest._fetch_process import fetch_in_process

    return fetch_in_process(request, limits)
