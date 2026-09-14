"""M2-15/M5-20 organizer Turn 2: deflate the published Turn 1 table without disturbing it.

Hand-calculated synthetic fixtures over BDDK/EVDS-shaped ingestion; no network.
"""

import json
from datetime import date

import pytest
from pydantic import ValidationError
from test_co_movement import CREDIT, MONTHS, QUESTION, TOTAL_ID, arguments, turn_one
from test_co_movement import lake as lake
from test_evds_load import FakeSource as EvdsSource

from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry
from kkb_agent.agent.loop import workspace_prompt
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace
from kkb_agent.analytics.deflation import DeflationRefused, deflate
from kkb_agent.core import (
    CumulativeKind,
    Frequency,
    Period,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.ingest.evds_load import ingest_series
from kkb_agent.ingest.evds_request import EvdsWindow
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics
from kkb_agent.llm import scripted
from kkb_agent.tools import make_change_detection_tool, make_table_transform_tool
from kkb_agent.tools.table_transform import TableTransformArguments

CPI_ID = "EVDS:TP.TUKFIY2025.GENEL"
CPI = [100.0, 99.0, 101.0, 101.0, 100.0, 102.5]
# real = nominal * CPI[June] / CPI[t]
REAL = [c * 102.5 / i for c, i in zip(CREDIT, CPI, strict=True)]
CPI_SEMANTICS = SeriesSemantics(
    unit="index",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.INDEX,
    cumulative=CumulativeKind.NONE,
    base_year=2025,
)
TURN_TWO = (
    "Konut kredisi ve faiz oranları tablosunu bozmadan konut kredisi tutarlarını "
    "enflasyondan arındırır mısın?"
)


def credit_column(values=CREDIT, **update):
    return [
        ResultValue(
            label="credit",
            value=v,
            unit="TRY",
            scale=Scale.MILLION,
            measure=StockFlow.STOCK,
            period=Period(start=end.replace(day=1), end=end, frequency=Frequency.MONTHLY),
        ).model_copy(update=update)
        for end, v in zip(MONTHS, values, strict=True)
    ]


def index(values=CPI):
    return [Observation(end.replace(day=1), end, v) for end, v in zip(MONTHS, values, strict=True)]


def run_deflate(column=None, observations=None, semantics=CPI_SEMANTICS, reference=MONTHS[5]):
    return deflate(
        credit_column() if column is None else column,
        index() if observations is None else observations,
        semantics,
        column_label="credit",
        index_id=CPI_ID,
        reference_end=reference,
    )


def test_deflation_matches_hand_calculation_in_reference_month_prices():
    result = run_deflate()
    assert [v.value for v in result.values] == pytest.approx(REAL)
    assert REAL[1] == pytest.approx(1025.0) and REAL[4] == pytest.approx(1055.75)
    assert result.label == f"credit real, 2021-06 prices ({CPI_ID})"
    assert {(v.unit, v.scale, v.measure) for v in result.values} == {
        ("TRY", Scale.MILLION, StockFlow.STOCK)
    }
    record = result.transformation
    assert record.operation == "deflate" and record.parameters["reference_index"] == 102.5
    assert record.parameters["index_base_year"] == 2025
    # The reference month's real value equals its nominal value.
    assert result.values[-1].value == CREDIT[-1]


def test_missing_index_months_stay_missing():
    result = run_deflate(observations=index([100.0, None, 101.0, 101.0, 100.0, 102.5]))
    assert [v.period.end for v in result.values] == [MONTHS[0], *MONTHS[2:]]
    assert result.missing_periods == (MONTHS[1],)


@pytest.mark.parametrize(
    "case",
    ["rate_column", "not_index", "weekly_index", "no_reference", "non_positive", "empty", "dupe"],
)
def test_deflation_refuses_what_it_cannot_state(case):
    kwargs = {}
    if case == "rate_column":
        kwargs["column"] = credit_column(unit="percent", scale=Scale.ONE, measure=StockFlow.RATE)
    elif case == "not_index":
        kwargs["semantics"] = SeriesSemantics(
            unit="percent",
            scale=Scale.ONE,
            frequency=Frequency.MONTHLY,
            observation=StockFlow.RATE,
            cumulative=CumulativeKind.NONE,
        )
    elif case == "weekly_index":
        kwargs["semantics"] = SeriesSemantics(
            unit="index",
            scale=Scale.ONE,
            frequency=Frequency.WEEKLY,
            anchor=WeeklyAnchor.FRIDAY,
            observation=StockFlow.INDEX,
            cumulative=CumulativeKind.NONE,
            base_year=2025,
        )
    elif case == "no_reference":
        kwargs["reference"] = date(2022, 1, 31)
    elif case == "non_positive":
        kwargs["observations"] = index([100.0, 0.0, 101.0, 101.0, 100.0, 102.5])
    elif case == "empty":
        kwargs["column"] = []
    else:
        kwargs["column"] = credit_column() + credit_column()[:1]
    with pytest.raises(DeflationRefused):
        run_deflate(**kwargs)


def cpi_values(data):
    for item in data["items"]:
        item["TP_TUKFIY2025_GENEL"] = str(CPI[int(item["Tarih"][5:7]) - 1])


@pytest.fixture
def pool(lake):
    ingest_series(
        lake,
        "TP.TUKFIY2025.GENEL",
        EvdsWindow(start=date(2021, 1, 1), end=date(2021, 6, 30)),
        retrieve=EvdsSource(mutate=cpi_values),
    )
    answered, workspace, _ = turn_one(
        lake, "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı."
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED
    return lake, workspace


def transform(**change):
    return TableTransformArguments.model_validate(
        {
            "operation": "deflate",
            "source": "konut_kredisi_ve_faiz",
            "column": TOTAL_ID,
            "index_series_id": CPI_ID,
            "reference_period": "2021-06-30",
            **change,
        }
    )


def tool(lake, workspace):
    return make_table_transform_tool(
        lake.connection,
        workspace,
        lineage=lake.lineage,
        series_names=prepared_series_names(lake.connection),
    )


def test_deflate_keeps_every_published_value_and_adds_one_column(pool):
    lake, workspace = pool
    source = workspace.value_of("konut_kredisi_ve_faiz")
    result = tool(lake, workspace).run(transform(), ExecutionContext("turn 2")).output
    assert result.status is ResultStatus.COMPUTED and result.tool == "table_transform"
    assert result.values[: len(source.values)] == source.values
    label = f"{TOTAL_ID} real, 2021-06 prices ({CPI_ID})"
    added = [(v.period.end, v.value) for v in result.values if v.label == label]
    assert [end for end, _ in added] == MONTHS
    assert [value for _, value in added] == pytest.approx(REAL)
    assert [t.operation for t in result.evidence.transformations] == [
        "align_weekly_to_monthly",
        "deflate",
    ]
    assert "Values are nominal; no inflation adjustment was applied" not in result.limitations
    assert any("every other column is unchanged and nominal" in item for item in result.limitations)
    assert result.parameters["series_names"][CPI_ID].startswith("TÜFE genel endeksi (2025=100)")
    assert result.parameters["highlighted_periods"] == source.parameters["highlighted_periods"]
    assert result_faults({"turn2": result}, lake.connection) == {}


def test_refusals_and_failures_are_explicit(pool):
    lake, workspace = pool
    run = tool(lake, workspace).run
    rate_label = "EVDS:TP.KTF12 monthly average (by_end)"
    assert run(transform(column=rate_label), ExecutionContext("q")).output.status is (
        ResultStatus.ABSTAINED
    )
    assert run(transform(source="missing"), ExecutionContext("q")).error_category == (
        "workspace_reference"
    )
    assert run(
        transform(index_series_id="EVDS:TP.KFE.TR"), ExecutionContext("q")
    ).error_category == ("series_unknown")
    kfe_as_index = run(transform(index_series_id="EVDS:TP.KTF12"), ExecutionContext("q")).output
    assert kfe_as_index.status is ResultStatus.ABSTAINED and "price index" in kfe_as_index.reason
    for invalid in ({"reference_period": "2021-06-15"}, {"operation": "rebase"}, {"sql": "x"}):
        with pytest.raises(ValidationError):
            transform(**invalid)


def test_planner_sees_published_names_and_labels_but_no_values(pool):
    lake, workspace = pool
    prompt = workspace_prompt(workspace)
    assert "- konut_kredisi_ve_faiz: produced by analytics (monthly-direction-v1)" in prompt
    assert TOTAL_ID in prompt and "EVDS:TP.KTF12 monthly average (by_end)" in prompt
    assert f"{TOTAL_ID} means: BDDK Aylık Bülten" in prompt
    assert "990" not in prompt and "1.010" not in prompt
    assert workspace_prompt(Workspace.open(lake.connection, "empty")) is None


def test_turn_two_end_to_end_is_accepted_published_and_keeps_turn_one(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    names = prepared_series_names(lake.connection)
    registry.register(
        make_change_detection_tool(lake.connection, lineage=lake.lineage, series_names=names)
    )
    registry.register(tool(lake, workspace))
    plan = {
        "question": TURN_TWO,
        "steps": [
            {
                "step_id": "turn2",
                "tool": "table_transform",
                "arguments": json.loads(transform().model_dump_json()),
            }
        ],
    }
    draft = (
        "Tablo korunarak bakiyeye reel sütun eklendi; Şubat 2021'de reel bakiye 1.025 milyon TL."
    )
    session = Session(scripted(json.dumps(plan), draft), registry)
    answered = session.answer(
        TURN_TWO, lake.connection, workspace=workspace, remember="konut_kredisi_ve_faiz_reel"
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert workspace.names() == ["konut_kredisi_ve_faiz", "konut_kredisi_ve_faiz_reel"]
    (table,) = answered.tables
    assert len(table.columns) == 5 and len(table.rows) == 6
    assert table.columns[-1].endswith(
        "real, 2021-06 prices (TÜFE genel endeksi (2025=100), TÜİK, aylık)"
    )
    planner_messages = [m.content for m in session.provider.seen[0]]
    assert any("Results published in earlier turns" in m for m in planner_messages)
    assert any("table_transform" in m for m in planner_messages)
    # Turn 1's published result is unchanged.
    assert workspace.value_of("konut_kredisi_ve_faiz").tool == "analytics"


def test_prepared_check_runs_both_turns_in_one_workspace(lake, tmp_path):
    from kkb_agent import live_check

    ingest_series(
        lake,
        "TP.TUKFIY2025.GENEL",
        EvdsWindow(start=date(2021, 1, 1), end=date(2021, 6, 30)),
        retrieve=EvdsSource(mutate=cpi_values),
    )
    lake.connection.execute("CHECKPOINT")
    first = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "t1",
                "tool": "change_detection",
                "arguments": json.loads(arguments().model_dump_json(exclude_none=True)),
            }
        ],
    }
    second = {
        "question": TURN_TWO,
        "steps": [
            {
                "step_id": "t2",
                "tool": "table_transform",
                "arguments": json.loads(transform().model_dump_json()),
            }
        ],
    }
    provider = scripted(
        json.dumps(first),
        "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı.",
        json.dumps(second),
        "Şubat 2021'de reel bakiye 1.025 milyon TL.",
    )
    report = live_check.run_prepared_check(provider, lake.root, tmp_path / "work", turns=2)
    assert report["passed"] is True
    first_turn, second_turn = report["turns"]
    assert second_turn["published"] == ["konut_kredisi_ve_faiz", "konut_kredisi_ve_faiz_reel"]
    assert second_turn["result"]["transformations"] == ["align_weekly_to_monthly", "deflate"]
    assert second_turn["tables"][0]["rows"] == 6
    assert live_check.run_prepared_check(scripted(), lake.root, tmp_path / "w2", turns=3) == {
        "passed": False,
        "configuration": "unsupported_turns",
    }
