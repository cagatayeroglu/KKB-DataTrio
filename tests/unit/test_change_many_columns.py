"""Several columns' changes in one call (live B1, 2026-09-23 on 8012).

Four columns' monthly net changes took four `change` calls one after the other, and the
turn ran out of calls before its table was published. One call now takes `columns`, and
its result is what one-column calls in turn would have built.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from test_co_movement import lake as lake  # noqa: F401 - the pool fixture builds on it
from test_same_plan_tables import PUBLISHED
from test_turn_two import pool as pool  # noqa: F401
from test_turn_two import tool as transform_tool

from kkb_agent.agent import ExecutionContext
from kkb_agent.agent.executor import ToolStatus
from kkb_agent.core import ResultStatus
from kkb_agent.tools.table_transform import TableTransformArguments


def change(pool, **arguments):
    lake, workspace = pool
    parsed = TableTransformArguments.model_validate(
        {"operation": "change", "source": PUBLISHED, "kind": "difference", **arguments}
    )
    return transform_tool(lake, workspace).run(parsed, ExecutionContext("turn"))


def columns_of(result) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for value in result.values:
        found.setdefault(value.label, {})[value.period.end] = value.value
    return found


def labels(pool) -> list[str]:
    """The table's monthly series columns (it also holds counts, which have no change)."""
    _, workspace = pool
    counted: dict[str, int] = {}
    for value in workspace.value_of(PUBLISHED).values:
        if value.period is not None and value.period.frequency.value == "monthly":
            counted[value.label] = counted.get(value.label, 0) + 1
    return [label for label, count in counted.items() if count >= 3]


def test_one_call_adds_every_columns_change_beside_it(pool):
    names = labels(pool)
    assert len(names) >= 2
    done = change(pool, columns=names)
    assert done.status is ToolStatus.SUCCESS
    assert done.output.status is ResultStatus.COMPUTED, done.output.reason
    got = columns_of(done.output)
    for name in names:
        assert f"{name} change (lag 1)" in got
    # The table's own columns are unchanged beside the new ones.
    _, workspace = pool
    source = columns_of(workspace.value_of(PUBLISHED))
    for name in names:
        assert got[name] == source[name]


def test_it_is_what_one_call_per_column_builds(pool):
    names = labels(pool)
    many = columns_of(change(pool, columns=names).output)
    for name in names:
        one = columns_of(change(pool, column=name).output)
        assert many[f"{name} change (lag 1)"] == one[f"{name} change (lag 1)"]


@pytest.mark.parametrize("arguments", [{}, {"column": "a", "columns": ["b"]}])
def test_a_column_is_named_one_way(arguments):
    with pytest.raises(ValidationError):
        TableTransformArguments.model_validate(
            {"operation": "change", "source": PUBLISHED, "kind": "difference", **arguments}
        )


def test_an_unknown_column_stops_the_call(pool):
    done = change(pool, columns=[labels(pool)[0], "Yok"])
    assert done.output.status is not ResultStatus.COMPUTED
