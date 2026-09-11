# Architecture

This file owns technical structure and contracts. [ROADMAP](ROADMAP.md) owns delivery/status, [DECISIONS](DECISIONS.md) confirmed choices, [SECURITY](SECURITY.md) boundary controls, and [EVALUATION](EVALUATION.md) behavioral validation.

## Reading the design

- **CURRENTLY IMPLEMENTED** describes the source boundaries below; merged revisions, validation and remaining task acceptance are maintained only in [ROADMAP Current Project Status](ROADMAP.md#current-project-status).
- **TARGET / CONFIRMED** describes authorized behavior, not delivery.
- **PROPOSED / BENCHMARK-GATED** needs task review or measured benefit before adoption.
- **BLOCKED BY EXTERNAL ANSWER** names the organizer/platform dependency in OPEN_QUESTIONS.
- **DEFERRED** is outside the core slice unless a later explicit scope decision changes it.

The implemented spine includes bounded file admission, CSV/XLSX loading and direct-GET safe fetch, DuckDB/Parquet storage and financial semantics, typed results, an offline Kloudeks boundary, validated planning/execution, content-addressed workspace values and multi-result answer gating. Five brief tools exist: `lakehouse`, `change_detection` (comparison), `anomaly`, `causality` (association, lag and Granger precedence) and `web_url`, which reads a CSV/XLSX table or a PDF's text and ruled tables at an address the user wrote. Synthetic tests compose an end-to-end answer with a scripted model. Live source adapters/provider, CSV/XLSX profiling, catalog retrieval, breakpoint detection, complete proof/replay, `web_search`, `web_url`'s HTML/image/scanned-PDF extraction and redirects, evaluation runner, UI and deployment remain incomplete. Day 0 drafts remain outside the shared runtime.

## Goals and non-goals

CONFIRMED goals:

- Handle unfamiliar questions and new-but-supported sources through common contracts.
- Use the LLM for interpretation and planning; use deterministic tools for calculations.
- Make assumptions, transformations, failures, and evidence inspectable.
- Preserve explicit multi-turn analysis state and invalidate dependent results correctly.
- Fail safely when data meaning or execution authority is insufficient.
- Keep the inner loop fast and the demonstration reliable under constrained model access.

Non-goals for this window: arbitrary generated-code execution, a general autonomous web crawler, a hosted warehouse platform, distributed agent infrastructure, enterprise tenancy/security systems, or a training pipeline.

The stack is selected in DECISIONS and is not re-argued here: DuckDB with Parquet and Pandas (DEC-112), a custom bounded loop (DEC-113), initial hybrid retrieval with benchmark-gated extensions (DEC-130; DEC-127/115 superseded), an artifact DAG in DuckDB (DEC-117), FastAPI with SSE behind Next.js (DEC-123), and the excluded-technology list (DEC-124). Router fine-tuning and multi-agent topology remain out of scope.

## Layer map

```text
  6. Trust layer          lineage graph + verifier            -> components 10, 12
  5. Agent core           planner / router / executor         -> components 1, 3, 4
  4. Tool layer           the six brief-named tools           -> components 4, 9
  3. Semantic layer       catalog, hybrid baseline, aliases  -> component 13
  2. Lakehouse            DuckDB + Parquet, bronze/silver/gold -> component 12
  1. Ingest               BDDK bulletins, EVDS API, uploads   -> components 5, 6, 7
```

Target packages follow DEC-125 (only existing source links below imply implementation): `src/kkb_agent/{app,agent,tools,ingest,transform,catalog,lineage,llm,eval}/`, with the web client in `web/`.

## End-to-end request lifecycle

CONFIRMED responsibility flow. The coordinator is a custom bounded state machine under DEC-113; no orchestration framework mediates these steps.

```text
User request + explicit workspace ID
  |
  v
Request intake / workspace lookup
  | selects allowed capabilities; separates user intent from source content
  v
Intent + relevant source metadata + tool schemas
  |
  v
LLMProvider (Kloudeks) -> candidate AnalyticalPlan
  |
  v
Plan validation
  | schema -> registry/arguments -> references/dependencies -> capability/budgets
  +-- invalid -> bounded repair or clarification/failure
  |
  v
Executor -> registered deterministic tool
  |              |
  |              +-> source adapters -> safe fetch / file guards -> parser/profile
  |              +-> normalization -> analytics -> structured result
  v
Staged workspace changes + source/transformation/run evidence
  |
  v
Verifier -> accepted claims / rejected claims / explicit limitations
  |
  v
Commit valid state transition -> answer/table/chart/evidence presentation
  |
  v
Next turn reuses explicit state; changed inputs invalidate dependents
```

PROPOSED execution sequence:

1. Resolve the workspace and relevant prior selections; identify an ambiguous request before expensive retrieval.
2. Discover/inspect source candidates using bounded metadata. A model may propose a mapping; deterministic rules and source metadata determine whether it is usable.
3. Obtain a candidate typed plan, constrained to registered capabilities and known references.
4. Validate structure and per-tool inputs before dispatch. Do not execute a plan simply because it deserializes.
5. Load bounded data and record source identity/vintage/retrieval metadata; profile uncertainty rather than guessing.
6. Apply explicit normalization and analytical operations, retaining exact input/output references.
7. Verify material outputs and lineage. Preserve failed-run metadata without presenting failed results as verified.
8. Assemble only supported claims; render values from tool outputs. Ask for missing semantics or explain abstention where necessary.
9. Publish a coherent workspace update, including assumptions and invalidations, so follow-ups have a reproducible base.

An authorized supported external source may be added during the same lifecycle. It still passes the same guards as an initial upload. Tool/model outputs do not create new authority.

## Data flow and trust boundaries

```text
UNTRUSTED                          SYSTEM-OWNED BOUNDARIES
URL / upload / source metadata --> fetch/file guards --> bounded parser
                                                        |
                                                        v
                                             raw data reference + profile
                                                        |
model schema-mapping suggestion -----------------------> semantic validation
                                                        |
                                                        v
                                             DataContract + known unknowns
                                                        |
                                                        v
                                             deterministic transformations
                                                        |
                                                        v
                                             analytical result + lineage
                                                        |
model narrative proposal -----------------------------> verifier/claim gate
                                                        |
                                                        v
                                             displayed supported answer
```

Preserve original observations independently of normalized/derived references. Never overwrite raw values to make a transformation convenient. DuckDB/Parquet storage is confirmed by DEC-112/117. Content-addressed typed result values are implemented in the workspace; immutable input snapshots and full replay remain target work, distinct from result digests and mutable gold cells.

## Component contracts

Each boundary below describes responsibility, inputs, outputs, prohibited behavior, failures, and validation. Runtime controls are specified in SECURITY rather than duplicated here as implementation status.

### 1. Request coordinator and intake — CONFIRMED mechanism (DEC-113)

- Responsibility: Resolve the request/workspace, orchestrate the validated lifecycle, apply budgets, and decide whether clarification is needed.
- Input: User request, workspace ID, available capabilities, configured request limits.
- Output: A bounded execution outcome and accepted workspace transition, or clarification/failure.
- Must NOT: Treat embedded source text as a user command, create tool authority from a model response, or keep retrying indefinitely.
- Likely failures: Unknown workspace, ambiguous intent, stale references, deadline exhaustion, incompatible follow-up.
- Validation expectations: Tests for no-work clarification, failed-turn state preservation, cancellation/deadline propagation, and follow-up invalidation.

CURRENTLY IMPLEMENTED: [Session](../src/kkb_agent/agent/loop.py) plans and executes through the registry. `Session.answer` additionally synthesizes computed results and calls the verifier gate; it can record a result in a caller-supplied Workspace and use its current named values across turns. Step/repair/retry counts are bounded. Automatic workspace loading, planner-driven recomputation, total request deadlines/cancellation and publishing state only after verification remain TARGET. A separate cheaper router call remains PROPOSED pending model/latency evidence.

### 2. LLMProvider / Kloudeks boundary — CONFIRMED interface direction

- Responsibility: Isolate model-specific structured generation, plan generation, and concise synthesis.
- Input: System-owned prompts, bounded selected metadata/workspace summary, and expected response schema.
- Output: Validated model output or categorized provider failure; synthesis remains subject to claim verification.
- Must NOT: Compute authoritative financial numbers, execute tools directly, accept a request-supplied endpoint, leak credentials, or silently call another provider.
- Likely failures: Missing configuration, unavailable model, timeout/rate limit, context overflow, refusal, malformed JSON/schema mismatch.
- Validation expectations: Offline provider doubles, strict response validation, all error branches, bounded retries, redaction tests, and separately recorded permitted live smoke.

CURRENTLY IMPLEMENTED: [provider.py](../src/kkb_agent/llm/provider.py), [config.py](../src/kkb_agent/llm/config.py), [structured.py](../src/kkb_agent/llm/structured.py) and [doubles.py](../src/kkb_agent/llm/doubles.py) provide the DEC-122 protocol, environment-driven configuration, local JSON/schema validation/repair and a scripted non-networking provider. [kloudeks.py](../src/kkb_agent/llm/kloudeks.py) (M4-07) is the one transport: `httpx` against DEC-129's chat and embedding endpoints, refusing any base URL but DEC-129's host, fixed paths and configured models only, redirects and ambient proxy/environment settings off, responses read under a byte cap and deadline, and errors reduced to a status category without key, prompt or body. Schema repair is the same loop the double runs; transport retries are M4-10's. It is tested offline against an in-process transport, one authorized live smoke ([smoke.py](../src/kkb_agent/llm/smoke.py), M4-12) passed for chat and embedding, and one live end-to-end question on synthetic data ([live_check.py](../src/kkb_agent/live_check.py), M4-15) went through planning, a tool, drafting and the gate to an ACCEPTED answer. That run showed the served model rejects two system messages, so the transport joins the leading system turns into one. Capability flags are configured expectations, not live-probed organizer guarantees. The old Day 0 protocol is not delivered.

DEC-122's three-method surface is:

```python
complete(messages, *, model: str, schema: type[BaseModel] | None = None)
embed(texts: list[str], *, kind: Literal["query", "passage"])
vision(image_bytes: bytes, prompt: str)
```

Model identifier, base URL and whether structured output exists come from environment configuration, never from source constants. When the platform offers no structured-output mode, the provider validates against the schema, repairs with `json-repair`, and retries at most twice while feeding the validation error back to the model. The `kind` argument on `embed` preserves query/passage intent; the confirmed Qwen model's prefix convention remains Q-K-05. Do not assume an E5 convention applies.

Model roles are assigned by measurement, not parameter count. A proposed live measurement is a twenty-case tool-selection smoke test — Turkish question in, expected tool and arguments out — against an eligible text model, scoring correct-tool rate, argument-schema validity, JSON malformation rate and latency. Use locally validated text responses unless native function/tool calling is separately confirmed; the compatible endpoint alone does not establish that feature. The router base is chosen from that score. Role/model splits and exact call budgets remain PROPOSED pending those measurements. Models may propose or summarize; deterministic code verifies material calculations. Reranking is optional under DEC-130. Vision, OCR and embedding availability are officially confirmed in [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy); live integration remains unimplemented.

CONFIRMED: [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the exact host/base URL, MIA-key authentication, model IDs, endpoints and image-count limits. The `openai` SDK is allowed exclusively as the Kloudeks-compatible client; third-party hosted LLM destinations and fallback remain banned. The source still has no live transport, and its blanket SDK-name test needs a later implementation-policy correction (ROADMAP M4). The primary-guide record confirms local key provisioning; live authentication remains unexercised. Still unknown: live access, context/output capacity, native tool calling/guaranteed JSON, quotas/concurrency/timeout behavior, embedding dimension/prefix and dedicated reranker availability (narrowed Q-K-01..05). Local response validation remains mandatory.

### 3. Planner and plan validator — CONFIRMED separation; partial implementation

- Responsibility: Translate intent into typed registered-tool steps and reject unsafe/invalid plans before execution.
- Input: Request, allowed tool schemas, source candidates, current workspace references/assumptions.
- Output: A validated executable plan, a bounded repair request, or an explicit unsupported/clarification outcome.
- Must NOT: Dispatch arbitrary names, code, imports, SQL, URLs, or paths from free-form text; silently resolve unknown data semantics.
- Likely failures: Unknown tool, extra/invalid argument, bad dependency, unavailable input, too many steps, repeated invalid plan.
- Validation expectations: Positive plan fixtures plus negative names/arguments/dependency/reference/capability cases; verify rejection occurs before any tool side effect.

CURRENTLY IMPLEMENTED: [AnalyticalPlan](../src/kkb_agent/agent/plan.py) contains `question` and `steps`; each step has `step_id`, `tool`, `arguments` and `depends_on`. [validate_plan](../src/kkb_agent/agent/executor.py) checks registered names and argument schemas, duplicate/self/unknown dependencies, cycles and step limits, then topologically orders the steps. It does not resolve workspace/data-reference ownership, require declared output types or enforce financial semantics. Those remain target checks; a parsed plan is not a proof of them.

### 4. Tool registry and executor — CONFIRMED tool set (DEC-121)

- Responsibility: Map approved names to deterministic implementations, validate argument schemas, apply limits, and record structured outcomes.
- Input: Validated plan steps, typed arguments, permitted workspace references, configured budgets.
- Output: ToolResult plus referenced data/result/evidence and proposed state changes.
- Must NOT: Use `eval`/`exec`, dynamic imports from input, unrestricted shell, or direct model SQL; treat an arbitrary filesystem path as an authorized data reference.
- Likely failures: Invalid schema, tool timeout, empty data, numerical precondition failure, unknown semantics, resource exhaustion.
- Validation expectations: Registry uniqueness, validation-before-dispatch, failure categorization, retry limits, stale-reference rejection, and valid/failed workspace effects.

CURRENTLY IMPLEMENTED: [ToolSpec / ToolRegistry](../src/kkb_agent/agent/registry.py) own names, Pydantic argument schemas and callable dispatch. [ToolResult](../src/kkb_agent/agent/executor.py) carries `status`, `step_id`, `tool`, an untyped `output`, error category, recoverability, warnings and optional lineage `evidence`. Statuses are success/failure/partial/not_run. Failure requires a category and success forbids one. Five tools have implementations: `lakehouse`, `change_detection`, `anomaly`, `causality` (association/lag) and `web_url`, whose `output` is a `WebUrlOutput` — a loaded table or PDF document, or a fixed reason — rather than an `AnalyticalResult`. The lakehouse `output` is a `LakehouseOutput` pairing an M6-01 `AnalyticalResult` with the rows behind it; `output` itself stays `object`, so the typing is the tool's discipline rather than the executor's. A successful call that established no measurement stays SUCCESS and reports the reason as a warning — the query ran, and conflating that with a failure would hide which of the two happened. Output-reference/ownership validation remains target work. `Session.answer` integrates workspace values and verification, while lower-level execution alone is not an answer gate.

### 5. Source discovery and adapters — CONFIRMED abstraction

- Responsibility: Discover/inspect/load/profile a source through the common data boundary and return source provenance.
- Input: Bounded search/selection arguments, allowed source capabilities, approved data/source references.
- Output: Candidate IDs, DataContract, loaded data reference, profile, SourceRef.
- Must NOT: Make the core depend on BDDK/EVDS naming, invent missing units, bypass safe fetch/file guards, or execute document instructions.
- Likely failures: Unknown/ambiguous series, schema drift, unavailable source, revisions, empty range, unexpected content type.
- Validation expectations: Synthetic discovery/load fixtures, wrong-near-match selection tests, unfamiliar schemas, source outage, and stable provenance.

TARGET operations are discovery, inspection, loading, profiling and provenance. No SourceAdapter protocol or runtime BDDK/EVDS adapter is delivered. [INGESTION_PROFILE](INGESTION_PROFILE.md) specifies observable results; an executable shared adapter/selection interface remains implementation work. Adapters unable to discover (for example, a single uploaded file) should report unsupported capability explicitly rather than invent source candidates.

### 6. Safe ingestion, extraction, and profiling — partial implementation; confirmed boundary

- Responsibility: Validate and bound content, extract observations, and describe data quality without silently deciding financial meaning.
- Input: Guarded upload/fetched bytes, explicit selection such as sheet/table/page, parser limits.
- Output: Original-data reference, profile, source fragment references, extraction warnings, candidate schema mappings.
- Must NOT: Execute formulas/macros/scripts, fetch embedded resources without authorization, write to supplied paths, or convert OCR uncertainty into verified numbers.
- Likely failures: Empty/corrupt/oversized file, ambiguous delimiter/date, archive expansion, multi-sheet ambiguity, scanned PDF, missing table.
- Validation expectations: Exact row/type expectations; empty/malformed/oversized/content-mismatch negatives; sheet/page lineage; hostile-text cases.

Spreadsheet reading is split by trust boundary, not by file type. The TARGET operator-ingestion path for recorded BDDK/EVDS sources will read with Pandas and calamine under DEC-114. A file named by a user, a model or a prompt-supplied URL goes through the M1-10 bounded loader under DEC-111, with admission checks, streamed package validation, resource budgets and a terminated worker. The rule is the provenance of the request to read, never the extension. Both target paths must retain original bytes/hashes and enforce SEC-URL/SEC-FILE limits; a familiar source is not trusted content. The operator path is not yet implemented.

Generic path: identify supported format -> enforce guards -> parse bounded content -> profile -> propose mapping -> confirm required semantics. Unknown source but supported format uses this path. Unknown format returns an unsupported-format outcome; it does not trigger code generation or unbounded scraping. CURRENTLY IMPLEMENTED: [admission](../src/kkb_agent/ingestion_policy.py), [sheet selection](../src/kkb_agent/xlsx_sheets.py), the [bounded XLSX loader](../src/kkb_agent/xlsx_loader.py) and the [bounded CSV loader](../src/kkb_agent/csv_loader.py) (M1-06: explicit delimiter, strict UTF-8, no guessed dates, units or frequency). The [bounded PDF loader](../src/kkb_agent/pdf_loader.py) (M7-09/M7-10) returns page text, a text-layer flag and ruled tables with page coordinates and literal cells, and refuses encrypted, malformed and text-less PDFs with fixed codes. Date/numeric profiling remains target work; HTML follows. Vision/OCR capability is confirmed by DEC-129, but document/OCR ingestion is not implemented. OCR requires bounded PDF-to-page-image rendering where needed, the organizer's exact prompt/`extra_body`, and handling of untrusted layout-tag output; availability does not bypass file limits or prove numeric extraction.

CURRENTLY IMPLEMENTED: [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py) supplies bounded direct HTTP/HTTPS GET, validated DNS-to-socket binding, hostname-verified TLS, byte/decompression/time budgets and structured rejections (M7-01/02/03/05/06). Every 3xx is rejected; redirect following, POST/form requests and source-specific trust configuration remain incomplete. A fetched CSV/XLSX/PDF passes the same admission checks and loaders as an upload through [load_fetched](../src/kkb_agent/ingest/fetched.py) (M7-08/M7-09), chosen by the validated response media type, never the URL; the [`web_url`](../src/kkb_agent/tools/web_url.py) tool (M7-17) reaches it only for an address written in the user's question. HTML and image content has no parser route yet. Live exposure still needs source/network permission.

### 7. DataContract and normalization — CONFIRMED semantic boundary

- Responsibility: Represent known/unknown meaning and permit only semantically valid explicit transformations.
- Input: Loaded data, source metadata, confirmed/user-supplied assumptions with provenance, requested transformation.
- Output: Validated derived data reference, updated semantic description, transformation record, or unresolved-semantics outcome.
- Must NOT: Infer stock/flow solely from frequency, aggregate without policy, silently interpolate/drop/scale, or conflate ingestion time with observation vintage.
- Likely failures: Unknown unit/reset rule, incompatible periods, duplicate/revised observations, missing baseline, different index bases.
- Validation expectations: Hand-calculated oracles, unit/frequency/cumulative negative cases, recorded parameters, and preserved originals.

CURRENTLY IMPLEMENTED: [DataContract](../src/kkb_agent/core/models.py) holds contract/source/title, optional unit/time metadata, frequency, stock/flow, nullable cumulative/reset, source period, transformations and semantic warnings. It has no confidence field. [SeriesSemantics](../src/kkb_agent/lakehouse/semantics.py) adds scale, weekly anchor, cumulative kind and aggregation; silver promotion rejects missing required meaning, while unknown aggregation remains representable until an operation requires it. These two vocabularies need explicit mapping, not implicit coercion.

Period/cumulative functions and weekly-to-monthly alignment are implemented. Currency/rate conversions, source-vintage conflict handling, index rebasing/deflation and a unified finance semantic guard remain target work. Do not confuse metadata enums with implemented transformations.

Operation prerequisites:

| Operation | Required meaning | Insufficient meaning outcome |
| --- | --- | --- |
| Frequency aggregation | Source/target periods, stock/flow, aggregation and missing-period policy | Clarify or reject transformation |
| Unit/scale conversion | Known source and target units/scales | Reject incompatible/unknown conversion |
| Cumulative-to-flow | Reset rule, ordering, prior baseline where needed | Keep original cumulative values; explain missing prerequisite |
| Deflation | Compatible nominal unit, price index, index/reference base and dates | Ask for appropriate index/base or abstain |
| Lag/association | Explicit alignment, sample count, missing policy, lag convention | Reject invalid statistic or report limitation |

### 8. AnalysisWorkspace — CONFIRMED explicit-state direction

- Responsibility: Retain analysis inputs, derived references, assumptions, transformations, evidence, and results across turns.
- Input: Workspace creation/lookup and validated staged changes from successful operations.
- Output: Coherent next-state snapshot and references for subsequent plans/verifications.
- Must NOT: Depend only on chat history, silently reuse stale results, mix workspaces, or discard prior lineage after an assumption correction.
- Likely failures: Dangling reference, partial write, stale derived data, accidental mutation of prior state, unavailable persisted data.
- Validation expectations: Round-trip state, add-series/date-range follow-ups, failed-turn preservation, assumption correction, and dependent-result invalidation.

CURRENTLY IMPLEMENTED: [Workspace](../src/kkb_agent/agent/workspace.py) persists artifact definitions, workspace-scoped name bindings, revision history and typed result values in DuckDB. Identity includes a recorded value reference; changed bindings invalidate dependents. The result integration below supersedes the original definition-only behavior from PR #29.

CURRENTLY IMPLEMENTED (M5-10/11/12): the workspace holds actual typed results, not only definitions. `workspace_results` stores each `AnalyticalResult` keyed by its own `digest()`, so identical content is one row, differing content never overwrites an earlier turn's, and a read that no longer hashes true is refused rather than served. **`resolve` and `value_of` refuse a stale read** — returning one and hoping the caller checks `is_stale` is how a superseded number reaches an answer — with `allow_stale=True` reserved for inspection. **`refresh` requires a recomputer** for any name holding a value, because rebinding alone would clear the stale flag while leaving the old figure in place. `artifact_id` includes a recorded value's address so a changed result cannot masquerade as an unchanged definition. `Session.answer` records a turn's result under a name, so the next turn builds on it.

CURRENTLY IMPLEMENTED: M8-17 lets one answer cite several current named results from `Workspace.values()`, excluding stale columns. Still TARGET under DEC-117/128: planner-driven recomputation (the recomputer is caller-supplied) and publishing state transitions only after verification. No claim of complete replay or end-to-end workspace isolation follows from names being scoped by workspace ID.

Never regenerate the whole table per turn. That is how a value silently changes between two answers the user believes are the same table. Cross-process durability and reset semantics remain Q-INFRA-02 and Q-DEMO-02; do not advertise restart durability without implementation and tests.

### 9. Deterministic analytics and presentation data — CONFIRMED responsibility

- Responsibility: Compute supported changes, comparisons, anomalies, association/lag, and justified statistical tests; emit chart/table data from computed results.
- Input: Validated data references, semantic prerequisites, explicit parameters and periods.
- Output: Material values, units, sample counts, warnings/limitations, and reproducible run/evidence references.
- Must NOT: Treat model prose as numbers, hide denominator/zero handling, select lags without recording policy, or claim causality from correlation alone.
- Likely failures: Too few observations, constant series, missing baseline, non-stationarity, incompatible real/nominal data, undefined statistic.
- Validation expectations: Independent numerical oracles, per-case tolerances, prerequisite failures, lag-direction cases, and causality/abstention checks.

Prefer small tools over one general “analyze everything” tool. DuckDB/Pandas and the DEC-120 lagged-correlation/Granger direction are CONFIRMED. Exact anomaly parameters, window/lag policies and minimum samples need task-level review and tests. Research-grade inference is deferred under DEC-128; defensible abstention remains required.

CURRENTLY IMPLEMENTED (M6-02/03/04): the [analytics](../src/kkb_agent/analytics/change.py) package computes `absolute_change`, `relative_change` and `compare_periods` as typed results, with the declared semantics deciding what a change means rather than the numbers. A stock's difference is the change in an outstanding balance and says so; a cumulative series abstains until converted to flow; unresolved semantics abstain outright; a rate or index changes in **points**, carried in the value's unit so the verifier's scale check can see it. The denominator policy is a refusal rather than a formula — a zero base has no proportion and a negative base inverts the sign, so both return UNDEFINED with a reason instead of a number nobody should quote. Endpoint selection is exact, and a null endpoint is INSUFFICIENT rather than a forward fill. [analytics/association.py](../src/kkb_agent/analytics/association.py) (M6-07..10) adds association and lag, exposed as the brief-named [`causality`](../src/kkb_agent/tools/causality.py) tool. It pairs two series only on periods both published and **refuses a frequency mismatch rather than resampling**, because choosing a resampling is a per-series semantic decision. Pearson and Spearman are reported together, and a material gap between them says the relationship is not linear. Lag is bounded and its **sign convention is stated in the label, the parameters and a warning** — reading it backwards inverts the finding — with per-offset sample counts and an explicit note that the strongest of N offsets is inflated by the search. When both series trend strongly the result says two trending series correlate whatever they measure and names differencing as the check, without silently differencing. Under DEC-120 every result carries "association, not causation" and related limits, which the M6-01 contract enforces by refusing to construct a relational result without them. [analytics/granger.py](../src/kkb_agent/analytics/granger.py) (M6-11) adds the tool's `granger` operation through `statsmodels`: at each order p up to the window, in both directions, an F-test of whether p lags of one series improve on a constant and p lags of the other. Regression rows use the same calendar positions as the lag search, so no row reaches across a missing period, and each order runs only with three rows per coefficient and never fewer than the pair floor. Every order's F, p-value and row count are reported; the result counts the tests searched, flags trending levels, and reads a small p-value as predictive precedence, never mechanism, with DEC-120's common-driver, structural-break and small-sample limits attached. No stationarity, cointegration or break test is implemented.

[analytics/anomaly.py](../src/kkb_agent/analytics/anomaly.py) (M6-05/06) adds the anomaly baseline, exposed as the brief-named [`anomaly`](../src/kkb_agent/tools/anomaly.py) tool. It examines period-over-period **changes** rather than levels — a steadily rising series would otherwise flag its own present — and scores them by median absolute deviation, which the outlier cannot inflate the way it inflates a standard deviation. MAD collapses to exactly zero when over half the changes are identical, so the Iglewicz–Hoaglin mean-absolute-deviation fallback covers that case; only a series whose every change is identical is genuinely UNDEFINED. The threshold and minimum sample are **unmeasured defaults, recorded in every result and not exposed to the planner**, because a model that can move a threshold will. The count of anomalies is always reported, including zero, so the gate can bind it.

Exposed to the planner as the brief-named [`change_detection`](../src/kkb_agent/tools/change_detection.py) tool (M6-22), which reads the declared semantics and observations from the lakehouse, records lineage for a computed comparison and none for a refused one, and names its `operation` so breakpoint detection can join the same schema without being implied by the tool's name before it exists. No seventh tool was added; the registry still refuses any name outside the six.

CURRENTLY IMPLEMENTED: [core/results.py](../src/kkb_agent/core/results.py) defines what a tool returns — `AnalyticalResult` with typed `ResultValue`s, explicit `Period`s, `SampleCounts`, warnings, limitations, `unresolved_semantics` and `ResultEvidence` references, under `ResultKind`/`ResultStatus`. Three refusals are structural: a value states its unit or the result declares what is unresolved (`DIMENSIONLESS` is not the same as unknown); a non-COMPUTED result carries no values and names what stopped it, keeping INSUFFICIENT, UNDEFINED and ABSTAINED distinct; and an association, lag or causality result must state limitations, which puts DEC-120 in the type system. `digest()` hashes content excluding the caller's `result_id`, which is the identity M5 needs to reject a stale read and M8 needs to detect an altered result. `lakehouse` is the first producer (M6-21). [tools/_projection.py](../src/kkb_agent/tools/_projection.py) maps a validated query onto that contract by **reading the semantics the lakehouse already stores** — `silver_series` records unit, scale, frequency, anchor and observation kind as exact enum values — and declaring every semantic the query did not select rather than inferring one. Two refusals live here rather than in the SQL gates, which were never meant to catch them: a query reading **no lakehouse table** abstains, so `SELECT 42 AS value` cannot mint a figure; and a query with no `value` column abstains as a listing. Since M6-23, reading an allowed table is not provenance on its own: [_projection_provenance.py](../src/kkb_agent/tools/_projection_provenance.py) admits only direct `silver_observations`/`silver_series` columns joined on `series_id`, then rechecks every returned row against its stored identity, value and semantics through fixed SQL, so literal, computed, aggregated or otherwise derived measurements abstain instead of becoming COMPUTED. The tool returns [LakehouseOutput](../src/kkb_agent/tools/lakehouse.py), keeping the verifiable `result` and the presentation `table` apart so a rendering convenience cannot become an analytical claim.

The four analytical tools emit typed analytical results, consumed by the result verifier and answer gate. `web_url` returns a loaded table or document rather than a result, so the answer path does not treat it as one; `web_search` remains absent. The verifier resolves preserved table/lineage references on this path; complete source/run/transformation resolution remains M8-04. A matching digest is not a proof of correctness.

### 10. Evidence ledger and verifier — CONFIRMED direction

- Responsibility: Resolve lineage and check every material claim against source inputs, deterministic transformations/results, and validation rules.
- Input: Candidate claims, tool runs, data references, SourceRefs, TransformationRecords, expected semantic constraints.
- Output: Passed/failed/not-run validation, accepted claim set, limitations, and inspectable evidence references.
- Must NOT: Mark an unverified claim passed because a citation exists, let the model self-certify numbers, or ignore contradictory/stale inputs.
- Likely failures: Missing/orphan references, altered output, incomplete periods, incompatible units, contradictory sources, unsupported inference.
- Validation expectations: Recompute representative material results; inject wrong values/missing lineage; verify failed/not-run claims cannot appear as verified.

Present SourceRef holds identity/type/locator and optional retrieval time/hash. Present TransformationRecord holds operation/parameters/input refs/output ref. Present EvidenceRecord holds claim, sources, optional run, transformations, period/columns, validation, limitations. Validation defaults to NOT_RUN. These records do not enforce a complete evidence chain; the ledger service and claim rules are still pending.

CURRENTLY IMPLEMENTED: [Lineage](../src/kkb_agent/lakehouse/lineage.py) stores typed hash-addressed nodes/edges in DuckDB and traverses ancestors directly (no networkx consumer). Gold requires a source ancestor, but this is not proof that all inputs/values/semantics are complete. [lakehouse query records](../src/kkb_agent/tools/lakehouse.py) are optional and table-level: statement hash, purpose, table/column names, counts and truncation. They do not retain replayable SQL, immutable result cells or a complete input/run chain. Since M6-21 the same query also produces a typed `AnalyticalResult` whose `input_refs` name the tables read; since M6-23 only a COMPUTED result records the query and carries that record as its `evidence.lineage_node`, so a claim has a period, unit and run identity to bind to and a refused projection leaves no provenance behind.

M8-06/07 adds [`verify_result`](../src/kkb_agent/agent/verifier.py) beside the original `verify`. It binds each written number to a value of **one result** rather than to any stored value of similar magnitude, with no store-wide fallback; rejects a figure whose written scale word contradicts the value's recorded `Scale` (the BDDK/FinTürk 1000x error, which survives every value-only check); rejects a figure whose sentence attributes it to years outside its period; resolves `lineage_node` and every `input_refs` entry against the database, so a dangling reference cannot render as provenance; and rechecks each value against the store through fixed SQL keyed on series and period, independent of the statement the model wrote. That recheck is a second *read*, not an independent derivation, and the verdict says so.

M8-10 makes it a gate rather than a report. [`gate_answer`](../src/kkb_agent/agent/verifier.py) withholds any sentence carrying a number the verifier could not support, qualifies what survives with the verdict's limitations, and returns an **abstention** when nothing is left — never a shortened claim, which reads as a complete answer. A result that failed as a whole takes the entire draft with it, prose included, because that prose describes the same broken result. Every omission is recorded with its reasons. [`Session.answer`](../src/kkb_agent/agent/loop.py) composes the slice, and `render_result` gives the writer computed values with their units and periods but **not the rows**, so there is nothing to aggregate and nothing for an injected instruction to travel in.

M8-17 makes the gate work over **several named results** — `verify_claims` and `gate_answer` accept one result, a sequence, or a workspace-name mapping, and `Session.answer` gates over `Workspace.values()` merged with the current turn's. That is what makes the reference scenario's table answerable: a sentence citing housing credit beside its rate binds both numbers instead of withholding itself. Disqualification is **per result**: a broken column faults exactly the numbers resting on it, reported under its own name, while a sound column still reports; only when every result is disqualified does the prose fall too. Stale columns never enter, because `values()` excludes them.

M8-18 binds a figure's explicit qualifiers as well as its magnitude. [claim_qualifiers.py](../src/kkb_agent/agent/claim_qualifiers.py) checks explicit workspace/result/value identifiers, Turkish/English month names, calendar years/ISO dates and attached unit/currency/scale words against the candidate value; a number that two supported values match fails closed as ambiguous instead of binding to the first; unsupported causal wording is withheld even in a sentence without a number; and an amount-qualified year-like figure loses the calendar exemption. The vocabulary is bounded and deterministic — it does not infer series aliases or read general prose. Still target work: transformation prerequisites are not validated, and no claim is recomputed from raw inputs. `verify` remains reachable for callers holding no typed result.

[verify](../src/kkb_agent/agent/verifier.py) extracts numbers and finds a numerically close gold cell or silver observation; caller-allowed context values and years can also pass. Gold matching returns the first numeric match, without tying it to the requested period/unit/series/workspace/run. A verdict may reject unbound numbers, but acceptance is not independent recomputation, semantic correctness or sufficient claim-level proof. Ambiguous numeric locale interpretations also need explicit policy. This legacy `verify` API remains callable, but `Session.answer` uses the stronger result-bound gate described above.

TARGET / CONFIRMED: DEC-119 requires a gate, strengthened by DEC-128's proof chain. Before an answer reaches the user:

1. Every number in the response text must resolve to a cell in an artifact. If one does not, the answer is rejected rather than annotated.
2. Units and scales are checked against the contract, not inferred from magnitude.
3. Each headline metric is recomputed on a second independent path — SQL against Pandas — and the two results compared.
4. A headline claim is cross-checked against a searched source where one is available, and the source is shown.
5. Model-extracted content from a document or image is never written straight into a table. It must satisfy a schema and a total or consistency check first; failing that, the system states that it could not extract reliable data from that source.

Abstention is a first-class outcome. A hallucinated number that enters lineage silently is worse than no answer, because the trust layer then certifies it.

```text
claim ID -> tool run -> output reference
                 |         |
                 |         +-> exact value/period/unit displayed
                 v
      input refs -> transformation chain -> original source fragment/vintage
                 |
                 v
      verifier result + assumptions/limitations
```

### 11. Answer/UI adapter — CONFIRMED stack (DEC-123)

- Responsibility: Present supported claims, tables/charts, assumptions, progress, and evidence; make clarification and failure actionable.
- Input: Verified claim set, structured execution state, safe source/evidence summaries.
- Output: User-visible answer and explicit follow-up request/workspace operation.
- Must NOT: Recalculate values with the LLM, hide partial/failed verification, expose secrets/internal stack traces, or relabel cached data as live.
- Likely failures: Missing evidence link, stale display after a follow-up, confusing partial result, unsuitable demo environment.
- Validation expectations: Independent teammate runs happy path, clarification, outage, and multi-turn correction; displayed values match tool outputs.

The TARGET FastAPI application will stream plan and tool progress over server-sent events, so a multi-step analysis is legible while it runs. The client is Next.js with Tailwind and shadcn/ui, TanStack Table for the analysis table, `react-plotly.js` for charts, with a concise claim/evidence view first. Graph-heavy React Flow presentation is DEFERRED under DEC-128. The logical UI contract above still does not depend on that stack: Streamlit remains the recorded fallback, and the front end must not gate backend acceptance.

### 12. Lakehouse and medallion layout — CONFIRMED storage (DEC-112)

- Responsibility: Hold retrieved sources, normalized series and analysis-ready facts with the semantics each layer is allowed to assert.
- Input: Retrieved bytes with hash and retrieval time; parsed tables; confirmed unit/frequency/semantic metadata.
- Output: Parquet datasets queryable through DuckDB, plus the series metadata the catalog indexes.
- Must NOT: Promote a value to `silver` without recorded unit, frequency and stock/flow semantics; overwrite a vintage; treat a cumulative series as a flow.
- Likely failures: Bulletin format drift between periods, a cumulative series that resets in January, mixed thousand/million scales, weeks crossing month boundaries, revised historical values.
- Validation expectations: Hand-calculated fixtures for every cumulative and aggregation rule; identity and round-trip cases; explicit negatives for unknown unit, unknown frequency and unknown reset behavior.

```text
bronze/   original bytes + sha256 + source URL + retrieval timestamp; never edited
silver/   one row per (series, period, value) with explicit unit, frequency,
          stock/flow and cumulative semantics; every transformation recorded
gold/     analysis-ready facts on a canonical time spine, joined and aligned
```

TARGET normalization scope (only the implemented subset identified above may be claimed): Cumulative detection and correction handles both forms the brief names: series cumulative since first publication, and series that reset each January. Frequency alignment maps daily, weekly and monthly sources onto one canonical spine. The aggregation policy lives in each series' metadata rather than in code — a stock series aggregates to period end, a flow series sums, a rate series uses the rule its metadata names — because hard-coding it is how a credit stock silently becomes a sum. Unit and scale normalization is mandatory metadata; thousand-versus-million confusion is the classic BDDK error. None of these transformations merges without unit tests.

TARGET adapters must retrieve/catalog series identifiers instead of hard-coding runtime selections. Example identifiers in source inventories are evidence, not an implemented selection policy.

### 13. Semantic catalog and retrieval — confirmed baseline; benchmark-gated extensions

TARGET under [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline), superseding DEC-127; DEC-115 remains historical. No retrieval implementation currently exists.

Mandatory HYBRID baseline: one Turkish normalizer shared by query/index paths, reviewed aliases/concept families, metadata filters, lexical/BM25 and dense semantic retrieval using the organizer's Qwen3-Embedding-8B (exact model/endpoint in DEC-129). LanceDB remains the selected lightweight series-vector index. Dense retrieval starts in the baseline without waiting for lexical failure or a prior gain measurement. Candidates retain IDs, original titles, source, unit/scale/frequency, coverage and archived/unknown flags. Exact aliases do not bypass ambiguity or semantic checks.

Two distinct flows reuse this boundary:

- **Direct series retrieval:** lexical+dense retrieval maps a named concept such as “konut kredisi faiz oranı” to the correct known series. Compare lexical-only, dense-only and combined candidates; evaluate Recall@5/10, final selection, latency and failure behavior.
- **Catalog-bounded relationship discovery:** a target such as “konut kredilerindeki hareketi ne açıklayabilir?” leads to reviewed concept families, hybrid lexical+dense search inside those families, diversity/deduplication, finance-semantic filtering and a bounded candidate pool. Searching or embedding only the target phrase can return near-duplicate target variants and miss relevant families. The family policy defines catalog neighborhoods to investigate, not economic causes. Candidate quality has its own evaluation track.

PROPOSED / BENCHMARK-GATED: RRF requires demonstrably complementary lexical/dense paths and held-out fusion gain; listwise reranking requires meaningful final-selection gain worth another model call, latency, token usage, failure surface and weak-model instability. Additional retrieval/vector infrastructure needs measured benefit. Record candidate pooling/deduplication and budgets for the combined baseline; hybrid does not itself prescribe RRF. Compare path/combined quality and failures in [EVALUATION](EVALUATION.md#retrieval-and-product-evaluation-tracks); label single-path fallback degraded, not full hybrid. Optional document-chunk indexing also needs permitted web_url ingestion. No implementation/dependency change is implied.

## Product behaviors and proof target

TARGET / CONFIRMED direction from [DEC-128](DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence), implemented through the same spine after core prerequisites:

1. **Premise validation:** Check claimed movement against the requested dates and semantics before explanatory execution. “Faiz düştü ama krediler artmadı” may need correction because nominal credit rose while real credit fell. Do not invent the price index/reference period needed to make that distinction.
2. **Finance semantic guard:** Before an operation, check stock/flow, rate/amount, cumulative/reset, frequency/aggregation, unit/scale, percentage representation, index base, coverage/missing periods and archived/stale source status. Return ALLOW, NEEDS_TRANSFORM, NEEDS_INPUT or REJECT. Required transformations are explicit and recorded; source/model text cannot waive a guard.
3. **Catalog-bounded relationship discovery:** On a permitted real catalog, produce a small reviewed-family candidate set, validate semantics, then run deterministic analyses. Report RELATIONSHIP SUPPORTED, WEAK, UNSTABLE, INSUFFICIENT or INVALID COMPARISON; no forced winner or causal claim.
4. **Relationship stability:** Compare a bounded set of windows/periods to expose similar, weakening, reversed or insufficient relationships. Reuse analytics/change-detection contracts. Window/lag/minimum-sample policies remain PROPOSED, not a research-grade regime detector.
5. **Claim-level proof:** Preserve the following logical chain. Exact storage schema/hash/transaction choices remain PROPOSED; implement only the minimum reproducible slice in M6/M5/M8 before adding presentation.

```text
Claim -> VerificationResult -> AnalysisRun -> ResultSnapshot
      -> InputSnapshots -> TransformationSpec -> Source
```

Important values need sufficient immutable result/input identity, a run bound to those inputs and transformations, stale/tampered-result rejection, independent second-path recomputation and an enforced verification gate. Definition hashes, numeric equality to any cell or a source ancestor are insufficient. “Why?” is the presentation of this proof, not its substitute.

Evidence states are claim-type-specific: numeric VERIFIED / NOT VERIFIED; relationship EXPLORATORY / STABILITY-SUPPORTED / INSUFFICIENT; causality NOT ESTABLISHED. Optional quality/match/semantics/statistical/external/causal dimensions use UNKNOWN / N/A when missing; never average them into a probability. Relationship strength labels describe the observed analysis, whereas evidence states describe its support.

Optional bounded robustness checks may compare a small deterministic set of valid windows/lags or missing-period sensitivity. DEFER / CUT IF BEHIND: Leading Indicator Miner, research-grade regime segmentation, causal event attribution, graph-heavy proof UI, recursive challenge/debate and mandatory RRF/reranking or extra vector infrastructure. Dense semantic retrieval is part of the initial baseline under DEC-130. Official-source web context is contextual evidence only.

Core first: permitted real ingestion, the existing lakehouse tool, deterministic result contracts, workspace integration, verification, live Kloudeks and required brief tools. These behaviors must not delay that vertical slice. ROADMAP owns their start conditions; confirmation here does not make a task READY.

## Multi-turn behavior

PROPOSED state transition rules, to validate in M5/M8:

| Follow-up | Preserve | Change / invalidate |
| --- | --- | --- |
| Add another series | Existing selections, raw inputs, historical evidence | Add contract/source; recompute comparisons that now include it |
| Change date range | Sources, transformation definitions, prior run history | Update selection; invalidate dependent values/charts/evidence |
| Deflate previous result | Original nominal series and its lineage | Add index/reference assumption and derived real series; recalculate dependents |
| Correct prior assumption | Original observation/history and correction record | Replace active assumption; invalidate every dependent transformation/claim |
| Failed new request | Last coherent accepted workspace | Record failure metadata; do not silently replace verified results |

TARGET transitions use the DuckDB artifact DAG of DEC-117, extending its existing definition/binding persistence with actual result recomputation and stale-read rejection. Exact persistence lifetime and reset semantics remain Q-DEMO-02 and Q-INFRA-02; never advertise restart durability without implementation and tests.

## Failure, retry, and recovery

PROPOSED outcome categories, not all present schema enums: validation error, unknown semantics, unsupported capability, unavailable source/provider, timeout/resource limit, contradictory evidence, and internal tool failure. Clarification is an orchestration outcome; it is not currently a ToolStatus enum value.

Retry transient transport/tool failures only when repeat execution is safe. Repair malformed/invalid plans with sanitized validation feedback. Track both per-step attempts and a request-wide budget so nested retries cannot multiply without bound. Do not retry blocked destinations, forbidden tools, missing permissions, or unknown semantics as if they were transient.

Exact limits are UNDECIDED pending Q-K-04 and measurements. They must be configured and tested before exposure. Exhaustion returns a structured final failure/partial result, never an endless “trying again.” Cached fallbacks need organizer permission, visible source vintage, and a clear distinction from live results.

## Security boundaries

Apply [SECURITY](SECURITY.md) at source retrieval, upload/parser entry, provider configuration, plan/tool dispatch, evidence logging, and UI output. Data locators are provenance, not execution authority. Source HTTP uses safe fetch; provider HTTP uses an organizer-configured transport that cannot be selected by user/model text. Do not treat URL syntax validation or Pydantic alone as SSRF protection.

No arbitrary runtime Python/shell execution is permitted, and the `lakehouse` tool never generates Python.

SQL is no longer optional: DEC-121 makes restricted text-to-SQL the `lakehouse` tool's mechanism, so its controls are mandatory. Generated SQL is parsed, checked against a schema whitelist, dry-run through `EXPLAIN`, and only then executed read-only, with DuckDB's file, network and extension capabilities disabled and data access limited to approved objects. Read-only SQL text alone does not prevent exfiltration; the capability restrictions are the control, and the parse is what makes the whitelist meaningful.

## Latency and extension points

Measure stage timings before optimizing: provider planning, discovery/fetch, parsing, normalization, analytics, verification, synthesis. Report cold/warm and offline/live separately. Prefer bounded metadata selection, deterministic routing for obvious formats, and reuse of verified data references. Cache only with confirmed permission and source-aware invalidation. Never skip semantic checks or evidence to make a timing target.

Extension rules:

1. New source: implement supported adapter capabilities, guards, metadata mapping, synthetic fixtures, and unfamiliar-schema tests.
2. New tool: add typed args/result expectations, registry entry, semantic prerequisites, evidence rules, and independent numerical/failure cases.
3. New model: change provider configuration/adapter capability handling; keep analytical tests unchanged.
4. New file format: confirm scope, guard/parser limits and fragment provenance, then add supported/unsupported/hostile cases.
5. New persistence/UI/orchestration dependency: resolve the relevant decision with a small tested requirement first.

Decided as of M0-ARCH and no longer open here: orchestration (DEC-113), analytical engine and lakehouse (DEC-112), spreadsheet paths (DEC-111, DEC-114), hybrid catalog baseline and benchmark-gated extensions (DEC-116, DEC-130), workspace persistence (DEC-117), lineage (DEC-118), verification (DEC-119), causality method (DEC-120), tool surface (DEC-121), provider interface (DEC-122), API and frontend (DEC-123), dependencies (DEC-124), layout (DEC-125) and deployment topology (DEC-126).

DEC-129 answers Kloudeks endpoint/auth/model availability and listed image limits. Remaining external questions cover credential access, native tool/JSON guarantees, capacity/quotas/timeouts, embedding dimension/prefix and dedicated reranker (Q-K-01..05); measured retry/latency budgets; source access/redistribution (Q-DATA-01/03); demo egress (Q-NET-01/02); and runtime/storage (Q-INFRA-01/02), which can override DEC-126. Router fine-tuning and multi-agent topology stay deferred.
