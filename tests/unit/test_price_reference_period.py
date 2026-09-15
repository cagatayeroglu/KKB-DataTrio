"""M11-11: a recorded deflation reference month is not a second period claim.

M11-07's live repeat withheld Turn 2 because the writer quoted a 2023-12 real
balance "2025-12 fiyatlarıyla"; the period rule read 2025 as the claim's year.
"""

import pytest
from test_claim_semantic_binding import connection as connection  # noqa: F401
from test_claim_semantic_binding import result
from test_claim_semantic_binding import (
    verified_execution_boundary as verified_execution_boundary,  # noqa: F401
)

from kkb_agent.agent.verifier import AnswerStatus, gate_answer
from kkb_agent.core import TransformationRecord


def deflated(reference="2026-06-30", output="housing_credit"):
    base = result()
    record = TransformationRecord(
        operation="deflate",
        parameters={"reference_period": reference},
        input_refs=["housing_credit_nominal"],
        output_ref=output,
    )
    evidence = base.evidence.model_copy(update={"transformations": [record]})
    return base.model_copy(update={"evidence": evidence})


@pytest.mark.parametrize(
    "draft",
    [
        "Ocak 2025'te reel bakiye 2026-06 fiyatlarıyla 100 milyon TL.",
        "Ocak 2025'te reel bakiye Haziran 2026 fiyatlarıyla 100 milyon TL.",
        "Ocak 2025'te reel bakiye HAZİRAN 2026 fiyatlarıyla 100 milyon TL.",
        "Reel bakiye 2026 Haziran fiyatlarıyla Ocak 2025'te 100 milyon TL.",
        "Ocak 2025'te reel bakiye 100 milyon TL (2026-06 fiyatlarıyla).",
        "In January 2025 the real balance at 2026-06 prices was 100 million TRY.",
    ],
)
def test_recorded_reference_month_beside_a_real_figure_is_accepted(connection, draft):  # noqa: F811
    assert gate_answer(draft, deflated(), connection).status is AnswerStatus.ACCEPTED
    # The same sentence without the recorded deflation still names a second year.
    assert gate_answer(draft, result(), connection).status is AnswerStatus.ABSTAINED


@pytest.mark.parametrize(
    ("draft", "evidence"),
    [
        ("Ocak 2025'te reel bakiye 2027-06 fiyatlarıyla 100 milyon TL.", {}),
        ("Ocak 2025 ve Haziran 2026'da reel bakiye 100 milyon TL.", {}),
        ("Haziran 2026'da reel bakiye 100 milyon TL.", {}),
        (
            "Ocak 2025'te reel bakiye 2026-06 fiyatlarıyla 100 milyon TL.",
            {"output": "another_column"},
        ),
        ("Ocak 2025'te reel bakiye 2026-06 fiyatlarıyla 100 milyon TL.", {"reference": "bad"}),
    ],
)
def test_other_dates_and_unrecorded_references_still_fail(connection, draft, evidence):  # noqa: F811
    gated = gate_answer(draft, deflated(**evidence), connection)
    assert gated.status is AnswerStatus.ABSTAINED
    assert any("period" in reason for reason in gated.omitted[0].reasons)
