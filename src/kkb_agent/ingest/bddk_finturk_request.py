"""Closed FinTürk request contract; no caller-selected URL, headers or POST body.

One answer is one table for one quarter, for the sector and every province ("HEPSİ"), so
every column and province of a table is read out of the same kept bytes: a table costs one
request a quarter however many of its cells are asked for (`wire_fingerprint`, DEC-176).
Only selectors the pinned listing supports reach transport.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from typing import Annotated, Final, Self
from urllib.parse import urlencode

from pydantic import ConfigDict, Field, SecretStr, StrictInt, model_validator

from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_finturk import listed_finturk
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.safe_fetch import FetchLimits, FetchOutcome, FetchRequest

FINTURK_ENDPOINT: Final = "https://www.bddk.org.tr/BultenFinturk/tr/Home/VeriGetir"
EVERY_PROVINCE: Final = "HEPSİ"
#: The first quarter a series is read from: the period the product is prepared for (DEC-137).
FIRST_QUARTER: Final = (2021, 3)
MAX_QUARTERS: Final = 80
MAX_FORM_BYTES: Final = 256
# Operator ceilings, not claims about BDDK quotas or a permission to fetch.
FINTURK_LIMITS: Final = FetchLimits(
    max_url_chars=256,
    max_header_bytes=16 * 1024,
    max_response_bytes=512 * 1024,
    max_decompressed_bytes=1024 * 1024,
    max_redirects=0,
)


class Quarter(ContractModel):
    """A quarter by its last month, as the source names it: 2026-6."""

    model_config = ConfigDict(frozen=True)

    year: Annotated[StrictInt, Field(ge=2007, le=2100)]
    month: Annotated[StrictInt, Field(ge=3, le=12, multiple_of=3)]

    def key(self) -> str:
        return f"{self.year}-{self.month}"

    def end(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])


def quarters_until(last: Quarter) -> tuple[Quarter, ...]:
    """Every quarter from `FIRST_QUARTER` to `last`, in order."""
    found: list[Quarter] = []
    year, month = FIRST_QUARTER
    while (year, month) <= (last.year, last.month):
        found.append(Quarter(year=year, month=month))
        year, month = (year + 1, 3) if month == 12 else (year, month + 3)
        if len(found) > MAX_QUARTERS:
            raise ValueError("FinTürk range holds more quarters than one series may ask for")
    return tuple(found)


def newest_quarter(today: date) -> Quarter:
    """The last quarter that ended on or before `today`; whether it is published is asked."""
    year, month = today.year, today.month - today.month % 3
    if month == 0:
        year, month = year - 1, 12
    candidate = Quarter(year=year, month=month)
    if candidate.end() > today:
        year, month = (year - 1, 12) if month == 3 else (year, month - 3)
        candidate = Quarter(year=year, month=month)
    return candidate


class FinturkRequest(ContractModel):
    """Serialized across the fixed worker boundary and revalidated there."""

    model_config = ConfigDict(frozen=True)
    selector: BddkSelector
    quarter: Quarter

    @model_validator(mode="after")
    def supported(self) -> Self:
        listed_finturk(self.selector)
        return self

    def fingerprint(self) -> str:
        checked = FinturkRequest.model_validate(self)
        payload = json.dumps(
            {
                "schema": "bddk-finturk-request-v1",
                "selector": checked.selector.canonical_selector(),
                "quarter": checked.quarter.key(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def wire_fingerprint(self) -> str:
        """What is actually asked of the source: a table and a quarter, never a cell."""
        checked = FinturkRequest.model_validate(self)
        payload = json.dumps(
            {"schema": "bddk-finturk-wire-v1", "form": checked.form_body().decode("ascii")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def fetch_request(self) -> FetchRequest:
        return FetchRequest(
            source_ref="bddk:finturk:" + self.fingerprint(),
            url=SecretStr(FINTURK_ENDPOINT),
            accepted_media_types=("application/json",),
        )

    def form_body(self) -> bytes:
        checked = FinturkRequest.model_validate(self)
        body = urlencode(
            [
                ("tabloNo", checked.selector.table),
                ("donem", checked.quarter.key()),
                ("tarafList[0]", checked.selector.bank_group),
                ("sehirList[0]", EVERY_PROVINCE),
            ]
        ).encode("ascii")
        if len(body) > MAX_FORM_BYTES:
            raise ValueError("FinTürk request exceeds its form budget")
        return body


def fetch_finturk(request: FinturkRequest) -> FetchOutcome:
    """Use the common supervised DNS/peer/TLS/bounded-response transport.

    No retries, redirects, auth/cookies or caller-supplied transport settings.
    """
    from kkb_agent.ingest._fetch_process import fetch_in_process

    request = FinturkRequest.model_validate(request)
    return fetch_in_process(request.fetch_request(), FINTURK_LIMITS, finturk=request)
