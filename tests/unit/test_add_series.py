"""M5-20: generic monthly joins preserve published state and their proof boundary."""

import json
from dataclasses import replace
from datetime import date

import pytest
from pydantic import ValidationError
from test_co_movement import lake as lake
from test_turn_two import CPI_ID, CPI_SEMANTICS, MONTHS, index, transform
from test_turn_two import pool as pool

from kkb_agent.agent import AnswerStatus, ExecutionContext, Session, ToolRegistry
from kkb_agent.agent.presentation import period_table
from kkb_agent.agent.verifier import result_faults
from kkb_agent.analytics.table_series import SeriesAdditionRefused, add_monthly_series
from kkb_agent.core import (
    DIMENSIONLESS,
    CumulativeKind,
    Frequency,
    ResultStatus,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.ingest.prepared_series import prepared_series_names
from kkb_agent.lakehouse.records import Observation
from kkb_agent.llm import scripted
from kkb_agent.tools import make_table_transform_tool
from kkb_agent.tools.table_transform import TableTransformArguments


def source_of(pool):
    return pool[1].value_of("konut_kredisi_ve_faiz")


def add(source, observations=None, semantics=CPI_SEMANTICS, series_id=CPI_ID):
    return add_monthly_series(
        source, index() if observations is None else observations, semantics, series_id=series_id
    )


def arguments(**changes):
    return TableTransformArguments.model_validate(
        {
            "operation": "add_series",
            "source": "konut_kredisi_ve_faiz",
            "series_id": CPI_ID,
            **changes,
        }
    )


def bound_tool(pool):
    lake, workspace = pool
    return make_table_transform_tool(
        lake.connection,
        workspace,
        lineage=lake.lineage,
        series_names=prepared_series_names(lake.connection),
    )


def test_generic_monthly_series_uses_its_own_units_and_source_periods(pool):
    source = source_of(pool)
    source_before = source.model_dump_json()
    semantics = replace(CPI_SEMANTICS, unit="TRY", observation=StockFlow.STOCK, base_year=None)
    joined = add(source, semantics=semantics, series_id="TEST:deposits")
    assert [v.period.end for v in joined.values] == MONTHS
    assert all(v.label == "TEST:deposits" and v.unit == "TRY" for v in joined.values)
    assert joined.transformation.parameters["source_rows"] == 6
    assert source.model_dump_json() == source_before


def test_missing_zero_and_outside_observations_are_distinguished(pool):
    observations = [
        Observation(date(2020, 12, 1), date(2020, 12, 31), 88.0),
        *index([100.0, None, 0.0, 101.0, 100.0, 102.5]),
        Observation(date(2021, 7, 1), date(2021, 7, 31), 111.0),
    ]
    joined = add(source_of(pool), observations)
    assert [v.period.end for v in joined.values] == [MONTHS[0], *MONTHS[2:]]
    assert joined.values[1].value == 0.0
    assert joined.missing_periods == (MONTHS[1],)
    assert joined.transformation.parameters["outside_table_periods"] == 2
    assert joined.transformation.parameters["base_year"] == 2025
    assert joined.transformation.parameters["fill"] == "none"


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "wrong_start",
        "wrong_end",
        "nonfinite",
        "one_match",
        "no_match",
        "source_duplicate",
        "source_weekly",
        "column_collision",
        "unknown_semantics",
        "weekly",
        "cumulative",
    ],
)
def test_refuses_ambiguous_or_incompatible_joins(pool, case):
    source = source_of(pool)
    observations = index()
    semantics = CPI_SEMANTICS
    identity = CPI_ID
    if case == "duplicate":
        observations.append(observations[0])
    elif case == "wrong_start":
        observations[0] = replace(observations[0], period_start=date(2021, 1, 2))
    elif case == "wrong_end":
        observations[0] = replace(observations[0], period_end=date(2021, 1, 30))
    elif case == "nonfinite":
        observations[0] = replace(observations[0], value=float("nan"))
    elif case == "one_match":
        observations = observations[:1]
    elif case == "no_match":
        observations = []
    elif case == "source_duplicate":
        dated = next(v for v in source.values if v.period is not None and v.unit != DIMENSIONLESS)
        source = source.model_copy(update={"values": [*source.values, dated]})
    elif case == "source_weekly":
        dated = next(v for v in source.values if v.period is not None and v.unit != DIMENSIONLESS)
        changed = dated.model_copy(
            update={"period": dated.period.model_copy(update={"frequency": Frequency.WEEKLY})}
        )
        source = source.model_copy(
            update={"values": [changed if v is dated else v for v in source.values]}
        )
    elif case == "column_collision":
        identity = source.values[0].label
    elif case == "unknown_semantics":
        semantics = replace(semantics, cumulative=CumulativeKind.UNKNOWN)
    elif case == "weekly":
        semantics = replace(semantics, frequency=Frequency.WEEKLY, anchor=WeeklyAnchor.FRIDAY)
    else:
        semantics = replace(
            semantics, observation=StockFlow.FLOW, cumulative=CumulativeKind.YEARLY_RESET
        )
    with pytest.raises(SeriesAdditionRefused):
        add(source, observations, semantics, identity)


