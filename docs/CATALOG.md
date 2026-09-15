# Catalog and retrieval reference

This reference owns reviewed mappings, lexical ranking, local vector storage,
candidate composition and bounded planner continuation. Delivery status belongs
to [ROADMAP](ROADMAP.md#current-project-status), runtime composition to
[ARCHITECTURE](ARCHITECTURE.md#catalog-runtime-composition), and measured results
to [EVALUATION](EVALUATION.md#catalog-validation-records). A catalog hit is neither
an observation nor permission to calculate or fetch.

Use the operator-selected [v3/r4 artifact](catalog/prepared_v3.json) with the
matching prepared pool. [EVDS_COVERAGE](EVDS_COVERAGE.md) records its review.
The v1/v2 mapping tables below are preserved historical snapshot references;
their old availability and implementation statements do not describe current dev.
Rebuild vector generations when the catalog content digest changes.


<a id="catalog_search-bounded-combined-candidate-contract"></a>

## Bounded combined candidate contract

`CatalogDenseStage(index, embed_query, combination_policy)` binds a checked local
index to an operator-supplied normalized-query embedding callback. It must implement
the explicit input policy declared by the index and return a matching `QueryVector`.
Composition chooses no endpoint, prefix, key or hosted fallback. The lexical-only
factory does not initialize the native vector engine. No live callback or real
index generation is enabled automatically; the prepared API enables one only for
an explicit `--catalog-index` (see [prepared runtime dense stage](#catalog_search-prepared-runtime-dense-stage)).

Provider, native-frequency and archive eligibility is shared by both stages.
Matched reviewed exact/longest phrases additionally bound IDs; similarity cannot
widen a precise CPI-base query or fill unresolved disbursement with balance.
Empty eligibility skips embedding and retains UNRESOLVED/FILTERED_OUT.

Both combination policies take up to ten candidates per stage, interleave stage
positions and deduplicate IDs. The shared deterministic reviewed-intent post-order
then refines candidates only for explicit query qualifiers with typed/reviewed
counterparts: amount/rate kind, new/outstanding rate basis, inclusion/exclusion,
currency/component, base year and archive intent. Unknown candidate semantics are
neutral, and the pre-policy order breaks ties. Archived records stay after
non-archived records unless the caller both opts in and explicitly requests archive
material; UNKNOWN status is never called active. The caller's 1–10 limit applies
last. The default
**`reviewed-match-order-v1`** ([DEC-142](DECISIONS.md#dec-142--catalog-query-embedding-policy-and-reviewed-match-combination))
starts with the lexical position only when a reviewed alias or phrase matched and
with the dense position otherwise. **`alternating-archive-tier-v1`**, the M13-09
baseline, always starts lexical and stays selectable for comparison. Native distance
ties use stable IDs. There is no BM25/cosine score addition, RRF or model/listwise
reranker; the post-order never creates candidates or changes stage scores/status.
Measured gains and remaining losses are in
[EVALUATION](EVALUATION.md#m13-15-catalog-quality-hardening-2026-09-15).

Candidates carry retrieval source(s), per-stage rank, BM25 score if present in
that stage, and cosine distance if present in dense. Unmeasured scores are null.
Metadata comes from the reviewed snapshot, not a vector-table declaration.
`total_candidates` counts the retrieved union; per-stage totals describe eligible
candidates before caps. `truncated` covers stage or final caps. Scores/ranks are
not confidence or permission to calculate.

`m13-05-combined-v1` output reports snapshot/profile identity, input policy and
embedding origin. `hybrid` means both configured mechanics succeeded; an
`offline_fixture` origin does not establish Qwen semantic quality. No similarity
threshold is invented: unfamiliar wording may yield nearby candidates that still
need relevance/semantic review or clarification. Under
[DEC-143](DECISIONS.md#dec-143--similarity-only-catalog-results-are-unresolved-candidates),
such a nonempty similarity-only result is `PARTIAL`, not `MATCH`, when no reviewed
alias or phrase identified a catalog concept. Candidate order and visibility are unchanged.

Snapshot mismatch, embedding/policy failure or invalid/native index output
returns **`lexical_degraded`**, `dense_status=failed`, a fixed category and a tool
warning. Private exceptions are not copied. Unknowns/ambiguity remain even when
dense succeeds. The implemented bounded discovery/replan round is enabled in the
prepared runtime; its retrieval is hybrid only when an index generation is configured.

<a id="catalog_search-prepared-runtime-dense-stage"></a>

### Prepared runtime dense stage

`python -m kkb_agent.api ... --catalog-index <absolute generation>` opens a local
generation whose profile is `kkbhackathon2026/Qwen3-Embedding-8B`, 4096 dimensions,
`qwen3-instruct-query-v1` and origin `kloudeks`, bound to the `--catalog` snapshot.
Startup (including `--check`) refuses another snapshot, input policy, fixture origin,
missing/invalid generation or a `KLOUDEKS_EMBEDDING_MODEL` other than that model,
before any provider is built, with the existing redacted error. `--check` reports
`catalog_retrieval` (`hybrid` or `lexical`) without an embedding call. When serving,
each distinct normalized discovery query costs one embedding request through the
same configured provider (same timeout and attempts); a bounded cache holds the last
256 query vectors. Embedding or index failure yields `lexical_degraded` for that
search, not a failed turn. Without `--catalog-index` retrieval stays lexical.


<a id="catalog_search-catalog-and-observation-boundary"></a>

## Catalog and observation boundary

[DEC-137’s dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes user concept → catalog_search → trusted prepared series candidate → lakehouse the primary demo routing target. A prepared-pool miss may clarify/abstain; runtime cache-miss materialization remains future scalability. The current [prepared_v3 snapshot](catalog/prepared_v3.json), review r4, has 37 identities; v1/v2 remain historical snapshots. The [dated pool evidence](EVALUATION.md#prepared-api-delivery-and-pool-evidence) records observation counts and reproducibility limits separately. Catalog discovery does not prove local observations or requested-window coverage. See [runtime composition](ARCHITECTURE.md#catalog-runtime-composition) for prepared registration and [ROADMAP](ROADMAP.md#m13) for delivery status.

The final catalog spans safely representable BDDK/EVDS identities beyond the four-series vertical slice. Conceptual prepared/fetchable/unresolved/unsupported states require trusted manifest/adapter evidence; no such fields are added to the current result schema here. UNRESOLVED cannot trigger a fetch. The combined-stage contract above defines retrieval; it adds no observation-availability fields or fetch authority.


<a id="catalog_search-required-final-hybrid-and-vector-search-target"></a>

## Required final hybrid and vector-search target

The [runtime composition and final hybrid architecture](ARCHITECTURE.md#catalog-runtime-composition)
own the Qwen model/dimension, logical vector record, lakehouse separation,
lexical/dense flow and benchmark-gated extensions. [ROADMAP M13](ROADMAP.md#m13)
owns acceptance status. The contracts below describe how the configured stages
work; no index/profile declaration proves live embedding or semantic quality.

<a id="catalog_search-trusted-configuration-and-contracts"></a>

## Trusted configuration and contracts

The operator calls `make_catalog_search_tool(snapshot_bytes=...)` and explicitly
registers the returned ToolSpec. The factory validates the closed, at-most-256-KiB
M13-08 artifact, its content digest/references and demo/development purpose.
There is no default external loader, supplied path/URL/SQL, network access,
model call, live catalog update or mutable shared output. A valid digest proves
integrity, not authenticity: only owner-reviewed artifact bytes belong here.
The initial reviewed artifact remains `m13-08-demo-v1/r1` without modification.

Closed arguments:

| Field | Meaning / bound |
| --- | --- |
| query | Nonblank text, 1–512 characters, no control characters; shared normalization |
| max_results | Strict integer 1–10, default 10 |
| source | Optional provider name, 1–64 characters; normalized exact match, not a URL |
| frequency | Optional existing Frequency enum, including explicit unknown |
| include_archived | Strict boolean, default false |

The typed output contains status, candidates, matched concepts/conditions and
unresolved reasons, total eligible candidate count, truncation and clarification
flags, archive exclusion count, snapshot version/hash and retrieval version
`m13-04-lexical-v1`. Each candidate preserves the complete ReviewedSeries /
CatalogRecord, original source identity/labels/provenance, concept/family IDs,
rank, BM25 score, matched terms and method. Observation kind is explicitly
unknown because CatalogRecord does not declare it. Unknown active state,
frequency, unit, scale, aggregation permissions and base year stay unchanged.
Metadata remains untrusted and cannot authorize fetches or calculations.


<a id="catalog_search-deterministic-retrieval"></a>

## Deterministic retrieval

1. Shared normalization is applied to query and indexed titles/display labels
   and positive reviewed aliases. No numeric interpretation, stemming or hidden
   synonym generation occurs; exclusion/unresolved notes are not indexed as
   positive evidence.
2. An exact reviewed alias restricts candidates to the union of its concept
   mappings. Otherwise, whole-token contained reviewed phrases are recognized;
   a more specific phrase supersedes its generic substring. Equal phrases with
   multiple concepts and separate matched concepts remain sets. An unresolved
   mapping never falls back to a superficially similar series.
3. Provider/native-frequency filters and default archive exclusion apply before
   ranking. Without a reviewed phrase, BM25 searches only eligible reviewed
   records and keeps positive lexical scores. Family membership accompanies
   candidates; this is not relationship discovery or an automatic family-wide
   expansion/cause assertion.
4. BM25 uses `k1=1.2`, `b=0.75`, term frequency and document length, with positive
   `log(1 + (N-df+0.5)/(df+0.5))` IDF. Query terms count once. Corpus statistics
   use eligible records; scores are rounded to 12 decimal places. Scores are
   relevance evidence, never probabilities or cross-query comparable confidence.
5. Initial order is non-archived before explicitly included archived, descending
   score, then stable series ID. The shared reviewed-intent policy described above
   may stably refine that order for explicit compatible qualifiers. It does not
   expand retrieval, infer missing candidate metadata, or change MATCH/PARTIAL.
   No active status is inferred for UNKNOWN records. Apply max_results last;
   return the pre-cap count and truncation flag.

All returned candidates require clarification/semantic review, even top-1.
Four housing-rate IDs, the two weekly and two monthly pairs, KFE geographies,
unknown bases and unresolved amount/rate distinctions are not collapsed.
`PARTIAL` means candidates coexist with unresolved concept meaning or are supported
only by BM25/dense similarity without a reviewed concept match; `UNRESOLVED`
means a reviewed concept has no real candidate mapping. `FILTERED_OUT` means
mapped IDs were excluded by filters; `NO_MATCH` means no positive lexical or
reviewed match. Empty results never invent IDs. No stock/rate or unit inference
and no automatic successor for archived TP.VK02 / TP.TK02 are introduced.


<a id="catalog_index-inputs-and-storage"></a>

## Inputs and storage

`catalog.vectors.catalog_documents(snapshot)` builds stable ID-ordered passages
from titles, descriptions, labels, positive reviewed aliases and declared
semantics using the shared Turkish normalizer. Missing metadata stays unknown;
unresolved-only aliases/exclusion notes are not added as positive records.
A representation over 8192 UTF-8 bytes is refused instead of truncated.
No financial observation values are read or indexed.

An operator supplies a `CatalogVectors` batch with exactly one vector per
snapshot identity and the matching text digest. `VectorProfile` requires the
confirmed Qwen model/dimension, an **explicit input-policy identifier** and an
`offline_fixture` or `kloudeks` origin. The identifier is a declaration, not
proof of live approval or quality. There is no default input policy or guessed
query/passage prefix. Later embedding integration must implement/review that
policy for both kinds of input under Q-K-05.

`build_catalog_index(absolute_local_root, snapshot, vectors)` creates a fresh
local generation. Existing directories are refused. Wrong dimensions, nonfinite
or zero vectors, duplicate/missing/extra IDs and stale snapshot/text digests
fail before a directory is created. Vectors are normalized with stable scaling
and stored as Arrow float32 with a digest of those bytes. Text, identity and
concept/family IDs remain together. A manifest binds snapshot, profile, count
and row digest; it is written last. A failed build leaves no usable manifest.
Retry into a fresh directory without deleting/overwriting an earlier generation.

These directories are operator-owned artifacts, **not an upload/import format**.
Paths are never tool/model arguments. Relative paths, URI strings and UNC shares
are rejected. The local connection class is used directly, with no cloud
dispatcher, embedding-function metadata, SDK fallback or key. Hashes detect
mismatches, not an attacker controlling both database and manifest. Keep the
root out of Git, e.g. under the existing ignored `data/processed` directory.


<a id="catalog_index-opening-and-searching"></a>

## Opening and searching

`LocalCatalogIndex.open(root, snapshot, profile)` opens table version 1 and
requires the same snapshot, input policy and origin. It checks the fixed Arrow
schema, bounded count, representation/identity fields, vector digests and unit
norms. Missing/partial/changed content fails with fixed error categories.
Readers do not append or update the generation.

`index.search(QueryVector(...), eligible_ids=frozenset(...), limit=10)` takes
eligibility decided from reviewed metadata by the caller. The index cannot
decide archive/provider/native-frequency policy or financial meaning. Only
checked numeric ordinals enter the predicate; IDs/user strings are never SQL.
Eligibility applies **before** retrieval; empty eligibility returns immediately.
Exact cosine bypasses approximate indexes, reads all eligible bounded candidates
and sorts equal distances by ID before applying the 1–10 result limit.
Distances are not probabilities/confidence; even the nearest result is a candidate.

The separate [combined catalog layer](CATALOG.md#catalog_search-bounded-combined-candidate-contract)
maps IDs back to reviewed records for an optional operator-configured dense stage.
This index module does not combine BM25 scores, select an answer, provide financial
evidence, replan a conversation or call Kloudeks. RRF/reranking remain benchmark-gated. Broader
catalog ingestion and capacity/performance checks must precede raising the
current 40-record snapshot limit for full-source coverage.


<a id="catalog_evaluation-m13-09-retrieval-evaluation"></a>

## M13-09 retrieval evaluation and real embedding policies

[retrieval_cases_v3.json](catalog/retrieval_cases_v3.json) holds 44 reviewed
question-to-series cases (26 development, 18 holdout) bound to the v3/r4 content
digest. `relevant_series_ids` lists every acceptable identity; `primary_series_id`
appears only when the wording selects one; empty relevance cases list acceptable
lexical/hybrid statuses instead. The loader refuses unknown IDs, a primary outside
relevance, duplicate IDs, a missing split or another snapshot.

[retrieval_cases_v3_r2.json](catalog/retrieval_cases_v3_r2.json) keeps those 44
cases as development (the first holdout was inspected when PROP-08 was proposed)
and adds a fresh holdout N01–N22 written before any run on it.

`python -m kkb_agent.catalog.retrieval_eval --catalog docs/catalog/prepared_v3.json --cases docs/catalog/retrieval_cases_v3_r2.json --out <report>`
scores lexical-only offline. Adding `--index <generation> --policy <id> --env-file .env --enable-embedding-requests`
also scores dense-only (shared metadata eligibility, exact cosine), `hybrid`
(DEC-142 order) and `hybrid_alternating` (M13-09 baseline), caching one query
embedding per normalized query, and reports paired top-1 wins/losses per split. Both
real-embedding commands refuse a configured embedding model other than the profile's. Reports hold
hit@1/5, Recall@5/10, MRR, primary@1, no-answer status, archive leaks, dense
failures and latency per split and mode; dense-only has no abstention, so its top
candidate on no-answer cases is reported, not scored.

`kkb_agent.catalog.embedding` names two input policies: `qwen3-plain-v1`
(unchanged text) and `qwen3-instruct-query-v1` (queries as
`Instruct: <task>\nQuery:<text>`, passages unchanged).
`python -m kkb_agent.catalog.embedding --catalog ... --root <new absolute generation> --policy <id> --env-file .env --enable-embedding-requests`
embeds passages in batches (default 16) and builds a fresh generation; keep roots
under ignored `data/processed`. Measured results are in
[EVALUATION](EVALUATION.md#m13-09-retrieval-evaluation-2026-09-15) and
[the fresh-holdout record](EVALUATION.md#m13-05-fresh-holdout-2026-09-15);
DEC-142 selects the instruct policy for the prepared runtime.

<a id="catalog_continuation-activation-and-compatibility"></a>

## Activation and compatibility

`Session(..., catalog_continuation=True)` enables the phase contract. The registry
must explicitly contain an operator-configured `catalog_search` to use discovery.
If a plan directly uses known reviewed identities or published tables, it executes
without an extra discovery/model call. The default `False` preserves the prior
one-plan path. `Session.plan()` only plans; `Session.run()` owns execution and the
single continuation. No general autonomous research loop is introduced.

The existing prepared-pool rehearsal can opt in with a reviewed snapshot:

```powershell
python -m kkb_agent.live_check --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v2.json --turns 3
```

This command makes live Kloudeks calls and remains subject to the existing run
authorization. It is documentation, not evidence that a live run passed. It reads
and validates the bounded operator-owned catalog file, registers lexical search
and enables continuation. It does not silently enable query embeddings. An
application can separately inject the [configured combined stage](CATALOG.md)
into its registered tool once its real embedding policy is accepted. Invalid
catalog bytes fail before pool copying or a model call; paths/errors are redacted.

The prepared lakehouse must be closed during its existing private-copy step.
Analysis writes stay in that copy; source preparation is unchanged.


<a id="catalog_continuation-what-the-harness-enforces"></a>

## What the harness enforces

- A discovery plan contains only `catalog_search`, at most four independent
  queries. Mixing calculations or dependent queries into it is rejected before
  any step executes and consumes the ordinary plan-repair budget.
- Only successful typed catalog outputs reach the second plan. Metadata is
  revalidated and projected without source locators, observation samples or
  source-evidence file references. Financial declarations, original descriptions,
  review notes, ambiguity, unresolved conditions and stage provenance remain.
- The feedback is a JSON **user/data message**, never a system message. The
  Kloudeks transport's leading-system merge preserves this distinction. JSON
  is a representation, not a proof against injection; executable authority is
  still enforced by the registry, phase validation and analytical tools.
- Feedback is capped at 32 KiB in UTF-8. Oversized metadata is refused rather
  than silently dropping conditions that could determine the series choice.
- The one continuation may use only registered `lakehouse`, `anomaly`,
  `causality`, `change_detection` and `table_transform`, or clarify. It receives
  only those tool descriptions. No second discovery or catalog-derived
  `web_search`/`web_url` action is accepted, even if a web tool exists in the
  broader registry. A separately requested direct web workflow remains separate.
- Continuation IDs must be fresh, and discovery steps cannot be referenced as
  calculation dependencies. The analysis gets a fresh execution context; catalog
  metadata is not an input table or numerical evidence.
- `max_steps` and `max_plan_repairs` are shared across both phases. With defaults,
  at most eight distinct steps and two plan repairs across at most two planning
  phases are accepted. Each provider call retains its own bounded transport/schema
  retries; the plan counts are not a claim of total HTTP-call or wall-time limits.
- The executor binds every returned tool/step identity to the validated step,
  including exhausted retries, preserving the outcome's real trace and evidence.

`Planned.plan` is the final analysis/clarification plan; `Planned.discovery_plan`
keeps the earlier validated plan separately. `attempts` and `rejections` are
aggregate; `discovery_rounds` is zero or one. `ExecutionOutcome.results` preserves
both phases in order. The live-check report includes a separate discovery record.
It does not merge historical discovery steps into an executable clarification plan.


<a id="catalog_continuation-clarification-and-remaining-limits"></a>

## Clarification and remaining limits

`AnalyticalPlan` has either nonempty steps or `steps=[]` plus one fixed reason:
`ambiguous_series`, `missing_series`, `unresolved_semantics`, `unsupported_request`.
Neither an empty reasonless plan nor a reason plus executable steps is accepted.
A clarification produces a fixed Turkish prompt, no writer/model prose, no
analytical claim and no workspace publication. Candidate details remain available
in the discovery outcome for a future UI; no invented explanation is displayed.

This is an **offline-tested integration**, not live model-selection quality.
The planner still decides whether the question distinguishes candidates; mandatory
selected-series inspection has a [prepared-reader slice](ARCHITECTURE.md#series_inspection-prepared-series-metadata-inspection),
while broader M13-13 and natural-language choice validation remain unfinished. Total deadline/cancellation,
cross-turn automatic replanning/staleness, wider source availability, real embedding
input policy and held-out retrieval quality are separate work. The mode is not a
proof that every candidate ambiguity is resolved correctly.

The four example searches for total housing credit, housing interest, CPI and KFE
produce 15 returned candidate entries and **25,385 UTF-8 bytes** of projected
feedback with the reviewed v2 snapshot. This is below the local cap; it is not a
measurement of model context/token capacity or live latency.

See [ARCHITECTURE](ARCHITECTURE.md), [SECURITY](SECURITY.md),
[EVALUATION](EVALUATION.md), and the [current ROADMAP](ROADMAP.md#current-project-status).


<a id="catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping"></a>

## Historical mapping — M13-08 — Reviewed offline demo catalog mapping

Snapshot reference headings and their full contents follow below.


<a id="catalog_mapping-current-prepared-scope-revision-2026-09-14"></a>

## Historical mapping — Current prepared-scope revision (2026-09-14)

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


<a id="catalog_mapping-historical-v1-review"></a>

## Historical mapping — Historical v1 review

Owner: Çağatay. Team/owner review artifact: [PR #117](https://github.com/cagatayeroglu/KKB-DataTrio/pull/117). Scope was explicitly approved on 2026-09-12; merge/completion evidence is maintained in [ROADMAP](ROADMAP.md#m13). No separate external reviewer or live approval is claimed.


<a id="catalog_mapping-version-and-trust-boundary"></a>

## Historical mapping — Version and trust boundary

- Snapshot: [demo_v1.json](catalog/demo_v1.json), version `m13-08-demo-v1`, review revision `r1`, date `2026-09-12`.
- Canonical content SHA-256: `230807e195663a59978c69448c8cb63acbd10130080b09a5f3d474a6b58da5f6`. Hash sorted-key compact UTF-8 JSON of the validated payload excluding only `content_sha256`; array order is retained. This is integrity/version identity, not proof of source truth.
- Evidence revision: `904e22dd9e70100e0a7b69b02aa08dffb5daa905`. Evidence entries pin the path, section and SHA-256 of the already-merged [BDDK](BDDK_SOURCE.md) and [EVDS](EVDS_SOURCE.md) inventories. No ignored raw files, stash, source fetch or model output was used.
- 10 real source identities; 50 distinct original alias strings / 51 concept-alias entries, 14 concepts, 4 families. Original aliases are reviewed authored vocabulary, not claimed provider titles.
- This is a small repository-backed **demo/development** snapshot, not the full EVDS catalog, M13-09 holdout, independently validated live metadata or permission to calculate/fetch. Labels and source fragments remain untrusted data.
- `CatalogRecord` semantics are referenced rather than copied into aliases. ReviewedSeries adds only documented geography and rate basis (new credit versus outstanding portfolio); both interest-rate types remain `StockFlow.RATE`.
- KFE titles are clearly labelled inventory descriptions, not verbatim provider series titles. Their base year, coverage, unit/scale and active status are not inferred. All eight non-archived records have status UNKNOWN. No samples are fabricated. Only TP.KTF12 has the explicit complete aggregation flags demonstrated in the inventory.


<a id="catalog_mapping-real-identity-inventory"></a>

## Historical mapping — Real identity inventory

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


<a id="catalog_mapping-complete-concept-mapping"></a>

## Historical mapping — Complete concept mapping

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


<a id="catalog_mapping-unresolved-source-context"></a>

## Historical mapping — Unresolved source context

- **BDDK balance in this v1 snapshot:** table 4, row 2, Sektör 10001 and TP/YP/Toplam selectors are documented; no BDDK CatalogRecord was minted at M13-08 delivery. M3-05 now defines a separate selector identity/metadata builder below. This snapshot still has no BDDK candidate, and monthly stock does not establish disbursement.
- **BDDK weekly/FinTürk:** retain Friday/Milyon TL versus quarterly/province/Bin TL and mixed-unit table context, without inventing a housing row, column schema or series identity. Bank/currency variants are not interchangeable.
- **CPI:** `bie_tukfiy2025`, `bie_tukfiy2003` and archived `bie_tukfiy4` are groups, not series. Preserve 2025/2003 base labels; CPI level and inflation rate remain separate unresolved concepts.
- **KFE:** the four current-group identities are retained. Archived `bie_tkfe` (2010) / `bie_hkfe` (2017) have no documented series mapping; broad KFE remains PARTIAL for these variants. Do not assign their bases to current-group IDs.
- **Archived housing labels:** TP.VK02 / TP.TK02 are archived; exact economic meaning, native frequency and successor/equivalence relationships are unknown. They are not silently attached to a rate/balance family.


<a id="catalog_mapping-families-and-ambiguity"></a>

## Historical mapping — Families and ambiguity

Families are `housing_amount`, `housing_rates`, `consumer_prices`, `housing_prices`; membership is explicit on each concept. All exclude the two archived identities from default family discovery. Family rationale describes a catalog neighborhood, not an economic cause or a preselected winning relationship. No target-to-family expansion algorithm is implemented; later discovery must exclude target/derived duplicates and support no useful candidate.

The exact key `konut kredisi` belongs to both the generic and balance concepts. Lookup unions candidate identities deterministically and retains both unresolved concept references; it never overwrites one mapping with another. Both weekly housing-rate IDs and both monthly IDs remain distinct. KFE geography/version is never silently selected by ranking.


<a id="catalog_mapping-loading-and-validation"></a>

## Historical mapping — Loading and validation

`catalog.mappings.load_reviewed_snapshot(bytes)` accepts at most 256 KiB, validates closed contracts, digest, identities, references, resolutions, normalized keys and family exclusions. It performs no file/network/SQL/model operation. Caller supplies trusted, review-selected artifact bytes; validation alone does not establish that arbitrary submitted metadata is authentic.

`lookup_alias(snapshot, query, include_archived=False)` is exact dictionary validation/lookup, not catalog_search or BM25. It uses the existing normalizer, returns a sorted union and explicit clarification/unresolved state. Archived candidates are removed unless explicitly requested; UNKNOWN status remains UNKNOWN. It does not implement general metadata/semantic filtering or select a series.

`tests/unit/test_catalog_mappings.py` pins the real ID set and repository evidence, validates ambiguity, unknowns, group-vs-series boundaries, family exclusions, normalization, deterministic serialization and hostile/inconsistent inputs. It is development validation only. No M13-09 query-to-series holdout is authored or consumed.


<a id="catalog_mapping-current-catalog-boundary"></a>

## Historical mapping — Current catalog boundary

DEC-135 retains this reviewed local/versioned artifact as demo input, not the
entire final BDDK/EVDS catalog. Aliases are precision shortcuts rather than the
only catalog knowledge. Broader reviewed metadata coverage remains future work;
under the [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement), prepared observations are the primary demo path. A pool miss may clarify/abstain; official adapter materialization at runtime is future scalability, not a core demo prerequisite. Neither discovery nor materialization may invent identities; this snapshot contains no implemented availability/router extension. M13-04 is now DONE for bounded offline lexical retrieval;
see [the delivered catalog_search contract](CATALOG.md).

The [DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime) initial dataset is housing credit balance, housing/mortgage rate, CPI/TÜFE and KFE over approximately 2021-01–2026-06. This metadata snapshot is not that observation dataset. The BDDK housing semantic/component selection and CPI real series IDs still need resolution; the separate M3-05 internal selector identity does not resolve those choices; CPI datagroups cannot substitute for series. Preserve unknown rate status and KFE base/reference-year distinctions. The four concepts are the first verified vertical-slice target, not final coverage; broader loan/deposit/rate/catalog coverage must reuse the same trusted identity and ingestion architecture. Conceptual availability must distinguish prepared, officially fetchable, unresolved and unsupported based on trusted evidence, not an alias match. No JSON mappings or source evidence hashes are changed by this architecture clarification.

M3-05 separately supplies an [offline monthly BDDK identity/metadata builder](BDDK_MONTHLY_METADATA.md). Its labelled composite selectors can form explicit CatalogRecord/ReviewedSeries candidates; this historical v1 artifact and its unresolved BDDK entries remain unchanged. Adding candidates to the reviewed discovery snapshot requires a separate evidence-backed update that retains stock/disbursement and TP/YP/TOTAL clarification. No current alias is remapped by the builder.

The final hybrid target combines shared Turkish normalization, reviewed aliases, metadata filters, BM25 and Qwen dense retrieval (`kkbhackathon2026/Qwen3-Embedding-8B`, 4096). Dense and vector indexing remain unimplemented. Catalog vector records may bind trusted IDs, concept/family, normalized text/hash, model/dimension/vector and snapshot/version; financial values stay in lakehouse silver/gold, with bronze as source evidence. LanceDB is the selected catalog vector index (DEC-138), not yet installed. Broader reviewed catalog/prepared coverage follows the first real slice as safely practical; this historical JSON snapshot and its source pins remain unchanged.


<a id="catalog_mapping-handoff-to-m13-04"></a>

## Historical mapping — Handoff to M13-04

**Historical handoff at M13-08 delivery:** After this task merges, the reviewed mapping and usable bounded CatalogRecord input prerequisites for **offline demo-scope M13-04** are satisfied. M13-04 still implements its own bounded typed tool, lexical/BM25 and metadata filters. Review DuckDB FTS extension/index requirements without relaxing the existing hardened lakehouse connection; no index design is selected here. This snapshot cannot resolve BDDK/CPI questions or claim full-source coverage.

DEC-130 remains unchanged: M13-05 dense retrieval is required for full hybrid acceptance; RRF/reranking remain benchmark-gated. This task starts none of those stages and closes no live-access or source-use question.
