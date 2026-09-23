"""Operator-run harvest of the BDDK weekly bulletin's own listing (not a unit test).

    python tests/manual/harvest_bddk_weekly_directory.py

The weekly bulletin's page renders one table at a time, in the order a person reads it, and
every value cell names the item it charts: `ShowModalGraph('<table>.0.<row>','TRY',<column>)`.
This script walks the nine tables through the page's own table switch and keeps what a
person reads there: table title, row number and label, the row a sub-item sits under, the
item id and which columns the row has. No observation value is stored. The listing is
written as `src/kkb_agent/ingest/bddk_weekly_directory.py`, pinned by its own SHA-256.

Ten requests, one a second. An earlier version asked the series endpoint for ids 1..120 of
each table and stopped after eight misses; it missed Menkul Değerler and Yabancı Para
Pozisyonu, whose ids start at 11 and 14, and it could not see which row a sub-item belongs to.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

PAGE = "https://www.bddk.org.tr/BultenHaftalik"
ENDPOINT = "https://www.bddk.org.tr/BultenHaftalik/tr/Home/KiyaslamaJsonGetir"
TARGET = Path(__file__).resolve().parents[2] / "src/kkb_agent/ingest/bddk_weekly_directory.py"
SWITCH = re.compile(
    r'<form action="/BultenHaftalik/" method="post">'
    r'<input name="__RequestVerificationToken" type="hidden" value="([^"]+)"'
)
MENU = re.compile(r"TabloDegistir\('(\d+)'\).*?<span class=\"text\">([^<]+)</span>", re.S)
ROW = re.compile(r'<tr class="satir"[^>]*>(.*?)</tr>', re.S)
NUMBER = re.compile(r'<td scope="row"[^>]*>\s*(\d+)\s*</td>')
LABEL = re.compile(r'<td class="ortala">(.*?)</td>', re.S)
CELL = re.compile(
    r'data-label="([^"]*)"[^>]*onclick="ShowModalGraph\(\'(\d+)\.0\.(\d+)\',\'TRY\',(\d)\)"'
)
UNIT = re.compile(r"Birim:\s*<b>\s*([^<]+?)\s*</b>")
TAG = re.compile(r"<[^>]+>")


def text_of(fragment: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", fragment)).replace("\xa0", " ").split())


def curl(jar: str, *args: str) -> str:
    """One request; a transient transport failure (TLS reset, timeout) is asked again."""
    for attempt in range(4):
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                "curl",
                "-s",
                "--max-time",
                "60",
                "-H",
                "User-Agent: Mozilla/5.0",
                "-b",
                jar,
                "-c",
                jar,
                *args,
            ],  # noqa: S607, E501
            capture_output=True,
            check=False,
        )
        time.sleep(1.0)
        if done.returncode == 0 and done.stdout:
            return done.stdout.decode("utf-8", errors="replace")
        time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("the source did not answer after four attempts")


def rows_of(page: str, table: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    parent: str | None = None
    for body in ROW.findall(page):
        number, label, cells = NUMBER.search(body), LABEL.search(body), CELL.findall(body)
        if number is None or label is None or not cells:
            continue  # the page keeps empty template rows
        if {int(found) for _, found, _, _ in cells} != {table}:
            raise RuntimeError(f"table {table} shows an item of another table")
        items = {int(row) for _, _, row, _ in cells}
        if len(items) != 1:
            raise RuntimeError(f"table {table} row {number.group(1)} charts several items")
        name = text_of(label.group(1))
        indented = "font-style:italic" in label.group(1)
        if not indented:
            parent = name
        rows.append(
            {
                "number": int(number.group(1)),
                "row": items.pop(),
                "label": name,
                "parent": parent if indented else None,
                "columns": {column: header for header, _, _, column in cells},
            }
        )
    return rows


def main() -> int:
    with tempfile.TemporaryDirectory() as folder:
        jar = str(Path(folder) / "cookies.txt")
        page = curl(jar, PAGE)
        menu = [(code, html.unescape(title).strip()) for code, title in MENU.findall(page)]
        tables: dict[str, object] = {}
        units = set()
        for position, (code, title) in enumerate(menu, start=1):
            token = SWITCH.search(page)
            if token is None:
                raise RuntimeError("the page no longer carries its table switch")
            page = curl(
                jar, "-L", "-X", "POST", PAGE + "/",
                "--data-urlencode", "__RequestVerificationToken=" + token.group(1),
                "--data-urlencode", "tabloId=" + code,
            )  # fmt: skip
            unit = UNIT.search(page)
            units.add(text_of(unit.group(1)) if unit else "")
            rows = rows_of(page, position)
            tables[str(position)] = {"title": title, "rows": rows}
            print(f"{position} {title}: {len(rows)} rows", flush=True)
    if len(units) != 1:
        raise RuntimeError(f"the tables do not share one unit caption: {sorted(units)}")
    payload = {
        "source": ENDPOINT,
        "page": PAGE,
        "side": "Sektör",
        "unit_text": units.pop(),
        "tables": tables,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
    TARGET.write_text(
        '"""GENERATED by tests/manual/harvest_bddk_weekly_directory.py; do not edit by hand.\n\n'
        "The BDDK weekly bulletin's own listing: tables, rows in the order the page shows them,\n"
        "the row a sub-item sits under, item ids and columns, for the sector aggregate in TL.\n"
        'No observation value is stored; `DIRECTORY_SHA256` pins the exact content.\n"""\n\n'
        "# ruff: noqa: E501 - the listing keeps the source's own labels, however long\n"
        "import json\nfrom typing import Any, Final\n\n"
        f'DIRECTORY_SHA256: Final = "{digest}"\n'
        "DIRECTORY_JSON: Final = r'''" + body + "'''\n"
        "DIRECTORY: Final[dict[str, Any]] = json.loads(DIRECTORY_JSON)\n",
        encoding="utf-8",
        newline="\n",
    )
    total = sum(len(table["rows"]) for table in tables.values())  # type: ignore[index]
    print(f"wrote {TARGET.name}: {len(tables)} tables, {total} rows, sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
