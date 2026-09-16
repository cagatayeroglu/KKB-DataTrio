"""Monthly table comparisons: hand-checked counts and actual execution boundaries."""

import json
from datetime import date

import pytest
from pydantic import ValidationError
from test_add_series import arguments as addition_arguments
from test_add_series import bound_tool, source_of
from test_co_movement import TOTAL_ID
from test_co_movement import lake as lake
from test_turn_two import CPI_ID, MONTHS, credit_column
from test_turn_two import pool as pool

from kkb_agent.agent import (
    AnswerStatus,
    ExecutionContext,
    Session,
    ToolRegistry,
    gate_answer,
    render_results,
)
from kkb_agent.agent.executor import PlanRejected, execute, validate_plan
from kkb_agent.agent.plan import AnalyticalPlan
from kkb_agent.agent.presentation import period_table
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics.table_relationship import TableComparisonRefused, compare_table_directions
from kkb_agent.core import AnalyticalResult, ResultEvidence, ResultKind, ResultStatus, StockFlow
from kkb_agent.llm import scripted
from kkb_agent.tools import make_change_detection_tool
from kkb_agent.tools.change_detection import ChangeDetectionArguments


def table(prices=(100, 105, 103, 108, 110, 110), rates=(8, 7, 7, 6, 5, 6)):
    return AnalyticalResult(
        result_id="fixture:monthly-table",
        kind=ResultKind.COMPARISON,
        status=ResultStatus.COMPUTED,
        tool="change_detection",
        method="synthetic",
        evidence=ResultEvidence(input_refs=["synthetic fixture"]),
        values=[
            *credit_column([10, 9, 10, 10, 8, 9]),
            *credit_column(prices, label="price", unit="index", measure=StockFlow.INDEX),
            *credit_column(rates, label="rate", unit="percent", measure=StockFlow.RATE),
        ],
    )


def compare(source=None, **changes):
    return compare_table_directions(
        table() if source is None else source,
        **{
            "driver_column": "price",
            "target_column": "credit",
            "driver_direction": "up",
            "target_direction": "non_increasing",
            "when_column": "rate",
            "when_direction": "down",
            **changes,
        },
    )


def counts(result):
    return [v.value for v in result.values if v.label.startswith("table comparison ")]


def test_conditions_counts_and_preserved_values_match_hand_calculation():
    source = table()
    result = compare(source)
    assert result.values[: len(source.values)] == source.values
    assert period_table(result) == period_table(source)
    assert counts(result) == [5, 0, 3, 3, 3, 3]
    record = result.evidence.transformations[-1]
    assert record.parameters["joint_periods"] == ["2021-02-28", "2021-04-30", "2021-05-31"]
    assert any("other factors are not controlled" in item for item in result.limitations)
    assert counts(
        compare(when_direction="unchanged", driver_direction="down", target_direction="up")
    ) == [5, 0, 1, 1, 1, 1]
    assert counts(compare(when_column=None, when_direction=None)) == [5, 0, 5, 3, 3, 3]


def test_zero_eligible_periods_is_explicit_without_a_percentage():
    assert counts(compare(table(rates=[8] * 6))) == [5, 0, 0, 0, 0, 0]


def test_missing_month_does_not_bridge_the_gap_or_change_the_denominator_silently():
    source = table()
    source = source.model_copy(
        update={
            "values": [
                v for v in source.values if not (v.label == "price" and v.period.end == MONTHS[2])
            ]
        }
    )
    result = compare(source)
    assert counts(result) == [3, 2, 2, 2, 2, 2]
    assert result.warnings
    assert result.values[: len(source.values)] == source.values


