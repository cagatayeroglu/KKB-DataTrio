# M1-09 synthetic XLSX fixtures

Created with openpyxl under [DEC-111](../../../docs/DECISIONS.md#dec-111--openpyxl-for-the-untrusted-xlsx-boundary). All data is synthetic. These are ordinary `.xlsx` files with no formulas, macros, external links, hidden sheets or source-specific assumptions.

| File | Worksheet order | Exact table shape |
| --- | --- | --- |
| [single_sheet.xlsx](single_sheet.xlsx) | `Observations` | Header `as_of, measure, label`; 3 data rows, 3 columns |
| [multi_sheet.xlsx](multi_sheet.xlsx) | `Observations`, `Categories` | Same observations; `Categories` has header `code, description` and 2 data rows |

`Observations` contains typed dates 2026-01-31, 2026-02-28, 2026-03-31; numeric values 100, missing, 125.5; and text `Örnek`, `çığ`, `C`. The missing cell is blank, never zero. `Categories` contains `A, Synthetic alpha` and `B, Örnek beta`. It is a second independent table, not an instruction to join it to observations. Date display is `yyyy-mm-dd`. Dates/numbers do not establish unit, frequency, time role, stock/flow, cumulative or reset semantics; all remain unknown without an explicit declaration.

## Sheet-selection contract

[`select_sheet(workbook, selection=None)`](../../../src/kkb_agent/xlsx_sheets.py) accepts an already-open openpyxl workbook and returns `SheetSelection(status, sheets, selection, code)`. It lists tabular worksheets in workbook order, including hidden worksheets if present, and excludes chart-only tabs. It does not inspect cell values, infer table validity, or use the active tab as a default.

- One worksheet with no selection: `selected` with its exact name.
- Multiple worksheets with no selection: `needs_input`, `SELECTION_REQUIRED`, all eligible names, no selected sheet.
- Exact existing name: `selected` with that name. Case and whitespace are not normalized.
- Nonexistent/empty name: `needs_input`, `UNKNOWN_SHEET`, eligible names, no fallback selection.
- No tabular worksheet: `rejected`, `NO_WORKSHEETS`.

Names are untrusted metadata, not paths or instructions. The result is selection metadata, **not** a loaded table or an `ok` ingestion/profile result. A later adapter must preserve `needs_input` with no data reference/count/profile as specified in [INGESTION_PROFILE](../../../docs/INGESTION_PROFILE.md). The caller owns safe workbook opening, resource limits and closing. No upload loader is enabled here; M1-10 still owns bounded XLSX parsing, corrupt-file handling and parser/security integration. Existing M1-02 admission checks alone are not a full XLSX security verdict.

## Reproduction and targeted validation

Install the project's normal runtime/dev dependencies. Run `python scripts/generate_xlsx_fixtures.py` from the repository, or pass a temporary output directory to compare a regeneration. The script uses openpyxl for workbook writing and normalizes core/ZIP timestamps. Output is byte-stable with the same toolchain (created using openpyxl 3.1.5); serialization may change across supported dependency versions, so tests primarily pin exact sheet order, types, values and missingness.

Run `PYTHONPATH=src python -m pytest -q tests/unit/test_xlsx_fixtures.py`. Tests reopen both files with openpyxl, check their package/content and existing admission compatibility, exercise selection and invalid-name behavior, and verify generator repeatability. Fixture rendering is a development check, not a runtime dependency or additional worksheet.
