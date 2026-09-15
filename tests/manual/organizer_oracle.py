"""Independent organizer three-turn oracle over a prepared pool (read-only, no tools).

Plain SQL rows and Decimal arithmetic only; none of the analytics, transform or
verifier code is imported. It prints counts and a few exact values to compare
against the live answer cells. Usage:

    python tests/manual/organizer_oracle.py data/processed/lakehouse
"""

import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import duckdb

TOTAL = "BDDK:selector:v1:fa6e3c79bc8c9ead8680507965533a20366829cdf7aab8aa754224beb82b0f66"
RATE = "EVDS:TP.KTF12"
CPI = "EVDS:TP.TUKFIY2025.GENEL"
KFE = "EVDS:TP.KFE.TR"
FIRST, LAST = "2021-01", "2025-12"


def monthly(connection, series_id):
    rows = connection.execute(
        "SELECT period_end, value FROM silver_observations WHERE series_id = ? ORDER BY period_end",
        [series_id],
    ).fetchall()
    return {f"{end:%Y-%m}": Decimal(str(value)) for end, value in rows if value is not None}


def weekly_average_by_end(connection, series_id):
    groups = defaultdict(list)
    for end, value in connection.execute(
        "SELECT period_end, value FROM silver_observations WHERE series_id = ? ORDER BY period_end",
        [series_id],
    ).fetchall():
        if value is not None:
            groups[f"{end:%Y-%m}"].append(Decimal(str(value)))
    return {month: sum(values) / len(values) for month, values in groups.items()}


def main(root: Path) -> None:
    connection = duckdb.connect(str(root / "kkb.duckdb"), read_only=True)
    try:
        balance = monthly(connection, TOTAL)
        cpi = monthly(connection, CPI)
        kfe = monthly(connection, KFE)
        rate = weekly_average_by_end(connection, RATE)
    finally:
        connection.close()
    months = sorted(m for m in balance if FIRST <= m <= LAST)
    transitions = list(zip(months, months[1:], strict=False))
    base = cpi[LAST]
    real = {m: balance[m] * base / cpi[m] for m in months}
    rate_fell = [(a, b) for a, b in transitions if rate[b] < rate[a]]
    nominal_not_rising = [b for a, b in rate_fell if balance[b] <= balance[a]]
    kfe_up_real_not_rising = [b for a, b in rate_fell if kfe[b] > kfe[a] and real[b] <= real[a]]
    real_not_rising = [b for a, b in transitions if real[b] <= real[a]]
    rate_fell_real_not_rising = [b for a, b in rate_fell if real[b] <= real[a]]
    print(
        json.dumps(
            {
                "months": len(months),
                "transitions": len(transitions),
                "turn1": {
                    "rate_fell": len(rate_fell),
                    "balance_not_rising": nominal_not_rising,
                    "balance_change": {
                        b: str(balance[b] - balance[a])
                        for a, b in rate_fell
                        if b in nominal_not_rising
                    },
                },
                "turn2": {
                    "cpi_base": LAST,
                    "real_2021_01": str(round(real["2021-01"], 1)),
                    "real_2023_12": str(round(real["2023-12"], 1)),
                    "real_2025_12": str(round(real["2025-12"], 1)),
                    "real_highlighted": {
                        m: str(round(real[m], 1))
                        for m in ("2021-02", "2021-05", "2023-12", "2024-01")
                    },
                },
                "turn3": {
                    "kfe_up": sum(1 for a, b in transitions if kfe[b] > kfe[a]),
                    "real_not_rising": len(real_not_rising),
                    "rate_fell_real_not_rising": len(rate_fell_real_not_rising),
                    "same_months_without_kfe_condition": (
                        rate_fell_real_not_rising == kfe_up_real_not_rising
                    ),
                    "rate_fell_kfe_up_real_not_rising": len(kfe_up_real_not_rising),
                    "months": kfe_up_real_not_rising,
                    "kfe_2025_12": str(kfe["2025-12"]),
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
