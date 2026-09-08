# Architecture

This file owns technical structure and contracts. [ROADMAP](ROADMAP.md) owns delivery/status, [DECISIONS](DECISIONS.md) confirmed choices, [SECURITY](SECURITY.md) boundary controls, and [EVALUATION](EVALUATION.md) behavioral validation.

## Reading the design

- **CONFIRMED**: an invariant/decision carried in DECISIONS, not a claim of completed code.
- **PROPOSED**: a concrete design to test and refine before adoption.
- **UNDECIDED**: requires a team or organizer answer; do not implement an assumption as a confirmed choice.

Implementation snapshot, 2026-09-09: `dev` contains the minimal core contracts ([core/models.py](../src/kkb_agent/core/models.py)), the file admission policy ([ingestion_policy.py](../src/kkb_agent/ingestion_policy.py)), sheet discovery ([xlsx_sheets.py](../src/kkb_agent/xlsx_sheets.py)) and the bounded XLSX loader ([xlsx_loader.py](../src/kkb_agent/xlsx_loader.py)), with synthetic CSV/XLSX fixtures. Nothing else below is implemented: there is no lakehouse, catalog, CSV loader, profiler, adapter registry, provider, planner, executor, tool, verifier or UI in the tree. Day 0 provider and evaluation drafts remain in a local stash and are not delivered.

As of M0-ARCH the technology stack is decided; components below therefore describe agreed target behavior rather than open options. A decided component is still unwritten code until ROADMAP records it merged.

## Goals and non-goals

CONFIRMED goals:

- Handle unfamiliar questions and new-but-supported sources through common contracts.
- Use the LLM for interpretation and planning; use deterministic tools for calculations.
- Make assumptions, transformations, failures, and evidence inspectable.
- Preserve explicit multi-turn analysis state and invalidate dependent results correctly.
- Fail safely when data meaning or execution authority is insufficient.
- Keep the inner loop fast and the demonstration reliable under constrained model access.

Non-goals for this window: arbitrary generated-code execution, a general autonomous web crawler, a hosted warehouse platform, distributed agent infrastructure, enterprise tenancy/security systems, or a training pipeline.

The stack is selected in DECISIONS and is not re-argued here: DuckDB with Parquet and Pandas (DEC-112), a custom bounded loop (DEC-113), LanceDB with DuckDB FTS (DEC-115), an artifact DAG in DuckDB (DEC-117), FastAPI with SSE behind Next.js (DEC-123), and the excluded-technology list (DEC-124). Router fine-tuning and multi-agent topology remain out of scope.

## Layer map

```text
  6. Trust layer          lineage graph + verifier            -> components 10, 12
  5. Agent core           planner / router / executor         -> components 1, 3, 4
  4. Tool layer           the six brief-named tools           -> components 4, 9
  3. Semantic layer       catalog, hybrid retrieval, aliases  -> component 13
  2. Lakehouse            DuckDB + Parquet, bronze/silver/gold -> component 12
  1. Ingest               BDDK bulletins, EVDS API, uploads   -> components 5, 6, 7
```

Source packages follow the same names under DEC-125: `src/kkb_agent/{app,agent,tools,ingest,transform,catalog,lineage,llm,eval}/`, with the web client in `web/`.

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

Preserve original observations independently of normalized/derived references. Never overwrite raw values to make a transformation convenient. Backend storage of those references is UNDECIDED; this is a logical separation, not a database mandate.

## Component contracts

Each boundary below describes responsibility, inputs, outputs, prohibited behavior, failures, and validation. Runtime controls are specified in SECURITY rather than duplicated here as implementation status.

### 1. Request coordinator and intake — CONFIRMED mechanism (DEC-113)

- Responsibility: Resolve the request/workspace, orchestrate the validated lifecycle, apply budgets, and decide whether clarification is needed.
- Input: User request, workspace ID, available capabilities, configured request limits.
- Output: A bounded execution outcome and accepted workspace transition, or clarification/failure.
- Must NOT: Treat embedded source text as a user command, create tool authority from a model response, or keep retrying indefinitely.
- Likely failures: Unknown workspace, ambiguous intent, stale references, deadline exhaustion, incompatible follow-up.
- Validation expectations: Tests for no-work clarification, failed-turn state preservation, cancellation/deadline propagation, and follow-up invalidation.

The loop is our own code: an explicit planner -> router -> executor -> verifier state machine with bounded retry, repair and cancellation. The router is a separate, cheaper call than the planner, because plan generation and tool selection have different accuracy and latency profiles. No framework mediates the transitions, so every state change is directly testable.

