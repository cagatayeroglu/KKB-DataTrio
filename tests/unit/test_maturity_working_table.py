"""One working table carries derived groups through movement and final projection."""

from __future__ import annotations

import json

from pydantic import BaseModel
from test_base_month import DEC, FEB, JAN, MAR, SERIES, read
from test_base_month import rig as rig

from kkb_agent.agent.executor import ToolResult, ToolStatus
from kkb_agent.agent.registry import ToolRegistry, ToolSpec
from kkb_agent.agent.trust_loop import FINISH, run_turn
from kkb_agent.core import ResultStatus
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import ToolCall
from kkb_agent.tools.table_compute import make_table_compute_tool
from kkb_agent.tools.table_transform import make_table_transform_tool


class Search(BaseModel):
    query: str = "maturity"


def call(identifier: str, tool: str, arguments: dict) -> tuple[ToolCall, ...]:
    return (ToolCall(identifier, tool, json.dumps(arguments, ensure_ascii=False)),)


def finish(identifier: str, publish: str) -> tuple[ToolCall, ...]:
    return call(identifier, FINISH, {"answer": "Hareket tablosu hazır.", "publish": publish})


def test_derived_groups_continue_one_table_and_only_movements_are_published(rig):  # noqa: F811
    lake, workspace = rig
    base = read(lake, since=DEC)
    group_a, group_b = "group A", "group B"
    stocks = [*SERIES, group_a, group_b]
    movements = [f"{label} change (lag 1)" for label in stocks]

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="catalog_search",
            description="Discovery metadata, not a table.",
            arguments=Search,
            run=lambda arguments, context: ToolResult(  # noqa: ARG005
                ToolStatus.SUCCESS, "", "catalog_search", output={"candidates": []}
            ),
            discovery_only=True,
        )
    )
    registry.register(make_table_compute_tool(lake.connection))
    registry.register(
        make_table_transform_tool(lake.connection, workspace, lineage=lake.lineage)
    )

    provider = scripted(
        call("c1", "catalog_search", {"query": "maturity"}),
        # Discovery ids are refused as table sources instead of becoming the current table.
        call(
            "c2",
            "table_transform",
            {"operation": "filter", "source": "a1", "start_period": JAN.isoformat()},
        ),
        call(
            "c3",
            "table_compute",
            {"source": "base", "label": group_a, "operation": "sum", "columns": list(SERIES)},
        ),
        # The model names the base again. The loop continues the proven current descendant.
        call(
            "c4",
            "table_compute",
            {"source": "base", "label": group_b, "operation": "max", "columns": list(SERIES)},
        ),
        # A raw/intermediate publication is rejected before the turn can finish.
        finish("f1", "base"),
        call(
            "c5",
            "table_transform",
            {
                "operation": "change",
                "source": "base",
                "columns": stocks,
                "kind": "difference",
                "lag": 1,
            },
        ),
        call(
            "c6",
            "table_transform",
            {
                "operation": "filter",
                "source": "base",
                "start_period": JAN.isoformat(),
                "end_period": MAR.isoformat(),
                "columns": movements,
            },
        ),
        finish("f2", "a7"),
    )
    outcome = run_turn(
        "Stok olmasın; önceki aya göre aylık hareketi ve iki türetilmiş grubu göster.",
        provider=provider,
        registry=registry,
        instructions="",
        published={"base": base},
    )

    discovery_source = outcome.observations[1]
    assert discovery_source.action.tool == "table_transform"
    assert discovery_source.result.status is ToolStatus.FAILURE
    assert discovery_source.result.error_category == "workspace_reference"

    by_label = {
        item.action.arguments.get("label"): item
        for item in outcome.observations
        if item.action.tool == "table_compute"
    }
    first, second = by_label[group_a], by_label[group_b]
    assert second.action.arguments["source"] == first.action.id
    second_labels = {value.label for value in second.result.output.values}
    assert {group_a, group_b} <= second_labels

    refused_finish = [
        item for item in outcome.observations if item.result.error_category == "completion"
    ]
    assert len(refused_finish) == 1

    changed = next(
        item
        for item in outcome.observations
        if item.action.arguments.get("operation") == "change"
    )
    changed_labels = {value.label for value in changed.result.output.values}
    assert set(stocks) <= changed_labels
    assert set(movements) <= changed_labels

    final = next(item.result.output for item in outcome.observations if item.action.id == "a7")
    assert final.status is ResultStatus.COMPUTED
    assert {value.label for value in final.values} == set(movements)
    assert {value.period.end for value in final.values} == {JAN, FEB, MAR}
    assert DEC not in {value.period.end for value in final.values}
    assert min(value.period.end for value in final.values) == JAN
    assert max(value.period.end for value in final.values) == MAR
    assert outcome.publish == "a7"
    assert not outcome.publication_blocked
