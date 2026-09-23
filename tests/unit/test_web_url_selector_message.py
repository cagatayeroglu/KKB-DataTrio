"""A follow sent with the page's address beside it is told how to follow (live TCMB run).

2026-09-23 the model followed a link of the TCMB 2024 announcements page with url,
read_from and follow together; the refusal said only "give exactly one of ...", and a
round went to learning which one was too many.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kkb_agent.tools.web_url import WebUrlArguments


def test_a_follow_with_the_address_beside_it_is_told_the_way_that_works():
    with pytest.raises(ValidationError) as refused:
        WebUrlArguments.model_validate(
            {"url": "https://www.example.test/list", "read_from": "a2", "follow": "Duyuru"}
        )
    said = str(refused.value)
    assert "this call gave url, read_from" in said
    assert "give read_from (that read's id) and follow only" in said


def test_one_selector_is_still_enough():
    assert WebUrlArguments.model_validate({"read_from": "a2", "follow": "Duyuru"}).url is None
