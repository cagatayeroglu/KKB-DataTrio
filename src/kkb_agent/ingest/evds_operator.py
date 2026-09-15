"""Operator command for reviewed EVDS series ingestion and its acceptance checks.

    python -m kkb_agent.ingest.evds_operator smoke \
        --start 2026-01-01 --end 2026-06-30 --series TP.KFE.TR \
        --expect TP.KFE.TR:2026-06-30=231.34
    python -m kkb_agent.ingest.evds_operator prepare \
        --root data/processed/lakehouse --start 2021-01-01 --end 2026-06-30 \
        --series TP.KTF12 --series TP.TUKFIY2025.GENEL --series TP.KFE.TR

Each run makes live requests to EVDS and needs separate operator authorization;
no gate calls this. `smoke` ingests into a temporary lakehouse that is removed
afterwards, so a short check can never occupy the immutable batch of a prepared
series (a different window is VERSION_CONFLICT). `prepare` writes to an explicit
root that must stay out of Git (`data/processed/` is ignored).

Every run checks, per series: materialization, offline exact-window
verification with raw reparsing and manifest recomputation, lineage to the raw
response, read-back through the analytics reader against the independently
generated calendar, and optional `SERIES:PERIOD_END=VALUE` oracles compared
exactly. `smoke` also repeats the ingestion to prove idempotency; rerunning
`prepare` is its repeat. Exit 0 when every check passes, 1 when a check fails,
2 on refusal. Failures print a fixed code, never remote text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from pydantic import JsonValue

from kkb_agent.ingest.evds_load import (
    EvdsLoadError,
    expected_period_ends,
    ingest_series,
    materialized_series,
)
from kkb_agent.ingest.evds_request import EvdsRequest, EvdsWindow, fetch_series
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, reviewed_series
from kkb_agent.ingest.safe_fetch import FetchOutcome
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.store import Lakehouse, LakehouseError
from kkb_agent.tools.change_detection import read_series

Retrieve = Callable[[EvdsRequest], FetchOutcome]


def _day(text: str) -> date:
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            raise ValueError
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def _expectation(text: str) -> tuple[str, str, float]:
    """SERIES:YYYY-MM-DD=VALUE, keyed by period end; an oracle names its series."""
    target, separator, value = text.partition("=")
    code, colon, period = target.rpartition(":")
    try:
        if not separator or not colon or code not in REVIEWED_SERIES:
            raise ValueError
        return code, _day(period).isoformat(), float(value)
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("expected SERIES:YYYY-MM-DD=VALUE") from None


def accept(
    lake: Lakehouse,
    code: str,
    window: EvdsWindow,
    *,
    retrieve: Retrieve = fetch_series,
    expected: dict[str, float] | None = None,
    repeat: bool = True,
) -> dict[str, JsonValue]:
    """Ingest, optionally repeat, then verify from stored state. Raises EvdsLoadError."""
    series = reviewed_series(code)
    first = ingest_series(lake, code, window, retrieve=retrieve)
    checks: dict[str, bool] = {}
    if repeat:
        again = ingest_series(lake, code, window, retrieve=retrieve)
        checks["repeat_is_idempotent"] = (
            again.already_present and again.manifest_id == first.manifest_id
        )
    verified = materialized_series(lake, code, window)
    stored = read_series(lake.connection, first.series_id)
    observations = {o.period_end.isoformat(): o.value for o in stored.observations}
    calendar = [end.isoformat() for end in expected_period_ends(series, window)]
    checks |= {
        "stored_window_verified": verified is not None
        and verified.manifest_id == first.manifest_id,
        "lineage_reaches_raw_response": len(lake.lineage.sources_of(first.lineage_id)) == 1,
        "read_back_matches_calendar": list(observations) == calendar,
        "expectations_match": all(
            observations.get(period) == value for period, value in (expected or {}).items()
        ),
    }
    semantics = stored.semantics
    return {
        "series": code,
        "series_id": first.series_id,
        "manifest_id": first.manifest_id,
        "window": {"start": window.start.isoformat(), "end": window.end.isoformat()},
        "observations_count": first.observations,
        "missing_values": first.missing_values,
        "excluded_outside_window": first.excluded_outside_window,
        "first_run_already_present": first.already_present,
        "semantics": {
            "unit": semantics.unit,
            "scale": semantics.scale.value,
            "frequency": semantics.frequency.value,
            "anchor": semantics.anchor.value if semantics.anchor else None,
            "observation": semantics.observation.value,
            "aggregation": semantics.aggregation.value,
            "base_year": semantics.base_year,
        },
        "observations": [[period, value] for period, value in observations.items()],
        "expectations": [
            {"period_end": period, "expected": value, "actual": observations.get(period)}
            for period, value in sorted((expected or {}).items())
        ],
        "checks": dict(checks),
        "passed": all(checks.values()),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kkb_agent.ingest.evds_operator")
    modes = parser.add_subparsers(dest="mode", required=True)
    smoke = modes.add_parser("smoke", help="a short window into a temporary lakehouse")
    prepare = modes.add_parser("prepare", help="an explicit window into a persistent root")
    prepare.add_argument("--root", type=Path, required=True)
    for mode in (smoke, prepare):
        mode.add_argument("--start", type=_day, required=True)
        mode.add_argument("--end", type=_day, required=True)
        mode.add_argument(
            "--series", choices=sorted(REVIEWED_SERIES), action="append", required=True
        )
        mode.add_argument("--expect", type=_expectation, action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None, *, retrieve: Retrieve = fetch_series) -> int:
    """`retrieve` is trusted test injection only; the command line cannot set it."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    codes = list(dict.fromkeys(arguments.series))
    expected: dict[tuple[str, str], float] = {}
    for code, period, value in arguments.expect:
        # Never let a later oracle silently replace or skip an earlier one.
        if (code, period) in expected or code not in codes:
            parser.error("each --expect needs a requested series and a distinct period end")
        expected[(code, period)] = value
    report: dict[str, JsonValue] = {"mode": arguments.mode}

    def run(lake: Lakehouse, window: EvdsWindow, repeat: bool) -> list[JsonValue]:
        return [
            accept(
                lake,
                code,
                window,
                retrieve=retrieve,
                expected={p: v for (c, p), v in expected.items() if c == code},
                repeat=repeat,
            )
            for code in codes
        ]

    try:
        window = EvdsWindow(start=arguments.start, end=arguments.end)
        for code in codes:
            EvdsRequest(code=code, window=window)  # Refuse every unfit series before any fetch.
        if arguments.mode == "smoke":
            with tempfile.TemporaryDirectory(prefix="kkb-evds-smoke-") as root:
                with open_lakehouse(Path(root)) as lake:
                    results = run(lake, window, repeat=True)
            report["root"] = "temporary; removed"
        else:
            with open_lakehouse(arguments.root) as lake:
                results = run(lake, window, repeat=False)
                report["silver_parquet"] = [path.name for path in lake.export_silver()]
            report["root"] = str(arguments.root)
    except (ValueError, LakehouseError) as error:
        code = error.code.value if isinstance(error, EvdsLoadError) else "INVALID_REQUEST"
        report.update({"passed": False, "error": code})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    report["results"] = results
    report["passed"] = all(isinstance(r, dict) and r["passed"] is True for r in results)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
