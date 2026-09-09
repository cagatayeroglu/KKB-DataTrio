# Decision log

This file owns constraints and reasons for choices. [ROADMAP](ROADMAP.md) owns implementation status; [OPEN_QUESTIONS](OPEN_QUESTIONS.md) owns unanswered questions. CONFIRMED does **not** mean implemented.

Evidence policy: organizer constraints below are carried forward from the original repository decision log and agent instructions. They are **team-reported**; no primary organizer rulebook or dated confirmation is attached. Add the actual response/reference when received. Do not invent an approval, quotation, or date. Record authorized changes here before changing a hard constraint.

“Original date unrecorded” means exactly that. The review date is not a claimed decision date.

## Confirmed organizer constraints

### DEC-001 — Python and generic sources

- Status: CONFIRMED — carried forward from team-provided constraints.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Python is the primary backend/analytics language. Demo/hidden inputs may use sources other than BDDK or EVDS.
- Reason: Meet the supplied challenge scope and handle unseen inputs.
- Alternatives: A different primary language or source-specific core is outside the current constraint set.
- Consequences: Isolate source-specific retrieval/naming behind adapters; preserve unknown semantics.
- Revisit trigger: Organizer-confirmed language or input-scope change with evidence.

### DEC-002 — Delivered LLM access through Kloudeks

- Status: CONFIRMED — carried forward from team-provided constraints.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Runtime model access uses KKB/Kloudeks only. Do not add third-party LLM APIs to the delivered product. Open-weight models are expected through that platform; do not assume high-parameter models are available.
- Reason: Comply with supplied runtime restrictions and remain usable with constrained models.
- Alternatives: Direct OpenAI/Anthropic/Gemini or other third-party runtime access is excluded under current rules.
- Consequences: Endpoint, authentication, model IDs, and structured-output capabilities remain unresolved. Development-assistant permission is a separate question, Q-DEV-01.
- Revisit trigger: Written organizer change to runtime access rules.

### DEC-003 — No Snowflake; fine-tuning not required

- Status: CONFIRMED — carried forward from team-provided constraints.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Do not use Snowflake. Fine-tuning is not an organizer-required deliverable according to the supplied constraints.
- Reason: Stay within challenge scope and the delivery window.
- Alternatives: Analytical engine and orchestration choices remain open; absence of a fine-tuning requirement is not a ban on justified future experiments.
- Consequences: Build a measurable baseline first; do not allocate a training pipeline by default.
- Revisit trigger: Organizer correction or benchmark evidence supporting a time-boxed experiment.

### DEC-004 — Understandable development history

- Status: CONFIRMED — team-reported review expectation.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Preserve understandable development history because code progression may be reviewed. Exact judging requirements are unconfirmed.
- Reason: Make engineering work traceable.
- Alternatives: No specific commit format or review mechanism is mandated by the available evidence.
- Consequences: Keep changes coherent and obey Git authorization; ask Q-JUDGE-02 for submission/history requirements.
- Revisit trigger: Organizer specifies the review/submission format.

## Confirmed team decisions

### DEC-101 — Typed plans; deterministic calculations

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: LLMs interpret, plan, route, propose schema mappings, and summarize. Typed tools perform material calculations and statistical tests. Validate names/arguments before dispatch.
- Reason: Numeric correctness must be testable independently of model prose.
- Alternatives: Free-form model calculations and arbitrary generated-code execution are rejected.
- Consequences: Structural plan parsing alone is insufficient; registry, argument, reference, and capability checks are required.
- Revisit trigger: A tool-contract change; deterministic calculation remains a requirement.

### DEC-102 — Model-independent provider boundary

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Isolate Kloudeks specifics behind `LLMProvider`.
- Reason: Keep model changes out of analytics and evaluation code.
- Alternatives: Provider-specific calls embedded in tools would couple unrelated components.
- Consequences: Use synthetic provider doubles while access is unresolved. A non-networking stub is not a live integration.
- Revisit trigger: Confirmed platform capabilities require an interface adjustment.

### DEC-103 — Common data contracts and explicit workspace

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Use a common source-adapter/data-contract layer and explicit multi-turn analysis state.
- Reason: Support unfamiliar sources and preserve context without relying on chat history.
- Alternatives: BDDK/EVDS-specific core types and conversation-only state are rejected.
- Consequences: Record selections, semantics, transformations, assumptions, results, and evidence. Storage engine/persistence format are not decided.
- Revisit trigger: A concrete source or multi-turn requirement exposes a contract gap.

### DEC-104 — Traceable answers and explicit transformations

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Material answers link to source, transformation, and validation evidence. Unknown unit/frequency/stock-flow/cumulative semantics must not be guessed silently.
- Reason: Correct-looking numbers can be wrong when semantics or provenance are missing.
- Alternatives: Silent resampling/imputation and unsupported causal assertions are rejected.
- Consequences: Allow clarification, partial results, and abstention; a verifier must gate claims.
- Revisit trigger: A new operation needs an explicit policy; do not weaken evidence requirements for latency.

### DEC-105 — Early evaluation; simple orchestration baseline

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Build the benchmark harness early. Add orchestration complexity only for measured need.
- Reason: Hidden-input correctness and fast feedback matter more than infrastructure sophistication.
- Alternatives: Framework-first work or an elaborate agent topology without demonstrated need is deferred.
- Consequences: This does not select a custom loop, LangGraph, router model, or multi-agent topology.
- Revisit trigger: Repeated measured failures that a specific orchestration capability would resolve.

### DEC-106 — Boundary security and tiered checks

- Status: CONFIRMED.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Treat external/model content as untrusted; prohibit arbitrary runtime Python/shell execution and direct execution of model SQL. Validate tools, files, and URLs centrally. Keep ordinary checks fast.
- Reason: Protect likely hackathon failure paths without enterprise infrastructure.
- Alternatives: Unrestricted execution and heavy scans after every small task are rejected.
- Consequences: Security-sensitive code changes require negative tests. [AGENTS](../AGENTS.md) owns gate triggers; [SECURITY](SECURITY.md) owns control acceptance.
- Revisit trigger: Deployment/input scope changes or an actual boundary failure.

### DEC-107 — Integration and demo-stable branches

- Status: CONFIRMED — standardized by DEC-109.
- Date: Original date unrecorded; workflow updated 2026-09-08.
- Decision: Feature work goes through PRs to `dev`; `main` holds demo-stable checkpoints.
- Reason: Separate ongoing work from reproducible demonstrations.
- Alternatives: Routine direct development on `main` is outside the agreed workflow.
- Consequences: DEC-109 authorizes routine task branch/commit/push/PR operations for assigned work. Never implement on or push directly to `dev`/`main`; merging an agent's own PR still requires explicit instruction. Repository settings remain outside normal task authorization.
- Revisit trigger: Team explicitly changes integration policy.

### DEC-108 — Living roadmap and lightweight handoffs

- Status: CONFIRMED — requested in this documentation task.
- Date: 2026-09-08.
- Decision: ROADMAP is execution/status truth. Update only relevant tasks after meaningful work, with validated checkboxes, evidence, blockers, and next task.
- Reason: Three teammates must resume work without reconstructing chat history.
- Alternatives: Chat-only status and mandatory rewrites of every document are rejected.
- Consequences: As standardized by DEC-109, `[x]` requires merge into `dev` plus passing required targeted validation; document-only work requires verified edits and merge too. Local/feature-branch work stays PARTIAL / IN PROGRESS. Normal reading remains decisions, relevant roadmap section, and one relevant technical document.
- Revisit trigger: Handoffs omit necessary information or maintenance becomes slower than the work.

### DEC-109 — Fresh-dev task branches and merge-based completion

- Status: CONFIRMED — explicitly requested by the team in this workflow-standardization task.
- Date: 2026-09-08.
- Decision: Keep `dev` for shared integration and `main` for stable/demo-ready checkpoints. Every meaningful implementation task starts from freshly updated `dev` on a separate short-lived branch: prefer `feature/<milestone>-<task>`, `fix/<short-description>`, or `docs/<short-description>`. Implement, run targeted checks, update only the relevant ROADMAP record, commit clearly, push the task branch, and open a PR into `dev`. Work is COMPLETE/[x] only after merge into `dev` and passing required validation.
- Reason: Any teammate can pull latest `dev`, inspect READY tasks, and continue without inheriting unfinished feature work or mistaking local validation for shared delivery.
- Alternatives: Direct implementation/push on `dev` or `main`, reusing old feature branches, starting from unfinished feature work without an explicit documented dependency, and treating every task as a release gate are rejected.
- Consequences: Codex may perform normal Git/terminal branch, commit, push, and PR operations for an assigned task. It must not merge its own PR without explicit instruction or force-push shared branches. Delete task branches only after reviewed/verified merge and safe cleanup; start the next task from newly updated `dev`. Record Status, Owner, Branch, PR, Commit, Tests, and Handoff per active task. Approximately every 3–4 days or at an important stable milestone, prepare `dev -> main` only when integrated `dev` is demo-ready. Normal tasks use targeted checks/`make quick`; code PRs use the fast PR gate; full/release checks belong to main/final-demo checkpoints or explicit requests. Documentation-only work uses document checks. This supersedes earlier workflow, checkbox-completion, and automatic boundary-full-gate wording; security controls and targeted negative tests remain required.
- Revisit trigger: Explicit team workflow change. An explicit task-specific exception must record its branch/base and reason; the original documentation update stayed on `feature/day0-core` and merged in PR #1, without authorizing reuse for future unrelated tasks. DEC-110 standardizes DONE terminology and fresh-session ownership checks.

### DEC-110 — Repository-based startup, ownership, and handoff

- Status: CONFIRMED — explicitly requested for the teammate/bootstrap documentation task on 2026-09-08.
- Decision: A fresh session must continue from Git/PR history, ROADMAP, DECISIONS, and only relevant technical documentation, without chat history. Active task states are READY, IN PROGRESS, BLOCKED, PARTIAL, DONE; READY has no active owner. DONE requires implementation, passing required validation, merge into `dev`, and updated roadmap evidence. Legacy COMPLETE uses the same evidence threshold.
- Reason: Three developers must discover safe independent work and resume another session without guessing project state or ownership.
- Operating mechanism: Publish the ROADMAP claim on the fresh task branch with a draft PR before implementation; update the same PR for delivery. Inspect active PR/branch claims as well as `dev`. A local-only claim is invisible, and PR publication is not an atomic lock; stop overlapping work on a collision and confirm ownership. The bootstrap task itself follows the user's explicit instruction to open its PR after document validation.
- Consequences: No silent takeover based on age. Inspect branch/PR/Handoff, confirm activity with the owner/team, and record transfers explicitly. Independent tasks use separate branches from latest `dev`; prefer waiting for dependency merge, with explicit documented authorization for stacking. Report evidence mismatches and unresolved selection decisions. Preserve the existing targeted/fast/full gate split.
- Revisit trigger: Explicit team coordination change or repeated claim collisions. No fixed developer-to-task mapping, automatic stale timeout, or new tracking service is selected.

### DEC-111 — openpyxl for the untrusted XLSX boundary

- Status: CONFIRMED — approved for M1-09 on 2026-09-08; scope narrowed on 2026-09-09 by DEC-114.
- Date: 2026-09-08; amended 2026-09-09.
- Decision: Use `openpyxl>=3.1,<4` for XLSX input that the system does not control — demo-day uploads and files fetched from a prompt-supplied URL — and for deterministic synthetic fixture creation. [M1-10's bounded loader](../src/kkb_agent/xlsx_loader.py) is that boundary.
- Reason: One library supports both runtime reading and fixture writing, and the delivered loader wraps it in the streamed package validation, resource budgets and terminated worker that untrusted input requires.
- Alternatives: A separate writer or another XLSX library is unnecessary here. This does not select the analytical engine.
- Consequences: Macro execution remains unsupported. Explicit sheet selection is required when ambiguous and financial semantics are never inferred. Bulk reading of operator-fetched bulletins is **out of this decision's scope** and belongs to DEC-114; the per-file worker and five-second parser deadline are sized for one hostile upload, not for a multi-year bulletin corpus.
- Revisit trigger: A concrete XLSX compatibility or resource-limit failure in the untrusted-input path that openpyxl cannot handle within the hackathon scope.

### DEC-112 — DuckDB and Parquet as the analytical engine and lakehouse

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-02](OPEN_QUESTIONS.md#q-team-02--analyticalparsing-engine).
- Date: 2026-09-09.
- Decision: DuckDB over Parquet files is the storage and query engine, organized as a medallion lakehouse: `bronze` holds the retrieved artifact plus its hash and retrieval time, `silver` holds normalized series with explicit semantics, `gold` holds analysis-ready facts. Pandas is the in-process transformation and table-shaping library. Polars is not adopted.
- Reason: The organizer brief names DuckDB and Pandas; both run in-process with no server to deploy or fail during the demo. Parquet plus DuckDB gives typed columnar storage, SQL for the `lakehouse` tool, and a file layout that is directly deliverable as the required database definition.
- Alternatives: Polars is faster on large frames but adds a third dataframe dialect for a corpus measured in tens of thousands of rows. A hosted warehouse is excluded by DEC-003 and by the single-VM deployment in DEC-126. SQLite lacks the analytical functions the tools need.
- Consequences: Unblocks M1-03, M1-06 and the M2/M6 engine-dependent work. Every material calculation stays deterministic under DEC-101; DuckDB executes only validated SQL under DEC-121. Adds `duckdb`, `pandas` and `pyarrow` to the runtime manifest in DEC-124.
- Revisit trigger: A measured DuckDB limitation on the actual corpus that Pandas cannot cover.

### DEC-113 — Custom bounded orchestration loop

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-01](OPEN_QUESTIONS.md#q-team-01--orchestration-mechanism).
- Date: 2026-09-09.
- Decision: Implement orchestration as an explicit planner -> router -> executor -> verifier state machine in our own code. The planner produces a typed plan, the router selects a registered tool and typed arguments, the executor dispatches after validation, and the verifier gates the answer. LangChain, LangGraph and Celery are rejected.
- Reason: The lifecycle is a handful of states over a fixed tool set. A framework would add an abstraction whose failure modes we would have to learn during the delivery window, and it obscures exactly the plan/validation boundary DEC-101 requires us to test.
- Alternatives: LangGraph offers graph state management we do not need at this size; both rejected frameworks also pull dependency surface that DEC-124 excludes.
- Consequences: We own retry, repair and cancellation behavior explicitly, with bounded counts. Confirms the DEC-105 preference as a selected implementation. M5 delivers this loop.
- Revisit trigger: A concrete lifecycle requirement that a bounded custom loop demonstrably cannot express.

### DEC-114 — pandas with calamine for operator-fetched bulk spreadsheets

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Read spreadsheets that the ingestion layer itself retrieved from a recorded source — the BDDK weekly/monthly bulletins and FinTürk files — with `pandas.read_excel(..., engine="calamine")` backed by `python-calamine`. This path is separate from DEC-111's untrusted boundary and never handles prompt- or upload-supplied files.
- Reason: The bulk path reads many files whose provenance we recorded ourselves, and needs throughput; the untrusted path reads one hostile file and needs containment. One engine cannot be tuned for both. Calamine is materially faster than openpyxl for whole-sheet reads.
- Alternatives: Routing bulletins through the M1-10 loader would force a multi-year corpus through a per-file spawned worker with a five-second deadline and a 100,000-row cap. Replacing openpyxl entirely would discard the delivered untrusted-input containment and the fixture writer.
- Consequences: Two documented XLSX paths with a boundary rule: source retrieved and hashed by `ingest/` -> calamine; source named by a user, model or prompt URL -> M1-10 loader. Adds `python-calamine` and requires `pandas>=2.2`. Bronze retains the original bytes and hash regardless of path.
- Revisit trigger: Calamine failing on an actual BDDK bulletin, or the two paths converging in practice.

### DEC-115 — Hybrid series retrieval over LanceDB and DuckDB FTS

- Status: CONFIRMED — team decision on 2026-09-09; supersedes the deferred vector-database entry.
- Date: 2026-09-09.
- Decision: Index series and column metadata in LanceDB for dense retrieval and in DuckDB's full-text index for BM25, fuse the two result sets with reciprocal rank fusion, take the top 20 and reduce to a final five by listwise reranking with a small model that returns JSON. A second LanceDB collection holds document chunks retrieved by the `web_url` tool.
- Reason: EVDS exposes far more series than fit in a prompt, and Turkish financial phrasing rarely matches a series title exactly. Lexical search alone misses paraphrase; dense search alone misses exact codes and rare terms. RRF needs no score calibration between the two.
- Alternatives: A dedicated cross-encoder reranker is not assumed available (Q-K-05) and listwise LLM reranking substitutes for it. Elasticsearch is rejected by DEC-124; a bespoke vector store is unjustified when the brief names LanceDB.
- Consequences: Adds `lancedb` to the manifest and a DuckDB FTS index over catalog metadata. Retrieval quality must be measured, not assumed — see DEC-116. Embedding model, dimension and any query/passage prefix remain blocked on Q-K-05.
- Revisit trigger: Measured recall that stays weak after alias and BM25 weighting are exhausted.

### DEC-116 — Alias dictionary, single Turkish normalizer, and a measured recall floor

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Maintain a hand-written dictionary of roughly fifty Turkish financial concepts mapped to series identifiers. An exact alias hit bypasses retrieval entirely. All Turkish normalization — dotted/dotless i, case folding, diacritic removal — goes through one function used by both indexing and querying. Hand-write fifty query-to-series pairs and measure recall@10 before relying on embeddings.
- Reason: Retrieval quality cannot be assumed for Turkish financial vocabulary on an unknown embedding model. Normalizing differently at index and query time silently halves recall, and the failure is invisible without a measurement.
- Alternatives: Trusting embeddings without an oracle set would leave a demo-day failure undetectable in advance. Separate normalization helpers were rejected precisely because they drift.
- Consequences: M13 owns the dictionary, the normalizer and the recall measurement. A weak measured result shifts weight toward BM25 and the alias dictionary rather than triggering model changes we cannot make. The evaluation pairs feed M9.
- Revisit trigger: A measured recall change after any catalog, embedding or normalization change.

### DEC-117 — Analysis workspace as a persisted artifact DAG

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-05](OPEN_QUESTIONS.md#q-team-05--workspace-persistence-and-reference-storage).
- Date: 2026-09-09.
- Decision: Represent the analysis workspace as a directed acyclic graph of artifacts stored in DuckDB. A follow-up that adds a column adds a node; existing nodes and their computed cells are not rebuilt. Replaying the graph reproduces a result, and node identity drives cache invalidation.
- Reason: The organizer's reference scenario is explicitly incremental — inflation-adjust one column, then add another, without disturbing the table. Regenerating the table each turn is how stale or silently changed numbers reach the user. The same structure gives reproducibility and cache behavior without a second mechanism.
- Alternatives: Rebuilding from scratch per turn fails the stated requirement. Chat history as state is rejected by DEC-103. A separate persistence engine is unnecessary once DEC-112 puts DuckDB in the stack.
- Consequences: Every artifact needs a stable content-addressed identity and recorded inputs. Session and workspace state live in DuckDB alongside the lakehouse. M5 implements it; M10 renders it.
- Revisit trigger: A confirmed demo requirement for cross-process durability or reset semantics beyond a single-VM store (Q-INFRA-02, Q-DEMO-02).

### DEC-118 — Lineage graph as the provenance substrate

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Record provenance as a typed graph with node kinds `SourceFile`, `Series`, `Transform`, `Column`, `Metric` and `Claim`, and edge kinds `derives_from`, `aggregates`, `deflates_by` and `cites`. Store it as `lineage_nodes` and `lineage_edges` in DuckDB with hash-addressed identifiers; traverse it in memory with `networkx`. Every numeric claim carries a `claim_id` whose subgraph is the evidence panel. A cell without lineage is a defect, not a missing feature.
- Reason: DEC-104 requires each material claim to be traceable to source, transformation and validation. A typed graph is what makes "trace this number" a query rather than a narrative, and the evidence panel is the visible form of the trust layer the brief asks for.
- Alternatives: A graph database is rejected by DEC-124 for a few thousand nodes. Free-text provenance notes cannot be verified mechanically.
- Consequences: Every code path that produces a number must write lineage; M8 owns the writer and query surface, and M9 tests that provenance survives ingestion and normalization. Adds `networkx`.
- Revisit trigger: Graph size or query patterns that DuckDB plus networkx cannot serve.

### DEC-119 — Verifier gates the answer

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: No answer reaches the user before the verifier passes it. Every number in the response text must resolve to a cell in an artifact, or the answer is rejected. Units and scales are checked. Each headline metric is recomputed by a second independent path — SQL against Pandas — and compared. Model-extracted content from a document or image is never written straight into a table: it must satisfy a schema and a total or consistency check first, and otherwise the system states that it could not extract reliable data from that source.
- Reason: A hallucinated number that enters lineage silently is worse than an abstention, because the trust layer then certifies it. Recomputation on a second path catches the transformation errors that unit tests on fixtures do not.
- Alternatives: Trusting the generation step, or checking only formatting, leaves exactly the failure mode the brief's trust layer exists to prevent.
- Consequences: M8 implements the verifier; abstention is a first-class outcome with its own tests in M9. Adds latency per turn, which is accepted.
- Revisit trigger: A measured verifier false-rejection rate that blocks correct answers.

### DEC-120 — Causality reports association with stated limits

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-04](OPEN_QUESTIONS.md#q-team-04--causality-implementation-and-prerequisites).
- Date: 2026-09-09.
- Decision: The `causality` tool computes lagged cross-correlation and Granger causality tests using `statsmodels`, with `ruptures` for structural breaks and `scipy` for supporting statistics. Its output must always carry its limitations: small sample, common drivers such as inflation and the policy rate, and structural breaks in the window. The system does not emit a sentence of the form "X causes Y".
- Reason: Sixty to sixty-six monthly observations cannot identify a causal effect, and a finance jury knows it. Presenting an honest, well-qualified association is more defensible than an overclaim, and it satisfies the brief's causality tool without pretending to more.
- Alternatives: Structural causal models or instrumental variables need assumptions this data cannot support in the window. Omitting the tool would miss a named brief requirement.
- Consequences: M6 implements the tool; its abstention and phrasing rules are tested in M9. Granger results are reported as predictive precedence, never as mechanism.
- Revisit trigger: A dataset and identification strategy that genuinely support a stronger claim, plus statistical review.

### DEC-121 — Six brief-named tools with typed schemas and restricted SQL

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Expose exactly the six tools the brief names, spelled the same way: `lakehouse`, `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`. Define each tool's arguments once as a Pydantic v2 model, and derive both the JSON schema shown to the model and the runtime validation from that single definition. The `lakehouse` tool performs restricted text-to-SQL: generated SQL is parsed, checked against a schema whitelist, dry-run through `EXPLAIN`, and only then executed read-only. It never generates or executes free-form Python.
- Reason: Matching the brief's tool names makes the deliverable legible to the jury. A single schema source removes the drift between what the model is told and what the executor accepts. Restricting SQL keeps DEC-101's determinism and AGENTS' prohibition on executing model-generated code intact while still allowing natural-language querying.
- Alternatives: Renaming the tools obscures the mapping to the brief. Duplicating schemas by hand drifts. Free-form generated Python is prohibited outright.
- Consequences: M5 owns the registry and the argument validation; M6 owns `anomaly`, `causality` and `change_detection`; M7 owns `web_search` and `web_url`. Tool additions need their own decision entry.
- Revisit trigger: An organizer clarification changing the tool set or its names.

### DEC-122 — LLMProvider interface and structured-output fallback

- Status: CONFIRMED — team decision on 2026-09-09; implements the DEC-102 boundary.
- Date: 2026-09-09.
- Decision: All model access goes through one `LLMProvider` interface exposing `complete(messages, *, model, schema=None)`, `embed(texts, *, kind="query"|"passage")` and `vision(image_bytes, prompt)`. Model identifier, base URL and whether structured output is supported come from environment configuration, never from source constants. When the platform offers no structured-output mode, the provider validates against the Pydantic schema, repairs with `json-repair`, and retries at most twice while feeding the validation error back to the model.
- Reason: Kloudeks capabilities are unresolved (Q-K-01/02/03) and may differ per model. Confining that uncertainty to one file means a platform change edits one module rather than the planner, router and tools.
- Alternatives: Calling the platform directly from each caller couples every component to an unconfirmed API. Assuming structured output exists would strand the planner if it does not.
- Consequences: Keeps the DEC-002 constraint enforceable by inspection: no third-party LLM client, import or environment variable appears anywhere in the product. The `kind` argument exists because an E5-family embedding model silently loses quality without its `query:`/`passage:` prefix. M4 implements the provider; the interface is testable now with a synthetic double.
- Revisit trigger: Confirmed platform capabilities that make a method unnecessary or require another.

### DEC-123 — FastAPI with SSE behind a Next.js front end

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-03](OPEN_QUESTIONS.md#q-team-03--frontend-framework).
- Date: 2026-09-09.
- Decision: Serve the application from FastAPI, streaming plan and tool progress to the client over server-sent events. Build the user interface in Next.js with Tailwind and shadcn/ui, TanStack Table for the analysis table, `react-plotly.js` for charts, and React Flow for the evidence panel that renders a claim's lineage subgraph.
- Reason: The deliverable is a deployed working system that a jury operates, and the trust layer is only visible if provenance is rendered. Streaming the tool steps makes a multi-step analysis legible while it runs instead of after it finishes. The team has front-end capacity, so the stronger presentation is worth its cost.
- Alternatives: Streamlit needs less work and remains the fallback if front-end capacity disappears, but it renders a lineage graph poorly. A static rendered report would not support the multi-turn scenario.
- Consequences: The web client lives in `web/` at the repository root, outside the Python package (DEC-125). M10 owns it. The API contract must be stable before the front end is built against it; the front end is not a prerequisite for backend acceptance and must not gate M5–M8.
- Revisit trigger: Front-end work measurably delaying backend acceptance, in which case the Streamlit fallback is taken deliberately and recorded.

### DEC-124 — Dependency manifest and excluded technologies

- Status: CONFIRMED — team decision on 2026-09-09; extends DEC-003.
- Date: 2026-09-09.
- Decision: The runtime manifest is limited to `duckdb`, `pandas>=2.2`, `pyarrow`, `python-calamine`, `openpyxl`, `pydantic>=2`, `json-repair`, `lancedb`, `networkx`, `statsmodels`, `ruptures`, `scipy`, `plotly`, `kaleido`, `pypdf`, `pdfplumber`, `httpx`, `tenacity`, `diskcache` and `fastapi` with its server. The following are excluded regardless of individual merit: Spark, Airflow, dbt, Kubernetes, Elasticsearch, Neo4j, LangChain, Celery, Redis, Prophet and PyOD. Camelot and tabula are excluded specifically because they require a Java runtime. Any addition needs its own decision entry naming the concrete need.
- Reason: Every dependency is integration and demo risk before it is a feature. The excluded list is not a quality judgment; none of them earns its setup and failure surface inside this delivery window, and several duplicate capability the stack already has.
- Alternatives: Considering each candidate ad hoc during implementation is how a stack grows past what a three-person team can deploy and debug.
- Consequences: Statistics stay explainable rather than delegated to an opinionated forecasting library. Caching is a local disk cache, not a service. The implementation task that follows M0-ARCH reconciles `pyproject.toml` with this list, and may adopt `uv` for environment management provided `make install-dev`, `make quick`, `make pr` and `make full` keep their current names and behavior.
- Revisit trigger: A measured, specific requirement that nothing in the manifest covers.

### DEC-125 — Source layout with named module packages

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Keep the installable `src/` layout and place the architecture's modules as packages beneath it: `src/kkb_agent/{app,agent,tools,ingest,transform,catalog,lineage,llm,eval}/`. The Next.js client lives in `web/` at the repository root; `docs/`, `scripts/` and `tests/` keep their current positions.
- Reason: The module names make the architecture readable in the tree, while the `src/` layout preserves the working packaging, the strict mypy target, the Makefile commands and the CI paths. A flat top-level layout would rewrite all of those for a naming preference.
- Alternatives: Top-level module directories match an external sketch more literally but move 245 passing tests and every tooling path for no functional gain.
- Consequences: Imports stay `kkb_agent.<module>`. Existing modules move into these packages only when a task actually touches them; no bulk relocation is performed for its own sake. The list names the packages the architecture sketch implied; it is not a ceiling. A package that maps to a numbered ARCHITECTURE component may be added with its task — `lakehouse` was added by M12-01 for [component 12](ARCHITECTURE.md#12-lakehouse-and-medallion-layout--confirmed-storage-dec-112).
- Revisit trigger: A packaging or deployment requirement the `src/` layout cannot meet.

### DEC-126 — Single-VM deployment with Docker Compose

- Status: CONFIRMED as our target — team decision on 2026-09-09; the environment itself remains blocked on [Q-INFRA-01](OPEN_QUESTIONS.md#q-infra-01--runtimedeployment-environment).
- Date: 2026-09-09.
- Decision: Deploy as containers on a single virtual machine, composed with Docker Compose and fronted by Caddy for TLS and routing. Kubernetes and managed orchestration are excluded.
- Reason: The deliverable must be running and reachable on demo day. One host with one compose file is the topology a three-person team can rebuild under pressure, and it makes the required architecture and database definitions straightforward to hand over.
- Alternatives: Kubernetes adds an orchestration layer with no benefit at one host. Serverless would fragment the DuckDB and Parquet state this architecture depends on.
- Consequences: State lives on a mounted volume; a demo rehearsal must include a cold start. If the organizer supplies a fixed environment under Q-INFRA-01, this decision yields to it and is amended rather than defended.
- Revisit trigger: The organizer's answer to Q-INFRA-01.

## Proposed decisions

Candidates below are not approved selections. Compare options in a bounded task; do not silently promote a proposal to CONFIRMED.

| ID | Proposal | Alternatives / evidence needed | Owner | Next action |
| --- | --- | --- | --- | --- |
| PROP-01 | RESOLVED by DEC-113 | Custom bounded loop selected; LangGraph and other frameworks rejected | Eray | None; implement in M5 |
| PROP-02 | RESOLVED by DEC-112 | DuckDB with Parquet and Pandas selected; Polars rejected | Eray | None; implement in M12 |
| PROP-03 | RESOLVED by DEC-123 | FastAPI with SSE behind Next.js selected; Streamlit retained as a recorded fallback | Eray | None; implement in M10 |
| PROP-04 | Retry and latency budgets | Exact counts/timeouts depend on platform limits and baseline measurements | Unassigned | Obtain Q-K-04 and measure before fixing limits |
| PROP-05 | RESOLVED by DEC-120 | Lagged correlation and Granger with mandatory stated limits; stronger identification rejected for this data | Eray | None; implement in M6 |

## Deferred decisions

| Topic | Status | Why deferred | Revisit trigger |
| --- | --- | --- | --- |
| Router fine-tuning | DEFERRED; no training approach selected | No measured routing baseline or confirmed resources | Persistent routing errors after simpler fixes, plus time/compute |
| Vector DB / embeddings / reranking | RESOLVED by DEC-115; LanceDB with DuckDB FTS, RRF and listwise reranking | Superseded: the EVDS series count makes catalog retrieval a requirement, not a scale question | Embedding model, dimension and prefixes still need Q-K-05 |
| Multi-agent topology | DEFERRED; none selected | Added coordination cost is not justified | A bounded independent role measurably improves results |
| Workspace persistence backend | RESOLVED by DEC-117; artifact DAG persisted in DuckDB | Superseded: DEC-112 already places DuckDB in the stack, so no separate engine is needed | Cross-process durability and reset semantics still need Q-INFRA-02 and Q-DEMO-02 |
| GPU/training deployment | DEFERRED | Resource availability/need unknown | Q-COMP-01 answered and workload requires it |
| Enterprise security infrastructure | DEFERRED | Outside 8–9 day scope | Concrete production/organizer requirement |

Exact Kloudeks endpoint, authentication and model identifiers remain **UNDECIDED and externally blocked** (Q-K-01/02/03), as do the embedding model and its prefix convention (Q-K-05) and the vision model's limits. These are not preferences to settle by guessing; DEC-122 exists so that answering them changes one module.

Orchestration, analytical engine, frontend framework, causality method and workspace persistence are **no longer open** — see DEC-112, DEC-113, DEC-117, DEC-120 and DEC-123. Router fine-tuning and multi-agent topology remain deferred.

## Maintenance

Add an ADR when a constraint or choice actually changes. Use the fields above and link the answer, experiment, or PR. Keep rejected alternatives brief. Update OPEN_QUESTIONS for unresolved issues and ROADMAP for implementation progress.
