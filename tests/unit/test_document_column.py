"""M7-14 slice 2: a fetched document column joined onto a selected table; no network."""

import json
from datetime import date, datetime
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
from test_document_check import FakeFetch
from test_prepared_dense import POLICY, Recording, build_index
from test_series_inspection import SQL

from kkb_agent.agent import Workspace
from kkb_agent.agent.discovery import WEB_ADDRESS_INSTRUCTIONS
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics.table_series import SeriesAdditionRefused, add_document_column
from kkb_agent.api.prepared import PreparedRunner
from kkb_agent.api.proof import build_proof
from kkb_agent.api.service import SelectedResult
from kkb_agent.catalog import embedding
from kkb_agent.catalog.hybrid import CatalogDenseStage
from kkb_agent.catalog.lance_index import LocalCatalogIndex
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import (
    AnalyticalResult,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
)
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.tools._document_column import ColumnRefused, month_end, read_column
from kkb_agent.tools._document_value import Grid

URL = "https://data.example.test/PRIVATE-PATH/bist.csv?token=SECRET-QUERY"
ASK = f"{URL} adresindeki tablodan Kapanış sütununu önceki tabloya ekle. PRIVATE-QUESTION"
CSV = (
    "Ay;Kapanış (Puan);Not\n"
    "2026-03;9000;RAW-CONTENT\n"
    "Nisan 2026;9.100,5;x\n"
    "31.05.2026;;y\n"
    "2026-06-01;9200;z\n"
).encode()
PRIVATE = ("PRIVATE-PATH", "SECRET-QUERY", "PRIVATE-QUESTION", "RAW-CONTENT", "Kapanış (Puan)")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live request in these tests")

    monkeypatch.setattr("socket.socket.connect", forbidden)


def grid(*rows, headers=("Ay", "Kapanış (Puan)"), location=None):
    return Grid(location or {"table": 1}, headers, tuple(rows))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-01", date(2026, 1, 31)),
        ("01.2026", date(2026, 1, 31)),
        ("Ocak 2026", date(2026, 1, 31)),
        ("ŞUBAT 2024", date(2024, 2, 29)),
        ("March 2026", date(2026, 3, 31)),
        ("2026-01-31", date(2026, 1, 31)),
        ("2026-02-01", date(2026, 2, 28)),
        ("31.01.2026", date(2026, 1, 31)),
        (date(2026, 4, 30), date(2026, 4, 30)),
        (datetime(2026, 4, 1), date(2026, 4, 30)),
        ("2026-01-15", None),
        ("15.01.2026", None),
        ("Q1 2026", None),
        ("2026", None),
        ("13.2026", None),
        ("Ocak", None),
        ("Jan 2026", None),
        (datetime(2026, 1, 31, 12, 0), None),
        (202601, None),
        (None, None),
    ],
)
def test_only_explicit_months_are_periods(raw, expected):
    assert month_end(raw) == expected


def test_column_reads_months_numbers_and_header_unit():
    column = read_column(
        [
            grid(
                ("2026-04", "9.100,5"),
                ("", ""),
                ("2026-05", None),
                ("2026-06", 9200),
            )
        ],
        "ay",
        "KAPANIŞ",
    )
    assert (column.unit, column.scale, column.measure) == ("points", Scale.ONE, StockFlow.INDEX)
    assert column.location == {"table": 1, "column_index": 2}
    assert column.levels == {
        date(2026, 4, 30): 9100.5,
        date(2026, 5, 31): None,
        date(2026, 6, 30): 9200.0,
    }


@pytest.mark.parametrize(
    ("tables", "code"),
    [
        ([grid(("2026-04", "1"), headers=("Tarih", "Kapanış (Puan)"))], "COLUMN_NOT_FOUND"),
        ([grid(("2026-04", "1")), grid(("2026-05", "2"))], "AMBIGUOUS_COLUMN"),
        (
            [grid(("2026-04", "1", "2"), headers=("Ay", "Kapanış (Puan)", "Kapanış"))],
            "AMBIGUOUS_COLUMN",
        ),
        ([grid(("2026-04", "1"), headers=("Ay", "Kapanış"))], "UNIT_NOT_STATED"),
        ([grid(("2026-04-15", "1"))], "PERIOD_NOT_RECOGNISED"),
        ([grid(("2026-04", "1"), ("Toplam", "9"))], "PERIOD_NOT_RECOGNISED"),
        ([grid(("", "1"))], "PERIOD_NOT_RECOGNISED"),
        ([grid(("2026-01", "1"), ("31.01.2026", "2"))], "DUPLICATE_PERIOD"),
        ([grid(("2026-04", "1.234"))], "AMBIGUOUS_NUMBER"),
        ([grid(("2026-04", "yok"))], "NOT_A_NUMBER"),
        ([grid(("", ""))], "COLUMN_EMPTY"),
    ],
)
def test_column_refuses_what_it_would_have_to_decide(tables, code):
    with pytest.raises(ColumnRefused) as refused:
        read_column(tables, "Ay", "Kapanış")
    assert refused.value.code == code


