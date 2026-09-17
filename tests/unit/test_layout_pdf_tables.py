"""DEC-148: text-layout PDF tables, year context, digit convention and special rows.

The synthetic page copies the geometry of the organizer's gold trading PDF
(right-aligned numbers under right-aligned headers, filled group header cells,
a bilingual month column, a total row and a not-yet-published month) with
made-up figures. No network and no organizer file.
"""

import io
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pdf_builder import Page, build, right_aligned, ruled_table
from test_document_check import FakeFetch
from test_document_table import runtime

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.agent.verifier import AnswerStatus
from kkb_agent.core import Frequency, Period, SourceRef
from kkb_agent.ingest.fetched import source_id_for
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.pdf_loader import load_pdf
from kkb_agent.tools._document_column import ColumnRefused, read_column
from kkb_agent.tools._document_table import read_table, table_result
from kkb_agent.tools._document_value import (
    Grid,
    HeaderPath,
    ValueNotSelected,
    grids,
    is_total_label,
    number_convention,
    read_cell,
    read_number,
    select_cell,
    year_in_question,
)
from kkb_agent.tools.web_url import make_web_url_tool

PDF = "application/pdf"
URL = "https://data.example.test/PRIVATE-PATH/altin.pdf?token=SECRET-QUERY"
SOURCE = SourceRef(source_id="source:synthetic", source_type="upload", locator="opaque:fixture")
AS_OF = date(2026, 9, 17)
NOW = datetime(2026, 9, 17, 8, 0, tzinfo=UTC)

#: Right edges of the five value columns and the label column's left edge.
EDGES = (200, 280, 400, 480, 590)
LABEL_X = 20
#: (label, TL volume, TL kg, USD volume, USD kg, total kg); None leaves a cell empty.
ROWS = (
    ("Ocak / January", "81.204.117.330", "12.418", "2.914.006.118", "18.203", "30.621"),
    ("Subat / February", "76.330.905.412", "11.207", "3.108.442.907", "19.954", "31.161"),
    ("Mart / March", "142.019.338.004", "20.911", "4.877.312.645", "30.418", "51.329"),
    ("Nisan / April", "55.418.230.771", "8.104", "3.905.117.260", "25.117", "33.221"),
    ("Eylul / September", None, None, None, None, "0"),
    ("TOPLAM / TOTAL", "354.972.591.517", "52.640", "14.804.878.930", "93.692", "146.332"),
)


def gold_page(*, group_cells=True, background=False, rows=ROWS, title="(2026)"):
    page = Page()
    page.texts.append((150, 740, f"PRECIOUS METALS GOLD TRADING DATA {title}"))
    page.rects.append((10, 730, 590, 25))  # a title band, not a header cell
    page.texts += [(LABEL_X, 700, "AY/MONTH"), (160, 700, "TL"), (350, 700, "USD")]
    page.texts.append((500, 700, "TOPLAM / TOTAL"))
    if group_cells:
        page.rects += [(105, 696, 180, 14), (290, 696, 195, 14), (490, 696, 110, 14)]
    if background:
        page.rects.append((105, 668, 495, 44))
    page.texts += [
        right_aligned(200, 685, "Hacim/Volume (TL)"),
        right_aligned(280, 685, "Miktar/Amount"),
        right_aligned(400, 685, "Hacim/Volume (USD)"),
        right_aligned(480, 685, "Miktar/Amount"),
        right_aligned(590, 685, "Miktar/Amount"),
        right_aligned(280, 673, "(KG)"),
        right_aligned(480, 673, "(KG)"),
        right_aligned(590, 673, "(KG)"),
    ]
    for number, (label, *values) in enumerate(rows):
        y = 655 - 16 * number
        page.texts.append((LABEL_X, y, label))
        page.rects.append((490, y - 4, 110, 16))  # shading that pdfplumber reads as a table
        for edge, value in zip(EDGES, values, strict=True):
            if value is not None:
                page.texts.append(right_aligned(edge, y, value))
    return page


