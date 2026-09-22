"""M6-25 organizer Turn 1: monthly co-movement over prepared BDDK/EVDS-shaped data.

Hand-calculated synthetic fixtures; real values are used only in the recorded
live evidence, never here. No network.
"""

import json
from datetime import date

import pytest
from test_bddk_monthly_load import response as bddk_response
from test_evds_load import FakeSource as EvdsSource

from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry
from kkb_agent.agent.presentation import display_value
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import Workspace
from kkb_agent.analytics.comovement import co_movement
from kkb_agent.core import (
    DIMENSIONLESS,
    Aggregation,
    CumulativeKind,
    Frequency,
    ResultStatus,
    ResultValue,
    Scale,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.ingest.bddk_monthly import BddkSelector, MonthlyPeriod
from kkb_agent.ingest.bddk_monthly_load import ingest_monthly
from kkb_agent.ingest.bddk_monthly_request import MonthlyRange
from kkb_agent.ingest.evds_load import ingest_series
from kkb_agent.ingest.evds_request import EvdsWindow
from kkb_agent.ingest.prepared_series import (
    prepared_series_coverage,
    prepared_series_names,
    reviewed_series_names,
)
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.records import Observation
from kkb_agent.lakehouse.semantics import SeriesSemantics
from kkb_agent.llm import scripted
from kkb_agent.tools import make_change_detection_tool
from kkb_agent.tools.change_detection import ChangeDetectionArguments

RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)
STOCK = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
)
MONTHS = [date(2021, m, d) for m, d in ((1, 31), (2, 28), (3, 31), (4, 30), (5, 31), (6, 30))]
# Rate falls in Feb, Mar, Apr and Jun; credit falls in Feb and Jun and is flat in Apr.
RATES = [10.0, 9.5, 9.0, 8.5, 9.0, 8.75]
CREDIT = [1000.0, 990.0, 1010.0, 1010.0, 1030.0, 1025.0]
TOTAL_ID = BddkSelector(
    bulletin_family="monthly",
    table=4,
    row=2,
    bank_group=10001,
    presentation_currency="TL",
    value_dimension="TOTAL",
).internal_id()


def monthly(values):
    return [Observation(end.replace(day=1), end, v) for end, v in zip(MONTHS, values, strict=True)]


def compute(rates=RATES, credit=CREDIT, **kwargs):
    arguments = {
        "start": date(2021, 1, 1),
        "end": date(2021, 6, 30),
        "driver_label": "rate",
        "target_label": "credit",
        "input_refs": ["silver_observations"],
        **kwargs,
    }
    return co_movement(monthly(rates), RATE, monthly(credit), STOCK, **arguments)


def by_label(result, label):
    return [(v.period.end, v.value) for v in result.values if v.label == label]


def test_directions_counts_and_flagged_months_match_hand_calculation():
    result = compute()
    assert result.status is ResultStatus.COMPUTED and result.samples.used == 5
    assert by_label(result, "credit") == list(zip(MONTHS, CREDIT, strict=True))
    assert by_label(result, "rate month-over-month change") == [
        (MONTHS[1], -0.5),
        (MONTHS[2], -0.5),
        (MONTHS[3], -0.5),
        (MONTHS[4], 0.5),
        (MONTHS[5], -0.25),
    ]
    assert [v.value for v in result.values if v.unit == DIMENSIONLESS] == [5.0, 4.0, 1.0, 3.0]
    # A flat balance (April) did not rise; only March rose while the rate fell.
    assert result.parameters["highlighted_periods"] == {
        "rate fell and credit did not rise": ["2021-02-28", "2021-04-30", "2021-06-30"]
    }
    assert by_label(result, "credit month-over-month change") == [
        (MONTHS[1], -10.0),
        (MONTHS[2], 20.0),
        (MONTHS[3], 0.0),
        (MONTHS[4], 20.0),
        (MONTHS[5], -5.0),
    ]
    # Every number appears once per label and period, so a quote is never ambiguous.
    keys = [(v.label, v.period.end) for v in result.values]
    assert len(keys) == len(set(keys))
    change = next(v for v in result.values if v.label == "rate month-over-month change")
    assert (change.unit, change.scale) == ("percentage point", Scale.ONE)
    assert any("not new lending or disbursement" in item for item in result.limitations)
    assert any("not evidence that one series caused" in item for item in result.limitations)
    assert any("nominal" in item for item in result.limitations)


