"""Native web tools must describe fields their JSON schema actually accepts."""

import json

import pytest

from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.trust_loop import tool_menu
from kkb_agent.tools.web_search import make_web_search_tool
from kkb_agent.tools.web_url import WebUrlArguments, make_web_url_tool


class OfflineSearch:
    def search(self, request):
        raise AssertionError("description check must not perform I/O")


@pytest.mark.parametrize("name", ["web_search", "web_url"])
def test_native_web_menu_does_not_request_unaccepted_plan_edges(name):
    registry = ToolRegistry()
    registry.register(make_web_search_tool(backend=OfflineSearch()))
    registry.register(make_web_url_tool())
    entry = next(e["function"] for e in tool_menu(registry) if e["function"]["name"] == name)
    # A plan edge is not a tool argument in native mode. Include property
    # descriptions too: found_by/read_from previously repeated that instruction.
    assert "depends_on" not in json.dumps(entry)


def test_native_search_reference_is_accepted_without_a_plan_edge():
    assert WebUrlArguments.model_validate({"found_by": "a1", "result": 1}).found_by == "a1"
