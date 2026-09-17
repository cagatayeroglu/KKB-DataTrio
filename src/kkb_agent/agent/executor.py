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

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from kkb_agent.agent.plan import AnalyticalPlan, ClarificationReason, PlanStep
from kkb_agent.agent.registry import ArgumentsRejected, RegistryError, ToolRegistry

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

    max_steps: int = 8
    max_plan_repairs: int = 2
    max_tool_retries: int = 1


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
    plan: AnalyticalPlan, registry: ToolRegistry, *, budget: Budget = DEFAULT_BUDGET
) -> ValidatedPlan:
    """Decide whether a proposed plan may run, and in what order."""
    if len(plan.steps) > budget.max_steps:
        raise PlanRejected(
            f"Plan has {len(plan.steps)} steps; the budget allows {budget.max_steps}",
            category=RejectionCategory.STEP_BUDGET,
        )

    seen: set[str] = set()
    for step in plan.steps:
        if step.step_id in seen:
            raise PlanRejected(
                f"Duplicate step id {step.step_id!r}",
                category=RejectionCategory.STRUCTURE,
            )
        seen.add(step.step_id)

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

    # Only the last computed result is answered and published. A second
    # unconsumed calculation would be silently discarded, so refuse the plan and
    # let the planner combine conditions or chain the steps instead (M11-11).
    consumed = {dependency for step in plan.steps for dependency in step.depends_on}
    final = [
        step.step_id
        for step in plan.steps
        if step.step_id not in consumed and not registry.get(step.tool).discovery_only
    ]
    if len(final) > 1:
        raise PlanRejected(
            f"Plan has {len(final)} final calculation steps ({', '.join(final)}); only one "
            "final result is answered and published. Express every condition in one "
            "operation (for example table_co_movement when_column/when_direction) or make "
            "each later step depend on the earlier one",
            category=RejectionCategory.STRUCTURE,
        )

    return ValidatedPlan(plan.question, tuple(_ordered(plan, validated)), plan.clarification)


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
            continue
        result = _run_step(validated, registry, context, budget, selection)
        results.append(result)
        if result.status is ToolStatus.SUCCESS:
            context.outputs[validated.step.step_id] = result.output
        elif result.status is ToolStatus.FAILURE:
            stopped = True

    return ExecutionOutcome(tuple(results), completed=not stopped)


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
