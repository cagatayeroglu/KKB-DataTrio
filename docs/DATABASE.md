# Database definition

The database definition the brief lists as a deliverable, alongside the architecture drawings, the documents and the repository.

One DuckDB file holds every table. There is no server: DuckDB runs inside the application process, so there is nothing to deploy, nothing listening on a port, and nothing to fail separately on demo day. [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse) records why.

Every table is created by `apply_schema` in [database.py](../src/kkb_agent/database.py), which is also the only list of what exists. The DDL itself lives beside the code that reads and writes each table, so a table's rules sit next to their enforcement; `TABLES` keeps a single answer to "what is in here", and [test_database.py](../tests/unit/test_database.py) fails if this document and the code disagree.

## Prepared official-data boundary

Under [DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime), scoped official BDDK/EVDS ingestion prepares the initial housing balance/rate, CPI and KFE observations (approximately 2021-01–2026-06) before demo runtime. Bronze preserves source artifacts and retrieval provenance; silver records normalized values with explicit source semantics; gold holds required derived/aligned representations. Thin source adapters reuse these storage boundaries. Runtime `catalog_search` selects trusted metadata and `lakehouse` queries prepared values; neither a metadata snapshot nor empty storage tables constitute a prepared dataset.

The tables below are implemented storage. Bounded Monthly and EVDS adapters now prepare official data through the existing bronze/manifest/silver/lineage boundaries. Arda's [recorded 29-series / 4,124-observation pool](HANDOFF_ARDA_2026-09-14.md) is operator-local: a fresh Git checkout has no `data/processed/lakehouse`, and the exact snapshot is not repository-reproducible today. Rebuild instructions do not establish identical source bytes or pool hashes. Preparation must retain source identity, vintage, normalization and computation evidence. Fixed-pool acceptance does not require sophisticated refresh orchestration, but competing vintages and retention remain M3-09/M12-12 and Q-DATA-03 concerns.

## Versioned dataset and object storage target

Under DEC-137, catalog identity is separate from availability for an exact requested window and dataset version. Intended lifecycle: discover → fetch → snapshot → parse → validate → materialize → version → query → refresh. Stage/validate before publishing a usable dataset version; failure must leave prior trusted versions intact. Same source content/selector/parser/semantic policy yields the same content version or idempotent no-op. Preserve raw snapshots, retrieval/release context and prior vintages when new periods, corrected values, metadata or archive state appear. Existing silver primary keys/upserts do not implement this version/refresh policy; M3-09/M12-12 must establish it.

Parquet is persistent analytical data/artifact format; DuckDB is embedded computation/query, not a hosted service. A future provider-neutral Dataset/Object Storage boundary may support local persistent filesystem/volume and S3-compatible storage for bronze, Parquet, manifests and versions. AWS S3 is not selected; S3-compatible integration is not implemented. Q-INFRA-01/02 own volume lifetime, availability and runtime credentials. Vector caches/indexes contain catalog descriptions/aliases/concepts, never financial observation values.

Core official materialization is intended persistent/versioned catalog data. CSV/XLSX/PDF and authorized URL artifacts remain session-scoped external data, even when common bronze/parser/lakehouse primitives are reused; they cannot automatically become permanent official series. Retention/redistribution and dataset publication are distinct from M5-21's accepted-turn workspace commit.

## Lakehouse layers and separate vector-search responsibility

