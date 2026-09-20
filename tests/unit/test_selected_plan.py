"""Generic selected-source enforcement before dispatch and between steps."""

import duckdb
import pytest
from pydantic import BaseModel
from test_workspace_publication import result

from kkb_agent.agent.executor import (
    ExecutionContext,
    PlanRejected,
    ToolResult,
    ToolStatus,
    execute,
    validate_plan,
)
from kkb_agent.agent.plan import AnalyticalPlan
from kkb_agent.agent.registry import TableInput, ToolRegistry, ToolSpec
from kkb_agent.agent.selection import SelectedTable
from kkb_agent.agent.workspace import ArtifactKind, Workspace


class Args(BaseModel):
    source: str | None = None
    input_step: str | None = None


@pytest.fixture
def scope():
    with duckdb.connect(":memory:") as connection:
        workspace = Workspace.open(connection, "owned")
        artifact = workspace.record("chosen", ArtifactKind.VALUE, result())
        yield SelectedTable(workspace, "chosen", artifact.artifact_id, artifact.value_ref)


def setup(scope, *, mutate=False):
    calls = []
    registry = ToolRegistry()

    def run(args, context):
        calls.append(args)
        if mutate:
            scope.workspace.define(
                "chosen", ArtifactKind.VALUE, parameters={"changed": "yes"}, value_ref=scope.version
            )
        return ToolResult(ToolStatus.SUCCESS, "", "anomaly", output=result())

    # This synthetic non-financial declaration proves the harness uses registry
    # metadata, not hardcoded table_transform or BDDK/EVDS names.
    registry.register(
        ToolSpec(
            "anomaly",
            "fixture",
            Args,
            run,
            table_input=lambda a: TableInput(a.source, a.input_step),
        )
    )
    return registry, calls


def plan(*steps):
    return AnalyticalPlan.model_validate({"question": "fixture", "steps": list(steps)})


def step(name, *, after=(), **args):
    return {
        "step_id": name,
        "tool": "anomaly",
        "arguments": args,
        "depends_on": [args["input_step"]] if args.get("input_step") else list(after),
    }


def test_registry_declared_chain_uses_selected_source(scope):
    registry, calls = setup(scope)
    validated = validate_plan(plan(step("a", source="chosen"), step("b", input_step="a")), registry)
    outcome = execute(validated, registry, context=ExecutionContext("fixture"), selection=scope)
    assert outcome.completed and len(calls) == 2


@pytest.mark.parametrize("args", [{"source": "other"}, {}, {"source": "chosen", "input_step": "a"}])
def test_whole_invalid_plan_rejected_before_valid_prefix_runs(scope, args):
    registry, calls = setup(scope)
    with pytest.raises(PlanRejected):
        # A bare ordering edge is rejected as two finals at validation; an
        # actual typed input with invalid selected-source grounding is rejected
        # at dispatch. Neither path may run the otherwise valid prefix.
        validated = validate_plan(
            plan(step("a", source="chosen"), step("b", after=("a",), **args)), registry
        )
        execute(validated, registry, context=ExecutionContext("fixture"), selection=scope)
    assert calls == []


def test_parallel_final_calculations_are_refused_before_dispatch(scope):
    registry, calls = setup(scope)
    with pytest.raises(PlanRejected, match="final calculation steps"):
        validate_plan(plan(step("a", source="chosen"), step("b", source="chosen")), registry)
    assert calls == []


def test_ordering_dependency_does_not_consume_a_sibling_result(scope):
    registry, calls = setup(scope)
    # "b" waits for "a" but reads the selected workspace table again. Its typed
    # input does not include "a", so publishing only "b" would silently lose it.
    with pytest.raises(PlanRejected, match="final calculation steps"):
        validate_plan(
            plan(step("a", source="chosen"), step("b", source="chosen", after=("a",))), registry
        )
    assert calls == []


def test_mutated_argument_rechecked_at_dispatch(scope):
    registry, calls = setup(scope)
    validated = validate_plan(plan(step("a", source="chosen")), registry)
    scope.validate_plan(validated, registry)
    validated.steps[0].arguments.source = "other"
    with pytest.raises(PlanRejected):
        execute(validated, registry, context=ExecutionContext("fixture"), selection=scope)
    assert calls == []


def test_source_change_between_steps_stops_dispatch(scope):
    registry, calls = setup(scope, mutate=True)
    validated = validate_plan(plan(step("a", source="chosen"), step("b", input_step="a")), registry)
    outcome = execute(validated, registry, context=ExecutionContext("fixture"), selection=scope)
    assert not outcome.completed and len(calls) == 1
    assert outcome.results[1].error_category == "SelectionError"
