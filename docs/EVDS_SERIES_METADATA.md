# M3-07/M3-08 — Reviewed EVDS series and bounded ingestion

This bounded slice resolves the first-slice EVDS identities from live catalog
metadata and prepares them through a reusable `fe` ingestion path under
[DEC-137](DECISIONS.md#dec-137-prepared-pool-refinement) and
[DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git).
The [source inventory](EVDS_SOURCE.md) remains unchanged historical evidence
(its content hash is pinned by M13-08); where this document disagrees with it,
this document records the newer measurement. Retrieval was authorized by Eray
on 2026-09-14. Retrieved data stays in an ignored operator-local root.

## Reviewed identities

Resolved on 2026-09-14 from `serieList/fe` per datagroup, `searchResults` and
`categories/withDatagroups`. [evds_series](../src/kkb_agent/ingest/evds_series.py)
pins each datagroup series list by SHA-256; only these four codes reach transport.

| Code | Meaning (source fields) | Declared semantics |
| --- | --- | --- |
| `TP.KTF12` | Konut Kredisi (TL, Akım, %), datagroup `bie_kt100h` Kredi Faiz Oranları (Akım), source *Mevduat, Kalkınma ve Yatırım Bankaları*, HAFTALIK(CUMA), unit "Ağırlıklı ortalama" | percent, one, weekly Friday, RATE, not cumulative, average (sum forbidden) |
| `TP.TUKFIY2025.GENEL` | Genel Endeks, `bie_tukfiy2025` Tüketici Fiyat Endeksi (2025=100), TÜİK, AYLIK | index 2025=100, monthly, INDEX, average |
| `TP.GENENDEKS.T1` | Genel Endeks (2003=100), `bie_tukfiy2003`, TÜİK, AYLIK | index 2003=100, monthly, INDEX, average |
| `TP.KFE.TR` | Konut Fiyat Endeksi (KFE), `bie_kfe`, TCMB, AYLIK | index 2023=100, monthly, INDEX, average |

**Housing-rate ambiguity resolved by source fields, not names.** Of the four
`konut kredisi` rate series, `TP.KTF12` is the deposit/development/investment
banks' new-loan interest rate. `TP.KBK.TRY.18` (name differs by one comma) is the
participation banks' profit share (`bie_kt200h`), `TP.BKR.TRY.18` the deposit
banks' outstanding-portfolio rate and `TP.KKP.TRY.18` the participation banks'
portfolio profit share. "Faiz oranlarının düştüğü dönemler" concerns new loans,
so `TP.KTF12` is the reviewed rate; the others are refused.

**CPI base.** Both CPI series cover 2021-01–2026-06. Over 2021-01→2025-12 their
cumulative ratios are identical (6.845646) and monthly changes differ by at most
0.0042 percentage points, so the 2025=100 series is the 2003=100 index re-based
and linked. `TP.TUKFIY2025.GENEL` is the reviewed deflator (current TÜİK base,
eight-decimal precision); `TP.GENENDEKS.T1` stays as an independent cross-check.
Any deflation must still name the index and an explicit reference period (M2-15).

**KFE base.** EVDS titles carry no base label. The 2023 annual mean of the
published index is 99.999 (2022: 49.42, 2024: 141.54), so 2023=100 is recorded
from observations; the TCMB metadata page is script-rendered and was not read.

EVDS `STATUS: 1` is present on all four but its meaning is undocumented, so
catalog status stays UNKNOWN. Aggregation flags are read from the source:
`DEFAULT_AGG_METHOD avg`, `SUMABLE 0`, the others 1.

## Request contract

`POST https://evds3.tcmb.gov.tr/igmevdsms-dis/fe`, captured from the EVDS3
client. [evds_request](../src/kkb_agent/ingest/evds_request.py) fixes every field:

```json
{"type":"json","series":"<code>","aggregationTypes":"avg","formulas":"0",
 "startDate":"DD-MM-YYYY","endDate":"DD-MM-YYYY","frequency":"<native>",
 "decimalSeperator":".","decimal":"8","dateFormat":"0","lang":"tr","yon":"0",
 "sira":"0","ozelFormuller":[],"groupSeperator":false,"isRaporSayfasi":false}
```

- `frequency` is the client's code (1 daily, 2 business day, 3 weekly, 4 twice
  monthly, 5 monthly, 6 quarterly, 7 semiannual, 8 annual) and is always the
  series' native cadence, so no server-side conversion occurs. The catalog's
  own `FREQUENCY` field uses a different numbering and is not used.
