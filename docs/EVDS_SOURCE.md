# M3-03 — TCMB EVDS source inventory

How EVDS is accessed and what it publishes, established by reading the live service on 2026-09-09. Companion to the [BDDK inventory](BDDK_SOURCE.md); together they cover the sources the reference scenario needs.

Retrieved payloads are **not** committed. The catalog and two series lists were written to the ignored `data/raw/evds/` path for inspection. No adapter is implemented — [M3-07 and M3-08](ROADMAP.md#m3) still own retrieval, behind safe fetch.

## The documented API no longer exists

Every tutorial, the `evds` PyPI package and the organizer-era references point at `https://evds2.tcmb.gov.tr/service/evds/...` with an `key=` API key. That service now answers **302 to `https://evds3.tcmb.gov.tr`** for every path tried, including `series=`, `categories` and `serieList`. Treat published EVDS API documentation and any API-key instructions as stale until confirmed otherwise.

This matters for planning: the open question "has the EVDS API key been obtained?" may have no answer to obtain. Confirm the intended access route with the organizers rather than budgeting time to register for a key that may no longer gate anything.

## EVDS3 serves a keyless internal API

The EVDS3 web application talks to `https://evds3.tcmb.gov.tr/igmevdsms-dis/`. Every endpoint below answered **without credentials, cookies or a key**, from Python as well as the browser.

| Endpoint | Method | Returns |
| --- | --- | --- |
| `categories/withDatagroups/type=json` | GET | The whole catalog: 154 categories, 678 datagroups, 727 KB |
| `serieList/fe/type=json&code=<datagroup>` | GET | Series within a datagroup, with aggregation metadata |
| `searchResults?searchVal=<query>` | GET | Full-text search, split into `veriGruplari`, `seriler`, `raporlar` |
| `serieList/baslangicBitis` | POST | Series coverage start/end |
| `fe` | POST | Observations |
| `calendar/aylikYayinlar?yil=&ay=` | GET | Publication calendar |
| `genel-ayarlar?key=MAX_SERIE_COUNT` etc. | GET | Server-side request limits |

The request payloads for the two POST endpoints were not captured; they are formed by the application's own client and did not respond to the shapes tried. Capture them from the browser's network panel when implementing M3-08 rather than guessing. Unlike BDDK, `evds3.tcmb.gov.tr` presents a complete certificate chain and verifies cleanly against certifi.

`MAX_SERIE_COUNT`, `MAX_GRID_COUNT` and `MAX_CHART_COUNT` are published as settings. Read them rather than assuming a request size.

## The catalog is the semantic layer, already built

Do not hard-code series codes. Each datagroup carries:

```json
{"DATAGROUP_CODE": "bie_kfe", "DATAGROUP_TYPE": "Konut Fiyat Endeksi",
 "FREQUENCY_STR": "AYLIK", "DATASOURCE": "TÜİK",
 "METADATA_LINK": "...", "REV_POL_LINK": "...", "APP_CHA_LINK": "..."}
```

and each series carries something better:

```json
{"SERIE_CODE": "TP.KTF12", "SERIE_NAME": "Konut Kredisi (TL, Akım, %)",
 "FREQUENCY_STR": "HAFTALIK(CUMA)", "DEFAULT_AGG_METHOD": "avg",
 "AVGABLE": 1, "SUMABLE": 0, "FIRSTABLE": 1, "LASTABLE": 1, "MAXABLE": 1, "MINABLE": 1}
```

**EVDS publishes the aggregation policy per series.** [M12-09](ROADMAP.md#m12) requires that policy to live in metadata rather than in code; for EVDS series it already does, and we read it instead of authoring it. Every rate series inspected carries `SUMABLE: 0` — the source itself forbids summing a rate. Honour these flags; do not compute an aggregation a series is not flagged for.

Coverage of the useful fields is partial: `METADATA_LINK` is present on 456 of 678 datagroups and `REV_POL_LINK` on only 180. A missing revision-policy link is not evidence that a series is never revised, so [M12-12](ROADMAP.md#m12) cannot rely on this field alone.

`DATASOURCE` needs normalizing before it is grouped or displayed: the catalog contains both `BANKALAR` (63) and `Bankalar` (11) as separate values for the same source. This is a small thing that becomes a wrong denominator in a chart.

## Nine frequencies, not three

| Frequency | Datagroups |
| --- | --- |
| AYLIK | 286 |
| ÜÇ AYLIK | 163 |
| YILLIK | 102 |
| HAFTALIK(CUMA) | 87 |
| İŞ GÜNÜ | 26 |
| GÜNLÜK | 10 |
| ALTI AYLIK | 2 |
| HAFTALIK(ÇARŞAMBA) | 1 |
| AYDA İKİ KEZ | 1 |

The brief describes EVDS as "günlük – haftalık – aylık". The catalog has nine conventions, and the distinctions matter: weekly data is anchored to **Friday for 87 datagroups and Wednesday for one**, so a single "weekly" bucket silently misaligns them. `İŞ GÜNÜ` (business day) and `GÜNLÜK` (calendar day) differ on weekends and holidays, which changes both the observation count and any average computed over a month. [M12-08](ROADMAP.md#m12) must key alignment on `FREQUENCY_STR`, not on observed row spacing.

## A third of the catalog is archived

228 of 678 datagroups have `Arşiv` in their title, and archived series appear under plain names — `TP.VK02` is `A) KONUT (Arşiv)`, `TP.TK02` is `IA- KONUT (Arşiv)`. A search for `Konut` returns 82 series and several archived ones rank near the top.

An archived series still returns data; it just stopped being updated. A retrieval that silently picks one produces a chart that ends years early and looks like a real finding. Archived status must be a retrieval filter and must be surfaced when a match is archived.

## Base-year variants make deflation a trap

The consumer price index exists as `bie_tukfiy2025` (2025=100), `bie_tukfiy2003` (2003=100) and archived variants including `bie_tukfiy4` (2003=100). The housing price index exists as `bie_kfe` plus archived `bie_tkfe` (2010=100) and `bie_hkfe` (2017=100).

The organizer's second question — inflation-adjust the housing credit column — requires choosing one of these and a reference period. Different base years give different real values, and both look plausible. [M12](ROADMAP.md#m12) rebasing must therefore require an explicit reference period, verify overlap before rebasing, and state which index and base it used. The base year is in the title text, so it has to be parsed rather than assumed.

`bie_kfe` also contains 20 series: the national index `TP.KFE.TR` plus regional breakdowns such as `TP.KFE.TR10` (İstanbul), `TP.KFE.TR51` (Ankara), `TP.KFE.TR31` (İzmir). "Konut fiyat endeksi" alone does not identify one of them.

## The demo's own series are genuinely ambiguous

Searching `konut kredisi` returns exactly four series:

| Code | Frequency | Name |
| --- | --- | --- |
| `TP.KBK.TRY.18` | HAFTALIK(CUMA) | Konut Kredisi**,** (TL, Akım, %) |
| `TP.KTF12` | HAFTALIK(CUMA) | Konut Kredisi (TL, Akım, %) |
| `TP.BKR.TRY.18` | AYLIK | Konut Kredisi (TL, Stok, %) |
| `TP.KKP.TRY.18` | AYLIK | Konut Kredisi (TL, Stok, %) |

Two weekly flow rates and two monthly stock rates. `TP.KBK.TRY.18` and `TP.KTF12` differ **only by a comma** in their display names, and the two monthly names are identical. No embedding, no BM25 score and no reranker can choose correctly between them from the name, because the name does not contain the distinction.

This is the wrong-near-match case [M3-10](ROADMAP.md#m3) requires, and it is not a contrived edge case — it is the first series the demo needs. The resolution is the one [DEC-116](DECISIONS.md#dec-116--alias-dictionary-single-turkish-normalizer-and-a-measured-recall-floor) and [DEC-119](DECISIONS.md#dec-119--verifier-gates-the-answer) already require: the alias dictionary pins a specific code for a concept, and where several candidates remain the system asks rather than ranking. Recall@10 is the right metric precisely because top-1 is not achievable here.

Akım and Stok are also different economic quantities, not a formatting choice. The flow rate is the rate on newly extended loans; the stock rate is the average rate on the outstanding book. "Faiz oranlarının düştüğü dönemler" is a question about the flow rate.

## The reference scenario requires frequency alignment

Putting the two inventories together, the organizer's first question needs:

| Quantity | Source | Frequency |
| --- | --- | --- |
| Housing credit volume | BDDK monthly bulletin, table 4 | monthly, stock, Milyon TL |
| Housing loan rate | EVDS `TP.KTF12` | **weekly, Friday**, flow, % |
| Consumer price index | EVDS `bie_tukfiy*` | monthly, index, base-year variants |
| Housing price index | EVDS `bie_kfe` | monthly, index |

The credit series is monthly and the rate series is weekly. There is no monthly variant of the flow rate, so alignment is not an optimization — the demo cannot be answered without it. The rate is flagged `SUMABLE: 0, AVGABLE: 1`, so weekly-to-monthly reduction is an average, and that choice must be recorded as a transformation rather than performed silently.

## Read observations in their original form

The `fe` response looks like this:

```json
{"totalCount": 191,
 "items": [{"Tarih": "06-01-2023", "YEARWEEK": "2023-1",
            "TP_AB_C1": "46,750", "TP_AB_C2": "79,659", "F-1": "126,409",
            "UNIXTIME": {"$numberLong": "1672952400"}}]}
```

Three things to handle. Values are **strings with a comma decimal separator** — `"46,750"` is 46.75, and reading that comma as a thousands separator yields 46,750, a 1000x error that produces a plausible-looking chart. Dates are `DD-MM-YYYY`, which is ambiguous with `MM-DD-YYYY` for the first twelve days of a month; `UNIXTIME` is present and unambiguous, so use it and treat `Tarih` as a label. Column keys are series codes with dots replaced by underscores, so `TP.AB.C1` arrives as `TP_AB_C1`, and a `F-1`-style key is a **server-computed formula column**, not a published series.

EVDS offers server-side frequency conversion and formula transforms — the report screen exposes `Frekans Dönüşüm Yöntemi` and a `Formül` selector with `Düzey` as one option. Always request the original observation at its native frequency in level form, and perform conversions ourselves. A server-side transform produces a number whose derivation is not in our lineage graph, which [DEC-118](DECISIONS.md#dec-118--lineage-graph-as-the-provenance-substrate) does not allow.

## What this does not establish

No adapter, no schedule, no retention decision. The two POST payloads are uncaptured. Revision behaviour is untested: `REV_POL_LINK` exists for 180 datagroups but no restatement was observed, so whether EVDS revises a published value remains open for [M12-12](ROADMAP.md#m12) and Q-DATA-04. Terms of use were not reviewed; the site publishes `KULLANIM ŞARTLARI` and `GİZLİLİK POLİTİKASI` links that [M3-01](ROADMAP.md#m3) should read before any scheduled retrieval. Request-rate limits are unknown beyond the published `MAX_SERIE_COUNT` family. This inspection issued roughly a dozen requests.
