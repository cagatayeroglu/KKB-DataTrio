"""DEC-177: a series EVDS lists itself is declared from the source's fields and loaded strictly.

Shapes are the ones measured live on 2026-09-19 (one series per native frequency): every
calendar day for GÜNLÜK, every weekday for İŞ GÜNÜ with holidays as nulls, "2024-1Ç" for
quarters, a JSON number for years, and a Wednesday week stamped with that week's Friday.
Values here are synthetic; no network.
"""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from kkb_agent.core import Aggregation, Frequency, Scale, StockFlow, WeeklyAnchor
from kkb_agent.ingest import evds_load as load
from kkb_agent.ingest.evds_directory import (
    ListedGroup,
    declare_series,
    listed_groups,
    parse_series_list,
    series_list_request,
)
from kkb_agent.ingest.evds_load import EvdsLoadCode, EvdsLoadError, ingest_series, parse_fe
from kkb_agent.ingest.evds_request import EvdsRequest, EvdsWindow, ListedCalendar
from kkb_agent.ingest.evds_series import REVIEWED_SERIES
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.lakehouse import open_lakehouse

SOURCE_DAY = timezone(timedelta(hours=3))


def group(**changes):
    base = {
        "code": "bie_dkdovytl",
        "title": "Döviz Kurları",
        "title_eng": "Exchange Rates",
        "category": "KURLAR",
        "frequency_str": "GÜNLÜK",
        "data_source": "TCMB",
        "unit_text": "Türk lirası",
        "archived": False,
    }
    return ListedGroup(**{**base, **changes})


def listed(code="TP.DK.USD.A.YTL", name="(USD) ABD Doları (Döviz Alış)", **flags):
    raw = {
        "SERIE_CODE": code,
        "SERIE_NAME": name,
        "SERIE_NAME_ENG": "(USD) US Dollar (Buying)",
        "FREQUENCY_STR": flags.pop("frequency", "GÜNLÜK"),
        "DEFAULT_AGG_METHOD": flags.pop("default", "avg"),
        "AVGABLE": 1,
        "SUMABLE": flags.pop("summable", 0),
        "FIRSTABLE": 1,
        "LASTABLE": 1,
        "MINABLE": 1,
        "MAXABLE": 1,
    }
    return {**raw, **flags}


# --- declarations come from the source's own fields ---------------------------------------------


def test_a_listed_series_is_declared_from_its_datagroup_and_its_own_flags():
    dollar = declare_series(group(), listed())
    assert (dollar.code, dollar.unit, dollar.scale) == ("TP.DK.USD.A.YTL", "TRY", Scale.ONE)
    assert (dollar.frequency, dollar.request_frequency) == (Frequency.DAILY, 1)
    assert dollar.stock_flow is StockFlow.STOCK and dollar.aggregation is Aggregation.AVERAGE
    assert dollar.policy.sum is False and dollar.policy.average is True
    assert "incelenmedi" in dollar.note and dollar.datagroup == "bie_dkdovytl"


@pytest.mark.parametrize(
    ("unit_text", "name", "summable", "expected"),
    [
        ("bin TL", "Toplam Krediler", 0, ("TRY", Scale.THOUSAND, StockFlow.STOCK)),
        ("milyon ABD doları", "İhracat", 1, ("USD", Scale.MILLION, StockFlow.FLOW)),
        ("Yüzde", "Politika Faizi", 0, ("percent", Scale.ONE, StockFlow.RATE)),
        ("Ağırlıklı ortalama", "Mevduat Faizi (TL, %)", 0, ("percent", Scale.ONE, StockFlow.RATE)),
        ("", "Üretim Endeksi (2021=100)", 0, ("index", Scale.ONE, StockFlow.INDEX)),
        ("Adet", "Konut Satışları", 1, ("count", Scale.ONE, StockFlow.FLOW)),
    ],
)
def test_units_and_kinds_follow_a_closed_vocabulary(unit_text, name, summable, expected):
    declared = declare_series(
        group(unit_text=unit_text, frequency_str="AYLIK"),
        listed(
            name=name, summable=summable, frequency="AYLIK", default="sum" if summable else "avg"
        ),
    )
    assert (declared.unit, declared.scale, declared.stock_flow) == expected
    if expected[0] == "index":
        assert declared.base_year == 2021


