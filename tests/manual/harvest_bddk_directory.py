"""Operator-run harvest of the BDDK monthly bulletin's own table listing (not a unit test).

    python tests/manual/harvest_bddk_directory.py [--year 2026 --month 5]

Every request is live traffic to the public bulletin endpoint, one a second, for the sector
aggregate in TL. Two things are read and nothing else:

1. **The listing** of each of the seventeen tables for one published month: caption (title and
   unit), column headers, and every row's number and label. No observation value is kept. The
   listing is written as `src/kkb_agent/ingest/bddk_monthly_directory.py`, pinned by its own
   SHA-256, and is what the monthly adapter accepts a selector against (DEC-176).
2. **Year-boundary evidence** for each table laid out as TP / YP / Toplam: the December and
   January totals of every row, reduced to one word per row. A row whose January is under a
   quarter of its December at every examined boundary publishes a year-to-date total that
   resets ("always"); a row that never does publishes a month-end position ("never"); anything
   else is "mixed", and a row that could not be compared is "unmeasured". Behaviour is per row,
   not per table: the balance sheet carries the period's profit, which resets. Only the word
   is stored, never a value; the per-table counts are printed for `docs/BDDK_SOURCE.md`.

`curl` is used on purpose: the bulletin host omits its intermediate certificate, which curl and
browsers complete from the system store (docs/BDDK_SOURCE.md). The product's own transport is
not involved and gains no authority from this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

ENDPOINT = "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"
TARGET = Path(__file__).resolve().parents[2] / "src/kkb_agent/ingest/bddk_monthly_directory.py"
COMPONENT_HEADERS = ["", "", "", "BasitFont", "TP", "YP", "Toplam"]


def table(number: int, year: int, month: int) -> dict[str, Any]:
    body = f"tabloNo={number}&yil={year}&ay={month}&paraBirimi=TL&taraf=10001"
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["curl", "-s", "--max-time", "30", "-X", "POST", ENDPOINT, "-d", body],  # noqa: S607
        capture_output=True,
        check=True,
    )
    time.sleep(1.0)
    document = json.loads(done.stdout.decode("utf-8"))
    if document.get("success") is not True:
        raise SystemExit(f"table {number} {year}/{month}: unsuccessful response")
    report = document["Json"]
    return {
        "caption": report["caption"],
        "headers": report["colNames"],
        "rows": [row["cell"] for row in report["data"]["rows"]],
    }


def caption_parts(caption: str) -> tuple[str, str | None]:
    """("Tüketici Kredileri", "milyon TL") from the caption; the unit is None when absent."""
    head = caption.split(", Dönem:")[0].strip() if ", Dönem:" in caption else caption.strip()
    if head.endswith(")") and "(" in head:
        title, unit = head[:-1].rsplit("(", 1)
        return " ".join(title.split()), " ".join(unit.split())
    return " ".join(head.split()), None


def boundary_verdict(number: int, years: tuple[int, ...]) -> dict[int, str]:
    """Per row: is January under a quarter of December at every examined boundary?"""
    compared: dict[int, int] = {}
    fell: dict[int, int] = {}
    for year in years:
        december = {row[1]: row[6] for row in table(number, year, 12)["rows"]}
        january = {row[1]: row[6] for row in table(number, year + 1, 1)["rows"]}
        for row, before in december.items():
            after = january.get(row)
            if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
                continue
            if abs(before) < 1:
                continue
            compared[row] = compared.get(row, 0) + 1
            fell[row] = fell.get(row, 0) + (abs(after) < abs(before) * 0.25)
    verdict = {}
    for row, count in compared.items():
        if count < len(years):
            verdict[row] = "unmeasured"
        elif fell[row] == count:
            verdict[row] = "always"
        elif fell[row] == 0:
            verdict[row] = "never"
        else:
            verdict[row] = "mixed"
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=5)
    parser.add_argument("--evidence-years", type=int, nargs="*", default=[2024, 2025])
    args = parser.parse_args()

    tables: dict[int, dict[str, Any]] = {}
    for number in range(1, 18):
        listing = table(number, args.year, args.month)
        title, unit = caption_parts(str(listing["caption"]))
        tables[number] = {
            "title": title,
            "unit_text": unit,
            "headers": list(listing["headers"]),
            "rows": {
                int(cell[1]): {"label": " ".join(str(cell[2]).split()), "resets": "unmeasured"}
                for cell in listing["rows"]
            },
        }
        print(f"{number:>2} {title} ({unit}) rows={len(tables[number]['rows'])}")

    print("Year-boundary evidence, rows by verdict:")
    for number, item in tables.items():
        if item["headers"] != COMPONENT_HEADERS:
            continue
        verdict = boundary_verdict(number, tuple(args.evidence_years))
        counts: dict[str, int] = {}
        for row, entry in item["rows"].items():
            entry["resets"] = verdict.get(row, "unmeasured")
            counts[entry["resets"]] = counts.get(entry["resets"], 0) + 1
        print(f"{number:>2} {item['title']}: {json.dumps(counts, sort_keys=True)}")

    payload = {
        "harvested_month": f"{args.year}-{args.month:02d}",
        "evidence_years": list(args.evidence_years),
        "bank_group": 10001,
        "presentation_currency": "TL",
        "tables": {
            str(number): {
                **item,
                "rows": {str(row): entry for row, entry in item["rows"].items()},
            }
            for number, item in tables.items()
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
    header = (
        '"""GENERATED by tests/manual/harvest_bddk_directory.py; do not edit by hand.\n\n'
        "The BDDK monthly bulletin's own listing for the sector aggregate in TL: table titles,\n"
        "caption units, column headers, row labels, and one measured word per row saying\n"
        "whether the row resets every January. No observation value is stored. The monthly\n"
        "adapter accepts a selector only against this listing (DEC-176), and\n"
        "`DIRECTORY_SHA256` pins the exact content.\n"
        '"""\n\n'
        "# ruff: noqa: E501 - the listing keeps the source's own labels, however long\n"
        "import json\n"
        "from typing import Final\n\n"
    )
    TARGET.write_text(
        header
        + f'DIRECTORY_SHA256: Final = "{digest}"\n'
        + "DIRECTORY_JSON: Final = r'''"
        + body
        + "'''\n"
        + "DIRECTORY: Final = json.loads(DIRECTORY_JSON)\n",
        encoding="utf-8",
        newline="\n",
    )
    total = sum(len(item["rows"]) for item in tables.values())
    print(f"wrote {TARGET.name}: {total} rows, sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
