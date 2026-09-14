# M13-08 — Reviewed offline demo catalog mapping

## Current prepared-scope revision (2026-09-14)

[prepared_v2.json](catalog/prepared_v2.json), `m13-08-prepared-v2` / `r2`, is
the current reviewed discovery input. Arda's [PR #152](https://github.com/cagatayeroglu/KKB-DataTrio/pull/152)
reviews merged M3-05/06 and M3-07/08 metadata; it makes no new live-source claim.
Its canonical digest is `723567b3f25c0703ddd2fa9001c67c41fd4f83a6c46ef82f0d40e556e0104e31`.
The historical v1 artifact, source inventories and tests remain unchanged below.
The two newly pinned review documents use LF checkout bytes through
`.gitattributes`, so their Git-revision hashes also match on Windows.

The 15 identities include all seven supported prepared series and the earlier
eight discovery-only candidates. Five identities are added: the three reviewed
BDDK Monthly housing balance selectors (TP/YP/TOTAL, sector, million TRY), and
CPI `TP.TUKFIY2025.GENEL` / `TP.GENENDEKS.T1`. Records for the four reviewed EVDS
series match the adapter's CatalogRecord declarations; BDDK records match its
existing composite-selector builder. Internal BDDK hashes are labelled as such,
never presented as source-native codes. There are 21 reviewed concepts.

The newer [EVDS review](EVDS_SERIES_METADATA.md) distinguishes deposit-bank
interest from participation-bank profit share. Interest aliases now yield
`TP.KTF12` (new loans) or `TP.BKR.TRY.18` (portfolio); explicit profit-share
aliases yield `TP.KBK.TRY.18` or `TP.KKP.TRY.18`. General housing-finance
ambiguity remains. CPI level queries preserve the two bases; precise base-year
aliases narrow them. Native inflation rate and new disbursement stay unresolved.
The national KFE base is explicitly **observation-derived review**, not an EVDS
title declaration; regional bases remain unknown. General balance queries keep
the three components; explicit total wording follows DEC-139.

Select the reviewed artifact in operator configuration:

```python
from pathlib import Path
from kkb_agent.tools import make_catalog_search_tool

tool = make_catalog_search_tool(
    snapshot_bytes=Path("docs/catalog/prepared_v2.json").read_bytes()
)
```

The factory consumes validated bytes; the model cannot select an arbitrary
catalog path or modify it. This revision does **not** register the factory into
every runtime, add a planner discovery/replan round, or claim LanceDB/hybrid
retrieval. A catalog hit does not establish local availability, period coverage
or permission to calculate/fetch. No sample observations are stored here.
Wider source coverage and automatic availability inspection remain separate work.

## Historical v1 review

Owner: Çağatay. Team/owner review artifact: [PR #117](https://github.com/cagatayeroglu/KKB-DataTrio/pull/117). Scope was explicitly approved on 2026-09-12; merge/completion evidence is maintained in [ROADMAP](ROADMAP.md#m13). No separate external reviewer or live approval is claimed.

## Version and trust boundary

- Snapshot: [demo_v1.json](catalog/demo_v1.json), version `m13-08-demo-v1`, review revision `r1`, date `2026-09-12`.
- Canonical content SHA-256: `230807e195663a59978c69448c8cb63acbd10130080b09a5f3d474a6b58da5f6`. Hash sorted-key compact UTF-8 JSON of the validated payload excluding only `content_sha256`; array order is retained. This is integrity/version identity, not proof of source truth.
- Evidence revision: `904e22dd9e70100e0a7b69b02aa08dffb5daa905`. Evidence entries pin the path, section and SHA-256 of the already-merged [BDDK](BDDK_SOURCE.md) and [EVDS](EVDS_SOURCE.md) inventories. No ignored raw files, stash, source fetch or model output was used.
- 10 real source identities; 50 distinct original alias strings / 51 concept-alias entries, 14 concepts, 4 families. Original aliases are reviewed authored vocabulary, not claimed provider titles.
- This is a small repository-backed **demo/development** snapshot, not the full EVDS catalog, M13-09 holdout, independently validated live metadata or permission to calculate/fetch. Labels and source fragments remain untrusted data.
- `CatalogRecord` semantics are referenced rather than copied into aliases. ReviewedSeries adds only documented geography and rate basis (new credit versus outstanding portfolio); both interest-rate types remain `StockFlow.RATE`.
- KFE titles are clearly labelled inventory descriptions, not verbatim provider series titles. Their base year, coverage, unit/scale and active status are not inferred. All eight non-archived records have status UNKNOWN. No samples are fabricated. Only TP.KTF12 has the explicit complete aggregation flags demonstrated in the inventory.

## Real identity inventory

| Source ID | Meaning / evidence | Status |
| --- | --- | --- |
| `TP.KBK.TRY.18` | Konut Kredisi, (TL, Akım, %); weekly; new_credit | unknown |
| `TP.KTF12` | Konut Kredisi (TL, Akım, %); weekly; new_credit | unknown |
| `TP.BKR.TRY.18` | Konut Kredisi (TL, Stok, %); monthly; outstanding_portfolio | unknown |
| `TP.KKP.TRY.18` | Konut Kredisi (TL, Stok, %); monthly; outstanding_portfolio | unknown |
| `TP.KFE.TR` | Konut Fiyat Endeksi — Türkiye; monthly | unknown |
| `TP.KFE.TR10` | Konut Fiyat Endeksi — İstanbul; monthly | unknown |
| `TP.KFE.TR51` | Konut Fiyat Endeksi — Ankara; monthly | unknown |
| `TP.KFE.TR31` | Konut Fiyat Endeksi — İzmir; monthly | unknown |
| `TP.VK02` | A) KONUT (Arşiv); unknown | archived |
| `TP.TK02` | IA- KONUT (Arşiv); unknown | archived |

