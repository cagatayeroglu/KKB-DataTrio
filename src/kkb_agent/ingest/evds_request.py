"""Closed EVDS `fe` request contract; no caller-selected URL, headers or body.

The JSON body mirrors the EVDS3 web client (captured 2026-09-14) with every
option fixed for original observations: the series' native frequency (so no
server-side frequency conversion), level formula `0`, no custom formulas, a dot
decimal separator, no group separator and the client's maximum eight decimals
(so the server does not round values). The server refuses requests without the
client's Origin/Referer; they are fixed constants here, never credentials.

This infrastructure is not a planner tool or source-access permission. Only
series in the reviewed M3-07 registry reach transport.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from typing import Annotated, Self

from pydantic import ConfigDict, Field, SecretStr, model_validator

from kkb_agent.core import Frequency
from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.evds_series import ReviewedEvdsSeries, reviewed_series
from kkb_agent.ingest.safe_fetch import FetchLimits, FetchOutcome, FetchRequest

FE_ENDPOINT = "https://evds3.tcmb.gov.tr/igmevdsms-dis/fe"
CLIENT_HEADERS = (
    ("Origin", "https://evds3.tcmb.gov.tr"),
    ("Referer", "https://evds3.tcmb.gov.tr/tumSeriler"),
)
MAX_WINDOW_DAYS = 12 * 366
MAX_BODY_BYTES = 512
# Operator ceilings, not claims about EVDS quotas or a permission to fetch.
EVDS_LIMITS = FetchLimits(
    max_url_chars=256,
    max_header_bytes=16 * 1024,
    max_response_bytes=1024 * 1024,
    max_decompressed_bytes=2 * 1024 * 1024,
    max_redirects=0,
)
SeriesCode = Annotated[str, Field(strict=True, pattern=r"^TP\.[A-Z0-9_.]{1,60}$")]


def _evds_date(value: date) -> str:
    return f"{value.day:02d}-{value.month:02d}-{value.year:04d}"


class EvdsWindow(ContractModel):
    """Inclusive calendar dates; an observation belongs if its period ends inside."""

    model_config = ConfigDict(frozen=True)
    start: date
    end: date

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if not date(2000, 1, 1) <= self.start <= self.end <= date(2100, 12, 31):
            raise ValueError("EVDS window must be ordered and within 2000..2100")
        if (self.end - self.start).days + 1 > MAX_WINDOW_DAYS:
            raise ValueError("EVDS window exceeds its day budget")
        return self


class EvdsRequest(ContractModel):
    """Serialized across the fixed worker boundary and revalidated there."""

    model_config = ConfigDict(frozen=True)
    code: SeriesCode
    window: EvdsWindow

    @model_validator(mode="after")
    def supported(self) -> Self:
        series = reviewed_series(self.code)
        if series.frequency is Frequency.MONTHLY and (
            self.window.start.day != 1
            or self.window.end.day
            != calendar.monthrange(self.window.end.year, self.window.end.month)[1]
        ):
            raise ValueError("A monthly EVDS window must span whole months")
        return self

    @property
    def series(self) -> ReviewedEvdsSeries:
        return reviewed_series(EvdsRequest.model_validate(self).code)

    def fingerprint(self) -> str:
        checked = EvdsRequest.model_validate(self)
        payload = json.dumps(
            {"schema": "evds-fe-request-v1", "body": json.loads(checked.json_body())},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def fetch_request(self) -> FetchRequest:
        return FetchRequest(
            source_ref="evds:fe:" + self.fingerprint(),
            url=SecretStr(FE_ENDPOINT),
            accepted_media_types=("application/json",),
        )

    def json_body(self) -> bytes:
        checked = EvdsRequest.model_validate(self)
        series = reviewed_series(checked.code)
        body = json.dumps(
            {
                "type": "json",
                "series": series.code,
                "aggregationTypes": "avg",
                "formulas": "0",
                "startDate": _evds_date(checked.window.start),
                "endDate": _evds_date(checked.window.end),
                "frequency": str(series.request_frequency),
                "decimalSeperator": ".",
                "decimal": "8",
                "dateFormat": "0",
                "lang": "tr",
                "yon": "0",
                "sira": "0",
                "ozelFormuller": [],
                "groupSeperator": False,
                "isRaporSayfasi": False,
            },
            separators=(",", ":"),
        ).encode("ascii")
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("EVDS request exceeds its body budget")
        return body


def fetch_series(request: EvdsRequest) -> FetchOutcome:
    """Use the common supervised DNS/peer/TLS/bounded-response transport.

    No retries, redirects, cookies or caller-supplied transport settings. System
    trust must verify EVDS; no reviewed issuer is added for this host.
    The operator must separately authorize source access before calling this.
    """
    from kkb_agent.ingest._fetch_process import fetch_in_process

    request = EvdsRequest.model_validate(request)
    return fetch_in_process(request.fetch_request(), EVDS_LIMITS, evds=request)