### 2. LLMProvider / Kloudeks boundary — CONFIRMED interface direction

- Responsibility: Isolate model-specific structured generation, plan generation, and concise synthesis.
- Input: System-owned prompts, bounded selected metadata/workspace summary, and expected response schema.
- Output: Validated model output or categorized provider failure; synthesis remains subject to claim verification.
- Must NOT: Compute authoritative financial numbers, execute tools directly, accept a request-supplied endpoint, leak credentials, or silently call another provider.
- Likely failures: Missing configuration, unavailable model, timeout/rate limit, context overflow, refusal, malformed JSON/schema mismatch.
- Validation expectations: Offline provider doubles, strict response validation, all error branches, bounded retries, redaction tests, and separately recorded permitted live smoke.

Present protocol methods are `generate_structured(prompt, response_model)`, `create_plan(request, workspace)`, and `synthesize(prompt)`. Present stub methods raise `KloudeksIntegrationPendingError` and perform no networking. `KLOUDEKS_ENDPOINT`, `KLOUDEKS_MODEL`, and `KLOUDEKS_CREDENTIAL` are provisional local configuration names, not a confirmed organizer API contract.

DEC-122 fixes the target surface at three methods, replacing the present protocol as implementation proceeds:

```python
complete(messages, *, model: str, schema: type[BaseModel] | None = None)
embed(texts: list[str], *, kind: Literal["query", "passage"])
vision(image_bytes: bytes, prompt: str)
```

Model identifier, base URL and whether structured output exists come from environment configuration, never from source constants. When the platform offers no structured-output mode, the provider validates against the schema, repairs with `json-repair`, and retries at most twice while feeding the validation error back to the model. The `kind` argument on `embed` exists because an E5-family model silently loses retrieval quality without its `query:`/`passage:` prefix; the convention itself is Q-K-05.

Model roles are assigned by measurement, not parameter count. The first provider task is a twenty-case tool-calling smoke test — Turkish question in, expected tool and arguments out — run against every available model, scoring correct-tool rate, argument-schema validity, JSON malformation rate and latency. The router base is chosen from that score. Expected shape: the larger model plans, verifies and writes the final narrative at no more than three calls per turn; a smaller model routes, reranks and classifies; the vision model serves the `web_url` tool's image branch.

Still UNDECIDED and externally blocked: endpoint and authentication format (Q-K-01), exact model identifiers and context capacity (Q-K-02), native tool-calling and structured output (Q-K-03), quotas and concurrency (Q-K-04), embedding and reranker availability (Q-K-05). Native structured output would help but never replaces local validation. Any repair path stays inside Kloudeks and the configured attempt budget; DEC-002 forbids a third-party client, import or environment variable anywhere in the product.

### 3. Planner and plan validator — CONFIRMED separation; implementation pending

- Responsibility: Translate intent into typed registered-tool steps and reject unsafe/invalid plans before execution.
- Input: Request, allowed tool schemas, source candidates, current workspace references/assumptions.
- Output: A validated executable plan, a bounded repair request, or an explicit unsupported/clarification outcome.
- Must NOT: Dispatch arbitrary names, code, imports, SQL, URLs, or paths from free-form text; silently resolve unknown data semantics.
- Likely failures: Unknown tool, extra/invalid argument, bad dependency, unavailable input, too many steps, repeated invalid plan.
- Validation expectations: Positive plan fixtures plus negative names/arguments/dependency/reference/capability cases; verify rejection occurs before any tool side effect.

Present AnalyticalPlan fields: `plan_id`, `goal`, `required_inputs`, ordered `steps`. Present PlanStep fields: `step_id`, `tool`, JSON `arguments`, `dependencies`, `expected_output_type`, `verification_required`.

Present model validators reject duplicate IDs and unknown/forward dependencies, plus self/duplicate step dependencies. **They do not validate tool membership, per-tool arguments, workspace reference existence, or semantic preconditions.** Those checks belong in the registry/validator. The `verification_required` field cannot authorize bypassing mandatory material-claim verification.

### 4. Tool registry and executor — CONFIRMED tool set (DEC-121)