@pytest.mark.parametrize(
    "case",
    [
        "unknown_label",
        "same_column",
        "half_condition",
        "duplicate",
        "invalid_date",
        "nan",
        "mixed_unit",
        "flow",
        "unknown_semantics",
        "no_pair",
        "not_computed",
    ],
)
def test_invalid_comparisons_refuse_instead_of_guessing(case):
    source = table()
    kwargs = {}
    if case == "unknown_label":
        kwargs["driver_column"] = "unavailable"
    elif case == "same_column":
        kwargs["driver_column"] = "credit"
    elif case == "half_condition":
        kwargs["when_direction"] = None
    elif case == "duplicate":
        source = source.model_copy(update={"values": [*source.values, source.values[0]]})
    elif case == "unknown_semantics":
        source = source.model_copy(update={"unresolved_semantics": ["unreviewed unit"]})
    elif case == "no_pair":
        source = source.model_copy(
            update={"values": [v for v in source.values if v.period.end.month in (1, 3, 5)]}
        )
    elif case == "not_computed":
        source = source.model_copy(update={"status": ResultStatus.ABSTAINED})
    else:
        value = source.values[0]
        updates = {
            "invalid_date": {"period": value.period.model_copy(update={"start": date(2021, 1, 2)})},
            "nan": {"value": float("nan")},
            "mixed_unit": {"unit": "USD"},
            "flow": {"measure": StockFlow.FLOW},
        }[case]
        source = source.model_copy(
            update={"values": [value.model_copy(update=updates), *source.values[1:]]}
        )
    with pytest.raises(TableComparisonRefused):
        compare(source, **kwargs)


def test_repeat_comparison_refuses_duplicate_counts_but_new_criteria_are_distinct():
    first = compare()
    with pytest.raises(TableComparisonRefused, match="already present"):
        compare(first)
    second = compare(first, target_direction="up")
    assert second.values[: len(first.values)] == first.values
    assert len({v.label for v in second.values if v.label.startswith("table comparison ")}) == 12


def args(**changes):
    return {
        "operation": "table_co_movement",
        "input_step": "add",
        "driver_column": CPI_ID,
        "target_column": TOTAL_ID,
        "driver_direction": "up",
        "target_direction": "non_increasing",
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "published"},
        {"input_step": None},
        {"input_step": "../table"},
        {"when_column": "rate"},
        {"when_direction": "up"},
        {"sql": "SELECT 1"},
        {"driver_direction": "probably"},
        {"driver_column": TOTAL_ID},
    ],
)
def test_closed_schema_rejects_invalid_references_conditions_and_extra_actions(changes):
    with pytest.raises(ValidationError):
        ChangeDetectionArguments.model_validate(args(**changes))


