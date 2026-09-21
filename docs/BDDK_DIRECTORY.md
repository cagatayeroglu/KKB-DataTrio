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

## Every layout, and rows by label (DEC-185)

The 2026-09-21 harvest measures year-boundary behaviour for every table that has a total the
adapter reads, comparing rows by their label rather than their number:

| Table | Layout read | Supported rows |
| --- | --- | --- |
| 1 Bilanço, 2 Kar Zarar, 4 Tüketici Kredileri, 7, 8 Menkul Kıymetler, 14 Bilanço Dışı | TP, YP, Toplam | 60, 45, 37, 3, 22, 47 |
| 3 Krediler | Toplam TP, Toplam YP, Toplam (after maturity bands) | 20 |
| 5 Sektörel Kredi Dağılımı (bin TL) | Toplam Nakdi Krediler | 70 |
| 6 KOBİ Kredileri | Nakdi Kredi TP, Nakdi Kredi YP, Toplam Nakdi Krediler | 4 |
| 9 Mevduat Türler, 10 Mevduat Vade, 11 Likidite | the closing Toplam | 26, 24, 43 |
| 12 Sermaye Yeterliliği, 13 Yabancı Para Pozisyonu | Toplam (two capital ratios are percent) | 28, 9 |
| 15 Rasyolar | Rasyo, rows labelled "(%)" that do not reset in January | 16 |
| 16 Diğer Bilgiler | Adet (counts) | 7 |
| 17 Yurt Dışı Şube Rasyoları | none: no unit anywhere | 0 |

461 rows, 937 identities. A row is found in each month by its label without arithmetic or
footnote marks, because the bulletin renumbers rows when it inserts one; a month that does
not have the row yet is a missing value.

## Refreshing

Run the harvest again (58 public requests, one a second) and review the diff of
`src/kkb_agent/ingest/bddk_monthly_directory.py` in a PR. A new row becomes a new entry; a
renamed or renumbered row fails closed at fetch time until the listing is refreshed.

# BDDK weekly bulletin — the pinned listing (DEC-182)

`tests/manual/harvest_bddk_weekly_directory.py` walks the bulletin's nine tables through the
page's own table switch (ten public requests, one a second) and keeps what a person reads
there: table titles, rows in page order with their numbers and labels, the row a sub-item
sits under, the item id each value cell charts (`<table>.0.<row>`) and which of TP / YP /
TOPLAM the row has. No observation value is kept. 2026-09-20: 9 tables, 179 rows, 515
identities; one caption for all of them, "Birim: Milyon TL".

| Table | Rows | Columns |
| --- | --- | --- |
| 1 Krediler | 22 | TP, YP, Toplam |
| 2 Takipteki Alacaklar | 12 | TP, YP, Toplam |
| 3 Menkul Değerler | 13 | TP, YP, Toplam |
| 4 Mevduat | 12 | TP, YP, Toplam; two memo rows have no YP |
| 5 Diğer Bilanço Kalemleri | 16 | TP, YP, Toplam |
| 6 Bilanço Dışı İşlemler | 4 | TP, YP, Toplam |
| 7 Bankalarda Saklanan Menkul Değerler - 1 (nominal) | 45 | TP, YP, Toplam |
| 8 Bankalarda Saklanan Menkul Değerler - 2 (market value) | 45 | TP, YP, Toplam |
| 9 Yabancı Para Pozisyonu | 10 | Toplam only |

Item ids are not row numbers: the page shows "KOBİ Kredileri (Bilgi)" as row 19 of Krediler
and charts it as `1.0.11`, and the ids of tables 3 and 9 start at 11 and 14. The listing keeps
both, and the adapter asks by id and describes by the number a person sees.

Every item is declared the same way, because every table is a position table: weekly with a
Friday anchor, TRY million, STOCK, not cumulative, reduced over time by its last value and
never summed. What the series endpoint was measured to do (the ninety-day answer, holiday
weeks, the empty chart for an unknown id) is recorded in [DEC-182](DECISIONS.md).

Refreshing is the same: run the harvest, review the diff of
`src/kkb_agent/ingest/bddk_weekly_directory.py` in a PR. A renamed or renumbered row fails
closed at fetch time, because the answer's title no longer equals the listed label.

# BDDK FinTürk — the pinned listing (DEC-184)

`tests/manual/harvest_bddk_finturk_directory.py` reads the page's own option lists (tables,
quarters, provinces) and asks each table once, for the latest quarter and every province
(eight public requests, one a second). It keeps what a person reads there: table labels with
their unit, column names in page order, and the provinces each table has. No observation
value is kept. 2026-09-21: 7 tables, 76 columns, 81 provinces plus "YURT DIŞI", quarters from
2007-12, latest 2026-6.

| Table | Columns | Unit | Provinces |
| --- | --- | --- | --- |
| 1 Krediler | 4 | Bin TL | 82 |
| 2 Mevduat | 7 | Bin TL | 82 |
| 3 Bireysel Bankacılık | 8 | Bin TL | 82 |
| 4 Seçilmiş Sektörel Krediler | 31 | Bin TL | 82 |
| 5 Oranlar | 16 | % | 81 |
| 6 Şubeler ve Nüfusa Göre Dağılım | 6 | adet; kişi/şube; TL per head | 81 |
| 7 Altın Kredileri ve Altın Mevduatı | 4 | Bin TL | 82 |

A series is one cell: a column of a table for a province, quarterly, a quarter-end position
(not cumulative), reduced over time by its last value and never summed. **The money tables
are TRY thousand; the bulletins are TRY million.** The entry's note says so, and the
declared scale makes a comparison convert rather than mislead.

Refreshing is the same: run the harvest, review the diff of
`src/kkb_agent/ingest/bddk_finturk_directory.py` in a PR. A renamed, added or reordered
column fails closed at fetch time, because the answer's column names no longer equal the
listed ones.
