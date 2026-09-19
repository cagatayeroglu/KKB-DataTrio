# BDDK monthly bulletin — the pinned listing (DEC-176)

[BDDK_SOURCE.md](BDDK_SOURCE.md) is the M3-02 inventory and is pinned by its content hash; this
document records what the 2026-09-19 harvest added and is free to change with the next one.

`tests/manual/harvest_bddk_directory.py` harvested all 17 tables for 2026/5 (sector aggregate,
TL): 516 rows. It stores table titles, caption units, column headers, row numbers and labels,
and one measured word per row. No observation value is kept.

## Units come only from captions

Fourteen tables say "milyon TL", Sektörel Kredi Dağılımı says "bin TL", and Rasyolar, Diğer
Bilgiler and Yurt Dışı Şube Rasyoları carry no caption unit (their units sit in row labels or
headers). The adapter declares a unit only for the caption texts it knows ("milyon TL",
"bin TL"); any other caption leaves the table unsupported.

## Layouts

Six tables are laid out as TP / YP / Toplam (1 Bilanço, 2 Kar Zarar, 4 Tüketici Kredileri,
7 Sendikasyon Seküritizasyon, 8 Menkul Kıymetler, 14 Bilanço Dışı İşlemler). The others have
maturity, size, sector or single-value columns and are listed but not yet supported.

## Year-boundary evidence

For each row of those six tables: is the January total under a quarter of December, at both
2024→25 and 2025→26?

| Table | always | never | mixed | unmeasured |
| --- | --- | --- | --- | --- |
| 1 Bilanço | 1 (the period's profit) | 60 | 0 | 1 |
| 2 Kar Zarar | 45 | 1 | 5 | 2 |
| 4 Tüketici Kredileri | 0 | 37 | 0 | 4 (rows of zeros) |
| 7 Sendikasyon Seküritizasyon | 0 | 3 | 0 | 0 |
| 8 Menkul Kıymetler | 0 | 22 | 1 | 6 |
| 14 Bilanço Dışı İşlemler | 0 | 47 | 1 | 4 |

A table's family is the behaviour two thirds of its measured rows share; a row is supported
only when its own word is that behaviour: `never` → month-end position (STOCK, not
cumulative), `always` → year-to-date total that resets every January (FLOW, YEARLY_RESET).
214 rows are supported, 642 identities with their TP / YP / Toplam components.

## Refreshing

Run the harvest again (58 public requests, one a second) and review the diff of
`src/kkb_agent/ingest/bddk_monthly_directory.py` in a PR. A new row becomes a new entry; a
renamed or renumbered row fails closed at fetch time until the listing is refreshed.
