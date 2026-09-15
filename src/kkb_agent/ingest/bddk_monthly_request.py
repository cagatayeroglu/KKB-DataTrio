"""Closed Monthly request contract; no caller-selected URL, headers or POST body.

This infrastructure is not a planner tool or source-access permission. Only
selectors supported by the reviewed M3-05 metadata boundary reach transport.
"""

from __future__ import annotations

import hashlib
import json
from typing import Self
from urllib.parse import urlencode

from pydantic import ConfigDict, SecretStr, model_validator

from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_monthly import (
    BddkSelector,
    MonthlyPeriod,
    reviewed_monthly_catalog,
)
from kkb_agent.ingest.safe_fetch import FetchLimits, FetchOutcome, FetchRequest

MONTHLY_ENDPOINT = "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"
MAX_MONTHS = 120
MAX_FORM_BYTES = 256
# Operator ceilings, not claims about BDDK quotas or a permission to fetch.
MONTHLY_LIMITS = FetchLimits(
    max_url_chars=256,
    max_header_bytes=16 * 1024,
    max_response_bytes=1024 * 1024,
    max_decompressed_bytes=2 * 1024 * 1024,
    max_redirects=0,
)


def period_key(period: MonthlyPeriod) -> str:
    period = MonthlyPeriod.model_validate(period)
    return f"{period.year:04d}-{period.month:02d}"


class MonthlyRange(ContractModel):
    """Explicit inclusive whole months, with a fixed maximum request count."""

    model_config = ConfigDict(frozen=True)
    start: MonthlyPeriod
    end: MonthlyPeriod

    @model_validator(mode="after")
    def bounded(self) -> Self:
        count = (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1
        if not 1 <= count <= MAX_MONTHS:
            raise ValueError("Monthly range must contain 1 through 120 months")
        return self

    def periods(self) -> tuple[MonthlyPeriod, ...]:
        checked = MonthlyRange.model_validate(self)
        start = checked.start.year * 12 + checked.start.month - 1
        end = checked.end.year * 12 + checked.end.month - 1
        return tuple(MonthlyPeriod(year=n // 12, month=n % 12 + 1) for n in range(start, end + 1))


class MonthlyRequest(ContractModel):
    """Serialized across the fixed worker boundary and revalidated there.

    Metadata review, not the shape of an opaque fingerprint, grants support.
    Row/component are response selections, never undocumented form fields.
    """

    model_config = ConfigDict(frozen=True)
    selector: BddkSelector
    period: MonthlyPeriod

    @model_validator(mode="after")
    def supported(self) -> Self:
        reviewed_monthly_catalog(self.selector)
        return self

    def fingerprint(self) -> str:
        checked = MonthlyRequest.model_validate(self)
        payload = json.dumps(
            {
                "schema": "bddk-monthly-request-v1",
                "selector": checked.selector.canonical_selector(),
                "period": period_key(checked.period),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def fetch_request(self) -> FetchRequest:
        return FetchRequest(
            source_ref="bddk:monthly:" + self.fingerprint(),
            url=SecretStr(MONTHLY_ENDPOINT),
            accepted_media_types=("application/json",),
        )

    def form_body(self) -> bytes:
        checked = MonthlyRequest.model_validate(self)
        body = urlencode(
            {
                "tabloNo": checked.selector.table,
                "yil": checked.period.year,
                "ay": checked.period.month,
                "paraBirimi": checked.selector.presentation_currency,
                "taraf": checked.selector.bank_group,
            }
        ).encode("ascii")
        if len(body) > MAX_FORM_BYTES:
            raise ValueError("Monthly request exceeds its form budget")
        return body


def fetch_monthly(request: MonthlyRequest) -> FetchOutcome:
    """Use the common supervised DNS/peer/TLS/bounded-response transport.

    No retries, redirects, auth/cookies or caller-supplied transport settings.
    System trust must verify the certificate and hostname or retrieval fails.
    The operator must separately authorize source access before calling this.
    """
    from kkb_agent.ingest._fetch_process import fetch_in_process

    request = MonthlyRequest.model_validate(request)
    return fetch_in_process(request.fetch_request(), MONTHLY_LIMITS, monthly=request)
