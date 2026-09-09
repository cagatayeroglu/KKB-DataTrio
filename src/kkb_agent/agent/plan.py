"""The typed plan (M5-01).

A plan is a proposal, never an instruction. It arrives as model output derived
from a prompt that may contain source text, so nothing here is trusted until
validation has checked it against the registry — DEC-101's rule that structural
parsing alone is not authority to execute.

`extra="forbid"` is doing real work: a plan carrying a field nobody defined is
rejected rather than quietly ignored, which is how an injected instruction would
try to travel.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints

Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    step_id: Identifier
    tool: Identifier
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[Identifier] = Field(default_factory=list)


class AnalyticalPlan(BaseModel):
    """What the planner proposes. Its steps are candidates, not commitments."""

    model_config = ConfigDict(extra="forbid", strict=False)

    question: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)

    def fingerprint(self) -> str:
        """Stable identity for detecting a model that keeps proposing the same thing."""
        return self.model_dump_json()