def test_gaps_are_never_bridged():
    rates = [10.0, 9.5, None, 8.5, 9.0, 8.75]
    result = compute(rates=rates)
    assert [v.period.end for v in result.values if v.label == "rate month-over-month change"] == [
        MONTHS[1],
        MONTHS[4],
        MONTHS[5],
    ]
    assert result.samples.used == 3 and result.samples.missing == 2


@pytest.mark.parametrize(
    "change,status",
    [
        ({"rates": [10.0, None, 9.0, None, 8.0, None]}, ResultStatus.INSUFFICIENT),
        ({"end": date(2020, 12, 31)}, ResultStatus.UNDEFINED),
    ],
)
def test_too_few_transitions_or_backwards_window(change, status):
    result = compute(**change)
    assert result.status is status and not result.values and result.reason


def test_non_monthly_cumulative_duplicate_or_unresolved_inputs_abstain():
    weekly = SeriesSemantics(
        unit="percent",
        scale=Scale.ONE,
        frequency=Frequency.WEEKLY,
        anchor=WeeklyAnchor.FRIDAY,
        observation=StockFlow.RATE,
        cumulative=CumulativeKind.NONE,
    )
    cumulative = SeriesSemantics(
        unit="TRY",
        scale=Scale.MILLION,
        frequency=Frequency.MONTHLY,
        observation=StockFlow.FLOW,
        cumulative=CumulativeKind.YEARLY_RESET,
    )
    unknown = SeriesSemantics(
        unit="TRY",
        scale=Scale.UNKNOWN,
        frequency=Frequency.MONTHLY,
        observation=StockFlow.STOCK,
        cumulative=CumulativeKind.NONE,
    )
    window = {
        "start": date(2021, 1, 1),
        "end": date(2021, 6, 30),
        "driver_label": "r",
        "target_label": "c",
        "input_refs": ["x"],
    }
    for driver, target in ((weekly, STOCK), (RATE, cumulative), (RATE, unknown)):
        result = co_movement(monthly(RATES), driver, monthly(CREDIT), target, **window)
        assert result.status is ResultStatus.ABSTAINED and not result.values
    doubled = monthly(CREDIT) + monthly(CREDIT)[:1]
    assert (
        co_movement(monthly(RATES), RATE, doubled, STOCK, **window).status is ResultStatus.ABSTAINED
    )


def test_point_units_are_displayable_and_bindable():
    point = ResultValue(label="x", value=-0.403, unit="percentage point", scale=Scale.ONE)
    assert display_value(point) == "-0,4030 yüzde puan"
    index = ResultValue(label="x", value=1.5, unit="index point", scale=Scale.ONE)
    assert display_value(index) == "1,5 endeks puan"


def test_reviewed_names_cover_every_reviewed_series_and_only_registered_ones(tmp_path):
    names = reviewed_series_names()
    assert TOTAL_ID in names and "kullandırım değil" in names[TOTAL_ID]
    assert {
        "EVDS:TP.KTF12",
        "EVDS:TP.TUKFIY2025.GENEL",
        "EVDS:TP.GENENDEKS.T1",
        "EVDS:TP.KFE.TR",
    } <= (set(names))
    assert len(names) == 29  # Three BDDK components and the expanded 26-series EVDS review.
    with open_lakehouse(tmp_path / "lake") as lake:
        assert prepared_series_names(lake.connection) == {}


# --- tool and end-to-end over ingested BDDK/EVDS-shaped data ---------------------------------


def bddk_source(request):
    total = CREDIT[request.period.month - 1]
    payload = bddk_response(request, values=(total - 5, 5, total))
    return FetchSuccess(
        source_ref=request.fetch_request().source_ref,
        content=json.dumps(payload, ensure_ascii=False).encode(),
        media_type="application/json",
        http_status=200,
    )


