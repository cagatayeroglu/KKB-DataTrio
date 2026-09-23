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
from kkb_agent.core import AnalyticalResult, ResultStatus

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
    max_steps: int = 16
    max_plan_repairs: int = 2
    max_tool_retries: int = 1
    #: How many times the planner may look at what its tools returned and plan again.
    #: Two allowed one initial catalogue phase and a single auxiliary one, which was
    #: sized for a planner call that cost a minute; on DeepSeek-V4.1-Flash the same
    #: call takes about two seconds, so a question that needs three or four looks —
    #: search, read what came back, search again for what it named, then analyse —
    #: no longer has to be answered from the first guess. Still bounded, and still
    #: bounded again by `max_steps`: each round must leave room for the analysis.
    max_discovery_rounds: int = 5

    def __post_init__(self) -> None:
        if not 0 <= self.max_discovery_rounds <= 8:
            raise ValueError("Catalog discovery permits at most eight rounds")


#: Frozen defaults, so a shared budget cannot be mutated by one caller.
DEFAULT_BUDGET = Budget()


@dataclass(slots=True)
class ExecutionContext:
    """What a tool is allowed to see. Deliberately small."""

    question: str
    outputs: dict[str, object] = field(default_factory=dict)
    #: Addresses a web_search step of THIS turn returned whole, which web_url may read.
    #: The person asked for a search and for what it finds; making them write the address
    #: again in a second message was a product limit, not a security one (live 2026-09-21:
    #: "TCMB Mart 2024 PPK kararını web'de ara ve özetle" found the official page and could
    #: not read it). A page's own content still cannot become a request: only a search this
    #: turn ran fills this, never a fetched document, and a locator whose query string was
    #: redacted is left out because it no longer names the resource the hit named.
    searched: frozenset[str] = frozenset()


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
    interpret: bool = True


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
    # Several steps nobody consumes used to refuse the plan ("only one final result"). The
    # plan's last result is still the table that is published; the results of the others
    # are shown to the writer beside it (`Session.answer`), so none is silently dropped,
    # which is what the refusal was there to prevent (M11-11).
    return ValidatedPlan(
        plan.question,
        ordered,
        plan.clarification,
        plan.reply,
        plan.clarification_text,
        plan.interpret,
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
    #: Steps that ran but produced nothing another step can compute from. A tool that
    #: refuses an operation returns SUCCESS carrying an ABSTAINED result (the refusal is
    #: the answer to that step), so the plan does not stop - but a step reading that table
    #: has nothing to read. Live 2026-09-21: a refused join was followed by a comparison
    #: that reported "The referenced table is unavailable or cannot be verified", naming
    #: the wrong step and hiding the refusal that actually ended the plan.
    unusable: set[str] = set()

    for validated in plan.steps:
        blocked = sorted(unusable & _reads(validated, registry))
        if stopped or blocked:
            reason = (
                f"step {blocked[0]!r} produced no computed result"
                if blocked
                else "an earlier step failed"
            )
            results.append(
                ToolResult(
                    ToolStatus.NOT_RUN,
                    validated.step.step_id,
                    validated.step.tool,
                    warnings=(reason,) if blocked else (),
                )
            )
            if tracer is not None:
                tracer.event(
                    "tool",
                    validated.step.tool,
                    status="not_run",
                    step_id=validated.step.step_id,
                    reason=reason,
                )
            if blocked:
                unusable.add(validated.step.step_id)
            continue
        checkpoint(f"tool.{validated.step.tool}")
        result = _traced_step(validated, registry, context, budget, selection, tracer)
        results.append(result)
        if result.status is ToolStatus.SUCCESS:
            context.outputs[validated.step.step_id] = result.output
            if not _is_computed(result.output):
                unusable.add(validated.step.step_id)
        elif result.status is ToolStatus.FAILURE:
            stopped = True

    return ExecutionOutcome(tuple(results), completed=not stopped and not unusable)


def analytical(output: object) -> AnalyticalResult | None:
    """The measurement in a tool's output, whether it returned one or wrapped one.

    `lakehouse` and `web_url` answer with an object that carries the result beside
    what it is for — the rows as a table, the page it was read from — because a
    rendering convenience must not become an analytical claim. Every reader of a
    result therefore has to look one level in, and a reader that does not sees no
    result at all: live 2026-09-23 a turn answered straight from `lakehouse` was
    neither published nor checked, because both the publication and the gate
    tested the wrapper for being a result and it is not one.
    """
    candidate = getattr(output, "result", output)
    return candidate if isinstance(candidate, AnalyticalResult) else None


def _is_computed(output: object) -> bool:
    """Whether a step's output is a result a later step could compute from."""
    candidate = analytical(output)
    return candidate.status is ResultStatus.COMPUTED if candidate is not None else True


def _reads(validated: ValidatedStep, registry: ToolRegistry) -> set[str]:
    """The steps this one reads: its edges, its declared table inputs, its required steps."""
    reads = set(validated.step.depends_on)
    try:
        spec = registry.get(validated.step.tool)
    except RegistryError:
        return reads
    if spec.table_input is not None:
        table = spec.table_input(validated.arguments)
        if table is not None:
            reads.update(
                name for name in (table.source, table.input_step, *table.others) if name is not None
            )
    if spec.required_steps is not None:
        reads.update(spec.required_steps(validated.arguments))
    return reads


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