def load(page_or_bytes):
    content = page_or_bytes if isinstance(page_or_bytes, bytes) else build([page_or_bytes])
    result = load_pdf(io.BytesIO(content), filename="d.pdf", content_type=PDF, source=SOURCE)
    assert result.status == "loaded", result.code
    return result.document


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


@pytest.fixture(scope="module")
def gold():
    return load(gold_page())


class TestALayoutTableIsReconstructed:
    def test_columns_headers_groups_rows_and_year(self, gold):
        (table,) = gold.tables  # the one-column shading fragment is dropped

        assert table.kind == "layout" and table.years == (2026,)
        assert table.rows[0] == (
            "AY/MONTH",
            "Hacim/Volume (TL)",
            "Miktar/Amount (KG)",
            "Hacim/Volume (USD)",
            "Miktar/Amount (KG)",
            "Miktar/Amount (KG)",
        )
        assert table.groups == (None, "TL", "TL", "USD", "USD", "TOPLAM / TOTAL")
        assert table.rows[1:] == ROWS

    def test_without_drawn_group_cells_groups_bind_to_nothing(self):
        (table,) = load(gold_page(group_cells=False)).tables

        assert table.kind == "layout" and table.groups is None
        with pytest.raises(ValueNotSelected, match="^AMBIGUOUS_VALUE$"):
            select_cell(grids(None, load(gold_page(group_cells=False))), "Miktar", "Ocak 2026")

    def test_a_shaded_area_around_column_headers_is_no_group_cell(self):
        # The shading also forms an unstroked "ruled" grid; it hides nothing.
        (table,) = load(gold_page(group_cells=False, background=True)).tables

        assert table.kind == "layout" and table.groups is None

    def test_a_misaligned_number_leaves_the_block_as_text(self):
        page = gold_page()
        page.texts = [  # one figure 5 points off its column edge
            right_aligned(585, y, text) if text == "31.161" else (x, y, text)
            for x, y, text in page.texts
        ]

        assert not [table for table in load(page).tables if table.kind == "layout"]

    def test_a_text_cell_breaking_a_row_refuses_the_table(self):
        rows = list(ROWS)
        rows[0] = ("Ocak / January", "81.204.117.330", "yok", "2.914.006.118", "18.203", "30.621")

        assert not [table for table in load(gold_page(rows=rows)).tables if table.kind == "layout"]

    def test_a_ruled_table_is_not_read_twice(self):
        page = ruled_table(
            50, 700, [["Tarih", "Tutar (TL)"], ["Ocak 2026", "1.234,5"], ["Subat 2026", "1.300,0"]]
        )

        assert [table.kind for table in load(page).tables] == ["ruled"]

    def test_numbers_inside_sentences_are_no_table(self):
        page = Page(
            texts=[(40, 700, "Faiz 12,5 oldu ve 2026 boyunca"), (40, 684, "Kredi 1.234 artti 55")]
        )

        assert load(page).tables == ()

    def test_several_years_above_the_table_are_all_recorded(self):
        (table,) = load(gold_page(title="(2025-2026)")).tables

        assert table.years == (2025, 2026)