- `formulas "0"` is the level; `decimal "8"` is the client maximum, avoiding the
  default two-decimal server rounding; `groupSeperator false` avoids thousands
  separators. **The comma decimal the inventory saw is a request option, not a
  source property.**
- The server returns an HTML error page unless the client's `Origin` and
  `Referer` are sent. They are fixed constants in code, never credentials; no
  cookie, key or session is used. `serieList/baslangicBitis` takes
  `{"frequency": n, "series": [...], "datagroups": [...]}` but answered
  inconsistently outside the browser and is not used: coverage is established
  from the observations.
- Transport reuses the supervised worker: descriptor/endpoint/limit
  revalidation before DNS, DNS/peer binding, system-verified TLS (EVDS serves a
  complete chain; no reviewed issuer is added), no redirects or retries, 1 MiB
  encoded / 2 MiB decoded body, 5/5/30-second deadlines, one request per series
  window (at most twelve years).

## Response parsing

[evds_load](../src/kkb_agent/ingest/evds_load.py) validates before use:

- Envelope keys are `totalCount`, `items` and the inert presentation copies
  `transposedItems`, `transposedColumns`, `seriesNames`, `frequencyConversion`
  (the last is `true` even at native frequency; its meaning is undocumented).
  `totalCount` equals the row count; duplicate JSON keys fail.
- Every row has exactly `Tarih`, `UNIXTIME`, the series column (dots → underscores)
  and, for weekly series, `YEARWEEK` (format-checked only; it is not ISO week).
  A server formula column (`F-1`) or another series fails.
- Values are dot-decimal strings or null. Commas, group separators, exponents,
  JSON numbers, empty strings and `NaN` fail; null stays missing.
- **Dates:** `Tarih` is `YYYY-MM` (monthly) or `DD-MM-YYYY` (weekly). `UNIXTIME`
  is local midnight at a varying offset — UTC+1 for 2021-01..03 and UTC+3 later
  in every measured series — so the inventory's "take UNIXTIME" rule is unsafe
  alone. The label date must equal the UNIXTIME date at UTC+3; rows must strictly
  increase.
- Monthly rows become calendar months; weekly rows become Saturday..Friday
  periods. A weekly request also returns the week whose Friday falls after the
  window end: periods ending outside the window are excluded and counted in the
  manifest. The kept period ends must equal a calendar generated independently
  of the response, so a gap or extra period fails instead of being filled.

## Storage and verification

The raw response is immutable content-addressed bronze. The internal
`evds-fe-batch-v1` manifest binds series, window, request fingerprint, raw hash,
excluded count, parser/semantic versions, transformation policy and the
normalized-observation hash; its SHA-256 is the series' silver `artifact_id`.
Series, observations and SOURCE_FILE → TRANSFORM → SERIES lineage commit in one
transaction. Identical inputs are an idempotent no-op; a changed window, bytes
or contract returns `VERSION_CONFLICT` and preserves prior values.
`materialized_series` reparses the raw artifact, recomputes the manifest and
compares semantics, observations and lineage offline.

The [operator command](../src/kkb_agent/ingest/evds_operator.py) mirrors BDDK's:
`smoke` (temporary lakehouse, in-run repeat) and `prepare` (explicit root,
silver Parquet export), with calendar read-back and `SERIES:YYYY-MM-DD=VALUE`
oracles keyed by period end.

## Live acceptance (2026-09-14)

**Smoke** 2026-01-01..2026-06-30, all four series, 8 requests: every check
passed, including the idempotent repeat (EVDS returned identical bytes);
oracles `TP.KTF12` 2026-06-26 = 41.56, CPI 2025=100 2026-06 = 129.99, CPI
2003=100 = 4137.93, KFE = 231.34 matched values captured separately during
discovery.

**Preparation** `prepare --root data/processed/lakehouse --start 2021-01-01
--end 2026-06-30` for the four series, 4 requests in 2.5 s: `TP.KTF12` 287
Fridays (2021-01-01..2026-06-26; one trailing week excluded), each monthly
series 66 months; 0 missing values; every check and oracle passed (first and
last period of each series). The local pool now holds the first four-series
vertical slice: BDDK housing balance TP/YP/TOTAL, the housing new-loan rate,
CPI (two bases) and national KFE, 2021-01–2026-06.

Not established: revision behaviour and restatement policy (M3-09/M12-12), a
prepare rerun against live bytes, other EVDS series or catalog-wide discovery
(rest of M3-07), catalog_search registration, deployment egress, and any
alignment, deflation or answer over these series (Turn 1 onward).