@pytest.mark.parametrize(
    ("header", "unit", "measure"),
    [
        ("Kapanış (Puan)", "points", StockFlow.INDEX),
        ("Kapanış (Endeks)", "index", StockFlow.INDEX),
        ("Kapanış (Milyon TL)", "TRY", StockFlow.UNKNOWN),
        ("Faiz (%)", "percent", StockFlow.RATE),
        ("Faiz (Milyon %)", "percent", StockFlow.UNKNOWN),
        ("Kapanış (Milyon Puan)", "points", StockFlow.UNKNOWN),
    ],
)
def test_only_points_index_or_percent_units_name_a_measure(header, unit, measure):
    column = read_column(
        [grid(("2026-04", "1"), ("2026-05", "2"), headers=("Ay", header))],
        "Ay",
        header.split(" (")[0],
    )
    assert (column.unit, column.measure) == (unit, measure)


def monthly_table(label="BDDK:total", unit="TRY"):
    values = [
        ResultValue(
            label=label,
            value=value,
            unit=unit,
            scale=Scale.MILLION,
            measure=StockFlow.STOCK,
            period=Period(
                start=date(2026, m, 1), end=date(2026, m, last), frequency=Frequency.MONTHLY
            ),
        )
        for m, last, value in [(4, 30, 100.0), (5, 31, 120.0), (6, 30, 150.0)]
    ]
    return AnalyticalResult(
        result_id="t",
        kind=ResultKind.SERIES,
        status=ResultStatus.COMPUTED,
        tool="lakehouse",
        values=values,
        evidence=ResultEvidence(input_refs=["silver_observations"]),
    )


def test_join_keeps_every_cell_and_fills_nothing():
    source = monthly_table()
    levels = {
        date(2026, 3, 31): 9000.0,
        date(2026, 4, 30): 9100.5,
        date(2026, 5, 31): None,
        date(2026, 6, 30): 9200.0,
    }
    added = add_document_column(
        source,
        levels,
        label="Kapanış",
        unit="points",
        scale=Scale.ONE,
        document_rows=4,
        content_hash="sha256:x",
    )
    assert [(v.period.end, v.value, v.measure) for v in added.values] == [
        (date(2026, 4, 30), 9100.5, StockFlow.UNKNOWN),
        (date(2026, 6, 30), 9200.0, StockFlow.UNKNOWN),
    ]
    assert added.missing_periods == (date(2026, 5, 31),)
    parameters = added.transformation.parameters
    assert parameters["outside_table_periods"] == 1 and parameters["fill"] == "none"
    assert parameters["measure"] == "unknown" and parameters["unit_source"] == "column header"


@pytest.mark.parametrize("problem", ["label_exists", "one_match", "no_unit", "stated_stock"])
def test_join_refuses_collisions_thin_columns_and_unknown_units(problem):
    source = monthly_table()
    levels = {date(2026, 4, 30): 1.0, date(2026, 5, 31): 2.0}
    label, unit, measure = "Kapanış", "points", StockFlow.UNKNOWN
    if problem == "stated_stock":
        measure = StockFlow.STOCK
    elif problem == "label_exists":
        label = "BDDK:total"
    elif problem == "one_match":
        levels = {date(2026, 4, 30): 1.0}
    else:
        unit = ""
    with pytest.raises(SeriesAdditionRefused):
        add_document_column(
            source,
            levels,
            label=label,
            unit=unit,
            scale=Scale.ONE,
            document_rows=2,
            content_hash="h",
            measure=measure,
        )


