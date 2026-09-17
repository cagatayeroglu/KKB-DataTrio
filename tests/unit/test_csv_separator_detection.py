"""DEC-147 (a): an undeclared CSV separator on the document path; no network."""

import calendar
import io
import json
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from test_document_check import FakeFetch
from test_document_table import ask, runtime, step

from kkb_agent import csv_loader as loader
from kkb_agent.agent import Workspace
from kkb_agent.core import SourceRef
from kkb_agent.ingest.fetched import load_document
from kkb_agent.ingestion_policy import DEFAULT_LIMITS
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted

SOURCE = SourceRef(source_id="source:synthetic", source_type="upload", locator="opaque:fixture")
URL = "https://data.example.test/PRIVATE-PATH/kredi.csv?token=SECRET-QUERY"
AMBIGUOUS = b"a,b;c\n1,2;3\n"


def _months():
    return [f"{year}-{month:02d}" for year in range(2021, 2026) for month in range(1, 13)]


def _credit(index):
    whole = 1_200_000 + index * 7_919
    return f"{whole:,}".replace(",", ".") + f",{index % 10}"


def _rate(index):
    return f"{8 + index % 30},{index * 7 % 100:02d}"


#: The measured U1 shape: Turkish decimal commas, `;` separator, no declaration.
U1 = (
    "Ay;Konut Kredisi (Milyon TL);Faiz (%)\n"
    + "".join(f"{m};{_credit(i)};{_rate(i)}\n" for i, m in enumerate(_months()))
).encode()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def detect(content, *, delimiter=None, limits=DEFAULT_LIMITS):
    return loader.load_csv(
        io.BytesIO(content),
        filename="document.csv",
        content_type="text/csv",
        source=SOURCE,
        delimiter=delimiter,
        detect_delimiter=True,
        limits=limits,
    )


class TestOneSeparatorIsChosen:
    def test_the_measured_semicolon_shape_is_detected_and_read_exactly(self):
        result = detect(U1)

        assert result.status == "loaded", result.code
        table = result.table
        assert (table.delimiter, table.delimiter_source) == (";", "detected")
        assert table.headers == ("Ay", "Konut Kredisi (Milyon TL)", "Faiz (%)")
        assert table.rows[0] == ("2021-01", _credit(0), _rate(0))
        assert len(table.rows) == 60

    @pytest.mark.parametrize(
        ("content", "delimiter"),
        [
            (b'label,value\n"a;b",1\n"c|d",2\n', ","),
            (b"label\tvalue\n1,5;x\t2\n3\t4\n", "\t"),
            (b"label|value\na,b|1\nc;d|2\n", "|"),
            (b"\xef\xbb\xbfAy;Tutar (TL)\n2026-01;1\n", ";"),
            (b'Ay;Not\n2026-01;"iki\nsatir"\n2026-02;x\n', ";"),
        ],
    )
    def test_quotes_bom_and_other_separators(self, content, delimiter):
        result = detect(content)

        assert result.status == "loaded", result.code
        assert (result.table.delimiter, result.table.delimiter_source) == (delimiter, "detected")

    @pytest.mark.parametrize(
        "content",
        [
            AMBIGUOUS,  # comma and semicolon both give two even columns
            b"value\n1\n2\n",  # one column under every separator
            b"a,b\n1\n",  # uneven under every separator
            b"a;b\n",  # no data record
            b'a;b\n"open;1\n',  # an unclosed quote everywhere
        ],
    )
    def test_no_or_several_candidates_still_need_a_declaration(self, content):
        result = detect(content)

        assert (result.status, result.code, result.table) == (
            "needs_input",
            "PARSING_DECLARATION_REQUIRED",
            None,
        )

    def test_the_strict_loader_default_never_detects(self):
        result = loader.load_csv(
            io.BytesIO(U1), filename="d.csv", content_type="text/csv", source=SOURCE
        )

        assert (result.status, result.code) == ("needs_input", "PARSING_DECLARATION_REQUIRED")

    def test_the_document_path_detects(self):
        result = load_document(U1, "text/csv", source=SOURCE)

        assert result.status == "loaded" and result.table.delimiter_source == "detected"


