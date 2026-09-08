"""Minimal source, semantics and evidence records selectively recovered for M0-01.

No planner, tool execution, workspace or source-adapter protocol is defined here.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StringConstraints,
)

# Reject blank/coerced identifiers without trimming or rewriting source metadata.
NonEmptyText = Annotated[str, StringConstraints(strict=True, pattern=r"\S")]


class ContractModel(BaseModel):
    """Validate declared fields; revalidate records when they cross a boundary."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        revalidate_instances="always",
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )


class SourceRef(ContractModel):
    """Caller-owned source/fragment identity; locator is metadata, never opened.

    Use distinct source IDs/locators for distinct selected sheets or fragments.
    Retrieval time is optional and timezone-aware when supplied; no clock default.
    """

    source_id: NonEmptyText
    source_type: NonEmptyText
    locator: NonEmptyText
    retrieved_at: AwareDatetime | None = None
    content_hash: NonEmptyText | None = None


class Frequency(StrEnum):
    UNKNOWN = "unknown"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    IRREGULAR = "irregular"


class StockFlow(StrEnum):
    UNKNOWN = "unknown"
    STOCK = "stock"
    FLOW = "flow"


class TransformationRecord(ContractModel):
    """Declared operation and lineage metadata; not proof of execution or replayability."""

    operation: NonEmptyText
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    input_refs: list[NonEmptyText] = Field(min_length=1)
    output_ref: NonEmptyText


class DataContract(ContractModel):
    """Semantic descriptor for a table or series, not a loaded/profiled result.

    None means unknown for nullable semantics; enum UNKNOWN is serialized as
    "unknown". In particular, cumulative=None differs from cumulative=False.
    Values are declarations, never inferred from title, dtype or frequency.
    A descriptor alone cannot authorize a transformation or prove its meaning.
    """

    contract_id: NonEmptyText
    source: SourceRef
    title: NonEmptyText
    unit: NonEmptyText | None = None
    frequency: Frequency = Frequency.UNKNOWN
    time_column: NonEmptyText | None = None
    time_semantics: NonEmptyText | None = None
    stock_flow: StockFlow = StockFlow.UNKNOWN
    cumulative: StrictBool | None = None
    reset_behavior: NonEmptyText | None = None
    source_period: NonEmptyText | None = None
    transformations: list[TransformationRecord] = Field(default_factory=list)
    semantic_warnings: list[NonEmptyText] = Field(default_factory=list)


class ValidationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class EvidenceRecord(ContractModel):
    """Claim/source/lineage metadata; NOT_RUN until a caller records validation.

    This is not a verifier or a complete evidence-chain guarantee. Metadata and
    validation outcomes still require independent checks by their consumers.
    """

    evidence_id: NonEmptyText
    claim: NonEmptyText
    sources: list[SourceRef] = Field(min_length=1)
    tool_run_id: NonEmptyText | None = None
    transformations: list[TransformationRecord] = Field(default_factory=list)
    period: NonEmptyText | None = None
    columns: list[NonEmptyText] = Field(default_factory=list)
    validation: ValidationOutcome = ValidationOutcome.NOT_RUN
    limitations: list[NonEmptyText] = Field(default_factory=list)
