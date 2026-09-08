# Architecture

This file owns technical structure and contracts. [ROADMAP](ROADMAP.md) owns delivery/status, [DECISIONS](DECISIONS.md) confirmed choices, [SECURITY](SECURITY.md) boundary controls, and [EVALUATION](EVALUATION.md) behavioral validation.

## Reading the design

- **CONFIRMED**: an invariant/decision carried in DECISIONS, not a claim of completed code.
- **PROPOSED**: a concrete design to test and refine before adoption.
- **UNDECIDED**: requires a team or organizer answer; do not implement an assumption as a confirmed choice.

Implementation snapshot, 2026-09-08: local/untracked Day 0 models (`src/kkb_agent/core/models.py`), protocols (`src/kkb_agent/core/interfaces.py`), a non-networking provider stub (`src/kkb_agent/providers/kloudeks.py`), and evaluation scaffolding exist only in the originating checkout. They are excluded from the documentation commit and have not been validated in this task. Components below are target behavior unless explicitly described as locally present. No ingestion service, executor, analytics, safe fetch, verifier, or UI is implemented in the inspected tree.

## Goals and non-goals

CONFIRMED goals:

- Handle unfamiliar questions and new-but-supported sources through common contracts.
- Use the LLM for interpretation and planning; use deterministic tools for calculations.
- Make assumptions, transformations, failures, and evidence inspectable.
- Preserve explicit multi-turn analysis state and invalidate dependent results correctly.
- Fail safely when data meaning or execution authority is insufficient.
- Keep the inner loop fast and the demonstration reliable under constrained model access.

Non-goals for this window: arbitrary generated-code execution, a general autonomous web crawler, a warehouse platform, distributed agent infrastructure, enterprise tenancy/security systems, or a training pipeline. No orchestration framework, analytical engine, frontend framework, vector DB, or multi-agent topology is selected here.

## End-to-end request lifecycle

CONFIRMED responsibility flow; the coordinator mechanism is UNDECIDED.

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

### 1. Request coordinator and intake — PROPOSED implementation

- Responsibility: Resolve the request/workspace, orchestrate the validated lifecycle, apply budgets, and decide whether clarification is needed.
- Input: User request, workspace ID, available capabilities, configured request limits.
- Output: A bounded execution outcome and accepted workspace transition, or clarification/failure.
- Must NOT: Treat embedded source text as a user command, create tool authority from a model response, or keep retrying indefinitely.
- Likely failures: Unknown workspace, ambiguous intent, stale references, deadline exhaustion, incompatible follow-up.
- Validation expectations: Tests for no-work clarification, failed-turn state preservation, cancellation/deadline propagation, and follow-up invalidation.

The exact loop/framework is Q-TEAM-01. A small sequential baseline is a complexity preference, not an approval to adopt a particular framework.

### 2. LLMProvider / Kloudeks boundary — CONFIRMED interface direction

- Responsibility: Isolate model-specific structured generation, plan generation, and concise synthesis.
- Input: System-owned prompts, bounded selected metadata/workspace summary, and expected response schema.
- Output: Validated model output or categorized provider failure; synthesis remains subject to claim verification.
- Must NOT: Compute authoritative financial numbers, execute tools directly, accept a request-supplied endpoint, leak credentials, or silently call another provider.
- Likely failures: Missing configuration, unavailable model, timeout/rate limit, context overflow, refusal, malformed JSON/schema mismatch.
- Validation expectations: Offline provider doubles, strict response validation, all error branches, bounded retries, redaction tests, and separately recorded permitted live smoke.

Present protocol methods are `generate_structured(prompt, response_model)`, `create_plan(request, workspace)`, and `synthesize(prompt)`. Present stub methods raise `KloudeksIntegrationPendingError` and perform no networking. `KLOUDEKS_ENDPOINT`, `KLOUDEKS_MODEL`, and `KLOUDEKS_CREDENTIAL` are provisional local configuration names, not a confirmed organizer API contract.

UNDECIDED: endpoint/auth format, exact model, tool/JSON-schema support, context/quota, embeddings/reranker. Native structured output may help but does not replace local validation. Any response-repair path must remain inside Kloudeks and the configured attempt budget.

### 3. Planner and plan validator — CONFIRMED separation; implementation pending

- Responsibility: Translate intent into typed registered-tool steps and reject unsafe/invalid plans before execution.
- Input: Request, allowed tool schemas, source candidates, current workspace references/assumptions.
- Output: A validated executable plan, a bounded repair request, or an explicit unsupported/clarification outcome.
- Must NOT: Dispatch arbitrary names, code, imports, SQL, URLs, or paths from free-form text; silently resolve unknown data semantics.
- Likely failures: Unknown tool, extra/invalid argument, bad dependency, unavailable input, too many steps, repeated invalid plan.
- Validation expectations: Positive plan fixtures plus negative names/arguments/dependency/reference/capability cases; verify rejection occurs before any tool side effect.

Present AnalyticalPlan fields: `plan_id`, `goal`, `required_inputs`, ordered `steps`. Present PlanStep fields: `step_id`, `tool`, JSON `arguments`, `dependencies`, `expected_output_type`, `verification_required`.