## Complete concept mapping

Candidate IDs below omit the stable internal `EVDS:` prefix for readability. A MAPPED concept is not permission for automatic selection: conditions, unknown semantics and ambiguity still apply. All v1 concepts explicitly retain clarification requirements.

| Concept | Original aliases | Candidate source IDs | Resolution |
| --- | --- | --- | --- |
| `housing_credit` | konut kredisi; konut kredileri; konut finansmanı; mortgage kredisi; mortgage | TP.KBK.TRY.18, TP.KTF12, TP.BKR.TRY.18, TP.KKP.TRY.18 | PARTIAL |
| `housing_balance` | konut kredisi; konut kredisi bakiyesi; konut kredisi stoku; toplam konut kredisi bakiyesi; konut kredisi hacmi | none | UNRESOLVED |
| `housing_disbursement` | yeni konut kredisi kullandırımı; kullandırılan konut kredileri; konut kredisi akımı; yeni kullandırılan konut kredisi | none | UNRESOLVED |
| `housing_rate` | konut kredisi faiz oranı; konut kredi faizi; konut kredisi faizleri; mortgage faiz oranı; konut finansmanı faiz oranı | TP.KBK.TRY.18, TP.KTF12, TP.BKR.TRY.18, TP.KKP.TRY.18 | MAPPED |
| `housing_rate_new` | konut kredisi akım faiz oranı; yeni konut kredisi faiz oranı; yeni kullandırılan konut kredisi faizi; konut kredisi faizi (akım); konut kredisi faiz oranı (TL, Akım, %) | TP.KBK.TRY.18, TP.KTF12 | MAPPED |
| `housing_rate_portfolio` | konut kredisi stok faiz oranı; mevcut konut kredisi faiz oranı; konut kredisi portföy faizi; konut kredisi faiz oranı (TL, Stok, %) | TP.BKR.TRY.18, TP.KKP.TRY.18 | MAPPED |
| `cpi_level` | TÜFE; tüketici fiyat endeksi; TÜFE endeks düzeyi; tüketici fiyatları endeksi | none | UNRESOLVED |
| `inflation_rate` | enflasyon oranı; TÜFE değişim oranı; tüketici fiyat enflasyonu; TÜFE artış oranı | none | UNRESOLVED |
| `kfe` | KFE; konut fiyat endeksi; konut fiyatları endeksi; konut fiyat göstergesi | TP.KFE.TR, TP.KFE.TR10, TP.KFE.TR51, TP.KFE.TR31 | PARTIAL |
| `kfe_national` | Türkiye konut fiyat endeksi; ulusal konut fiyat endeksi; Türkiye KFE | TP.KFE.TR | MAPPED |
| `kfe_istanbul` | İstanbul konut fiyat endeksi; İstanbul KFE | TP.KFE.TR10 | MAPPED |
| `kfe_ankara` | Ankara konut fiyat endeksi; Ankara KFE | TP.KFE.TR51 | MAPPED |
| `kfe_izmir` | İzmir konut fiyat endeksi; İzmir KFE | TP.KFE.TR31 | MAPPED |
| `housing_archived` | konut arşiv serileri; arşiv konut serisi | TP.VK02, TP.TK02 | PARTIAL |

## Unresolved source context

- **BDDK balance in this v1 snapshot:** table 4, row 2, Sektör 10001 and TP/YP/Toplam selectors are documented; no BDDK CatalogRecord was minted at M13-08 delivery. M3-05 now defines a separate selector identity/metadata builder below. This snapshot still has no BDDK candidate, and monthly stock does not establish disbursement.
- **BDDK weekly/FinTürk:** retain Friday/Milyon TL versus quarterly/province/Bin TL and mixed-unit table context, without inventing a housing row, column schema or series identity. Bank/currency variants are not interchangeable.
- **CPI:** `bie_tukfiy2025`, `bie_tukfiy2003` and archived `bie_tukfiy4` are groups, not series. Preserve 2025/2003 base labels; CPI level and inflation rate remain separate unresolved concepts.
- **KFE:** the four current-group identities are retained. Archived `bie_tkfe` (2010) / `bie_hkfe` (2017) have no documented series mapping; broad KFE remains PARTIAL for these variants. Do not assign their bases to current-group IDs.
- **Archived housing labels:** TP.VK02 / TP.TK02 are archived; exact economic meaning, native frequency and successor/equivalence relationships are unknown. They are not silently attached to a rate/balance family.

