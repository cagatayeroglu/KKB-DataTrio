"""`table_transform document_row`: months across a table's header, read as a monthly column.

A yearly report sets its months across the header and a row per year, and the tools read
months only down a period column, so a model holding such a table could quote its cells
and compute nothing from them (A3, 2026-09-23). Every table here is made up, in three
different subjects, in both layouts a document gives: one cell per column, and a PDF row
the extractor left in one cell.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import Workspace
from kkb_agent.agent.executor import ExecutionContext, ToolStatus
from kkb_agent.agent.verifier import result_faults
from kkb_agent.core import ResultStatus, Scale, SourceRef, StockFlow
from kkb_agent.html_loader import HtmlDocument, HtmlTable
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.tools.table_transform import make_table_transform_tool
from kkb_agent.tools.web_url import WebUrlOutput


def document(
    *tables: tuple[tuple[str, ...], ...], text: str = "", retrieved: date = date(2025, 12, 31)
) -> WebUrlOutput:
    source = SourceRef(
        source_id="web:synthetic",
        source_type="web_url",
        locator="https://example.invalid/report.html",
        retrieved_at=datetime(retrieved.year, retrieved.month, retrieved.day, tzinfo=UTC),
        content_hash="a" * 64,
    )
    return WebUrlOutput(
        "loaded",
        None,
        source,
        "text/html",
        document=HtmlDocument(
            source=source,
            text=text,
            tables=tuple(HtmlTable(number, rows) for number, rows in enumerate(tables, 1)),
        ),
    )


SALES = (
    ("Yıl", "Ocak", "Şubat", "Mart", "Nisan", "Toplam"),
    ("2024", "1.050", "1.100", "1.180", "1.210", "4.540"),
    ("2025", "1.200", "1.450", "", "1.300", "3.950"),
    # A share row, as reports carry: its decimal commas settle how "1.200" is read.
    ("Pay (%)", "3,5", "4,1", "", "3,8", "11,4"),
)

INDEX = (
    ("DÖNEM Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık Ortalama",),
    ("2023 101,2 103,4 104,0 104,9 105,5 106,1 107,0 107,6 108,2 109,0 109,5 110,1 106,3",),
    ("2024 110,5 111,0 112,3",),
)


@pytest.fixture
def rig(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        workspace = Workspace.open(lake.connection, "rows")
        tool = make_table_transform_tool(
            lake.connection, workspace, lineage=lake.lineage, document_fetch=lambda *a, **k: None
        )
        yield lake, workspace, tool


def run(tool, held, **arguments):
    parsed = tool.parse({"operation": "document_row", "source": "a1", **arguments})
    return tool.run(parsed, ExecutionContext("soru", outputs={"a1": held}))


class TestOneCellPerColumn:
    held = document(SALES, text="Aylık satışlar (adet), bayi raporu.")

    def test_the_row_becomes_a_monthly_column_with_its_gap_kept(self, rig):
        lake, _, tool = rig
        result = run(tool, self.held, row="2025", label="satış 2025", unit="adet").output
        assert result.status is ResultStatus.COMPUTED and result.tool == "table_transform"
        assert [(v.period.end, v.value) for v in result.values] == [
            (date(2025, 1, 31), 1200.0),
            (date(2025, 2, 28), 1450.0),
            (date(2025, 4, 30), 1300.0),
        ]
        assert {(v.unit, v.scale) for v in result.values} == {("count", Scale.ONE)}
        # The empty March is said, never filled; the total is said, never read as a month.
        assert any("1 empty month" in w for w in result.warnings)
        assert any("'Toplam'" in w and "NOT_A_MONTH" in w for w in result.warnings)
        assert result_faults({"a2": result}, lake.connection) == {}

    def test_provenance_is_kept(self, rig):
        _, _, tool = rig
        result = run(tool, self.held, row="2025", label="satış 2025", unit="adet").output
        [record] = result.evidence.transformations
        assert record.parameters["row"] == {
            "label": "2025",
            "row_number": 2,
            "orientation": "months across columns",
            "layout": "one cell per column",
            "year": 2025,
            "year_from": "row label",
        }
        assert record.parameters["content_hash"] == "a" * 64
        assert result.evidence.lineage_node is not None

    def test_the_monthly_column_is_one_summarize_and_change_read(self, rig):
        _, workspace, tool = rig
        built = run(tool, self.held, row="2025", label="satış 2025", unit="adet")
        context = ExecutionContext("soru", outputs={"a2": built.output})
        highest = tool.run(
            tool.parse(
                {
                    "operation": "summarize",
                    "source": "a2",
                    "column": "satış 2025",
                    "aggregation": "max",
                    "requested_aggregation": "max",
                }
            ),
            context,
        ).output
        assert highest.status is ResultStatus.COMPUTED
        assert [(v.value, v.period.end) for v in highest.values[-1:]] == [
            (1450.0, date(2025, 2, 28))
        ]
        changed = tool.run(
            tool.parse(
                {
                    "operation": "change",
                    "source": "a2",
                    "column": "satış 2025",
                    "kind": "difference",
                }
            ),
            context,
        ).output
        assert changed.status is ResultStatus.COMPUTED

    def test_only_the_named_months(self, rig):
        _, _, tool = rig
        result = run(tool, self.held, row="2025", label="s", columns=["Ocak", "Şubat"]).output
        assert [v.period.end.month for v in result.values] == [1, 2]
        assert result.unresolved_semantics  # No unit named: the unit is said to be unknown.

    def test_a_table_whose_numbers_have_two_readings_is_refused(self, rig):
        _, _, tool = rig
        failed = run(tool, document(SALES[:3]), row="2025", label="s")
        assert failed.status is ToolStatus.FAILURE and "AMBIGUOUS_NUMBER" in failed.warnings[0]

    @pytest.mark.parametrize(
        "arguments, code",
        [
            ({"row": "2026"}, "ROW_NOT_FOUND"),
            ({"row": "2025", "year": 2024}, "YEAR_CONFLICT"),
            ({"row": "2025", "columns": ["Mayıs"]}, "COLUMN_NOT_FOUND"),
            ({"row": "2025", "unit": "milyon TL"}, "UNIT_NOT_IN_DOCUMENT"),
            ({"row": "2025", "unit": "kilometre kare"}, "UNIT_NOT_RECOGNISED"),
        ],
    )
    def test_what_it_cannot_read_it_says(self, rig, arguments, code):
        _, _, tool = rig
        failed = run(tool, self.held, label="s", **arguments)
        assert failed.status is ToolStatus.FAILURE
        assert code in failed.warnings[0]


class TestACollapsedRow:
    """A PDF row left in one cell, as an extractor leaves a borderless table."""

    def test_a_partial_year_fills_the_months_that_have_ended(self, rig):
        _, _, tool = rig
        held = document(INDEX, text="Endeks (2020=100) %", retrieved=date(2024, 4, 15))
        result = run(tool, held, row="2024", label="endeks 2024").output
        assert [(v.period.end, v.value) for v in result.values] == [
            (date(2024, 1, 31), 110.5),
            (date(2024, 2, 29), 111.0),
            (date(2024, 3, 31), 112.3),
        ]
        [record] = result.evidence.transformations
        assert record.parameters["row"]["layout"] == "space-aligned cells"

    def test_a_full_year_reads_every_month_and_leaves_the_average_out(self, rig):
        _, _, tool = rig
        held = document(INDEX, retrieved=date(2024, 4, 15))
        result = run(tool, held, row="2023", label="endeks 2023").output
        assert len(result.values) == 12 and result.values[-1].value == 110.1
        assert any("'Ortalama'" in w for w in result.warnings)

    def test_a_gap_that_cannot_be_placed_is_refused(self, rig):
        _, _, tool = rig
        # Three values for a year that has ended: which month is missing cannot be known.
        held = document(INDEX, retrieved=date(2025, 6, 30))
        failed = run(tool, held, row="2024", label="endeks 2024")
        assert failed.status is ToolStatus.FAILURE and "CELLS_NOT_ALIGNED" in failed.warnings[0]


class TestAnotherSubject:
    def test_a_named_series_row_takes_its_year_from_the_argument(self, rig):
        rates = (
            ("Seri", "Ocak", "Şubat", "Mart"),
            ("Politika faizi (%)", "45,00", "45,00", "42,50"),
            ("Mevduat faizi (%)", "48,10", "47,80", "46,90"),
        )
        _, _, tool = rig
        held = document(rates, text="Oranlar yüzde (%) olarak.")
        needs = run(tool, held, row="Mevduat faizi", label="mevduat")
        assert needs.status is ToolStatus.FAILURE and "YEAR_NEEDED" in needs.warnings[0]
        result = run(tool, held, row="Mevduat faizi", label="mevduat", year=2025, unit="%").output
        assert [v.value for v in result.values] == [48.10, 47.80, 46.90]
        assert {v.measure for v in result.values} == {StockFlow.RATE}
        [record] = result.evidence.transformations
        assert record.parameters["row"]["year_from"] == "argument"

    def test_two_headers_for_one_month_are_refused(self, rig):
        twice = (("Yıl", "Ocak", "Ocak", "Şubat"), ("2025", "1", "2", "3"))
        _, _, tool = rig
        failed = run(tool, document(twice), row="2025", label="x")
        assert failed.status is ToolStatus.FAILURE and "DUPLICATE_PERIOD" in failed.warnings[0]

    def test_a_source_that_is_not_a_document_is_named(self, rig):
        _, _, tool = rig
        parsed = tool.parse(
            {"operation": "document_row", "source": "a9", "row": "2025", "label": "x"}
        )
        failed = tool.run(parsed, ExecutionContext("soru", outputs={"a9": {"not": "a document"}}))
        assert failed.status is ToolStatus.FAILURE and "not a document" in failed.warnings[0]
