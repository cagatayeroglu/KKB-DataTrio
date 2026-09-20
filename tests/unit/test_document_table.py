"""M10-04 slice 2: a published monthly table built from a document; no network."""

import json
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
from test_document_check import FakeFetch
from test_prepared_api import BASE, wait_http

from kkb_agent.agent import Workspace
from kkb_agent.agent.verifier import result_faults
from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.proof import build_proof
from kkb_agent.api.service import AnalysisService
from kkb_agent.core import Scale, StockFlow
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.tools._document_column import ColumnRefused
from kkb_agent.tools._document_table import read_table
from kkb_agent.tools._document_value import Grid
from kkb_agent.tools.web_url import WebUrlArguments, declared_units

HEADERS = ("Ay", "Kapanış (Puan)", "Faiz (%)", "Hacim", "Adet (Bin TL)")
ROWS = (
    # "12.5" reads only as English and "4,5" only as Turkish: no convention (DEC-148).
    ("2026-04", "9000", "4,5", "12.5", "1.234"),
    ("2026-05", "9100", "4,25", "13", "2"),
    ("2026-06", "9200", "4", "", "3"),
)
DOCUMENT = (
    "Ay;Kapanış (Puan);Faiz (%);Hacim;Not\n"
    "2026-04;9000;4,5;12;RAW-CONTENT\n"
    "2026-05;9100;4,75;13;x\n"
    "2026-06;9200;4,25;14;y\n"
).encode()
URL = "https://data.example.test/PRIVATE-PATH/bist.csv?token=SECRET-QUERY"
PRIVATE = ("PRIVATE-PATH", "SECRET-QUERY", "RAW-CONTENT")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def grid(rows=ROWS, headers=HEADERS, location=None):
    return Grid(location or {"table": 1}, headers, tuple(rows))


def test_table_keeps_usable_columns_and_names_every_skipped_one():
    table = read_table(
        [grid()],
        "ay",
        ["Kapanış", "Faiz", "Hacim", "Adet", "Yok", "kapanis", "BDDK:x"],
        is_series=lambda label: label == "BDDK:x",
    )
    assert table.months == (date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30))
    assert [(c.label, c.unit, c.unit_source, c.measure) for c in table.columns] == [
        ("Kapanış", "points", "column header", StockFlow.INDEX),
        ("Faiz", "percent", "column header", StockFlow.RATE),
        # No unit in the header: kept, declared unresolved, never guessed.
        ("Hacim", None, None, StockFlow.UNKNOWN),
    ]
    assert [value for _, value, _ in table.columns[1].cells] == [4.5, 4.25, 4.0]
    assert dict(table.skipped) == {
        "Adet": "AMBIGUOUS_NUMBER",
        "Yok": "COLUMN_NOT_FOUND",
        "kapanis": "DUPLICATE_COLUMN",
        "BDDK:x": "COLUMN_NOT_FOUND",
    }


