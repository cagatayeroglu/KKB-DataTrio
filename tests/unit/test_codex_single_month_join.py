"""A one-month table is valid input for a same-month join or column sum."""

from test_compute_contracts import JAN, cell, compute, table

from kkb_agent.agent.executor import ToolStatus
from kkb_agent.core import ResultStatus
from kkb_agent.tools.table_transform import JoinTableArguments, _joined


def test_single_month_columns_can_be_summed():
    outcome = compute(
        table(cell("short_a", JAN, 10), cell("short_b", JAN, 20)),
        label="short",
        operation="sum",
        columns=["short_a", "short_b"],
    )
    assert outcome.status is ToolStatus.SUCCESS
    assert [v.value for v in outcome.output.values if v.label == "short"] == [30]


def test_single_month_tables_can_be_joined_without_forcing_extra_months():
    outcome = _joined(
        JoinTableArguments(operation="join_table", source="a1", other="a2"),
        table(cell("short_a", JAN, 10)),
        table(cell("short_b", JAN, 20)),
    )
    assert outcome.status is ResultStatus.COMPUTED, outcome.reason
    assert {(v.label, v.value) for v in outcome.values} == {("short_a", 10), ("short_b", 20)}
