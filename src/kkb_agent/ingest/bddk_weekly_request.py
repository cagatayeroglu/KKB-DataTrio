"""Closed weekly request contract; no caller-selected URL, headers or POST body.

The weekly bulletin serves an item's history through one stateless endpoint: asked for a
date, it answers with the published weeks dated within the ninety days up to it (measured
2026-09-20: asked 17.09 the answer began 19.06, asked 18.09 it began 26.06; the `gun` field
is sent as the page sends it and changes nothing). Asked for a Friday whose week is
published, that is exactly thirteen weeks, so a series is read as a few thirteen-week
windows and one shorter answer dated today. Only selectors the pinned listing supports
reach transport, and the model supplies none of this: not the address, not the item, not
the date.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Final, Self
from urllib.parse import urlencode

from pydantic import ConfigDict, SecretStr, model_validator

from kkb_agent.core.models import ContractModel
from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.bddk_weekly import COLUMNS, listed_weekly
from kkb_agent.ingest.safe_fetch import FetchLimits, FetchOutcome, FetchRequest

WEEKLY_ENDPOINT: Final = "https://www.bddk.org.tr/BultenHaftalik/tr/Home/KiyaslamaJsonGetir"
#: Weeks an answer dated to a published Friday carries, and so the distance between two
#: windows of one series. An answer dated to another day carries fewer.
WEEKS_PER_ANSWER: Final = 13
#: The first week a series is read from: a Friday, and the start of the period the product
#: is prepared for (DEC-137), so a weekly series spans what the monthly ones span.
FIRST_WEEK: Final = date(2021, 1, 1)
MAX_WINDOWS: Final = 60
MAX_FORM_BYTES: Final = 256
# Operator ceilings, not claims about BDDK quotas or a permission to fetch.
WEEKLY_LIMITS: Final = FetchLimits(
    max_url_chars=256,
    max_header_bytes=16 * 1024,
    max_response_bytes=64 * 1024,
    max_decompressed_bytes=128 * 1024,
    max_redirects=0,
)


def friday_of(day: date) -> date:
    """The Friday of the Monday-to-Sunday week `day` falls in."""
    return day + timedelta(days=4 - day.weekday())


class WeeklyRequest(ContractModel):
    """Serialized across the fixed worker boundary and revalidated there.

    `asked` is the date handed to the source, not a period: the answer holds the published
    weeks dated within the ninety days up to it.
    """

    model_config = ConfigDict(frozen=True)
    selector: BddkSelector
    asked: date

    @model_validator(mode="after")
    def supported(self) -> Self:
        listed_weekly(self.selector)
        if not FIRST_WEEK <= self.asked <= date(2100, 12, 31):
            raise ValueError("Weekly request date is outside the supported range")
        return self

    def fingerprint(self) -> str:
        checked = WeeklyRequest.model_validate(self)
        payload = json.dumps(
            {
                "schema": "bddk-weekly-request-v1",
                "selector": checked.selector.canonical_selector(),
                "asked": checked.asked.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def fetch_request(self) -> FetchRequest:
        return FetchRequest(
            source_ref="bddk:weekly:" + self.fingerprint(),
            url=SecretStr(WEEKLY_ENDPOINT),
            accepted_media_types=("application/json",),
        )

    def form_body(self) -> bytes:
        checked = WeeklyRequest.model_validate(self)
        selector = checked.selector
        body = urlencode(
            {
                "dil": "tr",
                "tarih": f"{checked.asked:%d.%m.%Y}",
                "id": f"{selector.table}.0.{selector.row}",
                "parabirimi": "TRY",
                "sutun": COLUMNS[selector.value_dimension][0],
                "gun": 90,
                "tarafKodu": selector.bank_group,
            }
        ).encode("ascii")
        if len(body) > MAX_FORM_BYTES:
            raise ValueError("Weekly request exceeds its form budget")
        return body


def grid_windows(latest: date) -> tuple[date, ...]:
    """The fixed windows whose last week is published: every grid Friday up to `latest`.

    Windows end on a grid of Fridays thirteen weeks apart, counted from `FIRST_WEEK`, never
    from today: a window asked for again next week is the same request, so its kept answer
    still serves (DEC-159). `latest` is the last week the source has published, which the
    caller reads out of the one request dated today; a window ending on or before it is
    complete, and only such windows are returned.
    """
    if latest.weekday() != 4:
        raise ValueError("Weekly windows are counted in Fridays")
    span = timedelta(weeks=WEEKS_PER_ANSWER)
    ends: list[date] = []
    end = FIRST_WEEK + span - timedelta(weeks=1)
    while end <= latest:
        ends.append(end)
        end += span
        if len(ends) > MAX_WINDOWS:
            raise ValueError("Weekly range needs more windows than one series may ask for")
    return tuple(ends)


def fetch_weekly(request: WeeklyRequest) -> FetchOutcome:
    """Use the common supervised DNS/peer/TLS/bounded-response transport.

    No retries, redirects, auth/cookies or caller-supplied transport settings.
    System trust must verify the certificate and hostname or retrieval fails.
    """
    from kkb_agent.ingest._fetch_process import fetch_in_process

    request = WeeklyRequest.model_validate(request)
    return fetch_in_process(request.fetch_request(), WEEKLY_LIMITS, weekly=request)
