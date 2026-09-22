"""Getting a typed object out of a model that may not offer structured output.

The platform's structured-output support is unresolved (Q-K-03), and the brief
expects open-weight models, which malform JSON more often than large hosted
ones. So the fallback is not a contingency, it is the likely path: extract the
JSON from whatever came back, validate strictly,
and on failure tell the model exactly what was wrong and ask again.

Strictly is the operative word. A plan that deserializes is not a plan that may
be executed — DEC-101 requires the schema to be the gate, so extra fields are
rejected rather than ignored.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ValidationError

from kkb_agent.llm.provider import Completion, Message, Role, SchemaViolation

#: One model turn: the text it returned and, when the platform says, why it stopped.
Ask = Callable[[list[Message]], tuple[str, str | None]]

#: Only the first this many characters of a validation error are fed back. The
#: message names fields and types, and a long one wastes a small context window.
FEEDBACK_LIMIT = 600


def extract_json(text: str) -> str:
    """Return the JSON document inside a response, fences and prose included.

    Models routinely wrap JSON in ```json fences or a sentence of preamble.
    Cutting to the outermost balanced braces handles both without a parser, and
    without silently accepting a second object hiding after the first.
    """
    fenced = text.strip()
    if fenced.startswith("```"):
        newline = fenced.find("\n")
        closing = fenced.rfind("```")
        if newline != -1 and closing > newline:
            fenced = fenced[newline + 1 : closing].strip()
    start = fenced.find("{")
    if start == -1:
        raise SchemaViolation("Response contains no JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(fenced)):
        character = fenced[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                # Whatever follows the object is the model talking, not a second plan:
                # a closing remark holding one bracket used to end the turn. Live
                # 2026-09-22 the planner searched, `web_url` loaded the TCMB decision
                # page, and the continuation that decides what to do with it was thrown
                # away for what came after its own valid JSON. The first balanced object
                # is the answer; strict validation still runs on it.
                return fenced[start : index + 1]
    raise SchemaViolation("Response contains an unterminated JSON object")


def parse_structured[ModelT: BaseModel](text: str, schema: type[ModelT]) -> ModelT:
    """Validate complete JSON against `schema`; malformed text requires a new response.

    Raises `SchemaViolation` with a message describing the fault, which is what
    the retry loop feeds back to the model.
    """
    document = extract_json(text)
    try:
        payload = json.loads(document)
    except json.JSONDecodeError:
        # Repairing a brace-balanced document is punctuation, not invention: the keys
        # and values are the model's own and strict validation still follows. Removing
        # it cost a whole turn live (2026-09-22) — the planner had searched, `web_url`
        # had loaded the TCMB decision page, and the continuation that decides what to
        # do with it came back malformed, so the answer abstained on a page already in
        # hand. A response that cannot be repaired still raises, and the retry loop
        # still tells the model what was wrong.
        payload = _repair(document)
    if not isinstance(payload, dict):
        # Defensive: extraction guarantees a brace-balanced document, so this
        # only fires if the repair step ever returns something else.
        raise SchemaViolation("Response JSON is not an object")
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        raise SchemaViolation(_summarize(error)) from error


def complete_with_repair(
    ask: Ask,
    messages: Sequence[Message],
    *,
    schema: type[BaseModel] | None,
    max_attempts: int,
    model: str,
) -> Completion:
    """Ask, validate against `schema`, and on failure ask again with the fault.

    Shared by every provider so the loop a test scripts is the loop that runs
    against the platform. Without a schema the first answer is returned.
    """
    max_attempts = min(max_attempts, 2)  # One correction, never an expanding repair loop.
    conversation = list(messages)
    last_problem = ""
    for attempt in range(1, max_attempts + 1):
        text, finish_reason = ask(conversation)
        if schema is None:
            return Completion(text=text, model=model, attempts=attempt, finish_reason=finish_reason)
        try:
            parsed = parse_structured(text, schema)
        except SchemaViolation as error:
            last_problem = str(error)
            if attempt == max_attempts:
                break
            # Feed the fault back rather than retrying the same prompt: an
            # unchanged prompt tends to reproduce the same malformation.
            conversation = [
                *conversation,
                Message(Role.ASSISTANT, text),
                Message(Role.USER, repair_feedback(schema, last_problem)),
            ]
            continue
        return Completion(
            text=text,
            model=model,
            attempts=attempt,
            parsed=parsed,
            finish_reason=finish_reason,
        )
    raise SchemaViolation(
        f"Schema not satisfied after {max_attempts} attempt(s): {last_problem}",
        attempts=max_attempts,
    )


def schema_instructions(schema: type[BaseModel]) -> str:
    """Render one system-owned response contract identically for planning and repair."""
    return (
        "Reply with a single JSON object and nothing else, matching this schema:\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False, sort_keys=True)}"
    )


def repair_feedback(schema: type[BaseModel], problem: str) -> str:
    """The correction handed back to the model on a retry.

    The original schema and context remain in the conversation. Repeat only
    the correction instruction, not another copy of the tool/plan schema.
    """
    return (
        f"The previous response was rejected: {problem[:FEEDBACK_LIMIT]}. "
        "Emit one complete schema-valid JSON object only, using the same schema and context."
    )


def _repair(document: str) -> object:
    """Second attempt at parsing, using json-repair for the usual malformations."""
    try:
        from json_repair import repair_json
    except ImportError as error:  # pragma: no cover - declared in the manifest
        raise SchemaViolation("Response is not valid JSON and no repair is available") from error
    repaired = repair_json(document)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as error:
        raise SchemaViolation("Response is not valid JSON even after repair") from error


def _summarize(error: ValidationError) -> str:
    """A short, value-free description of what failed validation.

    Only field locations and error types are reported. The offending values are
    model output derived from a prompt that may hold source data, so they stay
    out of messages that reach logs.
    """
    parts = []
    for item in error.errors():
        location = ".".join(str(piece) for piece in item["loc"]) or "<root>"
        parts.append(f"{location}: {item['type']}")
    summary = "; ".join(parts) or "schema validation failed"
    return summary[:FEEDBACK_LIMIT]
