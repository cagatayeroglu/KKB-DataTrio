"""One loop: the model decides, the tools run, the observations come back raw.

This replaces the plan-validate-execute-continue arrangement with a single turn
the model drives. It exists because the old shape spent its refusals on the
model's strategy rather than on anything unsafe: a plan that searched the
catalogue and read a named PDF in one go was refused for mixing phases, a plan
that named a step it had not run yet was healed by the harness, and a tool that
refused at runtime started a separate repair machine. Every one of those decided
*how* to work, which is the model's job.

What the harness does here is narrow and mechanical:

* dispatch an action to the tool the model named,
* hand the result back as it is, success or failure,
* count what has been spent.

It decides nothing about order, phase, sufficiency or when a question is
answered. Those are stated in the system prompt and left to the model.

Context is the model's too. Each iteration it may write `state`: a note to its
own next turn. What travels forward is that note plus the observations of the
last iteration, not a projection the harness chose. Results themselves never
expire — every action has an id and its output stays in the workspace, so a
later action reads it by name instead of carrying its bytes.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.observer import Tracer
from kkb_agent.agent.registry import ArgumentsRejected, ToolRegistry
from kkb_agent.llm.provider import Completion, LLMProvider, Message, Role, ToolCall


class Action(BaseModel):
    """One tool the model wants run.

    `id` is how a later action refers to what this one produced. Nothing checks
    that the id is new or that a referenced id exists: a tool that cannot find
    its input says so, and that sentence is worth more to the model than a
    refusal written by a validator that never saw the data.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    #: A choice made on the reader's behalf, shown under the answer.
    note: str | None = Field(default=None, max_length=400)


class AgentStep(BaseModel):
    """What the model decides this iteration.

    Nothing here is exclusive. A step may carry actions and a state note; it may
    say it is done and name what to publish. The only reading the loop makes is
    the obvious one: run whatever actions are here, and stop when told to stop.
    """

    model_config = ConfigDict(extra="ignore")

    #: The model's note to its own next turn. This is the memory it keeps.
    state: str | None = Field(default=None, max_length=8000)
    actions: list[Action] = Field(default_factory=list)
    done: bool = False
    #: Which result the reader should see. Absent, the last computed one is used.
    publish: str | None = Field(default=None, max_length=64)
    #: Asked only when the model genuinely cannot tell what is wanted.
    ask: str | None = Field(default=None, max_length=1500)
    #: Calls whose arguments could not be read, as (id, tool). Reported, never run.
    malformed: tuple[tuple[str, str], ...] = ()
    #: The answer itself, when the model wrote prose instead of calling anything.
    reply: str | None = None


@dataclass(frozen=True, slots=True)
class Budget:
    """Counters, not policy. Nothing here says what a good answer looks like."""

    max_iterations: int = 8
    max_tool_calls: int = 20
    max_actions_per_iteration: int = 4
    max_wall_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_iterations < 1 or self.max_tool_calls < 1:
            raise ValueError("A loop needs at least one iteration and one call")


@dataclass(frozen=True, slots=True)
class Observation:
    """What one action produced, as the tool left it."""

    action: Action
    result: ToolResult

    @property
    def ok(self) -> bool:
        return self.result.status is ToolStatus.SUCCESS


@dataclass(slots=True)
class TurnOutcome:
    """Everything the turn produced, for the answer and for the trace."""

    observations: list[Observation] = field(default_factory=list)
    state: str | None = None
    publish: str | None = None
    ask: str | None = None
    iterations: int = 0
    #: Set when a counter ran out. The turn still answers with what it has.
    exhausted: str | None = None
    #: What the model wrote when it stopped calling tools; the answer itself.
    reply: str | None = None

    @property
    def results(self) -> dict[str, ToolResult]:
        return {item.action.id: item.result for item in self.observations}


#: How a model says it is finished when tool calls are all it can send.
FINISH: Final = "finish"


def tool_menu(registry: ToolRegistry) -> list[dict[str, Any]]:
    """The tools, plus the one that ends the turn.

    Native tool calling leaves a model two moves — call something or write prose —
    and no field for `done` or `publish`. Live 2026-09-22 it reached for a tool
    named `publish` that did not exist, which is the protocol asking for this: the
    way to stop is a call like any other.
    """
    menu: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.arguments.model_json_schema(),
            },
        }
        for spec in registry
    ]
    menu.append(
        {
            "type": "function",
            "function": {
                "name": FINISH,
                "description": (
                    "Yeterli kanitin oldugunda bunu cagir ve turu bitir. "
                    "answer: okuyucuya gidecek Turkce cevap. "
                    "publish: okuyucuya gosterilecek sonucun id'si."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "publish": {"type": "string"},
                    },
                    "required": ["answer"],
                },
            },
        }
    )
    return menu


