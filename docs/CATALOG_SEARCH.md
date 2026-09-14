# M13-04 — Offline reviewed catalog search

`catalog_search` discovers bounded candidates, not observation values or verified
analytical claims. It uses the [M13-08 reviewed snapshot](CATALOG_MAPPING.md) and
shared Turkish normalizer. Delivered under DEC-133 and retained by DEC-135, this is
the authoritative lexical/reviewed baseline for the bounded offline demo scope;
full hybrid acceptance still needs M13-05 dense retrieval and evaluation.

The separate [local LanceDB index](CATALOG_INDEX.md) implements validated vector
persistence and exact search over eligible IDs. The existing factory now accepts
an optional operator-injected `CatalogDenseStage` for combined candidate retrieval.
Without it, lexical-only behavior remains. Configured stages run both methods
when reviewed eligibility is nonempty, even after lexical success. This is tested
with fixture vectors; live policy and semantic quality remain separate work.
The opt-in [bounded catalog continuation](CATALOG_CONTINUATION.md) now lets a
planner consume these candidate results as data before one analysis/clarification
plan. Default one-plan sessions retain their previous behavior.

## Bounded combined candidate contract

`CatalogDenseStage(index, embed_query)` binds a checked local index to an
operator-supplied normalized-query embedding callback. It must implement the
explicit input policy declared by the index and return a matching `QueryVector`.
Composition chooses no endpoint, prefix, key or hosted fallback. The lexical-only
factory does not initialize the native vector engine. No live callback or real
index generation is enabled automatically.

Provider, native-frequency and archive eligibility is shared by both stages.
Matched reviewed exact/longest phrases additionally bound IDs; similarity cannot
widen a precise CPI-base query or fill unresolved disbursement with balance.
Empty eligibility skips embedding and retains UNRESOLVED/FILTERED_OUT.

The initial **`alternating-archive-tier-v1`** policy takes up to ten candidates
per stage, alternates lexical then dense positions, deduplicates IDs, keeps
explicitly requested archives after current/unknown records, then applies the
caller's 1–10 final limit. Native distance ties use stable IDs. There is no BM25/
cosine score addition, RRF or reranker. This transparent baseline is for later
same-case quality comparison, not a claim of measured gain.

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
need relevance/semantic review or clarification.

Snapshot mismatch, embedding/policy failure or invalid/native index output
returns **`lexical_degraded`**, `dense_status=failed`, a fixed category and a tool
warning. Private exceptions are not copied. Unknowns/ambiguity remain even when
dense succeeds. Full M13-05 acceptance still needs live policy, actual corpus/query
embeddings and separate development/held-out evaluation. The implemented bounded
discovery/replan round is enabled in prepared runtime; its retrieval remains lexical.

## Catalog and observation boundary

