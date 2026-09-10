"""M8-10: what the verifier lets through, and the first end-to-end slice.

Verification that nothing routes through is a report, not a gate. These tests
are about the decision itself — which sentence is shown, which is withheld,
and when the honest output is no answer at all.

The end-to-end class is the first time a question reaches a gated answer
through the real planner, registry, tool and verifier, with only the model
scripted.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import (
    AnswerStatus,
    ExecutionContext,
    Session,
    ToolRegistry,
    collect_results,
    gate_answer,
    render_result,
)
from kkb_agent.core import (
    Aggregation,
    AnalyticalResult,
    CumulativeKind,
    Frequency,
    Period,
    ResultEvidence,
    ResultKind,
    ResultStatus,
    ResultValue,
    SampleCounts,
    Scale,
    SourceRef,
    StockFlow,
)
from kkb_agent.lakehouse import Observation, SeriesSemantics, open_lakehouse
from kkb_agent.llm.doubles import scripted
from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool

NOW = datetime(2026, 9, 9, tzinfo=UTC)
MONTHLY = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
PUBLISHED = {date(2026, 4, 30): 767314.0, date(2026, 5, 31): 782918.0, date(2026, 6, 30): 801438.0}

JUNE = Period(start=date(2026, 6, 1), end=date(2026, 6, 30), frequency=Frequency.MONTHLY)
SUPPORTED = "Haziran 2026'da konut kredisi stoğu 801.438 milyon TL."
INVENTED = "Temmuz ayında 912.000 milyon TL'ye ulaştı."


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        artifact = lake.record_artifact(
            b'{"konut": 801438}',
            source=SourceRef(source_id="bddk", source_type="http-json", locator="opaque:t4"),
            media_type="application/json",
            recorded_at=NOW,
        )
        lake.register_series(
            "bddk:konut",
            title="Tüketici Kredileri - Konut",
            semantics=MONTHLY,
            artifact_id=artifact.artifact_id,
        )
        lake.append_observations(
            "bddk:konut",
            [Observation(date(end.year, end.month, 1), end, v) for end, v in PUBLISHED.items()],
        )
        yield lake


def result(**overrides) -> AnalyticalResult:
    fields = {
        "result_id": "r1",
        "kind": ResultKind.LEVEL,
        "status": ResultStatus.COMPUTED,
        "tool": "lakehouse",
        "values": [
            ResultValue(
                label="bddk:konut",
                value=801438.0,
                unit="TRY",
                scale=Scale.MILLION,
                measure=StockFlow.STOCK,
                period=JUNE,
            )
        ],
        "samples": SampleCounts(used=3),
        "evidence": ResultEvidence(input_refs=["silver_observations"]),
    }
    fields.update(overrides)
    return AnalyticalResult(**fields)


class TestASupportedAnswerPassesThrough:
    def test_it_is_accepted_whole(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection)

        assert gated.status is AnswerStatus.ACCEPTED
        assert gated.text == SUPPORTED
        assert gated.omitted == ()
        assert gated.presentable

    def test_the_limitations_travel_with_it(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection)
        assert any("bound to this result's values" in item for item in gated.limitations)

    def test_prose_without_numbers_is_kept(self, house):
        draft = f"{SUPPORTED} Seri aylık yayımlanmaktadır."
        gated = gate_answer(draft, result(), house.connection)

        assert gated.status is AnswerStatus.ACCEPTED
        assert "aylık yayımlanmaktadır" in gated.text


class TestAnUnsupportedSentenceIsWithheld:
    def test_only_the_offending_sentence_is_dropped(self, house):
        gated = gate_answer(f"{SUPPORTED} {INVENTED}", result(), house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert gated.text == SUPPORTED
        assert "912.000" not in gated.text

    def test_the_withheld_sentence_is_recorded_not_discarded(self, house):
        # A silently shortened answer is indistinguishable from one that never
        # made the claim, and the operator needs to see the difference.
        gated = gate_answer(f"{SUPPORTED} {INVENTED}", result(), house.connection)

        assert len(gated.omitted) == 1
        assert gated.omitted[0].text == INVENTED
        assert gated.omitted[0].reasons

    def test_a_wrongly_scaled_sentence_is_withheld_though_its_number_is_real(self, house):
        # The figure exists; "bin" contradicts the recorded million scale.
        gated = gate_answer(
            f"{SUPPORTED} Diğer bir deyişle 801.438 bin TL.", result(), house.connection
        )

        assert gated.status is AnswerStatus.QUALIFIED
        assert "bin TL" not in gated.text
        assert any("recorded as million" in r for r in gated.omitted[0].reasons)

    def test_a_sentence_attributed_to_the_wrong_year_is_withheld(self, house):
        gated = gate_answer(
            f"{SUPPORTED} 2019'da da 801.438 milyon TL idi.", result(), house.connection
        )

        assert gated.status is AnswerStatus.QUALIFIED
        assert "2019" not in gated.text

    def test_the_final_sentence_without_trailing_punctuation_is_still_gated(self, house):
        gated = gate_answer(f"{SUPPORTED} Ayrıca 912.000 milyon TL", result(), house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert "912.000" not in gated.text


class TestAbstention:
    def test_an_answer_with_nothing_left_abstains_rather_than_shrinking(self, house):
        gated = gate_answer(INVENTED, result(), house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.text == ""
        assert not gated.presentable
        assert gated.abstention

    def test_a_disqualified_result_takes_the_whole_draft_with_it(self, house):
        # A dangling evidence reference poisons the unnumbered prose too,
        # because the prose describes the same broken result.
        broken = result(evidence=ResultEvidence(input_refs=["silver_invented"]))
        gated = gate_answer(f"{SUPPORTED} Seri aylıktır.", broken, house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.text == ""
        assert "resolves to no table" in (gated.abstention or "")

    def test_a_tampered_result_abstains(self, house):
        tampered = result(
            values=[
                ResultValue(
                    label="bddk:konut",
                    value=850000.0,
                    unit="TRY",
                    scale=Scale.MILLION,
                    period=JUNE,
                )
            ]
        )
        gated = gate_answer("Haziran 2026'da 850.000 milyon TL.", tampered, house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert "stored as 801438.0" in (gated.abstention or "")

    def test_a_sample_floor_failure_abstains(self, house):
        gated = gate_answer(SUPPORTED, result(), house.connection, minimum_samples=24)

        assert gated.status is AnswerStatus.ABSTAINED
        assert "below the 24" in (gated.abstention or "")

    def test_an_empty_draft_abstains_and_says_which_kind_of_nothing(self, house):
        gated = gate_answer("   ", result(), house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert gated.abstention == "The answer was empty"


class TestWhatTheWriterIsGiven:
    def test_the_rendered_result_carries_units_and_periods(self):
        rendered = render_result(result())

        assert "801438.0" in rendered
        assert "unit TRY" in rendered
        assert "scale million" in rendered
        assert "2026-06-01..2026-06-30" in rendered

    def test_an_unknown_unit_is_shown_as_unknown_not_omitted(self):
        rendered = render_result(
            result(
                values=[ResultValue(label="x", value=1.0)],
                unresolved_semantics=["unit is unresolved"],
            )
        )

        assert "unit UNKNOWN" in rendered
        assert "Unresolved: unit is unresolved" in rendered

    def test_limitations_reach_the_writer(self):
        rendered = render_result(
            result(
                kind=ResultKind.ASSOCIATION,
                values=[ResultValue(label="r", value=0.7, unit="dimensionless", scale=Scale.ONE)],
                limitations=["Association only; not a cause"],
            )
        )
        assert "Limitation: Association only" in rendered


def plan_json(sql: str) -> str:
    return json.dumps(
        {
            "question": "konut kredisi",
            "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {"sql": sql}}],
        }
    )


FULLY_TYPED = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    " WHERE o.period_end = DATE '2026-06-30'"
)


class TestTheWholeSliceEndToEnd:
    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
        return registry

    def test_a_question_becomes_a_gated_answer(self, house):
        provider = scripted(plan_json(FULLY_TYPED), SUPPORTED)
        session = Session(provider, self.registry(house))

        answered = session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        assert answered.answer.status is AnswerStatus.ACCEPTED
        assert "801.438" in answered.answer.text
        assert answered.results[-1].status is ResultStatus.COMPUTED

    def test_a_model_that_invents_a_figure_has_it_stripped(self, house):
        provider = scripted(plan_json(FULLY_TYPED), f"{SUPPORTED} {INVENTED}")
        session = Session(provider, self.registry(house))

        answered = session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        assert answered.answer.status is AnswerStatus.QUALIFIED
        assert "912.000" not in answered.answer.text
        assert answered.answer.omitted

    def test_the_writer_never_sees_rows_only_computed_values(self, house):
        provider = scripted(plan_json(FULLY_TYPED), SUPPORTED)
        session = Session(provider, self.registry(house))
        session.answer("Haziran'da konut kredisi stoğu neydi?", house.connection)

        writer_prompt = "\n".join(m.content for m in provider.seen[-1])
        assert "801438" in writer_prompt
        assert "SELECT" not in writer_prompt

    def test_a_query_that_establishes_nothing_abstains_without_a_draft(self, house):
        # The model is never asked to write about an analysis that produced
        # nothing, so there is only one scripted response to consume.
        provider = scripted(plan_json("SELECT series_id, title FROM silver_series"))
        session = Session(provider, self.registry(house))

        answered = session.answer("Hangi seriler var?", house.connection)

        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert "listing" in (answered.answer.abstention or "")

    def test_a_failed_step_yields_an_abstention_not_an_answer(self, house):
        provider = scripted(plan_json("SELECT * FROM lineage_nodes"))
        session = Session(provider, self.registry(house))

        answered = session.answer("Soy ağacı nedir?", house.connection)

        assert answered.answer.status is AnswerStatus.ABSTAINED
        assert "No tool produced an analytical result" in (answered.answer.abstention or "")

    def test_results_are_collected_only_from_successful_steps(self, house):
        registry = self.registry(house)
        outcome = registry.get("lakehouse").run(
            LakehouseArguments(sql="SELECT * FROM lineage_nodes"),
            ExecutionContext(question="q"),
        )

        class Outcome:
            results = (outcome,)

        assert collect_results(Outcome()) == ()