def _describe(result: ToolResult) -> str:
    """One observation, rendered for the model. Failures read like successes."""
    body: dict[str, Any] = {"status": result.status.value}
    if result.error_category is not None:
        body["error"] = result.error_category
    if result.warnings:
        body["warnings"] = list(result.warnings)
    if result.output is not None:
        payload = result.output
        dumped = payload.model_dump() if isinstance(payload, BaseModel) else payload
        body["output"] = dumped
    return json.dumps(body, ensure_ascii=False, default=str)


def _observed(carried: list[Observation], native: bool) -> list[Message]:
    """The last iteration's results, addressed the way the calls were made.

    With native tool calling a result belongs to a call, and the pairing is the id:
    the assistant turn names what it asked for and each tool turn answers one of
    them. Flattening both into user prose lost that, so a model reading three
    results could not tell which was which. Without native calls the same
    observations travel as text, which is what the JSON envelope expects.
    """
    if not carried:
        return []
    if not native:
        return [
            Message(Role.USER, f"{item.action.id} ({item.action.tool}): {_describe(item.result)}")
            for item in carried
        ]
    asked = Message(
        Role.ASSISTANT,
        "",
        tool_calls=tuple(
            ToolCall(
                id=item.action.id,
                name=item.action.tool,
                arguments=json.dumps(item.action.arguments, ensure_ascii=False),
            )
            for item in carried
        ),
    )
    answers = [
        Message(Role.TOOL, _describe(item.result), tool_call_id=item.action.id) for item in carried
    ]
    return [asked, *answers]


def _asked_for(completion: Completion) -> AgentStep | None:
    """The model's decision, however the platform let it express one.

    A server with native tool calling answers with `tool_calls` and no prose; one
    without answers with the JSON object the schema asked for. Both say the same
    thing, so both are read the same way rather than one being the supported path
    and the other a fallback that behaves differently.
    """
    if completion.tool_calls:
        actions: list[Action] = []
        malformed: list[tuple[str, str]] = []
        for index, call in enumerate(completion.tool_calls):
            identifier = call.id or f"a{index + 1}"
            try:
                arguments = json.loads(call.arguments or "{}")
            except json.JSONDecodeError:
                # Unreadable arguments are not empty arguments. Running the tool on its
                # defaults would answer a request the model never made, and the model
                # would never learn that what it sent could not be read.
                malformed.append((identifier, call.name))
                continue
            if not isinstance(arguments, dict):
                malformed.append((identifier, call.name))
                continue
            actions.append(Action(id=identifier, tool=call.name, arguments=arguments))
        finished = next((a for a in actions if a.tool == FINISH), None)
        if finished is not None:
            return AgentStep(
                done=True,
                reply=str(finished.arguments.get("answer") or "").strip() or None,
                publish=str(finished.arguments.get("publish") or "") or None,
                actions=[a for a in actions if a.tool != FINISH],
                malformed=tuple(malformed),
            )
        return AgentStep(actions=actions, malformed=tuple(malformed))
    if isinstance(completion.parsed, AgentStep):
        return completion.parsed
    if completion.text.strip():
        # Native tool calling gives a model two ways to answer and only two: call
        # something, or say something. There is no field left for `done`, so prose
        # with no call is the finish — and it is the answer, which is why no second
        # writer call is needed for it. Live 2026-09-22 the model answered well on
        # its third turn and the loop read that as "no decision", kept going, and
        # spent its budget repeating work it had already done.
        return AgentStep(done=True, reply=completion.text.strip())
    return None


