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
from collections.abc import Collection, Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus
from kkb_agent.agent.observer import MAX_ATTRIBUTE_CHARS, MAX_DETAIL_CHARS, Tracer
from kkb_agent.agent.registry import ArgumentsRejected, ToolRegistry
from kkb_agent.llm.provider import (
    Completion,
    LLMProvider,
    Message,
    ProviderError,
    Role,
    ShowsRequests,
    ToolCall,
)


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
    #: The platform's own id for this call, when it made one. It addresses the tool
    #: turn on the wire and nothing else: the model did not choose it and does not
    #: see it, so it is never the name a result is known by.
    call_id: str | None = Field(default=None, max_length=128)


class Malformed(BaseModel):
    """A call whose arguments could not be read, kept whole so it can be answered.

    The platform's own id rides along because the tool turn that reports the refusal
    has to answer the call the model actually made, and the text it sent rides along
    because a model shown `{}` for its own bad arguments cannot see what was wrong
    with them.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=64)
    call_id: str | None = Field(default=None, max_length=128)
    #: What the model sent, as it sent it. Clipped: a refusal is not a place for a
    #: whole document, and what matters is the shape of the mistake.
    sent: str | None = Field(default=None, max_length=2000)


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
    #: Calls whose arguments could not be read. Reported to the model, never run.
    malformed: tuple[Malformed, ...] = ()
    #: The answer itself, when the model wrote prose instead of calling anything.
    reply: str | None = None


@dataclass(frozen=True, slots=True)
class Budget:
    """Counters, not policy. Nothing here says what a good answer looks like."""

    max_iterations: int = 8
    max_tool_calls: int = 20
    max_actions_per_iteration: int = 4
    max_wall_seconds: float = 300.0
    #: How much of the accumulated exchange travels. A counter, like the others: the
    #: harness never chooses *what* about an observation matters, only how much room
    #: there is. Live 2026-09-23 a turn that searched the catalogue six times for a
    #: series the catalogue does not hold grew its prompt 3 KB, 49, 96, 143, 169, and
    #: the sixth request died in the transport — the reader got nothing although ten
    #: observations had come back. Sized well above the runs that work, which peaked
    #: around 30 KB.
    max_exchange_bytes: int = 96_000

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


#: How much of one observation the model is shown before it is clipped. A page or a
#: sixty-row read is worth its room; a whole document is not, and the result stays
#: addressable by its id for a second, narrower look.
MAX_OBSERVATION_CHARS: Final = 40_000

#: Where the trace's own attribute ceiling cuts a call's arguments for display. The
#: step's detail keeps them whole; this only says whether the display is complete.
MAX_TRACE_ARGUMENT_CHARS: Final = MAX_ATTRIBUTE_CHARS

#: How a model says it is finished when tool calls are all it can send.
FINISH: Final = "finish"

#: How long an answer the reader can be shown, told to the model as a fact. The
#: product's own ceiling (`api.projection.MAX_TEXT_CHARS`) is a little above it.
MAX_ANSWER_CHARS: Final = 8_000


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
                    f"answer: okuyucuya gidecek Turkce cevap, en fazla {MAX_ANSWER_CHARS} "
                    "karakter. "
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


def _describe(result: ToolResult, identifier: str | None = None) -> str:
    """One observation, rendered for the model. Failures read like successes.

    The id leads, because it is the only name by which this result can be asked
    for again. Live 2026-09-23 the model had no way to learn it: results were
    addressed by the platform's own call id, which it never sees, so when a
    follow-up asked it to add a column to the table it had just built it guessed
    `s2`, then a digest, then the call ids themselves, and spent the turn's budget
    on names that could not exist.
    """
    body: dict[str, Any] = {"status": result.status.value}
    if identifier is not None:
        body = {"id": identifier, **body}
    if result.error_category is not None:
        body["error"] = result.error_category
    if result.warnings:
        body["warnings"] = list(result.warnings)
    if result.output is not None:
        body["output"] = observed_payload(result.output)
    rendered = json.dumps(body, ensure_ascii=False, default=str)
    if len(rendered) <= MAX_OBSERVATION_CHARS:
        return rendered
    # Too long to show whole. It used to be cut at a character count, so a PDF reached
    # the model as one string of JSON that stopped mid-page: sixteen of twenty pages,
    # no word of the rest, nothing saying where a table was (live 2026-09-23, QA-23).
    # Now the structure stays whole and its leaves give way — every text and every list
    # shortened alike, each cut saying how much it left out — until it fits. What comes
    # back is an index of the result: every page, every table, the start and end of
    # each, under the id that `inspect` reads the full thing by.
    plain = json.loads(json.dumps(body["output"], ensure_ascii=False, default=str))
    body["clipped"] = True
    body["read_more"] = READ_MORE
    for text, items in _FITS:
        body["output"] = _shortened(plain, text, items)
        rendered = json.dumps(body, ensure_ascii=False)
        if len(rendered) <= MAX_OBSERVATION_CHARS:
            return rendered
    # Even the index does not fit: cut, and said so, as before.
    body["output"] = json.dumps(plain, ensure_ascii=False)[:MAX_OBSERVATION_CHARS]
    return json.dumps(body, ensure_ascii=False)


#: Ever shorter limits for one text and for one list, tried in turn until an observation
#: fits. Texts give way first and lists later, so a document keeps every page in its
#: index for as long as it can. Generic: nothing here knows what a page or a table is.
_FITS: Final = (
    (4_000, 200),
    (2_000, 100),
    (1_000, 60),
    (500, 60),
    (300, 50),
    (200, 40),
    (120, 30),
    (80, 20),
    (60, 10),
)

#: Beside a shortened observation: what happened to it and how to read the rest.
READ_MORE: Final = (
    "Bu sonuç sığmadığı için kısaltıldı: yapısı tam, uzun metinler ve listeler kısaltıldı "
    "ve her kesim ne kadarını dışarıda bıraktığını yazıyor. Tamamı bu id'yle duruyor; "
    "inspect ile oku: bir belgenin sayfası için page=N, o sayfadaki bir tablo için page=N "
    "ve table=J; uzun bir metinde offset ile devam et."
)


def _shortened(value: Any, text: int, items: int) -> Any:
    """The same structure, with every string and list no longer than the limits.

    A string keeps its start and its end, because a page's heading is at the top and
    its caption, total or page number is often at the bottom.
    """
    if isinstance(value, str):
        if len(value) <= text:
            return value
        head = text * 2 // 3
        tail = text - head
        return f"{value[:head]} … [+{len(value) - text} karakter] … {value[-tail:]}"
    if isinstance(value, list):
        kept = [_shortened(item, text, items) for item in value[:items]]
        if len(value) > items:
            kept.append(f"… [+{len(value) - items} öğe daha]")
        return kept
    if isinstance(value, dict):
        return {key: _shortened(item, text, items) for key, item in value.items()}
    return value


def observed_payload(output: object) -> Any:
    """What a tool returned, as data the model can read.

    A dataclass rendered by `str()` shows only the fields its author left in its
    repr, and a tool that reads a source keeps the source out of its repr on
    purpose — `WebUrlOutput` hides `document`, `table` and `links`. So a page the
    fetcher had downloaded in full reached the model as
    `WebUrlOutput(status='loaded', code=None, media_type='text/html',
    followed=False)`: a success with nothing in it. Live 2026-09-23 the model then
    spent fifteen calls guessing at links on a page whose text it already had, and
    the report it was asked for was named in that text. `repr=False` is a choice
    about logs; it was never a statement about what the model may see.

    This is the one boundary. The loop's observations and the fallback writer's
    evidence both pass through it, so a tool's content cannot reach one reader and
    not the other.
    """
    if isinstance(output, BaseModel):
        return output.model_dump()
    if is_dataclass(output) and not isinstance(output, type):
        return asdict(output)
    return output


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
                id=_wire(item.action),
                name=item.action.tool,
                arguments=json.dumps(item.action.arguments, ensure_ascii=False),
            )
            for item in carried
        ),
    )
    answers = [
        Message(Role.TOOL, _describe(item.result, item.action.id), tool_call_id=_wire(item.action))
        for item in carried
    ]
    return [asked, *answers]


def _wire(action: Action) -> str:
    """The id the platform pairs a tool turn by, which is its own when it made one."""
    return action.call_id or action.id


#: Said once when the oldest of the exchange no longer fits. It names the two things
#: that do survive, because both are the model's own: the note it writes itself, and
#: a result, which is still there under its id whether or not its bytes are in view.
DROPPED: Final = (
    "Bu turun en eski araç sonuçları artık istemde değil (yer bütçesi). Silinmediler: "
    "her sonuç kendi id'siyle duruyor, inspect ile yeniden açabilir ya da bir araca "
    "source olarak verebilirsin. Taşımak istediğin şeyi state notuna yaz."
)

#: Words this loop uses to talk about a call. Dropped only from a tool that does not
#: declare them: `web_url` has no `id`, and a tool that does — a source addressed by its
#: own identifier — must receive the one the model sent. Stripping it unconditionally
#: made a required argument go missing and the call fail validation instead.
PROTOCOL_KEYS: Final = frozenset({"id", "step_id", "note", "assumption"})


def _within(history: list[Message], budget: int) -> list[Message]:
    """Drop the oldest exchanges until what is left fits, and return what was dropped.

    Whole exchanges, oldest first, because a tool turn without the assistant turn
    that asked for it is not a conversation the protocol can read. The newest is
    never dropped: a model that cannot see what just came back cannot act on it.
    """
    dropped: list[Message] = []
    while len(history) > 1 and sum(len(m.content.encode()) for m in history) > budget:
        following = next(
            (index for index in range(1, len(history)) if history[index].tool_calls), len(history)
        )
        if following >= len(history):
            break
        dropped.extend(history[:following])
        del history[:following]
    return dropped


def _inventory(observations: list[Observation], gone: Collection[str]) -> str:
    """One line for every result whose exchange is out of view: what it is, by name.

    The note alone said results were still there under their ids, and gave none. Live
    2026-09-23 the exchange that had read a PDF was dropped for room, and two requests
    later the model fetched the same listing and the same PDF again (QA-23): nothing in
    front of it said the document was already in hand as `a3`.
    """
    lines = [
        f"- {item.action.id} ({item.action.tool} "
        f"{json.dumps(item.action.arguments, ensure_ascii=False)[:200]}): "
        f"{item.result.status.value}; {_outline(item.result.output)}"
        for item in observations
        if _wire(item.action) in gone
    ]
    return "\nİstemden çıkan sonuçlar:\n" + "\n".join(lines) if lines else ""


def _outline(output: object) -> str:
    """What a result holds, as sizes and short facts, never its content.

    Generic: every short scalar and the length of every list, two levels deep, so a
    document reads as its page count and a series as its value count and coverage.
    """
    if output is None:
        return "çıktı yok"
    try:
        plain = json.loads(json.dumps(observed_payload(output), ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return type(output).__name__
    facts: list[str] = []

    def walk(value: Any, path: str, depth: int) -> None:
        if isinstance(value, list):
            facts.append(f"{path}: {len(value)} öğe")
        elif isinstance(value, dict) and depth < 2:
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key), depth + 1)
        elif isinstance(value, str | int | float | bool) and len(str(value)) <= 80:
            facts.append(f"{path}={value}")

    walk(plain, "", 0)
    return ", ".join(facts)[:600] or type(output).__name__


def _without_protocol_keys(
    arguments: Mapping[str, JsonValue], declared: Collection[str] = ()
) -> dict[str, JsonValue]:
    """The arguments a tool declared, without the loop's own vocabulary.

    Results are named, so the model names things — live 2026-09-23 it sent `id`
    alongside `web_url`'s real arguments, and a schema that forbids extras refused
    the whole call. The address it had worked out was thrown away over a word the
    harness had taught it.

    Only a word this tool does not declare is dropped. A tool that really does take
    an `id` gets the one the model sent: dropping it regardless made a required
    argument go missing, so the call failed validation for the opposite reason.
    Anything else the schema does not declare is still the model's mistake and is
    still reported back.
    """
    return {
        key: value
        for key, value in arguments.items()
        if key not in PROTOCOL_KEYS or key in declared
    }


def _unreadable(identifier: str, call: ToolCall) -> Malformed:
    """A call the loop could not read, kept with everything needed to answer it."""
    sent = call.arguments or ""
    return Malformed(
        id=identifier,
        tool=call.name,
        call_id=call.id,
        sent=sent[:2000] or None,
    )


def _asked_for(completion: Completion, taken: int = 0) -> AgentStep | None:
    """The model's decision, however the platform let it express one.

    A server with native tool calling answers with `tool_calls` and no prose; one
    without answers with the JSON object the schema asked for. Both say the same
    thing, so both are read the same way rather than one being the supported path
    and the other a fallback that behaves differently.
    """
    if completion.tool_calls:
        actions: list[Action] = []
        malformed: list[Malformed] = []
        for index, call in enumerate(completion.tool_calls):
            # Short, this turn's own, and counted across iterations so `a3` means one
            # thing for the whole turn. The platform's id rides along for the wire.
            identifier = f"a{taken + index + 1}"
            try:
                arguments = json.loads(call.arguments or "{}")
            except json.JSONDecodeError:
                # Unreadable arguments are not empty arguments. Running the tool on its
                # defaults would answer a request the model never made, and the model
                # would never learn that what it sent could not be read.
                malformed.append(_unreadable(identifier, call))
                continue
            if not isinstance(arguments, dict):
                malformed.append(_unreadable(identifier, call))
                continue
            actions.append(
                Action(id=identifier, tool=call.name, arguments=arguments, call_id=call.id)
            )
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


def _calls(calls: tuple[ToolCall, ...]) -> list[dict[str, str]]:
    return [{"id": call.id, "name": call.name, "arguments": call.arguments} for call in calls]


def _request(
    provider: LLMProvider,
    messages: list[Message],
    model: str | None,
    menu: list[dict[str, Any]] | None,
    schema: type[BaseModel] | None = AgentStep,
) -> tuple[str, dict[str, Any]]:
    """What this iteration sends the model, for the trace, and where the record came from.

    A provider that renders its own wire body shows exactly that: every role, content,
    `tool_calls` and `tool_call_id`, the tool schemas and the model options, as they
    are posted. Any other provider gets the loop's own messages, field for field.
    Recording never costs the turn: a rendering that fails falls back to the loop's.
    """
    if isinstance(provider, ShowsRequests):
        try:
            return "wire", provider.request_body(messages, model=model, schema=schema, tools=menu)
        except Exception:  # noqa: BLE001, S110 - a trace must not end a turn
            pass
    turns: list[dict[str, Any]] = []
    for message in messages:
        turn: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.tool_calls:
            turn["tool_calls"] = _calls(message.tool_calls)
        if message.tool_call_id is not None:
            turn["tool_call_id"] = message.tool_call_id
        turns.append(turn)
    return "loop", {
        "model": model,
        "schema": schema.__name__ if schema is not None else None,
        "messages": turns,
        "tools": menu,
    }


def traced_complete(
    provider: LLMProvider,
    messages: list[Message],
    *,
    model: str | None,
    tools: list[dict[str, Any]] | None,
    schema: type[BaseModel] | None,
    tracer: Tracer | None,
    stage: str = "loop",
    name: str = "iteration",
    **attributes: JsonValue,
) -> Completion:
    """One model request, recorded both ways when there is a tracer.

    The whole protocol, so every request can be read and replayed: live 2026-09-23 the
    step recorded sizes only, and what the model had been shown could not be checked
    (QA-21). The request is written before the call, so one that never comes back is
    still on record; the tracer redacts it and caps it, and the length says whether the
    cap was reached. Every model request of a turn goes through here, the answer's too:
    the one that wrote A3's answer was the one request with no record (QA-23).
    """
    if tracer is None:
        return provider.complete(messages, model=model, schema=schema, tools=tools)
    with tracer.span(stage, name) as span:
        span.set(**attributes, prompt_bytes=sum(len(m.content.encode()) for m in messages))
        source, request = _request(provider, messages, model, tools, schema)
        sent = json.dumps(request, ensure_ascii=False, default=str)
        detail = '{"request": ' + sent + "}"
        span.describe(detail)
        span.set(
            request_source=source,
            detail_chars=len(detail),
            detail_clipped=len(detail) > MAX_DETAIL_CHARS,
        )
        completion = provider.complete(messages, model=model, schema=schema, tools=tools)
        # The reply first: were the record ever capped, it is the request's tail that
        # goes, and the request is rebuilt from the steps before.
        received = json.dumps(_received(completion), ensure_ascii=False)
        detail = '{"response": ' + received + ', "request": ' + sent + "}"
        span.describe(detail)
        span.set(
            model=completion.model,
            provider_attempts=completion.attempts,
            finish_reason=completion.finish_reason,
            detail_chars=len(detail),
            detail_clipped=len(detail) > MAX_DETAIL_CHARS,
        )
        return completion


#: Said in the last iteration that may still run tools, so the model spends it knowing.
LAST_ROUND: Final = (
    "Bu, araç çağırabileceğin son tur (kalan araç çağrısı: {calls}). Bu turda "
    "çağırdığın araçların sonuçlarını bir sonraki adımda göreceksin; ondan sonra araç "
    "çalıştırılamaz ve cevabı elindekilerle yazacaksın. Yeterli kanıtın varsa şimdi "
    "finish ile bitirebilirsin."
)

#: Said when a counter ran out and the model is asked once more, with no tools, to answer.
CLOSING: Final = (
    "Araç bütçesi doldu; bu adımda hiçbir araç çalıştırılamaz. Son araç sonuçları dahil "
    "elindeki bütün sonuçları değerlendir ve okuyucuya cevabı şimdi yaz (finish ile ya da "
    "düz metin olarak): ne bulduğunu, sayıların hangi sonuçtan geldiğini ve neyin eksik "
    "kaldığını açıkça söyle. Elde olmayan bir sayıyı tahmin etme."
)

#: Counters whose running out still leaves the model able to write from what it has.
CLOSABLE: Final = frozenset({"iterations", "tool calls", "time"})


def _compose(
    preamble: list[Message],
    question: str,
    outcome: TurnOutcome,
    history: list[Message],
    carried: list[Observation],
    native: bool,
    budget: int,
    gone: set[str],
    extra: list[Message],
) -> list[Message]:
    """The request for one iteration, with the newest observations in it.

    With native tool calling the exchange itself is the memory: the assistant turns
    that made the calls and the tool turns that answered them accumulate, exactly as
    the protocol expects. Carrying only the last iteration made the model amnesiac two
    steps back — live 2026-09-22 it searched, read, then searched and read the same
    series again and spent its budget on work it had already done. Without native calls
    the model keeps its own `state` note instead, so only the newest observations need
    repeating.

    What the budget pushes out is remembered in `gone`, and every later request names
    it, so a result out of view is still a result the model knows it has.
    """
    history.extend(_observed(carried, native))
    gone.update(
        message.tool_call_id
        for message in _within(history, budget)
        if message.tool_call_id is not None
    )
    messages = [*preamble, Message(Role.USER, question)]
    if outcome.state:
        messages.append(Message(Role.ASSISTANT, outcome.state))
    if gone:
        messages.append(Message(Role.SYSTEM, DROPPED + _inventory(outcome.observations, gone)))
    messages.extend(history if native else _observed(carried, native))
    messages.extend(extra)
    return messages


def _decided(
    tracer: Tracer,
    outcome: TurnOutcome,
    step: AgentStep,
    completion: Completion,
    *,
    closing: bool = False,
) -> None:
    tracer.event(
        "loop",
        "decision",
        iteration=outcome.iterations,
        actions=[f"{a.id}:{a.tool}" for a in step.actions],
        done=step.done,
        publish=step.publish,
        asked=step.ask is not None,
        native=bool(completion.tool_calls),
        malformed=[f"{item.id}:{item.tool}" for item in step.malformed],
        # How the loop read the reply: the ids it gave each call, the arguments it will
        # run, and the note, ask or answer. The note alone was here, and with native
        # calls there is none, so every decision recorded nothing.
        detail=step.model_dump_json(exclude_defaults=True),
        closing=closing,
    )


def _received(completion: Completion) -> dict[str, Any]:
    """What came back, as the provider handed it over. Hidden reasoning is not in it."""
    return {
        "model": completion.model,
        "attempts": completion.attempts,
        "finish_reason": completion.finish_reason,
        "content": completion.text,
        "tool_calls": _calls(completion.tool_calls),
        "usage": asdict(completion.usage) if completion.usage is not None else None,
        "reconnected": list(completion.reconnected),
    }


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
    #: Platform call ids of tool turns the exchange budget pushed out of view.
    gone: set[str] = set()

    while True:
        if outcome.iterations >= limits.max_iterations:
            outcome.exhausted = "iterations"
            break
        if time.monotonic() - started > limits.max_wall_seconds:
            outcome.exhausted = "time"
            break

        extra: list[Message] = []
        if outcome.iterations + 1 == limits.max_iterations:
            extra.append(
                Message(Role.SYSTEM, LAST_ROUND.format(calls=max(0, limits.max_tool_calls - calls)))
            )
        messages = _compose(
            preamble,
            question,
            outcome,
            history,
            carried,
            native,
            limits.max_exchange_bytes,
            gone,
            extra,
        )
        try:
            completion = traced_complete(
                provider,
                messages,
                model=model,
                tools=menu,
                schema=AgentStep,
                tracer=tracer,
                iteration=outcome.iterations + 1,
                carried=len(carried),
            )
        except ProviderError:
            # The request did not come back. That ends the deciding, not the turn: live
            # 2026-09-23 the sixth request of a turn died in the transport and the reader
            # was told the turn had failed, although ten observations had already come
            # back and the answer could have been written from them. A turn with nothing
            # in hand still fails, because there is nothing to write from.
            if not outcome.observations:
                raise
            outcome.exhausted = "provider"
            outcome.iterations += 1
            break
        outcome.iterations += 1
        native = bool(completion.tool_calls)
        step = _asked_for(completion, len(outcome.observations))
        if tracer is not None and step is not None:
            _decided(tracer, outcome, step, completion)
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
        for unread in step.malformed:
            # The model has to see that what it sent could not be read, or it will
            # send it again unchanged — and it has to see *what* it sent, or it has
            # nothing to correct. The platform's own id answers the call it made.
            refused = Observation(
                Action(id=unread.id, tool=unread.tool, call_id=unread.call_id),
                ToolResult(
                    ToolStatus.FAILURE,
                    unread.id,
                    unread.tool,
                    error_category="arguments",
                    warnings=(
                        "Bu çağrının argümanları geçerli JSON nesnesi değildi; araç "
                        "çalıştırılmadı. Gönderdiğin metin: "
                        + (unread.sent if unread.sent is not None else "(boş)"),
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
                sent = json.dumps(action.arguments, ensure_ascii=False)
                seen = _describe(item.result, action.id)
                tracer.event(
                    "tool",
                    action.tool,
                    status="ok" if item.ok else "failed",
                    step_id=action.id,
                    tool=action.tool,
                    # What the model actually asked for. Without this the record said a
                    # tool ran and never which question it was asked, so no reviewer
                    # could tell a right answer from a right-looking one, or see that a
                    # retry differed from the call before it.
                    # Shown in full up to the attribute ceiling, where the tracer marks
                    # the cut itself; cutting it here first was silent. The length says
                    # whether the whole call is in view, and the step's detail holds it.
                    arguments=sent,
                    arguments_chars=len(sent),
                    arguments_clipped=len(sent) > MAX_TRACE_ARGUMENT_CHARS,
                    # Which platform call this answers, so the exchange can be followed
                    # back to the request the model made.
                    call_id=action.call_id,
                    error_category=item.result.error_category,
                    warnings=list(item.result.warnings),
                    evidence=item.result.evidence,
                    # The complete record, under this step's own sequence: every
                    # argument as sent and the observation exactly as the model then
                    # received it. The tracer redacts secrets in it and keeps it whole
                    # (the step endpoint returns it unclipped), so a call can be
                    # reproduced from the record and a reviewer can see what the model
                    # saw rather than a preview of it.
                    detail=json.dumps(
                        {"arguments": action.arguments, "observation": seen},
                        ensure_ascii=False,
                    ),
                )
        if outcome.exhausted or step.done:
            # `done` beside actions means finish after them, not instead of them: the
            # work was asked for and dropping it silently loses a turn's evidence.
            break

    closed = False
    if (
        outcome.exhausted in CLOSABLE
        and outcome.reply is None
        and outcome.ask is None
        and outcome.observations
    ):
        # A counter ran out with the model's last results still unseen. Live 2026-09-23
        # the eighth iteration's two calls ran, the loop stopped, and those results never
        # reached the model; a separate writer was handed every observation clipped and
        # the turn ended with no answer at all (QA-23). The model is asked once more, in
        # the same exchange with those results in it, and with nothing left to call but
        # `finish`: what it writes is the answer, limits and all.
        messages = _compose(
            preamble,
            question,
            outcome,
            history,
            carried,
            native,
            limits.max_exchange_bytes,
            gone,
            [Message(Role.SYSTEM, CLOSING)],
        )
        last: Completion | None
        try:
            last = traced_complete(
                provider,
                messages,
                model=model,
                tools=[entry for entry in menu if entry["function"]["name"] == FINISH],
                schema=AgentStep,
                tracer=tracer,
                iteration=outcome.iterations + 1,
                carried=len(carried),
                closing=True,
            )
        except ProviderError:
            last = None
        if last is not None:
            closed = True
            outcome.iterations += 1
            answer = _asked_for(last, len(outcome.observations))
            if tracer is not None and answer is not None:
                _decided(tracer, outcome, answer, last, closing=True)
            if answer is not None:
                # Only what answers: a tool asked for now could not be run.
                if answer.state:
                    outcome.state = answer.state
                if answer.publish:
                    outcome.publish = answer.publish
                outcome.reply = answer.reply

    if tracer is not None:
        tracer.event(
            "loop",
            "finished",
            iterations=outcome.iterations,
            tool_calls=calls,
            exhausted=outcome.exhausted,
            published=outcome.publish,
            closing=closed,
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
        parsed = spec.parse(_without_protocol_keys(action.arguments, spec.arguments.model_fields))
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