- Responsibility: Map approved names to deterministic implementations, validate argument schemas, apply limits, and record structured outcomes.
- Input: Validated plan steps, typed arguments, permitted workspace references, configured budgets.
- Output: ToolResult plus referenced data/result/evidence and proposed state changes.
- Must NOT: Use `eval`/`exec`, dynamic imports from input, unrestricted shell, or direct model SQL; treat an arbitrary filesystem path as an authorized data reference.
- Likely failures: Invalid schema, tool timeout, empty data, numerical precondition failure, unknown semantics, resource exhaustion.
- Validation expectations: Registry uniqueness, validation-before-dispatch, failure categorization, retry limits, stale-reference rejection, and valid/failed workspace effects.

Present AnalyticalTool protocol exposes `name`, `arguments_model`, and `execute(arguments, workspace)`. It is not a dispatcher. Present ToolResult statuses are `success`, `failure`, `partial`; it contains run/tool IDs, result reference, evidence IDs, warnings, recoverability, and error category. Failure requires an error category; success forbids one. Result existence, warning taxonomy, and retry behavior remain to be enforced.

### 5. Source discovery and adapters — CONFIRMED abstraction

- Responsibility: Discover/inspect/load/profile a source through the common data boundary and return source provenance.
- Input: Bounded search/selection arguments, allowed source capabilities, approved data/source references.
- Output: Candidate IDs, DataContract, loaded data reference, profile, SourceRef.
- Must NOT: Make the core depend on BDDK/EVDS naming, invent missing units, bypass safe fetch/file guards, or execute document instructions.
- Likely failures: Unknown/ambiguous series, schema drift, unavailable source, revisions, empty range, unexpected content type.
- Validation expectations: Synthetic discovery/load fixtures, wrong-near-match selection tests, unfamiliar schemas, source outage, and stable provenance.

Present protocol operations: `discover`, `inspect`, `load`, `profile`, `provenance`. `load` currently returns a string reference; `profile` a generic dictionary. A strict profile/selection contract and capability negotiation are PROPOSED work, not present types. Adapters unable to discover (for example, a single uploaded file) should report unsupported capability explicitly rather than invent source candidates.

### 6. Safe ingestion, extraction, and profiling — PROPOSED implementation

- Responsibility: Validate and bound content, extract observations, and describe data quality without silently deciding financial meaning.
- Input: Guarded upload/fetched bytes, explicit selection such as sheet/table/page, parser limits.
- Output: Original-data reference, profile, source fragment references, extraction warnings, candidate schema mappings.
- Must NOT: Execute formulas/macros/scripts, fetch embedded resources without authorization, write to supplied paths, or convert OCR uncertainty into verified numbers.
- Likely failures: Empty/corrupt/oversized file, ambiguous delimiter/date, archive expansion, multi-sheet ambiguity, scanned PDF, missing table.
- Validation expectations: Exact row/type expectations; empty/malformed/oversized/content-mismatch negatives; sheet/page lineage; hostile-text cases.

Spreadsheet reading is split by trust boundary, not by file type. A file whose retrieval `ingest/` performed and recorded — a BDDK bulletin, an EVDS export — is read with Pandas and calamine under DEC-114. A file named by a user, a model or a prompt-supplied URL goes through the M1-10 bounded loader under DEC-111, with admission checks, streamed package validation, resource budgets and a terminated worker. The rule is the provenance of the request to read, never the extension. Bronze retains the original bytes and their hash on both paths.

Generic path: identify supported format -> enforce guards -> parse bounded content -> profile -> propose mapping -> confirm required semantics. Unknown source but supported format uses this path. Unknown format returns an unsupported-format outcome; it does not trigger code generation or unbounded scraping. CSV/XLSX is the first planned scope; HTML/PDF follows; image/OCR depends on confirmed requirements/capability.

### 7. DataContract and normalization — CONFIRMED semantic boundary

- Responsibility: Represent known/unknown meaning and permit only semantically valid explicit transformations.
- Input: Loaded data, source metadata, confirmed/user-supplied assumptions with provenance, requested transformation.
- Output: Validated derived data reference, updated semantic description, transformation record, or unresolved-semantics outcome.
- Must NOT: Infer stock/flow solely from frequency, aggregate without policy, silently interpolate/drop/scale, or conflate ingestion time with observation vintage.
- Likely failures: Unknown unit/reset rule, incompatible periods, duplicate/revised observations, missing baseline, different index bases.
- Validation expectations: Hand-calculated oracles, unit/frequency/cumulative negative cases, recorded parameters, and preserved originals.

Present DataContract fields cover ID, SourceRef, title, unit, frequency, time column/semantics, stock-flow, cumulative/reset, aggregation, source period, transformations, confidence, and semantic warnings. Defaults explicitly preserve unknowns. Confidence is not proof of semantic correctness.

