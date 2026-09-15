"""M3-04 fixture oracles only; no adapter, network or source interpretation."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1] / "fixtures/sources"
HASHES = {
    "bddk/display_cases.json": ("707aa8e7012da0dc0b3e5fc87d2f87079e19bd51b59ada7099e8cfffec2921de"),
    "bddk/monthly_stock_2026_01.json": (
        "102f3837150ba69a7ed76f9d0957aab351cbe0dea4dc53d1ad3b51cfabbf31b3"
    ),
    "bddk/monthly_stock_2026_02.json": (
        "2cc4d3e870e8994e3bfd8247ac67e48843d727c03ca1622e3c05226236c72c95"
    ),
    "bddk/monthly_ytd_2025_12.json": (
        "69d267b262cbe7c8648b98c947329e9d0aae30f628cac4467460f478b6f81ce4"
    ),
    "bddk/monthly_ytd_2026_01.json": (
        "4f7efed2ffbcf61a3915816a3827be2e7a9582edda8a2d407c04a67b192ebda1"
    ),
    "evds/datagroup_records.json": (
        "fd43d1e036a05d736e67f6201b7f81188b98b97e651feb02abe6305c287d9880"
    ),
    "evds/observations.json": ("2fea1b230e391e4c0390e6e50d7d5f208009bc87f81b2be06a8ac9018612fca8"),
    "evds/series_records.json": (
        "10599f0bcfb63ddd3542a62e614048a79a796f73a393f4525a979792324e4b09"
    ),
}


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def unique_pairs(pairs):
    result = dict(pairs)
    assert len(result) == len(pairs), "Duplicate JSON keys hide fixture fields"
    return result


@pytest.mark.parametrize("name", HASHES)
def test_fixtures_are_small_stable_utf8_json_without_hidden_fields(name):
    raw = (ROOT / name).read_bytes()
    assert 0 < len(raw) < 4096
    assert raw.endswith(b"\n") and b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8", errors="strict")
    json.loads(text, object_pairs_hook=unique_pairs)
    assert hashlib.sha256(raw).hexdigest() == HASHES[name]
    # Hash + field oracles pin reviewed synthetic values; the normal PR gate
    # additionally runs the repository's secret scanner.
    assert not re.search(r"(?i)api[_-]?key|password|authorization|bearer|cookie|token|secret", text)


def test_inventory_and_documented_fidelity_limits():
    assert {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.json")} == set(HASHES)
    assert sum((ROOT / name).stat().st_size for name in HASHES) < 8192
    note = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "not real captured responses",
        "colModels",
        "Project-owned case container",
        "not the uncaptured category/catalog envelope",
        "POST request bodies",
        "not a newly inferred provider timezone guarantee",
    ):
        assert phrase in note
    for link in re.findall(r"\]\(([^)]+)\)", note):
        assert (ROOT / link).is_file()


@pytest.mark.parametrize(
    "name,caption,label,values",
    [
        (
            "monthly_stock_2026_01.json",
            "Tüketici Kredileri (milyon TL), Dönem:2026/1",
            "Tüketici Kredileri - Konut",
            [300, 5, 305],
        ),
        (
            "monthly_stock_2026_02.json",
            "Tüketici Kredileri (milyon TL), Dönem:2026/2",
            "Tüketici Kredileri - Konut",
            [295, 4, 299],
        ),
        (
            "monthly_ytd_2025_12.json",
            "Kar Zarar (milyon TL), Dönem:2025/12",
            "DÖNEM NET KARI (ZARARI)",
            [80, 4, 84],
        ),
        (
            "monthly_ytd_2026_01.json",
            "Kar Zarar (milyon TL), Dönem:2026/1",
            "DÖNEM NET KARI (ZARARI)",
            [8, 1, 9],
        ),
    ],
)
def test_monthly_documented_projection_and_numeric_cells(name, caption, label, values):
    payload = read("bddk/" + name)
    assert set(payload) == {"success", "Json"} and payload["success"] is True
    table = payload["Json"]
    assert set(table) == {"caption", "colNames", "data"}  # colModels schema is uncaptured.
    assert table["caption"] == caption
    assert table["colNames"] == ["", "", "", "BasitFont", "TP", "YP", "Toplam"]
    assert table["data"] == {
        "page": "1",
        "total": "1",
        "records": "1",
        "rows": [{"id": "9001", "cell": ["Sektör", 9001, label, "", *values]}],
    }
    assert all(type(value) is int for value in table["data"]["rows"][0]["cell"][4:])


def test_monthly_decline_and_year_boundary_remain_distinct_cases():
    def total(name):
        return read("bddk/" + name)["Json"]["data"]["rows"][0]["cell"][-1]

    # Only pin the synthetic input pattern. No stock/cumulative classifier here.
    assert total("monthly_stock_2026_02.json") < total("monthly_stock_2026_01.json")
    assert total("monthly_ytd_2026_01.json") < total("monthly_ytd_2025_12.json")


def test_weekly_display_cases_keep_opaque_ids_and_friday_caption():
    cases = read("bddk/display_cases.json")
    assert cases["fixture_kind"] == "project_owned_synthetic_display_cases"
    assert cases["weekly"]["transport"] == "server-rendered HTML"
    assert cases["weekly"]["options"] == [
        {
            "donemId": 90001,
            "label": "Ocak/2 (1. Hafta)",
            "caption": "Sektör / Krediler (2 Ocak 2026 Cuma) (Milyon TL)",
        },
        {
            "donemId": 90002,
            "label": "Ocak/9 (2. Hafta)",
            "caption": "Sektör / Krediler (9 Ocak 2026 Cuma) (Milyon TL)",
        },
    ]
    assert datetime(2026, 1, 2).weekday() == datetime(2026, 1, 9).weekday() == 4


def test_finturk_display_cases_keep_quarters_scale_and_unknown_column_units():
    case = read("bddk/display_cases.json")["finturk"]
    assert case == {
        "period_options": ["2026-3", "2026-6"],
        "display_metadata": [
            {"table": "Krediler", "unit_text": ["Bin TL"]},
            {"table": "Oranlar", "unit_text": ["%"]},
            {"table": "Şubeler ve Nüfusa Göre Dağılım", "unit_text": ["Adet", "TL"]},
        ],
        "column_units": "unknown",
    }


def test_evds_record_projections_keep_missing_links_archive_and_source_casing():
    groups = read("evds/datagroup_records.json")
    assert len(groups) == 4 and len({g["DATAGROUP_CODE"] for g in groups}) == 4
    required = {"DATAGROUP_CODE", "DATAGROUP_TYPE", "FREQUENCY_STR", "DATASOURCE"}
    documented = required | {"METADATA_LINK", "REV_POL_LINK", "APP_CHA_LINK"}
    for group in groups:
        assert required <= group.keys() <= documented
        assert group["DATAGROUP_CODE"].startswith("synthetic_m304_")
        for key in documented - required:
            if key in group:
                url = urlsplit(group[key])
                assert url.hostname == "metadata.example.invalid"
                assert url.username is None and url.password is None and not url.query
    assert [g["FREQUENCY_STR"] for g in groups] == [
        "HAFTALIK(CUMA)",
        "HAFTALIK(ÇARŞAMBA)",
        "AYLIK",
        "AYLIK",
    ]
    assert groups[0]["DATASOURCE"] == "BANKALAR" and groups[1]["DATASOURCE"] == "Bankalar"
    assert "REV_POL_LINK" not in groups[0] and "METADATA_LINK" not in groups[1]
    assert groups[2]["DATAGROUP_TYPE"] == "Sentetik Fiyat Endeksi (2003=100) (Arşiv)"
    assert groups[3]["DATAGROUP_TYPE"] == "Sentetik Fiyat Endeksi (2025=100)"
    # No undocumented ACTIVE/ARCHIVED flag is invented from a title marker.


def test_evds_ambiguous_names_native_cadence_and_aggregation_flags():
    series = read("evds/series_records.json")
    assert [s["SERIE_CODE"] for s in series] == [f"TP.SYNTH.M304.{s}" for s in "ABCDE"]
    assert series[0]["SERIE_NAME"].replace("Kredisi,", "Kredisi") == series[1]["SERIE_NAME"]
    assert series[2]["SERIE_NAME"] == series[3]["SERIE_NAME"]
    assert [s["FREQUENCY_STR"] for s in series] == [
        "HAFTALIK(CUMA)",
        "HAFTALIK(CUMA)",
        "AYLIK",
        "AYLIK",
        "HAFTALIK(ÇARŞAMBA)",
    ]
    flags = {
        "DEFAULT_AGG_METHOD": "avg",
        "AVGABLE": 1,
        "SUMABLE": 0,
        "FIRSTABLE": 1,
        "LASTABLE": 1,
        "MAXABLE": 1,
        "MINABLE": 1,
    }
    for record in series:
        assert set(record) == {"SERIE_CODE", "SERIE_NAME", "FREQUENCY_STR"} | flags.keys()
        assert {key: record[key] for key in flags} == flags


def test_evds_observation_shape_preserves_decimal_and_date_ambiguity():
    payload = read("evds/observations.json")
    assert set(payload) == {"totalCount", "items"}
    assert payload["totalCount"] == len(payload["items"]) == 2
    assert [row["TP_SYNTH_M304_A"] for row in payload["items"]] == ["46,750", "47,125"]
    assert [row["TP_SYNTH_M304_B"] for row in payload["items"]] == ["12,345", "13,001"]
    assert [row["F-1"] for row in payload["items"]] == ["77,007", "78,125"]
    keys = {s["SERIE_CODE"].replace(".", "_") for s in read("evds/series_records.json")[:2]}
    fixture_zone = timezone(timedelta(hours=3))
    for week, row in enumerate(payload["items"], start=1):
        assert set(row) == keys | {"Tarih", "YEARWEEK", "F-1", "UNIXTIME"}
        assert row["YEARWEEK"] == f"2026-{week}"
        assert all(re.fullmatch(r"\d+,\d{3}", row[key]) for key in keys | {"F-1"})
        label_date = datetime.strptime(row["Tarih"], "%d-%m-%Y")
        wrong_date = datetime.strptime(row["Tarih"], "%m-%d-%Y")
        assert label_date != wrong_date and label_date.weekday() == 4
        assert set(row["UNIXTIME"]) == {"$numberLong"}
        timestamp = row["UNIXTIME"]["$numberLong"]
        assert isinstance(timestamp, str) and timestamp.isdigit()
        assert datetime.fromtimestamp(int(timestamp), UTC).astimezone(fixture_zone) == (
            label_date.replace(tzinfo=fixture_zone)
        )