def test_columns_that_share_a_reason_share_one_line():
    """Five columns without a stated unit produced five near-identical lines.

    They read as five different limitations of the answer instead of one fact
    about the document (finding L2-5).
    """
    from datetime import UTC, datetime

    from kkb_agent.ingest.fetched import fetched_source
    from kkb_agent.tools._document_table import table_result

    headers = ("Ay", "Hacim", "Adet", "Islem")
    rows = (
        ("2026-04", "12", "34", "56"),
        ("2026-05", "13", "35", "57"),
        ("2026-06", "14", "36", "58"),
    )
    table = read_table([grid(rows, headers)], "ay", ["Hacim", "Adet", "Islem"])
    assert [column.unit for column in table.columns] == [None, None, None]
    source = fetched_source(
        "https://data.example.test/t.csv",
        b"x",
        retrieved_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    result = table_result(table, source, source_node=None)
    unresolved = result.unresolved_semantics
    assert unresolved == ["Hacim, Adet, Islem: the document states no unit or scale"]
    # The same grouping for the stock/flow statement they all share.
    measures = [note for note in result.limitations if "stocks, flows, rates" in note]
    assert len(measures) == 1 and measures[0].startswith("Hacim, Adet, Islem: ")


def test_a_column_with_fewer_than_two_values_is_left_out():
    rows = (("2026-04", "1", ""), ("2026-05", "", "2"), ("2026-06", "", "3"))
    table = read_table([grid(rows, ("Ay", "A (TL)", "B (TL)"))], "Ay", ["A", "B"])
    assert [c.label for c in table.columns] == ["B"] and table.skipped == (("A", "TOO_FEW_VALUES"),)


@pytest.mark.parametrize(
    ("tables", "code"),
    [
        ([grid(headers=("Tarih", *HEADERS[1:]))], "COLUMN_NOT_FOUND"),
        ([grid(headers=("Ay", "Ay", *HEADERS[2:]))], "AMBIGUOUS_COLUMN"),
        ([grid(), grid(location={"table": 2})], "AMBIGUOUS_COLUMN"),
        ([grid(rows=(*ROWS, ("2026-06", "1", "1", "1", "1")))], "DUPLICATE_PERIOD"),
        ([grid(rows=(*ROWS, ("Ortalama", "1", "1", "1", "1")))], "PERIOD_NOT_RECOGNISED"),
        ([grid(rows=(("2026-04-15", "1", "1", "1", "1"),))], "PERIOD_NOT_RECOGNISED"),
    ],
)
def test_period_problems_refuse_the_whole_table(tables, code):
    with pytest.raises(ColumnRefused) as refused:
        read_table(tables, "Ay", ["Kapanış", "Faiz"])
    assert refused.value.code == code


def test_no_usable_column_refuses_the_table():
    with pytest.raises(ColumnRefused) as refused:
        read_table([grid()], "Ay", ["Yok", "Adet"])
    assert refused.value.code == "NO_USABLE_COLUMN"


def test_a_unit_the_user_wrote_fills_a_header_without_one_but_never_overrides_it():
    table = read_table(
        [grid()],
        "Ay",
        ["Kapanış", "Hacim"],
        declared_units={"Hacim": ("TRY", Scale.THOUSAND), "Kapanış": ("TRY", Scale.ONE)},
    )
    assert [(c.label, c.unit, c.scale, c.unit_source) for c in table.columns] == [
        ("Hacim", "TRY", Scale.THOUSAND, "question")
    ]
    assert dict(table.skipped) == {"Kapanış": "UNIT_CONFLICT"}


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Hacim sütununu ekle.", "UNIT_NOT_IN_QUESTION"),
        ("Hacim adet olarak.", "UNIT_NOT_RECOGNISED"),
    ],
)
def test_a_declared_unit_must_be_written_by_the_user_in_a_known_vocabulary(question, code):
    units = {"Hacim": "bin TL"} if code == "UNIT_NOT_IN_QUESTION" else {"Hacim": "adet"}
    assert declared_units(units, question) == code
    assert declared_units({"Hacim": "Bin TL"}, "Hacim bin TL cinsinden.") == {
        "Hacim": ("TRY", Scale.THOUSAND)
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"period_column": "Ay"},
        {"value_columns": ["Kapanış"]},
        {"period_column": "Ay", "value_columns": ["Kapanış"], "column": "Kapanış", "row": "x"},
        {"period_column": "Ay", "value_columns": ["Kapanış", "Kapanış"]},
        {"period_column": "Ay", "value_columns": [f"C{i}" for i in range(13)]},
        {"period_column": "Ay", "value_columns": []},
    ],
)
def test_table_arguments_are_closed(arguments):
    with pytest.raises(ValidationError):
        WebUrlArguments.model_validate({"attached": True, **arguments})


def runtime(tmp_path, provider, *, fetch=None):
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    runner = PreparedRunner(
        provider,
        root,
        tmp_path.resolve() / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        web_url_fetch=fetch,
        document_uploads=True,
    )
    service = AnalysisService(
        runner,
        mode="scripted",
        selected_runner=runner.selected,
        document_store=runner.admit_document,
    )
    return runner, create_app(service, prepared=runner.status)


def table_plan(**source):
    arguments = {
        "delimiter": ";",
        "period_column": "Ay",
        "value_columns": ["Kapanış", "Faiz", "Hacim"],
        **(source or {"attached": True}),
    }
    return proposal({"step_id": "t", "tool": "web_url", "arguments": arguments})


def step(step_id, tool, **arguments):
    return proposal({"step_id": step_id, "tool": tool, "arguments": arguments})


def ask(client, sid, headers, question, **extra):
    path = f"/v1/sessions/{sid}/turns"
    body = {"request_id": uuid4().hex, "question": question, **extra}
    admitted = client.post(path, json=body, headers=headers)
    assert admitted.status_code == 202, admitted.text
    return wait_http(client, f"{path}/{admitted.json()['turn_id']}", headers)


