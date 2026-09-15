"""M2-14/M5-20 tool boundary for trusted unary table transformations."""

from datetime import date

import pytest
from pydantic import ValidationError
from test_add_series import arguments as add_arguments
from test_add_series import bound_tool
from test_co_movement import lake as lake
from test_turn_two import CPI, CPI_ID, MONTHS
from test_turn_two import pool as pool

from kkb_agent.agent import ExecutionContext
from kkb_agent.agent.verifier import result_faults
from kkb_agent.agent.workspace import ArtifactKind
from kkb_agent.core import ResultStatus
from kkb_agent.tools.table_transform import TableTransformArguments


def operation(name, source="table", **parameters):
    return TableTransformArguments.model_validate(
        {"operation": name, "source": source, **parameters}
    )


def published_index_table(pool):
    lake, workspace = pool
    added = bound_tool(pool).run(add_arguments(), ExecutionContext("add index")).output
    assert added.status is ResultStatus.COMPUTED
    workspace.record(
        "table",
        ArtifactKind.VALUE,
        added,
        inputs=("konut_kredisi_ve_faiz",),
    )
    return lake, workspace, added


def test_rebase_adds_hand_calculated_index_column_and_is_independently_verifiable(pool):
    lake, workspace, source = published_index_table(pool)
    before = source.digest()
    result = (
        bound_tool(pool)
        .run(
            operation(
                "rebase",
                column=CPI_ID,
                reference_period="2021-06-30",
                new_base=200.0,
            ),
            ExecutionContext("rebase index"),
        )
        .output
    )
    assert result.status is ResultStatus.COMPUTED
    assert result.values[: len(source.values)] == source.values
    label = f"{CPI_ID} rebased, 2021-06-30=200"
    actual = [value.value for value in result.values if value.label == label]
    expected = [old / CPI[-1] * 200.0 for old in CPI]
    assert actual == pytest.approx(expected)
    assert workspace.value_of("table").digest() == before
    assert result.parameters["rebasing"]["reference_value"] == CPI[-1]
    assert [record.operation for record in result.evidence.transformations][-2:] == [
        "add_series",
        "rebase",
    ]
    assert result_faults({"rebased": result}, lake.connection) == {}

    altered = result.model_copy(
        update={
            "values": [
                result.values[0].model_copy(update={"value": result.values[0].value + 1.0}),
                *result.values[1:],
            ]
        }
    )
    assert result_faults({"altered": altered}, lake.connection)


def test_align_and_filter_select_existing_cells_and_record_their_policies(pool):
    lake, workspace = pool
    source = workspace.value_of("konut_kredisi_ve_faiz")
    before = source.digest()
    period_labels = []
    for value in source.values:
        if value.period is not None and value.label not in period_labels:
            period_labels.append(value.label)
    assert len(period_labels) >= 2

    aligned_run = bound_tool(pool).run(
        operation(
            "align",
            source="konut_kredisi_ve_faiz",
            columns=period_labels[:2],
            join="inner",
        ),
        ExecutionContext("align exact periods"),
    )
    assert aligned_run.output is not None, aligned_run
    aligned = aligned_run.output
    assert aligned.status is ResultStatus.COMPUTED
    assert aligned.parameters["alignment"]["join"] == "inner_exact_period"
    assert aligned.parameters["alignment"]["fill"] == "none"
    assert all(value in source.values for value in aligned.values)
    assert result_faults({"aligned": aligned}, lake.connection) == {}

    filtered = (
        bound_tool(pool)
        .run(
            operation(
                "filter",
                source="konut_kredisi_ve_faiz",
                start_period="2021-02-28",
                end_period="2021-04-30",
            ),
            ExecutionContext("filter periods"),
        )
        .output
    )
    assert filtered.status is ResultStatus.COMPUTED
    assert {value.period.end for value in filtered.values} == set(MONTHS[1:4])
    assert all(value in source.values for value in filtered.values)
    assert filtered.coverage.start == date(2021, 2, 1)
    assert filtered.coverage.end == MONTHS[3]
    assert filtered.parameters["filter"]["predicate"] == "period_end_inclusive"
    assert filtered.samples is None
    assert workspace.value_of("konut_kredisi_ve_faiz").digest() == before
    assert result_faults({"filtered": filtered}, lake.connection) == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "filter", "source": "table"},
        {
            "operation": "filter",
            "source": "table",
            "start_period": "2021-06-30",
            "end_period": "2021-01-31",
        },
        {
            "operation": "align",
            "source": "table",
            "columns": ["a", "b"],
            "join": "left",
        },
        {
            "operation": "align",
            "source": "table",
            "columns": ["a", "b"],
            "join": "inner",
            "anchor_column": "a",
        },
        {
            "operation": "rebase",
            "source": "table",
            "column": "index",
            "reference_period": "2021-01-31",
            "new_base": 100.0,
            "sql": "SELECT *",
        },
    ],
)
def test_new_operation_arguments_fail_closed(payload):
    with pytest.raises(ValidationError):
        TableTransformArguments.model_validate(payload)


def test_incompatible_rebase_abstains_without_publishing_numbers(pool):
    _, _, _ = published_index_table(pool)
    result = (
        bound_tool(pool)
        .run(
            operation(
                "rebase",
                column=CPI_ID,
                reference_period="2020-12-31",
                new_base=100.0,
            ),
            ExecutionContext("bad reference"),
        )
        .output
    )
    assert result.status is ResultStatus.ABSTAINED
    assert result.values == []
    assert "no value at reference period" in result.reason
