"""Validation and bounded execution (M5-04, M5-05, M5-09, M5-13).

Validation is where a proposal becomes something that may run. It checks the
tool exists, the arguments satisfy that tool's own schema, the dependencies form
an order, and the plan fits the budget. Anything that fails is refused whole:
executing the valid prefix of an invalid plan produces a partial answer nobody
asked for.

Execution is bounded on purpose. A step that fails recoverably is retried within
a small budget; a step that fails otherwise stops the run and everything
downstream is reported as not run, rather than being skipped silently.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from kkb_agent.agent.cancellation import checkpoint
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.plan import AnalyticalPlan, ClarificationReason, PlanStep
from kkb_agent.agent.registry import ArgumentsRejected, RegistryError, TableInput, ToolRegistry

if TYPE_CHECKING:
    from kkb_agent.agent.selection import SelectedTable


class RejectionCategory(StrEnum):
    STRUCTURE = "structure"
    TOOL_ARGUMENTS = "tool_arguments"
    DEPENDENCIES = "dependencies"
    SELECTED_TABLE = "selected_table"
    DISCOVERY_RULE = "discovery_rule"
    STEP_BUDGET = "step_budget"
    UNKNOWN = "unknown"


class PlanRejected(ValueError):
    """The plan may not run. The message is fed back to the planner verbatim."""

    def __init__(
        self, message: str, category: RejectionCategory = RejectionCategory.UNKNOWN
    ) -> None:
        self.category = category
        super().__init__(message)


class ToolStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class Budget:
    """Every loop in this package is bounded by one of these."""

    # A document chain (read -> join -> align -> compare) plus discovery needs
    # more than the eight steps a prepared-only question used.
    max_steps: int = 12
    max_plan_repairs: int = 2
    max_tool_retries: int = 1
    # One initial catalog phase and, only when necessary, one auxiliary phase.
    max_discovery_rounds: int = 2

    def __post_init__(self) -> None:
        if self.max_discovery_rounds not in (0, 1, 2):
            raise ValueError("Catalog discovery permits at most two rounds")


#: Frozen defaults, so a shared budget cannot be mutated by one caller.
DEFAULT_BUDGET = Budget()


@dataclass(slots=True)
class ExecutionContext:
    """What a tool is allowed to see. Deliberately small."""

    question: str
    outputs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: ToolStatus
    step_id: str
    tool: str
    output: object = field(default=None, repr=False)
    error_category: str | None = None
    recoverable: bool = False
    warnings: tuple[str, ...] = ()
    #: Lineage node for what this step produced, when the tool recorded one.
    evidence: str | None = None

    def __post_init__(self) -> None:
        if self.status is ToolStatus.SUCCESS and self.error_category is not None:
            raise ValueError("A successful result cannot carry an error category")
        if self.status is ToolStatus.FAILURE and self.error_category is None:
            raise ValueError("A failed result must name its error category")


@dataclass(frozen=True, slots=True)
class ValidatedStep:
    step: PlanStep
    arguments: BaseModel


@dataclass(frozen=True, slots=True)
class ValidatedPlan:
    """A plan whose every step is known to be runnable, in dependency order."""

    question: str
    steps: tuple[ValidatedStep, ...]
    clarification: ClarificationReason | None = None
    reply: str | None = None
    clarification_text: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    results: tuple[ToolResult, ...]
    completed: bool

    def by_step(self, step_id: str) -> ToolResult:
        for result in self.results:
            if result.step_id == step_id:
                return result
        raise KeyError(step_id)


def validate_plan(
    plan: AnalyticalPlan,
    registry: ToolRegistry,
    *,
    budget: Budget = DEFAULT_BUDGET,
    known_tables: Collection[str] | None = None,
) -> ValidatedPlan:
    """Decide whether a proposed plan may run, and in what order.

    `known_tables` are the workspace names a table argument may refer to. When
    given, every table a step names must be one of them or an earlier step of
    this plan that produces a table, declared in `depends_on`; a name that is
    neither is refused here with the published names, instead of failing at
    run time after the fetch already succeeded (E1 trace, 2026-09-19).
    """
    if len(plan.steps) > budget.max_steps:
        raise PlanRejected(
            f"Plan has {len(plan.steps)} steps; the budget allows {budget.max_steps}",
            category=RejectionCategory.STEP_BUDGET,
        )

    seen: set[str] = set()
    tools_by_id: dict[str, str] = {}
    for step in plan.steps:
        if step.step_id in seen:
            raise PlanRejected(
                f"Duplicate step id {step.step_id!r}",
                category=RejectionCategory.STRUCTURE,
            )
        seen.add(step.step_id)
        tools_by_id[step.step_id] = step.tool

    if known_tables is not None and (collisions := seen.intersection(known_tables)):
        raise PlanRejected(
            f"Step ID {sorted(collisions)[0]!r} collides with a published table name; "
            "use a fresh step ID so each table reference has one identity",
            category=RejectionCategory.DEPENDENCIES,
        )

    validated: dict[str, ValidatedStep] = {}
    for step in plan.steps:
        try:
            spec = registry.get(step.tool)
        except RegistryError as error:
            # An unregistered name is the shape a prompt injection takes.
            raise PlanRejected(
                str(error),
                category=RejectionCategory.STRUCTURE,
            ) from error
        try:
            arguments = spec.parse(step.arguments)
        except ArgumentsRejected as error:
            raise PlanRejected(
                str(error),
                category=RejectionCategory.TOOL_ARGUMENTS,
            ) from error
        if known_tables is not None and spec.table_input is not None:
            _check_table_names(
                step, spec.table_input(arguments), known_tables, tools_by_id, registry
            )
        required = spec.required_steps(arguments) if spec.required_steps is not None else ()
        for reference in required:
            if reference not in step.depends_on:
                raise PlanRejected(
                    f"Step {step.step_id!r} must declare input step {reference!r} in depends_on",
                    category=RejectionCategory.DEPENDENCIES,
                )
        for dependency in step.depends_on:
            if dependency not in seen:
                raise PlanRejected(
                    f"Step {step.step_id!r} depends on unknown step {dependency!r}",
                    category=RejectionCategory.DEPENDENCIES,
                )
            if dependency == step.step_id:
                raise PlanRejected(
                    f"Step {step.step_id!r} depends on itself",
                    category=RejectionCategory.DEPENDENCIES,
                )
        validated[step.step_id] = ValidatedStep(step, arguments)

    ordered = tuple(_ordered(plan, validated))
    # Only the last computed result is answered and published. A depends_on edge
    # orders execution but says nothing about whether the later tool actually
    # reads that result. Count only registry-declared typed inputs as consumption;
    # otherwise a planner could silence this guard with a fake ordering edge.
    consumed: set[str] = set()
    for validated_step in validated.values():
        spec = registry.get(validated_step.step.tool)
        table = spec.table_input(validated_step.arguments) if spec.table_input else None
        references = (
            tuple(
                name for name in (table.source, table.input_step, *table.others) if name is not None
            )
            if table is not None
            else ()
        )
        required = spec.required_steps(validated_step.arguments) if spec.required_steps else ()
        consumed.update(
            name
            for name in (*references, *required)
            if name in validated and name in validated_step.step.depends_on
        )
    final = [
        step.step_id
        for step in plan.steps
        if step.step_id not in consumed and not registry.get(step.tool).discovery_only
    ]
    if len(final) > 1:
        raise PlanRejected(
            f"Plan has {len(final)} final calculation steps ({', '.join(final)}); only one "
            "final result is answered and published. For compatible monthly tables, "
            "use table_transform join_table with both step IDs as source/other and both "
            "in depends_on; it keeps their units and exact-month join policy. A plain "
            "depends_on edge does not combine results. Incompatible tables and independent "
            "scalar + table outputs cannot be silently combined; clarify or separate them. "
            "For a joint condition, use one table_co_movement operation",
            category=RejectionCategory.STRUCTURE,
        )

    return ValidatedPlan(
        plan.question,
        ordered,
        plan.clarification,
        plan.reply,
        plan.clarification_text,
    )


def _check_table_names(
    step: PlanStep,
    table: TableInput | None,
    known_tables: Collection[str],
    tools_by_id: dict[str, str],
    registry: ToolRegistry,
) -> None:
    """Every table a step names is a published result or a declared earlier step."""
    if table is None:
        return
    for name in (table.source, *table.others):
        if name is None:
            continue
        if name == step.step_id:
            raise PlanRejected(
                f"Step {step.step_id!r} cannot use itself as its table",
                category=RejectionCategory.DEPENDENCIES,
            )
        if name in tools_by_id:
            if registry.get(tools_by_id[name]).discovery_only:
                raise PlanRejected(
                    f"Step {step.step_id!r} uses discovery step {name!r} as a table; "
                    "discovery output is metadata, not a table",
                    category=RejectionCategory.DEPENDENCIES,
                )
            if name not in step.depends_on:
                raise PlanRejected(
                    f"Step {step.step_id!r} uses step {name!r} as its table; "
                    f"declare {name!r} in depends_on",
                    category=RejectionCategory.DEPENDENCIES,
                )
        elif name not in known_tables:
            published = ", ".join(sorted(known_tables)) or "none"
            raise PlanRejected(
                f"Step {step.step_id!r} names table {name!r}, which is neither a published "
                f"result nor an earlier step of this plan. Published results: {published}",
                category=RejectionCategory.TOOL_ARGUMENTS,
            )


def _ordered(plan: AnalyticalPlan, validated: dict[str, ValidatedStep]) -> list[ValidatedStep]:
    """Topological order, refusing a cycle rather than picking an arbitrary start."""
    pending = {step.step_id: set(step.depends_on) for step in plan.steps}
    order: list[ValidatedStep] = []
    while pending:
        ready = sorted(name for name, needs in pending.items() if not needs)
        if not ready:
            raise PlanRejected(
                "Plan dependencies form a cycle",
                category=RejectionCategory.DEPENDENCIES,
            )
        for name in ready:
            order.append(validated[name])
            del pending[name]
        for needs in pending.values():
            needs.difference_update(ready)
    return order


def execute(
    plan: ValidatedPlan,
    registry: ToolRegistry,
    *,
    context: ExecutionContext | None = None,
    budget: Budget = DEFAULT_BUDGET,
    selection: SelectedTable | None = None,
    tracer: Tracer | None = None,
) -> ExecutionOutcome:
    """Run a validated plan in order, stopping at the first terminal failure."""
    context = context or ExecutionContext(question=plan.question)
    if selection is not None:
        selection.validate_plan(plan, registry)
    results: list[ToolResult] = []
    stopped = False

    for validated in plan.steps:
        if stopped:
            results.append(
                ToolResult(ToolStatus.NOT_RUN, validated.step.step_id, validated.step.tool)
            )
            if tracer is not None:
                tracer.event(
                    "tool",
                    validated.step.tool,
                    status="not_run",
                    step_id=validated.step.step_id,
                    reason="an earlier step failed",
                )
            continue
        checkpoint(f"tool.{validated.step.tool}")
        result = _traced_step(validated, registry, context, budget, selection, tracer)
        results.append(result)
        if result.status is ToolStatus.SUCCESS:
            context.outputs[validated.step.step_id] = result.output
        elif result.status is ToolStatus.FAILURE:
            stopped = True

    return ExecutionOutcome(tuple(results), completed=not stopped)


def _traced_step(
    validated: ValidatedStep,
    registry: ToolRegistry,
    context: ExecutionContext,
    budget: Budget,
    selection: SelectedTable | None,
    tracer: Tracer | None,
) -> ToolResult:
    """Run one step and record what it was asked for and what it returned."""
    if tracer is None:
        return _run_step(validated, registry, context, budget, selection)
    with tracer.span("tool", validated.step.tool) as span:
        arguments = validated.arguments.model_dump(mode="json")
        span.set(
            step_id=validated.step.step_id,
            tool=validated.step.tool,
            operation=arguments.get("operation") if isinstance(arguments, dict) else None,
            depends_on=list(validated.step.depends_on),
        )
        result = _run_step(validated, registry, context, budget, selection)
        span.set(
            status=result.status.value,
            warnings=len(result.warnings),
            evidence=result.evidence,
            recoverable=result.recoverable,
        )
        if result.status is ToolStatus.FAILURE:
            span.failed(result.error_category or "unknown")
        span.describe(
            "Arguments:\n"
            + json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
            + "\n\nReturned:\n"
            + tool_output_preview(result)
            + "\n\nFull output:\n"
            + tool_output_full(result)
        )
    return result


def tool_output_full(result: ToolResult) -> str:
    """Everything the step returned, as JSON, whether or not the model is shown it."""
    output = result.output
    try:
        # Models, dataclasses (a lakehouse output holds both), dates and enums
        # become plain JSON; only what has no JSON form falls back to its text.
        return json.dumps(to_jsonable_python(output, fallback=str), ensure_ascii=False, indent=2)
    except Exception:  # A trace never costs the turn; say what could not be written.
        return f"<{type(output).__name__} could not be serialized>"


def tool_output_preview(result: ToolResult) -> str:
    """What a step produced, in facts a reader can check, never the whole table."""
    lines = [f"status: {result.status.value}"]
    if result.error_category:
        lines.append(f"error_category: {result.error_category}")
    for warning in result.warnings[:6]:
        lines.append(f"warning: {warning}")
    output = getattr(result.output, "result", None) or result.output
    values = getattr(output, "values", None)
    if values is not None:
        labels = list(dict.fromkeys(str(getattr(value, "label", "")) for value in values))
        coverage = getattr(output, "coverage", None)
        lines += [
            f"result_id: {getattr(output, 'result_id', '')}",
            f"kind: {getattr(getattr(output, 'kind', None), 'value', '')}",
            f"method: {getattr(output, 'method', None)}",
            f"values: {len(values)}",
            f"columns: {', '.join(labels[:12])}",
        ]
        if coverage is not None:
            lines.append(f"coverage: {coverage.start}..{coverage.end} ({coverage.frequency.value})")
        for note in list(getattr(output, "unresolved_semantics", []))[:4]:
            lines.append(f"unresolved: {note}")
    elif output is not None:
        lines.append(f"output: {type(output).__name__}")
        for field_name in ("status", "code", "media_type"):
            value = getattr(output, field_name, None)
            if value is not None:
                lines.append(f"{field_name}: {value}")
    return "\n".join(lines)


def _run_step(
    validated: ValidatedStep,
    registry: ToolRegistry,
    context: ExecutionContext,
    budget: Budget,
    selection: SelectedTable | None,
) -> ToolResult:
    spec = registry.get(validated.step.tool)
    attempts = budget.max_tool_retries + 1
    last: ToolResult | None = None
    for _ in range(attempts):
        try:
            if selection is not None:
                selection.check()
            last = spec.run(validated.arguments, context)
        except Exception as error:  # noqa: BLE001 - a tool must not abort the run
            last = ToolResult(
                ToolStatus.FAILURE,
                validated.step.step_id,
                validated.step.tool,
                error_category=type(error).__name__,
            )
        if last.status is not ToolStatus.FAILURE or not last.recoverable:
            return replace(last, step_id=validated.step.step_id, tool=validated.step.tool)
    # Budget exhausted on a recoverable failure: report it as terminal.
    if last is None:  # pragma: no cover - attempts is always at least one
        raise PlanRejected(
            "Tool retry budget must allow at least one attempt",
            category=RejectionCategory.STEP_BUDGET,
        )
    return replace(last, step_id=validated.step.step_id, tool=validated.step.tool)
