"""What an analytical tool returns (M6-01).

`ToolResult.output` is typed `object`, so today every tool invents its own
shape and nothing downstream can reason about it. That single gap is what
holds three separate things back:

- the verifier binds a written number to *any* stored value of similar
  magnitude, because a result carries no period, unit or run to bind to;
- the workspace cannot reject a stale result, because a result has no
  identity to compare against;
- M6-02..M6-11 each need the same answer to "what does a tool hand back".

This module is that answer and nothing more. It is a contract, not a proof
engine: it decides what a result must *state* before anyone may use it. It
does not compute, verify, store or recompute anything. `AnalyticalResult`
carries `run_id`/`step_id` so M5 can bind a result to the run that produced
it, and `digest()` so M8 can tell a re-derived result from a tampered one.
Both are references and hashes; the run manager and the verification gate
belong to those milestones.

Three invariants here exist because of measured failures, not tidiness:

1. A value must *state* its unit. `None` means unknown, and an unknown unit
   or scale forces the result to declare unresolved semantics. BDDK publishes
   its monthly and weekly bulletins in million TRY while FinTürk publishes in
   thousand TRY, so a number without a recorded scale is a silent 1000x error
   waiting for someone to join two tables ([BDDK_SOURCE](../../../docs/BDDK_SOURCE.md)).
   A genuinely dimensionless quantity says so with `DIMENSIONLESS` rather than
   leaving the field empty.
2. A result that could not be computed carries no values at all. Half an
   answer is worse than an abstention, because the evidence panel then
   certifies the half.
3. An association, lag or causality result must state its limitations.
   [DEC-120](../../../docs/DECISIONS.md) permits reporting association with
   mandatory stated limits; a correlation that arrives without them reads as
   a cause by the time it reaches a slide.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, JsonValue, model_validator

from kkb_agent.core.models import (
    ContractModel,
    Frequency,
    NonEmptyText,
    Scale,
    SourceRef,
    StockFlow,
    TransformationRecord,
    WeeklyAnchor,
)

#: Declare this as a value's unit when the quantity genuinely has none — a
#: correlation coefficient, a ratio, a count. It is deliberately not the same
#: as leaving `unit` empty, which means nobody has established the unit yet.
DIMENSIONLESS = "dimensionless"

#: Reject strings and booleans rather than coercing them. Model and source
#: output reaches these models directly, and `"1.234"` is ambiguous in Turkish
#: text: silently reading it as 1.234 rather than 1234 is the exact thousandfold
#: error the verifier's number parser was written to avoid.
StrictFloat = Annotated[float, Field(strict=True)]
Count = Annotated[int, Field(strict=True, ge=0)]


class ResultKind(StrEnum):
    """What question a result answers, which decides how it may be read.

    The members cover the deterministic analytics the brief names. CAUSALITY
    is present because the brief requires a causality tool, not because a
    result of that kind establishes a cause; under DEC-120 it reports the
    same association evidence with its limits attached.
    """

    LEVEL = "level"
    CHANGE = "change"
    COMPARISON = "comparison"
    SERIES = "series"
    ANOMALY = "anomaly"
    CHANGE_POINT = "change_point"
    ASSOCIATION = "association"
    LAG = "lag"
    CAUSALITY = "causality"


#: Kinds whose output is an observed relationship rather than a measurement.
#: Each must state its limitations before it may be presented (DEC-120).
RELATIONAL_KINDS = frozenset({ResultKind.ASSOCIATION, ResultKind.LAG, ResultKind.CAUSALITY})


class ResultStatus(StrEnum):
    """Whether a value was produced, and if not, which kind of nothing.

    The three non-computed states are distinct on purpose. INSUFFICIENT is a
    data problem and more data would fix it; UNDEFINED is a mathematical one
    and more data of the same shape would not; ABSTAINED is a semantic one,
    where the numbers are available but their meaning is not established and
    computing anyway would invent it.
    """

    COMPUTED = "computed"
    INSUFFICIENT = "insufficient"
    UNDEFINED = "undefined"
    ABSTAINED = "abstained"


class Period(ContractModel):
    """An explicit closed interval, never a bare label like "2024".

    `end` is the period's last day, which is what the lakehouse stores and
    what `is_january` tests for a cumulative reset. A weekly period must name
    its anchor: EVDS anchors most weekly series to Friday and at least one to
    Wednesday, so "weekly" alone does not identify which days an observation
    covers.
    """

    start: date
    end: date
    frequency: Frequency = Frequency.UNKNOWN
    weekly_anchor: WeeklyAnchor | None = None

    @model_validator(mode="after")
    def _check_interval(self) -> Self:
        if self.end < self.start:
            raise ValueError("A period ends on or after it starts")
        if self.frequency is Frequency.WEEKLY:
            if self.weekly_anchor is None:
                raise ValueError("A weekly period must name the weekday it is anchored to")
            if self.end.weekday() != self.weekly_anchor.weekday:
                raise ValueError(
                    f"A {self.weekly_anchor.value}-anchored period must end on that weekday"
                )
        elif self.weekly_anchor is not None:
            raise ValueError("Only a weekly period carries a weekly anchor")
        return self


class SampleCounts(ContractModel):
    """How many observations went into a number, and how many did not.

    A statistic without its sample count cannot be judged: a correlation over
    four points and one over sixty read identically once formatted. `missing`
    and `excluded` are separate because they mean different things — a gap in
    the source is not the same as an observation a policy dropped — and both
    have to survive into the answer rather than being absorbed into `used`.
    """

    used: Count
    missing: Count = 0
    excluded: Count = 0
    #: The floor the tool applied, so an INSUFFICIENT result explains itself.
    minimum_required: Count | None = None

    @property
    def considered(self) -> int:
        """Observations the tool looked at, whether or not it kept them."""
        return self.used + self.missing + self.excluded

    @model_validator(mode="after")
    def _check_floor(self) -> Self:
        if (
            self.minimum_required is not None
            and self.used > 0
            and self.used < self.minimum_required
        ):
            raise ValueError(
                f"{self.used} observations is below the stated minimum of "
                f"{self.minimum_required}; report INSUFFICIENT instead of a value"
            )
        return self


class ResultValue(ContractModel):
    """One number a tool computed, carrying the semantics needed to read it.

    Unit and scale sit here rather than on the result because one result may
    legitimately mix them: a lag analysis reports a dimensionless coefficient
    alongside the periods it covers, and a comparison reports an amount in
    million TRY beside a percentage.
    """

    label: NonEmptyText
    value: StrictFloat
    #: `None` means the unit is unknown. A quantity that genuinely has none
    #: declares DIMENSIONLESS; the two are not interchangeable.
    unit: NonEmptyText | None = None
    scale: Scale = Scale.UNKNOWN
    measure: StockFlow = StockFlow.UNKNOWN
    period: Period | None = None
    #: Offset in periods for a lag result. Negative means the first series
    #: leads the second; the sign convention is recorded per M6-09.
    lag: Annotated[int, Field(strict=True)] | None = None
    #: Per-value counts, which a lag or per-window result needs because each
    #: offset is computed over a different number of overlapping observations.
    samples: SampleCounts | None = None

    @property
    def semantics_are_unresolved(self) -> bool:
        """True when this number cannot be safely combined or compared."""
        return self.unit is None or self.scale is Scale.UNKNOWN


class ResultEvidence(ContractModel):
    """What this result was derived from. References only, never copies.

    `input_refs` is required and non-empty: a computed number whose inputs are
    unnamed cannot be verified or recomputed, and storing it would put an
    unfalsifiable figure into the workspace. The referenced records live in
    the lineage graph and the evidence store; resolving them is M8's job, and
    this contract does not claim they resolve.
    """

    input_refs: list[NonEmptyText] = Field(min_length=1)
    transformations: list[TransformationRecord] = Field(default_factory=list)
    #: The lineage node recorded for this result, when the tool wrote one.
    lineage_node: NonEmptyText | None = None
    evidence_ids: list[NonEmptyText] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


class AnalyticalResult(ContractModel):
    """The typed output of a deterministic analytical tool.

    Identity is deliberately split. `result_id` is the caller's handle, stable
    across a rename or a re-serialization. `digest()` is derived from content
    alone, so two results with the same id and different digests are a stale
    or tampered read — which is what M5's workspace and M8's gate each need to
    detect, and neither can detect today.
    """

    result_id: NonEmptyText
    kind: ResultKind
    status: ResultStatus
    tool: NonEmptyText
    #: The concrete method, when a kind admits several — "pearson", "granger".
    method: NonEmptyText | None = None
    #: Set by M5 when the result comes from a recorded run. `None` means the
    #: result was computed outside one, not that a run is implied.
    run_id: NonEmptyText | None = None
    step_id: NonEmptyText | None = None
    values: list[ResultValue] = Field(default_factory=list)
    #: The span the analysis covers, distinct from any single value's period.
    coverage: Period | None = None
    #: Method parameters as applied: window, lag range, alpha, minimum sample.
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    samples: SampleCounts | None = None
    evidence: ResultEvidence | None = None
    warnings: list[NonEmptyText] = Field(default_factory=list)
    #: Why this method's output must not be over-read. Mandatory for the
    #: relational kinds under DEC-120.
    limitations: list[NonEmptyText] = Field(default_factory=list)
    #: Semantics nobody has established — an unknown unit, scale, stock/flow
    #: meaning or cumulative behaviour. Never inferred, never silently filled.
    unresolved_semantics: list[NonEmptyText] = Field(default_factory=list)
    #: Required when status is not COMPUTED: what stopped the computation.
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def _check_status_matches_content(self) -> Self:
        if self.status is ResultStatus.COMPUTED:
            self._check_computed()
        else:
            self._check_not_computed()
        return self

    def _check_computed(self) -> None:
        if not self.values:
            raise ValueError("A computed result must carry at least one value")
        if self.evidence is None:
            raise ValueError("A computed result must name the inputs it was derived from")
        if self.samples is not None and self.samples.used == 0:
            raise ValueError(
                "A computed result cannot rest on zero observations; "
                "report INSUFFICIENT with a reason instead"
            )
        if self.kind in RELATIONAL_KINDS and not self.limitations:
            raise ValueError(
                f"A {self.kind.value} result must state its limitations before it is presented"
            )
        if (
            any(value.semantics_are_unresolved for value in self.values)
            and not self.unresolved_semantics
        ):
            raise ValueError(
                "A value with an unknown unit or scale must record what is unresolved; "
                f"declare {DIMENSIONLESS!r} when the quantity genuinely has no unit"
            )

    def _check_not_computed(self) -> None:
        if self.values:
            raise ValueError(
                f"A {self.status.value} result carries no values; "
                "a partial number is read as a whole one"
            )
        if self.reason is None:
            raise ValueError(f"A {self.status.value} result must say what stopped it")

    def digest(self) -> str:
        """A stable hash of everything except the caller's chosen id.

        Two results describing the same computation over the same inputs hash
        alike whatever they are called, and any change to a value, period,
        sample count, parameter or evidence reference changes the hash. That
        is what makes a stale or altered result detectable; deciding what to
        do about one is M5's and M8's call, not this module's.
        """
        payload = self.model_dump(mode="json", exclude={"result_id"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def describes_same_computation(self, other: AnalyticalResult) -> bool:
        """Whether two results are the same content under possibly different ids."""
        return self.digest() == other.digest()
