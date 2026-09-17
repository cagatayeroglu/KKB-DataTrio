"""DEC-147 (b): month-form row labels give a cell its calendar month; no network."""

import json
from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import pytest
from test_document_check import FakeFetch
from test_document_table import runtime

from kkb_agent.agent import Session, ToolRegistry
from kkb_agent.agent.literal import literal_proof
from kkb_agent.agent.verifier import AnswerStatus, OmissionCode, result_faults
from kkb_agent.core import Frequency, Period, SourceRef
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.tools._document_column import month_end
from kkb_agent.tools._document_value import (
    Grid,
    ValueNotSelected,
    document_value,
    month_label,
    read_cell,
    row_period,
    select_cell,
)
from kkb_agent.tools.web_url import make_web_url_tool

URL = "https://data.example.test/PRIVATE-PATH/faiz.csv?token=SECRET-QUERY"
QUESTION = f"{URL} dosyasında Aralık 2025 faizi nedir?"
#: The measured U2b shape: month row labels, a percent column, undeclared `;`.
U2B = "Ay;Konut Kredisi (Milyon TL);Faiz (%)\n2025-11;678.100,0;36,75\n2025-12;678.970,0;37,29\n"
DECEMBER = Period(start=date(2025, 12, 1), end=date(2025, 12, 31), frequency=Frequency.MONTHLY)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def refused(code):
    return pytest.raises(ValueNotSelected, match=f"^{code}$")


class TestAMonthFormLabel:
    @pytest.mark.parametrize(
        ("label", "end"),
        [
            ("2025-12", date(2025, 12, 31)),
            (" 12.2025 ", date(2025, 12, 31)),
            ("Aralık 2025", date(2025, 12, 31)),
            ("ARALIK 2025", date(2025, 12, 31)),
            ("December 2025", date(2025, 12, 31)),
            ("Şubat 2024", date(2024, 2, 29)),
            ("02.2025", date(2025, 2, 28)),
        ],
    )
    def test_names_a_calendar_month(self, label, end):
        assert month_label(label) == end
        assert row_period(label) == Period(
            start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY
        )

    @pytest.mark.parametrize(
        "label",
        [
            "2025-13",
            "13.2025",
            "2025-00",
            "1899-12",
            "2101-01",
            "2025",
            "Aralık",
            "2025 Aralık",
            "Aralık 25",
            "12/2025",
            "Q4 2025",
            "Toplam",
            "2025-12-31",
            "31.12.2025",
        ],
    )
    def test_anything_else_is_not_a_month(self, label):
        assert month_label(label) is None

    @pytest.mark.parametrize("label", ["2025-12-31", "31.12.2025", "2025-12-01"])
    def test_a_full_date_stays_a_single_day(self, label):
        period = row_period(label)
        assert period is not None and period.start == period.end
        assert period.frequency is Frequency.UNKNOWN

    @pytest.mark.parametrize("label", ["2025-12", "12.2025", "Aralık 2025", "2025-12-31"])
    def test_the_table_rule_still_reads_the_same_months(self, label):
        assert month_end(label) == date(2025, 12, 31)


GRID = Grid(
    {"table": 1},
    ("Ay", "Faiz (%)", "Kur"),
    (("2025-11", "36,75", "34,1"), ("2025-12", "37,29", "34,5")),
)


class TestSelectingAMonthRow:
    @pytest.mark.parametrize("row", ["2025-12", "12.2025", "Aralık 2025", "december 2025"])
    def test_the_same_month_written_another_way_matches(self, row):
        cell = select_cell([GRID], "Faiz", row)

        assert (cell.raw, cell.row_label) == ("37,29", "2025-12")
        assert read_cell(cell).period == DECEMBER

    @pytest.mark.parametrize("row", ["2025-12-31", "31.12.2025", "2025-12-01", "2025", "Ocak 2026"])
    def test_a_day_a_year_or_another_month_does_not(self, row):
        with refused("VALUE_NOT_FOUND"):
            select_cell([GRID], "Faiz", row)

    def test_a_month_does_not_match_a_day_row(self):
        daily = Grid({"table": 1}, ("Tarih", "Faiz (%)"), (("2025-12-31", "37,29"),))

        with refused("VALUE_NOT_FOUND"):
            select_cell([daily], "Faiz", "Aralık 2025")
        assert read_cell(select_cell([daily], "Faiz", "31.12.2025")).period == Period(
            start=date(2025, 12, 31), end=date(2025, 12, 31)
        )

    def test_a_cell_that_reads_as_a_number_is_no_month_label(self):
        numbers = Grid(
            {"table": 1}, ("Kalem", "Faiz (%)", "Oran"), (("Toplam", "37,29", "12.2025"),)
        )

        with refused("VALUE_NOT_FOUND"):
            select_cell([numbers], "Faiz", "Aralık 2025")
        assert select_cell([numbers], "Faiz", "12.2025").raw == "37,29"  # exact text still matches

    def test_one_month_written_twice_is_ambiguous(self):
        twice = Grid(
            {"table": 1}, ("Ay", "Faiz (%)"), (("2025-12", "37,29"), ("Aralık 2025", "37,30"))
        )

        with refused("AMBIGUOUS_VALUE"):
            select_cell([twice], "Faiz", "2025-12")


