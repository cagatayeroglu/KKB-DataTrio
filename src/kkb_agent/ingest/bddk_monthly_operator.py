"""Operator command for reviewed BDDK Monthly ingestion and its acceptance checks.

    python -m kkb_agent.ingest.bddk_monthly_operator smoke \
        --month 2026-06 --component TOTAL --expect TOTAL:2026-06=801438
    python -m kkb_agent.ingest.bddk_monthly_operator prepare \
        --root data/processed/lakehouse --start 2021-01 --end 2026-06 \
        --component TP --component YP --component TOTAL

Each run makes live requests to BDDK and needs separate operator authorization;
no gate calls this. `smoke` ingests into a temporary lakehouse that is removed
afterwards, so a one-month check can never occupy the immutable batch of a
prepared series (a different range is VERSION_CONFLICT). `prepare` writes to an
explicit root that must stay out of Git (`data/processed/` is ignored).

Every run checks, per component: materialization, offline exact-window
verification with raw-byte reparsing, lineage reaching each raw response and
read-back through the analytics reader. `smoke` also repeats the ingestion to
prove idempotency; rerunning `prepare` is its repeat, so a long window is not
fetched twice. Optional `--expect`
values are independent oracles compared exactly. The JSON report carries public
official values and identities only; failures print a fixed code, never remote
text. Exit 0 when every check passes, 1 when a check fails, 2 on refusal.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import JsonValue

from kkb_agent.ingest.bddk_monthly import BddkSelector, MonthlyPeriod
from kkb_agent.ingest.bddk_monthly_load import (
    MonthlyLoadError,
    ingest_monthly,
    materialized_monthly,
)
from kkb_agent.ingest.bddk_monthly_request import (
    MonthlyRange,
    MonthlyRequest,
    fetch_monthly,
    period_key,
)
from kkb_agent.ingest.safe_fetch import FetchOutcome
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.store import Lakehouse, LakehouseError
from kkb_agent.tools.change_detection import read_series

Retrieve = Callable[[MonthlyRequest], FetchOutcome]
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
COMPONENTS = ("TP", "YP", "TOTAL")


def _month(text: str) -> MonthlyPeriod:
    match = _MONTH.fullmatch(text)
    if match is None:
        raise argparse.ArgumentTypeError("expected YYYY-MM")
    try:
        return MonthlyPeriod(year=int(match[1]), month=int(match[2]))
    except ValueError:
        raise argparse.ArgumentTypeError("expected a valid YYYY-MM month") from None


def _expectation(text: str) -> tuple[str, str, float]:
    """COMPONENT:YYYY-MM=VALUE; an oracle always names the component it checks."""
    target, separator, value = text.partition("=")
    component, colon, period = target.partition(":")
    try:
        if not separator or not colon or component not in COMPONENTS:
            raise ValueError
        return component, period_key(_month(period)), float(value)
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("expected COMPONENT:YYYY-MM=VALUE") from None


def housing_selector(component: str) -> BddkSelector:
    """The reviewed M3-05 contract; the component is always explicit."""
    return BddkSelector.model_validate(
        {
            "bulletin_family": "monthly",
            "table": 4,
            "row": 2,
            "bank_group": 10001,
            "presentation_currency": "TL",
            "value_dimension": component,
        }
    )


def accept(
    lake: Lakehouse,
    selector: BddkSelector,
    window: MonthlyRange,
    *,
    retrieve: Retrieve = fetch_monthly,
    expected: dict[str, float] | None = None,
    repeat: bool = True,
) -> dict[str, JsonValue]:
    """Ingest, optionally repeat, then verify from stored state. Raises MonthlyLoadError.

    `prepare` skips the in-run repeat so a long window is not fetched twice;
    rerunning the same command is its idempotency check.
    """
    first = ingest_monthly(lake, selector, window, retrieve=retrieve)
    checks: dict[str, bool] = {}
    if repeat:
        again = ingest_monthly(lake, selector, window, retrieve=retrieve)
        checks["repeat_is_idempotent"] = (
            again.already_present and again.manifest_id == first.manifest_id
        )
    verified = materialized_monthly(lake, selector, window)
    series = read_series(lake.connection, first.series_id)
    observations = {
        period_key(MonthlyPeriod(year=o.period_end.year, month=o.period_end.month)): o.value
        for o in series.observations
    }
    sources = lake.lineage.sources_of(first.lineage_id)
    comparisons: list[JsonValue] = [
        {"period": period, "expected": value, "actual": observations.get(period)}
        for period, value in sorted((expected or {}).items())
    ]
    semantics = series.semantics
    checks |= {
        "stored_window_verified": verified is not None
        and verified.manifest_id == first.manifest_id,
        "lineage_reaches_each_response": len(sources) == first.months,
        "read_back_matches_window": list(observations) == [period_key(p) for p in window.periods()],
        "expectations_match": all(
            observations.get(period) == value for period, value in (expected or {}).items()
        ),
    }
    return {
        "component": selector.value_dimension,
        "series_id": first.series_id,
        "manifest_id": first.manifest_id,
        "window": {"start": period_key(window.start), "end": period_key(window.end)},
        "months": first.months,
        "missing_values": first.missing_values,
        "first_run_already_present": first.already_present,
        "semantics": {
            "unit": semantics.unit,
            "scale": semantics.scale.value,
            "frequency": semantics.frequency.value,
            "observation": semantics.observation.value,
            "cumulative": semantics.cumulative.value,
        },
        "observations": [[period, value] for period, value in observations.items()],
        "expectations": comparisons,
        "checks": dict(checks),
        "passed": all(checks.values()),
    }


def _run(
    lake: Lakehouse,
    components: Sequence[str],
    window: MonthlyRange,
    retrieve: Retrieve,
    expected: dict[tuple[str, str], float],
    *,
    repeat: bool,
) -> list[JsonValue]:
    return [
        accept(
            lake,
            housing_selector(c),
            window,
            retrieve=retrieve,
            expected={period: value for (k, period), value in expected.items() if k == c},
            repeat=repeat,
        )
        for c in components
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kkb_agent.ingest.bddk_monthly_operator")
    modes = parser.add_subparsers(dest="mode", required=True)
    smoke = modes.add_parser("smoke", help="one month into a temporary lakehouse")
    smoke.add_argument("--month", type=_month, required=True)
    prepare = modes.add_parser("prepare", help="an explicit window into a persistent root")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--start", type=_month, required=True)
    prepare.add_argument("--end", type=_month, required=True)
    for mode in (smoke, prepare):
        mode.add_argument("--component", choices=COMPONENTS, action="append", required=True)
        mode.add_argument("--expect", type=_expectation, action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None, *, retrieve: Retrieve = fetch_monthly) -> int:
    """`retrieve` is trusted test injection only; the command line cannot set it."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    components = list(dict.fromkeys(arguments.component))
    expected: dict[tuple[str, str], float] = {}
    for component, period, value in arguments.expect:
        # Never let a later oracle silently replace or skip an earlier one.
        if (component, period) in expected or component not in components:
            parser.error("each --expect needs a requested component and a distinct month")
        expected[(component, period)] = value
    report: dict[str, JsonValue] = {"mode": arguments.mode}
    try:
        if arguments.mode == "smoke":
            window = MonthlyRange(start=arguments.month, end=arguments.month)
            with tempfile.TemporaryDirectory(prefix="kkb-bddk-smoke-") as root:
                with open_lakehouse(Path(root)) as lake:
                    results = _run(lake, components, window, retrieve, expected, repeat=True)
            report["root"] = "temporary; removed"
        else:
            window = MonthlyRange(start=arguments.start, end=arguments.end)
            with open_lakehouse(arguments.root) as lake:
                results = _run(lake, components, window, retrieve, expected, repeat=False)
                report["silver_parquet"] = [path.name for path in lake.export_silver()]
            report["root"] = str(arguments.root)
    except (ValueError, LakehouseError) as error:
        code = error.code.value if isinstance(error, MonthlyLoadError) else "INVALID_REQUEST"
        report.update({"passed": False, "error": code})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    report["results"] = results
    report["passed"] = all(isinstance(r, dict) and r["passed"] is True for r in results)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