@pytest.mark.parametrize(
    ("changes", "raw"),
    [
        ({"unit_text": "TL/kg, USD/ons, Euro/ons, TL/gr"}, {}),  # several units in one group
        ({"unit_text": ""}, {}),  # no unit anywhere
        ({"unit_text": "Endeks"}, {}),  # an index with no stated base year
        ({"frequency_str": "AYDA İKİ KEZ"}, {"frequency": "AYDA İKİ KEZ"}),  # unread calendar
        ({}, {"name": "Kümülatif Net Satışlar"}),  # a cumulative nobody measured
        ({"unit_text": "Yüzde"}, {"default": "sum", "summable": 1}),  # flags contradict the unit
        ({}, {"code": "XX.NOT.A.CODE"}),
    ],
)
def test_what_cannot_be_derived_stays_undeclared(changes, raw):
    assert declare_series(group(**changes), listed(**raw)) is None


def test_a_default_the_flags_forbid_is_no_declared_aggregation_not_a_dropped_series():
    """Live 2026-09-19: DEFAULT_AGG_METHOD=last with every *ABLE flag 0 (labour series)."""
    flags = {"AVGABLE": 0, "FIRSTABLE": 0, "LASTABLE": 0, "MINABLE": 0, "MAXABLE": 0}
    labour = group(code="bie_tisguc", title="Temel İşgücü Göstergeleri", unit_text="Bin kişi")
    labour = replace(labour, frequency_str="AYLIK")
    people = declare_series(labour, listed("TP.TIG04", "4.İşsiz", default="last", **flags))
    assert (people.unit, people.scale, people.stock_flow) == (
        "count",
        Scale.THOUSAND,
        StockFlow.STOCK,
    )
    assert people.aggregation is Aggregation.UNKNOWN and people.policy.last is False
    # A "(%)" row of a datagroup counted in persons is a rate, whatever the datagroup says.
    rate = declare_series(
        labour, listed("TP.TIG08", "8.İşsizlik oranı (%)", default="last", **flags)
    )
    assert (rate.unit, rate.scale, rate.stock_flow) == ("percent", Scale.ONE, StockFlow.RATE)


def test_a_price_per_quantity_is_its_own_unit_and_a_level():
    gold = replace(group(code="bie_mkaltytl", title="Altın Fiyatları", unit_text=""))
    gram = declare_series(gold, listed("TP.MK.KUL.YTL", "Külçe Altın Satış Fiyatı (TL/Gr)"))
    assert (gram.unit, gram.stock_flow) == ("TRY/g", StockFlow.STOCK)
    ounce = declare_series(
        gold, listed("TP.MK.LON.YTL", "1 Ons Altın Londra Satış Fiyatı (ABD Doları/Ons)")
    )
    assert ounce.unit == "USD/oz"
    dashed = declare_series(
        replace(gold, unit_text="TL/kg, USD/ons, Euro/ons, TL/gr"),
        listed("TP.ALTINPIYASA.KAP02", "Altın - Kapanış Fiyatı  - TL/kg", summable=1),
    )
    assert (dashed.unit, dashed.stock_flow) == ("TRY/kg", StockFlow.STOCK)
    # A bare currency in a name is the thing priced, not the unit.
    assert declare_series(group(), listed()).unit == "TRY"


def test_a_reviewed_code_keeps_its_reviewed_declaration():
    declared = declare_series(group(unit_text="bin TL"), listed(code="TP.KTF12", name="x"))
    assert declared is REVIEWED_SERIES["TP.KTF12"]


