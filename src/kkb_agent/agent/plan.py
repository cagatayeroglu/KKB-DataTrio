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

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
ClarificationReason = Literal[
    "ambiguous_series", "missing_series", "unresolved_semantics", "unsupported_request"
]


#: A footnote, not a paragraph: one sentence saying what the step assumed.
MAX_ASSUMPTION_CHARS = 200


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    step_id: Identifier
    tool: Identifier
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[Identifier] = Field(default_factory=list)
    assumption: str | None = Field(
        default=None,
        max_length=MAX_ASSUMPTION_CHARS,
        # The reason to write one, and when, is in the planner's instructions: this
        # contract is budgeted in bytes and every schema description is paid for there.
        description="Optional. One short Turkish sentence: the choice this step settled itself.",
    )


#: A conversational reply is short prose, never a place to carry a data table.
MAX_REPLY_CHARS = 1500


class AnalyticalPlan(BaseModel):
    """What the planner proposes. Its steps are candidates, not commitments.

    Exactly one of three decisions, in one planner call (no separate router):
    `steps` to run tools, `clarification` to ask, or `reply` to answer a message
    that needs no data or calculation. A reply publishes nothing and is gated
    like any draft: a figure in it must bind to an already published result.
    """

    model_config = ConfigDict(extra="forbid", strict=False)

    question: str = Field(min_length=1)
    steps: list[PlanStep]
    clarification: ClarificationReason | None = None
    clarification_text: str | None = Field(default=None, min_length=1, max_length=1500)
    reply: str | None = Field(default=None, min_length=1, max_length=MAX_REPLY_CHARS)
    #: False when the reader only asks to show, add, convert or filter: no 'Yorum' then.
    interpret: bool = True

    @model_validator(mode="after")
    def executable_or_clarification(self) -> Self:
        decisions = sum((bool(self.steps), self.clarification is not None, self.reply is not None))
        if decisions != 1:
            raise ValueError(
                "Provide exactly one of: executable steps, a clarification reason, or a reply"
            )
        if self.clarification_text is not None and self.clarification is None:
            raise ValueError("clarification_text requires a clarification reason")
        return self

    def fingerprint(self) -> str:
        """Stable identity for detecting a model that keeps proposing the same thing."""
        return self.model_dump_json()