def weekly_rates(data):
    for item in data["items"]:
        month = int(item["Tarih"][3:5])
        # Every Friday carries its month's rate; the trailing July week is excluded anyway.
        item["TP_KTF12"] = f"{(RATES + [7.0])[month - 1]:.2f}"


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as result:
        window = MonthlyRange(
            start=MonthlyPeriod(year=2021, month=1), end=MonthlyPeriod(year=2021, month=6)
        )
        selector = BddkSelector.model_validate(
            {
                "bulletin_family": "monthly",
                "table": 4,
                "row": 2,
                "bank_group": 10001,
                "presentation_currency": "TL",
                "value_dimension": "TOTAL",
            }
        )
        ingest_monthly(result, selector, window, retrieve=bddk_source)
        ingest_series(
            result,
            "TP.KTF12",
            EvdsWindow(start=date(2021, 1, 1), end=date(2021, 6, 30)),
            retrieve=EvdsSource(mutate=weekly_rates),
        )
        yield result


def arguments(**change):
    return ChangeDetectionArguments.model_validate(
        {
            "operation": "co_movement",
            "series_id": TOTAL_ID,
            "driver_series_id": "EVDS:TP.KTF12",
            "start": "2021-01-01",
            "end": "2021-06-30",
            "week_assignment": "by_end",
            **change,
        }
    )


def run_tool(lake, **change):
    tool = make_change_detection_tool(
        lake.connection, lineage=lake.lineage, series_names=prepared_series_names(lake.connection)
    )
    return tool.run(arguments(**change), ExecutionContext(question="turn 1")).output


def test_tool_reduces_weekly_rate_records_policy_and_passes_result_checks(lake):
    result = run_tool(lake)
    assert result.status is ResultStatus.COMPUTED
    rate_label = "EVDS:TP.KTF12 monthly average (by_end)"
    assert by_label(result, rate_label) == list(zip(MONTHS, RATES, strict=True))
    (alignment,) = result.evidence.transformations
    assert alignment.operation == "align_weekly_to_monthly"
    assert alignment.parameters["week_assignment"] == "by_end"
    assert alignment.parameters["incomplete_months_excluded"] == 0
    assert result.parameters["series_names"][TOTAL_ID].startswith("BDDK Aylık Bülten")
    assert result.run_id and result.evidence.evidence_ids
    assert result_faults({"turn1": result}, lake.connection) == {}


def test_week_assignment_is_a_visible_policy_not_a_hidden_default(lake):
    by_majority = run_tool(lake, week_assignment="by_majority")
    label = "EVDS:TP.KTF12 monthly average (by_majority)"
    # Friday 2 April 2021 holds five March days, so it moves into March.
    assert dict(by_label(by_majority, label))[MONTHS[2]] == pytest.approx((9.0 * 4 + 8.5) / 5)
    missing = run_tool(lake, week_assignment=None)
    assert missing.status is ResultStatus.ABSTAINED and "week_assignment" in missing.reason


@pytest.mark.parametrize(
    "change",
    [
        {"driver_series_id": None},
        {"operation": "compare", "start": "2021-01-31", "end": "2021-06-30"},
        {"week_assignment": "nearest"},
        {"unexpected": True},
    ],
)
def test_invalid_operation_arguments_are_refused(change):
    with pytest.raises(ValueError):
        arguments(**change)


def test_unknown_driver_is_a_tool_failure(lake):
    tool = make_change_detection_tool(lake.connection)
    outcome = tool.run(arguments(driver_series_id="EVDS:TP.KBK.TRY.18"), ExecutionContext("q"))
    assert outcome.error_category == "series_unknown"


def test_description_names_prepared_series_for_the_planner(lake):
    names = prepared_series_names(lake.connection)
    assert set(names) == {TOTAL_ID, "EVDS:TP.KTF12"}
    description = make_change_detection_tool(lake.connection, series_names=names).description
    assert f"{TOTAL_ID}: BDDK Aylık Bülten" in description and "EVDS:TP.KTF12: EVDS" in description
    assert "Prepared series" not in make_change_detection_tool(lake.connection).description


QUESTION = (
    "2021 yılının ilk yarısında konut kredileri ve konut kredisi faizlerini aylık göster; "
    "faiz düştüğü halde kredinin artmadığı aylar var mı?"
)