def registry_for(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    registry.register(
        make_change_detection_tool(
            lake.connection,
            workspace=workspace,
            lineage=lake.lineage,
        )
    )
    return registry


def plan(**changes):
    return AnalyticalPlan.model_validate(
        {
            "question": "Mevcut tabloyu koru, endeks yükselirken kredi bakiyesini karşılaştır.",
            "steps": [
                {
                    "step_id": "comparison",
                    "tool": "change_detection",
                    "arguments": args(),
                    "depends_on": ["add"],
                    **changes,
                },
                {
                    "step_id": "add",
                    "tool": "table_transform",
                    "arguments": addition_arguments().model_dump(mode="json"),
                },
            ],
        }
    )


def test_typed_dependency_orders_tools_and_computed_output_is_verified(pool):
    registry = registry_for(pool)
    validated = validate_plan(plan(), registry)
    assert [v.step.step_id for v in validated.steps] == ["add", "comparison"]
    outcome = execute(validated, registry)
    assert outcome.completed
    final = outcome.results[-1].output
    assert result_faults({"final": final}, pool[0].connection) == {}
    assert final.values[: len(source_of(pool).values)] == source_of(pool).values
    assert counts(final) == [5, 0, 5, 2, 3, 1]


@pytest.mark.parametrize("written", ["1 ay", "1,0 ay"])
def test_turn_three_supported_count_and_safe_decimal_format_bind(pool, written):
    """The oracle-derived joint count is an exposed result value, not a row recount."""
    outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
    final = outcome.results[-1].output

    gated = gate_answer(
        f"Koşul altında iki yönü birlikte karşılayan dönem sayısı {written}.",
        {"comparison": final},
        pool[0].connection,
    )

    assert counts(final)[-1] == 1
    assert gated.status is AnswerStatus.ACCEPTED
    assert gated.verdict.numbers[-1].value_label.endswith(
        "eligible transitions matching both directions"
    )
    context = render_results({"comparison": final})
    assert "Koşul altında iki yönü birlikte karşılayan dönem sayısı: display 1" in context


@pytest.mark.parametrize(
    "draft",
    [
        "Koşul altındaki dönemlerin oranı %17 oldu.",
        "Tabloda 6 aylık gözlem vardır.",
        "Koşul altında iki yönü birlikte karşılayan 19 ay vardır.",
        "Koşul altında hedef yönünü karşılayan dönem sayısı 1 ay.",
        "Mart 2021 döneminde price 105 endeks oldu.",
    ],
)
def test_turn_three_derived_fabricated_or_misattributed_numbers_stay_rejected(pool, draft):
    outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
    final = outcome.results[-1].output

    gated = gate_answer(draft, {"comparison": final}, pool[0].connection)

    assert gated.status is AnswerStatus.ABSTAINED
    assert gated.omitted


def test_turn_three_supported_claim_does_not_rescue_fabricated_extra_number(pool):
    outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
    final = outcome.results[-1].output
    supported = "Koşul altında iki yönü birlikte karşılayan dönem sayısı 1 ay."

    gated = gate_answer(
        supported + " Ayrıca desteklenmeyen 19 dönem vardır.",
        {"comparison": final},
        pool[0].connection,
    )

    assert gated.status is AnswerStatus.QUALIFIED
    assert gated.text == supported
    assert gated.omitted[0].text == "Ayrıca desteklenmeyen 19 dönem vardır."


@pytest.mark.parametrize(
    ("repaired", "accepted"),
    [
        ("Koşul altında iki yönü birlikte karşılayan dönem sayısı 1 ay.", True),
        ("Koşul altında iki yönü birlikte karşılayan dönem sayısı 19 ay.", False),
    ],
)
def test_turn_three_numeric_rewrite_reverifies_before_publication(pool, repaired, accepted):
    lake, workspace = pool
    source = source_of(pool)
    before = source.digest()
    provider = scripted(
        plan().model_dump_json(),
        "Birlikte karşılanan geçiş sayısı 1 ay.",
        repaired,
    )

    answered = Session(provider, registry_for(pool), repair_unmatched_numbers=True).answer(
        plan().question,
        lake.connection,
        workspace=workspace,
        remember="comparison",
    )

    assert len(provider.seen) == 3
    assert provider.seen[1][1].content == provider.seen[2][1].content
    assert "Birlikte karşılanan geçiş sayısı" not in provider.seen[2][0].content
    assert workspace.value_of("konut_kredisi_ve_faiz").digest() == before
    assert answered.answer.status is (AnswerStatus.ACCEPTED if accepted else AnswerStatus.ABSTAINED)
    assert ("comparison" in workspace.names()) is accepted


@pytest.mark.parametrize(
    "change",
    [
        {"depends_on": []},
        {"arguments": args(input_step="missing"), "depends_on": ["missing"]},
        {"arguments": args(input_step="comparison"), "depends_on": ["comparison"]},
    ],
)
def test_undeclared_unknown_or_self_input_never_reaches_execution(pool, change):
    with pytest.raises(PlanRejected):
        validate_plan(plan(**change), registry_for(pool))


@pytest.mark.parametrize("bad_output", [None, {"table": "pretend"}, table()])
def test_missing_wrong_type_and_unproved_inputs_are_rejected(pool, bad_output):
    tool = registry_for(pool).get("change_detection")
    result = tool.run(tool.parse(args()), ExecutionContext("compare", {"add": bad_output}))
    assert result.error_category == "table_reference"


def test_workspace_reference_and_rechecking_mutation(pool):
    tool = registry_for(pool).get("change_detection")
    arguments = args(
        input_step=None,
        source="konut_kredisi_ve_faiz",
        driver_column="EVDS:TP.KTF12 monthly average (by_end)",
        driver_direction="down",
    )
    result = tool.run(tool.parse(arguments), ExecutionContext("compare")).output
    assert counts(result) == [5, 0, 5, 4, 3, 3]
    assert result_faults({"final": result}, pool[0].connection) == {}
    forged = source_of(pool).model_copy(update={"values": []})
    assert tool.run(tool.parse(args()), ExecutionContext("compare", {"add": forged})).error_category


def test_composed_session_publishes_one_preserved_table_and_bound_numeric_claim(pool):
    registry = registry_for(pool)
    proposed = plan()
    provider = scripted(
        proposed.model_dump_json(), "Hazırlanan tabloda Şubat 2021 bakiyesi 990 milyon TL."
    )
    before = source_of(pool).digest()
    answered = Session(provider, registry).answer(
        proposed.question,
        pool[0].connection,
        workspace=pool[1],
        remember="comparison",
    )
    assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer
    assert "comparison" in pool[1].names()
    assert source_of(pool).digest() == before
    assert len(answered.tables) == 1
    assert len(answered.tables[0].columns) == 5
    writer_context = provider.seen[-1][1].content
    assert "driver column" in writer_context and CPI_ID in writer_context
    assert "[konut_kredisi_ve_faiz]" not in writer_context


def test_legacy_change_arguments_stay_flat():
    payload = {
        "operation": "compare",
        "series_id": "example",
        "start": "2021-01-31",
        "end": "2021-02-28",
    }
    parsed = ChangeDetectionArguments.model_validate(payload)
    assert json.loads(parsed.model_dump_json(exclude_unset=True)) == payload


REAL_LABEL = "credit real, 2023-06 prices (CPI)"


def table_with_real(real_values=(10, 11, 12, 13, 14, 15)):
    """The Turn 2 shape: a nominal credit column beside its deflated counterpart."""
    source = table()
    return source.model_copy(
        update={
            "values": [
                *source.values,
                *credit_column(real_values, label=REAL_LABEL),
            ]
        }
    )


class TestNominalAndRealAreNotInterchangeable:
    """M11-11: the 2026-09-16 Turn 3 compared the nominal column and said 4.

    The table it was given also carried the deflated column built one turn
    earlier, and the same comparison against that column is a different count.
    Choosing between them is the planner's, but which one was used must not be
    invisible in the result an answer is written from.
    """

    def test_the_nominal_choice_is_recorded_when_a_real_column_exists(self):
        result = compare(table_with_real(), target_column="credit")

        assert any(
            "compared in nominal terms" in item and REAL_LABEL in item
            for item in result.limitations
        )

    def test_using_the_real_column_carries_no_such_note(self):
        result = compare(table_with_real(), target_column=REAL_LABEL)

        assert not any("compared in nominal terms" in item for item in result.limitations)

    def test_a_table_without_a_real_column_carries_no_such_note(self):
        result = compare(target_column="credit")

        assert not any("compared in nominal terms" in item for item in result.limitations)

    def test_the_note_names_every_nominal_column_the_comparison_used(self):
        source = table_with_real().model_copy()
        source = source.model_copy(
            update={
                "values": [
                    *source.values,
                    *credit_column(
                        (1, 2, 3, 4, 5, 6),
                        label="rate real, 2023-06 prices (CPI)",
                        unit="percent",
                        measure=StockFlow.RATE,
                    ),
                ]
            }
        )
        result = compare(source, target_column="credit", when_column="rate")

        notes = [item for item in result.limitations if "compared in nominal terms" in item]
        assert len(notes) == 2

    def test_the_two_columns_really_do_give_different_counts(self):
        # Without this the note would be a warning about nothing.
        source = table_with_real()
        nominal = counts(compare(source, target_column="credit"))
        real = counts(compare(source, target_column=REAL_LABEL))

        assert nominal != real

    def test_the_note_does_not_disturb_the_counts_or_the_preserved_table(self):
        plain = compare(table(), target_column="credit")
        with_real = compare(table_with_real(), target_column="credit")

        assert counts(plain) == counts(with_real)
        assert [v.label for v in table().values] == [
            v.label for v in with_real.values if not v.label.startswith("table comparison ")
        ][: len(table().values)]