[DEC-137’s dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes user concept → catalog_search → trusted prepared series candidate → lakehouse the primary demo routing target. A prepared-pool miss may clarify/abstain; runtime cache-miss materialization remains future scalability. The current [prepared_v3 snapshot](catalog/prepared_v3.json), review r4, has 37 identities; v1/v2 remain historical snapshots. Arda's recorded 29-series / 4,124-observation pool is local to his environment, absent from a fresh Git checkout and not an identically reproducible repository artifact ([handoff](HANDOFF_ARDA_2026-09-14.md)). Catalog discovery does not prove local observations or requested-window coverage. The prepared runtime enables bounded discovery/replan continuation, but registers lexical catalog search without the real Qwen dense stage. Broader metadata coverage and availability routing remain unfinished.

The final catalog spans safely representable BDDK/EVDS identities beyond the four-series vertical slice. Conceptual prepared/fetchable/unresolved/unsupported states require trusted manifest/adapter evidence; no such fields are added to the current result schema here. UNRESOLVED cannot trigger a fetch. Required final hybrid retrieval adds the confirmed Qwen embedding model (4096 dimensions); aliases/filters/BM25 remain the default callable path, with an optional operator-configured combined stage. DEC-138 selected LanceDB; local indexing/composition are implemented, while live policy, actual embedding injection into prepared runtime and semantic quality remain unfinished.

## Required final hybrid and vector-search target

Turkish normalization + reviewed aliases + metadata filters + BM25/lexical + `kkbhackathon2026/Qwen3-Embedding-8B` dense retrieval (**4096 dimensions**) form the final hybrid architecture. The bounded LanceDB index and optional lexical/dense composition are implemented; actual Qwen corpus/query embeddings are not wired into default prepared runtime and live hybrid acceptance remains pending. Dense is a required final capability, not an optional enhancement. Model access remains Kloudeks-only.

```text
catalog_search -> BM25 candidates
  + query embedding via Qwen -> vector similarity search over catalog embeddings
  + metadata constraints -> bounded combined candidate set
  -> trusted prepared identity -> lakehouse financial values
```

The intended vector DB/index layer binds official/canonical selector IDs, concept/family, normalized catalog text and hash, embedding model/dimension/vector and snapshot/version metadata. It does not hold observation values or replace DuckDB/Parquet. LanceDB is the selected catalog vector index ([DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git)); its bounded local storage/search slice is described in [CATALOG_INDEX](CATALOG_INDEX.md), while live/hybrid integration remains pending. No separate PostgreSQL/pgvector service is justified by this refinement. Dedicated-index scaling beyond measured need is later work; required dense retrieval remains in the core delivery priorities.

This target does not imply that the implemented local index has a live query-embedding path. RRF/reranking remain benchmark-gated; a lexical fallback is degraded retrieval, not full hybrid acceptance.

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
5. Order is non-archived before explicitly included archived, descending score,
   then stable series ID. No active status is inferred for UNKNOWN records.
   Apply max_results last; return the pre-cap count and truncation flag.

All returned candidates require clarification/semantic review, even top-1.
Four housing-rate IDs, the two weekly and two monthly pairs, KFE geographies,
unknown bases and unresolved amount/rate distinctions are not collapsed.
`PARTIAL` means candidates coexist with unresolved concept meaning; `UNRESOLVED`
means a reviewed concept has no real candidate mapping. `FILTERED_OUT` means
mapped IDs were excluded by filters; `NO_MATCH` means no positive lexical or
reviewed match. Empty results never invent IDs. No stock/rate or unit inference
and no automatic successor for archived TP.VK02 / TP.TK02 are introduced.

## FTS review and scope

At implementation, local DuckDB 1.5.5 had no installed FTS extension. Even its
extension inventory requires filesystem access refused by the hardened lakehouse
connection. No INSTALL/LOAD/autoload or download was attempted. M13-04 uses a
bounded in-memory Python BM25 calculation over this small reviewed corpus instead
of requiring an extension or a separate index connection. This is a task-local
lexical implementation, not a change to the DEC-112 analytical engine. No new
dependency is needed. Lakehouse external-access/extension restrictions remain
unchanged. A larger corpus/index change needs its own measured task review.

## Validation and handoff

`tests/unit/test_catalog_search.py` covers aliases/normalization, specificity,
ambiguity/caps, source/frequency/archive filtering, preserved metadata/families,
unknown/unresolved cases, ranking/order/serialization, content identity and
holdout rejection, inert labels, output-mutation isolation, closed arguments,
planner discovery and seven coexisting factories. Scripted Session tests verify
catalog metadata cannot produce an analytical claim or enter the writer as
verified evidence. Existing six-tool/agent regressions remain required.

These development cases are not M13-09 holdout or Recall@5/10 evidence. No live
source/model/search request, embedding, RRF/reranking, table_transform or new
automatic inspection/quality/reconciliation harness integration is implemented. Actual delivery/merge evidence belongs to
[ROADMAP](ROADMAP.md#m13). M13-13 mandatory inspection still needs its trusted-ID lookup/usable-metadata
contract review before being claimed; M13-05 retains its transport/configuration
prerequisites.