class TestReadingTheGoldTable:
    @pytest.mark.parametrize(
        "column", ["TL Hacim", "Hacim TL", "tl volume", "Hacim (TL)", "TL Hacim/Volume"]
    )
    def test_a_group_and_a_bilingual_name_select_one_column(self, gold, column):
        cell = select_cell(grids(None, gold), column, "Mart 2026")

        assert (cell.raw, str(cell.header), cell.row_label) == (
            "142.019.338.004",
            "TL Hacim/Volume (TL)",
            "Mart / March",
        )
        reading = read_cell(cell, as_of=AS_OF)
        assert (reading.value, reading.unit) == (142019338004.0, "TRY")
        assert reading.period == Period(
            start=date(2026, 3, 1), end=date(2026, 3, 31), frequency=Frequency.MONTHLY
        )

    def test_the_tables_turkish_grouping_reads_an_ambiguous_kilogram_figure(self, gold):
        cell = select_cell(grids(None, gold), "USD Miktar", "Ocak 2026")

        assert cell.convention == "tr" and read_cell(cell, as_of=AS_OF).value == 18203.0

    @pytest.mark.parametrize(
        ("column", "code"), [("Hacim", "AMBIGUOUS_VALUE"), ("EUR Hacim", "VALUE_NOT_FOUND")]
    )
    def test_an_unqualified_or_absent_name_refuses(self, gold, column, code):
        with pytest.raises(ValueNotSelected, match=f"^{code}$"):
            select_cell(grids(None, gold), column, "Ocak 2026")

    def test_a_different_requested_year_conflicts_with_the_documents(self, gold):
        with pytest.raises(ValueNotSelected, match="^YEAR_CONFLICT$"):
            select_cell(grids(None, gold), "TL Hacim", "Ocak", year=2025)

    def test_a_month_after_retrieval_is_no_observation(self, gold):
        cell = select_cell(grids(None, gold), "Toplam Miktar", "Eylul 2026")

        assert read_cell(cell).value == 0.0  # without a retrieval date nothing is decided
        with pytest.raises(ValueNotSelected, match="^FUTURE_PERIOD$"):
            read_cell(cell, as_of=AS_OF)

    def test_several_stated_years_give_month_names_no_year(self):
        gridded = grids(None, load(gold_page(title="(2025-2026)")))

        with pytest.raises(ValueNotSelected, match="^VALUE_NOT_FOUND$"):
            select_cell(gridded, "TL Hacim", "Ocak 2026", year=2026)

    def test_the_monthly_table_skips_the_total_and_the_future_month(self, gold):
        table = read_table(
            grids(None, gold), "Ay", ["TL Hacim", "USD Hacim", "Toplam Miktar"], as_of=AS_OF
        )

        assert table.months == (
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
        )
        expected = {
            label: [Decimal(row[index].replace(".", "")) for row in ROWS[:4]]
            for label, index in (("TL Hacim", 1), ("USD Hacim", 3), ("Toplam Miktar", 5))
        }
        assert {
            c.label: [Decimal(str(v)) for _, v, _ in c.cells] for c in table.columns
        } == expected
        assert [(c.label, c.unit) for c in table.columns] == [
            ("TL Hacim", "TRY"),
            ("USD Hacim", "USD"),
            ("Toplam Miktar", "kg"),
        ]
        result = table_result(table, SOURCE, source_node=None)
        (transformation,) = result.evidence.transformations
        assert {
            key: transformation.parameters[key]
            for key in ("year", "number_convention", "skipped_rows")
        } == {
            "year": {"value": 2026, "source": "document"},
            "number_convention": "tr",
            "skipped_rows": {"FUTURE_PERIOD": 1, "TOTAL_ROW": 1},
        }
        assert any("(TOTAL_ROW)" in w for w in result.warnings)
        assert any("(FUTURE_PERIOD)" in w for w in result.warnings)
        assert any("page text above the table" in note for note in result.limitations)
        assert any("Turkish convention" in note for note in result.limitations)

    def test_an_added_column_uses_the_same_rules(self, gold):
        column = read_column(grids(None, gold), "Ay", "TL Miktar", as_of=AS_OF)

        assert [value for _, value, _ in column.rows] == [12418.0, 11207.0, 20911.0, 8104.0]
        assert column.rules.evidence()["skipped_rows"] == {"FUTURE_PERIOD": 1, "TOTAL_ROW": 1}


