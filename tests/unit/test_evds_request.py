"""M3-07 reviewed EVDS registry and the closed `fe` POST through the fixed worker.

Real HTTP parser with fake DNS/socket/TLS; no network.
"""

import io
import json
from datetime import date

import pytest
from pydantic import SecretStr, ValidationError
from test_bddk_monthly_load import request as monthly_request
from test_bounded_fetch import output_for, wire
from test_bounded_fetch import transport as transport
from test_evds_load import encoded, envelope, rows
from test_reviewed_trust import contexts as contexts
from test_reviewed_trust import reviewed_in

from kkb_agent.catalog.records import CatalogRecord, CatalogStatus
from kkb_agent.core import Aggregation, Frequency, StockFlow, WeeklyAnchor
from kkb_agent.ingest import _fetch_process, _fetch_worker
from kkb_agent.ingest.bddk_monthly_request import MONTHLY_LIMITS
from kkb_agent.ingest.evds_request import (
    EVDS_LIMITS,
    FE_ENDPOINT,
    EvdsRequest,
    EvdsWindow,
    fetch_series,
)
from kkb_agent.ingest.evds_series import (
    REVIEWED_SERIES,
    UnreviewedSeries,
    catalog_record,
    reviewed_series,
    series_semantics,
)
from kkb_agent.ingest.safe_fetch import FetchCode, FetchLimits, FetchRequest, FetchSuccess

WINDOW = EvdsWindow(start=date(2021, 1, 1), end=date(2026, 6, 30))


def evds(code="TP.KFE.TR", window=WINDOW):
    return EvdsRequest(code=code, window=window)


def test_registry_is_closed_to_the_reviewed_first_slice():
    assert set(REVIEWED_SERIES) == {
        "TP.KTF12",
        "TP.TUKFIY2025.GENEL",
        "TP.GENENDEKS.T1",
        "TP.KFE.TR",
    }
    with pytest.raises(TypeError):
        REVIEWED_SERIES["TP.KBK.TRY.18"] = REVIEWED_SERIES["TP.KTF12"]  # type: ignore[index]


@pytest.mark.parametrize(
    "code",
    [
        "TP.KBK.TRY.18",  # Name differs from TP.KTF12 only by a comma; participation banks.
        "TP.BKR.TRY.18",  # Outstanding-portfolio stock rate, not new credit.
        "TP.KFE.TR10",  # Istanbul, not national.
        "bie_kfe",  # A datagroup, not a series.
        "tp.kfe.tr",
        "TP.KFE.TR ",
    ],
)
def test_unreviewed_or_lookalike_codes_fail_before_any_request(code):
    with pytest.raises(UnreviewedSeries):
        reviewed_series(code)
    with pytest.raises(ValidationError):
        evds(code)


def test_catalog_declarations_keep_source_identity_and_explicit_semantics():
    rate = catalog_record(reviewed_series("TP.KTF12"))
    assert CatalogRecord.model_validate_json(rate.model_dump_json()) == rate
    assert (rate.series_id, rate.provider, rate.source_series_id) == (
        "EVDS:TP.KTF12",
        "EVDS",
        "TP.KTF12",
    )
    assert (rate.frequency, rate.weekly_anchor, rate.stock_flow) == (
        Frequency.WEEKLY,
        WeeklyAnchor.FRIDAY,
        StockFlow.RATE,
    )
    assert rate.aggregation.default is Aggregation.AVERAGE and rate.aggregation.sum is False
    assert rate.status is CatalogStatus.UNKNOWN  # EVDS STATUS 1 is undocumented.
    assert rate.group.publisher == "Mevduat, Kalkınma ve Yatırım Bankaları"
    assert len(rate.source.content_hash) == 64 and rate.source.retrieved_at is not None
    bases = {code: reviewed_series(code).base_year for code in REVIEWED_SERIES}
    assert bases == {
        "TP.KTF12": None,
        "TP.TUKFIY2025.GENEL": 2025,
        "TP.GENENDEKS.T1": 2003,
        "TP.KFE.TR": 2023,
    }
    for code in REVIEWED_SERIES:
        assert not series_semantics(reviewed_series(code)).unresolved


def test_request_body_asks_for_original_observations_only():
    body = json.loads(evds("TP.KTF12").json_body())
    assert body == {
        "type": "json",
        "series": "TP.KTF12",
        "aggregationTypes": "avg",
        "formulas": "0",
        "startDate": "01-01-2021",
        "endDate": "30-06-2026",
        "frequency": "3",  # Native weekly: no server-side frequency conversion.
        "decimalSeperator": ".",
        "decimal": "8",  # Client maximum, so the server does not round.
        "dateFormat": "0",
        "lang": "tr",
        "yon": "0",
        "sira": "0",
        "ozelFormuller": [],
        "groupSeperator": False,
        "isRaporSayfasi": False,
    }
    assert json.loads(evds().json_body())["frequency"] == "5"


@pytest.mark.parametrize(
    "start,end",
    [
        (date(2021, 1, 2), date(2021, 6, 30)),  # Monthly windows span whole months.
        (date(2021, 1, 1), date(2021, 6, 29)),
        (date(2021, 6, 30), date(2021, 1, 1)),
        (date(1999, 12, 1), date(2000, 1, 31)),
        (date(2000, 1, 1), date(2013, 1, 31)),
    ],
)
def test_invalid_windows_are_refused(start, end):
    with pytest.raises(ValidationError):
        evds(window=EvdsWindow(start=start, end=end))


