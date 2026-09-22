"""M2-14/M5-20 tool boundary for trusted unary table transformations."""

from datetime import date

import pytest
from pydantic import ValidationError
from test_add_series import arguments as add_arguments
from test_add_series import bound_tool
from test_co_movement import CREDIT, TOTAL_ID
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


#: The balance's own period change: the one other column of this pool that shares the
#: balance's unit, scale and measure, which is all `combine` asks of the columns it adds.
CHANGE_LABEL = f"{TOTAL_ID} change (lag 1)"
GROUP = "3 aya kadar TP mevduat"


def published_summable_table(pool):
    """Publish a table with two columns that can be added together.

    The pool's own columns are a balance, a rate and an index, and no two of them share
    unit, scale and measure. The balance's period change does, and it has no January, so
    it also gives the operation a period one of its columns genuinely lacks.
    """
    lake, workspace = pool
    changed = (
        bound_tool(pool)
        .run(
            operation("change", source="konut_kredisi_ve_faiz", column=TOTAL_ID, kind="difference"),
            ExecutionContext("add the monthly change"),
        )
        .output
    )
    assert changed.status is ResultStatus.COMPUTED
    workspace.record("table", ArtifactKind.VALUE, changed, inputs=("konut_kredisi_ve_faiz",))
    return lake, workspace, changed


def test_combine_adds_the_hand_calculated_group_total_and_is_independently_verifiable(pool):
    """Live 2026-09-22: a reader's group is the sum of columns the table already has."""
    lake, workspace, source = published_summable_table(pool)
    before = source.digest()
    result = (
        bound_tool(pool)
        .run(
            operation("combine", columns=[TOTAL_ID, CHANGE_LABEL], label=GROUP),
            ExecutionContext("sum two columns into one group"),
        )
        .output
    )
    assert result.status is ResultStatus.COMPUTED
    assert result.values[: len(source.values)] == source.values
    totals = {value.period.end: value.value for value in result.values if value.label == GROUP}
    assert totals == {
        end: CREDIT[position + 1] + (CREDIT[position + 1] - CREDIT[position])
        for position, end in enumerate(MONTHS[1:])
    }
    combination = result.parameters["combination"]
    assert combination["columns"] == [TOTAL_ID, CHANGE_LABEL]
    assert combination["period_rows"] == len(MONTHS) - 1
    assert combination["fill"] == "none"
    assert [record.operation for record in result.evidence.transformations][-2:] == [
        "change",
        "combine",
    ]
    assert workspace.value_of("table").digest() == before
    assert result_faults({"combined": result}, lake.connection) == {}

    altered = result.model_copy(
        update={
            "values": [
                *result.values[:-1],
                result.values[-1].model_copy(update={"value": result.values[-1].value + 1.0}),
            ]
        }
    )
    assert result_faults({"altered": altered}, lake.connection)


def test_a_month_one_column_lacks_has_no_group_total_and_is_reported(pool):
    """January has a balance but no change: its group total is not the balance alone."""
    _, _, _ = published_summable_table(pool)
    run = bound_tool(pool).run(
        operation("combine", columns=[TOTAL_ID, CHANGE_LABEL], label=GROUP),
        ExecutionContext("sum two columns into one group"),
    )
    result = run.output
    ends = {value.period.end for value in result.values if value.label == GROUP}
    assert ends == set(MONTHS[1:]) and MONTHS[0] not in ends
    assert result.parameters["combination"]["periods_missing_a_column"] == 1
    assert any("never read as zero" in warning for warning in run.warnings)


def test_an_unlabelled_group_is_named_by_the_columns_it_sums(pool):
    _, _, _ = published_summable_table(pool)
    result = (
        bound_tool(pool)
        .run(
            operation("combine", columns=[TOTAL_ID, CHANGE_LABEL]),
            ExecutionContext("sum two columns into one group"),
        )
        .output
    )
    assert result.status is ResultStatus.COMPUTED
    assert any(value.label == f"{TOTAL_ID} + {CHANGE_LABEL}" for value in result.values)


def test_columns_that_do_not_share_their_semantics_abstain_without_publishing_a_total(pool):
    """The rate column is percent, not million TRY: their sum would not be a quantity."""
    _, _, source = published_summable_table(pool)
    rate = next(
        value.label
        for value in source.values
        if value.label not in (TOTAL_ID, CHANGE_LABEL) and value.period is not None
    )
    result = (
        bound_tool(pool)
        .run(
            operation("combine", columns=[TOTAL_ID, rate]),
            ExecutionContext("sum a balance and a rate"),
        )
        .output
    )
    assert result.status is ResultStatus.ABSTAINED
    assert result.values == []
    assert "do not share one unit" in result.reason


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
        {"operation": "combine", "source": "table", "columns": ["a"]},
        {"operation": "combine", "source": "table", "columns": ["a", "a"]},
        {"operation": "combine", "source": "table", "columns": ["a", "b"], "label": "a\nb"},
        {"operation": "combine", "source": "table", "columns": ["a", "b"], "label": "  "},
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


def test_a_window_that_starts_later_still_has_its_first_change(pool):
    """Live 2026-09-22: a question asked each month's own amount over a window, and the
    window's first month came back empty because its predecessor sits outside the window.

    The store holds it. It completes the first change and appears as no row of its own.
    """
    lake, workspace, source = published_index_table(pool)
    windowed = (
        bound_tool(pool)
        .run(
            operation("filter", start_period="2021-03-31"),
            ExecutionContext("son aylar"),
        )
        .output
    )
    assert windowed.status is ResultStatus.COMPUTED
    workspace.record("windowed", ArtifactKind.VALUE, windowed, inputs=("table",))
    result = (
        bound_tool(pool)
        .run(
            operation("change", source="windowed", column=CPI_ID, kind="difference"),
            ExecutionContext("aylık değişim"),
        )
        .output
    )

    assert result.status is ResultStatus.COMPUTED, result.reason
    label = f"{CPI_ID} change (lag 1)"
    changes = {value.period.end: value.value for value in result.values if value.label == label}
    # March is the window's first month and its change is February's rise, read from the
    # store; February itself is in no row of the table.
    assert changes[date(2021, 3, 31)] == pytest.approx(CPI[2] - CPI[1])
    assert changes[date(2021, 4, 30)] == pytest.approx(CPI[3] - CPI[2])
    assert date(2021, 2, 28) not in changes
    assert not any(
        value.period is not None and value.period.end < date(2021, 3, 31) for value in result.values
    )
    recorded = result.evidence.transformations[-1].parameters
    assert recorded["periods_read_before_the_table"] == 1
    assert recorded["periods_without_predecessor"] == 0
    assert result_faults({"changed": result}, lake.connection) == {}