class TestYearContext:
    CSV_GRID = Grid({"table": 1}, ("Ay", "Tutar (TL)"), (("Ocak", "1.234,5"), ("Subat", "1.300,0")))

    def test_a_question_year_dates_month_names_when_the_document_states_none(self):
        cell = select_cell([self.CSV_GRID], "Tutar", "Ocak", year=2026)

        assert cell.year.source == "question"
        assert read_cell(cell).period.end == date(2026, 1, 31)

    def test_without_any_year_a_month_name_is_no_period(self):
        with pytest.raises(ColumnRefused, match="^PERIOD_NOT_RECOGNISED$"):
            read_table([self.CSV_GRID], "Ay", ["Tutar"])

    @pytest.mark.parametrize(
        ("question", "found"),
        [
            ("2026 yılında ocak tutarı?", True),
            ("Ocak 2026'daki tutar", True),
            ("2025-2026 arası", True),
            ("12.2026 tarihli", False),
            ("20261 kodlu", False),
            ("Ocak tutarı nedir?", False),
        ],
    )
    def test_a_year_must_be_written_as_its_own_number(self, question, found):
        assert year_in_question(2026, question) is found

    def test_a_month_name_pair_must_name_one_month(self):
        grid = Grid({"table": 1}, ("Ay", "Tutar (TL)"), (("Ocak / February", "1"), ("Subat", "2")))

        with pytest.raises(ColumnRefused, match="^PERIOD_NOT_RECOGNISED$"):
            read_table([grid], "Ay", ["Tutar"], year=2026)


class TestDigitConvention:
    @pytest.mark.parametrize(
        ("cells", "convention"),
        [
            (["93.824.682.381", "13.837"], "tr"),
            (["46,75", "1.234"], "tr"),
            (["1,234.5", "1,234"], "en"),
            (["4.5", "1.234"], "en"),
            (["1.234", "1017", "0"], None),
            (["46,75", "4.5"], None),
            (["12.2025", "01.06.2026", "2026-01", "1.234"], None),
            ([12.5, None, "1.234"], None),
        ],
    )
    def test_only_one_sided_evidence_settles_a_table(self, cells, convention):
        assert number_convention([cells]) == convention

    @pytest.mark.parametrize(
        ("raw", "convention", "value"),
        [
            ("1.234", "tr", 1234.0),
            ("1.234", "en", 1.234),
            ("1,234", "tr", 1.234),
            ("1,234", "en", 1234.0),
        ],
    )
    def test_a_convention_decides_only_an_ambiguous_figure(self, raw, convention, value):
        assert read_number(raw, convention) == value

    @pytest.mark.parametrize("raw", ["4.5", "1.234,56", "1.234.567", "0.125", "46,75"])
    def test_a_convention_never_changes_an_unambiguous_figure(self, raw):
        assert read_number(raw, "tr") == read_number(raw) == read_number(raw, "en")

    def test_a_contradicted_table_still_refuses(self):
        grid = Grid(
            {"table": 1},
            ("Ay", "A (TL)", "B (TL)"),
            (("2026-01", "1.234", "4.5"), ("2026-02", "46,75", "1")),
        )

        with pytest.raises(ValueNotSelected, match="^AMBIGUOUS_NUMBER$"):
            read_cell(select_cell([grid], "A", "2026-01"))


@pytest.mark.parametrize(
    ("label", "total"),
    [
        ("TOPLAM / TOTAL", True),
        ("Genel Toplam", True),
        ("total", True),
        ("Toplam Kredi", False),
        ("Ara Toplam", False),
        (None, False),
    ],
)
def test_only_closed_total_labels_are_skipped(label, total):
    assert is_total_label(label) is total


def test_a_composite_header_prints_as_group_and_leaf():
    assert str(HeaderPath("USD", "Hacim/Volume (USD)")) == "USD Hacim/Volume (USD)"


def _table_plan(**extra):
    arguments = {
        "url": URL,
        "period_column": "Ay",
        "value_columns": ["TL Hacim", "USD Hacim", "Toplam Miktar"],
        **extra,
    }
    return json.dumps(
        {"question": "q", "steps": [{"step_id": "t", "tool": "web_url", "arguments": arguments}]}
    )