def turn_one(lake, draft):
    registry = ToolRegistry()
    registry.register(
        make_change_detection_tool(
            lake.connection,
            lineage=lake.lineage,
            series_names=prepared_series_names(lake.connection),
        )
    )
    plan = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "turn1",
                "tool": "change_detection",
                "arguments": json.loads(arguments().model_dump_json(exclude_none=True)),
            }
        ],
    }
    workspace = Workspace.open(lake.connection)
    # These legacy cases exercise the model-writer/gate path explicitly.
    session = Session(scripted(json.dumps(plan), draft), registry, deterministic_presentation=False)
    answered = session.answer(
        QUESTION, lake.connection, workspace=workspace, remember="konut_kredisi_ve_faiz"
    )
    return answered, workspace, session


def test_turn_one_end_to_end_is_accepted_and_published(lake):
    draft = (
        "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı. "
        "Şubat 2021'de faiz 9,5 yüzde oldu ve bakiye 990 milyon TL'ye indi."
    )
    answered, workspace, session = turn_one(lake, draft)
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert workspace.names() == ["konut_kredisi_ve_faiz"]
    tools_prompt = session.provider.seen[0][1].content
    assert "kullandırım değil" in tools_prompt and TOTAL_ID in tools_prompt
    writer_prompt = session.provider.seen[1][1].content
    assert f"Series {TOTAL_ID} means: BDDK Aylık Bülten" in writer_prompt
    assert "did not rise: 2021-02-28, 2021-04-30, 2021-06-30" in writer_prompt
    assert "not evidence that one series caused" in writer_prompt


@pytest.mark.parametrize(
    "unsupported_cause",
    [
        "Faiz düşüşü kredi artışına neden oldu.",
        "Faiz düşüşü kredi artışına neden olmadı.",
    ],
)
def test_turn_one_causal_wording_is_kept_and_the_reader_is_told_what_was_tested(
    lake, unsupported_cause
):
    # The gate binds figures; wording is the writer's. A sentence about cause used to be
    # withheld, assertion and denial alike, and took the turn's table with it. It is kept,
    # and the harness's own note says what the tools did and did not establish.
    from kkb_agent.agent.loop import CAUSE_NOTE

    draft = (
        "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı. " + unsupported_cause
    )
    answered, workspace, _ = turn_one(lake, draft)
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert unsupported_cause in answered.answer.text and CAUSE_NOTE in answered.answer.text
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_turn_one_table_rows_bind_to_their_own_periods(lake):
    rate = "EVDS:TP.KTF12 monthly average (by_end)"
    draft = (
        "| Dönem | Bakiye | Faiz |\n|---|---:|---:|\n"
        "| 2021-01-01..2021-01-31 | 1.000 milyon TL | 10 yüzde |\n"
        "| 2021-02-01..2021-02-28 | 990 milyon TL | 9,5 yüzde |\n"
        "Faizin düştüğü ve bakiyenin artmadığı aylar:\n"
        "- 2021-02-01..2021-02-28: bakiye değişimi -10 milyon TL\n"
        "- 2021-06-01..2021-06-30: bakiye değişimi -5 milyon TL"
    )
    answered, workspace, _ = turn_one(lake, draft)
    (description,) = answered.results[-1].parameters["highlighted_periods"]
    assert description.startswith(rate)
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_a_wrong_table_row_is_withheld_without_silencing_the_others(lake):
    draft = (
        "| 2021-01-01..2021-01-31 | 1.000 milyon TL |\n"
        "| 2021-02-01..2021-02-28 | 1.010 milyon TL |\n"
        "| 2021-03-01..2021-03-31 | 1.010 milyon TL |"
    )
    answered, workspace, _ = turn_one(lake, draft)
    assert answered.answer.status is AnswerStatus.QUALIFIED
    assert len(answered.answer.omitted) == 1 and "2021-02-01" in answered.answer.omitted[0].text
    assert "2021-03-01..2021-03-31" in answered.answer.text
    # The table is what the tools computed; a withheld sentence about it does not unpublish it.
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_turn_one_with_an_invented_figure_is_not_published(lake):
    draft = "Şubat 2021'de bakiye 987 milyon TL'ye indi."
    answered, workspace, _ = turn_one(lake, draft)
    assert answered.answer.status is not AnswerStatus.ACCEPTED
    assert workspace.names() == []


