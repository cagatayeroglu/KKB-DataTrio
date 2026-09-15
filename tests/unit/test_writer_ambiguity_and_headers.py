"""M11-11: M11-07 live repeat 2 withheld Turn 3 sentences for two reasons.

A plain Turkish heading ("Değerlendirme:") was read as a result identity, and
counts copied from Turn 1 shared a number with the table comparison's counts, so
the gate could not bind them. The writer is now told which numbers are ambiguous.
"""

from datetime import date

import pytest
from test_claim_semantic_binding import connection as connection  # noqa: F401
from test_claim_semantic_binding import result
from test_claim_semantic_binding import (
    verified_execution_boundary as verified_execution_boundary,  # noqa: F401
)

from kkb_agent.agent.loop import render_results
from kkb_agent.agent.verifier import AnswerStatus, gate_answer, verify_claims
from kkb_agent.core import Period


@pytest.mark.parametrize("heading", ["Değerlendirme", "Sonuç", "Özet", "Not", "Assessment"])
def test_plain_discourse_heading_is_not_an_identity(connection, heading):  # noqa: F811
    gated = gate_answer(f"{heading}: Ocak 2025'te 100 milyon TL.", result(), connection)
    assert gated.status is AnswerStatus.ACCEPTED, gated.omitted


@pytest.mark.parametrize("heading", ["other_series", "EVDS:TP.KFE.TR", "series.2", "konut-faiz"])
def test_identifier_shaped_heading_must_still_name_the_value(heading):
    assert not verify_claims(f"{heading}: Ocak 2025'te 100 milyon TL.", result()).accepted


def test_known_name_heading_still_selects_or_conflicts():
    table = {"credit": result(), "other": result(label="other_series", value=200.0)}
    assert verify_claims("credit: 100 milyon TL.", table).accepted
    assert not verify_claims("other: 100 milyon TL.", table).accepted


def test_indistinguishable_values_are_marked_and_not_offered_to_the_writer():
    same = result().model_copy(update={"result_id": "copy"})
    june = result(period=Period(start=date(2025, 6, 1), end=date(2025, 6, 30)))
    percent = result(unit="percent")
    context = render_results({"credit": result(), "copy": same, "june": june, "rate": percent})
    blocks = dict(block.split("\n", 1) for block in context.split("\n\n"))
    assert "AMBIGUOUS" in blocks["[credit]"] and "AMBIGUOUS" in blocks["[copy]"]
    assert "display 100 milyon TL" not in blocks["[credit]"] + blocks["[copy]"]
    # A different period or unit is a qualifier the gate can bind.
    assert "AMBIGUOUS" not in blocks["[june]"] and "AMBIGUOUS" not in blocks["[rate]"]


def test_marking_matches_what_the_gate_withholds(connection):  # noqa: F811
    same = result().model_copy(update={"result_id": "copy"})
    table = {"credit": result(), "copy": same}
    assert not verify_claims("Ocak 2025'te 100 milyon TL.", table).accepted
    assert "AMBIGUOUS" not in render_results({"credit": result()})
    assert verify_claims("Ocak 2025'te 100 milyon TL.", {"credit": result()}).accepted
