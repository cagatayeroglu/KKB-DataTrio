"""Bounded offline runner and independent structural/numeric scorer for M9-05."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, ConfigDict

from kkb_agent.evaluation.cases import CaseSpec, Operation, smoke_cases
from kkb_agent.evaluation.models import (
    AssertionFailure,
    CaseOutcome,
    CaseStatus,
    CategorySummary,
    EvaluationReport,
    PlannerRecord,
    SuiteSummary,
)
from kkb_agent.llm import ScriptedProvider
from kkb_agent.llm.provider import Message, Role


class _OperationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Operation


def _case_set_sha256(cases: Sequence[CaseSpec]) -> str:
    payload = [
        {
            "case_id": case.case_id,
            "category": case.category,
            "turn": case.turn,
            "question": case.question,
            "operation": case.operation,
            "input_fixture": case.input_fixture,
            "expected": case.expected,
            "oracle": case.oracle.model_dump(mode="json"),
        }
        for case in cases
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _json_value(value: object) -> object | None:
    """Narrow scorer values to the JSON-safe case contract."""
    try:
        encoded = json.dumps(value, ensure_ascii=False)
        return cast(object, json.loads(encoded))
    except (TypeError, ValueError):
        return str(type(value).__name__)


def _compare(
    expected: object,
    actual: object,
    *,
    path: str,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> list[AssertionFailure]:
    failures: list[AssertionFailure] = []
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            return [
                AssertionFailure(
                    path=path,
                    expected=_json_value(expected),
                    actual=_json_value(actual),
                    reason="expected an object",
                )
            ]
        expected_keys, actual_keys = set(expected), set(actual)
        for key in sorted(expected_keys - actual_keys):
            failures.append(
                AssertionFailure(
                    path=f"{path}.{key}",
                    expected=_json_value(expected[key]),
                    actual=None,
                    reason="missing key",
                )
            )
        for key in sorted(actual_keys - expected_keys):
            failures.append(
                AssertionFailure(
                    path=f"{path}.{key}",
                    expected=None,
                    actual=_json_value(actual[key]),
                    reason="unexpected key",
                )
            )
        for key in sorted(expected_keys & actual_keys):
            failures.extend(
                _compare(
                    expected[key],
                    actual[key],
                    path=f"{path}.{key}",
                    absolute_tolerance=absolute_tolerance,
                    relative_tolerance=relative_tolerance,
                )
            )
        return failures
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)):
            return [
                AssertionFailure(
                    path=path,
                    expected=_json_value(expected),
                    actual=_json_value(actual),
                    reason="expected an array",
                )
            ]
        if len(expected) != len(actual):
            failures.append(
                AssertionFailure(
                    path=path,
                    expected=_json_value(expected),
                    actual=_json_value(actual),
                    reason=f"array length differs: expected {len(expected)}, got {len(actual)}",
                )
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
            failures.extend(
                _compare(
                    expected_item,
                    actual_item,
                    path=f"{path}[{index}]",
                    absolute_tolerance=absolute_tolerance,
                    relative_tolerance=relative_tolerance,
                )
            )
        return failures
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        if math.isclose(
            float(expected),
            float(actual),
            abs_tol=absolute_tolerance,
            rel_tol=relative_tolerance,
        ):
            return []
        return [
            AssertionFailure(
                path=path,
                expected=_json_value(expected),
                actual=_json_value(actual),
                reason=(
                    f"numeric mismatch outside atol={absolute_tolerance:g}, "
                    f"rtol={relative_tolerance:g}"
                ),
            )
        ]
    if expected != actual:
        failures.append(
            AssertionFailure(
                path=path,
                expected=_json_value(expected),
                actual=_json_value(actual),
                reason="exact value mismatch",
            )
        )
    return failures


def evaluate_case(case: CaseSpec) -> CaseOutcome:
    """Run one actual path and compare it only with its stored independent oracle."""
    planner: PlannerRecord | None = None
    try:
        provider = ScriptedProvider(
            responses=[json.dumps({"operation": case.operation})], max_attempts=1
        )
        completion = provider.complete(
            [
                Message(
                    Role.SYSTEM, "Select only the fixed operation; do not calculate an answer."
                ),
                Message(Role.USER, case.question),
            ],
            schema=_OperationPlan,
        )
        if not isinstance(completion.parsed, _OperationPlan):
            raise RuntimeError("scripted planner returned no typed operation")
        planner = PlannerRecord(
            operation=completion.parsed.operation,
            attempts=completion.attempts,
        )
        if completion.parsed.operation != case.operation:
            raise RuntimeError("scripted planner selected another operation")
        actual = case.execute()
        failures = _compare(
            case.expected,
            actual,
            path="$",
            absolute_tolerance=case.oracle.absolute_tolerance,
            relative_tolerance=case.oracle.relative_tolerance,
        )
    except Exception as error:  # one broken case must not suppress the remaining denominators
        actual = {"execution_error": type(error).__name__}
        failures = [
            AssertionFailure(
                path="$",
                expected=case.expected,
                actual=actual,
                reason="case execution failed before comparison",
            )
        ]
    return CaseOutcome(
        case_id=case.case_id,
        category=case.category,
        status=CaseStatus.FAILURE if failures else CaseStatus.SUCCESS,
        input_fixture=case.input_fixture,
        expected=case.expected,
        actual=actual,
        oracle=case.oracle,
        planner=planner,
        failures=tuple(failures),
    )


def run_suite(cases: Sequence[CaseSpec] | None = None) -> EvaluationReport:
    """Run at most the fixed selected cases and return stable ordered results."""
    selected = tuple(cases if cases is not None else smoke_cases())
    if not selected:
        raise ValueError("EVAL-SMOKE needs at least one case")
    if len(selected) > len(smoke_cases()):
        raise ValueError("EVAL-SMOKE case count exceeds its fixed bound")
    identifiers = [case.case_id for case in selected]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("EVAL-SMOKE case ids must be unique")
    outcomes = tuple(evaluate_case(case) for case in selected)
    category_summaries: dict[str, CategorySummary] = {}
    for category in sorted({outcome.category for outcome in outcomes}):
        rows = [outcome for outcome in outcomes if outcome.category == category]
        passed = sum(outcome.status is CaseStatus.SUCCESS for outcome in rows)
        category_summaries[category] = CategorySummary(
            total=len(rows), passed=passed, failed=len(rows) - passed
        )
    passed = sum(outcome.status is CaseStatus.SUCCESS for outcome in outcomes)
    return EvaluationReport(
        case_set_sha256=_case_set_sha256(selected),
        summary=SuiteSummary(
            total=len(outcomes),
            passed=passed,
            failed=len(outcomes) - passed,
            categories=category_summaries,
        ),
        cases=outcomes,
    )


def main(argv: Sequence[str] | None = None) -> int:
    cases = smoke_cases()
    by_id = {case.case_id: case for case in cases}
    parser = argparse.ArgumentParser(description="Run deterministic offline M9 EVAL-SMOKE")
    parser.add_argument(
        "--case",
        action="append",
        choices=tuple(by_id),
        help="run one case id; repeat to select several (default: all)",
    )
    arguments = parser.parse_args(argv)
    selected = cases if not arguments.case else tuple(by_id[case_id] for case_id in arguments.case)
    report = run_suite(selected)
    sys.stdout.write(report.model_dump_json(indent=2) + "\n")
    return 0 if report.summary.failed == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
