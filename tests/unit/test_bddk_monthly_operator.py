"""BDDK Monthly operator command: isolated smoke, explicit prepare, fixed failures.

Retrieval is injected with synthetic source-shaped responses; no network.
"""

import json
import tempfile

import pytest
from test_bddk_monthly_load import FakeSource

from kkb_agent.ingest import bddk_monthly_operator as operator
from kkb_agent.ingest.safe_fetch import FetchCode
from kkb_agent.lakehouse import open_lakehouse


def run(capsys, argv, source):
    code = operator.main(argv, retrieve=source)
    return code, json.loads(capsys.readouterr().out)


def test_smoke_runs_every_check_and_leaves_no_lakehouse(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    source = FakeSource()
    argv = ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "TOTAL:2026-06=120"]
    code, report = run(capsys, argv, source)
    assert code == 0 and report["passed"] is True
    (result,) = report["results"]
    assert all(result["checks"].values())
    assert result["observations"] == [["2026-06", 120.0]]
    assert result["semantics"] == {
        "unit": "TRY",
        "scale": "million",
        "frequency": "monthly",
        "observation": "stock",
        "cumulative": "none",
    }
    assert result["series_id"].startswith("BDDK:selector:v1:")
    assert result["first_run_already_present"] is False
    assert len(source.requests) == 2  # First ingestion and the idempotent repeat.
    assert list(tmp_path.iterdir()) == []


def test_expectation_mismatch_is_a_failed_check(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    argv = ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "TOTAL:2026-06=121"]
    code, report = run(capsys, argv, FakeSource())
    assert code == 1 and report["passed"] is False
    (result,) = report["results"]
    assert result["checks"]["expectations_match"] is False
    assert result["expectations"] == [{"period": "2026-06", "expected": 121.0, "actual": 120.0}]


def test_expectations_are_bound_to_their_own_component(capsys, monkeypatch, tmp_path):
    # Regression: period-only oracles collapsed so one value was checked against every component.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    argv = ["smoke", "--month", "2026-06"]
    for component, value in (("TP", 100), ("YP", 20), ("TOTAL", 120)):
        argv += ["--component", component, "--expect", f"{component}:2026-06={value}"]
    code, report = run(capsys, argv, FakeSource())
    assert code == 0 and report["passed"] is True
    assert [r["expectations"] for r in report["results"]] == [
        [{"period": "2026-06", "expected": value, "actual": value}]
        for value in (100.0, 20.0, 120.0)
    ]


def prepare(root, end="2026-03", *components):
    argv = ["prepare", "--root", str(root), "--start", "2026-01", "--end", end]
    for component in components or ("TP", "TOTAL"):
        argv += ["--component", component]
    return argv


def test_prepare_writes_explicit_root_with_parquet_and_repeats_idempotently(capsys, tmp_path):
    root = tmp_path / "lake"
    source = FakeSource()
    code, report = run(capsys, prepare(root), source)
    assert code == 0 and report["passed"] is True
    assert [r["component"] for r in report["results"]] == ["TP", "TOTAL"]
    assert [r["months"] for r in report["results"]] == [3, 3]
    assert len(source.requests) == 6  # No in-run repeat; one request per component-month.
    assert "repeat_is_idempotent" not in report["results"][0]["checks"]
    assert (root / "silver" / "silver_observations.parquet").is_file()
    code, again = run(capsys, prepare(root), FakeSource())
    assert code == 0 and all(r["first_run_already_present"] for r in again["results"])
    assert [r["manifest_id"] for r in again["results"]] == [
        r["manifest_id"] for r in report["results"]
    ]


def test_changed_window_is_refused_and_prior_series_preserved(capsys, tmp_path):
    root = tmp_path / "lake"
    assert run(capsys, prepare(root, "2026-03", "TOTAL"), FakeSource())[0] == 0
    code, report = run(capsys, prepare(root, "2026-04", "TOTAL"), FakeSource())
    assert code == 2 and report == {"mode": "prepare", "passed": False, "error": "VERSION_CONFLICT"}
    with open_lakehouse(root) as lake:
        count = lake.connection.execute("SELECT count(*) FROM silver_observations").fetchone()[0]
    assert count == 3


def test_retrieval_failure_reports_fixed_code_without_values(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    source = FakeSource(failure=FetchCode.TRANSPORT_FAILURE)
    code, report = run(capsys, ["smoke", "--month", "2026-06", "--component", "TOTAL"], source)
    assert code == 2
    assert report == {"mode": "smoke", "passed": False, "error": "RETRIEVAL_FAILED"}
    assert list(tmp_path.iterdir()) == []


def test_oversized_window_is_refused_before_retrieval(capsys, tmp_path):
    source = FakeSource()
    argv = ["prepare", "--root", str(tmp_path / "lake"), "--start", "2010-01", "--end", "2026-06"]
    code, report = run(capsys, [*argv, "--component", "TOTAL"], source)
    assert code == 2 and report["error"] == "INVALID_REQUEST" and source.requests == []


@pytest.mark.parametrize(
    "argv",
    [
        ["smoke", "--month", "2026-13", "--component", "TOTAL"],
        ["smoke", "--month", "2026-6", "--component", "TOTAL"],
        ["smoke", "--month", "2026-06"],
        ["smoke", "--month", "2026-06", "--component", "ALL"],
        ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "120"],
        ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "2026-06=120"],
        ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "ALL:2026-06=1"],
        ["smoke", "--month", "2026-06", "--component", "TOTAL", "--expect", "TP:2026-06=1"],
        [
            *["smoke", "--month", "2026-06", "--component", "TOTAL"],
            *["--expect", "TOTAL:2026-06=1", "--expect", "TOTAL:2026-06=2"],
        ],
        ["smoke", "--month", "2026-06", "--component", "TOTAL", "--root", "/tmp/x"],
        ["prepare", "--start", "2026-01", "--end", "2026-02", "--component", "TOTAL"],
    ],
)
def test_invalid_command_lines_are_rejected_before_retrieval(capsys, argv):
    source = FakeSource()
    with pytest.raises(SystemExit) as exit_info:
        operator.main(argv, retrieve=source)
    assert exit_info.value.code == 2 and source.requests == []