def test_a_served_prompt_address_layout_pdf_becomes_a_monthly_table(tmp_path):
    fetch = FakeFetch(build([gold_page(rows=ROWS[:4] + ROWS[5:])]), PDF)
    runner, _ = runtime(tmp_path, scripted(_table_plan(), "Tablo hazır."), fetch=fetch)
    sid = uuid4().hex

    answer = runner(sid, uuid4().hex, f"{URL} dosyasındaki altın verisiyle aylık tablo oluştur.")

    assert answer.status.value == "accepted" and answer.result is not None, answer
    cells = {(c.label, c.period.end): Decimal(str(c.value)) for c in answer.result.cells}
    assert len(cells) == 12
    for number, row in enumerate(ROWS[:4]):
        end = [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)][number]
        assert cells[("TL Hacim", end)] == Decimal(row[1].replace(".", ""))
        assert cells[("Toplam Miktar", end)] == Decimal(row[5].replace(".", ""))
    (document,) = answer.result.proof.documents
    assert (document.document_format, document.page, document.table) == ("pdf", 1, 1)
    assert answer.result.proof.availability == "available"
    assert "PRIVATE-PATH" not in answer.model_dump_json() and len(fetch.requests) == 1
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        table = Workspace.open(lake.connection, sid).value_of("analiz_1")
    assert table.evidence.transformations[0].parameters["year"] == {
        "value": 2026,
        "source": "document",
    }


def _cell_plan(**arguments):
    return json.dumps(
        {"question": "q", "steps": [{"step_id": "s", "tool": "web_url", "arguments": arguments}]}
    )


def test_a_layout_pdf_cell_answers_with_its_month(tmp_path):
    question = f"{URL} dosyasında Nisan 2026 TL işlem hacmi nedir?"
    with open_lakehouse(tmp_path / "lake") as lake:
        registry = ToolRegistry()
        fetch = FakeFetch(build([gold_page()]), PDF)
        registry.register(make_web_url_tool(fetch=fetch, lineage=lake.lineage, clock=lambda: NOW))
        plan = _cell_plan(url=URL, column="TL Hacim", row="Nisan 2026")
        draft = "Nisan 2026'da TL işlem hacmi 55.418.230.771 TL oldu."
        answered = Session(scripted(plan, draft), registry).answer(question, lake.connection)

    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    (result,) = answered.results
    assert result.parameters["period_source"] == "row label with the document year"
    assert result.values[0].period.end == date(2026, 4, 30)


def test_a_year_the_user_did_not_write_is_refused_before_any_fetch(tmp_path):
    fetch = FakeFetch(build([gold_page()]), PDF)
    with open_lakehouse(tmp_path / "lake") as lake:
        registry = ToolRegistry()
        registry.register(make_web_url_tool(fetch=fetch, lineage=lake.lineage, clock=lambda: NOW))
        plan = _cell_plan(url=URL, column="TL Hacim", row="Nisan", year=2026)
        answered = Session(scripted(plan, "x"), registry).answer(
            f"{URL} dosyasında nisan TL hacmi nedir?", lake.connection
        )

    assert answered.answer.status is AnswerStatus.ABSTAINED
    assert fetch.requests == []


def test_add_document_column_refuses_a_year_the_user_did_not_write(tmp_path):
    from test_document_column import first_table, served
    from test_document_table import step

    fetch = FakeFetch(build([gold_page()]), PDF)
    add = step(
        "d",
        "table_transform",
        operation="add_document_column",
        source="analiz_1",
        url=URL,
        period_column="Ay",
        value_column="TL Hacim",
        year=2026,
    )
    from test_document_column import table_turn

    runner = served(tmp_path, scripted(*table_turn(), add, "Eklendi."), fetch)
    sid, _, selection = first_table(runner)

    second = runner.selected(sid, uuid4().hex, f"{URL} dosyasındaki TL hacmini ekle.", selection)

    assert second.status.value != "accepted"
    # Only the page outline read the written address; the refused step fetched nothing more.
    assert [request.source_ref for request in fetch.requests] in ([], [source_id_for(URL)])