class TestADeclarationMeetsDetection:
    def test_an_agreeing_declaration_stays_declared(self):
        result = detect(U1, delimiter=";")

        assert (result.table.delimiter, result.table.delimiter_source) == (";", "declared")

    @pytest.mark.parametrize("declared", [",", "\t", "|"])
    def test_a_contradicting_declaration_is_refused(self, declared):
        result = detect(U1, delimiter=declared)

        assert (result.status, result.code, result.table) == (
            "needs_input",
            "DELIMITER_CONFLICT",
            None,
        )

    @pytest.mark.parametrize(("declared", "rows"), [(",", (("1", "2;3"),)), (";", (("1,2", "3"),))])
    def test_an_undecidable_file_keeps_the_declared_reading(self, declared, rows):
        result = detect(AMBIGUOUS, delimiter=declared)

        assert result.status == "loaded" and result.table.rows == rows
        assert result.table.delimiter_source == "declared"

    def test_an_unsupported_declaration_is_still_refused_first(self):
        assert detect(U1, delimiter="::").code == "UNSUPPORTED_DELIMITER"


class TestOnlyLeadingRecordsAreRead:
    def test_a_large_file_is_detected_from_its_prefix_and_parsed_whole(self):
        rows = "".join(f'{i};{i % 97},5;"not; a, separator"\n' for i in range(9_000))
        content = ("Sira;Deger (TL);Not\n" + rows).encode()
        assert len(content) > 3 * loader.DETECTION_PREFIX_CHARS

        result = detect(content)

        assert result.status == "loaded", result.code
        assert result.table.delimiter_source == "detected" and len(result.table.rows) == 9_000

    def test_a_quoted_field_across_the_cut_is_not_a_structure_error(self):
        head = "Ay;Not\n" + "2026-01;x\n" * 6_550
        cut = loader.DETECTION_PREFIX_CHARS - len(head)
        assert 0 < cut < 100
        content = (head + '2026-02;"' + "y\n" * 200 + '"\n2026-03;z\n').encode()

        result = detect(content)

        assert result.status == "loaded", result.code
        assert result.table.delimiter == ";" and result.table.rows[-1] == ("2026-03", "z")

    def test_a_later_break_refuses_rather_than_trying_another_separator(self):
        consistent = "2026-01;1,5;2,5\n" * 5_000
        content = (f"Ay;A (TL);B (%)\n{consistent}2026-02;1,5\n").encode()  # two fields
        assert content.index(b"2026-02") > loader.DETECTION_PREFIX_CHARS

        result = detect(content)

        assert (result.status, result.code) == ("rejected", "MALFORMED_TABLE")

    def test_too_few_complete_records_in_the_prefix_decide_nothing(self):
        huge = "z" * (loader.DETECTION_PREFIX_CHARS + 10)
        content = f'Ay;Not\n2026-01;"{huge}"\n2026-02;x\n'.encode()
        roomy = replace(DEFAULT_LIMITS, max_field_chars=loader.DETECTION_PREFIX_CHARS * 2)

        undecided = detect(content, limits=roomy)
        declared = detect(content, delimiter=";", limits=roomy)

        assert (undecided.status, undecided.code) == ("needs_input", "PARSING_DECLARATION_REQUIRED")
        assert declared.status == "loaded" and len(declared.table.rows) == 2

    def test_detection_runs_inside_the_bounded_worker(self, monkeypatch):
        def forbidden(*args, **kwargs):
            raise AssertionError("detection must not parse in the caller's process")

        monkeypatch.setattr(loader, "_detect", forbidden)

        assert detect(U1).status == "loaded"  # the spawned worker has its own module


def _table_plan(**extra):
    arguments = {
        "period_column": "Ay",
        "value_columns": ["Konut Kredisi", "Faiz"],
        **extra,
    }
    return json.dumps(
        {"question": "q", "steps": [{"step_id": "t", "tool": "web_url", "arguments": arguments}]}
    )


def _oracle(text):
    """Independent reading of the U1 bytes: split lines, Decimal arithmetic."""
    lines = text.decode().splitlines()
    expected = {}
    for line in lines[1:]:
        month, credit, rate = line.split(";")
        end = calendar.monthrange(int(month[:4]), int(month[5:]))[1]
        expected[("Konut Kredisi", f"{month}-{end}")] = Decimal(
            credit.replace(".", "").replace(",", ".")
        )
        expected[("Faiz", f"{month}-{end}")] = Decimal(rate.replace(",", "."))
    return expected