PROPOSED additions only when a real case needs them: explicit scale/currency, index base, vintage/publication time, timezone/calendar, missing/duplicate policies, and structured semantic evidence. Do not imply these are implemented fields.

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

Present model stores `workspace_id`, selected sources, data contracts, normalized refs, derived columns, transformations, evidence, assumptions, and results. No storage service or transaction mechanism is implemented yet.

DEC-117 fixes the shape: the workspace is a directed acyclic graph of artifacts persisted in DuckDB. A node is a table, a column, a chart or a derived value, addressed by a hash of its inputs and parameters. A follow-up that adds a column adds a node and computes only that node; existing nodes keep their computed cells, which is what "add a column without disturbing the table" actually requires. Replaying the graph reproduces a result, and node identity is the cache key, so invalidation follows edges rather than a separate mechanism.

Never regenerate the whole table per turn. That is how a value silently changes between two answers the user believes are the same table. Cross-process durability and reset semantics remain Q-INFRA-02 and Q-DEMO-02; do not advertise restart durability without implementation and tests.

### 9. Deterministic analytics and presentation data — CONFIRMED responsibility

- Responsibility: Compute supported changes, comparisons, anomalies, association/lag, and justified statistical tests; emit chart/table data from computed results.
- Input: Validated data references, semantic prerequisites, explicit parameters and periods.
- Output: Material values, units, sample counts, warnings/limitations, and reproducible run/evidence references.
- Must NOT: Treat model prose as numbers, hide denominator/zero handling, select lags without recording policy, or claim causality from correlation alone.
- Likely failures: Too few observations, constant series, missing baseline, non-stationarity, incompatible real/nominal data, undefined statistic.
- Validation expectations: Independent numerical oracles, per-case tolerances, prerequisite failures, lag-direction cases, and causality/abstention checks.

Prefer small tools over one general “analyze everything” tool. Engine and exact anomaly/causality methods are UNDECIDED. Advanced causal inference is optional unless confirmed requirements make it mandatory; defensible abstention remains required.

### 10. Evidence ledger and verifier — CONFIRMED direction

- Responsibility: Resolve lineage and check every material claim against source inputs, deterministic transformations/results, and validation rules.
- Input: Candidate claims, tool runs, data references, SourceRefs, TransformationRecords, expected semantic constraints.
- Output: Passed/failed/not-run validation, accepted claim set, limitations, and inspectable evidence references.
- Must NOT: Mark an unverified claim passed because a citation exists, let the model self-certify numbers, or ignore contradictory/stale inputs.
- Likely failures: Missing/orphan references, altered output, incomplete periods, incompatible units, contradictory sources, unsupported inference.
- Validation expectations: Recompute representative material results; inject wrong values/missing lineage; verify failed/not-run claims cannot appear as verified.

Present SourceRef holds identity/type/locator and optional retrieval time/hash. Present TransformationRecord holds operation/parameters/input refs/output ref. Present EvidenceRecord holds claim, sources, optional run, transformations, period/columns, validation, limitations. Validation defaults to NOT_RUN. These records do not enforce a complete evidence chain; the ledger service and claim rules are still pending.

DEC-118 makes provenance a typed graph rather than a set of records. Node kinds are `SourceFile`, `Series`, `Transform`, `Column`, `Metric` and `Claim`; edge kinds are `derives_from`, `aggregates`, `deflates_by` and `cites`. It is stored as `lineage_nodes` and `lineage_edges` in DuckDB with hash-addressed identifiers and traversed in memory with `networkx`. Every numeric claim carries a `claim_id` whose subgraph is exactly what the evidence panel draws. A cell without lineage is a defect, not a missing feature — every code path that produces a number writes lineage.

DEC-119 makes the verifier a gate rather than a report. Before an answer reaches the user:

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

FastAPI serves the application and streams plan and tool progress over server-sent events, so a multi-step analysis is legible while it runs. The client is Next.js with Tailwind and shadcn/ui, TanStack Table for the analysis table, `react-plotly.js` for charts, and React Flow for the evidence panel that draws a claim's lineage subgraph. The logical UI contract above still does not depend on that stack: Streamlit remains the recorded fallback, and the front end must not gate backend acceptance.

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