def table_turn():
    return proposal(
        {"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}}
    ), "Tablo hazır."


def add_plan(**overrides):
    arguments = {
        "operation": "add_document_column",
        "source": "analiz_1",
        "url": URL,
        "delimiter": ";",
        "period_column": "Ay",
        "value_column": "Kapanış",
        **overrides,
    }
    return proposal({"step_id": "b", "tool": "table_transform", "arguments": arguments})


def served(tmp_path, provider, fetch, **kwargs):
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    return PreparedRunner(
        provider,
        root,
        tmp_path.resolve() / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        web_url_fetch=fetch,
        **kwargs,
    )


def first_table(runner):
    sid, tid = uuid4().hex, uuid4().hex
    answer = runner(sid, tid, "Konut kredisi tablosunu getir.")
    assert answer.status.value == "accepted" and answer.result is not None, answer
    return sid, answer, SelectedResult(tid, answer.result.result_ref, answer.result.version)


def test_selected_table_takes_a_document_column_with_its_proof(tmp_path):
    fetch = FakeFetch(CSV)
    provider = scripted(*table_turn(), add_plan(), "Kapanış sütunu tabloya eklendi.")
    runner = served(tmp_path, provider, fetch)
    sid, first, selection = first_table(runner)

    second = runner.selected(sid, uuid4().hex, ASK, selection)
    assert second.status.value == "accepted" and second.result is not None, second
    cells = second.result.cells
    assert [c.value for c in cells[:3]] == [c.value for c in first.result.cells]
    assert [(c.label, c.value, c.unit, c.scale.value, c.measure.value) for c in cells[3:]] == [
        ("Kapanış", 9100.5, "points", "one", "index"),
        ("Kapanış", 9200.0, "points", "one", "index"),
    ]
    proof = second.result.proof
    # The synthetic seed has no raw-source lineage; the document part is complete.
    assert proof.availability != "unavailable" and set(proof.gaps) <= {"source_lineage_missing"}
    assert proof.steps[0].producer == "table_transform"
    assert {item.kind for item in proof.steps[0].inputs} == {"result", "document"}
    (document,) = proof.documents
    assert (document.host, document.document_format, document.row, document.column) == (
        "data.example.test",
        "csv",
        None,
        2,
    )
    assert document.values_read == 3 and document.sheet_selected is False
    assert not [item for item in PRIVATE if item in second.model_dump_json()]
    assert len(fetch.requests) == 1

    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        assert workspace.names() == ["analiz_1", "analiz_2"]
        assert workspace.value_of("analiz_1").digest() == first.result.version
        stored = " ".join(
            str(row[0])
            for row in lake.connection.execute("SELECT attributes FROM lineage_nodes").fetchall()
        )
        assert "SECRET-QUERY" not in stored and "PRIVATE-QUESTION" not in stored
        added = workspace.value_of("analiz_2")
        assert not result_faults({"analiz_2": added}, lake.connection)
        changed = [
            value.model_copy(update={"value": 9999.0}) if value.label == "Kapanış" else value
            for value in added.values
        ]
        tampered = added.model_copy(update={"values": changed})
        assert result_faults({"analiz_2": tampered}, lake.connection)
        assert build_proof(lake.connection, tampered).availability == "unavailable"


@pytest.mark.parametrize(
    ("unit", "comparable"), [("Puan", True), ("Endeks", True), ("Milyon TL", False)]
)
def test_only_an_index_level_column_enters_a_table_comparison(tmp_path, unit, comparable):
    relationship = proposal(
        {
            "step_id": "c",
            "tool": "change_detection",
            "arguments": {
                "operation": "table_co_movement",
                "source": "analiz_2",
                "driver_column": "Kapanış",
                "target_column": TOTAL,
                "driver_direction": "up",
                "target_direction": "up",
            },
        }
    )
    csv = f"Ay;Kapanış ({unit})\n2026-04;9000\n2026-05;9100\n2026-06;9200\n".encode()
    provider = scripted(
        *table_turn(), add_plan(), "Eklendi.", relationship, "Karşılaştırma tamamlandı."
    )
    runner = served(tmp_path, provider, FakeFetch(csv))
    sid, _, selection = first_table(runner)
    second = runner.selected(sid, (tid := uuid4().hex), ASK, selection)
    assert second.status.value == "accepted" and second.result is not None, second
    follow = SelectedResult(tid, second.result.result_ref, second.result.version)
    third = runner.selected(sid, uuid4().hex, "Kapanış ile kredi aynı yönde mi?", follow)
    if not comparable:
        # DEC-145: a currency column's stock/flow meaning is not stated; nothing is guessed.
        assert third.status.value == "abstained" and third.result is None
        return
    assert third.status.value == "accepted" and third.result is not None, third
    counts = {
        cell.label.split(": ", 1)[1]: cell.value
        for cell in third.result.cells
        if cell.label.startswith("table comparison ")
    }
    # Both columns rise in both transitions (9000→9100→9200 and 100→120→150).
    assert counts["eligible transitions matching both directions"] == 2.0, counts
    assert [d.values_read for d in third.result.proof.documents] == [3]


def test_without_the_switch_the_operation_does_not_exist(tmp_path):
    fetch = FakeFetch(CSV)
    provider = scripted(*table_turn(), add_plan(), add_plan())
    runner = served(tmp_path, provider, None)
    sid, _, selection = first_table(runner)
    with pytest.raises(Exception, match="Planner repeated an invalid plan"):
        runner.selected(sid, uuid4().hex, ASK, selection)
    assert not fetch.requests
    tools = json.dumps([m.content for m in provider.seen[2]], ensure_ascii=False)
    assert "add_document_column" not in tools


@pytest.mark.parametrize(
    ("fetch", "plan", "question"),
    [
        (FakeFetch(CSV), add_plan(url="https://data.example.test/other.csv"), ASK),
        (FakeFetch(CSV), add_plan(), "Kapanış sütununu önceki tabloya ekle."),
        (FakeFetch(CSV.replace(b"2026-06-01", b"2026-05")), add_plan(), ASK),
        (FakeFetch(CSV.replace(b" (Puan)", b"")), add_plan(), ASK),
    ],
    ids=["other_address", "no_address_in_question", "duplicate_month", "unit_not_stated"],
)
def test_refused_columns_publish_nothing(tmp_path, fetch, plan, question):
    provider = scripted(*table_turn(), plan, "Eklendi.")
    runner = served(tmp_path, provider, fetch)
    sid, _, selection = first_table(runner)
    answer = runner.selected(sid, uuid4().hex, question, selection)
    assert answer.status.value == "abstained" and answer.result is None
    assert not [item for item in PRIVATE if item in answer.model_dump_json()]
    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        assert Workspace.open(lake.connection, sid).names() == ["analiz_1"]
    if "other.csv" in plan or question.startswith("Kapanış"):
        assert not fetch.requests


def test_hybrid_second_turn_adds_a_column_without_discovery(tmp_path):
    from test_catalog_continuation import discover

    calculate = proposal({"step_id": "a", "tool": "lakehouse", "arguments": {"sql": SQL}})
    provider = Recording(
        scripted(
            proposal(discover()),
            calculate,
            "Tablo hazır.",
            add_plan(),
            "Kapanış sütunu eklendi.",
            embedding_dimension=4096,
        )
    )
    index = build_index(tmp_path.resolve() / "index", CATALOG)
    snapshot = load_reviewed_snapshot(CATALOG.read_bytes())
    stage = CatalogDenseStage(
        LocalCatalogIndex.open(index, snapshot, embedding.profile_for(POLICY, "kloudeks")),
        embedding.query_embedder(provider, POLICY, origin="kloudeks"),
    )
    runner = served(tmp_path, provider, FakeFetch(CSV), catalog_dense=stage)
    sid, _, selection = first_table(runner)
    embedded = len(provider.embedded)
    second = runner.selected(sid, uuid4().hex, ASK, selection)
    assert second.status.value == "accepted" and second.result is not None, second
    assert len(provider.embedded) == embedded
    assert any(m.content == WEB_ADDRESS_INSTRUCTIONS for m in provider.seen[3])


def test_add_document_column_needs_no_discovery():
    from kkb_agent.agent.discovery import validate_discovery_phase
    from kkb_agent.agent.executor import ValidatedPlan, ValidatedStep
    from kkb_agent.agent.plan import PlanStep
    from kkb_agent.tools.table_transform import DocumentTableTransformArguments

    (step,) = json.loads(add_plan())["steps"]
    arguments = DocumentTableTransformArguments.model_validate(step["arguments"])
    plan = ValidatedPlan("q", (ValidatedStep(PlanStep(**step), arguments),))
    validate_discovery_phase(plan, continuation=False, require_series_discovery=True)