def test_an_uploaded_undeclared_semicolon_table_matches_an_independent_reading(tmp_path):
    from fastapi.testclient import TestClient

    runner, app = runtime(tmp_path, scripted(_table_plan(attached=True), "Tablo hazır."))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        created = client.post("/v1/sessions", json={}).json()
        sid, headers = created["session_id"], {"X-KKB-Session-Token": created["token"]}
        document = client.post(
            f"/v1/sessions/{sid}/documents",
            content=U1,
            headers={**headers, "Content-Type": "text/csv"},
        ).json()
        turn = ask(
            client,
            sid,
            headers,
            "Ekli dosyadan Konut Kredisi ve Faiz sütunlarıyla aylık tablo oluştur.",
            document_ref=document["document_ref"],
        )
    assert turn["answer"]["status"] == "accepted", turn
    cells = {(c["label"], c["period"]["end"]): c for c in turn["answer"]["result"]["cells"]}
    expected = _oracle(U1)
    assert len(cells) == len(expected) == 120
    mismatches = [
        key for key, value in expected.items() if Decimal(str(cells[key]["value"])) != value
    ]
    assert mismatches == []
    assert turn["answer"]["result"]["proof"]["availability"] == "available"
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        table = Workspace.open(lake.connection, sid).value_of("analiz_1")
        (transformation,) = table.evidence.transformations
        assert transformation.parameters["csv"] == {
            "delimiter": ";",
            "delimiter_source": "detected",
        }
        stored = [
            json.loads(attributes)
            for (attributes,) in lake.connection.execute(
                "SELECT attributes FROM lineage_nodes WHERE attributes LIKE '%document_table_v1%'"
            ).fetchall()
        ]
        snapshots = [json.loads(node["snapshot"]) for node in stored if "snapshot" in node]
    assert [s["csv"] for s in snapshots] == [{"delimiter": ";", "delimiter_source": "detected"}]


def test_a_contradicting_declaration_publishes_nothing(tmp_path):
    fetch = FakeFetch(U1)
    runner, _ = runtime(
        tmp_path, scripted(_table_plan(url=URL, delimiter=","), "Tablo hazır."), fetch=fetch
    )
    sid = uuid4().hex

    answer = runner(sid, uuid4().hex, f"{URL} adresindeki tablodan aylık tablo oluştur.")

    assert answer.status.value == "abstained" and answer.result is None
    assert "PRIVATE-PATH" not in answer.model_dump_json()
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == []
        assert not lake.connection.execute(
            "SELECT 1 FROM lineage_nodes WHERE attributes LIKE '%document_table_v1%'"
        ).fetchall()


def test_a_workbook_records_no_separator(tmp_path):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["Ay", "Faiz (%)"])
    sheet.append(["2026-01", "4,5"])
    sheet.append(["2026-02", "4,25"])
    buffer = io.BytesIO()
    book.save(buffer)
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    plan = json.dumps(
        {
            "question": "q",
            "steps": [
                {
                    "step_id": "t",
                    "tool": "web_url",
                    "arguments": {"url": URL, "period_column": "Ay", "value_columns": ["Faiz"]},
                }
            ],
        }
    )
    runner, _ = runtime(
        tmp_path, scripted(plan, "Tablo hazır."), fetch=FakeFetch(buffer.getvalue(), xlsx)
    )
    sid = uuid4().hex
    answer = runner(sid, uuid4().hex, f"{URL} adresindeki tablodan aylık tablo oluştur.")
    assert answer.status.value == "accepted", answer
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        table = Workspace.open(lake.connection, sid).value_of("analiz_1")
    assert "csv" not in table.evidence.transformations[0].parameters


def test_an_added_document_column_records_the_detected_separator(tmp_path):
    from test_series_inspection import SQL

    add = step(
        "d",
        "table_transform",
        operation="add_document_column",
        source="analiz_1",
        url=URL,
        period_column="Ay",
        value_column="Faiz",
    )
    runner, _ = runtime(
        tmp_path,
        scripted(step("a", "lakehouse", sql=SQL), "Tablo hazır.", add, "Faiz eklendi."),
        fetch=FakeFetch(b"Ay;Faiz (%)\n2026-04;4,5\n2026-05;4,25\n2026-06;4\n"),
    )
    sid, tid = uuid4().hex, uuid4().hex
    first = runner(sid, tid, "Konut kredisi tablosunu getir.")
    assert first.status.value == "accepted", first
    from kkb_agent.api.service import SelectedResult

    selection = SelectedResult(tid, first.result.result_ref, first.result.version)
    second = runner.selected(
        sid, uuid4().hex, f"{URL} adresindeki Faiz sütununu tabloya ekle.", selection
    )
    assert second.status.value == "accepted", second
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        added = Workspace.open(lake.connection, sid).value_of("analiz_2")
    assert [v.value for v in added.values if v.label == "Faiz"] == [4.5, 4.25, 4.0]
    assert added.evidence.transformations[-1].parameters["csv"] == {
        "delimiter": ";",
        "delimiter_source": "detected",
    }
