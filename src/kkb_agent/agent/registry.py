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

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from kkb_agent.agent.executor import ExecutionContext, ToolResult

#: The six names the brief fixes. Registering anything else needs a decision.
BRIEF_TOOLS = frozenset(
    {"lakehouse", "web_search", "web_url", "anomaly", "causality", "change_detection"}
)


class RegistryError(ValueError):
    """A tool was registered or requested in a way the registry cannot honour."""


class ArgumentsRejected(ValueError):
    """Arguments did not satisfy the tool's schema. Names fields, never values."""


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    arguments: type[BaseModel]
    run: Callable[[BaseModel, ExecutionContext], ToolResult]

    def parse(self, raw: dict[str, Any]) -> BaseModel:
        try:
            return self.arguments.model_validate(raw)
        except ValidationError as error:
            locations = "; ".join(
                ".".join(str(piece) for piece in item["loc"]) + f": {item['type']}"
                for item in error.errors()
            )
            raise ArgumentsRejected(f"{self.name}: {locations}") from error


class ToolRegistry:
    """Unique, system-owned tool names with their argument schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise RegistryError(f"Tool {spec.name!r} is already registered")
        if spec.name not in BRIEF_TOOLS:
            raise RegistryError(
                f"Tool {spec.name!r} is not one of the six names the brief fixes; "
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
                "arguments": spec.arguments.model_json_schema(),
            }
            for spec in self
        ]