`silver` carries the work that decides whether this project is correct. Cumulative detection and correction handles both forms the brief names: series cumulative since first publication, and series that reset each January. Frequency alignment maps daily, weekly and monthly sources onto one canonical spine. The aggregation policy lives in each series' metadata rather than in code — a stock series aggregates to period end, a flow series sums, a rate series uses the rule its metadata names — because hard-coding it is how a credit stock silently becomes a sum. Unit and scale normalization is mandatory metadata; thousand-versus-million confusion is the classic BDDK error. None of these transformations merges without unit tests.

EVDS series codes are never hard-coded. They are pulled from the catalog endpoint, indexed, and found by search.

### 13. Semantic catalog and retrieval — CONFIRMED mechanism (DEC-115, DEC-116)

- Responsibility: Turn a Turkish financial question into the right series identifiers without hard-coded codes.
- Input: Series and column metadata (Turkish name, unit, frequency, source, sample values); document chunks fetched by the `web_url` tool; a user question.
- Output: A ranked, bounded candidate set with enough metadata for the router to choose and cite.
- Must NOT: Normalize differently at index time and query time, return a candidate without its unit and frequency, or let retrieval scores substitute for confirmed semantics.
- Likely failures: Near-identical series titles, paraphrase the embedding misses, an exact code the dense index ignores, Turkish casing and diacritic mismatches.
- Validation expectations: Fifty hand-written question-to-series pairs with a measured recall@10; wrong-near-match cases that must be resolved explicitly rather than guessed.

Two LanceDB collections: series metadata, and chunks from documents the `web_url` tool retrieved. Lexical retrieval uses DuckDB's full-text index, dense retrieval uses LanceDB, and the two are fused with reciprocal rank fusion — which needs no score calibration between them. The top twenty go to a small model for listwise reranking that returns the best five as JSON; this stands in for a cross-encoder, whose availability is unresolved (Q-K-05).

Above that sits a hand-written dictionary of roughly fifty concepts — konut kredisi, ihtiyaç kredisi, taşıt kredisi, TÜFE, ÜFE, politika faizi, konut fiyat endeksi, takipteki alacaklar, mevduat, BIST100, altın, ipotekli satış and their siblings. An exact alias hit skips retrieval entirely. All Turkish normalization — dotted and dotless i, case folding, diacritic removal — goes through **one** function shared by indexing and querying; two implementations drift and halve recall invisibly. Retrieval quality is measured before it is trusted, and a weak measurement moves weight to BM25 and the alias dictionary rather than to model changes we cannot make.

## Multi-turn behavior

PROPOSED state transition rules, to validate in M5/M8:

| Follow-up | Preserve | Change / invalidate |
| --- | --- | --- |
| Add another series | Existing selections, raw inputs, historical evidence | Add contract/source; recompute comparisons that now include it |
| Change date range | Sources, transformation definitions, prior run history | Update selection; invalidate dependent values/charts/evidence |
| Deflate previous result | Original nominal series and its lineage | Add index/reference assumption and derived real series; recalculate dependents |
| Correct prior assumption | Original observation/history and correction record | Replace active assumption; invalidate every dependent transformation/claim |
| Failed new request | Last coherent accepted workspace | Record failure metadata; do not silently replace verified results |

Workspace state persists as the DuckDB artifact DAG of DEC-117, so these transitions are node additions and edge-following invalidations rather than table rebuilds. Exact persistence lifetime and reset semantics remain Q-DEMO-02 and Q-INFRA-02; never advertise restart durability without implementation and tests.

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

Decided as of M0-ARCH and no longer open here: orchestration (DEC-113), analytical engine and lakehouse (DEC-112), spreadsheet paths (DEC-111, DEC-114), catalog and retrieval (DEC-115, DEC-116), workspace persistence (DEC-117), lineage (DEC-118), verification (DEC-119), causality method (DEC-120), tool surface (DEC-121), provider interface (DEC-122), API and frontend (DEC-123), dependencies (DEC-124), layout (DEC-125) and deployment topology (DEC-126).

Still UNDECIDED, and externally blocked rather than open to preference: the Kloudeks endpoint, authentication, exact model identifiers, structured-output support, quotas, and the embedding and vision models (Q-K-01 through Q-K-05); retry and latency budgets, which need Q-K-04 plus measurement; live source access and redistribution (Q-DATA-01/03); network egress at demo time (Q-NET-01/02); and the runtime environment (Q-INFRA-01/02), which can override DEC-126. Router fine-tuning and multi-agent topology stay deferred. See DECISIONS and OPEN_QUESTIONS; this document does not settle them.