def test_the_pinned_directory_and_the_fixed_series_list_address():
    groups = {item.code: item for item in listed_groups()}
    assert len(groups) > 600 and groups["bie_kfe"].title == "Konut Fiyat Endeksi"
    request = series_list_request("bie_kfe")
    assert request.url.get_secret_value().endswith("serieList/fe/type=json&code=bie_kfe")
    for forged in ("bie_kfe&x=1", "../etc", "not_a_listed_group"):
        with pytest.raises(ValueError):
            series_list_request(forged)
    rows, digest = parse_series_list(json.dumps([listed()]).encode())
    assert rows[0]["SERIE_CODE"] == "TP.DK.USD.A.YTL" and len(digest) == 64
    with pytest.raises(ValueError):
        parse_series_list(b'{"not": "a list"}')


# --- the request carries a listed series' calendar ------------------------------------------------


def test_only_published_calendars_cross_the_worker_boundary():
    window = EvdsWindow(start=date(2024, 1, 1), end=date(2024, 3, 31))
    daily = ListedCalendar(frequency=Frequency.DAILY, request_frequency=1)
    request = EvdsRequest(code="TP.DK.USD.A.YTL", window=window, listed=daily)
    assert json.loads(request.json_body())["frequency"] == "1"
    assert json.loads(request.json_body())["series"] == "TP.DK.USD.A.YTL"
    with pytest.raises(ValueError, match="outside the reviewed registry"):
        EvdsRequest(code="TP.DK.USD.A.YTL", window=window)  # no calendar, no request
    with pytest.raises(ValueError):
        ListedCalendar(frequency=Frequency.DAILY, request_frequency=5)
    with pytest.raises(ValueError):
        EvdsRequest(code="TP.KTF12", window=window, listed=daily)  # reviewed stays reviewed
    # A reviewed request is still the closed {code, window} pair on the wire.
    reviewed = EvdsRequest(code="TP.KFE.TR", window=window)
    assert set(reviewed.model_dump(mode="json", exclude_none=True)) == {"code", "window"}


# --- strict loading for every published calendar -----------------------------------------------


def stamp(day):
    moment = datetime(day.year, day.month, day.day, tzinfo=SOURCE_DAY)
    return {"$numberLong": str(int(moment.astimezone(UTC).timestamp()))}


def envelope(code, rows):
    key = code.replace(".", "_")
    items = [
        {"Tarih": label, key: value, "UNIXTIME": stamp(day), **extra}
        for label, day, value, extra in rows
    ]
    return json.dumps({"totalCount": len(items), "items": items}).encode()


def days(start, end):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def request_for(code, frequency, request_frequency, start, end, anchor=None):
    return EvdsRequest(
        code=code,
        window=EvdsWindow(start=start, end=end),
        listed=ListedCalendar(
            frequency=frequency, request_frequency=request_frequency, anchor=anchor
        ),
    )


def test_daily_series_list_every_day_and_business_days_every_weekday():
    start, end = date(2024, 1, 1), date(2024, 1, 14)
    daily = request_for("TP.DK.USD.A.YTL", Frequency.DAILY, 1, start, end)
    rows = [
        (f"{d:%d-%m-%Y}", d, None if d.weekday() >= 5 else "30.10000000", {})
        for d in days(start, end)
    ]
    parsed = parse_fe(envelope("TP.DK.USD.A.YTL", rows), daily)
    assert len(parsed.observations) == 14
    assert sum(o.value is None for o in parsed.observations) == 4  # two weekends
    assert all(o.period_start == o.period_end for o in parsed.observations)

    business = request_for("TP.AB.A01", Frequency.BUSINESS_DAY, 2, start, end)
    weekdays = [row for row, d in zip(rows, days(start, end), strict=True) if d.weekday() < 5]
    assert len(parse_fe(envelope("TP.AB.A01", weekdays), business).observations) == 10
    with pytest.raises(EvdsLoadError):  # a weekend row in a business-day series
        parse_fe(envelope("TP.AB.A01", rows), business)


