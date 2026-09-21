"""The tool registry (M5-03, M5-04, DEC-121).

The registry owns tool names and argument schemas. One definition produces both
the description shown to the model and the validation applied to what comes
back, so the two cannot drift apart — the failure where a model is told about a
parameter the executor does not accept, or worse, the reverse.

A name that is not registered does not exist. That is the whole prompt-injection
defence at this layer: text in a source document can propose `shell`, but there
is no `shell`, so the plan is rejected before anything runs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.agent.executor import ExecutionContext, ToolResult

#: The six names the brief fixes. Registering anything else needs a decision.
BRIEF_TOOLS = frozenset(
    {"lakehouse", "web_search", "web_url", "anomaly", "causality", "change_detection"}
)


# M13-04 catalog_search; M5-20 table_transform (DEC-135, delivered operations only);
# DEC-181 document_read, whose output is a reading rather than evidence; DEC-183
# promote_series, whose output is an offer and whose write waits for the person.
IMPLEMENTED_PRODUCT_TOOLS = frozenset(
    {"catalog_search", "table_transform", "document_read", "promote_series"}
)


class RegistryError(ValueError):
    """A tool was registered or requested in a way the registry cannot honour."""


class ArgumentsRejected(ValueError):
    """Arguments did not satisfy the tool's schema. Names fields, never values."""


@dataclass(frozen=True, slots=True)
class TableInput:
    """Registry-owned declaration of a tool's actual table input."""

    source: str | None = None
    input_step: str | None = None
    #: Further tables the step reads by name (a join's other side).
    others: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    arguments: type[BaseModel]
    run: Callable[[BaseModel, ExecutionContext], ToolResult]
    # A tool may consume earlier step outputs only through explicit plan edges.
    required_steps: Callable[[BaseModel], tuple[str, ...]] | None = None

    table_input: Callable[[BaseModel], TableInput | None] | None = None
    discovery_only: bool = False

    def parse(self, raw: dict[str, Any]) -> BaseModel:
        try:
            return self.arguments.model_validate(raw)
        except ValidationError as error:
            locations = "; ".join(_describe(item) for item in error.errors())
            raise ArgumentsRejected(f"{self.name}: {locations}") from error


def _describe(item: Mapping[str, Any]) -> str:
    """One validation error as a repair instruction, never as a bare type code.

    A wrong `operation` on a discriminated union used to read "table_transform: :
    union_tag_invalid" (live E1c, 2026-09-19); the planner spent a repair on it. The
    tags the union accepts are what it needed.
    """
    location = ".".join(str(piece) for piece in item["loc"]) or "arguments"
    text = f"{location}: {item['type']}"
    context = item.get("ctx") or {}
    if "expected_tags" in context:
        text += (
            f" (operation {context.get('tag')!r} is not one of this tool's operations: "
            f"{context['expected_tags']})"
        )
    elif "expected" in context:
        text += f" (expected {context['expected']})"
    elif str(item["type"]) == "value_error" and item.get("msg"):
        # A model validator's own sentence is the repair; the type code alone is not
        # (live X4, 2026-09-19: "change_detection: co_movement: value_error").
        text += f" ({item['msg']})"
    return text


class ToolRegistry:
    """Unique, system-owned tool names with their argument schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise RegistryError(f"Tool {spec.name!r} is already registered")
        if spec.name not in BRIEF_TOOLS | IMPLEMENTED_PRODUCT_TOOLS:
            raise RegistryError(
                f"Tool {spec.name!r} is not an implemented approved tool; "
                "adding one needs its own decision"
            )
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError:
            raise RegistryError(f"Unknown tool {name!r}") from None

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[ToolSpec]:
        return iter(sorted(self._tools.values(), key=lambda spec: spec.name))

    def __len__(self) -> int:
        return len(self._tools)

    def descriptions(self) -> list[dict[str, Any]]:
        """Exactly what the planner is shown (M5-06).

        Derived from the same definitions the executor validates against, and
        nothing else: no source content, no workspace internals, no credentials.
        """
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "arguments": _without_titles(spec.arguments.model_json_schema()),
            }
            for spec in self
        ]


def _without_titles(node: Any, *, names: bool = False) -> Any:
    """A tool's JSON schema as a planner needs it: what to write, without the validator's marks.

    Removed, because they tell a planner nothing it can act on (the validator keeps them):
    the `title` pydantic generates for every field ("Driver Column" beside `driver_column`),
    the `anyOf [X, null]` + `default null` wrapper of an optional field (`required` already
    says which fields are not optional). `additionalProperties: false` stays, because it
    tells a planner not to invent a field the validator would refuse, and so does the
    discriminator, whose mapping lists a tool's operations by name. Measured on the served
    tools: 29.4 KB to about 25 KB. Inside `properties` and
    `$defs` a key is an argument's or a model's own name, never an annotation, and is kept.
    """
    if isinstance(node, dict):
        if not names:
            options = node.get("anyOf")
            if isinstance(options, list) and len(options) == 2 and {"type": "null"} in options:
                base = next(item for item in options if item != {"type": "null"})
                if isinstance(base, dict):
                    rest = {k: v for k, v in node.items() if k not in ("anyOf", "default")}
                    node = {**base, **rest}
        return {
            key: _without_titles(value, names=key in ("properties", "$defs"))
            for key, value in node.items()
            if names
            or not (
                (key == "title" and isinstance(value, str)) or (key == "default" and value is None)
            )
        }
    if isinstance(node, list):
        return [_without_titles(item) for item in node]
    return node
