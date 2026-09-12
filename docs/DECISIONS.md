# Decision log

This file owns constraints and reasons for choices. [ROADMAP](ROADMAP.md) owns implementation status; [OPEN_QUESTIONS](OPEN_QUESTIONS.md) owns unanswered questions. CONFIRMED does **not** mean implemented.

Evidence policy: organizer constraints below are carried forward from the original repository decision log and agent instructions. They are **team-reported**; no primary organizer rulebook or dated confirmation is attached. Add the actual response/reference when received. Do not invent an approval, quotation, or date. Record authorized changes here before changing a hard constraint.

“Original date unrecorded” means exactly that. The review date is not a claimed decision date. Status vocabulary: CONFIRMED is authorized direction; SUPERSEDED retains history but is no longer governing; PROPOSED needs review/evidence; BLOCKED needs the named answer; DEFERRED is outside the current delivery path. Implementation progress belongs only in ROADMAP.

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
- Consequences (updated 2026-09-09 by DEC-129, restated 2026-09-10 by DEC-131): Endpoint, MIA-key authentication and model IDs/capabilities are now officially recorded below. The `openai` SDK configured exclusively for Kloudeks is allowed; third-party hosted LLM access remains prohibited. The kick-off deck restates this prohibition verbatim at primary-source level, so it is not a relayed interpretation. Native tool/structured-output support and remaining limits are unresolved. Development-assistant permission was the separate question Q-DEV-01 and is **ANSWERED (2026-09-10): permitted for development only.** It grants nothing at runtime; this decision is unchanged.
- Revisit trigger: Written organizer change to runtime access rules.

### DEC-003 — No Snowflake; fine-tuning not required

- Status: CONFIRMED — carried forward from team-provided constraints.
- Date: Original date unrecorded; reviewed 2026-09-08.
- Decision: Do not use Snowflake. Fine-tuning is not an organizer-required deliverable according to the supplied constraints.
- Reason: Stay within challenge scope and the delivery window.
- Alternatives: Analytical engine and orchestration choices remain open; absence of a fine-tuning requirement is not a ban on justified future experiments.
- Consequences: Build a measurable baseline first; do not allocate a training pipeline by default.
- Revisit trigger: Organizer correction or benchmark evidence supporting a time-boxed experiment.
- Clarification (2026-09-09): Engine and orchestration were subsequently selected in DEC-112/113; the earlier open-choice wording is historical.

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
- Clarification (2026-09-09): Storage and persistence were subsequently selected in DEC-112/117; the earlier undecided wording is historical.

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
- Clarification (2026-09-09): DEC-113 subsequently selected the custom bounded loop; this early decision did not select it by itself.

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
- Clarification (2026-09-09): Recorded provenance does not make external bytes trusted. This bulk-parser choice does not waive SEC-URL/SEC-FILE bounds, TLS, or source-use permission. The operator adapter is still target work.

### DEC-115 — Hybrid series retrieval over LanceDB and DuckDB FTS

