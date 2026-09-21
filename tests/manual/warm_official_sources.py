"""Operator-run warm-up of the kept official answers before a demo (not a unit test).

    python tests/manual/warm_official_sources.py <state-root> [--weekly-tables 1,2,4]

A listed series is fetched from its source the first time a question reads it, and the raw
answers are kept under `<state-root>/acquired` by what was asked (DEC-176). This script asks
ahead of time, through the same supervised worker, strict loaders and kept-answer store the
served API uses, so the first question of a demo reads kept bytes instead of waiting for
BDDK:

* FinTürk: one cell of each of the seven tables. A table's answer for a quarter holds every
  column and province, so 7 x 22 requests cover all 6,210 cells.
* Monthly bulletin: one row of each listed table, for the same reason.
* Weekly bulletin: an answer holds one item in one column, so every identity is its own 23
  requests. Only the tables named by `--weekly-tables` are warmed (default: loans, non-
  performing loans, deposits), Toplam column only.

Series are loaded into a throwaway lakehouse; only the kept answers remain. Nothing is
written to the acquisitions log the served API owns, so this may run beside it. Public
data, one request at a time, no credentials. Re-running asks only for what is not kept.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from kkb_agent.ingest.acquisition import (
    Acquisition,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
)
from kkb_agent.ingest.bddk_finturk import supported_finturk_selectors
from kkb_agent.ingest.bddk_monthly import BddkSelector, supported_selectors
from kkb_agent.ingest.bddk_weekly import supported_weekly_selectors
from kkb_agent.lakehouse import open_lakehouse

ACQUIRED_DIRECTORY = "acquired"


class KeptAnswersOnly(AcquisitionStore):
    """The served store's kept answers, without touching the log its owner writes."""

    def record(self, item: Acquisition) -> None:
        return None


def one_per_table(selectors: tuple[BddkSelector, ...]) -> list[BddkSelector]:
    first: dict[int, BddkSelector] = {}
    for selector in selectors:
        first.setdefault(selector.table, selector)
    return [first[table] for table in sorted(first)]


def chosen(weekly_tables: set[int]) -> list[tuple[str, BddkSelector]]:
    weekly = [
        selector
        for selector in supported_weekly_selectors()
        if selector.table in weekly_tables and selector.value_dimension == "TOTAL"
    ]
    return [
        *(("finturk", item) for item in one_per_table(supported_finturk_selectors())),
        *(("monthly", item) for item in one_per_table(supported_selectors())),
        *(("weekly", item) for item in weekly),
    ]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("state_root", type=Path)
    parser.add_argument("--weekly-tables", default="1,2,4")
    args = parser.parse_args()
    if not args.state_root.is_dir():
        parser.error("state root does not exist")
    tables = {int(part) for part in args.weekly_tables.split(",") if part.strip()}
    store = KeptAnswersOnly(args.state_root / ACQUIRED_DIRECTORY)
    work = chosen(tables)
    print(f"{len(work)} series to warm into {args.state_root / ACQUIRED_DIRECTORY}")
    failed = 0
    with tempfile.TemporaryDirectory() as folder, open_lakehouse(Path(folder) / "lake") as lake:
        for index, (family, selector) in enumerate(work, start=1):
            acquirer = TurnAcquirer(lake, date.today(), sources=OfficialSources(store=store))
            started = time.monotonic()
            done = acquirer.acquire(selector.internal_id())
            failed += not done.stored and done.code.value != "already_present"
            print(
                f"[{index}/{len(work)}] {family} table {selector.table} row {selector.row}: "
                f"{done.code.value} {done.detail} {done.observations} obs "
                f"{'kept' if done.from_store else 'asked'} {time.monotonic() - started:.1f} s",
                flush=True,
            )
    print("done;", failed, "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