def test_an_unresolved_source_column_does_not_block_a_resolved_addition(pool):
    # Operation-scoped semantics: the join reads months only. The new column must
    # be resolved; what the source left unresolved is not this join's decision.
    source = source_of(pool).model_copy(
        update={"unresolved_semantics": ["source unit unconfirmed"]}
    )
    joined = add(source)
    assert [v.period.end for v in joined.values] == MONTHS
    with pytest.raises(SeriesAdditionRefused):
        add(source, semantics=replace(CPI_SEMANTICS, cumulative=CumulativeKind.UNKNOWN))


@pytest.mark.parametrize(
    "extra",
    [
        {"column": "credit"},
        {"index_series_id": CPI_ID},
        {"reference_period": "2025-12-31"},
        {"sql": "SELECT *"},
        {"path": "data.csv"},
        {"series_id": ""},
        {"source": "../other"},
    ],
)
def test_operation_specific_arguments_reject_extras(extra):
    with pytest.raises(ValidationError):
        arguments(**extra)


def test_existing_deflate_arguments_stay_flat_and_closed():
    original = transform().model_dump(mode="json")
    assert original["operation"] == "deflate" and "root" not in original
    with pytest.raises(ValidationError):
        TableTransformArguments.model_validate({**original, "series_id": CPI_ID})


def test_tool_preserves_the_table_and_records_recheckable_evidence(pool):
    lake, _ = pool
    source = source_of(pool)
    result = bound_tool(pool).run(arguments(), ExecutionContext("add CPI")).output
    assert result.status is ResultStatus.COMPUTED
    assert result.values[: len(source.values)] == source.values
    assert result.coverage == source.coverage
    assert result_faults({"added": result}, lake.connection) == {}
    assert [t.operation for t in result.evidence.transformations] == [
        "align_weekly_to_monthly",
        "add_series",
    ]
    old_table, new_table = period_table(source), period_table(result)
    assert new_table.columns[:-1] == old_table.columns
    assert [(p, cells[:-1]) for p, cells in new_table.rows] == list(old_table.rows)


def test_bad_references_and_tampered_source_stop_before_addition(pool):
    lake, workspace = pool
    tool = bound_tool(pool)
    context = ExecutionContext("add CPI")
    assert tool.run(arguments(source="absent"), context).error_category == "workspace_reference"
    assert tool.run(arguments(series_id="absent"), context).error_category == "series_unknown"
    # A stored observation that no longer agrees with the published source is rejected.
    lake.connection.execute(
        "UPDATE silver_observations SET value = value + 123 WHERE series_id != ?", [CPI_ID]
    )
    assert tool.run(arguments(), context).error_category == "workspace_evidence"
    assert workspace.names() == ["konut_kredisi_ve_faiz"]


