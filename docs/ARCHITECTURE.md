# Architecture

This file owns technical structure and contracts. [ROADMAP](ROADMAP.md) owns delivery/status, [DECISIONS](DECISIONS.md) confirmed choices, [SECURITY](SECURITY.md) boundary controls, and [EVALUATION](EVALUATION.md) behavioral validation.

## Reading the design

- **CURRENTLY IMPLEMENTED** describes the source boundaries below; merged revisions, validation and remaining task acceptance are maintained only in [ROADMAP Current Project Status](ROADMAP.md#current-project-status).
- **TARGET / CONFIRMED** describes authorized behavior, not delivery.
- **PROPOSED / BENCHMARK-GATED** needs task review or measured benefit before adoption.
- **BLOCKED BY EXTERNAL ANSWER** names the organizer/platform dependency in OPEN_QUESTIONS.
- **DEFERRED** is outside the core slice unless a later explicit scope decision changes it.

The implemented spine includes bounded file admission, CSV/XLSX loading and safe GET with validated redirects, DuckDB/Parquet storage and financial semantics, typed results, the Kloudeks transport (tested offline; one authorized live smoke and one live end-to-end question passed), validated planning/execution, content-addressed workspace values and multi-result answer gating. Eight callable factories exist: `table_transform` (deflate/add_series), M13-04 `catalog_search` and the six brief tools (search is offline-only): `lakehouse`, `change_detection` (comparison), `anomaly`, `causality` (association, lag and Granger precedence), `web_search` with an explicitly injected backend, and `web_url`, which reads a CSV/XLSX table, a PDF's text and ruled tables, or bounded static HTML text/tables at an address the user wrote, and can return one named cell as a result the answer gate binds. Synthetic tests compose an end-to-end answer with a scripted model. Bounded BDDK/EVDS adapters, the local prepared API and first Next.js client exist. Broader data/semantic coverage, full hybrid acceptance, complete proof/replay, production web search, JS/image-address extraction, benchmark runner, remaining UI and deployment remain incomplete. Day 0 drafts remain outside the shared runtime.

Current stateful boundary: [question submission](../web/lib/client.ts) sends the selected public result reference as `selected_result_id`; the [API contract](ARCHITECTURE.md#local_api-m10-18--selected-result-grounding-merged) resolves session ownership and immutable publication receipts. The prepared runner binds planning, dispatch and publication to that selected source. Retry/reload preserve the original request selection. General refresh invalidation is a separate contract; see [ROADMAP](ROADMAP.md#current-project-status) for remaining acceptance and [EVALUATION](EVALUATION.md#m10-18-browser-selection-2026-09-15) for the dated synthetic browser evidence.

## Goals and non-goals

CONFIRMED goals:

- Handle unfamiliar questions and new-but-supported sources through common contracts.
- Use the LLM for interpretation and planning; use deterministic tools for calculations.
- Make assumptions, transformations, failures, and evidence inspectable.
- Preserve explicit multi-turn analysis state and invalidate dependent results correctly.
- Fail safely when data meaning or execution authority is insufficient.
- Keep the inner loop fast and the demonstration reliable under constrained model access.

[DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria) preserves the own-harness/lakehouse and minimal-model-dependence criteria, retains the historical organizer relay, and clarifies current reuse across supported financial sources, datasets and schemas. Shared ingestion contracts, Bronze/Silver/Gold mechanics, planner/router/executor, registry, workspace/state, lineage/evidence/verifier, API/session, table rendering and adapter interfaces should not require rewriting for each supported financial source/schema. Reviewed adapters and finance semantics, cumulative rules, deflation, KFE, guards/transforms and mappings may remain finance-specific. This is not a healthcare or universal cross-domain platform requirement and does not justify speculative abstractions or a large refactor; new-source acceptance remains to be demonstrated.

Non-goals for this window: arbitrary generated-code execution, a general autonomous web crawler, a hosted warehouse platform, distributed agent infrastructure, enterprise tenancy/security systems, or a training pipeline.

The stack is selected in DECISIONS and is not re-argued here: DuckDB with Parquet and Pandas (DEC-112), a custom bounded loop (DEC-113), initial hybrid retrieval with benchmark-gated extensions (DEC-130; DEC-127/115 superseded), an artifact DAG in DuckDB (DEC-117), FastAPI with SSE behind Next.js (DEC-123), and the excluded-technology list (DEC-124). Router fine-tuning and multi-agent topology remain out of scope.

## Organizer maturity chain

This is the single product-evolution map for the organizer-relayed direction
([DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria)), not a claim that every
stage has passed acceptance. [ROADMAP](ROADMAP.md#current-project-status) owns
completion; [EVALUATION](EVALUATION.md) owns measured proof.

1. **Data dictionary/catalog:** reviewed financial identity, aliases, metadata,
   semantics and provenance establish what a supported series means.
2. **Automated preparation:** catalog identity → trusted adapter → Bronze →
   validation/normalization → Silver → prepared lakehouse (and required Gold).
3. **Automated analysis:** question → catalog discovery → planning → deterministic
   tools → mandatory checks → verifier → result.
4. **Stateful iterative analysis:** preserve the intended existing table, transform
   the requested column, add the requested series, and continue from that exact
   immutable result while retaining untouched values and history.
5. **Reuse across new supported financial sources/schemas:** add reviewed metadata
   and adapter/policy work without rewriting lakehouse mechanics, workspace/state,
   executor, lineage/evidence/verifier or API/session. BDDK/EVDS adapters and
   stock/flow/rate/index, cumulative, deflation and other financial semantics may
   remain finance-specific. This does not promise arbitrary domains or healthcare.

Our analytical lakehouse is **DuckDB + Parquet + our Bronze/Silver/Gold, ingestion
and provenance**. LanceDB is the separate catalog vector index; financial
observations do not move into it.

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

[DEC-137](DECISIONS.md#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) refines DEC-136's prepared-data direction into a catalog-complete, lakehouse-first target. “Catalog-complete” means extensible trusted metadata coverage for safely representable financial measures, not a claim that full coverage is delivered. Bounded Monthly/EVDS adapters have recorded live preparation evidence. Arda's 29-series / 4,124-observation pool is operator-local, absent from fresh Git checkout and not identically repository-reproducible today ([recorded pool](EVALUATION.md#prepared-api-delivery-and-pool-evidence)); broader coverage, availability routing and version/refresh orchestration remain unfinished.

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

The primary structured financial-data path does not fetch BDDK/EVDS at question time. This reduces financial-source network dependence, not the separate Kloudeks requirements of planning and query embeddings. Mandatory metadata inspection, observation-quality/semantic checks and applicable reconciliation run before dependent use, outside planner discretion under DEC-135. Prepared readers/projection now enforce metadata inspection automatically; broader inspection, observation quality and reconciliation remain incomplete. The diagram includes those required target integrations, not new registry tools. A prepared-pool miss may clarify/abstain until the future materialization path is deliberately implemented. It grants no arbitrary web/network authority. A known series with insufficient requested coverage is a miss for that window; observed min/max never establishes full coverage.

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

CURRENTLY IMPLEMENTED: [Session](../src/kkb_agent/agent/loop.py) plans and executes through the registry. `Session.answer` synthesizes computed results and calls the verifier gate; publication requires successful execution, an ACCEPTED answer and verified candidate evidence. It uses current named Workspace values across turns. The opt-in [bounded catalog continuation](CATALOG.md) executes catalog-only discovery and lets one further analysis/clarification plan consume candidate metadata in a data role. Step and repair counts cover both phases; tool retries remain bounded per step. Automatic workspace loading, planner-driven recomputation and total request deadlines/cancellation remain TARGET. A separate cheaper router call remains PROPOSED pending model/latency evidence.

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
| Financial series selected | Deterministic series_inspect: trusted source/ID, frequency, unit/scale, archive, stock/flow/rate, aggregation and coverage | M13-13 mandatory in configured prepared readers/projection; broader wiring incomplete; unavailable metadata stays unknown |
| Observations retrieved for analysis | Deterministic data_quality: bounded missing-period/coverage/gap/frequency/validity checks and supported stale/archive evidence before analysis-ready | M1-12 future wiring; never model confidence |
| Financial transformation | Semantic compatibility guard | Existing semantic guard layer; remaining operation/prerequisite gaps stay explicit |
| Multiple trusted sources/results support the same measure | Conditional deterministic/hybrid reconcile_sources over semantics, period, frequency, unit, scale and values | M8-09 future wiring; CONSISTENT / DIFFERENT / NOT_COMPARABLE / NEEDS_TRANSFORM / NEEDS_INPUT |
| Numeric final claim | Lineage/evidence binding and verifier/gate | Existing result-bound path; a citation or metadata candidate alone is not measurement proof |

The LLM must not skip correctness-critical checks. The first row is auto-wired for the prepared slice; broader inspection, observation quality and reconciliation remain incomplete. Existing guards/security/lineage/verifier remain mandatory system layers; no unfinished control is declared complete. A later explicit user comparison could expose reconciliation if separately designed, without making its correctness trigger discretionary.

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

TARGET operations are discovery, inspection, loading, profiling and provenance. A shared SourceAdapter protocol remains unimplemented; M3-06 supplies the bounded BDDK Monthly primitive described below and M3-07/08 a bounded reviewed EVDS `fe` primitive ([contract](EVDS_SERIES_METADATA.md)); both are live-accepted for their first series. The dated DEC-137 refinement prioritizes prepared-pool build/refresh; runtime official cache-miss loading remains future scalability, not a core-demo prerequisite. All observations reach analytics through validated lakehouse materialization. [INGESTION_PROFILE](ARCHITECTURE.md#ingestion_profile-m1-01--ingestionprofile-result-specification) specifies observable results; an executable shared adapter/selection interface remains implementation work. Adapters unable to discover (for example, a single uploaded file) should report unsupported capability explicitly rather than invent source candidates.

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

M10-01 specifies the [operator flow and API boundary requirements](ARCHITECTURE.md#operator_flow-m10-01--operator-flow-and-api-boundary-requirements). [M10-16](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results) implements a local FastAPI factory with closed version-one payloads, session capabilities, bounded single-worker admission and exact published-value projection. SSE reports actual turn lifecycle; full plan/tool callbacks remain pending. The [prepared runner/startup](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) now supplies inspected per-session copies and Session publication. The first Next.js client is delivered; bounded DEC-118 proof traversal remains unfinished; no global Session or unrestricted Lineage.trace export. “Why this number?” will present recorded evidence without upgrading verifier state; the current response explicitly reports proof graph unavailable.

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

For successive table transforms, the answer view follows declared source ancestors only while all their values are exactly preserved by the final result. This avoids copied amounts becoming ambiguous on Turn 3. Ancestors stay in the workspace, unrelated analyses stay visible, and the walk terminates on missing/self/cyclic or non-preserved references. This is bounded answer-view narrowing, not completion of general publication dependencies or stale-input invalidation. The M10-18 backend merged in PR #166 (`de11f3e`) adds explicit selected-table grounding: registry-owned table-input declarations constrain every calculation to the pinned workspace source or its derived step, with dispatch/source rechecks and an atomic publication input edge. The selected answer view excludes unrelated results and deduplicates preserved source values even across step-derived results. Rebinding the selected workspace source invalidates dependent selected publications; legacy/non-selected paths and official-data refresh invalidation remain separate. The prepared API and frontend submission/retry/reload are wired in PR #166; synthetic selected-flow browser acceptance passed on 2026-09-15, while live acceptance remains pending. Prepared metadata inspection is separately enforced by the M13-13 slice.

M6-25 `table_co_movement` consumes either a published `source` table or an earlier tool's `input_step`, never both. The latter must also appear in `depends_on`: an optional registry-owned `ToolSpec.required_steps` callback enforces argument references during whole-plan validation, before any tool runs. The existing executor stores successful outputs by step ID and orders dependencies; the receiving tool then requires a computed `AnalyticalResult` whose execution/store evidence passes `result_faults`. This is one typed table consumer, not a generic catalog-result replanner or completion of all output ownership/staleness contracts.

The operation selects two exact monthly STOCK/RATE/INDEX column labels and explicit directions (`up`, `down`, `unchanged`, `non_increasing`, `non_decreasing`), optionally restricted by a third column/direction. Flow columns are refused until their accumulation semantics can be inspected. Each transition needs all selected values in the current and preceding calendar month; missing months are never bridged. The result preserves every table value and adds six dimensionless counts: complete/excluded transitions, condition-eligible transitions, and eligible driver/target/joint matches. Zero eligible periods means zero counts, never a percentage or causal estimate. Comparison-specific labels avoid collisions; exactly repeated criteria are refused. Criteria, qualifying dates, denominators and source snapshots are retained in transformation/execution evidence and supplied to the writer. `live_check --turns 3` additionally requires publication and the actual KFE/real-credit/rate-condition calculation; merely adding a column or writing an unsupported explanation does not pass the operator rehearsal.

### 13. Semantic catalog and retrieval — confirmed baseline; benchmark-gated extensions

The [M13-13 prepared inspection](ARCHITECTURE.md#series_inspection-prepared-series-metadata-inspection) compares exact reviewed IDs and required declarations against local silver metadata. Catalog-configured prepared factories enforce it before selected-series calculation or direct-silver numerical promotion, recording a receipt in execution evidence. It is never a planner tool; generic input guards remain, and full-source quality, user-intent disambiguation and cross-turn staleness are still separate.

DEC-137 separates trusted **local/versioned catalog metadata and discovery** from **observation availability/materialization and lakehouse queries**. Approved reusable source adapters primarily populate the prepared official pool. Demo catalog routing is concept → trusted prepared candidate → lakehouse; a pool miss may clarify/abstain. Official adapter filling of known requested-window misses is future scalability, not a core demo prerequisite. catalog_search consumes reviewed catalog state; it does not fetch observations or invent IDs. The M13-08 demo snapshot is not a permanent full-catalog ceiling: reviewed aliases are precision shortcuts, not the only catalog knowledge. Broader versioned BDDK/EVDS metadata coverage is intended later and remains unimplemented; unseen concepts may use catalog retrieval without an exact alias, while unsupported identities remain unresolved.

TARGET under [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline), superseding DEC-127; DEC-115 remains historical. M13-04 supplies the lexical stage; local LanceDB search and optional hybrid composition are implemented. Default prepared API retrieval is lexical, without real Qwen embedding injection; live semantic-quality acceptance remains unfinished.

Mandatory HYBRID baseline: one Turkish normalizer shared by query/index paths, reviewed aliases/concept families, metadata filters, lexical/BM25 and dense semantic retrieval using the organizer's Qwen3-Embedding-8B (exact model/endpoint in DEC-129). DEC-138 selects LanceDB as the catalog vector index, keyed by series/concept ID, catalog text hash, model ID and dimension, with deterministic ranking tests. The confirmed model is `kkbhackathon2026/Qwen3-Embedding-8B`, measured at 4096 dimensions. Vectors index descriptions/aliases/concepts, never financial observation values; those remain DuckDB/Parquet. Dense retrieval starts in the baseline without waiting for lexical failure or a prior gain measurement. Candidates retain IDs, original titles, source, unit/scale/frequency, coverage and archived/unknown flags. Exact aliases do not bypass ambiguity or semantic checks.

<a id="intended-catalog-vector-search-boundary-not-implemented"></a>

<a id="catalog-runtime-composition"></a>

#### Catalog vector-search boundary: local index implemented, live acceptance pending

The final dense architecture includes a separate logical **vector DB / vector index layer** for catalog embeddings. The bounded [M13-05 local index](CATALOG.md) now persists reviewed representations and supplied vectors in pinned LanceDB 0.38.0, validates snapshot/text/model/input-policy bindings and searches exact cosine over explicit eligible IDs. It contains no financial observations and opens no model/network route. Its real-engine tests use labelled fixture vectors; an optional [combined catalog stage](CATALOG.md#catalog_search-bounded-combined-candidate-contract) now preserves both retrieval paths and explicit degradation. Confirmed live embedding policy and semantic-quality evaluation remain unfinished; the opt-in [bounded planner continuation](CATALOG.md) consumes candidate metadata separately from calculations. [DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git) selects this embedded index; no separate vector service is needed. PostgreSQL/pgvector requires a later decision justifying a separate PostgreSQL service.

| Conceptual vector record | Purpose |
| --- | --- |
| Official series ID / canonical selector ID; concept_id / family | Bind similarity candidates back to reviewed catalog identity |
| Normalized catalog/search text; text/content hash | Reproduce the indexed representation and detect text changes |
| Embedding model ID; dimension 4096; embedding vector | Enforce the confirmed Qwen representation contract |
| Catalog snapshot / embedding version metadata | Prevent silent mixing of stale text/model/cache versions |

These logical fields are bound by the implemented local index/profile contracts in [local index contract](CATALOG.md#catalog_index-inputs-and-storage); they do not imply a live embedding generation or query path.

```text
catalog_search -> shared Turkish normalization / reviewed aliases / metadata filters
  BM25 lexical candidates
  + query embedding via Kloudeks Qwen3-Embedding-8B -> vector similarity candidates
  -> metadata constraints / bounded combined candidates -> trusted identity resolution
  -> prepared lakehouse silver/gold for financial values
```

Dense remains required for final hybrid acceptance. Dedicated-index scaling beyond measured need is later work; RRF/reranking remain separately benchmark-gated. Invalid/unavailable dense output may yield explicitly degraded lexical results, never a falsely successful full-hybrid run.

Historical v1 reference: M13-08 added a [reviewed offline demo snapshot and exact alias mapping](CATALOG.md#catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping) over ten repository-evidenced identities. The shared record/normalizer are reused; unresolved BDDK/CPI identities stay absent. That artifact itself implements no retriever. M13-04 now provides the [bounded lexical catalog_search](CATALOG.md): reviewed alias/phrase sets, provider/frequency/archive filters and deterministic in-memory BM25; no FTS extension or lakehouse security change. Dense retrieval remains M13-05.

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


### M10-03 local client delivery

The [first local client](OPERATIONS.md#local_client-datatrio-local-analysis-workspace) lives in `web/`: Next.js, Tailwind,
shadcn-style Radix/CVA components and TanStack Table. Its bounded same-origin
JSON bridge reaches only a fixed operator-configured loopback Python API.
The browser owns presentation and a per-tab session capability; Python owns
question execution, deterministic calculations, inspected tools, publications
and canonical cells. No browser model client or secondary calculation path
exists. Model/planner failure stays an explicit API result, not a fallback.

Actual lifecycle states are polled; tool-stage SSE is not implied. Immutable
result versions and recorded cell metadata can be inspected. Source refresh,
uploads, charts/export, full claim/proof traversal, writable settings, cancel
and hosted authentication are not part of this first slice. Scripted real-pool
browser rehearsal proves client wiring, not live-model reasoning.


## Local API contracts


<a id="local_api-m10-16--version-one-local-api-and-owned-results"></a>

### M10-16 — Version-one local API and owned results

The first HTTP implementation of [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end)
provides a FastAPI factory, process-local session capabilities, bounded turn
execution and explicit published-result projection. This is **not a deployed
service**. [M10-17 startup](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) now supplies the inspected prepared
Session runner and an explicitly enabled loopback launcher. Tests use scripted execution.
[OPERATOR_FLOW](ARCHITECTURE.md#operator_flow-m10-01--operator-flow-and-api-boundary-requirements) retains the wider target requirements.

<a id="m10-18--selection-admission-and-workspace-resolution-partial"></a>
<a id="local_api-m10-18--selected-result-grounding-merged"></a>

### M10-18 — selected-result grounding (merged)

PR #163's admission slice is merged. `selected_result_id` is a published API
`result_ref`, not an internal workspace name or digest. Authentication comes
first. Admission resolves exactly one completed, ACCEPTED result in the same
session and pins its source turn, public reference and version. Unknown,
foreign, unpublished or ambiguous references return `invalid_result` (422)
without admitting work. Missing/null selection retains the original runner
behavior; an identical retry never runs again.

[PR #166](https://github.com/cagatayeroglu/KKB-DataTrio/pull/166) records a
process-local receipt only after prepared workspace publication and successful
API projection. Session, turn, public reference and result version bind the
exact workspace name and artifact. Existing session/turn limits bound receipts;
there is no restart recovery. Duplicate published turn IDs cannot overwrite them.

`PreparedRunner.resolve_selection` is a read-only worker helper. It resolves
only an owned receipt, rejects stale/missing/rebound artifacts, checks artifact
definition and stored result hashes, and returns a fresh snapshot. Older
publications remain selectable while their own bindings are unchanged and
non-stale. This helper is not an execution lease or renewed verifier approval.

The prepared launcher now injects `PreparedRunner.selected` as `selected_runner`.
That entry resolves the receipt again and runs the turn under the same runner
lock and owned connection. Stale/changed selections fail the admitted turn with
`invalid_result` before model execution. This differs from unknown/foreign
public references, which admission rejects with HTTP 422 before creating a turn.
Custom services without a selected handler still fail closed with HTTP 503.

The mandatory selected-table harness uses registry-owned `ToolSpec.table_input`
declarations, never a model's claim to have used the right table. Every
calculation must consume the selected workspace name or an explicitly declared
previous step derived from it. Discovery-only catalog plans and clarification
remain permitted. Plan repair is bounded; invalid plans run no valid prefix.
The executor rechecks the plan at dispatch and the pinned source before each
step/retry. Current supported consumers are `table_transform` (deflate/add_series)
and `change_detection` table_co_movement, including a prior transform's step
output. Other analytical operations must clarify until they declare an actual
supported table input; SQL cannot silently rebuild the selection.

Before publication the source is checked again. `Workspace.preview(inputs=...)`
and its existing atomic publish transaction record the selected source artifact
as an input. Rebinding that source invalidates its dependent publications via
the existing DAG. This covers explicit selected-table dependencies, not all
legacy results, independent official-data refreshes or assumption changes.
The writer/gate see only the selected source and its derived result, with exact
copied values deduplicated; mandatory tool evidence and verifier checks remain.
Failed/refused follow-ups do not replace previous published results.

Scripted HTTP and real-tool tests cover older selection, wrong-source repair,
catalog continuation, add-series then table comparison, retries, source changes
and dependency invalidation. PR #166 now also wires frontend selection, immutable
admission/retry identity and exact-reference reload recovery, with automated
client/bridge checks. Synthetic selected-flow browser acceptance passed on
2026-09-15; live Kloudeks selected-table quality remains pending. M10-18 is merged via #166 at `de11f3e`; the selected-flow delivery is DONE.
The broader limits above remain open.
See [client recovery and evidence](OPERATIONS.md#local_client-recovery-and-limits).

<a id="local_api-bounded-lifecycle"></a>

### Bounded lifecycle

| Boundary | Limit |
| --- | --- |
| Sessions / turns | 8 sessions, 24 turns each including failures; no silent eviction |
| Execution | One admitted turn globally on a dedicated worker; no application backlog |
| Question | 4,096 characters and 8 KiB UTF-8; nonblank, no unsupported controls |
| HTTP body | 16 KiB before JSON parsing including chunked bodies; 5-second read deadline |
| Output | Under 1 MiB including wrapper; 2,048 cells; refuse excess, never truncate tables |
| Text | 8,192 characters; labels/units 240; at most 16 bounded notices |
| SSE | One stream per session; three recorded events; 30-second connection window |

The runner owns/opens/closes its database connection on the worker. HTTP
threads never receive a DuckDB connection or global mutable Session. `queued`
means admitted and awaiting that worker. Events preserve the real admitted,
running and completed-or-failed transitions; elapsed time starts at worker
entry, admission is zero. Full plan/tool/gate callbacks remain separate work.
Replay preserves observed times; reconnect using `Last-Event-ID` or poll after
the stream closes. No fabricated tool progress is emitted.

Restart invalidates capabilities and in-memory responses. There is no expiry
scheduler, reset/delete endpoint, automatic file cleanup or durable resume.
Shutdown refuses new work and waits for the existing runner; a Python thread
is not safely killable. Provider/analytic bounds belong to the runner. A
disconnect never cancels or retries analysis. Full wall-clock kill/isolation
remains separate work.

<a id="local_api-canonical-values-and-trust"></a>

### Canonical values and trust

[project_answer](../src/kkb_agent/api/projection.py) takes `Answered` plus the
exact result read from the caller's **own published workspace**. Its digest
must match the last candidate and the answer must be ACCEPTED. Acceptance
alone cannot export candidates. QUALIFIED/ABSTAINED turns return safe answers
and notices without a newly published result in this slice.

Cells retain exact finite values, original slots, optional periods, units,
scales, stock/flow meaning, samples and lag. Display text uses the existing
deterministic formatter. Result version and claim kind survive; literal values
never upgrade unknown unit/scale. Cell/result references derive from the
server-issued turn and immutable result version, stable for repeat reads and
distinct across turns/versions. Clients may lay out cells but must not invent
missing cells or replacement values.

Raw outcomes, rejected sentences, prompts, errors, source locators and
transformation parameters are excluded. Gated prose/labels remain untrusted
text: render text nodes, never raw HTML. Conservative locator/credential
scrubbing and optional known-secret redaction prevent accidental display;
this is not a general secret detector. A production runner must use this
projector instead of raw internal serialization. `proof_graph="unavailable"`
is explicit; stable references are not a fabricated graph or verification
result. M10-08 owns bounded proof traversal; no unbounded Lineage.trace export.


## Prepared runtime


<a id="prepared_api-snapshot-and-session-ownership"></a>

### Snapshot and session ownership

The operator must close ingestion/other writers before startup. The runtime
validates the pool read-only, hashes its files, then copies it exclusively into
a new process-owned directory under `--state-root`. Before/after hashes detect
ordinary concurrent changes; this is not a transactional snapshot of an active
writer or protection from a malicious OS administrator.

Local absolute roots are required internally. Linked paths/junctions, UNC/network
paths, overlapping source/state roots, WAL/unexpected root files, over-deep
directory layouts and pools carrying another workspace's records are refused.
The pool is limited to 1 GiB / 10,000 files; directory visits are bounded too.
Every prepared series must have a consistent reviewed catalog identity. The
bound follows the catalog rather than a hardcoded list of seven series.
Catalog entries without prepared observations remain discovery candidates;
they never trigger silent source fetching. Larger coverage still requires
reviewed preparation/catalog expansion, not a new question argument.

Each server-issued session gets its own copy of the immutable process seed.
New periods appearing in the original after startup do not silently change
that process's analyses. Updating data requires a new validated startup;
automated refresh/version management remains separate. The original and seed
are never written by the analytical tools. There is no automatic deletion or
retention claim. At the initial worst-case cap, seed plus eight session copies
may need approximately nine times the prepared storage, plus derived results;
the expanded 29-series pool is about 8.13 MiB; the earlier seven-series pool was about 7.26 MiB.

The service's single worker opens/closes a session's connection for each turn.
The runner also refuses accidental concurrent entry. It registers inspected
`lakehouse`, `change_detection`, `anomaly`, `causality`, `table_transform`, plus
`catalog_search` and bounded catalog continuation. This prepared mode exposes
no generic web/search/upload tools or provider/gate settings to the caller.
Free catalog metadata remains continuation data, not SYSTEM instructions;
existing code-reviewed display constants are the only names added to tool
descriptions. Dense live retrieval is not silently enabled by this launcher.

Accepted publications receive server-owned names `analiz_1`, `analiz_2`, etc.
Subsequent plans see their own workspace metadata and may reference these names
for deflation/add-series operations. Earlier immutable results survive. Failed
turns may leave a numbering gap, not a fabricated publication. The runner
passes only an exact owned published result to the public projector.

The launcher also wires the [selected-result backend](ARCHITECTURE.md#local_api-m10-18--selected-result-grounding-merged).
An explicit API result reference is resolved to its pinned workspace artifact
under the runner lock; mandatory plan/dispatch checks bind supported table
operations to that source, and successful publications record that dependency.
Older unchanged results can be selected. PR #166's browser client now submits
this field when follow-selection is enabled, persisting the original reference
for retries and restoring the exact view on reload. Automated client/bridge
checks and the dated synthetic browser rehearsal pass; live selected-table
acceptance remains unverified.


## Wider operator-flow target

M10-01 target specification. Absence/prerequisite statements here describe its original scope; current routes and selected-result behavior are defined in the executable API contracts.

<a id="operator_flow-m10-01--operator-flow-and-api-boundary-requirements"></a>

### M10-01 — Operator flow and API boundary requirements

Status: M10-01 operator specification, with [M10-16 local API](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results), [M10-17 prepared runtime](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) and the [first Next.js client](OPERATIONS.md#local_client-datatrio-local-analysis-workspace) now delivered. The flow below includes wider requirements: full plan/tool progress, proof traversal, charts and deployment remain incomplete. Current executable routes and limits belong to LOCAL_API; the client currently exposes the prepared path, not the broader web/document tool surface.

<a id="operator_flow-backend-facts-and-integration-prerequisites"></a>

### Backend facts and integration prerequisites

- [Session.answer](../src/kkb_agent/agent/loop.py) returns Answered(planned, outcome, results, answer). It is synchronous and has no progress callback. Do not pretend post-hoc fabricated events were streamed during execution.
- Its Session has mutable rejection history; a process-global instance cannot be an uncontrolled multi-user session. [Workspace](../src/kkb_agent/agent/workspace.py) scopes bindings by workspace_id but defaults to `default`; this default must never silently identify an HTTP client. A workspace ID alone is not authorization. Some underlying result/artifact/lineage storage is shared, so arbitrary digest lookup is not a safe public API.
- Workspace.store_result/read_result retain and validate content-addressed AnalyticalResult values; artifact value_ref and bindings identify versions. These are the existing result snapshots, not a reason for a second UI result/provenance database.
- M5-21 stages a computed candidate in memory and publishes trusted workspace state only after successful execution, an ACCEPTED answer and candidate-level verification. QUALIFIED/ABSTAINED/errors do not publish. Publication is atomic and rejects changed workspace previews; earlier tool lineage/evidence writes are outside this transaction. The local API projects only gate-backed published results and preserves these failed-turn guarantees; broader proof traversal remains unfinished.
- [AnalyticalResult](../src/kkb_agent/core/results.py) has result_id, digest, run/step IDs, ResultValue entries, evidence, warnings and unresolved_semantics. ResultValue has no universal cell_id. Do not invent a global cell identity from a mutable label or an unrelated lineage node.
- [Lineage](../src/kkb_agent/lakehouse/lineage.py) stores hash-addressed typed nodes and edges. trace currently walks all ancestors; it is not a bounded public graph query. An adapter must bound database reads as well as returned JSON, rather than call trace then truncate.
- The [answer gate](../src/kkb_agent/agent/verifier.py) and [literal proof](../src/kkb_agent/agent/literal.py) remain the authority. API/proof projection must not rerun a weaker numeric matcher or equate a source hash with correctness.

These facts do not block operator-flow specification. They are acceptance requirements for the first API implementation; claiming a deployed/shared session service before satisfying them would be unsafe. Hosting, auth exposure, retention and restart behavior remain constrained by Q-INFRA-01/02, Q-DATA-03 and M10-02; no organizer answer is inferred here.

<a id="public-payload-requirements-for-the-later-typed-api"></a>
<a id="operator_flow-public-payload-requirements-and-implemented-local-api"></a>

### Public payload requirements and implemented local API

The bounded local API now implements versioned Pydantic/OpenAPI contracts, rejected extra fields, explicit nullable fields, finite numbers, body/count limits and fixed errors ([LOCAL_API](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results)). The table retains broader payload requirements; prior-result submission, full proof and charts are not implemented by those contracts. All payloads are JSON data; the UI receives no internal Python objects.

| Payload | Required shape / reuse | What must not be forwarded |
| --- | --- | --- |
| Session | Opaque server-issued session_id; lifecycle/expiry capability stated explicitly; request/result membership checked against that session | Caller-controlled filesystem/database paths; `default` shared workspace; implicit tenant/auth claims |
| Question | question string, session identity; optional owned prior-result reference only where backend supports it | Gate kwargs, provider/model credentials, arbitrary tool definitions or SQL |
| Turn/answer | Opaque turn/result references; AnswerStatus `accepted`, `qualified`, `abstained`; gated text, safe limitations/warnings and bounded tool statuses | Raw Answered dump, omitted sentence text, raw rejections, provider completions or exception strings |
| Result/table | result identity plus immutable version; bounded columns/rows projected from canonical ResultValue data; value separate from optional display text; Period, unit, Scale, sample counts, claim_kind retained | LLM-calculated presentation values, fabricated cells, implicit currency/scale, arbitrary raw SQL-result export |
| Cell reference | Opaque address scoped to session + immutable result snapshot + value slot; selected document coordinates/source fragment retained by existing proof | Row-index/label alone across mutable versions; a hash treated as proof or exposed in answer prose |
| Source/evidence | Bounded safe source label/type, nullable period/semantics, warnings and evidence/proof references | Full locator query/credentials, internal paths, arbitrary node attributes or raw source/provider contents |
| Chart | Optional reference to a trusted result-derived data/spec, absent until supported by M10-07 | Generated Python/JS/HTML, model-executable chart code, an empty chart claimed as implemented |

For DEC-132, preserve `literal_source_value`, unit=null and scale=unknown when that is the source state. The complete bounded source quotation may be supported only after existing exact result/cell/source-fragment proof. Unknown analytical values remain unsupported. A literal figure is not implicitly a verified financial interpretation, and the display must retain the unspecified-unit/scale qualification.

At the HTTP boundary, evaluate a minimal health/readiness response, session creation, question submission and turn retrieval before adding specialized endpoints. Proof/table data may be part of that response or fetched by owned reference; route names are not frozen by M10-01. Do not build upload, chart, reset or graph endpoints just because the eventual UI needs them.

<a id="operator_flow-sessionrequest-isolation-and-failure-lifecycle"></a>

### Session/request isolation and failure lifecycle

Use a trusted server-owned mapping from opaque session IDs to workspace/connection context, not one global Session/Workspace. A request must not resolve an otherwise valid result/node from another session. Initially serializing work per session is acceptable; thread safety and total concurrent capacity must be explicit implementation choices. Shared DuckDB connections must not be used concurrently without a verified ownership model.

The local API documents restart/expiry behavior in [LOCAL_API](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results); process restarts invalidate capabilities. No durable auth, retention period, arbitrary cleanup or multi-tenant architecture is selected here. Missing/expired/unowned references return safe unavailable/not-found responses without revealing another session's existence. Reset must not delete a shared lineage store as a shortcut.

Transport failure, planning failure, tool failure and verification abstention are different outcomes. Reuse ToolStatus (`success`, `failure`, `partial`, `not_run`) and existing safe tool categories; fetch/document subcodes are allowlisted as in live_check, never exception strings. Transport-level invalid request/session/timeout/internal categories belong to the implemented HTTP adapter. Unknown internal failures map to a fixed generic response; request IDs may aid operator correlation without exposing payloads. Never automatically retry a question after a disconnect: it may already have executed.

<a id="operator_flow-why-this-number-proof-requirements"></a>

### “Why this number?” proof requirements

Interaction: table cell → Why this number? → bounded recorded-evidence subgraph. This is analytical provenance for results produced by KKB DataTrio, not ORYN-style enterprise metadata discovery or discovery of external dbt/Airflow/SQL lineage.

Use the actual DEC-118 kinds:

- NodeKind: `source_file`, `series`, `transform`, `column`, `metric`, `claim`.
- EdgeKind: `derives_from`, `aggregates`, `deflates_by`, `cites`.
- Storage direction: upstream_id → downstream_id. A root query walks upstream but does not reverse stored edge meaning.

A target ProofGraph contains an owned result/cell reference, graph availability (`unavailable`, `partial`, `available`), nodes, edges, separately preserved verifier outcome, and limitations. Availability describes recorded graph coverage, not correctness. Nodes carry opaque ID, actual kind and a bounded safe label; no arbitrary attributes map. Edges contain actual endpoint IDs and actual EdgeKind. Do not invent `VerificationResult`/`InputSnapshot` nodes because the target architecture names them: return only records that exist. Do not manufacture a claim_id when current gate output lacks one.

The read-only adapter must resolve the owned immutable value first, then its actual evidence root. Traverse deterministically with explicit maximum nodes, edges, depth, label lengths, output bytes and database work; order parents by (ID, edge kind). Stop at budget exhaustion and report partial/truncated, never complete. Missing/invalid roots produce unavailable. Return no unrelated global roots and no fabricated edge to make disconnected evidence look complete. Existing document selected-cell proof is stronger than source presence; preserve that distinction. A complete-looking graph alone must never set a VERIFIED flag.

The exact executable graph schema, numeric limits, query implementation and cross-session tests belong to the later API/evidence implementation. M10-08 owns claim-level evidence inspection; DEC-128 defers graph-heavy layout, not stable evidence references. No new graph database, mutable UI provenance store or networkx dependency is needed for this specification.

<a id="operator_flow-sse-requirements-dec-123"></a>

### SSE requirements (DEC-123)

The future API must report observed lifecycle events in order with a per-turn monotonic sequence and owned turn identity. Minimum meanings: turn started; validated plan available; tool started/completed with ToolStatus and allowlisted category; gate started; turn completed with final gated-response reference; turn failed with safe error. Abstention is a completed turn with `abstained`, not an internal exception.

Instrument actual backend boundaries in its implementation task; do not simulate live progress by replaying a completed trace under misleading timestamps. Planner reasoning/prompts, raw arguments/results, document bytes, credentials, discarded drafts and stack traces never enter SSE. Reconnection/replay, cancellation and reset are not promised until M10-11 defines them. A stream ending unexpectedly does not grant another execution or erase evidence. SSE lifecycle hooks do not exist today.


## Ingestion and profile specification

Original bounded admission/profile specification. References to future integration describe this contract’s delivery scope; current completion belongs to ROADMAP.

<a id="ingestion_profile-m1-01--ingestionprofile-result-specification"></a>

### M1-01 — Ingestion/profile result specification

This is the reviewable specification for [M1-01](ROADMAP.md#m1), with synthetic examples. It defines planned observable results, not implemented CSV/XLSX support or new shared runtime types. [DEC-103/104](DECISIONS.md#dec-103--common-data-contracts-and-explicit-workspace) require generic references and explicit semantics; the analytical engine, undecided when this was written, was later selected by [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse).

<a id="ingestion_profile-integration-boundary"></a>

### Integration boundary

[ARCHITECTURE, components 5–7](ARCHITECTURE.md#5-source-discovery-and-adapters--confirmed-abstraction) describes `load` returning an opaque data reference and `profile` returning a dictionary. The fields below specify that dictionary's intended meaning without changing those signatures. The Day 0 protocol/models are stash-only in the verified checkout; integrate with the validated M0 contracts and their editor before adding runtime types. This task neither inspects nor recovers the stash.

An adapter profiles one explicitly selected table, regardless of source name or parser engine. A data reference resolves only through the application's authorized data boundary; it is not a user-supplied path, URL, SQL expression, or executable text. The source reference identifies the original source independently of the loaded/derived data reference. Sheet/table selection accompanies the source reference so two sheets cannot accidentally share a profile identity. Ingestion time must not substitute for observation date or source vintage.

<a id="ingestion_profile-result-fields"></a>

### Result fields

Names and types here are a proposed interchange shape for review, not a claim that matching Python classes exist. A JSON example below makes the contract testable without choosing Pandas, Polars, DuckDB, or another dependency.

| Field | Required meaning |
| --- | --- |
| `status` | `ok`, `needs_input`, or `rejected`. `ok` means a bounded table was loaded/profiled; it does not mean financial semantics are resolved or an analytical operation is safe. |
| `data_ref` | Opaque nonempty reference for `ok`; `null` otherwise. Never publish a usable reference to a failed or partly parsed table. |
| `source_ref` | Nonempty source identity assigned at intake, including on rejection; resolves to controlled provenance metadata. Raw bytes, credential-bearing URLs, and absolute local paths do not belong in this field. |
| `selection` | Explicit sheet/table identifier, or `null` when the source unambiguously contains one table. Ambiguous multi-table input returns `needs_input` before choosing one. |
| `row_count` | Exact number of data rows, excluding the header, for `ok`; positive integer. `null` when a table has not been accepted, including empty/header-only input. Never substitute sample size for total row count. |
| `columns` | Ordered column records below, one per accepted column. Empty on `needs_input`/`rejected`; order/identity must survive duplicate or empty labels. |
| `unresolved_semantics` | Structured records of affected column IDs, unresolved fields, and a short reason. An empty list means no unresolved fields in the declared semantic scope, not blanket analytical approval. |
| `diagnostics` | Short codes with safe column/selection references and counts where useful; no copied cell payload or stack trace. Empty when there is nothing to report. |
| `diagnostics_truncated` | Boolean; true if additional diagnostics were omitted because of the reporting cap. Never silently discard the fact that further issues exist. |

For non-`ok` results, counts/column profiles are unavailable (`row_count: null`, `columns: []`), rather than misleading zeros. Include a reason in `diagnostics` and, for `needs_input`, the precise missing selection or parsing declaration. Do not expose unsafe filenames in the diagnostic text.

<a id="ingestion_profile-column-fields-and-invariants"></a>

### Column fields and invariants

| Field | Meaning and invariants |
| --- | --- |
| `id`, `name` | `id` is unique and stable within this data reference (for example `c0` by ordinal); `name` preserves the original label as untrusted metadata. Labels are not unique keys or instructions. Renaming a label does not introduce source-specific code. |
| `type` | Engine-neutral observed representation: `integer`, `number`, `boolean`, `string`, `mixed`, or `unknown`. All-missing columns are `unknown`. A date-looking string can remain `string`; its date interpretation is a separate candidate. Record any accepted parsing declaration in provenance. |
| `missing_count` | Integer from 0 through `row_count`. Missingness follows the declared parser/null policy; absent fields and empty fields are not silently equated with zero. Whitespace and tokens such as `NA` need an explicit policy. |
| `missing_fraction` | `missing_count / row_count`. Store finite numbers only; display rounding must not change the counts. Zero-row input is rejected without column profiles, so no division by zero is attempted. |
| `date_candidates` | List of `{format, matched_count}` interpretations, tested over nonmissing cells. No automatic time-column selection. Invalid or ambiguous values stay visible; a format match does not prove business time semantics. |
| `numeric_candidates` | List of `{decimal_separator, thousands_separator, matched_count}` interpretations. `thousands_separator` may be `null`. Counts describe parseability, not a conversion already performed. |
| `candidate_state` | Separate `date` and `numeric` values: `unique`, `ambiguous`, `none`, or `not_evaluated`. `unique` requires one complete, unambiguous interpretation of all nonmissing cells. Partial matches remain `ambiguous`; an all-missing column is `not_evaluated`, not vacuously `unique`. |
| `semantics` | Explicit values for `unit`, `frequency`, `time_role`, `stock_flow`, `cumulative`, and `reset_rule`; each is `unknown` until declared/confirmed with provenance. Known cumulative values are booleans; `false` is not interchangeable with `unknown`. `not_applicable` needs an explicit justified declaration. |

Every candidate's `matched_count` is between 0 and `row_count - missing_count`; nonmatching nonmissing count is the difference. Candidate lists are empty for `none`/`not_evaluated`. `unique` has exactly one full-coverage candidate. `ambiguous` can mean multiple full-coverage interpretations, incomplete coverage, or an explicitly bounded search that did not establish uniqueness; a diagnostic distinguishes these reasons. A candidate never overwrites original values, drops failed rows, picks a locale, or fills missing values.

Each `unknown` semantic field is covered by `unresolved_semantics`, including after a successful parse. A known semantic declaration must retain an evidence reference in the source's controlled metadata; a dtype, regular-looking sample, confidence score, or header guess alone is insufficient. Date/numeric candidates can be reported while unit, frequency, stock/flow, and cumulative reset remain unknown. Any later transformation must check its own prerequisites under ARCHITECTURE rather than interpreting `status: ok` as permission.


## Prepared metadata inspection

The mechanism below is the prepared-reader contract. Its original “later API”
wording is historical integration context; the prepared launcher already passes
the catalog/inspection policy as described in [snapshot ownership](#prepared_api-snapshot-and-session-ownership).


<a id="series_inspection-prepared-series-metadata-inspection"></a>

### Prepared series metadata inspection

The M13-13 prepared-reader slice compares a selected series with an
operator-supplied reviewed catalog **before numerical use**. It is a mandatory
code path within catalog-configured prepared runs, not a planner-callable tool.

`PreparedSeriesInspector(snapshot)` owns a separately validated copy of the
reviewed snapshot. `inspect(connection, series_id)` uses exact identity lookup
and a parameterized, read-only metadata query over `silver_series` and its
`bronze_artifacts` reference. It reads no observations, follows no source URL,
loads no files and has no inference or network fallback. A successful result is
not cached; each new use checks current stored declarations.

<a id="series_inspection-non-skippable-wiring-in-the-prepared-mode"></a>

### Non-skippable wiring in the prepared mode

The existing [prepared rehearsal](CATALOG.md) constructs and injects
the inspector whenever `--catalog`/`catalog_bytes` is supplied. This applies even
if the model directly selects a series without first using catalog_search.

- `change_detection` (compare/co_movement), `anomaly`, `causality` and
  `table_transform` call the shared `read_series(..., inspector=...)`. It requires
  a consistent receipt before reading observations for that selected series.
  Neither direct invocation nor a model argument can skip this check in a
  configured factory. Unknown/mismatched inputs return a safe failure.
- The restricted `lakehouse` query can return raw inspection rows, but its
  existing direct-silver provenance check must succeed before any financial
  projection. Every selected series then requires a consistent receipt before
  rows become typed values. Failure produces no values, execution proof or
  numerical answer. Unsupported SQL/gold projections already abstain; this
  change grants them no new measurement authority.
- Existing published-table relationship analysis consumes previously verified
  results and does not select a new source series. Full cross-turn catalog
  revision/staleness revalidation remains separate work.

Successful receipts are bound into the producer's local execution-input snapshot
alongside the actual data used. SQL projection records one receipt per selected
identity. Receipts contain hashes/categories, not source descriptions, locators
or observation samples. The ordinary verifier resolves their immutable input
and output bindings. This is traceability, not independent source attestation
or protection from a privileged database/application writer.

No database schema, new tool name or source adapter changes. Factories without
a reviewed inspector retain existing generic input semantics/provenance guards.
This deliberate compatibility path is **not** completion of global M13-13
wiring. A later API must carry the selected preparation/catalog policy into all
its factories; omitting that operator configuration cannot be advertised as this
inspection mode. The lakehouse remains single-owner/not thread-safe.