## Families and ambiguity

Families are `housing_amount`, `housing_rates`, `consumer_prices`, `housing_prices`; membership is explicit on each concept. All exclude the two archived identities from default family discovery. Family rationale describes a catalog neighborhood, not an economic cause or a preselected winning relationship. No target-to-family expansion algorithm is implemented; later discovery must exclude target/derived duplicates and support no useful candidate.

The exact key `konut kredisi` belongs to both the generic and balance concepts. Lookup unions candidate identities deterministically and retains both unresolved concept references; it never overwrites one mapping with another. Both weekly housing-rate IDs and both monthly IDs remain distinct. KFE geography/version is never silently selected by ranking.

## Loading and validation

`catalog.mappings.load_reviewed_snapshot(bytes)` accepts at most 256 KiB, validates closed contracts, digest, identities, references, resolutions, normalized keys and family exclusions. It performs no file/network/SQL/model operation. Caller supplies trusted, review-selected artifact bytes; validation alone does not establish that arbitrary submitted metadata is authentic.

`lookup_alias(snapshot, query, include_archived=False)` is exact dictionary validation/lookup, not catalog_search or BM25. It uses the existing normalizer, returns a sorted union and explicit clarification/unresolved state. Archived candidates are removed unless explicitly requested; UNKNOWN status remains UNKNOWN. It does not implement general metadata/semantic filtering or select a series.

`tests/unit/test_catalog_mappings.py` pins the real ID set and repository evidence, validates ambiguity, unknowns, group-vs-series boundaries, family exclusions, normalization, deterministic serialization and hostile/inconsistent inputs. It is development validation only. No M13-09 query-to-series holdout is authored or consumed.

## Current catalog boundary

DEC-135 retains this reviewed local/versioned artifact as demo input, not the
entire final BDDK/EVDS catalog. Aliases are precision shortcuts rather than the
only catalog knowledge. Broader reviewed metadata coverage remains future work;
under the [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement), prepared observations are the primary demo path. A pool miss may clarify/abstain; official adapter materialization at runtime is future scalability, not a core demo prerequisite. Neither discovery nor materialization may invent identities; this snapshot contains no implemented availability/router extension. M13-04 is now DONE for bounded offline lexical retrieval;
see [the delivered catalog_search contract](CATALOG_SEARCH.md).

The [DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime) initial dataset is housing credit balance, housing/mortgage rate, CPI/TÜFE and KFE over approximately 2021-01–2026-06. This metadata snapshot is not that observation dataset. The BDDK housing semantic/component selection and CPI real series IDs still need resolution; the separate M3-05 internal selector identity does not resolve those choices; CPI datagroups cannot substitute for series. Preserve unknown rate status and KFE base/reference-year distinctions. The four concepts are the first verified vertical-slice target, not final coverage; broader loan/deposit/rate/catalog coverage must reuse the same trusted identity and ingestion architecture. Conceptual availability must distinguish prepared, officially fetchable, unresolved and unsupported based on trusted evidence, not an alias match. No JSON mappings or source evidence hashes are changed by this architecture clarification.

M3-05 separately supplies an [offline monthly BDDK identity/metadata builder](BDDK_MONTHLY_METADATA.md). Its labelled composite selectors can form explicit CatalogRecord/ReviewedSeries candidates; this historical v1 artifact and its unresolved BDDK entries remain unchanged. Adding candidates to the reviewed discovery snapshot requires a separate evidence-backed update that retains stock/disbursement and TP/YP/TOTAL clarification. No current alias is remapped by the builder.

The final hybrid target combines shared Turkish normalization, reviewed aliases, metadata filters, BM25 and Qwen dense retrieval (`kkbhackathon2026/Qwen3-Embedding-8B`, 4096). Dense and vector indexing remain unimplemented. Catalog vector records may bind trusted IDs, concept/family, normalized text/hash, model/dimension/vector and snapshot/version; financial values stay in lakehouse silver/gold, with bronze as source evidence. LanceDB is the selected catalog vector index (DEC-138), not yet installed. Broader reviewed catalog/prepared coverage follows the first real slice as safely practical; this historical JSON snapshot and its source pins remain unchanged.

## Handoff to M13-04

**Historical handoff at M13-08 delivery:** After this task merges, the reviewed mapping and usable bounded CatalogRecord input prerequisites for **offline demo-scope M13-04** are satisfied. M13-04 still implements its own bounded typed tool, lexical/BM25 and metadata filters. Review DuckDB FTS extension/index requirements without relaxing the existing hardened lakehouse connection; no index design is selected here. This snapshot cannot resolve BDDK/CPI questions or claim full-source coverage.

DEC-130 remains unchanged: M13-05 dense retrieval is required for full hybrid acceptance; RRF/reranking remain benchmark-gated. This task starts none of those stages and closes no live-access or source-use question.
