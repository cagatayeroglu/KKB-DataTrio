# Architecture

This file owns technical structure and contracts. [ROADMAP](ROADMAP.md) owns delivery/status, [DECISIONS](DECISIONS.md) confirmed choices, [SECURITY](SECURITY.md) boundary controls, and [EVALUATION](EVALUATION.md) behavioral validation.

## Reading the design

- **CURRENTLY IMPLEMENTED** describes the source boundaries below; merged revisions, validation and remaining task acceptance are maintained only in [ROADMAP Current Project Status](ROADMAP.md#current-project-status).
- **TARGET / CONFIRMED** describes authorized behavior, not delivery.
- **PROPOSED / BENCHMARK-GATED** needs task review or measured benefit before adoption.
- **BLOCKED BY EXTERNAL ANSWER** names the organizer/platform dependency in OPEN_QUESTIONS.
- **DEFERRED** is outside the core slice unless a later explicit scope decision changes it.

The implemented spine includes bounded file admission, CSV/XLSX loading and safe GET with validated redirects, DuckDB/Parquet storage and financial semantics, typed results, the Kloudeks transport (tested offline; one authorized live smoke and one live end-to-end question passed), validated planning/execution, content-addressed workspace values and multi-result answer gating. Seven callable factories exist: M13-04 `catalog_search` plus the six brief tools (search is offline-only): `lakehouse`, `change_detection` (comparison), `anomaly`, `causality` (association, lag and Granger precedence), `web_search` with an explicitly injected backend, and `web_url`, which reads a CSV/XLSX table, a PDF's text and ruled tables, or bounded static HTML text/tables at an address the user wrote, and can return one named cell as a result the answer gate binds. Synthetic tests compose an end-to-end answer with a scripted model. Scoped BDDK/EVDS ingestion adapters and the prepared official dataset, provider retries and limits, CSV/XLSX profiling, full hybrid/catalog coverage, breakpoint detection, complete proof/replay, production `web_search`, `web_url`'s JavaScript-rendered/image-address extraction, evaluation runner, UI and deployment remain incomplete. Day 0 drafts remain outside the shared runtime.

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
  4. Tool layer           six base + catalog_search + table_transform  -> components 4, 9
  3. Semantic layer       catalog, hybrid baseline, aliases  -> component 13
  2. Lakehouse            DuckDB + Parquet, bronze/silver/gold -> component 12
  1. Ingest               BDDK bulletins, EVDS API, uploads   -> components 5, 6, 7
```

Target packages follow DEC-125 (only existing source links below imply implementation): `src/kkb_agent/{app,agent,tools,ingest,transform,catalog,lineage,llm,eval}/`, with the web client in `web/`.

## Official-data preparation and demo runtime

[DEC-137](DECISIONS.md#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) refines DEC-136's prepared-data direction into a catalog-complete, lakehouse-first target. “Catalog-complete” means extensible trusted metadata coverage for safely representable financial measures, not a claim that full coverage is delivered. M3-06 now provides a bounded offline-validated Monthly ingestion primitive for reviewed selectors; the prepared official dataset, live adapter acceptance, availability routing, on-demand materialization and version/refresh orchestration remain unfinished.

The [dated DEC-137 refinement](DECISIONS.md#dec-137-prepared-pool-refinement) prioritizes the organizer prepared-pool model:

```text
PREPARATION / DEMO-CRITICAL (source policy required)
  BDDK / EVDS -> trusted reusable adapters -> bounded official retrieval
  -> raw bronze snapshots -> validation / normalization -> silver observations
  -> required gold aligned/joined/transformed analytical datasets
  -> prepared DuckDB + Parquet lakehouse

PRIMARY DEMO RUNTIME TARGET
  user -> planner -> catalog_search (lexical now; required dense hybrid target)
  -> trusted prepared candidate -> lakehouse (silver / appropriate trusted gold)
  -> guarded transforms / analytics -> mandatory correctness harness -> verifier
  -> accepted workspace publication / answer / table / chart
  prepared-pool miss / ambiguous identity / insufficient coverage -> clarify or abstain

FUTURE SCALABILITY, NOT A CORE THREE-TURN PREREQUISITE
  known unmaterialized identity + approved adapter/contract/policy
  -> official fetch -> snapshot / validate -> materialize / version -> reuse lakehouse

SEPARATE WEB BRANCH
  general discovery -> web_search / SearchBackend
  specific authorized URL/document -> web_url
```

The primary structured financial-data path does not fetch BDDK/EVDS at question time. This reduces financial-source network dependence, not the separate Kloudeks requirements of planning and query embeddings. Mandatory metadata inspection, observation-quality/semantic checks and applicable reconciliation run before dependent use, outside planner discretion under DEC-135. The diagram is intended integration, not current automatic wiring or a new registry tool. A prepared-pool miss may clarify/abstain until the future materialization path is deliberately implemented. It grants no arbitrary web/network authority. A known series with insufficient requested coverage is a miss for that window; observed min/max never establishes full coverage.

### Vertical slice and broader coverage

The first verified end-to-end target is **housing-credit outstanding balance, housing/mortgage rate, CPI/TÜFE and national KFE**, approximately **2021-01–2026-06**. All four are prepared (2026-09-14) in an operator-local lakehouse that is not committed: BDDK housing balance TP/YP/TOTAL, EVDS `TP.KTF12` new housing-loan rate, CPI `TP.TUKFIY2025.GENEL` (with `TP.GENENDEKS.T1` as cross-check) and KFE `TP.KFE.TR` ([EVDS contract](EVDS_SERIES_METADATA.md)). It is not the final product ceiling. Broader prepared coverage should use the same architecture for BDDK Monthly/Weekly/FinTürk loans (consumer/vehicle/commercial/SME), deposits, NPL, rates/ratios and other relevant banking measures, with supported TP/YP/TOTAL, bank-group/geography dimensions, and relevant EVDS rate/index/macro/banking families. Exact coverage and source permissions remain open; do not ingest every byte or guess unknown semantics.

Broad preparation is the primary/demo-critical path: lower latency, fewer financial-source runtime dependencies, repeatable demonstrations, stable provenance and resilience to source outages/layout drift. Expand safely practical prepared coverage after the first real E2E slice. On-demand official materialization and sophisticated refresh/vintage orchestration are future scalability extensions, not prerequisites for the core three-turn demo; their source permissions remain unresolved.

### Catalog availability and reusable adapters

The target catalog maps concept → official ID/canonical selector candidates → trusted metadata and ambiguity → availability → routing. Preserve provider, concept/family, label/aliases, frequency, unit/scale, stock/flow/rate/index semantics, cumulative behavior, aggregation permissions, base/reference year, archive state, coverage and source provenance. Availability may be represented in the catalog or a linked manifest; no fields/enums are added to current contracts here.

| Conceptual state | Required evidence / target behavior |
| --- | --- |
| Prepared / materialized | Validated dataset version and coverage for the selected identity/window; query lakehouse |
| Fetchable from official source (future scalability) | Resolved trusted identity/usable semantics, registered adapter, bounded request and policy; future fetch/validate/materialize before analysis. Demo-critical prepared-pool misses may clarify/abstain |
| Unresolved | Missing/ambiguous identity or required semantics; clarify/abstain, never upgrade to fetchable |
| Unavailable / unsupported | Missing adapter, unsupported calendar/shape or denied source policy; explicit limitation/abstention |

Source adapters own endpoint/request shape, trusted identity mapping, response validation/parsing, semantic interpretation and source provenance. Their primary near-term role is BUILD / REFRESH of the prepared official pool, reusing common safe-fetch/TLS/bounds, parser/storage, hashing and lineage. Runtime cache-miss routing is a future reuse of these primitives, not the demo-critical task. Current M3-06 refuses changed ranges/content rather than implementing refresh/version promotion. The LLM may choose intent-dependent actions, but cannot invent BDDK selectors, EVDS IDs, endpoints, semantics or materialization state.

BDDK's delivered `BDDK:selector:v1:<SHA256>` is an internal deterministic key over provider, bulletin_family, table, row, bank_group, presentation_currency, value_dimension and geography; period/clock are snapshot/observation properties. Only monthly/table 4/row 2/sector 10001/TL has reviewed metadata in M3-05, with explicit TP/YP/TOTAL. General M3-05 remains PARTIAL; M3-06 can ingest supported Monthly responses through the bounded path below, but no real official dataset is claimed prepared. Weekly/FinTürk require their own reviewed semantics (including FinTürk THOUSAND versus monthly MILLION).

M3-06's [Monthly ingestion contract](BDDK_MONTHLY_METADATA.md#m3-06-bounded-monthly-ingestion-offline-validated) reuses the supervised fetch worker for a closed official POST descriptor and existing bronze/silver/lineage storage. It validates an entire bounded month range, records a deterministic internal manifest over every raw source, then commits series/observations/lineage together. Identical batches are no-ops; changed bytes/range/contracts require a new version and never overwrite trusted history. Exact-window readback is available offline. An operator command (`python -m kkb_agent.ingest.bddk_monthly_operator`) runs an isolated `smoke` or an explicit-root `prepare` with acceptance checks; live acceptance and the 2021-01–2026-06 housing preparation passed on 2026-09-14. No planner tool or runtime cache-miss routing is added. Housing is the first reviewed metadata case; broader source mappings extend the review boundary without rewriting transport/storage.

EVDS adapters must work with any supported trusted catalog series ID; CPI/KFE/mortgage rates are first use cases. Preserve real series versus datagroup identity, native frequency/anchor, archive state, date/decimal parsing, aggregation flags, base/reference year and release/version provenance. Unknowns and indistinguishable rate candidates remain unresolved. Neither source inventory proves that a live adapter exists.

### Dataset lifecycle and publication

Intended lifecycle: **DISCOVER → FETCH → SNAPSHOT → PARSE → VALIDATE → MATERIALIZE → VERSION → QUERY → REFRESH**. Retain raw content hash, trusted selector/request, retrieval/release metadata, parser/semantic policy versions, normalized observations and recorded transformations. Validate semantics, periods, units and source contract before publishing a usable version/availability pointer; failed materialization must preserve previous trusted data.

Same official input content + selector + parser/semantic policy should yield the same content version or an idempotent no-op. Retrieval timestamps remain provenance and need not change content identity. Refresh can reveal new periods, corrected historical values, metadata or retirement/archive changes: retain old snapshots/versions, reconcile explicitly and never silently overwrite historical evidence. M3-06 delivers the bounded internal manifest and conflict refusal; broader version/vintage policy and promotion remain M3/M12 work; the existing one-value-per-series/period store is not a complete version system. No scheduler or new transaction framework is selected.

Dataset publication is separate from M5-21's delivered gate-approved workspace transition. New source storage alone cannot publish an accepted analytical result; M8-21 execution binding and the final answer gate still apply. Existing successful/failing turn semantics remain unchanged.

### Storage and trust domains

Parquet is persistent analytical data/artifact format. DuckDB is the embedded analytical/query engine, not a hosted external database. Provider-neutral dataset/object storage should accommodate:

```text
Dataset/Object Storage (target abstraction, not an implemented interface)
  local persistent filesystem / volume
  S3-compatible object storage (future option; AWS S3 not selected)
```

Object storage may later retain raw/bronze snapshots, Parquet, manifests and versioned prepared datasets; DuckDB remains compute/query. S3-compatible integration, persistent-volume lifetime and runtime credentials depend on Q-INFRA-01/02 and remain unimplemented. Source access, redistribution/retention and demo-time official fetch/egress remain open.

Official BDDK/EVDS catalog datasets are intended persistent/versioned core state. User CSV/XLSX/PDF, arbitrary authorized URLs and BIST/IMF/other documents remain session-scoped external artifacts with separate ownership/retention. Shared bronze/parser/lakehouse primitives do not promote them to permanent trusted official catalog series. General web discovery is separate; a search-returned URL has no automatic fetch authority.

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
  |              +-> trusted official availability -> prepared lakehouse or approved materialization
  |              +-> lakehouse observations -> transforms / analytics
  |              +-> authorized web_url / upload -> safe boundaries -> supported parser
  |              +-> structured result + source / computation evidence
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
5. Check trusted requested-window availability: use prepared lakehouse observations, or the DEC-137 policy-permitted official adapter/materialization path for known misses. Preserve source/version/retrieval evidence and apply mandatory quality checks before analysis. Separate authorized URL/upload paths retain their guards and session scope; clarify/abstain on unsafe misses.
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

CURRENTLY IMPLEMENTED: [Session](../src/kkb_agent/agent/loop.py) plans and executes through the registry. `Session.answer` synthesizes computed results and calls the verifier gate; publication requires successful execution, an ACCEPTED answer and verified candidate evidence. It uses current named Workspace values across turns. The opt-in [bounded catalog continuation](CATALOG_CONTINUATION.md) executes catalog-only discovery and lets one further analysis/clarification plan consume candidate metadata in a data role. Step and repair counts cover both phases; tool retries remain bounded per step. Automatic workspace loading, planner-driven recomputation and total request deadlines/cancellation remain TARGET. A separate cheaper router call remains PROPOSED pending model/latency evidence.

### 2. LLMProvider / Kloudeks boundary — CONFIRMED interface direction

- Responsibility: Isolate model-specific structured generation, plan generation, and concise synthesis.
- Input: System-owned prompts, bounded selected metadata/workspace summary, and expected response schema.
- Output: Validated model output or categorized provider failure; synthesis remains subject to claim verification.
- Must NOT: Compute authoritative financial numbers, execute tools directly, accept a request-supplied endpoint, leak credentials, or silently call another provider.
- Likely failures: Missing configuration, unavailable model, timeout/rate limit, context overflow, refusal, malformed JSON/schema mismatch.
- Validation expectations: Offline provider doubles, strict response validation, all error branches, bounded retries, redaction tests, and separately recorded permitted live smoke.

CURRENTLY IMPLEMENTED: [provider.py](../src/kkb_agent/llm/provider.py), [config.py](../src/kkb_agent/llm/config.py), [structured.py](../src/kkb_agent/llm/structured.py) and [doubles.py](../src/kkb_agent/llm/doubles.py) provide the DEC-122 protocol, environment-driven configuration, local JSON/schema validation/repair and a scripted non-networking provider. [kloudeks.py](../src/kkb_agent/llm/kloudeks.py) (M4-07) is the one transport: `httpx` against DEC-129's chat and embedding endpoints, refusing any base URL but DEC-129's host, fixed paths and configured models only, redirects and ambient proxy/environment settings off, responses read under a byte cap and deadline, and errors reduced to a status category without key, prompt or body. Schema repair is the same loop the double runs; transport retries are M4-10's. It is tested offline against an in-process transport, one authorized live smoke ([smoke.py](../src/kkb_agent/llm/smoke.py), M4-12) passed for chat and embedding, and one live end-to-end question on synthetic data ([live_check.py](../src/kkb_agent/live_check.py), M4-15) went through planning, a tool, drafting and the gate to an ACCEPTED answer. That run showed the served model rejects two system messages, so the transport joins the leading system turns into one. Capability flags are configured expectations, not live-probed organizer guarantees. The old Day 0 protocol is not delivered.

M7-19 extends `live_check` with opt-in `--document --question` mode. Its temporary lakehouse has no synthetic seed; the four analytical tools and `make_web_url_tool(lineage=lake.lineage)` share that store. The operator supplies the unchanged question to `Session.answer(question, lake.connection)`: planner → executor → `web_url` → `safe_fetch` → bounded CSV/XLSX/PDF loader → cell selection → `AnalyticalResult` → writer → answer gate. The command adds no fetch/parser bypass. Its bounded report resolves the selected transform/source edge and rechecks the retained answer against the same last result used by `Session.answer`; a document-bound numeric claim is mandatory. Raw source bytes are not persisted by this mode, and the temporary store is removed on exit. The existing synthetic command is unchanged. Offline tests cover this integration; **one live public CSV acceptance has passed** ([evidence and limits](EVALUATION.md#m7-19-live-csv-acceptance)), and later execution still needs explicit approval and an accepted Q-NET-01/02 boundary.

DEC-122's three-method surface is:

```python
complete(messages, *, model: str, schema: type[BaseModel] | None = None)
embed(texts: list[str], *, kind: Literal["query", "passage"])
vision(image_bytes: bytes, prompt: str)
```

Model identifier, base URL and whether structured output exists come from environment configuration, never from source constants. When the platform offers no structured-output mode, the provider validates against the schema, repairs with `json-repair`, and retries at most twice while feeding the validation error back to the model. The `kind` argument on `embed` preserves query/passage intent; the confirmed Qwen model's prefix convention remains Q-K-05. Do not assume an E5 convention applies.

Model roles are assigned by measurement, not parameter count. A proposed live measurement is a twenty-case tool-selection smoke test — Turkish question in, expected tool and arguments out — against an eligible text model, scoring correct-tool rate, argument-schema validity, JSON malformation rate and latency. Use locally validated text responses unless native function/tool calling is separately confirmed; the compatible endpoint alone does not establish that feature. The router base is chosen from that score. Role/model splits and exact call budgets remain PROPOSED pending those measurements. Models may propose or summarize; deterministic code verifies material calculations. Reranking is optional under DEC-130. Vision, OCR and embedding availability are officially confirmed in [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy). The transport's embedding call passed one live request (M4-12) and its `vision` method sends one image with a prompt; M7-11 adds explicit `ocr` injection into the PDF loader/web_url, using the organizer's literal OCR request contract. It is off by default; no live OCR is validated.

CONFIRMED: [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the exact host/base URL, MIA-key authentication, model IDs, endpoints and image-count limits. The `openai` SDK is allowed exclusively as the Kloudeks-compatible client; third-party hosted LLM destinations and fallback remain banned. M4-07 delivered the transport and replaced the blanket SDK-name test with destination tests; the key authenticated live for chat and embedding (M4-12, embedding dimension 4096) and one live question passed end to end (M4-15). Still unknown: OCR access, context/output capacity, native tool calling/guaranteed JSON, quotas/concurrency/timeout behavior, the embedding prefix convention and dedicated reranker availability (narrowed Q-K-01..05). Local response validation remains mandatory.

### 3. Planner and plan validator — CONFIRMED separation; partial implementation

- Responsibility: Translate intent into typed registered-tool steps and reject unsafe/invalid plans before execution.
- Input: Request, allowed tool schemas, source candidates, current workspace references/assumptions.
- Output: A validated executable plan, a bounded repair request, or an explicit unsupported/clarification outcome.
- Must NOT: Dispatch arbitrary names, code, imports, SQL, URLs, or paths from free-form text; silently resolve unknown data semantics.
- Likely failures: Unknown tool, extra/invalid argument, bad dependency, unavailable input, too many steps, repeated invalid plan.
- Validation expectations: Positive plan fixtures plus negative names/arguments/dependency/reference/capability cases; verify rejection occurs before any tool side effect.

CURRENTLY IMPLEMENTED: [AnalyticalPlan](../src/kkb_agent/agent/plan.py) contains `question` and `steps`; each step has `step_id`, `tool`, `arguments` and `depends_on`. The initial `Session.plan` system prompt includes this model's JSON schema via `schema_instructions`, the same renderer used by schema repair (M5-19); registry-owned argument schemas appear once beside it. This supplies the contract before the first response without changing validation or retry budgets. No workspace/source text is added to system instructions. [validate_plan](../src/kkb_agent/agent/executor.py) checks registered names and argument schemas, duplicate/self/unknown dependencies, cycles and step limits, then topologically orders the steps. Registry-owned input-step requirements are enforced when supplied by a tool. General workspace/data-reference ownership and output typing remain incomplete; financial semantics are checked by the receiving tools/harness. Those remain target checks; a parsed plan is not a proof of them.

### 4. Tool registry and executor — approved target (DEC-121/133)

- Responsibility: Map approved names to deterministic implementations, validate argument schemas, apply limits, and record structured outcomes.
- Input: Validated plan steps, typed arguments, permitted workspace references, configured budgets.
- Output: ToolResult plus referenced data/result/evidence and proposed state changes.
- Must NOT: Use `eval`/`exec`, dynamic imports from input, unrestricted shell, or direct model SQL; treat an arbitrary filesystem path as an authorized data reference.
- Likely failures: Invalid schema, tool timeout, empty data, numerical precondition failure, unknown semantics, resource exhaustion.
- Validation expectations: Registry uniqueness, validation-before-dispatch, failure categorization, retry limits, stale-reference rejection, and valid/failed workspace effects.

CURRENTLY IMPLEMENTED: [ToolSpec / ToolRegistry](../src/kkb_agent/agent/registry.py) own names, Pydantic argument schemas and callable dispatch. [ToolResult](../src/kkb_agent/agent/executor.py) carries `status`, `step_id`, `tool`, an untyped `output`, error category, recoverability, warnings and optional lineage `evidence`. Statuses are success/failure/partial/not_run. Failure requires a category and success forbids one. Eight factories have implementations, including table_transform and offline `web_search` and `catalog_search` alongside `lakehouse`, `change_detection`, `anomaly`, `causality` (association/lag) and `web_url`, whose `output` is a `WebUrlOutput` — a loaded table or PDF document, or a fixed reason; only when the planner names one cell by column header and row label does it also carry a document-bound `AnalyticalResult` (M7-18 and DEC-132 literal-source policy). The lakehouse `output` is a `LakehouseOutput` pairing an M6-01 `AnalyticalResult` with the rows behind it; `output` itself stays `object`, so the typing is the tool's discipline rather than the executor's. A successful call that established no measurement stays SUCCESS and reports the reason as a warning — the query ran, and conflating that with a failure would hide which of the two happened. General output-reference/ownership validation remains target work; the table_co_movement consumer below checks typed references and source evidence. `Session.answer` integrates workspace values and verification, while lower-level execution alone is not an answer gate.

### Approved tool surface

[DEC-135](DECISIONS.md#dec-135--planner-actions-and-mandatory-correctness-harness) supersedes DEC-133’s planner-callable portion with the eight-tool target below. All eight factories are implemented; `table_transform` exposes `deflate` and `add_series` (M5-20). Each Session sees only explicitly registered implementations. No runtime allowlist or registration changes are made by this decision.

| Tool | Status | Delivered scope or planned responsibility |
| --- | --- | --- |
| `lakehouse` | IMPLEMENTED, bounded scope | Restricted read-only SQL and typed result/provenance output; not full replay/proof |
| `web_search` | IMPLEMENTED, offline only | Bounded provider-neutral discovery; injected backend required; no production adapter or live acceptance |
| `web_url` | IMPLEMENTED, bounded scope | Guarded CSV/XLSX/PDF/static HTML and exact-cell evidence; bounded offline OCR fallback; no browser/JS or general image-address extraction |
| `anomaly` | IMPLEMENTED, bounded scope | Existing deterministic method subset; not every anomaly technique |
| `causality` | IMPLEMENTED, bounded scope | Association, lag and Granger precedence with stated limits; not causal identification |
| `change_detection` | PARTIAL | Period `compare`, monthly `co_movement` over series, and `table_co_movement` over verified table columns (M6-25); breakpoint/trend-break methods remain absent |
| `catalog_search` | OFFLINE IMPLEMENTED | Natural-language query to bounded ranked trusted CatalogRecord candidates; M13-04 |
| `table_transform` | PARTIAL | `deflate` and monthly `add_series` preserve the published source table (M5-20/M2-15); rebase/align/filter not exposed |

Every additional tool must define closed typed input and output contracts before registration. Query/filter/candidate limits reuse existing metadata enums; unknown or unavailable fields remain explicit. Candidate IDs, labels, unit/scale, frequency, stock/flow/cumulative kind, archive state and aggregation/coverage declarations come from trusted catalog state. Concept families and observation-kind metadata may be returned only when represented by reviewed source-backed contracts; retrieval must not manufacture them. Multiple plausible candidates remain multiple candidates, not a silently authoritative top-1.

The planner receives only registered implementations through `ToolRegistry.descriptions`; proposed names and operations stay out of runtime prompts until implemented. Executor argument validation and limits remain mandatory. Material calculations are deterministic; source/model text is untrusted. Semantic guards, security guards, lineage recording and verifier/gate run as harness requirements, never optional `semantic_guard`, `security_guard`, `lineage_recorder` or `verifier` calls. `proof` stays API/UI over the existing graph; `document_search` is excluded. Typed output validation/ownership gaps described above remain work, not a completed capability.

### Mandatory correctness harness

The planner selects user-intent-dependent actions. The following triggers are system obligations under DEC-135, not optional tool calls:

| Trigger | Required capability | Delivery boundary |
| --- | --- | --- |
| Financial series selected | Deterministic series_inspect: trusted source/ID, frequency, unit/scale, archive, stock/flow/rate, aggregation and coverage | M13-13 future wiring; unavailable metadata stays unknown |
| Observations retrieved for analysis | Deterministic data_quality: bounded missing-period/coverage/gap/frequency/validity checks and supported stale/archive evidence before analysis-ready | M1-12 future wiring; never model confidence |
| Financial transformation | Semantic compatibility guard | Existing semantic guard layer; remaining operation/prerequisite gaps stay explicit |
| Multiple trusted sources/results support the same measure | Conditional deterministic/hybrid reconcile_sources over semantics, period, frequency, unit, scale and values | M8-09 future wiring; CONSISTENT / DIFFERENT / NOT_COMPARABLE / NEEDS_TRANSFORM / NEEDS_INPUT |
| Numeric final claim | Lineage/evidence binding and verifier/gate | Existing result-bound path; a citation or metadata candidate alone is not measurement proof |

The LLM must not skip correctness-critical checks. The first, second and fourth rows are required architecture, **not implemented automatic integrations**. Existing guards/security/lineage/verifier remain mandatory system layers; no unfinished control is declared complete. A later explicit user comparison could expose reconciliation if separately designed, without making its correctness trigger discretionary.

### Web search implementation plan (M7-21/22)

IMPLEMENTED offline contract: [DEC-134](DECISIONS.md#dec-134--provider-neutral-web-search-with-mandatory-live-acceptance). M7-21 approves the abstraction; M7-22 delivers only the offline/provider-neutral tool, with merge evidence in ROADMAP.

`Qwen planner -> web_search ToolSpec -> SearchBackend.search -> configured backend`. SearchBackend is an internal interface, not a provider API. Use a closed bounded query/max_results input and typed ranked candidates (title, sanitized URL, snippet, domain, rank, supplied publication date or unknown), plus provider-neutral status. No optional domain/recency knobs until separately justified. Provider adapters translate to this stable contract; credentials, configuration and raw wire payloads are never planner inputs or outputs.

FakeSearchBackend exists only for deterministic offline tests. The real production adapter remains absent until separately selected, configured and validated; no default fake backend, automatic provider selection or fallback. M7-22 requires no API key, account or external call. Execution must bound query/result sizes, candidate count, response handling and backend time; map timeout/malformed replies/backend errors to fixed safe outcomes. Validate output before exposure, exclude unsafe URLs, deduplicate deterministically, preserve missing metadata and strip sensitive locator material without granting a new destination permission. Snippets/titles remain inert untrusted data and never become verified AnalyticalResults merely by being returned.

`web_url` still requires the exact URL in the original user question (`addresses_in` / `URL_NOT_IN_QUESTION`). Discovery never authorizes a later fetch, nor weakens safe-fetch DNS/TLS/redirect checks. Registry/planner expose only implemented tools; schema validation, security controls, lineage and verifier/gate remain mandatory. M13-04 catalog_search is implemented offline; table_transform is available and registered in prepared-pool rehearsals. DEC-135 inspection, quality and reconciliation are future harness integrations, not additional normal planner tools.

The callable factory is `make_web_search_tool(backend=..., timeout_seconds=5.0)`, registered explicitly on a ToolRegistry. The injected trusted adapter must be spawn-serializable and implement `search(SearchRequest) -> SearchReply`. No changes to planner schemas are needed to replace the backend. There is no automatic registration in operator live commands.

Input permits only `query` (1–512 characters, nonblank, no controls) and `max_results` (1–10, default 5). Backend replies contain at most 20 typed hits: title ≤512, URL ≤4096, optional snippet ≤2048 characters and supplied `published_at` date or null. Output adds derived domain, original 1-based backend rank, `locator_redacted`, exclusion/duplicate counts, `untrusted=true`, `fetch_authorized=false`, and status `ok/no_results/partial/rejected/failed`. Errors are fixed `BACKEND_TIMEOUT`, `BACKEND_ERROR`, `MALFORMED_RESPONSE`, `RESPONSE_LIMIT` or `UNSAFE_RESULTS` codes.

One spawned worker bounds backend time (default 5 s including startup; operator maximum 30 s), is terminated/reaped on deadline, suppresses backend stdout/stderr, and returns validated JSON capped at 64 KiB. Typed fields bound serialization before projection; the future adapter must also bound wire I/O before constructing a reply. This is not a sandbox for untrusted adapter code. Existing offline URL policy excludes unsafe targets without DNS/network access. Canonical display locators strip query/fragment, flag this loss, and deduplicate first-ranked hits conservatively; distinct query resources may collapse. Redacted locators are not equivalent fetch targets. No public-DNS claim is made, and a later authorized fetch still needs full safe_fetch validation.

Offline acceptance covers valid/empty/oversized queries, zero results, caps/order/duplicates, malformed replies, backend timeout/error redaction, unsafe URLs, missing metadata, injection-looking text, credential/config isolation, unknown args, planner discovery-vs-fetch distinction and regressions for the five pre-M7-22 tools; M13-04 subsequently verifies seven-factory coexistence. Only test-injected backends run.

**Before final submission/demo acceptance, at least one real production search backend must be configured and a live hidden-like web search smoke must PASS.** The separately triaged [production acceptance record](ROADMAP.md#web-search-production-acceptance) must cover official endpoint/auth/config, retention/privacy, network policy, real adapter and sanitized unseen-query evidence. Q-NET-01/02 remain open. Offline completion alone never satisfies production acceptance.

Under [DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime), SearXNG is the preferred production-search compatibility candidate only: no concrete backend is integrated or live accepted. Self-hosting may forward queries to upstream search engines, so privacy/retention and organizer/network approval remain open. It is separate from the structured lakehouse data path.

`web_url` remains the supplied/authorized URL extractor with its existing static/document support. Crawl4AI is only an optional future candidate for insufficient static extraction or dynamic/JS pages, not a selected replacement. Any candidate must retain URL authorization, SSRF/private-address checks, redirect/TLS validation, size/time bounds and source/value proof. Search results do not grant fetch authority; that product/security expansion remains undecided.

### 5. Source discovery and adapters — CONFIRMED abstraction

- Responsibility: Discover/inspect/load/profile a source through the common data boundary and return source provenance.
- Input: Bounded search/selection arguments, allowed source capabilities, approved data/source references.
- Output: Candidate IDs, DataContract, loaded data reference, profile, SourceRef.
- Must NOT: Make the core depend on BDDK/EVDS naming, invent missing units, bypass safe fetch/file guards, or execute document instructions.
- Likely failures: Unknown/ambiguous series, schema drift, unavailable source, revisions, empty range, unexpected content type.
- Validation expectations: Synthetic discovery/load fixtures, wrong-near-match selection tests, unfamiliar schemas, source outage, and stable provenance.

TARGET operations are discovery, inspection, loading, profiling and provenance. A shared SourceAdapter protocol remains unimplemented; M3-06 supplies the bounded BDDK Monthly primitive described below and M3-07/08 a bounded reviewed EVDS `fe` primitive ([contract](EVDS_SERIES_METADATA.md)); both are live-accepted for their first series. The dated DEC-137 refinement prioritizes prepared-pool build/refresh; runtime official cache-miss loading remains future scalability, not a core-demo prerequisite. All observations reach analytics through validated lakehouse materialization. [INGESTION_PROFILE](INGESTION_PROFILE.md) specifies observable results; an executable shared adapter/selection interface remains implementation work. Adapters unable to discover (for example, a single uploaded file) should report unsupported capability explicitly rather than invent source candidates.

M3-05 now provides an [offline monthly BDDK selector/metadata contract](BDDK_MONTHLY_METADATA.md): deterministic internal identities for explicit selectors and reviewed CatalogRecord declarations only for table 4 / housing row 2 / Sektör 10001 / TL presentation, retaining TP/YP/TOTAL. A separate bounded metadata projection validator checks the documented caption/period/headers/row. That M3-05 metadata slice adds no values or runtime/catalog_search registration. M3-06 subsequently delivered bounded offline request/response parsing, bronze snapshots, manifest and atomic silver/lineage materialization; general M3-05/M3-06 remain PARTIAL. Live BDDK/CA and real pool preparation remain unaccepted.

### 6. Safe ingestion, extraction, and profiling — partial implementation; confirmed boundary

- Responsibility: Validate and bound content, extract observations, and describe data quality without silently deciding financial meaning.
- Input: Guarded upload/fetched bytes, explicit selection such as sheet/table/page, parser limits.
- Output: Original-data reference, profile, source fragment references, extraction warnings, candidate schema mappings.
- Must NOT: Execute formulas/macros/scripts, fetch embedded resources without authorization, write to supplied paths, or convert OCR uncertainty into verified numbers.
- Likely failures: Empty/corrupt/oversized file, ambiguous delimiter/date, archive expansion, multi-sheet ambiguity, scanned PDF, missing table.
- Validation expectations: Exact row/type expectations; empty/malformed/oversized/content-mismatch negatives; sheet/page lineage; hostile-text cases.

Spreadsheet reading is split by trust boundary, not by file type. The TARGET operator-ingestion path for recorded BDDK/EVDS sources will read with Pandas and calamine under DEC-114. A file named by a user, a model or a prompt-supplied URL goes through the M1-10 bounded loader under DEC-111, with admission checks, streamed package validation, resource budgets and a terminated worker. The rule is the provenance of the request to read, never the extension. Both target paths must retain original bytes/hashes and enforce SEC-URL/SEC-FILE limits; a familiar source is not trusted content. The operator path is not yet implemented.

Generic path: identify supported format -> enforce guards -> parse bounded content -> profile -> propose mapping -> confirm required semantics. Unknown source but supported format uses this path. Unknown format returns an unsupported-format outcome; it does not trigger code generation or unbounded scraping. CURRENTLY IMPLEMENTED: [admission](../src/kkb_agent/ingestion_policy.py), [sheet selection](../src/kkb_agent/xlsx_sheets.py), the [bounded XLSX loader](../src/kkb_agent/xlsx_loader.py) and the [bounded CSV loader](../src/kkb_agent/csv_loader.py) (M1-06: explicit delimiter, strict UTF-8, no guessed dates, units or frequency). The [bounded PDF loader](../src/kkb_agent/pdf_loader.py) (M7-09/M7-10) returns page text, a text-layer flag and ruled tables with page coordinates and literal cells, and refuses encrypted, malformed and text-less PDFs with fixed codes. Date/numeric profiling remains target work. Static HTML is implemented in M7-07; optional untrusted OCR text is implemented offline in M7-11. OCR requires bounded PDF-to-page-image rendering where needed, the organizer's exact prompt/`extra_body`, and handling of untrusted layout-tag output; availability does not bypass file limits or prove numeric extraction.

CURRENTLY IMPLEMENTED: [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py) supplies bounded HTTP/HTTPS GET with 301/302/303/307/308 redirects (M7-04), fresh validated DNS-to-socket binding and hostname-verified TLS per hop. Redirects share one total deadline/worker and header budget; only the final body is read under the existing byte/decompression/media limits. Loops, hop overflow, malformed Location values and HTTPS downgrade fail closed; only fixed safe GET headers are rebuilt. `web_url` retains the original requested-source identity and content hash while recording the final locator with query/fragment removed. POST/form requests and source-specific trust configuration remain incomplete. A fetched CSV/XLSX/PDF passes the same admission checks and loaders as an upload through [load_fetched](../src/kkb_agent/ingest/fetched.py) (M7-08/M7-09), chosen by the validated response media type, never the URL; the [`web_url`](../src/kkb_agent/tools/web_url.py) tool (M7-17) reaches it only for an address written in the user's question. Static HTML has a bounded parser route (M7-07); JavaScript rendering and image-address loading remain unsupported. Live exposure still needs source/network permission.

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

Exposed to the planner as the brief-named [`change_detection`](../src/kkb_agent/tools/change_detection.py) tool (M6-22), which reads the declared semantics and observations from the lakehouse, records lineage for a computed comparison and none for a refused one, and names its `operation` so breakpoint detection can join the same schema without being implied by the tool's name before it exists. That historical change added no seventh tool; M13-04 subsequently adds catalog_search under DEC-133.

CURRENTLY IMPLEMENTED: [core/results.py](../src/kkb_agent/core/results.py) defines what a tool returns — `AnalyticalResult` with typed `ResultValue`s, explicit `Period`s, `SampleCounts`, warnings, limitations, `unresolved_semantics` and `ResultEvidence` references, under `ResultKind`/`ResultStatus`. Three refusals are structural: a value states its unit or the result declares what is unresolved (`DIMENSIONLESS` is not the same as unknown); a non-COMPUTED result carries no values and names what stopped it, keeping INSUFFICIENT, UNDEFINED and ABSTAINED distinct; and an association, lag or causality result must state limitations, which puts DEC-120 in the type system. `digest()` hashes content excluding the caller's `result_id`, which is the identity M5 needs to reject a stale read and M8 needs to detect an altered result. `lakehouse` is the first producer (M6-21). [tools/_projection.py](../src/kkb_agent/tools/_projection.py) maps a validated query onto that contract by **reading the semantics the lakehouse already stores** — `silver_series` records unit, scale, frequency, anchor and observation kind as exact enum values — and declaring every semantic the query did not select rather than inferring one. Two refusals live here rather than in the SQL gates, which were never meant to catch them: a query reading **no lakehouse table** abstains, so `SELECT 42 AS value` cannot mint a figure; and a query with no `value` column abstains as a listing. Since M6-23, reading an allowed table is not provenance on its own: [_projection_provenance.py](../src/kkb_agent/tools/_projection_provenance.py) admits only direct `silver_observations`/`silver_series` columns joined on `series_id`, then rechecks every returned row against its stored identity, value and semantics through fixed SQL, so literal, computed, aggregated or otherwise derived measurements abstain instead of becoming COMPUTED. The tool returns [LakehouseOutput](../src/kkb_agent/tools/lakehouse.py), keeping the verifiable `result` and the presentation `table` apart so a rendering convenience cannot become an analytical claim.

The four analytical tools emit typed analytical results, consumed by the result verifier and answer gate. `web_url` returns a loaded table or document, and a result only for one named cell: its unit and scale are what the column header states in parentheses, its period is a full date written as the row label, and anything unstated stays unresolved. Under DEC-132, exact source quotation may pass with a resolved literal cell proof; analytical interpretation still cannot (M7-18); `web_search` produces discovery metadata only and never an AnalyticalResult. The verifier resolves preserved table/lineage references on this path; complete source/run/transformation resolution remains M8-04. A matching digest is not a proof of correctness.

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

M8-20 separates that writer context from the trusted value. [`presentation.py`](../src/kkb_agent/agent/presentation.py) supplies a deterministic Turkish `display` phrase: integer-valued floats keep all integer digits with dot grouping; fractions use six significant digits, a decimal comma and fixed notation. A lone comma with exactly three fractional digits retains an extra zero (`1,2340`) to avoid the existing parser's grouping interpretation. No scaling or calculation occurs: `767314.0` at million TRY displays as `767.314 milyon TL`, and `4.447201536789372` percent as `4,4472 yüzde`. Unit labels reuse the verifier's bounded vocabulary; unknown/unsupported unit or scale gets `display UNAVAILABLE`, with canonical metadata retained. The writer sees the display instead of the raw float and is told to copy it verbatim. This prompt is not enforcement: the actual draft still passes through the unchanged result-bound gate, using the original value, identity, period and evidence. Tolerance remains `5e-4` relative plus the existing `1e-9` absolute floor; `4,45` against that rate is withheld. No `ResultValue`, digest or provenance mutation, arbitrary-unit localization or general prose verification is introduced.

M8-17 makes the gate work over **several named results** — `verify_claims` and `gate_answer` accept one result, a sequence, or a workspace-name mapping, and `Session.answer` gates over `Workspace.values()` merged with the current turn's. That is what makes the reference scenario's table answerable: a sentence citing housing credit beside its rate binds both numbers instead of withholding itself. Disqualification is **per result**: a broken column faults exactly the numbers resting on it, reported under its own name, while a sound column still reports; only when every result is disqualified does the prose fall too. Stale columns never enter, because `values()` excludes them.

M5-21 moves trusted workspace publication after the final gate. `Workspace.preview` snapshots the candidate and surviving named values in memory using the same definition/identity rules as `define`; dependents that a successful replacement would invalidate never enter the writer/gate view. Only successful execution, an ACCEPTED answer and candidate-level result verification permit `Workspace.publish`. QUALIFIED remains displayable but does not publish. A short native DuckDB transaction on its own connection atomically stores the result/artifact/binding/history and stale changes, with workspace state checks before writes and a fresh committed-state check before commit. Caller transactions are not committed or rolled back; writer/provider/verifier work occurs before the transaction. This protects publication, not arbitrary tool side effects, earlier lineage writes, general proof strength or the unfinished planner/workspace reference integration.

M8-21 additionally requires producer-recorded execution evidence for every COMPUTED `ANALYTICAL_VALUE`. The four trusted numeric tool implementations (`lakehouse`, `change_detection`, `anomaly`, `causality`) alone call the private persistence helper after their actual computation. Existing lineage tables hold content-addressed input snapshots and an execution node with producer identity, invocation arguments, ordered input references and the complete output/semantics snapshot. `ResultEvidence.evidence_ids` carries one `execution:<node-id>`; a producer invocation identity in `run_id` also binds the input snapshots and invocation arguments, preventing reference substitution between events with identical outputs but different inputs. This is producer execution identity, not a new Session run manager. The snapshot excludes only the execution self-reference, leaving the existing result digest algorithm and legacy serialization unchanged. The resolver checks node types, content addresses, input edges and exact output equality through a fresh reader; missing, corrupted, copied, uncommitted or mismatched evidence cannot authorize an answer/publication. A table/node name, declared run or self-computed result digest is insufficient.

Input snapshots preserve the buffers actually passed to analytics, source series/artifact identities, periods, nulls and declared semantics; invocation arguments and output parameters preserve selection/method policy. Lakehouse snapshots come only from the existing successful direct-column/stored-row provenance check. Document literal proof remains a separate mandatory cell/source/hash path. No generic constructor, collector, workspace store or verifier issues execution evidence. Source snapshots stay in the local evidence store, not writer prompts or ordinary logs. This establishes correspondence to trusted producer execution, not independent recomputation, source reconciliation, complete replay or new freshness/coverage guarantees; application code and database writers remain trusted. Old workspace/history records remain inspectable and unchanged but require valid evidence for newly trusted numeric reuse. Pure analytics calls and calls without a resolvable committed evidence store no longer suffice for analytical answer acceptance.

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

M10-01 specifies the [operator flow and API boundary requirements](OPERATOR_FLOW.md). It adds no running API. Session-scoped result identity, safe SSE, canonical table values and bounded DEC-118 evidence projection must be implemented before the client consumes them; no global Session or unrestricted Lineage.trace export. “Why this number?” presents existing recorded evidence without upgrading verifier state.

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

M6-25 `change_detection` `co_movement` answers the organizer's Turn 1: both series on months (a weekly series reduced with its declared aggregation and a planner-stated `week_assignment`, recorded as a transformation; incomplete months excluded), monthly levels, month-over-month changes (points for rates, net stock change for balances) and the period ends where the driver fell while the target did not rise. Levels keep series ids so the store recheck re-reads them; derived values use distinct labels and every value appears once, because a duplicate would make a quote ambiguous. Plans are one-shot and cannot pass catalog_search output to later steps, and BDDK ids are opaque hashes, so tools describe the prepared series they can read with reviewed names ([prepared_series](../src/kkb_agent/ingest/prepared_series.py)); the writer sees the same names and highlighted periods. The answer gate treats every line break as a claim boundary, so table rows and list items are verified against their own periods. M6-14 adds a deterministic period table: `Session.answer` lays out a fault-free, non-abstained result's per-period values from its own display phrases and returns them beside the prose (`Answered.tables`); the writer is told the table is shown separately and reads only summaries and highlighted-period values, while the gate still binds against the whole result. M5-20 registers `table_transform`; `deflate` (M2-15) reads a published workspace result by name, keeps every value exactly, adds one real column (`nominal × index[reference] / index[t]`, explicit month-end reference, monthly INDEX with base year, currency stock/flow only, missing index months left missing), replaces the nominal limitation, and records the transformation, lineage and M8-21 execution evidence with the source result as input. The planner sees published result names, coverage and column labels (never values) from the workspace; a transform that kept all of its source's values supersedes that source in the answer's view, so identical copied figures are not ambiguous. The gate treats year-months and period ranges as calendar tokens and headers. Live evidence is in [EVALUATION](EVALUATION.md#m6-25-organizer-turn-1-live-run-2026-09-14).

M12-08 weekly requested-boundary coverage requires `requested_start` and `requested_end` in `to_monthly`. Expected source period ends are generated independently of supplied rows, using the declared weekly anchor and inclusive period-end selection. All supplied rows still undergo duplicate/calendar validation; only ends inside the window contribute to counts and unchanged reducers. BY_END and BY_MAJORITY group expected and observed weeks identically, retaining neighbouring-month assignments. Every requested month has coverage even with no data or no expected anchor; no empty value is synthesized. `Coverage.complete` remains false for zero expectation. Completeness describes the requested source window, not automatically a full target month; the existing method dictionary records both requested dates, frequency, anchor and assignment. The strict weekly/month-based spine contract is unchanged. Daily/business-day/holiday/twice-monthly/irregular calendars remain unsupported; this does not add an adapter, table_transform, quality harness or automatic organizer Turn 1 integration. Gold column completeness still describes monthly cell presence, not upstream weekly completeness.

TARGET normalization scope (only the implemented subset identified above may be claimed): Cumulative detection and correction handles both forms the brief names: series cumulative since first publication, and series that reset each January. Frequency alignment maps daily, weekly and monthly sources onto one canonical spine. The aggregation policy lives in each series' metadata rather than in code — a stock series aggregates to period end, a flow series sums, a rate series uses the rule its metadata names — because hard-coding it is how a credit stock silently becomes a sum. Unit and scale normalization is mandatory metadata; thousand-versus-million confusion is the classic BDDK error. None of these transformations merges without unit tests.

TARGET adapters must retrieve/catalog series identifiers instead of hard-coding runtime selections. Example identifiers in source inventories are evidence, not an implemented selection policy.


M5-20 `add_series` adds a registered monthly series to a published table through the same tool. Its closed argument object contains only operation, source and series_id; deflate keeps its existing flat JSON fields in a separate discriminated schema. Before adding values, the tool rechecks the source result's evidence and reads the selected series' declared semantics. The join accepts resolved monthly, non-cumulative series, validates periods and duplicates, and preserves the displayed table's exact row set and all original values. Single-period prose metrics do not define table rows. Missing observations produce empty cells plus explicit warnings/coverage in the transformation record; zero stays zero. No filling, resampling, conversion or rebasing occurs. At least two matching observations are required by the current period-table renderer. The result records units, scale, measurement kind, index base, source/series snapshots and transformation lineage. Prior comparison metrics retain their original meaning; column addition does not calculate a new relationship.

For successive table transforms, the answer view follows declared source ancestors only while all their values are exactly preserved by the final result. This avoids copied amounts becoming ambiguous on Turn 3. Ancestors stay in the workspace, unrelated analyses stay visible, and the walk terminates on missing/self/cyclic or non-preserved references. This is bounded answer-view narrowing, not completion of general publication dependencies, stale-input invalidation or the M13-13 inspection harness.

M6-25 `table_co_movement` consumes either a published `source` table or an earlier tool's `input_step`, never both. The latter must also appear in `depends_on`: an optional registry-owned `ToolSpec.required_steps` callback enforces argument references during whole-plan validation, before any tool runs. The existing executor stores successful outputs by step ID and orders dependencies; the receiving tool then requires a computed `AnalyticalResult` whose execution/store evidence passes `result_faults`. This is one typed table consumer, not a generic catalog-result replanner or completion of all output ownership/staleness contracts.

The operation selects two exact monthly STOCK/RATE/INDEX column labels and explicit directions (`up`, `down`, `unchanged`, `non_increasing`, `non_decreasing`), optionally restricted by a third column/direction. Flow columns are refused until their accumulation semantics can be inspected. Each transition needs all selected values in the current and preceding calendar month; missing months are never bridged. The result preserves every table value and adds six dimensionless counts: complete/excluded transitions, condition-eligible transitions, and eligible driver/target/joint matches. Zero eligible periods means zero counts, never a percentage or causal estimate. Comparison-specific labels avoid collisions; exactly repeated criteria are refused. Criteria, qualifying dates, denominators and source snapshots are retained in transformation/execution evidence and supplied to the writer. `live_check --turns 3` additionally requires publication and the actual KFE/real-credit/rate-condition calculation; merely adding a column or writing an unsupported explanation does not pass the operator rehearsal.

### 13. Semantic catalog and retrieval — confirmed baseline; benchmark-gated extensions

DEC-137 separates trusted **local/versioned catalog metadata and discovery** from **observation availability/materialization and lakehouse queries**. Approved reusable source adapters primarily populate the prepared official pool. Demo catalog routing is concept → trusted prepared candidate → lakehouse; a pool miss may clarify/abstain. Official adapter filling of known requested-window misses is future scalability, not a core demo prerequisite. catalog_search consumes reviewed catalog state; it does not fetch observations or invent IDs. The M13-08 demo snapshot is not a permanent full-catalog ceiling: reviewed aliases are precision shortcuts, not the only catalog knowledge. Broader versioned BDDK/EVDS metadata coverage is intended later and remains unimplemented; unseen concepts may use catalog retrieval without an exact alias, while unsupported identities remain unresolved.

TARGET under [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline), superseding DEC-127; DEC-115 remains historical. M13-04 supplies the reviewed offline lexical stage; dense and full hybrid retrieval remain unimplemented.

Mandatory HYBRID baseline: one Turkish normalizer shared by query/index paths, reviewed aliases/concept families, metadata filters, lexical/BM25 and dense semantic retrieval using the organizer's Qwen3-Embedding-8B (exact model/endpoint in DEC-129). DEC-138 selects LanceDB as the catalog vector index, keyed by series/concept ID, catalog text hash, model ID and dimension, with deterministic ranking tests. The confirmed model is `kkbhackathon2026/Qwen3-Embedding-8B`, measured at 4096 dimensions. Vectors index descriptions/aliases/concepts, never financial observation values; those remain DuckDB/Parquet. Dense retrieval starts in the baseline without waiting for lexical failure or a prior gain measurement. Candidates retain IDs, original titles, source, unit/scale/frequency, coverage and archived/unknown flags. Exact aliases do not bypass ambiguity or semantic checks.

#### Intended catalog vector-search boundary (not implemented)

The final dense architecture includes a separate logical **vector DB / vector index layer** for catalog embeddings. The bounded [M13-05 local index](CATALOG_INDEX.md) now persists reviewed representations and supplied vectors in pinned LanceDB 0.38.0, validates snapshot/text/model/input-policy bindings and searches exact cosine over explicit eligible IDs. It contains no financial observations and opens no model/network route. Its real-engine tests use labelled fixture vectors; an optional [combined catalog stage](CATALOG_SEARCH.md#bounded-combined-candidate-contract) now preserves both retrieval paths and explicit degradation. Confirmed live embedding policy and semantic-quality evaluation remain unfinished; the opt-in [bounded planner continuation](CATALOG_CONTINUATION.md) consumes candidate metadata separately from calculations. [DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git) selects this embedded index; no separate vector service is needed. PostgreSQL/pgvector requires a later decision justifying a separate PostgreSQL service.

| Conceptual vector record | Purpose |
| --- | --- |
| Official series ID / canonical selector ID; concept_id / family | Bind similarity candidates back to reviewed catalog identity |
| Normalized catalog/search text; text/content hash | Reproduce the indexed representation and detect text changes |
| Embedding model ID; dimension 4096; embedding vector | Enforce the confirmed Qwen representation contract |
| Catalog snapshot / embedding version metadata | Prevent silent mixing of stale text/model/cache versions |

These are intended records, not an implemented schema or dependency choice.

```text
catalog_search -> shared Turkish normalization / reviewed aliases / metadata filters
  BM25 lexical candidates
  + query embedding via Kloudeks Qwen3-Embedding-8B -> vector similarity candidates
  -> metadata constraints / bounded combined candidates -> trusted identity resolution
  -> prepared lakehouse silver/gold for financial values
```

Dense remains required for final hybrid acceptance. Dedicated-index scaling beyond measured need is later work; RRF/reranking remain separately benchmark-gated. Invalid/unavailable dense output may yield explicitly degraded lexical results, never a falsely successful full-hybrid run.

M13-08 adds a [reviewed offline demo snapshot and exact alias mapping](CATALOG_MAPPING.md) over ten repository-evidenced identities. The shared record/normalizer are reused; unresolved BDDK/CPI identities stay absent. That artifact itself implements no retriever. M13-04 now provides the [bounded lexical catalog_search](CATALOG_SEARCH.md): reviewed alias/phrase sets, provider/frequency/archive filters and deterministic in-memory BM25; no FTS extension or lakehouse security change. Dense retrieval remains M13-05.

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

Apply [SECURITY](SECURITY.md) at source retrieval, upload/parser entry, provider configuration, plan/tool dispatch, evidence logging, and UI output. Data locators are provenance, not execution authority. Source HTTP uses safe fetch, and the `web_url` tool reaches it only for an address written in the user's question; provider HTTP uses an organizer-configured transport that cannot be selected by user/model text. Do not treat URL syntax validation or Pydantic alone as SSRF protection.

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

Decided as of M0-ARCH and no longer open here: orchestration (DEC-113), analytical engine and lakehouse (DEC-112), spreadsheet paths (DEC-111, DEC-114), hybrid catalog baseline and benchmark-gated extensions (DEC-116, DEC-130), workspace persistence (DEC-117), lineage (DEC-118), verification (DEC-119), causality method (DEC-120), tool surface (DEC-121/133), provider interface (DEC-122), API and frontend (DEC-123), dependencies (DEC-124), layout (DEC-125) and deployment topology (DEC-126).

DEC-129 answers Kloudeks endpoint/auth/model availability and listed image limits. Remaining external questions cover OCR access, native tool/JSON guarantees, capacity/quotas/timeouts, the embedding prefix convention and dedicated reranker (Q-K-01..05; the key authenticated live and the embedding dimension is measured at 4096); measured retry/latency budgets; source access/redistribution (Q-DATA-01/03); demo egress (Q-NET-01/02); and runtime/storage (Q-INFRA-01/02), which can override DEC-126. Router fine-tuning and multi-agent topology stay deferred.

### Literal source-value proof (M7-18 follow-up, DEC-132)

`AnalyticalResult.claim_kind` defaults to analytical. Only the deterministic document-cell producer sets literal eligibility. `record_cell` preserves a bounded selected-reading snapshot and a digest of the selected raw cell alongside coordinates/header/row. The verifier rereads the cell and source nodes, checks their content-addressed identities and direct edge, original result ID, selected value/unit/scale/period, source fragment/hash and unchanged coordinates. A flag or source citation alone is insufficient; missing store/snapshot, changed value/cell or transformation fails closed.

For unresolved literals, the writer receives a separate fixed source-quotation sentence and explicit missing-semantics sentence, while analytical display stays UNAVAILABLE. Only that complete quotation (no appended interpretation) can receive the semantic exemption. `live_check` already counts supported retained result-bound claims and therefore needs no separate verification pipeline. Literal permission does not transfer to later analytics: unknown analytical values remain unsupported. One unresolved literal per answer is the current bounded scope; arbitrary paraphrases and multi-literal synthesis are not enabled. Internal proof handles are withheld from document answer text.

### M7-11 bounded OCR text fallback

`load_pdf(..., ocr=provider)` and `make_web_url_tool(ocr=provider)` explicitly opt into OCR. Native PDF text/tables remain first choice; only pages with no text layer render through the installed pypdfium2, inside the existing terminated PDF worker. Defaults: 30 total PDF pages, 10-second parse/render deadline, at most 3 OCR pages, 2x render scale, 4 million pixels and 8 MiB PNG per page. Oversized pages are rejected, not silently downsampled. Worker output/address-space limits remain; PNGs are transient and never written to provenance.

`KloudeksProvider.ocr` uses the separately configured `KLOUDEKS_OCR_MODEL` (exact DEC-129 Unlimited-OCR ID), fixed prompt, token/temperature and vLLM fields. The HTTP JSON flattens the SDK `extra_body` entries into the body. PDF pages are sent individually, at most 3 calls, no retries, with the existing bounded provider transport. Missing capability, refusal, incomplete/empty output and limits fail closed. Text is capped at 65,536 characters per page (or a smaller admission field cap), layout tokens removed, and kept only in `PdfPage.ocr_text` with `OCR_UNVERIFIED`; native `text`/`has_text` remain unchanged. No OCR-to-table conversion, schema/total-check implementation, analytical result or literal-source eligibility is delivered. Such promotion still requires DEC-119 checks plus exact binding under DEC-132. An OCR-only Session.answer abstains before the writer. No automatic OCR registration in the operator command or live OCR acceptance is claimed.

### M7-07 static HTML documents

`text/html` follows safe_fetch → upload admission → a terminated standard-library `html.parser` worker → HtmlDocument → the existing Grid/cell selection → AnalyticalResult/lineage → writer/verifier. No browser, JavaScript, resource fetch, OCR fallback or parallel analytical pipeline. UTF-8/BOM only; conflicting HTTP or meta charset fails closed. Unknown media is not sniffed into HTML.

The extraction contract is explicitly closed markup, bounded static text (block boundaries retained), and rectangular tables in source order. First row supplies nonempty unique headers; th/td row labels work, empty data cells remain empty. Spans other than 1, nested tables, ragged rows and ambiguous headers are rejected. Text has source-local fragment `text:1`; tables have deterministic one-based IDs and existing row/column cell coordinates. Whitespace/entities are decoded deterministically, never numerically interpreted here. Caption/style metadata cannot supply units. Existing selection rejects duplicate matches across tables; DEC-132 exact literal proof applies unchanged.

Script/style/noscript/head/template/form/iframe/object/embed/SVG/MathML content is excluded, as are explicit hidden/aria-hidden and simple inline display:none/visibility:hidden nodes. Attributes, links, event handlers, meta refresh and resource URLs have no execution/navigation path. This is not CSS layout: computed visibility and browser DOM repair are unsupported. Blank/JS-only shells with no extracted static text return NO_STATIC_CONTENT; a shell with placeholder text still has no usable cell and cannot pass numeric acceptance. No partial tables are published on parse failure.

Defaults reuse admission limits: 10 MiB input, 1 MiB extracted UTF-8 text, 100,000 rows/table, 256 columns, 1,000,000 total cells, 65,536 characters/cell, 256/header, 50 MiB serialized output, 5-second killed/reaped worker and Linux 512 MiB address-space cap. Additional small caps: depth 64 and 20 tables. No live HTML acceptance is claimed.
