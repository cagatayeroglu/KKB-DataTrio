"""A query vector that was not made says why on the operator's console, and nothing else."""

import json

import pytest

from kkb_agent.api.__main__ import _reported
from kkb_agent.llm.provider import RateLimited, TransportError


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (TransportError("Kloudeks request failed (ReadTimeout)"), "TransportError"),
        (RateLimited("Kloudeks rate or quota limit reached (429)"), "RateLimited"),
    ],
)
def test_a_failed_query_vector_names_its_cause_and_not_the_question(capsys, error, kind):
    def failing(_text: str) -> object:
        raise error

    with pytest.raises(type(error)):
        _reported(failing)("gizli soru metni")
    line = json.loads(capsys.readouterr().out)
    assert line["query_embedding_failed"] == kind
    assert line["detail"] == str(error)
    assert "gizli" not in json.dumps(line)


def test_a_made_vector_passes_through_silently(capsys):
    assert _reported(str.upper)("soru") == "SORU"
    assert capsys.readouterr().out == ""
