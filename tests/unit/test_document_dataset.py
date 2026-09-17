"""Generic document datasets: any monthly CSV joins prepared data; no network, no model.

The fixture is deliberately not financial (monthly hospital admissions) and its
headers state no unit, the common case for an uploaded spreadsheet.
"""

from datetime import date

import pytest
from test_catalog_continuation import CATALOG, NOW, TOTAL
from test_document_table import ask, step

from kkb_agent.api.app import create_app
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.service import AnalysisService
from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, SourceRef, StockFlow
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse

BASE = "http://127.0.0.1:8000"
MONTHS = [date(2025, m, 1) for m in range(7, 13)] + [date(2026, m, 1) for m in range(1, 7)]
ADMISSIONS = [410, 432, 398, 455, 470, 440, 520, 505, 480, 495, 530, 512]
CREDIT = [100.0, 104.0, 103.0, 108.0, 111.0, 109.0, 115.0, 118.0, 116.0, 121.0, 125.0, 124.0]


def month_end(start):
    following = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


def csv(values=ADMISSIONS, header="Başvuru Sayısı"):
    lines = [f"Ay;{header}"]
    lines += [f"{start:%Y-%m};{value}" for start, value in zip(MONTHS, values, strict=True)]
    return ("\n".join(lines) + "\n").encode()