def test_prepared_check_runs_turn_one_on_a_private_copy(lake, tmp_path):
    from kkb_agent import live_check

    lake.connection.execute("CHECKPOINT")
    before = lake.connection.execute("SELECT count(*) FROM lineage_nodes").fetchone()
    lake.connection.close()  # Prepared datasets must be closed before copying.
    plan = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "turn1",
                "tool": "change_detection",
                "arguments": json.loads(arguments().model_dump_json(exclude_none=True)),
            }
        ],
    }
    draft = "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı."
    report = live_check.run_prepared_check(
        scripted(json.dumps(plan), draft), lake.root, tmp_path / "work", question=QUESTION
    )
    assert report["passed"] is True and report["answer"]["status"] == "accepted"
    assert report["published"] == [live_check.TURN_ONE_NAME]
    assert report["prepared_series"] == 2
    assert report["result"]["transformations"] == ["align_weekly_to_monthly"]
    assert sorted(report["result"]["counts"].values()) == [1.0, 3.0, 4.0, 5.0]
    # Runtime evidence and workspace writes went to the copy, not the prepared root.
    with open_lakehouse(lake.root) as prepared:
        assert (
            prepared.connection.execute("SELECT count(*) FROM lineage_nodes").fetchone() == before
        )
        assert prepared.connection.execute(
            "SELECT count(*) FROM workspace_artifacts"
        ).fetchone() == (0,)


def test_prepared_check_refuses_a_root_without_a_lakehouse(tmp_path):
    from kkb_agent import live_check

    report = live_check.run_prepared_check(scripted(), tmp_path / "missing", tmp_path / "work")
    assert report == {"passed": False, "configuration": "prepared_root_missing"}


# --- M6-14 deterministic period table ---------------------------------------------------------


def test_period_table_lays_out_series_values_by_code():
    from kkb_agent.agent.presentation import period_table

    table = period_table(compute(parameters={"series_names": {"credit": "Konut bakiyesi"}}))
    assert table.columns == (
        "Konut bakiyesi",
        "rate",
        "rate month-over-month change",
        "Konut bakiyesi month-over-month change",
    )
    assert len(table.rows) == 6
    assert table.rows[0] == ("2021-01-01..2021-01-31", ("1.000 milyon TL", "10 yüzde", "", ""))
    assert table.rows[1][1] == ("990 milyon TL", "9,5 yüzde", "-0,5 yüzde puan", "-10 milyon TL")
    markdown = table.markdown().splitlines()
    assert markdown[0].startswith("| Dönem | Konut bakiyesi |") and len(markdown) == 8
    # Counts and single-value summaries stay in the prose.
    assert not any("transitions" in column for column in table.columns)


def test_period_table_refuses_non_series_or_ambiguous_results():
    from kkb_agent.agent.presentation import period_table

    assert period_table(compute(end=date(2020, 12, 31))) is None
    result = compute()
    doubled = result.model_copy(update={"values": [*result.values, result.values[0]]})
    assert period_table(doubled) is None
    single = result.model_copy(update={"values": result.values[:2]})
    assert period_table(single) is None


def test_turn_one_answer_carries_the_table_and_writer_is_told_not_to_repeat_it(lake):
    draft = "Faizin düştüğü 4 aylık geçişin 3'ünde konut kredisi bakiyesi artmadı."
    answered, workspace, session = turn_one(lake, draft)
    assert answered.answer.status is AnswerStatus.ACCEPTED
    (table,) = answered.tables
    assert len(table.rows) == 6 and table.columns[0].startswith("BDDK Aylık Bülten")
    writer_rules = session.provider.seen[1][0].content
    assert "the reader sees the full table separately" in writer_rules
    assert "meaningful series name" in writer_rules
    assert "dimensionless displays" in writer_rules and "without that" in writer_rules


def test_no_table_accompanies_an_abstained_answer(lake):
    answered, _, _ = turn_one(lake, "Şubat 2021'de bakiye 987 milyon TL'ye indi.")
    assert answered.answer.status is AnswerStatus.ABSTAINED and answered.tables == ()


