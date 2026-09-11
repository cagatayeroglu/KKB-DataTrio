# M3-04 synthetic source-shaped fixtures

All files here are **authored synthetic fixtures, not real captured responses**.
No network request, raw data directory, credential or preserved stash was used.
Observation values, dates, row IDs and `TP.SYNTH.M304.*` / `synthetic_m304_*`
identifiers are test inputs, never production series selections. Public field
names, labels and conventions come only from the merged inventories:
[BDDK_SOURCE](../../../docs/BDDK_SOURCE.md) and
[EVDS_SOURCE](../../../docs/EVDS_SOURCE.md). Links use `example.invalid` and must
not be fetched. JSON is UTF-8 without BOM, with LF endings and a final newline.

## Fidelity and intended use

| Files | Documented behavior represented | Deliberate boundary |
| --- | --- | --- |
| `bddk/monthly_stock_2026_01.json`, `monthly_stock_2026_02.json` | Aylık Bülten `success`/`Json`/`data.rows[].cell` layout; seven ordered cells; numeric TP/YP/Toplam; unit and period in caption. Synthetic stock values decrease within a year. | Projections of the documented response: `colModels` is omitted because only `[...]` was documented. Row IDs are arbitrary synthetic IDs. No complete jqGrid schema or additional source fields are asserted. |
| `bddk/monthly_ytd_2025_12.json`, `monthly_ytd_2026_01.json` | Same documented monthly layout with the Kar Zarar label, a December/January boundary and a smaller January value. | Synthetic boundary example for later tests, not evidence that two observations prove a reset rule. No differencing or classification is implemented. |
| `bddk/display_cases.json` | Weekly HTML transport, opaque `donemId`/option labels and Friday captions carrying Milyon TL; FinTürk quarter-end selectors and Bin TL, %, and mixed Adet/TL display metadata. | **Project-owned case container, not a BDDK JSON response.** Its keys organize documented display facts. No weekly DOM/table columns, FinTürk response schema, option-list wire structure or per-column unit assignment was captured; none is fabricated. `column_units: unknown` is a test annotation, not a provider field. |
| `evds/datagroup_records.json` | Documented datagroup fields; source case variants, Friday/Wednesday/monthly cadence, missing metadata links, base-year labels and an Arşiv title. | **Array of synthetic record projections**, not the uncaptured category/catalog envelope. No category keys, archived/active boolean or group-to-series foreign key is invented. An unmarked title does not prove that a series is active or never revised. |
| `evds/series_records.json` | Documented series fields and aggregation flags (`avg`, AVGABLE=1, SUMABLE=0); names differing only by a comma or identical names at different IDs. | Project collection spanning example cases, not a full response from one real datagroup. There is no preferred candidate or adapter/alias mapping. |
| `evds/observations.json` | Documented `totalCount`/`items` envelope, comma-decimal strings, dot-to-underscore series keys, `Tarih`, `YEARWEEK`, nested UNIXTIME, and `F-1` formula-shaped column. | Both dates are ambiguous without a declaration. UNIXTIME represents synthetic midnight at UTC+03:00 (fixture convention, not a newly inferred provider timezone guarantee). `F-1` is an opaque server-formula example, never a native series or a formula to execute. |

## Oracles and unknowns

- Monthly numeric cells are already JSON numbers; EVDS observation numbers stay
  strings. In the documented EVDS convention `46,750` means 46.75, not 46750.
  Tests preserve these strings; this task adds no conversion or financial inference.
- Weekly option IDs are deliberately unrelated to their dates. Read the declared
  option/caption pair; do not derive a date from the number. FinTürk periods remain
  quarterly, and the mixed-unit display case deliberately lacks a column mapping.
- Keep missing revision-policy links missing. Keep duplicate/near-identical series
  labels, archive markers, source casing and frequency anchors visible. Do not choose
  a source series, fill a unit or declare revision behavior from these examples.
- The tests pin syntax, exact values/field sets, small byte budgets and a SHA-256
  inventory for deliberate fixture changes. They are fixture oracles, **not adapter,
  discovery, unit-normalization, archive-filter or retrieval implementations**.

Uncaptured details remain work for authorized adapter development: weekly HTML DOM
and table schema, FinTürk response fields, BDDK `colModels`, EVDS catalog/category
envelopes, and EVDS `fe` / `serieList/baslangicBitis` POST request bodies. These fixtures
cannot establish live permissions, retries, limits, TLS behavior, retention or
redistribution policy. JSON/HTML must not be routed through the CSV/XLSX admission
path merely to make an offline test pass.

Targeted check: `pytest -q tests/unit/test_source_fixtures.py`. `make pr` also runs
the repository secret scan. Tests need neither credentials nor internet access.
