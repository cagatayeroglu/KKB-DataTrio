# Database definition

The database definition the brief lists as a deliverable, alongside the architecture drawings, the documents and the repository.

One DuckDB file holds every table. There is no server: DuckDB runs inside the application process, so there is nothing to deploy, nothing listening on a port, and nothing to fail separately on demo day. [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse) records why.

Every table is created by `apply_schema` in [database.py](../src/kkb_agent/database.py), which is also the only list of what exists. The DDL itself lives beside the code that reads and writes each table, so a table's rules sit next to their enforcement; `TABLES` keeps a single answer to "what is in here", and [test_database.py](../tests/unit/test_database.py) fails if this document and the code disagree.

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

The series catalog and its search indexes ([M13](ROADMAP.md#m13)) will add DuckDB tables for series metadata and the alias dictionary, plus a DuckDB full-text index. Vectors live in LanceDB, outside this file, under [DEC-115](DECISIONS.md#dec-115--hybrid-series-retrieval-over-lancedb-and-duckdb-fts). Evaluation results ([M9](ROADMAP.md#m9)) and a turn log will add tables here. No second relational database is planned.

Revisions and source vintages ([M12-12](ROADMAP.md#m12)) are unresolved: `silver_observations` currently permits one value per period, and whether BDDK or EVDS restate a published figure has not been tested.