def test_prepared_report_uses_bounded_presentation_and_lists_tables(lake, tmp_path):
    from kkb_agent import live_check

    lake.connection.close()
    plan = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "turn1",
                "tool": "change_detection",
                "arguments": json.loads(arguments().model_dump_json(exclude_none=True)),
            }
        ],
    }
    draft = "Faiz 4 geçişte düştü. Bakiye Şubat 2021'de 987 milyon TL oldu."
    report = live_check.run_prepared_check(
        scripted(json.dumps(plan), draft), lake.root, tmp_path / "work", question=QUESTION
    )
    assert report["answer"]["status"] == "accepted"
    assert report["answer"]["withheld_text"] == []
    (table,) = report["tables"]
    assert table["rows"] == 6 and table["first"] == "2021-01-01..2021-01-31"


def test_planner_is_told_where_columns_live_and_to_avoid_redundant_steps(lake):
    from kkb_agent.agent.loop import SYSTEM_PROMPT
    from kkb_agent.tools import make_lakehouse_tool

    description = make_lakehouse_tool(lake.connection).description
    assert "silver_series declaration (series_id, unit, scale" in description
    assert "join silver_series s on series_id" in description
    assert "another planned step already returns" in SYSTEM_PROMPT


def test_writer_reads_a_short_table_whole_and_the_gate_still_sees_everything(lake):
    draft = "Mart 2021'de bakiye 1.010 milyon TL oldu."  # A tabled, non-highlighted month.
    answered, _, session = turn_one(lake, draft)
    writer_prompt = session.provider.seen[1][1].content
    assert "shown to the reader separately for:" in writer_prompt
    assert "period 2021-02-01..2021-02-28" in writer_prompt  # highlighted
    # Six months is short enough to read: the writer is given every month, not only the
    # highlighted ones. Denied the middle, it wrote that the table lacked it (2026-09-21).
    assert "period 2021-03-01..2021-03-31" in writer_prompt
    assert "Every one of its values is listed below." in writer_prompt
    # The direction counts reach the writer under their controlled phrases, which
    # is what lets a later turn name an inherited count instead of a bare number.
    assert "Birinci serinin düştüğü ay sayısı" in writer_prompt
    assert "Birinci seri düşerken ikinci serinin artmadığı ay sayısı" in writer_prompt
    assert "transitions where" not in writer_prompt
    # Narrowing the writer's view does not narrow verification.
    assert answered.answer.status is AnswerStatus.ACCEPTED


def test_the_planner_reads_each_prepared_series_stored_window_beside_its_meaning(lake):
    """Live R2 (2026-09-19): the planner doubted the 2025-based CPI covered 2024."""
    names = prepared_series_names(lake.connection)
    assert prepared_series_coverage(lake.connection)[TOTAL_ID] == "2021-01..2021-06"
    assert "kapsam" not in names[TOTAL_ID]  # display names stay clean
    tool = make_change_detection_tool(lake.connection, lineage=lake.lineage, series_names=names)
    assert f"{TOTAL_ID}: {names[TOTAL_ID]} [2021-01..2021-06]" in tool.description


def _served_like(lake, *responses, **plan_fields):
    """The harness words the co-movement itself; the writer is asked only for its reading."""
    registry = ToolRegistry()
    registry.register(
        make_change_detection_tool(
            lake.connection,
            lineage=lake.lineage,
            series_names=prepared_series_names(lake.connection),
        )
    )
    plan = {
        "question": QUESTION,
        "steps": [
            {
                "step_id": "turn1",
                "tool": "change_detection",
                "arguments": json.loads(arguments().model_dump_json(exclude_none=True)),
            }
        ],
        **plan_fields,
    }
    workspace = Workspace.open(lake.connection)
    session = Session(scripted(json.dumps(plan), *responses), registry, commentary=True)
    answered = session.answer(
        QUESTION, lake.connection, workspace=workspace, remember="konut_kredisi_ve_faiz"
    )
    return answered, workspace, session