def seed(root):
    with open_lakehouse(root) as lake:
        artifact = lake.record_artifact(
            b"synthetic twelve-month totals",
            source=SourceRef(source_id="synthetic", source_type="fixture", locator="opaque:x"),
            media_type="text/plain",
            recorded_at=NOW,
        )
        lake.register_series(
            TOTAL,
            title="Synthetic housing total",
            semantics=SeriesSemantics(
                unit="TRY",
                scale=Scale.MILLION,
                frequency=Frequency.MONTHLY,
                observation=StockFlow.STOCK,
                cumulative=CumulativeKind.NONE,
                aggregation=Aggregation.LAST,
            ),
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations(
            TOTAL,
            [
                Observation(start, month_end(start), value)
                for start, value in zip(MONTHS, CREDIT, strict=True)
            ],
        )


@pytest.fixture
def served(tmp_path):
    from fastapi.testclient import TestClient

    def start(*responses):
        from kkb_agent.llm import scripted

        root = tmp_path.resolve() / "prepared"
        seed(root)
        runner = PreparedRunner(
            scripted(*responses),
            root,
            tmp_path.resolve() / "runtime",
            catalog_bytes=CATALOG.read_bytes(),
            document_uploads=True,
        )
        service = AnalysisService(
            runner,
            mode="scripted",
            selected_runner=runner.selected,
            document_store=runner.admit_document,
        )
        client = TestClient(create_app(service, prepared=runner.status), base_url=BASE)
        created = client.__enter__().post("/v1/sessions", json={}).json()
        headers = {"X-KKB-Session-Token": created["token"]}
        return runner, client, created["session_id"], headers

    clients = []

    def tracked(*responses):
        started = start(*responses)
        clients.append(started[1])
        return started

    yield tracked
    for client in clients:
        client.__exit__(None, None, None)


def upload(client, sid, headers, content):
    response = client.post(
        f"/v1/sessions/{sid}/documents",
        content=content,
        headers={**headers, "Content-Type": "text/csv"},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_ref"]


def table_step(**extra):
    return step(
        "t",
        "web_url",
        attached=True,
        period_column="Ay",
        value_columns=["Başvuru Sayısı"],
        **extra,
    )


def test_a_unitless_non_financial_upload_joins_prepared_data_and_is_compared(served):
    comparison = step(
        "c",
        "change_detection",
        operation="table_co_movement",
        source="analiz_2",
        driver_column="Başvuru Sayısı",
        target_column=TOTAL,
        driver_direction="up",
        target_direction="up",
    )
    runner, client, sid, headers = served(
        table_step(),
        "Başvuru tablosu oluşturuldu.",
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Konut kredisi eklendi.",
        comparison,
        "Aylık yönler karşılaştırıldı.",
    )
    document = upload(client, sid, headers, csv())
    first = ask(
        client,
        sid,
        headers,
        "Yüklediğim dosyadaki aylık başvuru sayılarını tablo yap.",
        document_ref=document,
    )
    assert first["answer"]["status"] == "accepted", first
    table = first["answer"]["result"]
    assert len([c for c in table["cells"] if c["label"] == "Başvuru Sayısı"]) == 12
    assert any(n.startswith("Başvuru Sayısı:") for n in table["proof"]["unresolved_semantics"])

    second = ask(
        client,
        sid,
        headers,
        "Tabloya toplam konut kredisini ekle.",
        selected_result_id=table["result_ref"],
    )
    assert second["answer"]["status"] == "accepted", second
    third = ask(
        client,
        sid,
        headers,
        "Başvurular ile kredi aynı yönde mi hareket etmiş?",
        selected_result_id=second["answer"]["result"]["result_ref"],
    )
    assert third["answer"]["status"] == "accepted", third
    result = third["answer"]["result"]
    counts = {
        c["label"].split(": ", 1)[1]: c["value"]
        for c in result["cells"]
        if c["label"].startswith("table comparison ")
    }
    # Hand count over 11 transitions: admissions rise in 6, credit in 7, both in 5.
    rises_a = sum(b > a for a, b in zip(ADMISSIONS, ADMISSIONS[1:], strict=False))
    rises_c = sum(b > a for a, b in zip(CREDIT, CREDIT[1:], strict=False))
    both = sum(
        b > a and d > c
        for a, b, c, d in zip(ADMISSIONS, ADMISSIONS[1:], CREDIT, CREDIT[1:], strict=False)
    )
    assert counts["complete monthly transitions"] == 11
    assert counts["eligible transitions matching the driver direction"] == rises_a
    assert counts["eligible transitions matching the target direction"] == rises_c
    assert counts["eligible transitions matching both directions"] == both
    limitations = " ".join(result["proof"]["limitations"])
    assert "inferred from the values" in limitations
    assert "no stated unit or scale" in limitations


def test_a_column_that_could_be_cumulative_is_not_compared_by_guess(served):
    rising = [sum(ADMISSIONS[: i + 1]) for i in range(len(ADMISSIONS))]
    comparison = step(
        "c",
        "change_detection",
        operation="table_co_movement",
        source="analiz_2",
        driver_column="Başvuru Sayısı",
        target_column=TOTAL,
        driver_direction="up",
        target_direction="up",
    )
    _, client, sid, headers = served(
        table_step(),
        "Tablo hazır.",
        step("a", "table_transform", operation="add_series", source="analiz_1", series_id=TOTAL),
        "Eklendi.",
        comparison,
        "Karşılaştırıldı.",
    )
    document = upload(client, sid, headers, csv(rising))
    first = ask(client, sid, headers, "Belgeden tablo yap.", document_ref=document)
    second = ask(
        client,
        sid,
        headers,
        "Konut kredisini ekle.",
        selected_result_id=first["answer"]["result"]["result_ref"],
    )
    third = ask(
        client,
        sid,
        headers,
        "Aynı yönde mi?",
        selected_result_id=second["answer"]["result"]["result_ref"],
    )
    assert third["answer"]["status"] == "abstained", third
    assert third["answer"]["result"] is None


def test_a_unit_written_in_the_question_is_recorded_as_the_users(served):
    _, client, sid, headers = served(
        table_step(column_units={"Başvuru Sayısı": "bin TL"}), "Tablo hazır."
    )
    document = upload(client, sid, headers, csv())
    first = ask(
        client,
        sid,
        headers,
        "Belgedeki Başvuru Sayısı sütunu bin TL cinsinden; aylık tablo yap.",
        document_ref=document,
    )
    assert first["answer"]["status"] == "accepted", first
    cell = next(c for c in first["answer"]["result"]["cells"] if c["label"] == "Başvuru Sayısı")
    assert (cell["unit"], cell["scale"]) == ("TRY", "thousand")
    assert any("as the user stated" in n for n in first["answer"]["result"]["proof"]["limitations"])


def test_an_earlier_upload_is_read_again_in_a_later_turn_without_reattaching(served):
    runner, client, sid, headers = served(
        step("a", "lakehouse", sql="SELECT 1 AS x"),
        "İlk tur.",
        table_step(document="belge_1"),
        "Tablo hazır.",
    )
    document = upload(client, sid, headers, csv())
    ask(client, sid, headers, "Önce başka bir şey soralım.")
    later = ask(client, sid, headers, "Az önce yüklediğim dosyadan aylık tablo yap.")
    assert later["answer"]["status"] == "accepted", later
    assert document  # admitted once, never re-sent with the second question
    outline = [
        message.content
        for conversation in runner._provider.seen
        for message in conversation
        if message.content.startswith("Documents uploaded in this conversation")
    ]
    assert outline and all(
        item.role.value == "user"
        for item in [
            message
            for conversation in runner._provider.seen
            for message in conversation
            if message.content.startswith("Documents uploaded in this conversation")
        ]
    )
    outline = outline[-1:]
    assert len(outline) == 1 and "Başvuru Sayısı" in outline[0]
    # Headers only: no cell value of the document reaches the planner.
    assert not any(str(value) in outline[0] for value in ADMISSIONS)


def test_several_documents_and_no_name_is_not_a_guess(served):
    _, client, sid, headers = served(table_step(), "Tablo hazır.")
    upload(client, sid, headers, csv())
    upload(client, sid, headers, csv(header="Hasta"))
    answer = ask(client, sid, headers, "Yüklediğim dosyadan tablo yap.")
    assert answer["answer"]["status"] == "abstained", answer


def test_two_uploaded_tables_join_on_the_selected_tables_months(served):
    beds = [70, 72, 69, 75, 80, 78, 85, 83, 81, 84, 88, 86]
    runner, client, sid, headers = served(
        table_step(document="belge_1"),
        "Başvuru tablosu hazır.",
        step(
            "u",
            "web_url",
            attached=True,
            document="belge_2",
            period_column="Ay",
            value_columns=["Yatış"],
        ),
        "Yatış tablosu hazır.",
        step("j", "table_transform", operation="join_table", source="analiz_2", other="analiz_1"),
        "Tablolar birleştirildi.",
    )
    upload(client, sid, headers, csv())
    upload(client, sid, headers, csv(beds[:10] + [88, 86], header="Yatış"))
    first = ask(client, sid, headers, "İlk belgeden tablo yap.")
    second = ask(client, sid, headers, "İkinci belgeden tablo yap.")
    assert first["answer"]["status"] == second["answer"]["status"] == "accepted"
    joined = ask(
        client,
        sid,
        headers,
        "Başvuru tablosunu bu tabloyla birleştir.",
        selected_result_id=second["answer"]["result"]["result_ref"],
    )
    assert joined["answer"]["status"] == "accepted", joined
    cells = joined["answer"]["result"]["cells"]
    labels = {c["label"] for c in cells}
    assert {"Yatış", "Başvuru Sayısı"} <= labels
    assert len([c for c in cells if c["label"] == "Başvuru Sayısı"]) == 12
    # The selected table's own cells are untouched by the join.
    before = {
        (c["label"], c["period"]["end"], c["value"]) for c in second["answer"]["result"]["cells"]
    }
    after = {(c["label"], c["period"]["end"], c["value"]) for c in cells}
    assert before <= after


def test_a_join_never_shadows_an_existing_column(served):
    _, client, sid, headers = served(
        table_step(document="belge_1"),
        "Bir.",
        table_step(document="belge_2"),
        "İki.",
        step("j", "table_transform", operation="join_table", source="analiz_2", other="analiz_1"),
        "Birleşti.",
    )
    upload(client, sid, headers, csv())
    upload(client, sid, headers, csv())
    ask(client, sid, headers, "Bir.")
    second = ask(client, sid, headers, "İki.")
    joined = ask(
        client,
        sid,
        headers,
        "Birleştir.",
        selected_result_id=second["answer"]["result"]["result_ref"],
    )
    assert joined["answer"]["status"] == "abstained", joined
