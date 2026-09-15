"""Independent-oracle and runner regressions for M9-05 EVAL-SMOKE."""

from __future__ import annotations

import json
import socket
from dataclasses import replace

import kkb_agent.evaluation.cases as case_module
from kkb_agent.evaluation import CaseStatus, evaluate_case, run_suite, smoke_cases
from kkb_agent.evaluation.runner import main


def test_fixed_smoke_cases_pass_with_category_denominators() -> None:
    report = run_suite()

    assert [case.case_id for case in report.cases] == [
        "turn1-monthly-directions",
        "turn2-deflate-credit-only",
        "turn3-add-monthly-kfe",
        "table-direction-relationship",
        "unknown-scale-abstention",
    ]
    assert (report.summary.total, report.summary.passed, report.summary.failed) == (5, 5, 0)
    assert all(case.status is CaseStatus.PASS and not case.failures for case in report.cases)
    assert set(report.summary.categories) == {
        "abstention",
        "finance_semantics",
        "multi_turn_state",
        "relationship",
        "table_transform",
    }
    assert all(
        summary.total == summary.passed == 1 for summary in report.summary.categories.values()
    )


def test_report_is_byte_deterministic_and_json_serializable() -> None:
    first = run_suite().model_dump_json(indent=2)
    second = run_suite().model_dump_json(indent=2)

    assert first == second
    decoded = json.loads(first)
    assert decoded["offline"] is True and decoded["deterministic"] is True
    assert len(decoded["case_set_sha256"]) == 64
    assert all(case["oracle"]["independence"] for case in decoded["cases"])


def test_wrong_independent_oracle_is_a_clear_failure() -> None:
    case = smoke_cases()[0]
    expected = dict(case.expected)
    expected["highlighted_periods"] = ["2021-02-28"]

    outcome = evaluate_case(replace(case, expected=expected))

    assert outcome.status is CaseStatus.FAIL
    assert [(failure.path, failure.reason) for failure in outcome.failures] == [
        ("$.highlighted_periods[0]", "exact value mismatch")
    ]


def test_an_incorrect_production_result_cannot_agree_with_the_oracle(monkeypatch) -> None:
    production = case_module.co_movement

    def wrong_result(*args, **kwargs):
        result = production(*args, **kwargs).model_copy(deep=True)
        count = next(
            value
            for value in result.values
            if value.label == f"transitions where {case_module.RATE_LABEL} fell"
        )
        count.value = 99.0
        return result

    monkeypatch.setattr(case_module, "co_movement", wrong_result)
    outcome = evaluate_case(smoke_cases()[0])

    assert outcome.status is CaseStatus.FAIL
    assert any(failure.path == "$.counts.rate_fell" for failure in outcome.failures)


def test_suite_remains_offline_when_socket_connections_are_forbidden(monkeypatch) -> None:
    def refuse_network(*args, **kwargs):
        raise AssertionError("EVAL-SMOKE attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse_network)

    assert run_suite().summary.failed == 0


def test_cli_outputs_machine_readable_report_and_selects_cases(capsys) -> None:
    exit_code = main(["--case", "unknown-scale-abstention"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "categories": {"abstention": {"total": 1, "passed": 1, "failed": 0}},
    }
    assert report["cases"][0]["status"] == "pass"