def test_weekly_windows_may_use_any_days_and_identity_is_deterministic():
    weekly = evds("TP.KTF12", EvdsWindow(start=date(2021, 1, 3), end=date(2021, 2, 17)))
    assert weekly.fingerprint() == evds("TP.KTF12", weekly.window).fingerprint()
    assert weekly.fingerprint() != evds("TP.KTF12").fingerprint() != evds().fingerprint()
    fetch = evds().fetch_request()
    assert fetch.url.get_secret_value() == FE_ENDPOINT
    assert fetch.accepted_media_types == ("application/json",)


@pytest.mark.parametrize("extra", [{"url": "https://evil.test"}, {"headers": {"Cookie": "x"}}])
def test_request_cannot_carry_network_controls(extra):
    with pytest.raises(ValidationError):
        EvdsRequest.model_validate({"code": "TP.KFE.TR", "window": WINDOW, **extra})


def fetch(req=None):
    req = req or evds()
    return _fetch_worker.fetch_once(req.fetch_request(), EVDS_LIMITS, lambda: None, evds=req)


def test_post_sends_fixed_json_client_headers_and_system_trust_only(transport, contexts):
    payload = encoded(envelope(rows(evds())))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])
    result = fetch()
    assert isinstance(result, FetchSuccess) and result.content == payload
    assert transport.resolutions == [("evds3.tcmb.gov.tr", 443)]
    assert transport.tls == ["evds3.tcmb.gov.tr"]
    sent = b"".join(transport.sockets[0].sent)
    assert sent.startswith(b"POST /igmevdsms-dis/fe HTTP/1.1\r\n")
    assert b"Content-Type: application/json\r\n" in sent
    assert b"Origin: https://evds3.tcmb.gov.tr\r\n" in sent
    assert b"Referer: https://evds3.tcmb.gov.tr/tumSeriler\r\n" in sent
    assert b"Cookie:" not in sent and b"Authorization:" not in sent
    assert sent.endswith(evds().json_body())
    (context,) = contexts
    assert reviewed_in(context) == []  # The BDDK issuer never reaches EVDS.


@pytest.mark.parametrize(
    "change",
    [
        {"url": SecretStr("https://evil.test/igmevdsms-dis/fe")},
        {"url": SecretStr("https://evds3.tcmb.gov.tr/igmevdsms-dis/fe/excel-indir")},
        {"source_ref": "evds:fe:other"},
    ],
)
def test_worker_rejects_changed_descriptor_before_dns(transport, change):
    req = evds()
    altered = req.fetch_request().model_copy(update=change)
    result = _fetch_worker.fetch_once(altered, EVDS_LIMITS, lambda: None, evds=req)
    assert result.code == FetchCode.INVALID_REQUEST and not transport.resolutions


def test_worker_rejects_other_limits_and_two_descriptors(transport):
    req = evds()
    wider = EVDS_LIMITS.model_copy(update={"max_redirects": 3})
    assert (
        _fetch_worker.fetch_once(req.fetch_request(), wider, lambda: None, evds=req).code
        == FetchCode.INVALID_REQUEST
    )
    both = _fetch_worker.fetch_once(
        req.fetch_request(), EVDS_LIMITS, lambda: None, evds=req, monthly=monthly_request()
    )
    assert both.code == FetchCode.INVALID_REQUEST and not transport.resolutions
    assert (
        _fetch_process.fetch_in_process(
            monthly_request().fetch_request(), MONTHLY_LIMITS, monthly=monthly_request(), evds=req
        ).code
        == FetchCode.INVALID_REQUEST
    )


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_post_redirects_are_never_followed(transport, status):
    transport.wire = wire(b"", status=status, headers=[("Location", "https://evds2.tcmb.gov.tr/")])
    assert fetch().code == FetchCode.REDIRECT_LIMIT
    assert len(transport.sockets) == 1


def test_html_error_page_is_a_content_type_failure(transport):
    transport.wire = wire(b"<html>Error</html>", headers=[("Content-Type", "text/html")])
    assert fetch().code == FetchCode.CONTENT_TYPE


def test_parent_dispatch_serializes_only_the_closed_contract(transport, monkeypatch):
    payload = encoded(envelope(rows(evds())))
    transport.wire = wire(payload, headers=[("Content-Type", "application/json")])

    class InlineWorker:
        returncode = 0
        stdin = stdout = None

        def communicate(self, message, *, timeout):
            data = json.loads(message)
            assert set(data["evds"]) == {"code", "window"} and "monthly" not in data
            result = _fetch_worker.fetch_once(
                FetchRequest.model_validate(data["request"]),
                FetchLimits.model_validate(data["limits"]),
                lambda: None,
                evds=EvdsRequest.model_validate(data["evds"]),
            )
            return b"CONNECTED\n" + output_for(result), None

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(_fetch_process.subprocess, "Popen", lambda *a, **k: InlineWorker())
    assert fetch_series(evds()).content == payload


def test_worker_main_revalidates_the_descriptor(transport, monkeypatch):
    transport.wire = wire(b"{}", headers=[("Content-Type", "application/json")])
    req = evds()
    data = req.fetch_request().model_dump(mode="json")
    data["url"] = FE_ENDPOINT
    message = {
        "request": data,
        "limits": EVDS_LIMITS.model_dump(mode="json"),
        "evds": req.model_dump(mode="json"),
    }

    class Input:
        buffer = io.BytesIO(json.dumps(message).encode())

    class Output:
        buffer = io.BytesIO()

    monkeypatch.setattr(_fetch_worker.sys, "stdin", Input())
    monkeypatch.setattr(_fetch_worker.sys, "stdout", Output())
    assert _fetch_worker.main() == 0 and b"POST " in b"".join(transport.sockets[0].sent)
    message["evds"]["code"] = "TP.KBK.TRY.18"
    Input.buffer = io.BytesIO(json.dumps(message).encode())
    Output.buffer = io.BytesIO()
    assert _fetch_worker.main() == 1 and Output.buffer.getvalue() == b""
    assert len(transport.sockets) == 1
