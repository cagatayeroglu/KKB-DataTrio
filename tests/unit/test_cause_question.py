"""A question about cause is answered, and the harness is the one who answers it.

DEC-120 settled that this data cannot identify a causal effect, so the gate refuses
any sentence of the form "X causes Y". It refuses the denials in the same words - a
bounded vocabulary cannot read negation, and trying to would be how an assertion
slips through - so the reader was left a gap exactly where the organizer's third
reference turn asks its question. The harness now closes the answer with one fixed
sentence of its own.
"""

import json

import pytest
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import fetch, registry_for
from test_turn_two import pool as pool  # noqa: F401

from kkb_agent.agent import AnswerStatus, Session
from kkb_agent.agent.claim_qualifiers import absence_fault, causal_fault
from kkb_agent.agent.loop import CAUSE_LIMITATION, CAUSE_NOTE, asks_about_cause
from kkb_agent.llm import scripted

CAUSE_QUESTION = "Faizlerin düştüğü halde kredilerin artmamasının sebebi fiyat artışı olabilir mi?"
PLAIN_QUESTION = "2024 ve 2025 için aylık toplam konut kredisi bakiyesini tablo olarak getir."


def answered(pool, question, draft="Tablo hazırlandı."):
    lake, workspace = pool
    provider = scripted(json.dumps({"question": question, "steps": [fetch()]}), draft)
    return Session(provider, registry_for(pool)).answer(
        question, lake.connection, workspace=workspace
    )


class TestWhichQuestionsAsk:
    @pytest.mark.parametrize(
        "question",
        [
            CAUSE_QUESTION,
            "Bu düşüşün nedeni nedir?",
            "Kredi artışı neden yavaşladı?",
            "Bu neye yol açtı?",
            "Artış neyden kaynaklanıyor?",
            "What caused the fall?",
        ],
    )
    def test_a_question_about_cause_is_recognised(self, question):
        assert asks_about_cause(question)

    @pytest.mark.parametrize(
        "question",
        [
            PLAIN_QUESTION,
            "Konut kredisi faizi ile bakiye aynı yönde mi hareket etmiş?",
            "Bu tabloyu enflasyondan arındırır mısın?",
        ],
    )
    def test_a_question_about_what_happened_is_not(self, question):
        assert not asks_about_cause(question)


class TestTheHarnessClosesTheAnswer:
    def test_the_note_is_added_when_the_reader_asked_why(self, pool):
        result = answered(pool, CAUSE_QUESTION)

        assert CAUSE_NOTE in result.answer.text
        assert CAUSE_LIMITATION in result.answer.limitations

    def test_an_ordinary_question_is_left_alone(self, pool):
        result = answered(pool, PLAIN_QUESTION)

        assert CAUSE_NOTE not in result.answer.text
        assert CAUSE_LIMITATION not in result.answer.limitations

    def test_the_note_goes_through_the_gate_rather_than_around_it(self):
        # It says what it says without the words the gate refuses, so it is checked
        # like the rest of the answer. Reword it into "sebep oldu" and this fails,
        # instead of the sentence quietly vanishing from every answer.
        assert causal_fault(CAUSE_NOTE) is None
        assert absence_fault(CAUSE_NOTE) is None

    def test_the_words_the_gate_refuses_are_still_refused(self):
        # The ban this works around is unchanged: a model writing the same thought
        # in those words is still withheld, in the assertion and in the denial.
        assert causal_fault("Fiyat artışı buna sebep olmuştur.") is not None
        assert causal_fault("Bu analiz sebep olduğunu göstermez.") is not None

    def test_the_note_carries_no_figure_and_names_no_series(self):
        # Nothing a run supplies is in it, which is what makes appending it safe.
        assert not any(character.isdigit() for character in CAUSE_NOTE)

    def test_an_abstention_is_not_dressed_up(self, pool):
        lake, workspace = pool
        provider = scripted(
            json.dumps(
                {"question": CAUSE_QUESTION, "steps": [], "clarification": "missing_series"}
            ),
        )
        result = Session(provider, registry_for(pool)).answer(
            CAUSE_QUESTION, lake.connection, workspace=workspace
        )

        assert result.answer.status is AnswerStatus.ABSTAINED
        assert CAUSE_NOTE not in result.answer.text
