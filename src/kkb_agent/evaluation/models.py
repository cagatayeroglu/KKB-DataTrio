"""Typed, machine-readable outcomes for deterministic evaluation suites."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from kkb_agent.core.models import ContractModel


class CaseStatus(StrEnum):
    """Verdict for one independently scored case."""

    PASS = "pass"
    FAIL = "fail"


class OracleRecord(ContractModel):
    """Human-reviewable basis for expected values, kept beside every outcome."""

    derivation: str
    semantic_assumptions: tuple[str, ...]
    independence: str
    absolute_tolerance: float = 0.0
    relative_tolerance: float = 0.0


class PlannerRecord(ContractModel):
    """The deterministic model fixture selects an operation, never its answer."""

    provider: Literal["scripted-model"] = "scripted-model"
    operation: str
    attempts: int


class AssertionFailure(ContractModel):
    """One exact structural or numeric mismatch."""

    path: str
    expected: object | None
    actual: object | None
    reason: str


class CaseOutcome(ContractModel):
    """Stable result for one smoke case."""

    case_id: str
    category: str
    status: CaseStatus
    input_fixture: dict[str, object]
    expected: dict[str, object]
    actual: dict[str, object]
    oracle: OracleRecord
    planner: PlannerRecord | None = None
    failures: tuple[AssertionFailure, ...] = ()


class CategorySummary(ContractModel):
    total: int
    passed: int
    failed: int


class SuiteSummary(ContractModel):
    total: int
    passed: int
    failed: int
    categories: dict[str, CategorySummary]


class EvaluationReport(ContractModel):
    """Reproducible suite report; intentionally contains no wall-clock timestamp."""

    suite_id: Literal["m9-05-eval-smoke-v1"] = "m9-05-eval-smoke-v1"
    case_set_sha256: str
    offline: Literal[True] = True
    deterministic: Literal[True] = True
    summary: SuiteSummary
    cases: tuple[CaseOutcome, ...]