Present model validators reject duplicate IDs and unknown/forward dependencies, plus self/duplicate step dependencies. **They do not validate tool membership, per-tool arguments, workspace reference existence, or semantic preconditions.** Those checks belong in the registry/validator. The `verification_required` field cannot authorize bypassing mandatory material-claim verification.

### 4. Tool registry and executor — PROPOSED implementation

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

Present model stores `workspace_id`, selected sources, data contracts, normalized refs, derived columns, transformations, evidence, assumptions, and results. No storage service or transaction mechanism is implemented. PROPOSED state versioning/staged updates can be implemented with a lightweight mechanism; database, durability, concurrency, and restart persistence are UNDECIDED.

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

Present SourceRef holds identity/type/locator and optional retrieval time/hash. Present TransformationRecord holds operation/parameters/input refs/output ref. Present EvidenceRecord holds claim, sources, optional run, transformations, period/columns, validation, limitations. Validation defaults to NOT_RUN. These records do not enforce a complete evidence chain; the ledger/service and claim rules are still pending.

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

### 11. Answer/UI adapter — PROPOSED implementation

- Responsibility: Present supported claims, tables/charts, assumptions, progress, and evidence; make clarification and failure actionable.
- Input: Verified claim set, structured execution state, safe source/evidence summaries.
- Output: User-visible answer and explicit follow-up request/workspace operation.
- Must NOT: Recalculate values with the LLM, hide partial/failed verification, expose secrets/internal stack traces, or relabel cached data as live.
- Likely failures: Missing evidence link, stale display after a follow-up, confusing partial result, unsuitable demo environment.
- Validation expectations: Independent teammate runs happy path, clarification, outage, and multi-turn correction; displayed values match tool outputs.

Frontend framework and hosting are UNDECIDED. The logical UI contract does not require a particular web stack.

## Multi-turn behavior

PROPOSED state transition rules, to validate in M5/M8:

| Follow-up | Preserve | Change / invalidate |
| --- | --- | --- |
| Add another series | Existing selections, raw inputs, historical evidence | Add contract/source; recompute comparisons that now include it |
| Change date range | Sources, transformation definitions, prior run history | Update selection; invalidate dependent values/charts/evidence |
| Deflate previous result | Original nominal series and its lineage | Add index/reference assumption and derived real series; recalculate dependents |
| Correct prior assumption | Original observation/history and correction record | Replace active assumption; invalidate every dependent transformation/claim |
| Failed new request | Last coherent accepted workspace | Record failure metadata; do not silently replace verified results |

Exact persistence lifetime is Q-DEMO-02/Q-INFRA-02. A single-process baseline may be sufficient, but never advertise restart durability without implementation and tests.

## Failure, retry, and recovery

PROPOSED outcome categories, not all present schema enums: validation error, unknown semantics, unsupported capability, unavailable source/provider, timeout/resource limit, contradictory evidence, and internal tool failure. Clarification is an orchestration outcome; it is not currently a ToolStatus enum value.

Retry transient transport/tool failures only when repeat execution is safe. Repair malformed/invalid plans with sanitized validation feedback. Track both per-step attempts and a request-wide budget so nested retries cannot multiply without bound. Do not retry blocked destinations, forbidden tools, missing permissions, or unknown semantics as if they were transient.

Exact limits are UNDECIDED pending Q-K-04 and measurements. They must be configured and tested before exposure. Exhaustion returns a structured final failure/partial result, never an endless “trying again.” Cached fallbacks need organizer permission, visible source vintage, and a clear distinction from live results.

## Security boundaries

Apply [SECURITY](SECURITY.md) at source retrieval, upload/parser entry, provider configuration, plan/tool dispatch, evidence logging, and UI output. Data locators are provenance, not execution authority. Source HTTP uses safe fetch; provider HTTP uses an organizer-configured transport that cannot be selected by user/model text. Do not treat URL syntax validation or Pydantic alone as SSRF protection.

No arbitrary runtime Python/shell execution is permitted. SQL remains optional; if introduced it needs parsed/allowlisted read-only operations and disabled file/network/extension capabilities. Read-only SQL text alone does not prevent exfiltration.

## Latency and extension points

Measure stage timings before optimizing: provider planning, discovery/fetch, parsing, normalization, analytics, verification, synthesis. Report cold/warm and offline/live separately. Prefer bounded metadata selection, deterministic routing for obvious formats, and reuse of verified data references. Cache only with confirmed permission and source-aware invalidation. Never skip semantic checks or evidence to make a timing target.

Extension rules:

1. New source: implement supported adapter capabilities, guards, metadata mapping, synthetic fixtures, and unfamiliar-schema tests.
2. New tool: add typed args/result expectations, registry entry, semantic prerequisites, evidence rules, and independent numerical/failure cases.
3. New model: change provider configuration/adapter capability handling; keep analytical tests unchanged.
4. New file format: confirm scope, guard/parser limits and fragment provenance, then add supported/unsupported/hostile cases.
5. New persistence/UI/orchestration dependency: resolve the relevant decision with a small tested requirement first.

Deliberately UNDECIDED: LangGraph versus custom loop, Pandas/Polars/DuckDB or other engine, database/persistence, exact Kloudeks model, exact causality implementation, frontend framework, embeddings/vector DB, router fine-tuning, and multi-agent topology. See DECISIONS and OPEN_QUESTIONS; this document does not settle them.
