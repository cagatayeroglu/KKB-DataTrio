"""M8-17: one answer over several named results.

The reference scenario's answer is about a *table* — housing credit beside its
interest rate, then a price index added without disturbing either. Gating that
against a single result cannot work: the moment an answer cites two columns,
one of them is unbound and the sentence is withheld.

The case worth the most attention is the middle one. A broken column must not
silence a sound one, and it must not be quietly reported either.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from kkb_agent.agent import (
    AnswerStatus,
    ArtifactKind,
    Session,
    ToolRegistry,
    Workspace,
    gate_answer,
    render_results,
    verify_claims,
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
from kkb_agent.tools import make_lakehouse_tool

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


def a_result(
    value: float, label: str = "bddk:konut", unit: str = "TRY", scale: Scale = Scale.MILLION, **over
) -> AnalyticalResult:
    fields = {
        "result_id": f"r-{label}-{value}",
        "kind": ResultKind.LEVEL,
        "status": ResultStatus.COMPUTED,
        "tool": "lakehouse",
        "values": [ResultValue(label=label, value=value, unit=unit, scale=scale, period=JUNE)],
        "samples": SampleCounts(used=3),
        "evidence": ResultEvidence(input_refs=["silver_observations"]),
    }
    fields.update(over)
    return AnalyticalResult(**fields)


STOK = a_result(801438.0)
FAIZ = a_result(46.75, label="evds:TP.KTF12", unit="percent", scale=Scale.ONE)
TABLE = {"konut_stok": STOK, "konut_faiz": FAIZ}
BOTH = "Haziran 2026'da konut kredisi stoğu 801.438 milyon TL, faiz oranı 46,75 idi."


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


class TestOneAnswerOverSeveralColumns:
    def test_a_sentence_citing_two_columns_is_accepted(self, house):
        gated = gate_answer(BOTH, TABLE, house.connection)

        assert gated.status is AnswerStatus.ACCEPTED, gated.verdict.rejected
        assert gated.text == BOTH

    def test_the_same_sentence_fails_against_one_column_alone(self, house):
        # This is the limitation M8-17 removes, stated as a test.
        gated = gate_answer(BOTH, STOK, house.connection)
        assert gated.status is AnswerStatus.ABSTAINED

    def test_each_number_names_the_column_it_came_from(self, house):
        verdict = verify_claims(BOTH, TABLE, house.connection)
        sources = {item.number.text: item.source for item in verdict.numbers if item.source}

        assert sources["801.438"] == "konut_stok"
        assert sources["46,75"] == "konut_faiz"

    def test_a_number_in_neither_column_is_still_unbound(self, house):
        gated = gate_answer(f"{BOTH} Konut fiyat endeksi 214,8 oldu.", TABLE, house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert "214,8" not in gated.text

    def test_a_list_of_results_works_without_names(self, house):
        verdict = verify_claims(BOTH, [STOK, FAIZ], house.connection)
        assert verdict.accepted, verdict.rejected

    def test_scale_is_still_checked_per_column(self, house):
        # 46,75 is a ratio; calling it "milyon" contradicts its recorded scale.
        gated = gate_answer("Faiz oranı 46,75 milyon TL idi.", TABLE, house.connection)
        assert gated.status is AnswerStatus.ABSTAINED


class TestABrokenColumnDoesNotSilenceASoundOne:
    def broken_table(self):
        return {
            "konut_stok": STOK,
            "konut_faiz": a_result(
                46.75,
                label="evds:TP.KTF12",
                unit="percent",
                scale=Scale.ONE,
                evidence=ResultEvidence(input_refs=["silver_invented"]),
            ),
        }

    def test_only_the_sentence_resting_on_it_is_withheld(self, house):
        draft = "Konut kredisi 801.438 milyon TL. Faiz oranı 46,75 idi."
        gated = gate_answer(draft, self.broken_table(), house.connection)

        assert gated.status is AnswerStatus.QUALIFIED
        assert "801.438" in gated.text
        assert "46,75" not in gated.text

    def test_the_reason_names_the_broken_column(self, house):
        draft = "Konut kredisi 801.438 milyon TL. Faiz oranı 46,75 idi."
        gated = gate_answer(draft, self.broken_table(), house.connection)

        assert any("konut_faiz:" in reason for reason in gated.omitted[0].reasons)

    def test_a_sentence_mixing_both_is_withheld_whole(self, house):
        # The broken half poisons the sentence it shares.
        gated = gate_answer(BOTH, self.broken_table(), house.connection)
        assert gated.status is AnswerStatus.ABSTAINED

    def test_when_every_column_is_broken_the_prose_falls_too(self, house):
        every = {
            "a": a_result(1.0, evidence=ResultEvidence(input_refs=["nope_a"])),
            "b": a_result(2.0, evidence=ResultEvidence(input_refs=["nope_b"])),
        }
        gated = gate_answer("Bir açıklama cümlesi.", every, house.connection)

        assert gated.status is AnswerStatus.ABSTAINED
        assert "nope_a" in (gated.abstention or "")

    def test_one_broken_column_leaves_unnumbered_prose_standing(self, house):
        gated = gate_answer(
            "Konut kredisi 801.438 milyon TL. Seri aylık yayımlanır.",
            self.broken_table(),
            house.connection,
        )

        assert gated.status is AnswerStatus.ACCEPTED
        assert "aylık yayımlanır" in gated.text


class TestWhatTheWriterSees:
    def test_each_result_is_labelled_by_its_name(self):
        rendered = render_results(TABLE)

        assert "[konut_stok]" in rendered
        assert "[konut_faiz]" in rendered
        assert "801438.0" in rendered
        assert "46.75" in rendered

    def test_units_stay_attached_to_the_right_column(self):
        rendered = render_results(TABLE)
        stok, faiz = rendered.split("[konut_faiz]")

        assert "unit TRY" in stok
        assert "unit percent" in faiz


def plan_json(sql: str) -> str:
    return json.dumps(
        {
            "question": "konut kredisi",
            "steps": [{"step_id": "s1", "tool": "lakehouse", "arguments": {"sql": sql}}],
        }
    )


SERIES_SQL = (
    "SELECT o.series_id, o.period_start, o.period_end, o.value, s.unit, s.scale,"
    " s.frequency, s.anchor, s.observation"
    " FROM silver_observations o JOIN silver_series s ON s.series_id = o.series_id"
    " WHERE o.period_end = DATE '2026-06-30'"
)


class TestAFollowUpCitesTheWholeTable:
    def registry(self, house):
        registry = ToolRegistry()
        registry.register(make_lakehouse_tool(house.connection, lineage=house.lineage))
        return registry

    def test_a_second_turn_may_quote_a_column_the_first_turn_computed(self, house):
        space = Workspace.open(house.connection)
        space.record("konut_faiz", ArtifactKind.VALUE, FAIZ)

        provider = scripted(plan_json(SERIES_SQL), BOTH)
        session = Session(provider, self.registry(house))
        answered = session.answer(
            "Konut kredisi ve faiz nedir?",
            house.connection,
            workspace=space,
            remember="konut_stok",
        )

        # 46,75 was never computed this turn; it came out of the workspace.
        assert answered.answer.status is AnswerStatus.ACCEPTED, answered.answer.verdict.rejected
        assert "46,75" in answered.answer.text

    def test_the_writer_is_shown_the_prior_column_too(self, house):
        space = Workspace.open(house.connection)
        space.record("konut_faiz", ArtifactKind.VALUE, FAIZ)

        provider = scripted(plan_json(SERIES_SQL), BOTH)
        Session(provider, self.registry(house)).answer(
            "Konut kredisi ve faiz nedir?",
            house.connection,
            workspace=space,
            remember="konut_stok",
        )

        writer_prompt = "\n".join(m.content for m in provider.seen[-1])
        assert "[konut_faiz]" in writer_prompt
        assert "[konut_stok]" in writer_prompt

    def test_a_stale_column_cannot_re_enter_the_answer(self, house):
        space = Workspace.open(house.connection)
        space.define("range", ArtifactKind.SOURCE, parameters={"to": "2025-12"})
        space.record("konut_faiz", ArtifactKind.VALUE, FAIZ, inputs=["range"])
        space.define("range", ArtifactKind.SOURCE, parameters={"to": "2026-06"})

        provider = scripted(plan_json(SERIES_SQL), BOTH)
        answered = Session(provider, self.registry(house)).answer(
            "Konut kredisi ve faiz nedir?",
            house.connection,
            workspace=space,
            remember="konut_stok",
        )

        # The rate is stale, so the sentence quoting it must not be shown.
        assert answered.answer.status is AnswerStatus.ABSTAINED

    def test_without_a_workspace_the_answer_still_works_on_this_turn_alone(self, house):
        provider = scripted(plan_json(SERIES_SQL), "Konut kredisi 801.438 milyon TL.")
        answered = Session(provider, self.registry(house)).answer(
            "Konut kredisi nedir?", house.connection
        )
        assert answered.answer.status is AnswerStatus.ACCEPTED