def test_third_turn_publishes_added_column_and_keeps_previous_tables(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    for question, args, name in [
        ("Krediyi enflasyondan arındır.", transform(), "konut_kredisi_ve_faiz_reel"),
        (
            "TÜFE sütununu ekle.",
            arguments(source="konut_kredisi_ve_faiz_reel"),
            "kredi_faiz_reel_endeks",
        ),
    ]:
        plan = {
            "question": question,
            "steps": [
                {
                    "step_id": "step",
                    "tool": "table_transform",
                    "arguments": args.model_dump(mode="json"),
                }
            ],
        }
        before = {n: workspace.value_of(n).digest() for n in workspace.names()}
        answer = Session(scripted(json.dumps(plan), "Tablo hazırlandı."), registry).answer(
            question, lake.connection, workspace=workspace, remember=name
        )
        assert answer.answer.status is AnswerStatus.ACCEPTED
        assert all(workspace.value_of(n).digest() == digest for n, digest in before.items())
        assert len(answer.tables) == 1
    final = workspace.value_of("kredi_faiz_reel_endeks")
    assert len(period_table(final).columns) == 6
    assert [t.operation for t in final.evidence.transformations] == [
        "align_weekly_to_monthly",
        "deflate",
        "add_series",
    ]
    assert workspace.names() == [
        "konut_kredisi_ve_faiz",
        "konut_kredisi_ve_faiz_reel",
        "kredi_faiz_reel_endeks",
    ]


def test_tool_records_missing_cells_without_changing_rows(pool):
    lake, _ = pool
    source = source_of(pool)
    lake.connection.execute(
        "UPDATE silver_observations SET value = NULL WHERE series_id = ? AND period_end = ?",
        [CPI_ID, MONTHS[1]],
    )
    result = bound_tool(pool).run(arguments(), ExecutionContext("add CPI")).output
    assert result.status is ResultStatus.COMPUTED
    before, after = period_table(source), period_table(result)
    assert [(p, values[:-1]) for p, values in after.rows] == list(before.rows)
    assert after.rows[1][1][-1] == ""
    assert result.parameters["added_series"]["missing_periods"] == ["2021-02-28"]
    assert any("empty, never filled" in warning for warning in result.warnings)
    assert result_faults({"added": result}, lake.connection) == {}


def test_planner_schema_exposes_separate_closed_operation_objects(pool):
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    schema = registry.descriptions()[0]["arguments"]
    assert schema["discriminator"]["propertyName"] == "operation"
    assert set(schema["discriminator"]["mapping"]) == {
        "deflate",
        "add_series",
        "join_table",
        "rebase",
        "align",
        "filter",
    }
    definitions = schema["$defs"]
    assert set(definitions["AddSeriesArguments"]["required"]) == {
        "operation",
        "source",
        "series_id",
    }
    assert definitions["AddSeriesArguments"]["additionalProperties"] is False
    assert definitions["DeflateArguments"]["additionalProperties"] is False


def test_single_period_prose_metric_does_not_expand_visible_table_rows(pool):
    source = source_of(pool)
    dated = next(v for v in source.values if v.period is not None and v.unit != DIMENSIONLESS)
    outside = Observation(date(2020, 12, 1), date(2020, 12, 31), 88.0)
    singleton = dated.model_copy(
        update={
            "label": "single-period-summary",
            "period": dated.period.model_copy(
                update={"start": outside.period_start, "end": outside.period_end}
            ),
        }
    )
    source = source.model_copy(update={"values": [*source.values, singleton]})
    before = period_table(source)
    joined = add(source, [outside, *index()])
    displayed = period_table(source.model_copy(update={"values": [*source.values, *joined.values]}))
    assert [(p, cells[:-1]) for p, cells in displayed.rows] == list(before.rows)
    assert [value.period.end for value in joined.values] == MONTHS
    assert joined.transformation.parameters["outside_table_periods"] == 1


def test_third_turn_copied_amounts_are_not_ambiguous_with_table_ancestors(pool):
    lake, workspace = pool
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    for args, name, draft in [
        (transform(), "konut_kredisi_ve_faiz_reel", "Tablo hazırlandı."),
        (
            arguments(source="konut_kredisi_ve_faiz_reel"),
            "kredi_faiz_reel_endeks",
            "Şubat 2021'de nominal bakiye 990 milyon TL, reel bakiye 1.025 milyon TL oldu.",
        ),
    ]:
        question = "Mevcut tabloyu koruyarak dönüştür."
        plan = {
            "question": question,
            "steps": [
                {
                    "step_id": "step",
                    "tool": "table_transform",
                    "arguments": args.model_dump(mode="json"),
                }
            ],
        }
        provider = scripted(json.dumps(plan), draft)
        answer = Session(provider, registry, deterministic_presentation=False).answer(
            question, lake.connection, workspace=workspace, remember=name
        )
        assert answer.answer.status is AnswerStatus.ACCEPTED, answer.answer
    writer_context = provider.seen[1][1].content
    assert "[konut_kredisi_ve_faiz]" not in writer_context
    assert "[konut_kredisi_ve_faiz_reel]" not in writer_context
    assert "[kredi_faiz_reel_endeks]" in writer_context
    assert len(workspace.names()) == 3


def test_equal_unrelated_result_is_not_hidden_by_ancestor_narrowing(pool):
    lake, workspace = pool
    source = source_of(pool)
    workspace.publish(workspace.preview("unrelated_analysis", source))
    registry = ToolRegistry()
    registry.register(bound_tool(pool))
    args = arguments()
    question = "Endeks sütununu ekle."
    plan = {
        "question": question,
        "steps": [
            {
                "step_id": "step",
                "tool": "table_transform",
                "arguments": args.model_dump(mode="json"),
            }
        ],
    }
    provider = scripted(json.dumps(plan), "Tablo hazırlandı.")
    answer = Session(provider, registry, deterministic_presentation=False).answer(
        question, lake.connection, workspace=workspace, remember="added"
    )
    assert answer.answer.status is AnswerStatus.ACCEPTED
    assert "[unrelated_analysis]" in provider.seen[1][1].content
    assert "[konut_kredisi_ve_faiz]" not in provider.seen[1][1].content
    assert workspace.value_of("unrelated_analysis").digest() == source.digest()