def test_a_monthly_cell_states_what_its_period_does_not_say():
    cell = select_cell([GRID], "Faiz", "Aralık 2025")
    source = SourceRef(source_id="web:x", source_type="web_url", locator="https://h/")

    result = document_value(
        cell,
        read_cell(cell),
        source=source,
        label="Faiz | Aralık 2025",
        source_node=None,
        cell_node=None,
    )

    assert result.values[0].period == DECEMBER
    assert result.parameters["period_source"] == "row label"
    assert any(
        "month-end level, a monthly average or a monthly total" in n for n in result.limitations
    )


def _cell_plan(row="2025-12"):
    arguments = {"url": URL, "column": "Faiz", "row": row}
    return json.dumps(
        {"question": "q", "steps": [{"step_id": "s1", "tool": "web_url", "arguments": arguments}]}
    )


@contextmanager
def answered_in(tmp_path, draft, *, content=U2B, row="2025-12"):
    with open_lakehouse(tmp_path / "lake") as lake:
        registry = ToolRegistry()
        fetch = FakeFetch(content.encode())
        registry.register(make_web_url_tool(fetch=fetch, lineage=lake.lineage))
        provider = scripted(_cell_plan(row), draft)
        yield Session(provider, registry).answer(QUESTION, lake.connection), lake


@pytest.mark.parametrize(
    "draft", ["Aralık 2025'te faiz %37,29 oldu.", "2025-12 döneminde faiz %37,29."]
)
def test_the_month_in_the_answer_binds_the_measured_u2b_cell(tmp_path, draft):
    with answered_in(tmp_path, draft) as (answered, lake):
        assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
        (result,) = answered.results
        assert result.values[0].period == DECEMBER
        assert literal_proof(result, lake.connection)
        assert not result_faults({"cell": result}, lake.connection)


@pytest.mark.parametrize(
    "draft", ["Kasım 2025'te faiz %37,29 oldu.", "Aralık 2024'te faiz %37,29 oldu."]
)
def test_another_month_is_still_withheld(tmp_path, draft):
    with answered_in(tmp_path, draft) as (answered, _):
        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert [o.codes for o in answered.answer.omitted] == [(OmissionCode.PERIOD,)]


def test_a_year_label_still_sets_no_period(tmp_path):
    content = "Yıl;Faiz (%)\n2024;40,1\n2025;37,29\n"
    draft = "Aralık 2025'te faiz %37,29 oldu."
    with answered_in(tmp_path, draft, content=content, row="2025") as (answered, _):
        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert answered.results[0].values[0].period is None


def test_a_tampered_period_loses_the_cell_proof(tmp_path):
    with answered_in(tmp_path, "Aralık 2025'te faiz %37,29 oldu.") as (answered, lake):
        (result,) = answered.results
        november = Period(
            start=date(2025, 11, 1), end=date(2025, 11, 30), frequency=Frequency.MONTHLY
        )
        moved = result.model_copy(
            update={"values": [result.values[0].model_copy(update={"period": november})]}
        )
        assert literal_proof(result, lake.connection)
        assert not literal_proof(moved, lake.connection)
        assert result_faults({"cell": moved}, lake.connection)


def test_the_served_prompt_address_cell_carries_its_month_and_proof(tmp_path):
    fetch = FakeFetch(U2B.encode())
    runner, _ = runtime(
        tmp_path,
        scripted(_cell_plan("Aralık 2025"), "Aralık 2025'te faiz %37,29 oldu."),
        fetch=fetch,
    )
    sid = uuid4().hex

    answer = runner(sid, uuid4().hex, QUESTION)

    assert answer.status.value == "accepted" and answer.result is not None, answer
    (cell,) = answer.result.cells
    assert (cell.value, cell.unit, cell.period.start, cell.period.end) == (
        37.29,
        "percent",
        date(2025, 12, 1),
        date(2025, 12, 31),
    )
    assert answer.result.proof.availability == "available"
    assert [d.row for d in answer.result.proof.documents] == [2]
    assert "PRIVATE-PATH" not in answer.model_dump_json() and len(fetch.requests) == 1