def test_uploaded_table_is_published_then_extended_and_compared(tmp_path):
    from fastapi.testclient import TestClient

    provider = scripted(
        table_plan(),
        "Belgeden tablo oluşturuldu.",
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Konut kredisi eklendi.",
        step(
            "c",
            "change_detection",
            operation="table_co_movement",
            source="analiz_2",
            driver_column="Kapanış",
            target_column=TOTAL,
            driver_direction="up",
            target_direction="up",
        ),
        "Karşılaştırma tamamlandı.",
    )
    runner, app = runtime(tmp_path, provider)
    with TestClient(app, base_url=BASE) as client:
        created = client.post("/v1/sessions", json={}).json()
        sid, headers = created["session_id"], {"X-KKB-Session-Token": created["token"]}
        document = client.post(
            f"/v1/sessions/{sid}/documents",
            content=DOCUMENT,
            headers={**headers, "Content-Type": "text/csv"},
        ).json()
        first = ask(
            client,
            sid,
            headers,
            "Ekli belgeden Kapanış, Faiz ve Hacim sütunlarıyla aylık tablo oluştur.",
            document_ref=document["document_ref"],
        )
        assert first["answer"]["status"] == "accepted", first
        result = first["answer"]["result"]
        cells = {(c["label"], c["period"]["end"]): c for c in result["cells"]}
        assert cells[("Kapanış", "2026-04-30")]["measure"] == "index"
        assert cells[("Faiz", "2026-05-31")]["value"] == 4.75
        assert cells[("Faiz", "2026-05-31")]["measure"] == "rate"
        assert cells[("Hacim", "2026-05-31")]["value"] == 13
        assert any(note.startswith("Hacim:") for note in result["proof"]["unresolved_semantics"])
        proof = result["proof"]
        assert proof["availability"] == "available", proof
        assert proof["steps"][0]["producer"] == "web_url"
        assert proof["steps"][0]["inputs"] == [{"kind": "document", "index": 0}]
        (source,) = proof["documents"]
        assert (source["source_type"], source["column"], source["values_read"]) == (
            "upload",
            None,
            9,  # Kapanış, Faiz and the unit-less Hacim, three months each
        )
        assert not any("'Hacim'" in note for note in proof["warnings"])

        second = ask(
            client,
            sid,
            headers,
            "Tabloya toplam konut kredisini ekle.",
            selected_result_id=result["result_ref"],
        )
        assert second["answer"]["status"] == "accepted", second
        third = ask(
            client,
            sid,
            headers,
            "Kapanış ile kredi aynı yönde mi?",
            selected_result_id=second["answer"]["result"]["result_ref"],
        )
    assert third["answer"]["status"] == "accepted", third
    counts = {
        c["label"].split(": ", 1)[1]: c["value"]
        for c in third["answer"]["result"]["cells"]
        if c["label"].startswith("table comparison ")
    }
    assert counts["eligible transitions matching both directions"] == 2.0
    assert [d["source_type"] for d in third["answer"]["result"]["proof"]["documents"]] == ["upload"]
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        assert workspace.names() == ["analiz_1", "analiz_2", "analiz_3"]
        table = workspace.value_of("analiz_1")
        assert not result_faults({"analiz_1": table}, lake.connection)
        changed = [
            v.model_copy(update={"value": 1.0}) if v.label == "Faiz" else v for v in table.values
        ]
        tampered = table.model_copy(update={"values": changed})
        assert result_faults({"analiz_1": tampered}, lake.connection)
        assert build_proof(lake.connection, tampered).availability == "unavailable"


def test_prompt_address_table_keeps_the_address_out_of_lineage(tmp_path):
    fetch = FakeFetch(DOCUMENT)
    provider = scripted(table_plan(url=URL), "Tablo hazır.")
    runner, _ = runtime(tmp_path, provider, fetch=fetch)
    sid = uuid4().hex
    answer = runner(sid, uuid4().hex, f"{URL} adresindeki tablodan aylık tablo oluştur.")
    assert answer.status.value == "accepted" and answer.result is not None, answer
    assert answer.result.proof.documents[0].host == "data.example.test"
    assert not [item for item in PRIVATE if item in answer.model_dump_json()]
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        stored = json.dumps(
            lake.connection.execute("SELECT attributes FROM lineage_nodes").fetchall(),
            default=str,
        )
    assert "SECRET-QUERY" not in stored and len(fetch.requests) == 1


def test_a_table_needs_a_free_question_not_a_selected_table(tmp_path):
    from test_series_inspection import SQL

    provider = scripted(
        step("a", "lakehouse", sql=SQL), "Tablo hazır.", table_plan(url=URL), table_plan(url=URL)
    )
    runner, _ = runtime(tmp_path, provider, fetch=FakeFetch(DOCUMENT))
    sid, tid = uuid4().hex, uuid4().hex
    first = runner(sid, tid, "Konut kredisi tablosunu getir.")
    from kkb_agent.api.service import SelectedResult

    selection = SelectedResult(tid, first.result.result_ref, first.result.version)
    with pytest.raises(Exception, match="declared table input"):
        runner.selected(sid, uuid4().hex, f"{URL} adresinden tablo oluştur.", selection)


def test_a_refused_table_publishes_nothing(tmp_path):
    duplicate = DOCUMENT.replace(b"2026-06;", b"2026-05;")
    provider = scripted(table_plan(url=URL), "Tablo hazır.")
    runner, _ = runtime(tmp_path, provider, fetch=FakeFetch(duplicate))
    sid = uuid4().hex
    answer = runner(sid, uuid4().hex, f"{URL} adresindeki tablodan aylık tablo oluştur.")
    assert answer.status.value == "abstained" and answer.result is None
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == []
