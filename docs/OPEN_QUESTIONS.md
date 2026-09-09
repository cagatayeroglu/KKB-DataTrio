# Actionable open questions

This file owns unresolved external/team questions and their evidence. [DECISIONS](DECISIONS.md) owns confirmed choices; [ROADMAP](ROADMAP.md) owns blocked/ready tasks. A temporary assumption is a planning aid, not organizer permission or an implementation fact.

Snapshot: 2026-09-09. The five team-decision questions Q-TEAM-01 through Q-TEAM-05 are **ANSWERED** by M0-ARCH and recorded in DECISIONS; those five choices are no longer blockers. Task-level proof/result schemas, reviewed concept-family membership and measured thresholds remain proposals until reviewed; they do not reopen those answered questions. No organizer answer has been received yet, so every Q-K, Q-INFRA, Q-DATA, Q-NET, Q-DEMO, Q-DEV, Q-JUDGE and Q-COMP entry remains open and unassigned; suggested lanes refer to ROADMAP's rotating A/B/C roles, not actual commitments.

The organizer questions are now the project's only external blockers, and several of them gate long-lead work: Q-K-01/02/03 gate every live model path, Q-K-05 gates only optional embedding/reranker experiments under DEC-127 (DEC-115 is SUPERSEDED), Q-NET-01/02 gate the `web_search` and `web_url` tools, Q-DATA-01 gates live source retrieval, and Q-INFRA-01 can override DEC-126. Ask them early rather than near the delivery date.

## How to use this list

- Claim the relevant question, obtain an answer, and record a dated message/document/reference without secrets or private payloads.
- Check a question only when the answer/evidence is recorded and its affected roadmap blockers are updated. A question being sent is not a resolved question.
- `Can we proceed before answer?` applies to the **blocked slice named in that entry**. Independent synthetic work may still proceed even when the answer is NO.
- Use Status: OPEN, WAITING (asked, no answer), ANSWERED, or DEFERRED. Add actual owner and next follow-up date when someone accepts the question; no automated messaging is implied.
- Do not ask organizers for every internal implementation preference. The team-decision section is resolved by teammates and recorded as an ADR.

## Priority queue

| Priority | Questions | Why now | Independent work while waiting |
| --- | --- | --- | --- |
| First available organizer contact | Q-K-01/02/03, Q-NET-01/02, Q-DATA-01/02, Q-DEMO-01 | Determine live access and required input/demo scope | Offline provider/tool integration, synthetic contracts/oracles |
| Before private data or deployment | Q-DATA-03, Q-INFRA-01/02, Q-COMP-01, Q-DEMO-02/03 | Determine retention, environment, session/fallback rules | Credential-free unit tests, operator-flow design |
| Before final scope/experiments | Q-K-04/05, Q-DEV-01/02, Q-JUDGE-01/02, Q-COMP-02, Q-DATA-04 | Avoid unsupported tooling/scoring/resource assumptions | Core deterministic baseline |
| ~~Before affected implementation choice~~ | Q-TEAM-01/02/03/04/05 — **ANSWERED 2026-09-09** | Resolved by M0-ARCH; see DEC-112, DEC-113, DEC-117, DEC-120, DEC-123 | No longer blocking; implementation may proceed |

## Kloudeks

### Q-K-01 — Endpoint, authentication, and credential delivery