def run_turn(
    question: str,
    *,
    provider: LLMProvider,
    registry: ToolRegistry,
    instructions: str,
    model: str | None = None,
    budget: Budget | None = None,
    context: Mapping[str, str] = {},
    published: Mapping[str, object] = {},
    tracer: Tracer | None = None,
) -> TurnOutcome:
    """Drive one question to the point where the model says it can answer.

    `context` is whatever the caller already knows — the conversation so far, the
    table the reader has selected — passed through without interpretation. The
    loop adds nothing to it and removes nothing from it.
    """
    limits = budget or Budget()
    outcome = TurnOutcome()
    started = time.monotonic()
    calls = 0
    # Seeded with what earlier turns published, under the names they carry, so a
    # tool given "analiz_2" finds it without this turn having to read it again.
    workspace: dict[str, object] = dict(published)
    searched: set[str] = set()
    carried: list[Observation] = []
    #: The native exchange so far: what was asked for and what came back.
    history: list[Message] = []

    menu = tool_menu(registry)
    #: Whether the platform answered the last iteration with real tool calls. A result
    #: is handed back the way the call was made, so a server that speaks the protocol
    #: sees its own call ids and one that does not still gets readable text.
    native = False
    preamble = [Message(Role.SYSTEM, instructions)]
    preamble += [Message(Role.SYSTEM, text) for text in context.values() if text]

    while True:
        if outcome.iterations >= limits.max_iterations:
            outcome.exhausted = "iterations"
            break
        if time.monotonic() - started > limits.max_wall_seconds:
            outcome.exhausted = "time"
            break

        # With native tool calling the exchange itself is the memory: the assistant
        # turns that made the calls and the tool turns that answered them accumulate,
        # exactly as the protocol expects. Carrying only the last iteration made the
        # model amnesiac two steps back — live 2026-09-22 it searched, read, then
        # searched and read the same series again and spent its budget on work it had
        # already done. Without native calls the model keeps its own `state` note
        # instead, so only the newest observations need repeating.
        history.extend(_observed(carried, native))
        messages = [*preamble, Message(Role.USER, question)]
        if outcome.state:
            messages.append(Message(Role.ASSISTANT, outcome.state))
        messages.extend(history if native else _observed(carried, native))

        if tracer is None:
            completion = provider.complete(messages, model=model, schema=AgentStep, tools=menu)
        else:
            with tracer.span("loop", "iteration") as span:
                span.set(
                    iteration=outcome.iterations + 1,
                    prompt_bytes=sum(len(m.content.encode()) for m in messages),
                    carried=len(carried),
                )
                completion = provider.complete(messages, model=model, schema=AgentStep, tools=menu)
                span.set(model=completion.model, provider_attempts=completion.attempts)
        outcome.iterations += 1
        native = bool(completion.tool_calls)
        step = _asked_for(completion)
        if tracer is not None and step is not None:
            tracer.event(
                "loop",
                "decision",
                iteration=outcome.iterations,
                actions=[f"{a.id}:{a.tool}" for a in step.actions],
                done=step.done,
                publish=step.publish,
                asked=step.ask is not None,
                native=bool(completion.tool_calls),
                malformed=[f"{i}:{n}" for i, n in step.malformed],
                detail=step.state,
            )
        if step is None:
            outcome.exhausted = "undecided"
            break
        if step.state:
            outcome.state = step.state
        if step.publish:
            outcome.publish = step.publish
        if step.reply:
            outcome.reply = step.reply
        if step.ask:
            outcome.ask = step.ask
            break
        if not step.actions and not step.malformed:
            break

        carried = []
        for identifier, tool in step.malformed:
            # The model has to see that what it sent could not be read, or it will
            # send it again unchanged.
            refused = Observation(
                Action(id=identifier, tool=tool),
                ToolResult(
                    ToolStatus.FAILURE,
                    identifier,
                    tool,
                    error_category="arguments",
                    warnings=(
                        "Bu çağrının argümanları geçerli JSON değildi; araç "
                        "çalıştırılmadı. Argümanları yeniden yaz.",
                    ),
                ),
            )
            outcome.observations.append(refused)
            carried.append(refused)
        for action in step.actions[: limits.max_actions_per_iteration]:
            if calls >= limits.max_tool_calls:
                outcome.exhausted = "tool calls"
                break
            calls += 1
            item = Observation(action, _dispatch(action, registry, question, workspace, searched))
            if item.ok and item.result.output is not None:
                workspace[action.id] = item.result.output
            outcome.observations.append(item)
            carried.append(item)
            if tracer is not None:
                tracer.event(
                    "tool",
                    action.tool,
                    status="ok" if item.ok else "failed",
                    step_id=action.id,
                    tool=action.tool,
                    error_category=item.result.error_category,
                    warnings=list(item.result.warnings),
                    evidence=item.result.evidence,
                    detail=_describe(item.result)[:4000],
                )
        if outcome.exhausted or step.done:
            # `done` beside actions means finish after them, not instead of them: the
            # work was asked for and dropping it silently loses a turn's evidence.
            break

    if tracer is not None:
        tracer.event(
            "loop",
            "finished",
            iterations=outcome.iterations,
            tool_calls=calls,
            exhausted=outcome.exhausted,
            published=outcome.publish,
        )
    return outcome


def _dispatch(
    action: Action,
    registry: ToolRegistry,
    question: str,
    workspace: dict[str, object],
    searched: set[str],
) -> ToolResult:
    """Run one action. Every way it can go wrong is a result, never an exception."""
    if action.tool not in registry:
        return ToolResult(
            ToolStatus.FAILURE,
            action.id,
            action.tool,
            error_category="unknown_tool",
            warnings=(
                f"No tool is named {action.tool!r}. The ones there are: "
                + ", ".join(sorted(spec.name for spec in registry)),
            ),
        )
    spec = registry.get(action.tool)
    try:
        parsed = spec.parse(dict(action.arguments))
    except ArgumentsRejected as error:
        return ToolResult(
            ToolStatus.FAILURE,
            action.id,
            action.tool,
            error_category="arguments",
            warnings=(str(error),),
        )
    context = ExecutionContext(question, outputs=dict(workspace), searched=frozenset(searched))
    try:
        result = spec.run(parsed, context)
    except Exception as error:  # noqa: BLE001 - a tool fault is an observation
        return ToolResult(
            ToolStatus.FAILURE,
            action.id,
            action.tool,
            error_category=type(error).__name__,
            warnings=(str(error)[:400],),
        )
    searched.update(context.searched)
    return result


__all__ = [
    "Action",
    "AgentStep",
    "Budget",
    "Observation",
    "TurnOutcome",
    "run_turn",
    "tool_menu",
]