The [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes the prepared pool the primary structured BDDK/EVDS demo path. Build it through approved adapters before questions arrive; normal runtime uses silver canonical observations and gold where an appropriate trusted analytical materialization exists. Bronze is immutable raw source evidence, never direct analytical truth. All three are lakehouse layers:

| Boundary | Owns / serves |
| --- | --- |
| Bronze | Content-addressed raw official responses/snapshots and retrieval provenance |
| Silver | Normalized trusted canonical observations with declared source semantics |
| Gold | Aligned/joined/transformed analytical materializations/results with evidence |
| DuckDB + Parquet lakehouse | Financial observations and analytical data across those layers; raw bytes remain artifact files with database metadata |
| Intended vector DB/index layer | Catalog text embeddings and semantic series/selector discovery only; no financial observation values |

Vector records may bind official/canonical ID, concept/family, normalized search text and hash, model ID, dimension 4096, vector and snapshot/version metadata. No table/schema or vector index is added by this document. LanceDB is the selected catalog vector index ([DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git)), stored beside but separate from the lakehouse; the bounded local index is implemented ([CATALOG_INDEX](CATALOG_INDEX.md)). Default prepared API retrieval is still lexical, with real Qwen embedding injection and live hybrid acceptance pending. No PostgreSQL/pgvector service is introduced.

Runtime official-source cache-miss materialization, sophisticated refresh/vintage orchestration and object-storage optimization remain future scalability work, not core demo prerequisites. Minimum source identity/version evidence and refusal of silent historical overwrite still apply to every prepared dataset. Pool misses may clarify/abstain; no full availability router is claimed.

## Layout on disk

```text
<root>/
  kkb.duckdb        every table below
  bronze/<sha256>   retrieved payloads, verbatim, one file per artifact
  silver/*.parquet  exports for handover and inspection
  gold/             reserved for analysis-ready exports
```

Everything is a file under one directory, so a backup is a copy and a reset is a delete. Under [DEC-126](DECISIONS.md#dec-126--single-vm-deployment-with-docker-compose) that directory is a mounted volume on the demo host.

## How the layers connect

```text
bronze_artifacts ──┐
   (bytes+hash)    │ artifact_id
                   ▼
            silver_series ──┐
         (what it means)    │ series_id
                            ▼
                  silver_observations
                   (period, value)
                            │
                            ▼
                       gold_cells ──── column_node_id ───► lineage_nodes
                  (one spine, one table)                   lineage_edges
                                                                 ▲
workspace_bindings ──► workspace_artifacts ── lineage_node ──────┘
   (name → current)      (immutable definition)
workspace_history            │
   (every revision)          └── value_ref ──► workspace_results
                                                (immutable typed values)
```

Read it as one sentence: bytes arrive and are hashed, a series says what those numbers mean, observations carry the values, gold puts several series on one spine, lineage records how every cell got there, and the workspace remembers what the analysis currently consists of.

## bronze — what a source actually returned

### `bronze_artifacts`

| Column | Type | Meaning |
| --- | --- | --- |
| `artifact_id` | TEXT PK | SHA-256 of the payload. The id **is** the content |
| `source_id` | TEXT | Caller-owned source identity |
| `source_type` | TEXT | How it was obtained, e.g. `http-json` |
| `locator` | TEXT | Where it came from. Provenance, never re-opened as an instruction |
| `retrieved_at` | TIMESTAMPTZ | When the source returned it |
| `media_type` | TEXT | Declared content type |
| `byte_count` | BIGINT | Size, checked against the stored file |
| `payload_path` | TEXT | Path under `bronze/`, relative to the root |
| `recorded_at` | TIMESTAMPTZ | When we wrote it down |

**Rules.** Content addressing means two different payloads can never collide on one id, and recording identical bytes twice is a no-op — a re-fetch cannot rewrite history. Reads re-hash on the way out, so a file edited on disk is caught rather than served. Payloads are written with an exclusive create; nothing in bronze is ever overwritten.

## silver — numbers whose meaning is recorded

### `silver_series`

| Column | Type | Meaning |
| --- | --- | --- |
| `series_id` | TEXT PK | Stable identifier |
| `title` | TEXT | Human-readable name |
| `artifact_id` | TEXT FK | The bronze artifact it came from |
| `unit` | TEXT | `TRY`, `percent`, `index`, … |
| `scale` | TEXT | `one`, `thousand`, `million` |
| `frequency` | TEXT | `monthly`, `weekly`, `business_day`, … |
| `anchor` | TEXT | Weekday a weekly period ends on; null otherwise |
| `observation` | TEXT | `stock`, `flow`, `rate`, `index` |
| `cumulative` | TEXT | `none`, `since_inception`, `yearly_reset` |
| `aggregation` | TEXT | Permitted reduction across periods |
| `base_year` | INTEGER | Required for an index; null otherwise |

**Rules.** A series cannot be registered while its unit, scale, frequency, observation kind or accumulation behaviour is unknown. Re-registering the same series with *different* semantics is refused, because rows already stored were validated against the old declaration. Both rules exist because BDDK publishes in million TRY and FinTürk in thousand, and because one BDDK bulletin contains three different accumulation behaviours — see [BDDK_SOURCE](BDDK_SOURCE.md).

M3-06 uses an **internal** content-addressed batch manifest as the single `artifact_id`: canonical selector, inclusive month range, ordered raw hashes/request identities, parser/semantic versions, transformation policy and normalized-observation hash. Each raw response remains a separate bronze artifact; typed source → manifest → normalized-series lineage resolves all inputs. No new table or alternative storage engine is introduced. Whole-batch validation precedes a short series/observations/lineage transaction; failed materialization leaves silver unchanged, while immutable bronze may remain. Identical repeats are no-ops; changed bytes/range/contracts raise `VERSION_CONFLICT`, including range extensions, until version promotion is separately implemented. `materialized_monthly` verifies only the exact stored selector/window and counts nulls separately from successful materialization. This is offline-tested infrastructure, not real-source dataset acceptance. [Contract and limitations](BDDK_MONTHLY_METADATA.md#m3-06-bounded-monthly-ingestion-offline-validated).

`anchor` is a separate column rather than part of `frequency` because EVDS anchors 87 datagroups to Friday and one to Wednesday, and a single "weekly" bucket would silently misalign them ([EVDS_SOURCE](EVDS_SOURCE.md)).

### `silver_observations`

| Column | Type | Meaning |
| --- | --- | --- |
| `series_id` | TEXT FK | Its series |
| `period_start` | DATE | Inclusive |
| `period_end` | DATE | Inclusive; the key, because sources label by period end |
| `value` | DOUBLE | Null for a genuinely missing observation |

**Rules.** Every period is checked against the series' declared calendar before any of a batch is written, so a Friday-anchored series cannot accept a Thursday and a rejected batch leaves nothing behind. `(series_id, period_end)` is the primary key, so one period cannot hold two values; revisions are a separate, unresolved question. A null is a null: nothing in this schema fills a value forward.

## gold — several series on one spine

### `gold_cells`

| Column | Type | Meaning |
| --- | --- | --- |
| `table_id` | TEXT | Which analysis table |
| `column_name` | TEXT | Column within it |
| `period_start` | DATE | From the canonical spine |
| `period_end` | DATE | From the canonical spine |
| `value` | DOUBLE | Null where the series published nothing |
| `column_node_id` | TEXT | The lineage node for this column |

**Rules.** A column with no upstream lineage is refused at construction, so an untraceable column cannot reach a table. Absent and explicitly-missing periods are both null and neither is filled forward — a flat line drawn from a fill is indistinguishable from a real one. Every cell carries its column's lineage id, which is what makes any number on screen traceable.

## lineage — how every number got here

### `lineage_nodes`

| Column | Type | Meaning |
| --- | --- | --- |
| `node_id` | TEXT PK | SHA-256 over kind, label, sorted attributes and sorted upstream ids |
| `kind` | TEXT | `source_file`, `series`, `transform`, `column`, `metric`, `claim` |
| `label` | TEXT | What it is |
| `attributes` | TEXT | JSON. A transform stores its exact parameters here |

### `lineage_edges`

| Column | Type | Meaning |
| --- | --- | --- |
| `upstream_id` | TEXT | The node depended on |
| `downstream_id` | TEXT | The node that depends on it |
| `kind` | TEXT | `derives_from`, `aggregates`, `deflates_by`, `cites` |

**Rules.** Content addressing means the same derivation reached twice is one node, so a replayed pipeline converges on the same graph instead of duplicating it. An edge whose upstream does not exist is refused: an edge leading nowhere looks like provenance and is worse than none. A node that reaches no `source_file` has no provenance, and that is treated as a defect rather than a warning. [DEC-118](DECISIONS.md#dec-118--lineage-graph-as-the-provenance-substrate) records the model.

## workspace — what the analysis currently consists of

### `workspace_artifacts`

| Column | Type | Meaning |
| --- | --- | --- |
| `artifact_id` | TEXT PK | SHA-256 over kind, name, parameters and **ordered** input ids |
| `kind` | TEXT | `source`, `column`, `table`, `chart`, `value`, `assumption` |
| `name` | TEXT | The slot it was defined for |
| `parameters` | TEXT | JSON. The definition, not the result |
| `inputs` | TEXT | JSON array of artifact ids, order significant |
| `value_ref` | TEXT | Content address of the stored result in `workspace_results`, or null for a definition that holds no value |
| `lineage_node` | TEXT | Its node in the graph above |

### `workspace_bindings`

| Column | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | TEXT | Session or analysis, isolating concurrent work |
| `name` | TEXT | The slot |
| `artifact_id` | TEXT | What currently fills it |
| `stale` | BOOLEAN | An input changed and this has not been refreshed |
| `revision` | INTEGER | Increments each time the slot is rebound |

### `workspace_history`

| Column | Type | Meaning |
| --- | --- | --- |
| `workspace_id` | TEXT | Session |
| `name` | TEXT | Slot |
| `revision` | INTEGER | Which revision |
| `artifact_id` | TEXT | What the slot held then |

### `workspace_results`

| Column | Type | Meaning |
| --- | --- | --- |
| `result_digest` | TEXT PK | SHA-256 over the result's content, excluding its caller-chosen `result_id` |
| `result_id` | TEXT | The producer's handle for the same result |
| `payload` | TEXT | JSON of the `AnalyticalResult`: values, units, periods, sample counts, evidence |

**Rules.** Keyed by content, so storing the same result twice is one row and differing content can never overwrite what an earlier turn recorded. A read recomputes the digest and refuses a row that no longer hashes true, which is the only thing standing between a mutated row and an answer that cites it as evidence. Values are never edited in place; a changed analysis writes a new row and the old one stays readable, which is what keeps a superseded answer answerable.

**Rules.** Artifacts are immutable and addressed by their definition, so adding a column adds a node and leaves every existing artifact id unchanged — the mechanism behind "without disturbing the table". Changing an input marks exactly its transitive dependents stale and recomputes nothing, because whether they should be recomputed is the caller's decision and doing it silently is how a stale result hides. `refresh` refuses to run before a name's own inputs are refreshed, and a name that holds a value additionally requires a recomputer — rebinding a valued artifact without recomputing would clear the stale flag while leaving the old number in place, which is the exact failure this mechanism exists to prevent. Reading a stale name is refused rather than served with a caveat. Nothing is deleted, so what the analysis said before a change stays answerable. Input order is part of the id because a ratio of A to B is not the ratio of B to A. [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag) records the model.

## Conventions

Identifiers that address content — `artifact_id`, `node_id` — are lowercase SHA-256 hex. Timestamps are timezone-aware; a naive one is refused at the boundary. JSON columns are TEXT holding a sorted-key document, so two equal documents serialize identically and hash the same. `DOUBLE` is used for observations and `DECIMAL` where exactness is required at query time.

Foreign keys are declared for readability. DuckDB enforces them, but the application checks the same invariants first so that a violation produces a message naming the problem rather than a constraint error.

## What is not here yet

Catalog discovery ([M13](ROADMAP.md#m13)) currently uses the M13-08 versioned local reviewed JSON snapshot and M13-04 in-memory pure-Python BM25; no DuckDB FTS extension/index was installed. [DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime) separates catalog metadata from runtime queries over observations prepared in the lakehouse. A broader versioned BDDK/EVDS metadata snapshot remains future work; its storage expansion is not delivered or selected here. DEC-138 selects LanceDB; local vector persistence/exact search and optional hybrid composition are implemented. Actual Qwen embeddings are not wired into default prepared retrieval, and semantic-quality acceptance remains pending; DEC-115 is historical/superseded. Evaluation results ([M9](ROADMAP.md#m9)) and a turn log will add tables here. No second relational database is planned.

Revisions and source vintages ([M12-12](ROADMAP.md#m12)) are unresolved: `silver_observations` currently permits one value per period, and whether BDDK or EVDS restate a published figure has not been tested.