def test_the_reading_sits_under_figures_that_name_their_series(lake):
    """The jury: "nedenlerine ilişkin yorum ... katma değer" - over figures a reader can place.

    Handing the whole answer to the writer was built and measured on 2026-09-22 and left
    off: asked for it, the writer spent 1,550 seconds and all 16,384 of its tokens on
    reasoning and returned nothing, while this narrow call succeeded in 91 seconds on the
    same endpoint the same day. So the harness words the figures - and must say which series
    each count is about, which is the half that was missing.
    """
    reading = (
        "Yorum: Faizin düştüğü ayların çoğunda bakiye artmış; bu, kredi talebinin faize "
        "duyarlı olduğunu düşündürüyor ve muhtemelen para politikasıyla ilişkili."
    )
    answered, workspace, session = _served_like(lake, reading)
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert reading in answered.answer.text and answered.answer.text.index("Yorum:") > 0
    named = answered.answer.text.splitlines()[1]
    assert named.startswith("Birinci seri:") and "İkinci seri:" in named
    assert "konut kredisi faiz oranı" in named and "konut kredisi bakiyesi" in named
    asked = session.provider.seen[1]
    assert any("Write ONLY the 'Yorum:' paragraph" in item.content for item in asked)
    assert any(item.content.startswith("written:") for item in asked)
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_a_request_that_asks_for_no_interpretation_gets_none_and_costs_no_writer_call(lake):
    # Live 2026-09-21: "tabloyu bozmadan ... enflasyondan arındırır mısın?" was answered with
    # a 'Yorum:' paragraph restating what had been done, and 58 of the turn's 100 seconds
    # went to writing it. Whether the reader asked how, why or whether is the planner's
    # reading of the question, said in the plan.
    reading = "Yorum: Bu cümle hiç istenmemeli."
    answered, workspace, session = _served_like(lake, reading, interpret=False)
    assert answered.answer.status is AnswerStatus.ACCEPTED
    assert "Yorum:" not in answered.answer.text
    assert len(session.provider.seen) == 1  # the planner call, and no writer call
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_the_harness_wording_says_which_series_each_count_is_about(lake):
    """Where no writer runs, the fixed wording stands - and it must still name the series.

    It leads with a line naming the pair, because "Birinci serinin düştüğü ay sayısı" alone
    tells a reader nothing about which series fell. That line used to be dropped whenever a
    name carried a digit, which every index name does ("... (2023=100)").
    """
    answered, _, _ = _served_like(lake, interpret=False)
    lines = answered.answer.text.splitlines()
    assert lines[0] == "Aylık yön karşılaştırması hesaplandı."
    assert "Birinci seri:" in lines[1] and "İkinci seri:" in lines[1]
    assert "Yorum:" not in answered.answer.text
    assert len(lines) >= 5


def test_without_a_reading_the_verified_figures_stand_as_they_are(lake):
    answered, workspace, _ = _served_like(lake)  # the provider has no reading to give
    assert answered.answer.status is AnswerStatus.ACCEPTED and "Yorum:" not in answered.answer.text
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_a_reading_with_an_invented_figure_loses_that_sentence_and_nothing_else(lake):
    reading = "Yorum: Bakiye 987 milyon TL'ye ulaşmış olabilir. Talep faize duyarlı görünüyor."
    answered, workspace, _ = _served_like(lake, reading)
    assert answered.answer.status is AnswerStatus.QUALIFIED
    assert "987" not in answered.answer.text and "faize duyarlı" in answered.answer.text
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_causality_is_given_the_same_prepared_series_list_as_change_detection(lake):
    # Live 2026-09-21: asked for the housing-loan rate in a causality question the planner
    # wrote EVDS:TP.BKR.TRY.18 - the outstanding-portfolio rate, which no list offered it -
    # and the turn spent nine minutes failing to recover. change_detection carried the
    # list; causality, configured in the same call, carried none.
    from kkb_agent.tools.causality import make_causality_tool

    names = prepared_series_names(lake.connection)
    tool = make_causality_tool(lake.connection, lineage=lake.lineage, series_names=names)
    assert f"{TOTAL_ID}: {names[TOTAL_ID]}" in tool.description
    assert make_causality_tool(lake.connection, lineage=lake.lineage).description.count(":") < 3
