"""Monthly table comparisons: hand-checked counts and actual execution boundaries."""

import json
from calendar import monthrange
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
from kkb_agent.agent.claim_qualifiers import comovement_count_meaning, controlled_count_label
from kkb_agent.agent.executor import PlanRejected, execute, validate_plan
from kkb_agent.agent.loop import NUMERIC_REPAIR_INSTRUCTIONS, SYNTHESIS_PROMPT
from kkb_agent.agent.plan import AnalyticalPlan
from kkb_agent.agent.presentation import period_table
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics.table_relationship import TableComparisonRefused, compare_table_directions
from kkb_agent.core import (
    DIMENSIONLESS,
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
from kkb_agent.llm import scripted
from kkb_agent.tools import make_change_detection_tool
from kkb_agent.tools.change_detection import ChangeDetectionArguments
from kkb_agent.tools.table_relationship import (
    TableRelationshipArguments,
    _continued_condition,
    _deflated_columns,
)


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


def test_an_unrelated_unresolved_column_does_not_block_the_comparison():
    source = table()
    unknown = credit_column([1, 2, 3, 4, 5, 6], label="note", unit=None)
    source = source.model_copy(
        update={
            "values": [
                *source.values,
                *[v.model_copy(update={"scale": Scale.UNKNOWN}) for v in unknown],
            ],
            "unresolved_semantics": ["note: unit and scale are not stated"],
        }
    )
    result = compare(source)
    assert counts(result) == [5, 0, 3, 3, 3, 3]
    assert result.unresolved_semantics == ["note: unit and scale are not stated"]


def undeclared(levels, *, unit="TRY", scale=Scale.THOUSAND):
    """A document column: stated unit (or none), no stated stock/flow meaning."""
    return [
        v.model_copy(update={"unit": unit, "scale": scale, "measure": StockFlow.UNKNOWN})
        for v in credit_column(list(levels), label="sales")
    ]


def with_sales(levels, **kwargs):
    source = table()
    column = undeclared(levels, **kwargs)
    unresolved = (
        ["sales: unit and scale are not stated"] if kwargs.get("unit", "TRY") is None else []
    )
    return source.model_copy(
        update={"values": [*source.values, *column], "unresolved_semantics": unresolved}
    )


def test_an_undeclared_column_whose_values_fall_in_year_is_compared_as_a_level():
    result = compare(with_sales([5, 7, 6, 8, 9, 4]), target_column="sales")
    assert counts(result)[0] == 5
    assert any("inferred from the values" in note for note in result.limitations)


def test_an_undeclared_unitless_column_is_compared_with_both_decisions_recorded():
    source = with_sales([5, 7, 6, 8, 9, 4], unit=None, scale=Scale.UNKNOWN)
    result = compare(source, target_column="sales")
    assert any("no stated unit or scale" in note for note in result.limitations)
    assert result.unresolved_semantics == ["sales: unit and scale are not stated"]


@pytest.mark.parametrize("levels", [[1, 2, 3, 4, 5, 6], [1, 1, 2, 3, 3, 4]])
def test_an_undeclared_column_that_could_be_cumulative_asks_instead_of_guessing(levels):
    with pytest.raises(TableComparisonRefused, match="cumulative"):
        compare_table_directions(
            with_sales(levels),
            driver_column="price",
            target_column="sales",
            driver_direction="up",
            target_direction="up",
        )


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

    answered = Session(
        provider,
        registry_for(pool),
        repair_unmatched_numbers=True,
        deterministic_presentation=False,
    ).answer(
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
    answered = Session(provider, registry, deterministic_presentation=False).answer(
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


SUPPORTED_COUNT = "Koşul altında iki yönü birlikte karşılayan dönem sayısı 1 ay."
#: An index base is not one of the series' values; the gate rejects it as an
#: ambiguous binding, which is the numeric-rewrite category.
NUMERIC_ONLY_DRAFT = "Endeks tabanı 100 olarak alınmıştır."
#: The same base written beside a supported count fails period attribution
#: instead, which is the other rewrite category.
PERIOD_ONLY_DRAFT = "Endeks 2023=100 tabanlıdır ve birlikte karşılanan dönem sayısı 1 ay."


def repair_session(pool, *drafts, **flags):
    lake, workspace = pool
    provider = scripted(plan().model_dump_json(), *drafts)
    session = Session(
        provider,
        registry_for(pool),
        repair_unmatched_numbers=True,
        repair_period_wording=True,
        deterministic_presentation=False,
        **flags,
    )
    answered = session.answer(
        plan().question, lake.connection, workspace=workspace, remember="comparison"
    )
    return provider, workspace, answered


class TestOneRewritePerWordingProblem:
    """M11-11: a repaired draft may fail a different rule, and did, live.

    Three bounded runs on 2026-09-16 showed Turn 2 publishing exactly when its
    first failure was period attribution. When the first failure was a numeric
    binding instead, the single repair was spent there and the period fault the
    replacement introduced had none left, so a fully verified table went
    unpublished. Each category may now be rewritten once, and only once.
    """

    def test_a_second_problem_in_a_repaired_draft_gets_its_own_rewrite(self, pool):
        provider, workspace, answered = repair_session(
            pool, NUMERIC_ONLY_DRAFT, PERIOD_ONLY_DRAFT, SUPPORTED_COUNT
        )

        assert len(provider.seen) == 4
        assert answered.answer.status is AnswerStatus.ACCEPTED
        assert "comparison" in workspace.names()

    def test_the_same_problem_is_never_rewritten_twice(self, pool):
        provider, workspace, answered = repair_session(
            pool, NUMERIC_ONLY_DRAFT, NUMERIC_ONLY_DRAFT, SUPPORTED_COUNT
        )

        # Plan, draft, one numeric rewrite. The repeated numeric fault stops there.
        assert len(provider.seen) == 3
        assert answered.answer.status is not AnswerStatus.ACCEPTED
        assert "comparison" not in workspace.names()

    def test_two_rewrites_are_the_ceiling(self, pool):
        provider, workspace, answered = repair_session(
            pool, NUMERIC_ONLY_DRAFT, PERIOD_ONLY_DRAFT, NUMERIC_ONLY_DRAFT, SUPPORTED_COUNT
        )

        assert len(provider.seen) == 4
        assert answered.answer.status is not AnswerStatus.ACCEPTED
        assert "comparison" not in workspace.names()

    def test_every_rewrite_reuses_the_same_immutable_candidate(self, pool):
        before = source_of(pool).digest()
        provider, workspace, _ = repair_session(
            pool, NUMERIC_ONLY_DRAFT, PERIOD_ONLY_DRAFT, SUPPORTED_COUNT
        )

        results = [seen[1].content for seen in provider.seen[1:]]
        assert results[0] == results[1] == results[2]
        assert workspace.value_of("konut_kredisi_ve_faiz").digest() == before

    def test_a_rewrite_that_stays_unsupported_still_does_not_publish(self, pool):
        provider, workspace, answered = repair_session(
            pool,
            NUMERIC_ONLY_DRAFT,
            PERIOD_ONLY_DRAFT,
            "Koşul altında iki yönü birlikte karşılayan dönem sayısı 19 ay.",
        )

        assert len(provider.seen) == 4
        assert answered.answer.status is not AnswerStatus.ACCEPTED
        assert "comparison" not in workspace.names()

    def test_a_disabled_category_is_not_rewritten_at_all(self, pool):
        lake, workspace = pool
        provider = scripted(
            plan().model_dump_json(), NUMERIC_ONLY_DRAFT, PERIOD_ONLY_DRAFT, SUPPORTED_COUNT
        )
        Session(
            provider,
            registry_for(pool),
            repair_unmatched_numbers=True,
            deterministic_presentation=False,
        ).answer(plan().question, lake.connection, workspace=workspace, remember="comparison")

        # Numeric rewrite runs; the period fault it leaves has no enabled repair.
        assert len(provider.seen) == 3
        assert "comparison" not in workspace.names()


INHERITED_LABEL = "transitions where rate fell and credit did not rise"
INHERITED_PHRASE = "Sürücü düşerken hedefin artmadığı geçiş sayısı"
JOINT_PHRASE = "Koşul altında iki yönü birlikte karşılayan dönem sayısı"


def with_inherited_count(value):
    """A comparison whose source already carries an equal co-movement count.

    This is the live Turn 3 shape: the table built in Turn 1 contributes its own
    direction counts, and the new comparison publishes counts of its own.
    """
    source = table()
    inherited = credit_column()[0].model_copy(
        update={
            "label": INHERITED_LABEL,
            "value": value,
            "unit": DIMENSIONLESS,
            "scale": Scale.ONE,
            "measure": StockFlow.UNKNOWN,
        }
    )
    return compare(
        source.model_copy(update={"values": [*source.values, inherited]}),
        target_column="credit",
    )


class TestAnInheritedCountCanStillBeNamed:
    """M11-11: the count a later comparison inherits needs wording of its own.

    Measured twice live on 2026-09-16: Turn 3 withheld its sentence because the
    literals 4 and 32 each matched an inherited co-movement count and one or
    more new comparison counts, and the inherited one had no controlled phrase
    to name it with, so no wording could bind it.
    """

    def test_the_inherited_count_now_has_a_controlled_phrase(self):
        result = with_inherited_count(3.0)
        inherited = next(v for v in result.values if v.label == INHERITED_LABEL)

        assert controlled_count_label(result, inherited) == INHERITED_PHRASE

    def test_it_differs_from_the_new_comparison_phrase_at_the_same_value(self):
        result = with_inherited_count(3.0)
        equal = [v for v in result.values if v.value == 3.0 and v.unit == DIMENSIONLESS]
        phrases = {controlled_count_label(result, v) for v in equal}

        assert len(equal) > 1
        assert INHERITED_PHRASE in phrases and JOINT_PHRASE in phrases
        assert len(phrases) == len(equal)

    def test_the_writer_is_shown_the_phrase_rather_than_the_raw_label(self):
        context = render_results({"comparison": with_inherited_count(3.0)})

        assert f"{INHERITED_PHRASE}: display 3" in context
        assert INHERITED_LABEL not in context

    @pytest.mark.parametrize(
        ("label", "meaning"),
        [
            ("consecutive monthly transitions compared", "transitions"),
            ("transitions where rate fell", "driver_fell"),
            ("transitions where rate fell and credit rose", "target_rose"),
            ("transitions where rate fell and credit did not rise", "target_did_not_rise"),
            ("credit real, 2023-06 prices (CPI)", None),
            ("table comparison abc: complete monthly transitions", None),
        ],
    )
    def test_each_co_movement_shape_is_classified_and_nothing_else_is(self, label, meaning):
        assert comovement_count_meaning(label) is meaning

    def test_naming_the_inherited_count_binds_it(self, pool):
        outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
        final = outcome.results[-1].output
        inherited = next(
            (v for v in final.values if comovement_count_meaning(v.label) is not None), None
        )
        assert inherited is not None

        gated = gate_answer(
            f"{controlled_count_label(final, inherited)} {inherited.value:.0f} ay.",
            {"comparison": final},
            pool[0].connection,
        )

        assert gated.status is AnswerStatus.ACCEPTED

    def test_the_inherited_phrase_may_not_claim_a_different_count(self, pool):
        outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
        final = outcome.results[-1].output

        # The joint count is 1; naming it with the inherited count's wording must fail.
        gated = gate_answer(f"{INHERITED_PHRASE} 1 ay.", {"comparison": final}, pool[0].connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert any("co-movement count wording" in r for item in gated.omitted for r in item.reasons)

    def test_a_bare_number_matching_several_counts_is_still_ambiguous(self, pool):
        outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
        final = outcome.results[-1].output

        gated = gate_answer("Sonuç 1 aydır.", {"comparison": final}, pool[0].connection)

        assert gated.status is AnswerStatus.ABSTAINED


class TestTheCountContractIsFollowable:
    """M11-11: the writer is now told to name a count; that must be enough.

    Three live runs withheld Turn 3 on bare counts. Telling the writer to copy
    the listed phrase only helps if writing exactly that always binds, so this
    checks the instruction against every count a Turn 3 table carries rather
    than asserting the wording of the prompt.
    """

    def final(self, pool):
        outcome = execute(validate_plan(plan(), registry_for(pool)), registry_for(pool))
        return outcome.results[-1].output

    def listed_counts(self, result):
        return [
            (controlled_count_label(result, value), value.value)
            for value in result.values
            if value.unit == DIMENSIONLESS
        ]

    def test_every_count_in_the_table_has_a_phrase_to_write(self, pool):
        listed = self.listed_counts(self.final(pool))

        # Four inherited co-movement counts plus six comparison counts.
        assert len(listed) == 10
        assert all(phrase for phrase, _ in listed)
        assert len({phrase for phrase, _ in listed}) == 10

    def test_writing_a_count_as_instructed_binds_every_time(self, pool):
        final = self.final(pool)

        for phrase, value in self.listed_counts(final):
            gated = gate_answer(
                f"{phrase} {value:.0f} ay.", {"comparison": final}, pool[0].connection
            )
            assert gated.status is AnswerStatus.ACCEPTED, phrase

    def test_the_same_count_without_its_phrase_does_not_bind(self, pool):
        final = self.final(pool)
        collisions = [
            (phrase, value)
            for phrase, value in self.listed_counts(final)
            if [v for _, v in self.listed_counts(final)].count(value) > 1
        ]
        assert collisions, "the fixture must contain at least one shared count value"

        phrase, value = collisions[0]
        named = gate_answer(f"{phrase} {value:.0f} ay.", {"comparison": final}, pool[0].connection)
        bare = gate_answer(f"Sonuç {value:.0f} aydır.", {"comparison": final}, pool[0].connection)

        assert named.status is AnswerStatus.ACCEPTED
        assert bare.status is not AnswerStatus.ACCEPTED

    def test_both_writer_contracts_carry_the_rule(self):
        # The supported phrase/count behavior is exercised above; do not pin
        # this prompt to the older negative wording of the same instruction.
        assert all(word in SYNTHESIS_PROMPT.lower() for word in ("count", "listed", "role phrase"))
        assert "copy its listed phrase with the number" in NUMERIC_REPAIR_INSTRUCTIONS


class TestTheDeflatedColumnIsWhatAChangeQuestionCompares:
    """M11-11: a real column exists only because a turn was asked to deflate.

    Measured on 2026-09-16: Turn 3 compared the nominal credit column and
    published 4 joint months while the oracle's answer, over the deflated column
    the previous turn had just built, is 22. The columns were the planner's to
    pick and it kept picking nominal, so the tool now prefers the deflated
    counterpart and a plan that wants nominal terms says so.
    """

    def test_a_nominal_target_is_replaced_and_the_move_is_recorded(self):
        source = table_with_real()
        arguments = TableRelationshipArguments(
            operation="table_co_movement",
            input_step="earlier",
            driver_column="price",
            target_column="credit",
            driver_direction="up",
            target_direction="non_increasing",
        )
        columns = _deflated_columns(source, arguments)

        assert columns.target == REAL_LABEL
        assert columns.moved == {"target_column": "credit"}
        assert columns.driver == "price"

    def test_the_plan_cannot_decline_the_deflated_column(self):
        # A planner-facing opt-out was tried and the planner set it on a question
        # that never asked for nominal terms, so the schema no longer offers one.
        with pytest.raises(ValidationError):
            TableRelationshipArguments(
                operation="table_co_movement",
                input_step="earlier",
                driver_column="price",
                target_column="credit",
                driver_direction="up",
                target_direction="non_increasing",
                use_nominal=True,
            )

    def test_a_nominal_reading_is_reached_by_comparing_a_table_without_one(self):
        # The table from before the deflation turn carries no real counterpart,
        # so comparing it is how a nominal question is answered.
        arguments = TableRelationshipArguments(
            operation="table_co_movement",
            input_step="earlier",
            driver_column="price",
            target_column="credit",
            driver_direction="up",
            target_direction="non_increasing",
        )
        columns = _deflated_columns(table(), arguments)

        assert (columns.target, columns.moved) == ("credit", {})

    def test_a_table_without_a_real_column_is_untouched(self):
        arguments = TableRelationshipArguments(
            operation="table_co_movement",
            input_step="earlier",
            driver_column="price",
            target_column="credit",
            driver_direction="up",
            target_direction="non_increasing",
        )
        columns = _deflated_columns(table(), arguments)

        assert (columns.driver, columns.target, columns.moved) == ("price", "credit", {})

    def test_a_plan_already_comparing_the_pair_is_not_collapsed(self):
        # Nominal against its own real counterpart: substituting would make the
        # two columns identical and refuse the comparison outright.
        source = table_with_real()
        arguments = TableRelationshipArguments(
            operation="table_co_movement",
            input_step="earlier",
            driver_column="credit",
            target_column=REAL_LABEL,
            driver_direction="up",
            target_direction="non_increasing",
        )
        columns = _deflated_columns(source, arguments)

        assert columns.driver == "credit" and columns.target == REAL_LABEL
        assert columns.moved == {}

    def test_the_two_readings_really_do_differ(self):
        source = table_with_real()
        nominal = counts(compare(source, target_column="credit"))
        real = counts(compare(source, target_column=REAL_LABEL))

        assert nominal != real


def test_explanatory_continuation_keeps_distinct_joint_and_unconditional_counts():
    """A synthetic 60-month table separates 46 real non-rises from 22 joint months."""
    values = []
    nominal = real = rate = price = 100.0
    for index in range(60):
        year, month = 2021 + index // 12, index % 12 + 1
        period = Period(
            start=date(year, month, 1),
            end=date(year, month, monthrange(year, month)[1]),
            frequency=Frequency.MONTHLY,
        )
        if index:
            nominal += 1
            real += -1 if index <= 46 else 1
            rate += -1 if index <= 22 or 47 <= index <= 56 else 1
            price += 1
        for label, value, unit, measure in (
            ("credit", nominal, "TRY", StockFlow.STOCK),
            (REAL_LABEL, real, "TRY", StockFlow.STOCK),
            ("rate", rate, "percent", StockFlow.RATE),
            ("price", price, "index", StockFlow.INDEX),
        ):
            values.append(
                ResultValue(
                    label=label,
                    value=value,
                    unit=unit,
                    scale=Scale.ONE,
                    measure=measure,
                    period=period,
                )
            )
    source = AnalyticalResult(
        result_id="synthetic:continued-table",
        kind=ResultKind.COMPARISON,
        status=ResultStatus.COMPUTED,
        tool="change_detection",
        method="synthetic",
        values=values,
        parameters={
            "series_names": {
                "credit": "Konut kredisi bakiyesi",
                "rate": "Konut kredisi faiz oranı",
                "price": "Konut fiyat endeksi",
            },
            "direction_comparison": {
                "driver_column": "rate",
                "driver_direction": "down",
                "target_column": "credit",
                "target_direction": "non_increasing",
            },
        },
        evidence=ResultEvidence(input_refs=["synthetic fixture"]),
    )
    arguments = TableRelationshipArguments(
        operation="table_co_movement",
        input_step="add",
        driver_column="price",
        target_column="credit",
        driver_direction="up",
        target_direction="non_increasing",
    )
    independent = compare_table_directions(
        source,
        driver_column="price",
        target_column=REAL_LABEL,
        driver_direction="up",
        target_direction="non_increasing",
    )
    condition = _continued_condition(
        source, arguments, "When rates fell, could price growth explain why credit did not rise?"
    )
    assert condition == ("rate", "down")
    assert _continued_condition(
        source,
        arguments,
        "Tabloyu hiç bozmadan konut fiyat endeksini yeni bir sütun olarak ekle. "
        "Fiyat artışları kredinin artmamasını açıklıyor olabilir mi?",
    ) == ("rate", "down")
    continued = compare_table_directions(
        source,
        driver_column="price",
        target_column=REAL_LABEL,
        driver_direction="up",
        target_direction="non_increasing",
        when_column=condition[0],
        when_direction=condition[1],
    )
    assert counts(independent)[-1] == 46
    assert counts(continued)[-1] == 22
    assert counts(continued)[-2] == 22
    assert continued.values[: len(source.values)] == source.values
    swapped = arguments.model_copy(
        update={
            "driver_column": "credit",
            "target_column": "price",
            "driver_direction": "non_increasing",
            "target_direction": "up",
        }
    )
    assert _continued_condition(
        source, swapped, "When rates fell, could price growth explain why credit did not rise?"
    ) == ("rate", "down")
    assert _continued_condition(source, arguments, "Could price growth explain credit? ") is None
    assert (
        _continued_condition(source, arguments, "Could price growth explain why credit rose?")
        is None
    )
    assert (
        _continued_condition(
            source, arguments, "When rates rose, could price explain why credit did not rise?"
        )
        is None
    )
    assert (
        _continued_condition(
            source, arguments, "When rates did not fall, could price explain credit?"
        )
        is None
    )
    assert (
        _continued_condition(source, arguments, "Compare price with credit independently.") is None
    )
    assert _continued_condition(source, arguments, "Could price growth explain deposits?") is None
    unrelated = arguments.model_copy(update={"target_direction": "up"})
    assert (
        _continued_condition(source, unrelated, "Could price growth explain credit growth?") is None
    )
    nominal_only = source.model_copy(
        update={"values": [value for value in source.values if value.label != REAL_LABEL]}
    )
    assert _deflated_columns(nominal_only, arguments).target == "credit"


def test_a_same_plan_step_named_as_source_is_read_like_input_step(pool):
    """Live E1c (2026-09-19): the second co-movement count named the first step as source."""
    tool = registry_for(pool).get("change_detection")
    earlier = pool[1].value_of("konut_kredisi_ve_faiz")
    arguments = args(
        input_step=None,
        source="first_count",
        driver_column="EVDS:TP.KTF12 monthly average (by_end)",
        driver_direction="down",
    )
    result = tool.run(tool.parse(arguments), ExecutionContext("compare", {"first_count": earlier}))
    assert result.error_category is None, result.warnings
    assert counts(result.output) == [5, 0, 5, 4, 3, 3]
    missing = tool.run(tool.parse(arguments), ExecutionContext("compare"))
    assert missing.error_category == "table_reference"
