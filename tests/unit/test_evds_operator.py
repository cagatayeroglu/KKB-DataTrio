"""EVDS operator command: isolated smoke, explicit prepare, fixed failures.

Retrieval is injected with synthetic source-shaped responses; no network.
"""

import json
import tempfile

import pytest
from test_evds_load import FakeSource

from kkb_agent.ingest import evds_operator as operator
from kkb_agent.ingest.safe_fetch import FetchCode
from kkb_agent.lakehouse import open_lakehouse


def run(capsys, argv, source):
    code = operator.main(argv, retrieve=source)
    return code, json.loads(capsys.readouterr().out)


def smoke(*extra, series=("TP.KFE.TR",)):
    argv = ["smoke", "--start", "2021-01-01", "--end", "2021-06-30"]
    for code in series:
        argv += ["--series", code]
    return [*argv, *extra]


def test_smoke_runs_every_check_and_leaves_no_lakehouse(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    source = FakeSource()
    code, report = run(
        capsys,
        smoke(
            "--expect",
            "TP.KFE.TR:2021-06-30=105.25",
            "--expect",
            "TP.KTF12:2021-01-01=100.25",
            series=("TP.KFE.TR", "TP.KTF12"),
        ),
        source,
    )
    assert code == 0 and report["passed"] is True
    kfe, rate = report["results"]
    assert all(kfe["checks"].values()) and all(rate["checks"].values())
    assert kfe["observations"][-1] == ["2021-06-30", 105.25]
    assert kfe["semantics"]["base_year"] == 2023 and rate["semantics"]["anchor"] == "friday"
    assert rate["observations_count"] == 26 and rate["excluded_outside_window"] == 1
    assert len(source.requests) == 4  # First ingestion and the repeat, per series.
    assert list(tmp_path.iterdir()) == []


def test_expectation_mismatch_is_a_failed_check(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    code, report = run(capsys, smoke("--expect", "TP.KFE.TR:2021-06-30=105.26"), FakeSource())
    assert code == 1 and report["results"][0]["checks"]["expectations_match"] is False


def prepare(root, end="2021-06-30"):
    return [
        *["prepare", "--root", str(root), "--start", "2021-01-01", "--end", end],
        *["--series", "TP.TUKFIY2025.GENEL", "--series", "TP.GENENDEKS.T1"],
    ]


def test_prepare_writes_parquet_without_repeat_and_reruns_idempotently(capsys, tmp_path):
    root = tmp_path / "lake"
    source = FakeSource()
    code, report = run(capsys, prepare(root), source)
    assert code == 0 and len(source.requests) == 2
    assert "repeat_is_idempotent" not in report["results"][0]["checks"]
    assert (root / "silver" / "silver_series.parquet").is_file()
    code, again = run(capsys, prepare(root), FakeSource())
    assert code == 0 and all(r["first_run_already_present"] for r in again["results"])


def test_changed_window_is_refused_and_prior_series_preserved(capsys, tmp_path):
    root = tmp_path / "lake"
    assert run(capsys, prepare(root), FakeSource())[0] == 0
    code, report = run(capsys, prepare(root, "2021-07-31"), FakeSource())
    assert code == 2 and report == {"mode": "prepare", "passed": False, "error": "VERSION_CONFLICT"}
    with open_lakehouse(root) as lake:
        assert lake.connection.execute("SELECT count(*) FROM silver_observations").fetchone() == (
            12,
        )


def test_retrieval_failure_reports_a_fixed_code(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    code, report = run(capsys, smoke(), FakeSource(failure=FetchCode.TIMEOUT))
    assert code == 2 and report == {"mode": "smoke", "passed": False, "error": "RETRIEVAL_FAILED"}
    assert list(tmp_path.iterdir()) == []


def test_unfit_window_is_refused_before_any_retrieval(capsys):
    source = FakeSource()
    argv = ["smoke", "--start", "2021-01-02", "--end", "2021-06-30"]
    code, report = run(capsys, [*argv, "--series", "TP.KTF12", "--series", "TP.KFE.TR"], source)
    assert code == 2 and report["error"] == "INVALID_REQUEST" and source.requests == []


@pytest.mark.parametrize(
    "argv",
    [
        ["smoke", "--start", "2021-01-01", "--end", "2021-06-30"],
        [*smoke()[:5], "--series", "TP.KBK.TRY.18"],
        ["smoke", "--start", "20210101", "--end", "2021-06-30", "--series", "TP.KFE.TR"],
        smoke("--expect", "2021-06-30=1"),
        smoke("--expect", "TP.KTF12:2021-01-01=1"),
        smoke("--expect", "TP.KFE.TR:2021-06=1"),
        smoke("--expect", "TP.KFE.TR:2021-06-30=1", "--expect", "TP.KFE.TR:2021-06-30=2"),
        smoke("--root", "/tmp/x"),
    ],
)
def test_invalid_command_lines_are_rejected_before_retrieval(argv):
    source = FakeSource()
    with pytest.raises(SystemExit) as exit_info:
        operator.main(argv, retrieve=source)
    assert exit_info.value.code == 2 and source.requests == []
