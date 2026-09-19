"""A script-driven index page, end to end: outline -> endpoint -> monthly table -> join.

The fake site mirrors the shape of Borsa Istanbul's index pages: an HTML shell,
a same-site script that names a JSON endpoint, and daily closing values.
"""

import json
from datetime import date

import pytest
from test_address_outline import PAGE, SCRIPT, Site
from test_catalog_continuation import CATALOG, TOTAL
from test_document_dataset import BASE, seed
from test_document_table import ask, step

from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService
from kkb_agent.llm import scripted

HOST = "https://www.borsa.example.tr"
PAGE_URL = f"{HOST}/endeks/xtumy"
ENDPOINT = f"{HOST}/graphic.php?veriTuru=endeks-graphic&indexCode=XTUMY"


def daily_index():
    rows, day, level = [], date(2025, 7, 1), 1000.0
    while day <= date(2026, 7, 10):
        # A wave: the index rises and falls inside every month and year.
        level += 7.0 if (day.toordinal() // 9) % 2 == 0 else -5.0
        rows.append({"indexName": "XTUMY", "clval": round(level, 2), "hisTs": day.isoformat()})
        day = date.fromordinal(day.toordinal() + 1)
    return rows


def site(rows):
    return Site(
        {
            PAGE_URL: (PAGE, "text/html"),
            f"{HOST}/file/js/app.js?v=1": (SCRIPT, "application/javascript"),
            ENDPOINT: (json.dumps({"data": rows}).encode(), "application/json"),
        }
    )


@pytest.fixture
def runtime(tmp_path):
    from fastapi.testclient import TestClient

    clients = []

    def start(fetch, *responses):
        root = tmp_path.resolve() / "prepared"
        seed(root)
        runner = PreparedRunner(
            scripted(*responses),
            root,
            tmp_path.resolve() / "runtime",
            catalog_bytes=CATALOG.read_bytes(),
            web_url_fetch=fetch,
        )
        service = AnalysisService(runner, mode="scripted", selected_runner=runner.selected)
        client = TestClient(create_app(service, prepared=runner.status), base_url=BASE)
        client.__enter__()
        clients.append(client)
        created = client.post("/v1/sessions", json={}).json()
        return runner, client, created["session_id"], {"X-KKB-Session-Token": created["token"]}

    yield start
    for client in clients:
        client.__exit__(None, None, None)


def endpoint_table(**extra):
    arguments = {
        "url": PAGE_URL,
        "follow": "endpoint_1",
        "period_column": "hisTs",
        "value_columns": ["clval"],
        "daily_to_monthly": "last",
        **extra,
    }
    return step("t", "web_url", **arguments)


def test_index_page_endpoint_becomes_a_monthly_table_joined_with_prepared_data(runtime):
    rows = daily_index()
    fetch = site(rows)
    runner, client, sid, headers = runtime(
        fetch,
        endpoint_table(),
        "Endeks tablosu hazır.",
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Kredi eklendi.",
        step(
            "c",
            "change_detection",
            operation="table_co_movement",
            source="analiz_2",
            driver_column="clval",
            target_column=TOTAL,
            driver_direction="up",
            target_direction="up",
        ),
        "Karşılaştırıldı.",
    )
    first = ask(
        client, sid, headers, f"{PAGE_URL} sayfasındaki endeksin ay sonu değerlerini tablo yap."
    )
    assert first["answer"]["status"] == "accepted", first
    table = first["answer"]["result"]
    cells = {c["period"]["end"]: c["value"] for c in table["cells"] if c["label"] == "clval"}
    expected = {}
    for row in rows:
        expected[row["hisTs"][:7]] = row["clval"]  # later days overwrite: last of month
    assert cells["2025-07-31"] == expected["2025-07"]
    assert cells["2026-06-30"] == expected["2026-06"]
    assert len(cells) == 13  # July 2025 .. July 2026; July 2026 ended before retrieval
    assert {cell["unit"] for cell in table["cells"]} == {None}
    assert {cell["scale"] for cell in table["cells"]} == {"unknown"}
    assert {cell["measure"] for cell in table["cells"]} == {"unknown"}
    limitations = " ".join(table["proof"]["limitations"])
    assert "last daily observation" in limitations

    planner = [m.content for m in runner._provider.seen[0]]
    outline = next(m for m in planner if m.startswith("What the web address in the question"))
    assert '"name": "endpoint_1"' in outline and '"hisTs"' in outline
    assert str(rows[5]["clval"]) not in outline
    # Page, script and endpoint once each: the tool reused the outlined bytes.
    assert sorted(set(fetch.requests)) == sorted(fetch.requests)

    second = ask(
        client, sid, headers, "Toplam konut kredisini ekle.", selected_result_id=table["result_ref"]
    )
    assert second["answer"]["status"] == "accepted", second
    third = ask(
        client,
        sid,
        headers,
        "Endeks ile kredi aynı yönde mi?",
        selected_result_id=second["answer"]["result"]["result_ref"],
    )
    assert third["answer"]["status"] == "accepted", third


@pytest.mark.parametrize("code", ["XTUMY", "XU100"])
def test_reviewed_borsa_index_close_has_points_not_currency_and_keeps_proof(runtime, code):
    official = "https://www.borsaistanbul.com"
    page_url = f"{official}/endeks/{code.lower()}"
    endpoint = f"{official}/graphic.php?veriTuru=endeks-graphic&indexCode={code}"
    rows = [
        {"indexName": code, "clval": 1000.0 + day, "hisTs": date(2026, month, day).isoformat()}
        for month in (1, 2, 3)
        for day in (1, 2)
    ]
    fetch = Site(
        {
            page_url: (PAGE, "text/html"),
            f"{official}/file/js/app.js?v=1": (SCRIPT, "application/javascript"),
            endpoint: (json.dumps({"data": rows}).encode(), "application/json"),
        }
    )
    _, client, sid, headers = runtime(fetch, endpoint_table(url=page_url), "Endeks tablosu hazır.")
    answer = ask(client, sid, headers, f"{page_url} endeksinin ay sonu kapanışlarını göster.")
    assert answer["answer"]["status"] == "accepted", answer
    table = answer["answer"]["result"]
    assert {cell["unit"] for cell in table["cells"]} == {"index_points"}
    assert {cell["scale"] for cell in table["cells"]} == {"one"}
    assert {cell["measure"] for cell in table["cells"]} == {"index"}
    assert all("currency" not in cell and cell["unit"] != "TRY" for cell in table["cells"])
    # JSON endpoint proof is partial in the existing API projection, but its
    # verified execution/lineage step must not disappear with the new mapping.
    assert table["proof"]["availability"] == "partial"
    assert table["proof"]["steps"][0]["producer"] == "web_url"
    assert not table["proof"]["unresolved_semantics"]


def test_the_monthly_rule_must_come_from_the_question(runtime):
    runner, client, sid, headers = runtime(site(daily_index()), endpoint_table(), "Tablo hazır.")
    answer = ask(client, sid, headers, f"{PAGE_URL} endeks değerlerini tablo yap.")
    assert answer["answer"]["status"] == "abstained", answer


def test_an_endpoint_name_not_in_this_turns_outline_is_never_fetched(runtime):
    fetch = site(daily_index())
    _, client, sid, headers = runtime(fetch, endpoint_table(follow="endpoint_9"), "Tablo hazır.")
    answer = ask(client, sid, headers, f"{PAGE_URL} ay sonu değerleri.")
    assert answer["answer"]["status"] == "abstained", answer
    assert all("endpoint_9" not in url for url in fetch.requests)
