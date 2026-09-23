"""E6: what the anomaly and breakpoint tools are scored on, measured over the pool.

Reads the prepared lakehouse directly and scores every published change of every
series both ways - the difference in the series' own unit, and the log ratio to the
level it moved from. The scoring arithmetic is written out here rather than imported,
so the tools are checked against an independent implementation and not against
themselves. No model, source or network call.

    python tests/manual/measure_change_basis.py data/processed/lakehouse
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import date, timedelta
from math import log
from pathlib import Path
from statistics import fmean, median

import duckdb

MAD_TO_SIGMA = 0.6745
MEANAD_TO_SIGMA = 1.253314
ANOMALY_THRESHOLD = 3.5
BREAK_THRESHOLD = 3.0
MINIMUM_SEGMENT = 6
MAXIMUM_POINTS = 3


def scores(values: Sequence[float]) -> list[float]:
    """The Iglewicz-Hoaglin modified z-score, with the paper's zero-MAD fallback."""
    centre = median(values)
    deviations = [abs(value - centre) for value in values]
    spread = median(deviations)
    if spread == 0:
        spread = fmean(deviations) * MEANAD_TO_SIGMA * MAD_TO_SIGMA
    if spread == 0:
        return [0.0 for _ in values]
    return [MAD_TO_SIGMA * (value - centre) / spread for value in values]


def pooled(before: Sequence[float], after: Sequence[float]) -> float:
    total = sum((value - fmean(part)) ** 2 for part in (before, after) for value in part)
    degrees = len(before) + len(after) - 2
    return (total / degrees) ** 0.5 if degrees > 0 else 0.0


def statistic(values: Sequence[float], split: int) -> float:
    before, after = values[:split], values[split:]
    spread = pooled(before, after)
    if spread == 0:
        return 0.0
    error = spread * ((1 / len(before) + 1 / len(after)) ** 0.5)
    return abs(fmean(before) - fmean(after)) / error


def breakpoints(values: Sequence[float]) -> list[int]:
    """Binary segmentation, the same shape `analytics/breakpoint.py` runs."""
    found: list[int] = []
    segments = [(0, len(values))]
    while segments and len(found) < MAXIMUM_POINTS:
        begin, finish = segments.pop(0)
        part = values[begin:finish]
        if len(part) < 2 * MINIMUM_SEGMENT:
            continue
        best = max(
            (
                (begin + k, statistic(part, k))
                for k in range(MINIMUM_SEGMENT, len(part) - MINIMUM_SEGMENT + 1)
            ),
            key=lambda pair: pair[1],
        )
        if best[1] < BREAK_THRESHOLD:
            continue
        found.append(best[0])
        segments.extend([(begin, best[0]), (best[0], finish)])
        segments.sort()
    return sorted(found)


def top(ends: Sequence[date], values: Sequence[float], count: int = 2) -> str:
    order = sorted(range(len(values)), key=lambda i: -abs(values[i]))[:count]
    return ", ".join(f"{ends[i + 1].isoformat()} at {values[i]:.2f}" for i in order)


def main(root: str) -> int:
    connection = duckdb.connect(str(Path(root) / "kkb.duckdb"), read_only=True)
    listed = connection.execute(
        "select series_id, observation from silver_series order by series_id"
    ).fetchall()
    non_adjacent = 0
    for series_id, kind in listed:
        rows = connection.execute(
            "select period_start, period_end, value from silver_observations "
            "where series_id = ? order by period_end",
            [series_id],
        ).fetchall()
        published = [(start, end, float(value)) for start, end, value in rows if value is not None]
        non_adjacent += sum(
            1
            for (_, before_end, _), (start, _, _) in zip(published, published[1:], strict=False)
            if start != before_end + timedelta(days=1)
        )
        ends = [end for _, end, _ in published]
        levels = [value for _, _, value in published]
        if len(levels) < 2 * MINIMUM_SEGMENT + 1:
            continue
        difference = [levels[i] - levels[i - 1] for i in range(1, len(levels))]
        ratio = [log(levels[i] / levels[i - 1]) for i in range(1, len(levels))]
        by_difference, by_ratio = scores(difference), scores(ratio)
        print(f"\n{series_id} ({kind})")
        print(f"  anomaly  difference: {top(ends, by_difference)}")
        print(f"  anomaly  ratio     : {top(ends, by_ratio)}")
        print(
            f"  anomaly  flags past {ANOMALY_THRESHOLD}: "
            f"difference={sum(1 for s in by_difference if abs(s) > ANOMALY_THRESHOLD)} "
            f"ratio={sum(1 for s in by_ratio if abs(s) > ANOMALY_THRESHOLD)}"
        )
        print(
            f"  breaks   difference: {[ends[p + 1].isoformat() for p in breakpoints(difference)]}"
            f"  ratio: {[ends[p + 1].isoformat() for p in breakpoints(ratio)]}"
        )
    print(f"\nnon-adjacent published pairs across the pool: {non_adjacent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "data/processed/lakehouse"))