- Status: SUPERSEDED by [DEC-127](#dec-127--benchmark-gated-retrieval) on 2026-09-09, explicitly authorized by Çağatay. The original decision below is retained as historical evidence, not an active mandatory pipeline. DEC-127 was subsequently superseded by [DEC-130](#dec-130--initial-hybrid-retrieval-baseline); DEC-115 is not reinstated.
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
- Clarification (updated 2026-09-09): DEC-130 now governs the initial lexical+dense hybrid baseline and requires held-out Recall@5/10, final selection, latency and failure measurements. The earlier measurement wording does not gate use of the confirmed embedding model on lexical failure or prior quality gain. Reviewed aliases may resolve an unambiguous concept but must not bypass metadata, archived-status or semantic checks; ambiguous mappings require resolution. Concept families describe catalog neighborhoods, never causal facts.

### DEC-117 — Analysis workspace as a persisted artifact DAG

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-05](OPEN_QUESTIONS.md#q-team-05--workspace-persistence-and-reference-storage).
- Date: 2026-09-09.
- Decision: Represent the analysis workspace as a directed acyclic graph of artifacts stored in DuckDB. A follow-up that adds a column adds a node; existing nodes and their computed cells are not rebuilt. Replaying the graph reproduces a result, and node identity drives cache invalidation.
- Reason: The organizer's reference scenario is explicitly incremental — inflation-adjust one column, then add another, without disturbing the table. Regenerating the table each turn is how stale or silently changed numbers reach the user. The same structure gives reproducibility and cache behavior without a second mechanism.
- Alternatives: Rebuilding from scratch per turn fails the stated requirement. Chat history as state is rejected by DEC-103. A separate persistence engine is unnecessary once DEC-112 puts DuckDB in the stack.
- Consequences: Every artifact needs a stable content-addressed identity and recorded inputs. Session and workspace state live in DuckDB alongside the lakehouse. M5 implements it; M10 renders it.
- Revisit trigger: A confirmed demo requirement for cross-process durability or reset semantics beyond a single-VM store (Q-INFRA-02, Q-DEMO-02).
- Clarification (2026-09-09): The merged DAG hashes definitions, not immutable output values. `refresh` rebinds definitions; actual recomputation and stale-result rejection remain M5/M8 acceptance work. DEC-128 specifies the stronger proof direction without claiming it exists.

### DEC-118 — Lineage graph as the provenance substrate

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Record provenance as a typed graph with node kinds `SourceFile`, `Series`, `Transform`, `Column`, `Metric` and `Claim`, and edge kinds `derives_from`, `aggregates`, `deflates_by` and `cites`. Store it as `lineage_nodes` and `lineage_edges` in DuckDB with hash-addressed identifiers; traverse it in memory with `networkx`. Every numeric claim carries a `claim_id` whose subgraph is the evidence panel. A cell without lineage is a defect, not a missing feature.
- Reason: DEC-104 requires each material claim to be traceable to source, transformation and validation. A typed graph is what makes "trace this number" a query rather than a narrative, and the evidence panel is the visible form of the trust layer the brief asks for.
- Alternatives: A graph database is rejected by DEC-124 for a few thousand nodes. Free-text provenance notes cannot be verified mechanically.
- Consequences: Every code path that produces a number must write lineage; M8 owns the writer and query surface, and M9 tests that provenance survives ingestion and normalization. Adds `networkx`.
- Revisit trigger: Graph size or query patterns that DuckDB plus networkx cannot serve.
- Clarification (2026-09-09): The merged implementation traverses ancestors directly; no networkx consumer is implemented. DEC-128 defers graph-heavy presentation and optional layout dependency activation; typed backend lineage remains required. Source ancestry alone is not complete claim-level proof.

### DEC-119 — Verifier gates the answer

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: No answer reaches the user before the verifier passes it. Every number in the response text must resolve to a cell in an artifact, or the answer is rejected. Units and scales are checked. Each headline metric is recomputed by a second independent path — SQL against Pandas — and compared. Model-extracted content from a document or image is never written straight into a table: it must satisfy a schema and a total or consistency check first, and otherwise the system states that it could not extract reliable data from that source.
- Reason: A hallucinated number that enters lineage silently is worse than an abstention, because the trust layer then certifies it. Recomputation on a second path catches the transformation errors that unit tests on fixtures do not.
- Alternatives: Trusting the generation step, or checking only formatting, leaves exactly the failure mode the brief's trust layer exists to prevent.
- Consequences: M8 implements the verifier; abstention is a first-class outcome with its own tests in M9. Adds latency per turn, which is accepted.
- Revisit trigger: A measured verifier false-rejection rate that blocks correct answers.
- Clarification (2026-09-09): PR #32 delivers a numeric-binding shell, not full acceptance of this decision. Independent recomputation, semantic/run/result binding and an integrated answer gate remain required; DEC-128 makes their evidence states explicit.

### DEC-120 — Causality reports association with stated limits

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-04](OPEN_QUESTIONS.md#q-team-04--causality-implementation-and-prerequisites).
- Date: 2026-09-09.
- Decision: The `causality` tool computes lagged cross-correlation and Granger causality tests using `statsmodels`, with `ruptures` for structural breaks and `scipy` for supporting statistics. Its output must always carry its limitations: small sample, common drivers such as inflation and the policy rate, and structural breaks in the window. The system does not emit a sentence of the form "X causes Y".
- Reason: Sixty to sixty-six monthly observations cannot identify a causal effect, and a finance jury knows it. Presenting an honest, well-qualified association is more defensible than an overclaim, and it satisfies the brief's causality tool without pretending to more.
- Alternatives: Structural causal models or instrumental variables need assumptions this data cannot support in the window. Omitting the tool would miss a named brief requirement.
- Consequences: M6 implements the tool; its abstention and phrasing rules are tested in M9. Granger results are reported as predictive precedence, never as mechanism.
- Revisit trigger: A dataset and identification strategy that genuinely support a stronger claim, plus statistical review.
- Clarification (2026-09-09): DEC-128 scopes relationship stability to bounded windows; research-grade automatic regime segmentation and causal event attribution are DEFERRED. The named brief tool and deterministic-method decision remain in force.

### DEC-121 — Six brief-named tools with typed schemas and restricted SQL

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Expose exactly the six tools the brief names, spelled the same way: `lakehouse`, `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`. Define each tool's arguments once as a Pydantic v2 model, and derive both the JSON schema shown to the model and the runtime validation from that single definition. The `lakehouse` tool performs restricted text-to-SQL: generated SQL is parsed, checked against a schema whitelist, dry-run through `EXPLAIN`, and only then executed read-only. It never generates or executes free-form Python.
- Reason: Matching the brief's tool names makes the deliverable legible to the jury. A single schema source removes the drift between what the model is told and what the executor accepts. Restricting SQL keeps DEC-101's determinism and AGENTS' prohibition on executing model-generated code intact while still allowing natural-language querying.
- Alternatives: Renaming the tools obscures the mapping to the brief. Duplicating schemas by hand drifts. Free-form generated Python is prohibited outright.
- Consequences: M5 owns the registry and the argument validation; M6 owns `anomaly`, `causality` and `change_detection`; M7 owns `web_search` and `web_url`. Tool additions need their own decision entry.
- Scope clarification (2026-09-10, M6-22): a tool name may cover several operations, named in an `operation` argument rather than split into a new tool. `change_detection` implements `compare` — the level change between two published periods — with breakpoint and trend-break detection joining the same schema when M6-05/06 gives it a method. Keeping an unimplemented operation **out** of the schema is deliberate: a planner cannot request what it is never offered. This uses an existing brief name rather than the addition clause above, which stays unused.
- Amendment (2026-09-12): [DEC-133](#dec-133--eleven-tool-product-target-and-mandatory-harness) uses the addition clause to approve five product tools. The original six-name ceiling and the historical “addition clause unused” observation above are superseded; schemas and restricted SQL controls remain in force. Approval is a target, not evidence of runtime registration.
- Revisit trigger: An organizer clarification changing the tool set or its names.

### DEC-122 — LLMProvider interface and structured-output fallback

- Status: CONFIRMED — team decision on 2026-09-09; implements the DEC-102 boundary.
- Date: 2026-09-09.
- Decision: All model access goes through one `LLMProvider` interface exposing `complete(messages, *, model, schema=None)`, `embed(texts, *, kind="query"|"passage")` and `vision(image_bytes, prompt)`. Model identifier, base URL and whether structured output is supported come from environment configuration, never from source constants. When the platform offers no structured-output mode, the provider validates against the Pydantic schema, repairs with `json-repair`, and retries at most twice while feeding the validation error back to the model.
- Reason: At the original decision, Kloudeks transport/model facts were unresolved. DEC-129 now records them; native tool/structured-output support and remaining limits still need answers. The boundary keeps those changes out of the planner, router and tools.
- Alternatives: Calling the platform directly from each caller couples every component to its API. OpenAI compatibility does not establish guaranteed structured output or native tool calling; neither may be assumed.
- Consequences (corrected by DEC-129): Enforce the destination/service boundary, not an SDK-name ban. The `openai` client is allowed only with the explicit Kloudeks base URL and no hosted-service fallback. The interface remains testable with a synthetic double. `kind` preserves query/passage intent; the confirmed Qwen embedding model's prefix convention is unknown, so an E5 prefix must not be copied by analogy.
- Revisit trigger: Confirmed platform capabilities that make a method unnecessary or require another.

### DEC-123 — FastAPI with SSE behind a Next.js front end

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-03](OPEN_QUESTIONS.md#q-team-03--frontend-framework).
- Date: 2026-09-09.
- Decision: Serve the application from FastAPI, streaming plan and tool progress to the client over server-sent events. Build the user interface in Next.js with Tailwind and shadcn/ui, TanStack Table for the analysis table, `react-plotly.js` for charts, and React Flow for the evidence panel that renders a claim's lineage subgraph.
- Reason: The deliverable is a deployed working system that a jury operates, and the trust layer is only visible if provenance is rendered. Streaming the tool steps makes a multi-step analysis legible while it runs instead of after it finishes. The team has front-end capacity, so the stronger presentation is worth its cost.
- Alternatives: Streamlit needs less work and remains the fallback if front-end capacity disappears, but it renders a lineage graph poorly. A static rendered report would not support the multi-turn scenario.
- Consequences: The web client lives in `web/` at the repository root, outside the Python package (DEC-125). M10 owns it. The API contract must be stable before the front end is built against it; the front end is not a prerequisite for backend acceptance and must not gate M5–M8.
- Revisit trigger: Front-end work measurably delaying backend acceptance, in which case the Streamlit fallback is taken deliberately and recorded.
- Clarification (2026-09-09): DEC-128 defers graph-heavy proof UI. A concise claim/evidence view can serve the first UI; React Flow layout is not a prerequisite for the core slice. Framework choice remains confirmed.

### DEC-124 — Dependency manifest and excluded technologies

- Status: CONFIRMED — team decision on 2026-09-09; extends DEC-003.
- Date: 2026-09-09.
- Decision: The runtime manifest is limited to `duckdb`, `pandas>=2.2`, `pyarrow`, `python-calamine`, `openpyxl`, `pydantic>=2`, `json-repair`, `lancedb`, `networkx`, `statsmodels`, `ruptures`, `scipy`, `plotly`, `kaleido`, `pypdf`, `pdfplumber`, `httpx`, `tenacity`, `diskcache` and `fastapi` with its server. The following are excluded regardless of individual merit: Spark, Airflow, dbt, Kubernetes, Elasticsearch, Neo4j, LangChain, Celery, Redis, Prophet and PyOD. Camelot and tabula are excluded specifically because they require a Java runtime. Any addition needs its own decision entry naming the concrete need.
- Reason: Every dependency is integration and demo risk before it is a feature. The excluded list is not a quality judgment; none of them earns its setup and failure surface inside this delivery window, and several duplicate capability the stack already has.
- Alternatives: Considering each candidate ad hoc during implementation is how a stack grows past what a three-person team can deploy and debug.
- Consequences: Statistics stay explainable rather than delegated to an opinionated forecasting library. Caching is a local disk cache, not a service. The implementation task that follows M0-ARCH reconciles `pyproject.toml` with this list, and may adopt `uv` for environment management provided `make install-dev`, `make quick`, `make pr` and `make full` keep their current names and behavior.
- Revisit trigger: A measured, specific requirement that nothing in the manifest covers.
- Clarification (2026-09-09): This is an allowed dependency manifest, not a claim that all packages are installed or mandatory. DEC-130 includes dense retrieval and the retained LanceDB series index in the initial baseline; RRF, reranking and additional retrieval/vector infrastructure require measured benefit; DEC-128 defers graph-heavy UI. This docs change removes no dependency or code. DEC-129 additionally permits the `openai` SDK solely for the official Kloudeks-compatible transport; dependency installation remains future implementation work.

### DEC-125 — Source layout with named module packages

- Status: CONFIRMED — team decision on 2026-09-09.
- Date: 2026-09-09.
- Decision: Keep the installable `src/` layout and place the architecture's modules as packages beneath it: `src/kkb_agent/{app,agent,tools,ingest,transform,catalog,lineage,llm,eval}/`. The Next.js client lives in `web/` at the repository root; `docs/`, `scripts/` and `tests/` keep their current positions.
- Reason: The module names make the architecture readable in the tree, while the `src/` layout preserves the working packaging, the strict mypy target, the Makefile commands and the CI paths. A flat top-level layout would rewrite all of those for a naming preference.
- Alternatives: Top-level module directories match an external sketch more literally but move 245 passing tests and every tooling path for no functional gain.
- Consequences: Imports stay `kkb_agent.<module>`. Existing modules move into these packages only when a task actually touches them; no bulk relocation is performed for its own sake. The list names the packages the architecture sketch implied; it is not a ceiling. A package that maps to a numbered ARCHITECTURE component may be added with its task — `lakehouse` was added by M12-01 for [component 12](ARCHITECTURE.md#12-lakehouse-and-medallion-layout--confirmed-storage-dec-112), and `analytics` by M6-02/03/04 for component 9.
- Revisit trigger: A packaging or deployment requirement the `src/` layout cannot meet.

### DEC-126 — Single-VM deployment with Docker Compose

- Status: CONFIRMED as our target — team decision on 2026-09-09; the environment itself remains blocked on [Q-INFRA-01](OPEN_QUESTIONS.md#q-infra-01--runtimedeployment-environment).
- Date: 2026-09-09.
- Decision: Deploy as containers on a single virtual machine, composed with Docker Compose and fronted by Caddy for TLS and routing. Kubernetes and managed orchestration are excluded.
- Reason: The deliverable must be running and reachable on demo day. One host with one compose file is the topology a three-person team can rebuild under pressure, and it makes the required architecture and database definitions straightforward to hand over.
- Alternatives: Kubernetes adds an orchestration layer with no benefit at one host. Serverless would fragment the DuckDB and Parquet state this architecture depends on.
- Consequences: State lives on a mounted volume; a demo rehearsal must include a cold start. If the organizer supplies a fixed environment under Q-INFRA-01, this decision yields to it and is amended rather than defended.
- Revisit trigger: The organizer's answer to Q-INFRA-01.

### DEC-127 — Benchmark-gated retrieval

- Status: SUPERSEDED by [DEC-130](#dec-130--initial-hybrid-retrieval-baseline) on 2026-09-09 following a new explicit team decision from Çağatay. The original policy below is historical; it previously superseded DEC-115. Dense retrieval is no longer optional or gated on prior lexical results.
- Decision: **Turkish normalization + reviewed alias/concept mapping + metadata filtering + lexical/BM25 retrieval** is the mandatory baseline. Use one normalizer at index and query time. Preserve original titles and explicit unknown semantics; an alias or score never authorizes an invalid comparison.
- Measurement: Benchmark that baseline on a teammate-reviewed held-out set before enabling more stages. Record Recall@5, Recall@10, final series-selection quality and latency, with catalog/config versions and failure categories. Select a meaningful-gain criterion before inspecting the holdout; no threshold or current score is invented here. See [evaluation tracks](EVALUATION.md#retrieval-and-product-evaluation-tracks).
- Optional activation: Embedding/LanceDB retrieval is **BENCHMARK FIRST**, enabled only for a meaningful measured improvement. RRF/fusion is **BENCHMARK FIRST**, enabled only if lexical and dense paths provide complementary candidates and fusion improves held-out quality. Listwise/model reranking is **BENCHMARK FIRST**, enabled only if final-selection gain justifies latency, extra model calls, failure surface and weak-model instability. Each stage reports gain and cost separately; failed or unavailable optional stages must leave a usable baseline.
- Two retrieval problems: Direct series retrieval resolves a named concept to the correct catalog series. **Catalog-bounded relationship discovery** starts from a target, applies a reviewed concept-family policy, searches metadata inside those families, diversifies/deduplicates, applies financial semantic filters, and returns a bounded candidate set. Direct-series Recall@K alone cannot validate family coverage or the ability to return no useful candidate. Family policy names neighborhoods worth investigating, not an economic causality table.
- Reason: “Buy complexity only with measured quality.” A large catalog establishes the need for retrieval, not the need for every retrieval stage.
- Alternatives: The always-on dense + lexical + RRF + reranker pipeline in DEC-115 is superseded. No existing code or dependency is deleted by this decision; it controls necessity and activation.
- Consequences: M13 owns baseline/optional stages; M9 owns independent oracles and holdout protocol. Q-K-05 now covers optional embedding dimension/prefix/limit questions and dedicated reranker availability; DEC-129 confirms embedding availability without changing this benchmark gate. The baseline and synthetic benchmark design can proceed without model access. DuckDB/Pandas, custom orchestration and the Kloudeks-only runtime constraint remain unchanged.
- Revisit trigger: A versioned benchmark demonstrates an additional stage's benefit and affordable cost, or a catalog change invalidates earlier measurements.

### DEC-128 — Financial question validation and claim-level evidence

- Status: CONFIRMED **product direction and scope**, explicitly authorized by Çağatay on 2026-09-09. Exact schemas, thresholds, family membership, windows/lags and UI interaction details remain PROPOSED until reviewed in their implementation tasks. No new organizer permission is asserted.
- Decision: Reuse the existing planner/executor/workspace/lineage/verifier spine for the behaviors below; do not create separate agents/modules for each behavior.
  - **Premise validation:** Before explanatory analysis, check the stated trend in the requested period where data permits, including nominal/real and stock/flow meaning. Correct or refine a false premise; ask when its semantics are unknown.
  - **Catalog-bounded relationship discovery:** Investigate a small, diverse set from real, permitted BDDK/EVDS catalog metadata and reviewed concept families. Apply semantic checks before deterministic analysis. Return RELATIONSHIP SUPPORTED, WEAK, UNSTABLE, INSUFFICIENT or INVALID COMPARISON; do not force a winner or claim economic causes.
  - **Finance semantic guard:** Check stock/flow, rate/amount, cumulative/reset meaning, frequency/aggregation, unit/scale, percentage representation, index base, coverage/missing periods and archived/stale status. Outcomes are ALLOW, NEEDS_TRANSFORM, NEEDS_INPUT or REJECT. A model cannot override them.
  - **Relationship stability:** Use a bounded set of periods/windows to expose whether an observed relationship remains similar, weakens, reverses or becomes insufficient. Reuse analytics/change-detection boundaries; no research-grade regime-detection claim.
  - **Claim-level proof:** Important values must eventually resolve through `Claim -> VerificationResult -> AnalysisRun -> ResultSnapshot -> InputSnapshots -> TransformationSpec -> Source`. Require sufficient immutable result/input identity, run identity, stale-result rejection, second-path recomputation and a verification gate. A graph or “Why?” panel alone does not satisfy this.
  - **Evidence summary:** Numeric claims use VERIFIED / NOT VERIFIED; relationships use EXPLORATORY / STABILITY-SUPPORTED / INSUFFICIENT; causal evidence is NOT ESTABLISHED unless future evidence justifies otherwise. Optional dimensions (data quality, series match, semantic validity, statistical support, external evidence, causal evidence) use UNKNOWN / N/A when missing. Do not average them into a synthetic probability or claim calibrated “87% confidence.”
- Optional: A small deterministic robustness set may compare another valid window/lag or missing-period sensitivity. No recursive model self-critique, debate agent or uncontrolled challenge loop.
- DEFER / CUT IF BEHIND: Leading Indicator Miner, research-grade automatic regime segmentation, causal event attribution, graph-heavy proof UI, recursive challenge/debate and mandatory dense+RRF+rerank retrieval. Official-source web context may support context, never causal proof by itself.
- Priority: These differentiators must not delay the first real end-to-end slice: permitted source ingestion, the existing lakehouse tool, deterministic result contracts, workspace integration, verifier, live Kloudeks and required brief tools come first. Retrieval baseline/benchmark design may unblock that slice; broad relationship exploration and presentation wait for their prerequisites.
- Consequences: [ARCHITECTURE](ARCHITECTURE.md#product-behaviors-and-proof-target) owns integration boundaries; [EVALUATION](EVALUATION.md#retrieval-and-product-evaluation-tracks) owns separate behavioral tracks; ROADMAP sequences existing milestones and does not automatically promote this direction to READY.
- Revisit trigger: Measured core-slice failure, a reviewed benchmark or an explicit team/organizer scope change. No implementation is delivered by this ADR.
- Retrieval clarification (2026-09-09, DEC-130): Dense semantic retrieval is now initial baseline. The historical deferred dense+RRF+rerank bundle above does not defer dense retrieval itself; RRF/reranking and extra stages remain evidence-driven.

### DEC-129 — Official Kloudeks endpoints, models and compatible client policy

- Status: CONFIRMED — official organizer integration information relayed by Çağatay on 2026-09-09 for the PR #34 follow-up, then **verified against the organizer's primary document** `MIA · Hackathon Rehberi` supplied over Slack on 2026-09-10. The relayed facts below match the primary guide; the 2026-09-10 amendment adds the literal request contracts the earlier relay lacked. This records supplied guidance, not a live connectivity/capability test.
- Credential state (2026-09-10): the team's MIA API key was delivered over Slack and now exists **only in the operator-local, git-ignored `.env`**. No key value is recorded in this repository, and no live request has been made or authorized by a documentation task. See [SEC-KEY-01](SECURITY.md#sec-key-01--secrets-and-credential-storage).
- Live verification (2026-09-11 11:35 +0300, M4-12, explicitly authorized by Eray): one structured chat request and one embedding request through the M4-07 transport with the provisioned key both succeeded. `kkbhackathon2026/Qwen3.8-27B` accepted the key and returned JSON that passed strict local validation on the first attempt (`finish_reason: stop`, 529 ms); `kkbhackathon2026/Qwen3-Embedding-8B` returned one **4096-dimensional** vector (142 ms). One call each is evidence of access and shape, not of limits or quality. The OCR model was not called.
- Observed platform behaviour (2026-09-11 11:59 +0300, M4-15): the served chat model answers **`400` to a request carrying two system messages** and accepts the same content as one; two synthetic diagnostic calls isolated this after the first live end-to-end question failed on it. The product keeps its instructions and tool list as separate system turns, so the M4-07 transport joins leading system turns into one before sending. A later system turn after the conversation starts was not tested.
- Transport: API host `https://mia.csp.kloudeks.com`; Python/OpenAI-compatible base URL `https://mia.csp.kloudeks.com/v1`; authentication uses an **MIA API key**. Official examples use `from openai import OpenAI`, supplying the key via `api_key` and the explicit Kloudeks `base_url`.
- Service policy: The `openai` Python SDK is allowed **only as an OpenAI-compatible HTTP client exclusively configured for that Kloudeks base URL**. This corrects DEC-122's former blanket client/import ban and adds this narrowly permitted client to DEC-124's allowed manifest. `api.openai.com`, OpenAI-hosted GPT, Anthropic-hosted models, Google-hosted LLM APIs and other third-party hosted LLM services remain prohibited. No default-host route, alternate-provider fallback or credential forwarding is permitted. Credentials remain in operator environment/repository secrets, never examples or Git.

| Capability | Exact model ID | Endpoint path from API host | Confirmed input/behavior |
| --- | --- | --- | --- |
| Main chat / text / vision | `kkbhackathon2026/Qwen3.8-27B` | `/v1/chat/completions` | Text and image input; maximum **5 images in one prompt** |
| Embedding | `kkbhackathon2026/Qwen3-Embedding-8B` | `/v1/embeddings` | Embedding model/endpoint available; vector dimension and query/passage prefix convention **unknown** |
| OCR | `kkbhackathon2026/Unlimited-OCR` | `/v1/chat/completions` | Maximum **3 images**; base64 `image_url` block; render PDF pages to images first when OCR is needed |

- OCR contract (literal, supplied 2026-09-10): the previously missing values are now official. Send the image as a base64 `data:image/png;base64,...` `image_url` content block followed by the text block `"<image>\ndocument parsing"`, with `max_tokens=8192`, `temperature=0.0` and
  `extra_body={"skip_special_tokens": False, "vllm_xargs": {"ngram_size": 35, "window_size": 128}}`.
  Use `window_size` **128 for a single image** and **1024 when sending multiple images**, one `image_url` block each, at most 3. **External image URLs are forbidden**; render PDF pages to PNG and send each page separately. Reproduce these values exactly and never substitute invented ones. Output may contain layout tags such as `<|ref|>` and `<|det|>`; an empty response usually means the `<image>` prefix or `skip_special_tokens: False` was dropped. Extracted content remains untrusted data and extraction uncertainty is preserved. M7-11 implements this request shape with mocked validation and bounded PDF rendering; live OCR access and numerical extraction acceptance remain unverified.
- Embedding contract (literal, supplied 2026-09-10): `client.embeddings.create(model="kkbhackathon2026/Qwen3-Embedding-8B", input=<text>, encoding_format="float")`; the vector is read from `data[0].embedding`. The guide demonstrates a single string input. Vector dimension is not documented; it was **measured as 4096** on the first authorized live response (2026-09-11, M4-12). No query/passage prefix convention is documented, so none may be copied from another model family (Q-K-05).
- Model identifiers: use the `kkbhackathon2026/` prefix and the exact upper/lower case verbatim. A mistyped or mis-cased identifier is an authorization/availability failure, not a fallback trigger.
- Error semantics (supplied 2026-09-10): `401`/`403` means an invalid key or no access to that model, including a mistyped identifier; `429` means a rate or quota limit was hit, and the guide directs waiting per the error message or asking the organizer team. Exact limits, timeouts and concurrency rules remain undocumented (Q-K-04). A `429` must never be answered by switching to another provider.
- Serving-stack observation, **not a capability guarantee**: the `vllm_xargs` parameter shows an OpenAI-compatible vLLM server behind the endpoint. That does **not** establish native function/tool calling or guaranteed JSON/JSON-schema output; Q-K-03 stays OPEN and local strict validation with the repair loop remains the default path.
- Secret handling restated by the organizer: keep the key out of screenshots, slides, chats and browser-side code; never commit files containing a real key, including to a private repository; keep it in an environment variable and add `.env` to `.gitignore`. This matches the existing SEC-KEY-01 control and adds no exception.
- Still unknown after the 2026-09-10 amendment: Native function/tool calling; guaranteed structured JSON/JSON-schema; context window; general maximum output tokens beyond the OCR example's `8192`; exact request/rate/concurrency limits behind the documented `429`; provider timeout behavior; the embedding query/passage prefix convention; dedicated reranker availability; demo internet/egress. No dedicated reranker in this supplied model list does **not** prove none can be provided later. Live authentication was exercised for the chat and embedding models on 2026-09-11 (above); OCR access is still unverified.
- Capability wording: The main chat/LLM model supports the supplied chat/text and image-input behavior; no separate reasoning API, mode or guarantee is inferred. Its model ID is unchanged.
- Retrieval consequence (amended 2026-09-09): The subsequent explicit team decision DEC-130 makes the confirmed embedding model part of the initial hybrid baseline. DEC-127 is superseded; RRF/reranking and extra retrieval infrastructure still require measured benefit. Embedding dimension/prefix and remaining limits are still unknown.
- Implementation consequence: No SDK dependency or live client is delivered by this docs change. M4 must separately correct the package-wide `openai` string ban in [test_llm_provider.py](../tests/unit/test_llm_provider.py) and stale provider-policy comments, then validate exclusive Kloudeks routing, no hosted fallback and secret redaction. [ROADMAP M4](ROADMAP.md#m4) records the exact remaining policy conflict; do not weaken the hosted-service ban to make a test pass.
- Revisit trigger: Further official capability/limit guidance or a separately authorized, sanitized live test. Keep unanswered details in OPEN_QUESTIONS. The former "obtain the literal OCR guidance first" blocker is **cleared**; OCR implementation is now gated only by bounded rendering/parsing work and input-scope decisions, not by missing organizer values.

### DEC-130 — Initial hybrid retrieval baseline

- Status: CONFIRMED — new explicit team decision supplied by Çağatay on 2026-09-09 for PR #34; supersedes DEC-127. DEC-115 remains historical/SUPERSEDED and its mandatory RRF/reranking pipeline is not reinstated.
- Decision: The initial default **HYBRID baseline** is **Turkish normalization + reviewed alias/concept-family mapping + metadata filtering + lexical/BM25 retrieval + Qwen3-Embedding-8B dense semantic retrieval**. Use the organizer-provided `kkbhackathon2026/Qwen3-Embedding-8B` through `https://mia.csp.kloudeks.com/v1/embeddings` under DEC-129. Dense retrieval is baseline from the start; its use is not conditional on lexical failure or prior measured gain.
- Vector index: Retain **LanceDB** as the lightweight series-vector index selected in DEC-115/124; there is no new reason to reopen that storage choice. This does not make RRF, reranking, a second document collection or additional vector infrastructure mandatory. No package, index or transport is implemented by this documentation change.
- Benchmark: Compare lexical-only, dense-only and combined candidate quality on the same reviewed development/held-out catalog cases. Report Recall@5, Recall@10, final series selection, latency and failure behavior, with model/index/config versions and declared candidate budgets/combination policy. The experiment measures the hybrid baseline and guides tuning; it does not decide whether embeddings belong in it.
- Benchmark-gated stages: Enable **RRF** only when lexical/dense results are demonstrably complementary and fusion improves the held-out benchmark. Enable **listwise/model reranking** only for meaningful final-selection improvement worth another model call, latency, token usage, weak-model instability and added failure surface. Additional retrieval stages/vector infrastructure also need a concrete measured benefit. No fixed fusion formula, reranker model or score threshold is chosen here.
- Two evaluation paths: **Direct series retrieval** uses lexical+dense candidates to resolve a named concept. **Catalog-bounded relationship discovery** expands a target into reviewed financial concept families, performs hybrid retrieval within those families, diversifies/deduplicates, applies finance-semantic filters and produces a bounded candidate pool. Embedding only the target phrase and returning near-duplicate target variants does not satisfy discovery. Family policies define neighborhoods to investigate, not economic causes.
- Failure behavior: Measure each path's failures and the combined result. A labeled lexical-only or dense-only degraded response may preserve useful candidates, but it is not a successful full-hybrid run. Preserve ambiguity/unknown semantics and never fill missing candidates with invented matches. Optional-stage failure must not silently change the baseline or claim a complete run.
- Dependencies: M13 catalog/normalizer/aliases and M4 bounded Kloudeks transport remain implementation work. Q-K-05 dimension/prefix/limit details must be established for the vector index; model availability is already confirmed. Those prerequisites do not make dense retrieval optional or automatically mark M13-05 READY. Core-first priorities and ownership remain unchanged.
- Reason: The team has explicitly chosen to use the organizer's embedding capability in the first retrieval baseline while requiring evidence for fusion/reranking complexity.
- Revisit trigger: A reviewed failure/quality/cost measurement or explicit team/organizer change. Record changes as decisions; do not silently switch back to DEC-127.

### DEC-131 — Organizer kick-off brief: schedule, delivery form and demo-day input scope

- Status: CONFIRMED — organizer constraints read from the primary kick-off deck `KKB Hackathon 2026 Kick Off Sunum_07092026_FİNAL` (7 September 2026), reviewed on 2026-09-10. Several of these facts had shaped earlier work second-hand (the six tools, the three BDDK datasets, the reference scenario, the database deliverable) but the schedule, delivery form and demo-day input scope were never recorded. This entry records organizer requirements; it is not a team preference and cannot be traded away internally.
- Confirmed calendar: kick-off and brief **7 September 2026**; online development over Slack with mentoring **7–20 September 2026**; project review and announcement of the **top 10 teams on 5 October 2026**; **Final Day 17 October 2026** with jury presentations and awards.
- Consequence for planning: the **hard development deadline is 20 September 2026**, not the informal "8–9 day" window the earlier plan assumed, and the demo happens ~4 weeks later for teams that advance. [ROADMAP](ROADMAP.md#relative-execution-plan-anchored-to-the-confirmed-calendar) anchors the relative day plan to these dates. A longer window is not permission to widen scope; core-first sequencing under [DEC-128](#dec-128--financial-question-validation-and-claim-level-evidence) is unchanged.
- Two distinct gates: what is reviewed on 20 September is the **repository state**, while the 17 October Final Day is the **live demo**. Work that only matters for the demo must not displace the reviewed slice before 20 September.
- Delivery form: teams develop in their own environment, keep the code in a **private GitHub repository**, and deliver by **granting KKB access to that repository**. Architecture drawings, documents, the code repository and database definitions are all named deliverables. This confirms the existing repository/documentation posture and [SEC-REPO-01](SECURITY.md#sec-repo-01--githubprivate-repository-and-development-artifacts); a private repository is still not a secret store.
- Demo-day expectation: a **solution already deployed and running live** is expected, and teams must produce output from **inputs handed to them on the day** by running the real scenario. Prepared screenshots or a local-only run do not satisfy this. This is the organizer requirement behind [DEC-126](#dec-126--single-vm-deployment-with-docker-compose); exact hosting/OS/port constraints are still unspecified (Q-INFRA-01).
- Demo-day input scope: besides the lakehouse data, **URLs will be supplied inside the prompt** and meaning must be extracted from PDF, Excel, image and text content at those addresses. The brief names two example pages on `borsaistanbul.com` — the precious-metals market data page, whose gold-transactions PDF may be read for values, and the `xtumy` index page, from which BIST 100 daily or monthly change may be requested. These are illustrative examples of the required capability, **not an approved allowlist** and not a commitment that those exact URLs appear (Q-NET-02).
- Technology expectations: **Python is the main development language** and no second backend language should be introduced without a specific need; the frontend framework is free. **Open-weights** language models are expected (the brief names Qwen, Mistral, gpt-oss, Kimi) alongside **open-source libraries** — `pypdf`, Pandas, DuckDB, Plotly and LanceDB are named explicitly. This independently corroborates [DEC-112](#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse), [DEC-124](#dec-124--dependency-manifest-and-excluded-technologies) and the LanceDB index retained by [DEC-130](#dec-130--initial-hybrid-retrieval-baseline); it adds no new dependency and authorizes none.
- Third-party LLM prohibition restated verbatim by the organizer: external third-party LLM API services may not be used, and only open-source language models reachable through the Kloudeks platform are permitted. This confirms the hard constraint in [DEC-002](#dec-002--delivered-llm-access-through-kloudeks) and [DEC-129](#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) at the primary-source level. **Scope resolved 2026-09-10 (Q-DEV-01):** that sentence governs the models the delivered product calls, not the tools used to write it — coding assistants are permitted for development. The runtime restriction is unchanged and remains hard: no assistant, and no model an assistant runs on, may appear in a runtime path, a dependency or a delivered request.
- Data scope: the brief bounds both sources to **January 2021 – June 2026** and names the BDDK sections `Haftalık Bülten`, `Aylık Bülten` and `FinTürk - İllere Göre`, plus EVDS `tumSeriler`. Access permission itself is still unconfirmed (Q-DATA-01); a named dataset is not granted access.
- Reason: These constraints determine the deadline, the delivery mechanism and the required `web_url` capability surface. Leaving them unrecorded made the roadmap plan against an invented schedule and treat URL-document extraction as optional.
- Revisit trigger: An organizer schedule change, a published allowlist, or Slack answers to Q-INFRA-01, Q-NET-02, Q-DEMO-01/03 or Q-DEV-01.

### DEC-132 — Literal document quotation versus analytical meaning

- Status: CONFIRMED — explicit Çağatay product authorization, 2026-09-12.
- Decision: **Unknown semantics block interpretation and transformation, not exact source quotation.** Execution may mark an exact document-cell result `LITERAL_SOURCE_VALUE`; the default remains `ANALYTICAL_VALUE`. A model cannot request this privilege. It is usable only after the selected value, cell coordinates, result identity and source/transform lineage snapshot resolve in the same store, without analytical transformations.
- Reason: A correctly parsed source number with no declared unit can still be quoted as source text; it cannot be interpreted as currency, percent, an index, or a transformed/comparable amount.
- Consequences: DEC-104/119 analytical guards remain. Unknown literal values use one bounded Turkish source-quotation template, explicitly saying unit or scale is unspecified; extra interpretation is refused. No generic prose semantic understanding is claimed. Known-unit analytical presentation remains unchanged. M7-19 requires a supported retained claim bound to the exact document result, including an eligible literal claim; accepted prose alone is insufficient. Persist only the selected reading/cell proof metadata, never the whole downloaded document. Old cell nodes without a reading snapshot are ineligible until the document is selected again.
- Alternatives: Guessing a unit, weakening all unresolved-semantic checks, trusting a model's literal label, or treating a source URL alone as proof are rejected.
- Revisit trigger: A separately specified need for multiple literal values, alternate verified quotation templates or metadata outside the selected header. No new framework or live call is authorized by this decision.

### DEC-133 — Eleven-tool product target and mandatory harness

- Status: CONFIRMED — explicit Çağatay authorization, 2026-09-12.
- Decision: Retain the six first-class organizer tools (`lakehouse`, `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`) and approve five product tools in sequential delivery order: `catalog_search`, `series_inspect`, `table_transform`, `data_quality`, `reconcile_sources`. This amends DEC-121's name ceiling, not its execution controls. [ARCHITECTURE](ARCHITECTURE.md#approved-tool-surface) tracks actual implementation status; currently only five base tools have callable implementations.
- Responsibilities: `catalog_search` returns bounded ranked trusted CatalogRecord candidates, preserving ambiguity and unknowns; `series_inspect` exposes one trusted series' declared metadata and usable-operation limits; `table_transform` changes a trusted table deterministically while preserving other columns, state and lineage; `data_quality` reports deterministic data diagnostics, never model confidence; `reconcile_sources` compares trusted paths with semantic prerequisites and explicit CONSISTENT / DIFFERENT / NOT_COMPARABLE / NEEDS_TRANSFORM / NEEDS_INPUT outcomes.
- Boundaries: Semantic guards, verifier, security guards and lineage recording remain mandatory harness behavior, never planner-optional tools. `proof` remains API/UI over lineage; `document_search` is outside this target. Every delivered tool requires closed typed arguments and typed results, bounded execution, trusted reference validation and the existing semantic/verifier/gate checks. Planned names must not be exposed in planner schemas or executable registry entries before implementation and tests. Current ToolResult.output is not centrally schema-enforced; this decision does not claim that M5 validation gap is closed.
- Retrieval: Reuse M13 rather than build a second subsystem. DEC-130's initial hybrid baseline remains normalization, reviewed aliases/concept families, metadata filtering, lexical/BM25 and Qwen dense retrieval with LanceDB. M13-04 may deliver an explicitly lexical-only offline stage after its own prerequisites; it is not complete hybrid retrieval. RRF/reranking remain benchmark-gated. No invented catalog codes/metadata, silent archived inclusion, inferred financial meaning or live access is authorized here.
- Evidence and sequencing: [ROADMAP](ROADMAP.md#product-tool-delivery-order) maps the five tools to owning tasks. M13-01/03 are merged; reviewed aliases/catalog mappings, lexical and dense retrieval are absent. M13-04 remains blocked on M13-08 and usable reviewed catalog input. Approving tools neither supplies those records nor completes a prerequisite. Subsequent tools wait for their own dependencies and sequential triage.
- Alternatives: Exposing all eleven names immediately, letting the planner skip guards, duplicating retrieval or hard-coding demo series is rejected. No new engine, framework, provider or dependency is selected.
- Revisit trigger: Measured product need or organizer guidance changing tool responsibilities; broader infrastructure remains separately justified.

## Proposed decisions

Candidates below are not approved selections. Compare options in a bounded task; do not silently promote a proposal to CONFIRMED.

| ID | Proposal | Alternatives / evidence needed | Owner | Next action |
| --- | --- | --- | --- | --- |
| PROP-01 | RESOLVED by DEC-113 | Custom bounded loop selected; LangGraph and other frameworks rejected | Eray | None; implement in M5 |
| PROP-02 | RESOLVED by DEC-112 | DuckDB with Parquet and Pandas selected; Polars rejected | Eray | None; implement in M12 |
| PROP-03 | RESOLVED by DEC-123 | FastAPI with SSE behind Next.js selected; Streamlit retained as a recorded fallback | Eray | None; implement in M10 |
| PROP-04 | PROPOSED: retry and latency budgets | Exact counts/timeouts depend on platform limits and baseline measurements | Unassigned | Obtain Q-K-04 and measure before fixing limits |
| PROP-05 | RESOLVED by DEC-120 | Lagged correlation and Granger with mandatory stated limits; stronger identification rejected for this data | Eray | None; implement in M6 |
| PROP-06 | PROPOSED: web_search provider/API | No provider selected; explicit team choice and primary API contract required by M7-21 | Çağatay | [Complete provider decision](#web-search-provider-decision-m7-21); M7-22 stays BLOCKED |

### Web search provider decision (M7-21)

Status: OPEN / PROPOSED, not a confirmed provider selection. M7-21 owns this decision; [PR #113](https://github.com/cagatayeroglu/KKB-DataTrio/pull/113) publishes Çağatay's documentation-only claim. DEC-121/133 approve the `web_search` name, not a third-party service. DEC-129's Kloudeks chat/vision/embedding/OCR capabilities do not establish a search endpoint. No new confirmed DEC ID is allocated while the choice is unresolved.

Before approval, record the provider/service and official API documentation, endpoint/method, auth placement and secret configuration, request/response/error fields, supported filters, provider limits versus repository caps, billing/quota/access requirements and query retention/privacy implications. All these provider-specific values are **UNRESOLVED**; no credential was inspected and neither credential presence nor absence is asserted. Do not invent environment variable names, API paths, fields, quotas or guarantees.

Provider choice must be explicitly agreed, with dated team approval and primary-source contract evidence before M7-22 can start. Search-only metadata access must not introduce third-party hosted LLM generation contrary to AGENTS; no fallback provider or implicit answer-generation service. Q-NET-01/02 still govern live availability/exposure; a provider contract is not permission for unrestricted destination fetches. No live search is authorized by this task.

Implementation planning is in [ARCHITECTURE](ARCHITECTURE.md#web-search-implementation-plan-m7-2122). Merge of incomplete triage cannot be represented as a selected provider or completed decision. After the actual decision is approved, use the next available confirmed DEC ID, retain this proposal's history, and complete M7-21 through normal validated merge/bookkeeping. Do not start M7-22 in the decision session.

## Deferred decisions

| Topic | Status | Why deferred | Revisit trigger |
| --- | --- | --- | --- |
| Router fine-tuning | DEFERRED; no training approach selected | No measured routing baseline or confirmed resources | Persistent routing errors after simpler fixes, plus time/compute |
| RRF / reranking / extra retrieval infrastructure | PROPOSED / BENCHMARK-GATED under DEC-130; dense retrieval is CONFIRMED baseline | Additional stages must earn activation through held-out gain and measured cost | Complementarity/final-selection evidence; dedicated-reranker capability if used |
| Multi-agent topology | DEFERRED; none selected | Added coordination cost is not justified | A bounded independent role measurably improves results |
| Workspace persistence backend | RESOLVED by DEC-117; artifact DAG persisted in DuckDB | Superseded: DEC-112 already places DuckDB in the stack, so no separate engine is needed | Cross-process durability and reset semantics still need Q-INFRA-02 and Q-DEMO-02 |
| GPU/training deployment | DEFERRED | Resource availability/need unknown | Q-COMP-01 answered and workload requires it |
| Enterprise security infrastructure | DEFERRED | Outside the 7–20 September development window (DEC-131) | Concrete production/organizer requirement |

DEC-129 records confirmed Kloudeks transport, authentication, models, image-count limits and — since the 2026-09-10 primary-guide amendment — the literal OCR and embedding request contracts and documented error semantics. The MIA key authenticated for chat and embedding in the 2026-09-11 live smoke (M4-12), and the embedding dimension is measured as 4096. Still unresolved: OCR access, native function/tool calling, guaranteed JSON/JSON-schema output, context/output capacity, exact rate/concurrency/timeout limits behind the documented `429`, the embedding prefix convention and dedicated reranker availability (narrowed Q-K-01..05). DEC-131 records the organizer calendar, delivery form and demo-day input scope; hosting constraints (Q-INFRA-01) and URL permission policy (Q-NET-02) remain open, while coding-assistant policy (Q-DEV-01) is answered for development use without touching the runtime ban. Neither compatibility nor example parameters answer these questions.

Orchestration, analytical engine, frontend framework, causality method and workspace persistence are **no longer open** — see DEC-112, DEC-113, DEC-117, DEC-120 and DEC-123. Router fine-tuning and multi-agent topology remain deferred.

## Maintenance

Add an ADR when a constraint or choice actually changes. Use the fields above and link the answer, experiment, or PR. Keep rejected alternatives brief. Update OPEN_QUESTIONS for unresolved issues and ROADMAP for implementation progress.
