"""M6-22: the `change_detection` tool, and the planner's route to it.

The analytics were already correct. What this adds is that the agent can
*ask* for them, which means the interesting cases are the boundary ones: an
argument schema that refuses what the tool cannot do, an unknown series that
fails rather than guesses, and a refusal that reaches the model as a warning
instead of being mistaken for a number.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import (
    AnswerStatus,
    ArgumentsRejected,
    ExecutionContext,
    RegistryError,
    Session,
    ToolRegistry,
    ToolSpec,
    ToolStatus,
    validate_plan,
)
from kkb_agent.agent.plan import AnalyticalPlan
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    ResultKind,
    ResultStatus,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm.doubles import scripted
from kkb_agent.tools import (
    ChangeDetectionArguments,
    SeriesUnknown,
    make_change_detection_tool,
    read_series,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)
APRIL, MAY, JUNE = date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30)
KONUT = {APRIL: 767314.0, MAY: 782918.0, JUNE: 801438.0}
FAIZ = {APRIL: 40.0, MAY: 43.2, JUNE: 46.75}

STOCK = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 801438}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        for series_id, semantics, published in (
            ("bddk:konut", STOCK, KONUT),
            ("evds:TP.KTF12", RATE, FAIZ),
        ):
            lake.register_series(
                series_id,
                title=series_id,
                semantics=semantics,
                artifact_id=artifact.artifact_id,
            )
            lake.append_observations(
                series_id,
                [
                    Observation(date(end.year, end.month, 1), end, value)
                    for end, value in published.items()
                ],
            )
        yield lake


def run(house, *, lineage=True, series="bddk:konut", start=APRIL, end=JUNE):
    registry = ToolRegistry()
    registry.register(
        make_change_detection_tool(house.connection, lineage=house.lineage if lineage else None)
    )
    return registry.get("change_detection").run(
        ChangeDetectionArguments(operation="compare", series_id=series, start=start, end=end),
        ExecutionContext(question="q"),
    )


class TestTheToolComputesTheComparison:
    def test_it_returns_a_typed_comparison(self, house):
        outcome = run(house)

        assert outcome.status is ToolStatus.SUCCESS
        assert isinstance(outcome.output, AnalyticalResult)
        assert outcome.output.kind is ResultKind.COMPARISON
        assert outcome.output.status is ResultStatus.COMPUTED

    def test_the_numbers_are_the_hand_calculated_ones(self, house):
        by_label = {v.label: v.value for v in run(house).output.values}

        assert by_label["bddk:konut at 2026-04-30"] == pytest.approx(767314.0)
        assert by_label["bddk:konut absolute change"] == pytest.approx(34124.0)
        assert by_label["bddk:konut relative change"] == pytest.approx(4.4472015, rel=1e-7)

    def test_the_semantics_come_from_the_stored_declaration(self, house):
        # Nothing here infers a scale; silver_series declared it.
        level = next(v for v in run(house).output.values if v.label.endswith("2026-06-30"))

        assert level.unit == "TRY"
        assert level.scale is Scale.MILLION
        assert level.measure is StockFlow.STOCK

    def test_a_stock_still_warns_that_it_is_not_new_lending(self, house):
        assert any("not new lending" in w for w in run(house).warnings)

    def test_a_rate_changes_in_points_through_the_tool_too(self, house):
        outcome = run(house, series="evds:TP.KTF12")
        by_label = {v.label: v for v in outcome.output.values}

        # 46.75 - 40 = 6.75 points, and (46.75-40)/40 = 16.875 percent.
        assert by_label["evds:TP.KTF12 absolute change"].value == pytest.approx(6.75)
        assert by_label["evds:TP.KTF12 absolute change"].unit == "percentage point"
        assert by_label["evds:TP.KTF12 relative change"].value == pytest.approx(16.875)

    def test_the_evidence_names_the_tables_it_read(self, house):
        evidence = run(house).output.evidence

        assert evidence.input_refs == ["silver_series", "silver_observations"]

    def test_a_computed_comparison_records_lineage(self, house):
        outcome = run(house)

        assert outcome.evidence is not None
        assert outcome.output.evidence.lineage_node == outcome.evidence
        stored = house.connection.execute(
            "SELECT label FROM lineage_nodes WHERE node_id = ?", [outcome.evidence]
        ).fetchone()
        assert stored[0] == "change_detection_compare"

    def test_without_lineage_it_still_computes(self, house):
        outcome = run(house, lineage=False)

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.evidence is None
        assert outcome.output.evidence.lineage_node is None


class TestRefusalsReachTheModel:
    def test_an_unknown_series_fails_rather_than_guessing(self, house):
        outcome = run(house, series="bddk:hayalet")

        assert outcome.status is ToolStatus.FAILURE
        assert outcome.error_category == "series_unknown"
        assert any("bddk:hayalet" in w for w in outcome.warnings)

    def test_a_date_that_was_never_published_is_a_successful_refusal(self, house):
        # The tool ran and the answer is "no". Reporting that as a failure
        # would hide which of the two happened.
        outcome = run(house, start=date(2026, 4, 15))

        assert outcome.status is ToolStatus.SUCCESS
        assert outcome.output.status is ResultStatus.INSUFFICIENT
        assert any("2026-04-15" in w for w in outcome.warnings)

    def test_a_refused_comparison_records_no_lineage(self, house):
        # Provenance for a non-result would be a link to nothing.
        outcome = run(house, start=date(2026, 4, 15))
        assert outcome.evidence is None

    def test_the_reason_is_surfaced_as_a_warning(self, house):
        outcome = run(house, start=JUNE, end=APRIL)

        assert outcome.output.status is ResultStatus.ABSTAINED
        assert any("ends before it starts" in w for w in outcome.warnings)


class TestTheArgumentSchema:
    def test_an_unimplemented_operation_is_refused_by_the_schema(self, house):
        # Breakpoint detection is absent from the schema on purpose: a planner
        # cannot ask for something that does not work if it is never offered.
        registry = ToolRegistry()
        registry.register(make_change_detection_tool(house.connection))

        with pytest.raises(ArgumentsRejected):
            registry.get("change_detection").parse(
                {
                    "operation": "breaks",
                    "series_id": "x",
                    "start": "2026-01-31",
                    "end": "2026-06-30",
                }
            )

    def test_an_extra_field_is_refused(self, house):
        registry = ToolRegistry()
        registry.register(make_change_detection_tool(house.connection))

        with pytest.raises(ArgumentsRejected):
            registry.get("change_detection").parse(
                {
                    "operation": "compare",
                    "series_id": "x",
                    "start": "2026-01-31",
                    "end": "2026-06-30",
                    "sql": "SELECT 1",
                }
            )

    def test_the_description_offers_breakpoints_and_says_what_they_are_not(self, house):
        registry = ToolRegistry()
        registry.register(make_change_detection_tool(house.connection))

        described = registry.descriptions()[0]["description"]
        assert "breakpoint:" in described
        # The operation is offered, and its limits are part of the same sentence.
        assert "names no event and establishes no cause" in described
        assert "threshold is fixed by the harness" in described
        operations = registry.descriptions()[0]["arguments"]["$defs"]["SeriesChangeArguments"][
            "properties"
        ]["operation"]["enum"]
        assert "breakpoint" in operations

    def test_no_seventh_tool_was_added(self, house):
        # The registry refuses any name outside the six the brief fixes, so
        # this had to be one of them.
        registry = ToolRegistry()
        registry.register(make_change_detection_tool(house.connection))
        assert "change_detection" in registry

        rejected = ToolSpec(
            name="change_compare",
            description="A seventh name, which the registry does not allow.",
            arguments=ChangeDetectionArguments,
            run=lambda arguments, context: None,  # type: ignore[arg-type,return-value]
        )
        with pytest.raises(RegistryError, match="not an implemented approved tool"):
            registry.register(rejected)


class TestReadingTheSeries:
    def test_it_reads_the_declaration_and_every_observation(self, house):
        series = read_series(house.connection, "bddk:konut")

        assert series.semantics == STOCK
        assert len(series.observations) == 3
        assert series.observations[0].period_end == APRIL

    def test_an_unknown_series_raises(self, house):
        with pytest.raises(SeriesUnknown, match="No series"):
            read_series(house.connection, "nope")


class TestThePlannerCanRouteToIt:
    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_change_detection_tool(house.connection, lineage=house.lineage))
        return registry

    def plan_json(self):
        return json.dumps(
            {
                "question": "konut kredisi ne kadar değişti",
                "steps": [
                    {
                        "step_id": "s1",
                        "tool": "change_detection",
                        "arguments": {
                            "operation": "compare",
                            "series_id": "bddk:konut",
                            "start": "2026-04-30",
                            "end": "2026-06-30",
                        },
                    }
                ],
            }
        )

    def test_a_plan_naming_the_tool_validates(self, house):
        plan = AnalyticalPlan.model_validate_json(self.plan_json())
        validated = validate_plan(plan, self.registry(house))

        assert validated.steps[0].step.tool == "change_detection"

    def test_a_question_reaches_a_gated_answer_through_it(self, house):
        draft = "Nisan'dan Haziran'a konut kredisi stoğu 34.124 milyon TL arttı."
        provider = scripted(self.plan_json(), draft)

        answered = Session(provider, self.registry(house)).answer(
            "Konut kredisi ne kadar değişti?", house.connection
        )

        assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer.verdict.rejected
        assert "34.124" in answered.answer.text

    def test_an_invented_figure_is_still_stripped(self, house):
        draft = (
            "Nisan'dan Haziran'a konut kredisi stoğu 34.124 milyon TL arttı. "
            "Temmuz'da 50.000 milyon TL daha artacak."
        )
        provider = scripted(self.plan_json(), draft)

        answered = Session(provider, self.registry(house)).answer(
            "Konut kredisi ne kadar değişti?", house.connection
        )

        assert answered.answer.status is AnswerStatus.QUALIFIED
        assert "50.000" not in answered.answer.text