def test_a_wednesday_week_is_stamped_with_its_friday():
    start, end = date(2024, 1, 1), date(2024, 1, 31)
    request = request_for(
        "TP.D1TOP", Frequency.WEEKLY, 3, start, end, anchor=WeeklyAnchor.WEDNESDAY
    )
    wednesdays = [d for d in days(start, end) if d.weekday() == 2]
    rows = [
        (f"{d:%d-%m-%Y}", d + timedelta(days=2), "1.00000000", {"YEARWEEK": f"2024-{i}"})
        for i, d in enumerate(wednesdays, 1)
    ]
    parsed = parse_fe(envelope("TP.D1TOP", rows), request)
    assert [o.period_end for o in parsed.observations] == wednesdays
    unstamped = [
        (label, day - timedelta(days=2), value, extra) for label, day, value, extra in rows
    ]
    with pytest.raises(EvdsLoadError):
        parse_fe(envelope("TP.D1TOP", unstamped), request)


def test_quarters_and_years_are_read_and_an_unpublished_tail_is_not_a_gap():
    start, end = date(2024, 1, 1), date(2025, 12, 31)
    quarterly = request_for("TP.KVADEALACAKLI.KVDB", Frequency.QUARTERLY, 6, start, end)
    quarters = [(year, q) for year in (2024, 2025) for q in (1, 2, 3, 4)]
    rows = [
        (f"{year}-{q}Ç", date(year, 3 * q - 2, 1), "170499.00000000", {}) for year, q in quarters
    ]
    parsed = parse_fe(envelope("TP.KVADEALACAKLI.KVDB", rows), quarterly)
    assert [o.period_end for o in parsed.observations][:2] == [date(2024, 3, 31), date(2024, 6, 30)]
    # The source omits a quarter it has not published yet: fewer rows at the end are fine...
    assert len(parse_fe(envelope("TP.KVADEALACAKLI.KVDB", rows[:6]), quarterly).observations) == 6
    # ...a quarter missing inside, or nothing at all, is not.
    with pytest.raises(EvdsLoadError):
        parse_fe(envelope("TP.KVADEALACAKLI.KVDB", rows[:2] + rows[3:]), quarterly)
    with pytest.raises(EvdsLoadError):
        parse_fe(envelope("TP.KVADEALACAKLI.KVDB", []), quarterly)

    annual = request_for("TP.SEKBILA1122.GENEL", Frequency.ANNUAL, 8, start, end)
    years = [
        (2024, date(2024, 1, 1), "97521640220.80000000", {}),
        (2025, date(2025, 1, 1), "1.0", {}),
    ]
    parsed = parse_fe(envelope("TP.SEKBILA1122.GENEL", years), annual)
    assert [(o.period_start, o.period_end) for o in parsed.observations] == [
        (date(2024, 1, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 12, 31)),
    ]


def test_a_listed_series_is_stored_with_its_declared_semantics(tmp_path):
    declared = declare_series(group(), listed())
    window = EvdsWindow(start=date(2024, 1, 1), end=date(2024, 1, 7))
    rows = [(f"{d:%d-%m-%Y}", d, "30.10000000", {}) for d in days(window.start, window.end)]

    def source(request):
        assert request.listed is not None and request.code == declared.code
        return FetchSuccess(
            source_ref=request.fetch_request().source_ref,
            content=envelope(declared.code, rows),
            media_type="application/json",
            http_status=200,
        )

    with open_lakehouse(tmp_path / "lake") as lake:
        stored = ingest_series(lake, declared.code, window, retrieve=source, listed=declared)
        assert stored.observations == 7 and stored.series_id == "EVDS:TP.DK.USD.A.YTL"
        row = lake.connection.execute(
            "SELECT unit, scale, frequency, observation, cumulative, aggregation FROM "
            "silver_series WHERE series_id = ?",
            [stored.series_id],
        ).fetchone()
        assert row == ("TRY", "one", "daily", "stock", "none", "average")
        with pytest.raises(EvdsLoadError) as refused:  # another code's declaration is no pass
            ingest_series(lake, "TP.DK.EUR.A.YTL", window, retrieve=source, listed=declared)
        assert refused.value.code is EvdsLoadCode.RETRIEVAL_FAILED
    assert load.LISTED_SEMANTIC_VERSION != load.SEMANTIC_VERSION
