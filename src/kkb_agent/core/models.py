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
    """Reporting calendar. Members were added for conventions EVDS actually declares.

    WEEKLY does not say which weekday anchors the period; that is WeeklyAnchor,
    because EVDS anchors most weekly series to Friday and at least one to
    Wednesday. BUSINESS_DAY differs from DAILY on weekends and holidays, which
    changes both observation counts and any average taken over a period.
    """

    UNKNOWN = "unknown"
    DAILY = "daily"
    BUSINESS_DAY = "business_day"
    WEEKLY = "weekly"
    TWICE_MONTHLY = "twice_monthly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"
    IRREGULAR = "irregular"


class WeeklyAnchor(StrEnum):
    """Weekday a weekly period ends on. Required when Frequency is WEEKLY."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def weekday(self) -> int:
        """Match `datetime.date.weekday()`, where Monday is 0."""
        return list(WeeklyAnchor).index(self)


class StockFlow(StrEnum):
    """What an observation measures, which decides how periods may be combined.

    RATE and INDEX are neither stock nor flow: summing either is meaningless,
    and EVDS marks its rate series `SUMABLE: 0` for exactly that reason.
    """

    UNKNOWN = "unknown"
    STOCK = "stock"
    FLOW = "flow"
    RATE = "rate"
    INDEX = "index"


class Scale(StrEnum):
    """Multiplier a published value carries, kept separate from its unit.

    BDDK publishes its monthly and weekly bulletins in million TRY and FinTürk
    in thousand TRY, so a value without a recorded scale is unusable.
    """

    UNKNOWN = "unknown"
    ONE = "one"
    THOUSAND = "thousand"
    MILLION = "million"
    BILLION = "billion"

    @property
    def factor(self) -> int:
        if self is Scale.UNKNOWN:
            raise ValueError("Unknown scale has no factor")
        return {Scale.ONE: 1, Scale.THOUSAND: 10**3, Scale.MILLION: 10**6, Scale.BILLION: 10**9}[
            self
        ]


class CumulativeKind(StrEnum):
    """How a running total accumulates, if it does.

    Three distinct behaviours were measured in one BDDK bulletin, so a boolean
    cannot express this. NONE is a positive statement that the series does not
    accumulate; UNKNOWN means nobody has established which applies.
    """

    UNKNOWN = "unknown"
    NONE = "none"
    SINCE_INCEPTION = "since_inception"
    YEARLY_RESET = "yearly_reset"


class Aggregation(StrEnum):
    """Permitted reduction when combining periods; sources may publish this."""

    UNKNOWN = "unknown"
    SUM = "sum"
    AVERAGE = "average"
    FIRST = "first"
    LAST = "last"
    MIN = "min"
    MAX = "max"


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