- [ ] Record confirmed transport/authentication contract and unblock eligible M4 work.
- Question: When/how will credentials arrive, which endpoint is approved, and what authentication/TLS/network contract must the application use?
- Why it matters: The delivered offline provider boundary cannot become a live transport by guessing an endpoint or header.
- Blocks which milestone? M4 live transport/auth (M4-03/07/12), M11 live-model demo.
- Can we proceed before answer? NO for live transport/auth acceptance; YES for the merged offline interface/configuration/structured-output validation and provider doubles (PR #27).
- Temporary assumption: Runtime is Kloudeks-only; endpoint/auth remain unknown. Current environment variable names are local provisional conventions.
- Owner: Unassigned; suggested lane B / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded. Store contract/reference and date here, never the credential itself.

### Q-K-02 — Available models and context capacity

- [ ] Record available model IDs, supported roles/capabilities, and context limits.
- Question: Which model IDs/sizes are available, and what input/output/context limits apply to each?
- Why it matters: Planner context and model choice must fit actual platform capability.
- Blocks which milestone? M4 model configuration/live validation; M5 context sizing; M11 live candidate.
- Can we proceed before answer? NO for final live model selection; YES for model-independent contracts/doubles.
- Temporary assumption: Do not assume large models or a particular model ID; keep metadata prompts bounded.
- Owner: Unassigned; suggested lane B.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-K-03 — Structured output and tool calling

- [ ] Record native function/tool calling, JSON-schema support, and response-format behavior.
- Question: Does Kloudeks expose native tool calling or guaranteed structured JSON, and which schema features/error responses are supported?
- Why it matters: Determines provider parsing/repair approach without weakening local validation.
- Blocks which milestone? M4 structured-output integration; M5 live plan generation.
- Can we proceed before answer? NO for platform-specific implementation; YES for strict local schemas and malformed-output fixtures.
- Temporary assumption: No guarantee of native structured output; model results must validate locally in all cases.
- Owner: Unassigned; suggested lane B.
- Status: OPEN.
- Answer / evidence: None recorded; add a sanitized response/schema example only when permitted.

### Q-K-04 — Quotas, timeouts, and retry behavior

- [ ] Record request/token/concurrency limits, error semantics, and permitted retry behavior.
- Question: What rate/token/request limits, timeouts, concurrency rules, and retry guidance apply during development and the demo?
- Why it matters: Exact attempt/deadline budgets and latency expectations need real constraints.
- Blocks which milestone? M4 transport budgets; M5 bounded live loop; M9 live latency thresholds; M11 capacity rehearsal.
- Can we proceed before answer? YES for configurable bounded behavior and offline tests; NO for claiming quotas or a validated live SLA.
- Temporary assumption: Use conservative configurable limits in later implementation, measure them, and do not assume unlimited calls.
- Owner: Unassigned; suggested lane B with C measurement.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-K-05 — Embeddings and rerankers

- [ ] Record whether embeddings/rerankers exist and whether their use is necessary/permitted.
- Question: Are embedding/reranking endpoints exposed; which model IDs, vector dimensions, query/passage prefix conventions, batch/token limits, quotas and output contracts apply?
- Why it matters: Could improve discovery if a benchmark demonstrates a retrieval problem.
- Blocks which milestone? Optional M13-05 embedding/LanceDB and M13-07 model-reranking experiments only; fusion also needs benchmark evidence. Not the mandatory normalizer/alias/metadata/lexical baseline or offline benchmark design.
- Can we proceed before answer? YES.
- Temporary assumption: No embedding/reranker dependency; use deterministic metadata filtering and the basic provider boundary.
- Owner: Unassigned; suggested lane B.
- Status: OPEN; optional activation is BENCHMARK-GATED by DEC-127. No current embedding/reranking contract is claimed.
- Answer / evidence: None recorded.

## Organizer infrastructure

### Q-INFRA-01 — Runtime/deployment environment

- [ ] Record OS/runtime/container/port/storage constraints and submission environment.
- Question: Where must the application run, and what OS, Python/package installation, container, port, filesystem, and deployment restrictions apply?
- Why it matters: Determines reproducible setup, parser availability, and UI delivery.
- Blocks which milestone? M0 final setup validation, M10 deployment choice, M11 rehearsal environment.
- Can we proceed before answer? YES for local Python >=3.12 contracts/tests; NO for claiming deployment compatibility.
- Temporary assumption: Local development is provisional; no Docker/hosting/GPU requirement is inferred.
- Owner: Unassigned; suggested lane B / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-INFRA-02 — Storage lifetime and isolation

- [ ] Record local disk limits, reset behavior, persistence lifetime, and private-data cleanup requirements.
- Question: What survives process restart, demo questions, or session reset, and what storage/cleanup/isolation requirements apply?
- Why it matters: Workspace semantics must match actual retention/durability expectations.
- Blocks which milestone? M5 persistence acceptance, M10 reset/session behavior, M11 cleanup/restart demonstration.
- Can we proceed before answer? YES for explicit in-process state and synthetic tests; NO for promised restart durability/private retention.
- Temporary assumption: The merged workspace persists definition/binding/history tables, but result durability, cleanup and cross-session retention are not established. Do not commit or retain organizer data based on an assumption.
- Owner: Unassigned; suggested lane B with C operator requirements.
- Status: OPEN.
- Answer / evidence: None recorded.

## Datasets

### Q-DATA-01 — BDDK/EVDS and provided source access

- [ ] Record actual source inventory, approved endpoints/formats, access requirements, and source-use permissions.
- Question: Which datasets/series will be available, how do we access BDDK/EVDS or replacements, and which metadata/revision conventions are authoritative?
- Why it matters: Live adapters and semantic mappings require confirmed inputs; familiar source names do not prove access.
- Blocks which milestone? M3 live integration and source-semantic acceptance; M11 representative live analysis.
- Can we proceed before answer? NO for source-specific live acceptance; YES for generic ingestion and synthetic source-shaped fixtures.
- Temporary assumption: BDDK/EVDS are likely integrations, not the only possible sources. PR #21/#22 source inventories record observed endpoints/series metadata, not organizer-approved runtime access or redistribution. Do not invent missing request payloads, permissions or auth requirements.
- Owner: Unassigned; suggested lane A.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-DATA-02 — Hidden formats, schema variation, and size

- [ ] Record required file formats, maximum sizes, languages/encodings, and expected schema variation.
- Question: Can hidden inputs contain CSV/XLSX/multi-sheet workbooks, HTML, PDF/scanned PDF, images, unknown schemas, or unusually large files?
- Why it matters: Defines required parsers, limits, OCR scope, and adversarial coverage.
- Blocks which milestone? M1/M7 final format scope, M9 required coverage, M11 support claims.
- Can we proceed before answer? YES for bounded CSV/XLSX baseline and explicit unsupported-format behavior; NO for claiming full hidden-format coverage.
- Temporary assumption: CSV/XLSX first; HTML/PDF planned; image/OCR not guaranteed. All enabled parsers need tested limits.
- Owner: Unassigned; suggested lane A with C coverage.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-DATA-03 — Caching, retention, and redistribution

- [ ] Record permitted local cache/retention/export/fixture use and cleanup requirements.
- Question: May organizer datasets and derived results be cached locally, included in a demo fallback, exported, or committed/shared, and for how long?
- Why it matters: Determines legal/organizer permission for data handling and fallback artifacts; permission cannot be inferred from access.
- Blocks which milestone? M1 private storage, M3/M7 cache, M10/M11 fallback/exports, SEC-DATA-01.
- Can we proceed before answer? NO for private retention/redistribution/fallback use; YES with synthetic fixtures and explicitly permitted public-safe data.
- Temporary assumption: Do not commit organizer/private data or assume cache/fallback permission.
- Owner: Unassigned; suggested lane A / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded; link the actual permission and scope when received.

### Q-DATA-04 — Authoritative semantics and revisions

- [ ] Record who resolves missing/conflicting units, stock-flow/reset rules, and historical revisions.
- Question: Is an authoritative data dictionary/release vintage supplied, and how should we handle missing semantics or contradictory revised observations during judging?
- Why it matters: Prevents silently selecting a convenient interpretation to produce a number.
- Blocks which milestone? M2/M3 disputed source mappings; M9 oracle adjudication.
- Can we proceed before answer? YES with explicit unknowns and hand-specified synthetic semantics; NO for unsupported source-specific conversions.
- Temporary assumption: Preserve unknowns and vintages; clarify/abstain where required meaning is missing.
- Owner: Unassigned; suggested lane A with C oracle review.
- Status: OPEN.
- Answer / evidence: None recorded.

## External internet / network

### Q-NET-01 — Demo/development internet access

- [ ] Record outbound network, DNS, proxy, firewall, and package-install access for each environment.
- Question: Is internet access available to the application during development and demo, and through which DNS/proxy/firewall restrictions?
- Why it matters: Live retrieval/provider setup and reproducibility depend on actual connectivity.
- Blocks which milestone? M3/M4/M7 live paths and M11 network rehearsal.
- Can we proceed before answer? NO for promised live-source availability; YES for offline tools and fake transports.
- Temporary assumption: No guaranteed external internet; do not enable an unrestricted fallback fetch path.
- Owner: Unassigned; suggested lane B / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-NET-02 — Allowed external source URLs

- [ ] Record whether arbitrary public URLs, named domains, or only organizer-provided sources are permitted.
- Question: May the app retrieve arbitrary external HTTP(S) sources, or must it use an organizer-approved allowlist, including redirect destinations?
- Why it matters: Product capability policy is additional to technical SSRF protection.
- Blocks which milestone? M3/M7 live retrieval exposure and M11 supported-source claims.
- Can we proceed before answer? NO for enabling arbitrary external source fetching; YES for safe-fetch negative tests/design.
- Temporary assumption: No assumption that arbitrary URLs are permitted; safe-fetch must still block private/metadata destinations for source retrieval.
- Owner: Unassigned; suggested lane B with A source needs.
- Status: OPEN.
- Answer / evidence: None recorded.

## Demo format

### Q-DEMO-01 — Timing, format, and user interaction

- [ ] Record event dates, actual preparation window, demo duration, required interface, and who enters questions.
- Question: What are the exact deadline/demo format and duration, and will judges operate the app, upload files, or ask live follow-ups?
- Why it matters: Confirms whether 8–9 workdays, UI choices, operator steps, and latency budgets fit the event.
- Blocks which milestone? M10 UI/delivery acceptance and M11 timed rehearsal; schedule remains provisional.
- Can we proceed before answer? YES for backend/flow specification; NO for final demo-format assumptions.
- Temporary assumption: ROADMAP days are relative planning slots, not confirmed dates; prepare one clear analysis/evidence/follow-up path.
- Owner: Unassigned; suggested lane C.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-DEMO-02 — Multi-turn state and reset semantics

- [ ] Record whether state persists between questions, users, runs, or restarts, and how reset is expected to work.
- Question: What exactly is retained between demo turns, and must the system restore an analysis after process restart or user change?
- Why it matters: Explicit workspace state is required, but durable storage may not be.
- Blocks which milestone? M5/M10 final session/persistence behavior; M11 operator reset/restart script.
- Can we proceed before answer? YES for same-session explicit workspace; NO for a claim of required/working restart persistence.
- Temporary assumption: Preserve same-workspace analytical state; do not promise cross-session durability.
- Owner: Unassigned; suggested lane C with B implementation.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-DEMO-03 — Permitted fallback and demonstration assets

- [ ] Record whether local fixture/cache fallback, recorded screens, or preloaded data are permitted and how they must be labeled.
- Question: What fallback is allowed if live source/provider access fails, and which prepared demo assets may be used?
- Why it matters: Reliable recovery must remain honest about live versus synthetic/cached behavior.
- Blocks which milestone? M10 fallback UI and M11 outage rehearsal acceptance.
- Can we proceed before answer? NO for treating prepared assets as an approved demo fallback; YES for synthetic development/recovery tests.
- Temporary assumption: No silent fixture substitution or claim that a cache is live; no presumed fallback permission.
- Owner: Unassigned; suggested lane C.
- Status: OPEN.
- Answer / evidence: None recorded; coordinate data permission with Q-DATA-03.

## Allowed development tooling

### Q-DEV-01 — Coding assistants during development

- [ ] Record organizer policy on coding assistants used only to build the product.
- Question: Are Codex/Claude Code or other coding assistants permitted strictly as development tools while runtime uses only Kloudeks, and is disclosure required?
- Why it matters: Development-tool permission is separate from confirmed runtime LLM restrictions.
- Blocks which milestone? Organizer-compliance confirmation for development workflow and M11 submission; not offline architecture specification.
- Can we proceed before answer? YES for the user-authorized local documentation work; do not claim organizer permission for assistant-assisted event development.
- Temporary assumption: Runtime remains Kloudeks-only. Development-assistant allowance remains explicitly unconfirmed and should be clarified early.
- Owner: Unassigned; suggested organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-DEV-02 — External tools, libraries, and code disclosure

- [ ] Record restrictions on packages, development-time internet/tools, external services, and required attribution/disclosure.
- Question: Are there restrictions on third-party libraries, development services, pre-existing code, or generated assets beyond the known runtime constraints?
- Why it matters: Avoid adopting tooling/assets that cannot be used in the submitted product.
- Blocks which milestone? M0 setup policy, optional M7 extraction dependencies, M10 assets, M11 submission review.
- Can we proceed before answer? YES with the existing minimal declared stack and explicit hard constraints; NO for claiming unrestricted additional tooling permission.
- Temporary assumption: Add no speculative service dependency; record concrete package needs and ask before assuming event allowance.
- Owner: Unassigned; suggested organizer liaison with B technical input.
- Status: OPEN.
- Answer / evidence: None recorded.

## Scoring / judging

### Q-JUDGE-01 — Rubric and unsupported-answer handling

- [ ] Record scoring weights, required use cases, numeric tolerances, and treatment of clarification/abstention/causality.
- Question: How are correctness, evidence, recovery, latency, UI, and unsupported/causal answers scored, and are hidden-case categories or tolerances specified?
- Why it matters: Determines final acceptance thresholds and rational scope cuts without gaming unknown criteria.
- Blocks which milestone? M9 final score thresholds and M11 go/no-go criteria.
- Can we proceed before answer? YES with category-based correctness metrics; NO for claiming organizer score thresholds.
- Temporary assumption: Prioritize correct, traceable results and honest abstention; do not invent weights or required pass percentages.
- Owner: Unassigned; suggested lane C.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-JUDGE-02 — Submission and development-history evidence

- [ ] Record deliverables, repository visibility/access, history/review expectations, and submission deadline.
- Question: Which source/history/PR/benchmark/demo artifacts must be submitted, and how will development progression be reviewed?
- Why it matters: The team-reported review expectation needs an actionable submission contract.
- Blocks which milestone? M0 remote-sharing setup and M11 final submission/release packaging.
- Can we proceed before answer? YES with coherent local changes and safe records; NO for assuming publication/access requirements.
- Temporary assumption: Keep history understandable; no automatic commit/push/merge or private-data disclosure.
- Owner: Unassigned; suggested lane C / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

## Compute / resources

### Q-COMP-01 — Provided machine and resource limits

- [ ] Record CPU/RAM/disk/GPU availability and whether the team must use its own machine.
- Question: Will organizers provide a machine/GPU or require team hardware, and what CPU/RAM/disk/concurrency limits apply?
- Why it matters: Determines parser limits, local setup, and realistic latency/rehearsal conditions.
- Blocks which milestone? M0 environment acceptance, M7 resource limits, M10/M11 deployment/rehearsal.
- Can we proceed before answer? YES for bounded CPU-friendly baseline; NO for claiming resource compatibility or assuming a GPU.
- Temporary assumption: No dedicated GPU or distributed infrastructure; measure on the actual environment when known.
- Owner: Unassigned; suggested lane B.
- Status: OPEN.
- Answer / evidence: None recorded.

### Q-COMP-02 — Optional training/inference experiment budget

- [ ] Record permitted compute/time/quota for optional fine-tuning or retrieval experiments if a measured need appears.
- Question: If a baseline reveals a routing/retrieval weakness, are local training or additional inference experiments permitted and resourced?
- Why it matters: Prevents speculative fine-tuning work from consuming the delivery window.
- Blocks which milestone? Optional enhancements only; no baseline milestone.
- Can we proceed before answer? YES.
- Temporary assumption: No fine-tuning pipeline, vector infrastructure, or additional model topology is allocated by default.
- Owner: Unassigned; suggested lane B with C benchmark evidence.
- Status: OPEN; experiments DEFERRED until justified.
- Answer / evidence: None recorded.

## Internal team choices — resolve with evidence, not organizer guesses

### Q-TEAM-01 — Orchestration mechanism

- [x] Record chosen minimal mechanism and rationale in DECISIONS after team review.
- Question: Does the tested lifecycle need a custom bounded loop, LangGraph, or another framework?
- Why it matters: Adds coordination/dependency cost and affects shared plan/workspace boundaries.
- Blocks which milestone? M5 framework adoption; lifecycle fixtures and registry contracts can proceed.
- Can we proceed before answer? YES for interface/tests; NO for silently committing the team to a framework.
- Temporary assumption (superseded by the answer below): Simple orchestration is a confirmed preference, not a selected implementation.
- Owner: Eray (M0-ARCH). Original suggestion: suggested lane B; another teammate reviews.
- Status: ANSWERED (2026-09-09, M0-ARCH).
- Answer / evidence: Custom bounded planner -> router -> executor -> verifier loop, recorded in [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop). LangChain, LangGraph and Celery rejected; the lifecycle is small enough that owning retry, repair and cancellation explicitly is cheaper than learning a framework's failure modes during delivery. Implemented in M5.

### Q-TEAM-02 — Analytical/parsing engine

- [x] Record engine/dependency choice against concrete ingestion/normalization requirements.
- Question: Which minimal combination of Pandas, Polars, DuckDB, or another engine best meets parsing/date/semantic needs and installation constraints?
- Why it matters: Shared data references, deterministic operations, and dependency setup depend on the choice.
- Blocks which milestone? M1 implementation dependency, M2/M6 engine-specific operations.
- Can we proceed before answer? YES for contracts/synthetic oracles; NO for engine adoption by assumption.
- Temporary assumption (superseded by the answer below): Python and Pydantic exist; no analytical engine is selected; Snowflake remains prohibited.
- Owner: Eray (M0-ARCH). Original suggestion: suggested lane A with B review.
- Status: ANSWERED (2026-09-09, M0-ARCH).
- Answer / evidence: DuckDB over Parquet in a bronze/silver/gold medallion, with Pandas for in-process transformation, recorded in [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse). Polars rejected as a third dataframe dialect at this corpus size. Spreadsheet reading is split by trust boundary between [DEC-111](DECISIONS.md#dec-111--openpyxl-for-the-untrusted-xlsx-boundary) and [DEC-114](DECISIONS.md#dec-114--pandas-with-calamine-for-operator-fetched-bulk-spreadsheets). Unblocks M1-03, M1-06 and the M2/M6 engine-dependent tasks; implemented in M12.

### Q-TEAM-03 — Frontend framework

- [x] Record UI choice after confirming demo environment and operator needs.
- Question: Which frontend approach delivers the required upload/plan/result/evidence/follow-up flow with the least setup risk?
- Why it matters: UI polish must not outrun backend acceptance or environment compatibility.
- Blocks which milestone? M10 implementation choice.
- Can we proceed before answer? YES for flow specification; NO for framework commitment.
- Temporary assumption (superseded by the answer below): Minimal clear UI, no chosen framework or hosting product.
- Owner: Eray (M0-ARCH). Original suggestion: suggested lane C with B deployment review.
- Status: ANSWERED (2026-09-09, M0-ARCH).
- Answer / evidence: FastAPI with server-sent events behind a Next.js client using Tailwind, shadcn/ui, TanStack Table, react-plotly.js and React Flow, recorded in [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end). The team has front-end capacity and the trust layer is only visible if lineage is rendered. Streamlit is retained as an explicitly recorded fallback if front-end work starts delaying backend acceptance. Q-DEMO-01 and Q-INFRA-01 still shape hosting, not the framework choice. Implemented in M10.

### Q-TEAM-04 — Causality implementation and prerequisites

- [x] Record method, supported claims, sample/assumption rules, and scope decision.
- Question: Which statistical/causality method, if any, is defensible within the deadline and actual data, and when must it abstain?
- Why it matters: A named test is not sufficient evidence of causal identification.
- Blocks which milestone? M6 advanced method; M9 method-specific oracles; not change/association/abstention baseline.
- Can we proceed before answer? YES for deterministic descriptive statistics and causal-discipline tests; NO for claiming an exact causal method is agreed.
- Temporary assumption (superseded by the answer below): Report association honestly; advanced causal inference stays unselected/optional pending need and review.
- Owner: Eray (M0-ARCH). Original suggestion: suggested lane A/C statistical review.
- Status: ANSWERED (2026-09-09, M0-ARCH).
- Answer / evidence: Lagged cross-correlation plus Granger tests via `statsmodels`, with `ruptures` for structural breaks, and mandatory printed limitations, recorded in [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits). Sixty to sixty-six monthly observations cannot identify a causal effect, so the system never emits an "X causes Y" claim and Granger output is reported as predictive precedence. Implemented in M6; abstention and phrasing tested in M9.

### Q-TEAM-05 — Workspace persistence and reference storage

- [x] Record the minimum persistence mechanism after lifetime/reset requirements are known.
- Question: Is in-process state sufficient, or do confirmed demo requirements require a local durable store and restore behavior?
- Why it matters: Explicit state is mandatory; a specific database is not.
- Blocks which milestone? M5 durable storage selection and M10/M11 restart acceptance.
- Can we proceed before answer? YES for explicit model/state-transition tests; NO for a database commitment or durability claim.
- Temporary assumption (superseded by the answer below): Preserve state explicitly within a workspace; persistence engine remains deferred.
- Owner: Eray (M0-ARCH). Original suggestion: suggested lane B with C operator input.
- Status: ANSWERED (2026-09-09, M0-ARCH).
- Answer / evidence: An artifact DAG persisted in DuckDB, recorded in [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag). Adding a column adds a node rather than rebuilding the table, which is what the organizer's incremental scenario requires, and the same structure supplies replay and cache invalidation. No separate persistence engine is needed once DEC-112 puts DuckDB in the stack. Cross-process durability and reset semantics still depend on Q-INFRA-02 and Q-DEMO-02. Implemented in M5.
