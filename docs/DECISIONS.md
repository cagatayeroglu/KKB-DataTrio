# Decision log

Decision entries and dated amendments preserve their original rationale and implementation snapshots. They do not independently track current delivery; consult [ROADMAP](ROADMAP.md#current-project-status) and [ARCHITECTURE](ARCHITECTURE.md).

This file owns constraints and reasons for choices. [ROADMAP](ROADMAP.md) owns implementation status; the [Open Questions section](#open-questions) owns unanswered questions. CONFIRMED does **not** mean implemented.

Evidence policy: original organizer constraints are **team-reported** unless a later entry identifies primary evidence (for example DEC-129/131). [DEC-141](#dec-141-organizer-verbal-criteria) records the new verbal criteria as relayed by Çağatay, not independently verified transcript evidence. Add the actual response/reference when received; do not invent an approval, quotation, or date. Record authorized changes here before changing a hard constraint.

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

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-02](DECISIONS.md#history-q-team-02--analyticalparsing-engine).
- Date: 2026-09-09.
- Decision: DuckDB over Parquet files is the storage and query engine, organized as a medallion lakehouse: `bronze` holds the retrieved artifact plus its hash and retrieval time, `silver` holds normalized series with explicit semantics, `gold` holds analysis-ready facts. Pandas is the in-process transformation and table-shaping library. Polars is not adopted.
- Reason: The organizer brief names DuckDB and Pandas; both run in-process with no server to deploy or fail during the demo. Parquet plus DuckDB gives typed columnar storage, SQL for the `lakehouse` tool, and a file layout that is directly deliverable as the required database definition.
- Alternatives: Polars is faster on large frames but adds a third dataframe dialect for a corpus measured in tens of thousands of rows. A hosted warehouse is excluded by DEC-003 and by the single-VM deployment in DEC-126. SQLite lacks the analytical functions the tools need.
- Consequences: Unblocks M1-03, M1-06 and the M2/M6 engine-dependent work. Every material calculation stays deterministic under DEC-101; DuckDB executes only validated SQL under DEC-121. Adds `duckdb`, `pandas` and `pyarrow` to the runtime manifest in DEC-124.
- Revisit trigger: A measured DuckDB limitation on the actual corpus that Pandas cannot cover.

### DEC-113 — Custom bounded orchestration loop

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-01](DECISIONS.md#history-q-team-01--orchestration-mechanism).
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

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-05](DECISIONS.md#history-q-team-05--workspace-persistence-and-reference-storage).
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

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-04](DECISIONS.md#history-q-team-04--causality-implementation-and-prerequisites).
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
- Amendment (2026-09-12): [DEC-133](#dec-133--eleven-tool-product-target-and-mandatory-harness) uses the addition clause to approve five product tools. The original six-name ceiling and the historical “addition clause unused” observation above are superseded; schemas and restricted SQL controls remain in force. Approval is a target, not evidence of runtime registration. DEC-135 subsequently supersedes the planner-callable portion of DEC-133; this amendment remains historical.
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

- Status: CONFIRMED — team decision on 2026-09-09; answers [Q-TEAM-03](DECISIONS.md#history-q-team-03--frontend-framework).
- Date: 2026-09-09.
- Decision: Serve the application from FastAPI, streaming plan and tool progress to the client over server-sent events. Build the user interface in Next.js with Tailwind and shadcn/ui, TanStack Table for the analysis table, `react-plotly.js` for charts, and React Flow for the evidence panel that renders a claim's lineage subgraph.
- Reason: The deliverable is a deployed working system that a jury operates, and the trust layer is only visible if provenance is rendered. Streaming the tool steps makes a multi-step analysis legible while it runs instead of after it finishes. The team has front-end capacity, so the stronger presentation is worth its cost.
- Alternatives: Streamlit needs less work and remains the fallback if front-end capacity disappears, but it renders a lineage graph poorly. A static rendered report would not support the multi-turn scenario.
- Consequences: The web client lives in `web/` at the repository root, outside the Python package (DEC-125). M10 owns it. The API contract must be stable before the front end is built against it; the front end is not a prerequisite for backend acceptance and must not gate M5–M8.
- Revisit trigger: Front-end work measurably delaying backend acceptance, in which case the Streamlit fallback is taken deliberately and recorded.
- Implementation note (2026-09-15, M10-07, Eray): charts use `react-plotly.js` 4.1.0 through its factory, bound to `plotly.js-dist-min` 4.1.1 installed under the `plotly.js` name to satisfy the peer dependency without the source build; the plot chunk (about 4.6 MB) loads client-only when a result has a period table. No other chart library is added.
- Clarification (2026-09-09): DEC-128 defers graph-heavy proof UI. A concise claim/evidence view can serve the first UI; React Flow layout is not a prerequisite for the core slice. Framework choice remains confirmed.

### DEC-124 — Dependency manifest and excluded technologies

> Refinement (2026-09-14): [DEC-137](#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this decision-time record. Hybrid lexical+dense retrieval remains required; DEC-137 supersedes the earlier mandatory LanceDB product selection. Named library examples/allowlists do not establish a currently selected or implemented vector backend.

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

- Status: CONFIRMED as our target — team decision on 2026-09-09; the environment itself remains blocked on [Q-INFRA-01](DECISIONS.md#open_questions-q-infra-01--runtimedeployment-environment).
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

> Refinement (2026-09-14): [DEC-137](#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this decision-time record. Hybrid lexical+dense retrieval remains required; DEC-137 supersedes the earlier mandatory LanceDB product selection. Named library examples/allowlists do not establish a currently selected or implemented vector backend.

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

> Refinement (2026-09-14): [DEC-137](#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this decision-time record. Hybrid lexical+dense retrieval remains required; DEC-137 supersedes the earlier mandatory LanceDB product selection. Named library examples/allowlists do not establish a currently selected or implemented vector backend.

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

> Refinement (2026-09-14): [DEC-137](#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this decision-time record. Hybrid lexical+dense retrieval remains required; DEC-137 supersedes the earlier mandatory LanceDB product selection. Named library examples/allowlists do not establish a currently selected or implemented vector backend.

> Historical decision-time record. Its planner-callable target/roles are **SUPERSEDED IN PART by [DEC-135](#dec-135--planner-actions-and-mandatory-correctness-harness)**. The original text and implementation snapshot below are retained; current delivery is in ROADMAP. Retrieval and execution-control requirements remain in force.

- Status: CONFIRMED — explicit Çağatay authorization, 2026-09-12.
- Decision: Retain the six first-class organizer tools (`lakehouse`, `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`) and approve five product tools in sequential delivery order: `catalog_search`, `series_inspect`, `table_transform`, `data_quality`, `reconcile_sources`. This amends DEC-121's name ceiling, not its execution controls. [ARCHITECTURE](ARCHITECTURE.md#approved-tool-surface) tracks actual implementation status; currently only five base tools have callable implementations.
- Responsibilities: `catalog_search` returns bounded ranked trusted CatalogRecord candidates, preserving ambiguity and unknowns; `series_inspect` exposes one trusted series' declared metadata and usable-operation limits; `table_transform` changes a trusted table deterministically while preserving other columns, state and lineage; `data_quality` reports deterministic data diagnostics, never model confidence; `reconcile_sources` compares trusted paths with semantic prerequisites and explicit CONSISTENT / DIFFERENT / NOT_COMPARABLE / NEEDS_TRANSFORM / NEEDS_INPUT outcomes.
- Boundaries: Semantic guards, verifier, security guards and lineage recording remain mandatory harness behavior, never planner-optional tools. `proof` remains API/UI over lineage; `document_search` is outside this target. Every delivered tool requires closed typed arguments and typed results, bounded execution, trusted reference validation and the existing semantic/verifier/gate checks. Planned names must not be exposed in planner schemas or executable registry entries before implementation and tests. Current ToolResult.output is not centrally schema-enforced; this decision does not claim that M5 validation gap is closed.
- Retrieval: Reuse M13 rather than build a second subsystem. DEC-130's initial hybrid baseline remains normalization, reviewed aliases/concept families, metadata filtering, lexical/BM25 and Qwen dense retrieval with LanceDB. M13-04 may deliver an explicitly lexical-only offline stage after its own prerequisites; it is not complete hybrid retrieval. RRF/reranking remain benchmark-gated. No invented catalog codes/metadata, silent archived inclusion, inferred financial meaning or live access is authorized here.
- Evidence and sequencing: [ROADMAP](ROADMAP.md#product-tool-delivery-order) maps the five tools to owning tasks. M13-01/03 are merged; reviewed aliases/catalog mappings, lexical and dense retrieval are absent. M13-04 remains blocked on M13-08 and usable reviewed catalog input. Approving tools neither supplies those records nor completes a prerequisite. Subsequent tools wait for their own dependencies and sequential triage.
- Alternatives: Exposing all eleven names immediately, letting the planner skip guards, duplicating retrieval or hard-coding demo series is rejected. No new engine, framework, provider or dependency is selected.
- Revisit trigger: Measured product need or organizer guidance changing tool responsibilities; broader infrastructure remains separately justified.

### DEC-134 — Provider-neutral web search with mandatory live acceptance

- Status: CONFIRMED — explicit Çağatay decision, 2026-09-12; supersedes PROP-06's requirement to choose a concrete provider before offline implementation.
- Decision: `web_search` depends on a narrow internal `SearchBackend` protocol. Planner -> registered typed ToolSpec -> SearchBackend -> operator-configured backend. Tool request/result schemas remain provider-neutral; replacing a provider must not change planner/tool schemas. Backend credentials/configuration never enter planner-visible data. No concrete commercial or self-hosted search service is selected.
- Offline scope: M7-22 implements the bounded tool, typed contracts, injected backend boundary and deterministic FakeSearchBackend for tests. No API key, billing/account setup or network is required. Fake search is test-only, never silently enabled as production. Missing production configuration must not create a fake-success path. Provider errors are safe fixed outcomes; result text/URLs remain untrusted data, not verified facts or executable instructions.
- Discovery boundary: Search results do not grant `web_url` fetch permission. Its exact original-question URL check and `URL_NOT_IN_QUESTION` behavior remain unchanged. No implicit result following, source fetch, model generation, credential access or security/verifier weakening is authorized.
- Release/demo requirement: **Before final submission/demo acceptance, at least one real production search backend must be configured and a live hidden-like web search smoke must PASS.** Offline implementation complete and live production search accepted are separate claims. Until the later acceptance record passes, live search is NOT RUN / BLOCKED and production capability must not be claimed.
- Later explicit acceptance: Select the production backend; document official endpoint/method/auth/config, limits/errors, privacy/retention, deployment network policy and the real adapter; validate a bounded unseen-query live smoke with sanitized evidence under separate authorization. Q-NET-01/02 remain open. The [M7 production acceptance record](ROADMAP.md#web-search-production-acceptance) remains untriaged; this decision allocates no speculative new task ID or implementation claim.
- Reason: Decouple the stable tool contract and offline trust tests from a replaceable provider without mistaking fake results for final delivery. DEC-121/133 names and mandatory harness rules remain; no new dependency/framework or hosted LLM is approved.
- Revisit trigger: An explicitly selected provider that cannot satisfy the neutral contract or documented product/network constraints; review before adapting, never silently broaden tool permission.

### DEC-135 — Planner actions and mandatory correctness harness

> Current clarification: DEC-136 and DEC-137 below refine the runtime observation path described in DEC-135; the original decision is retained, including its planner/harness responsibilities. DEC-134 remains the search abstraction and live-acceptance policy.

- Status: CONFIRMED — explicit Çağatay authorization, 2026-09-12. Supersedes only the planner-callable target and roles in DEC-133; its historical record, DEC-130 retrieval policy and mandatory execution controls are preserved.
- Rationale: “More planner-callable tools do not inherently make the agent better. User-intent-dependent capabilities remain tools; correctness-critical checks must be deterministic mandatory harness behavior.”
- Planner target: Eight names — `lakehouse`, `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`, `catalog_search`, `table_transform`. Seven callable factories exist after M13-04; `table_transform` remains planned. Sessions expose only explicitly registered implementations. This documentation decision registers/unregisters nothing.
- Mandatory inspection: Selecting a financial series must trigger deterministic `series_inspect` before its observations are used. Inspect trusted source/identity, frequency, unit, scale, archive state, stock/flow/rate semantics, aggregation permissions, coverage and other available catalog semantics; unknowns remain explicit. M13-13 owns this future harness step, not a planner-optional tool. Automatic wiring is not implemented.
- Mandatory quality: Retrieving observations for analysis must trigger bounded deterministic `data_quality` before analysis-ready status: missing periods, coverage/gaps, frequency consistency, trusted stale/archive evidence and known validity constraints. M1-12 owns this future gate; the LLM cannot skip it. Existing diagnostics are not proof of automatic wiring, which remains unimplemented.
- Conditional reconciliation: When multiple trusted sources/results purport to support the same financial measure, M8-09 must provide deterministic/hybrid `reconcile_sources` outside planner discretion. Compare semantic compatibility, period, frequency, unit, scale and values; return CONSISTENT / DIFFERENT / NOT_COMPARABLE / NEEDS_TRANSFORM / NEEDS_INPUT. No invented equivalence or silent conversion. This capability is not implemented or counted as a normal planner tool. A later explicit comparison action may expose it if separately designed, but correctness cannot depend solely on the LLM invoking it.
- Harness boundary: Financial transformations require semantic compatibility guards; numeric final claims require lineage/evidence/verifier binding. Existing semantic guards, verifier/gate, lineage and security controls remain system layers. The new inspection/quality/reconciliation triggers are required target behavior, not a claim that every path is already wired or unfinished output/ownership validation is complete.
- Catalog versus observations: Discovery reads trusted versioned local catalog metadata and reviewed aliases/concept mappings. Runtime observations use approved source adapters/data paths when available; discovery does not fetch observations or let the LLM invent IDs. M13-08's ten-identity demo snapshot is not the final full catalog. Reviewed aliases are precision shortcuts, not the only possible catalog knowledge or a prohibition on unseen concepts. A broader versioned BDDK/EVDS metadata snapshot is intended later, not implemented now.
- Current lexical delivery: M13-04 is DONE for the reviewed offline demo scope: shared Turkish normalization, reviewed aliases/concepts, metadata filtering and bounded pure-Python BM25. Exact/reviewed aliases take precedence; ambiguity remains explicit, top-1 is not truth, and UNRESOLVED never invents an ID. No DuckDB FTS extension was installed, no dependency added and no lakehouse security relaxed. This is the authoritative current lexical/reviewed baseline, not completed DEC-130 hybrid retrieval; mandatory dense retrieval remains separate work.
- Web search unchanged: DEC-134's provider-neutral SearchBackend/offline implementation is DONE; no production provider is selected, and live production acceptance remains NOT RUN / BLOCKED. Organizer clarification of external search API/network policy remains necessary. Untrusted search snippets do not grant web_url fetch authority.
- Task mapping: Preserve M13-13, M1-12 and M8-09 IDs with the harness roles above; M5-20 retains the planned table_transform callable. No task is claimed or promoted to READY/DONE, no full catalog/dense completion is claimed, and no new dependency, runtime behavior or live access is authorized by this docs reconciliation.
- Revisit trigger: Explicit product/organizer evidence requiring a changed user-facing action or harness trigger; any new callable registration still needs implemented, validated contracts.

### DEC-136 — Scoped official-data preparation and lakehouse-first demo runtime

> Refinement (2026-09-14): [DEC-137](#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this decision-time record. Its scoped preparation remains valid; the final target also includes broader coverage and policy-permitted official-source materialization on catalog cache misses.

- Status: CONFIRMED team architecture direction, 2026-09-13, explicitly requested by Çağatay. This does not grant organizer/source/network permissions or claim implementation.
- Decision: Demo-critical official BDDK/EVDS observations are prepared through scoped ingestion into the trusted local/versioned DuckDB + Parquet lakehouse. Runtime financial queries use those observations; general web discovery remains a separate `web_search` capability.
- Preparation: official sources → approved bounded retrieval → thin source-specific ingestion adapters → common trusted Observation representation → bronze/silver/gold. Adapters own endpoint/request shape, selectors, source parsing, frequency/unit/scale and provenance; they reuse common network/security/parser/storage infrastructure. BDDK/EVDS ingestion adapters and the prepared official demo dataset are not delivered.
- Initial scope: approximately **2021-01 through 2026-06**, for **housing credit balance, housing/mortgage credit interest rate, CPI/TÜFE and KFE**. This is scoped ingestion, not the entire BDDK/EVDS universe. Consumer, vehicle and commercial loans, deposits/additional rates and broader catalogs are later coverage expansion.
- Semantic contract: preserve BDDK Monthly/Weekly Bulletin and FinTürk distinctions where relevant, source table/selectors, TP/YP/Total, bank group/geography, unit/scale, period and stock/flow/cumulative meaning. Preserve EVDS real series IDs versus datagroups, native frequency/anchor, active/archived/unknown status, comma-decimal/date parsing, aggregation and base/reference-year meaning, and new-credit flow-rate versus outstanding stock-rate. Unresolved IDs/metadata remain unresolved; catalog ancestry alone does not prove values.
- Runtime: question → planner/`catalog_search` → trusted series/concept → `lakehouse` prepared observations → alignment/transforms/analytics → verifier. Preparation reduces source availability, page/endpoint drift and network-latency dependencies during questions. Optional operational refresh is separate and must retain provenance, version identity, retrieval vintage and explicit refresh/revision policy. It is not a silent runtime fallback.
- Separate web discovery: retain `SearchBackend`; a production backend is not implemented. **SearXNG is the preferred compatibility-evaluation candidate**, not selected, integrated or live accepted. Self-hosting may still forward queries to upstream engines; organizer/network/privacy/retention confirmation remains required. DEC-134's real production-backend live acceptance remains mandatory.
- Separate URL extraction: preserve current `web_url` for a specific supplied/authorized URL and its bounded safe retrieval/supported document parsing. **Crawl4AI is only an optional future compatibility candidate** when static/document extraction is insufficient, especially dynamic/JS pages; it is neither selected nor a replacement. Any future integration must preserve URL authorization, SSRF/private-address, redirect/TLS, size/time, provenance and verifier controls.
- Search → fetch: returned search URLs remain `fetch_authorized=false`; discovery does not authorize `web_url`. Any expansion needs a separate product/security decision, still unresolved.
- Priority: scoped data definition → BDDK ingestion → EVDS ingestion → prepared dataset → demo catalog mappings → table_transform → multi-turn table grounding → mandatory inspection/quality/semantic gates → organizer real three-turn E2E → production search compatibility → API/UI → evaluation/deployment/rehearsal. This is planning direction, not READY/DONE status or permission to postpone mandatory guards: each dependent capability must satisfy its correctness prerequisites before exposure.
- Supersedes only DEC-135's implication that runtime financial observations require source-adapter retrieval; its eight planner tools and mandatory harness roles remain unchanged. DEC-131's real deployed solution and on-day inputs still apply: prepare official observations, not canned answers or synthetic substitutes. Q-DATA-01/03, Q-NET-01/02 and relevant demo/environment questions remain open.
- Evidence and consequences: existing safe-fetch, parsing, storage, catalog and verification components provide reusable boundaries, not completed source ingestion. [ARCHITECTURE](ARCHITECTURE.md#official-data-preparation-and-demo-runtime) owns the target flow; [ROADMAP](ROADMAP.md#ordered-next-safe-tasks) owns readiness. Historical source inventories and completion records remain evidence of their original scope.

### DEC-137 — Catalog-complete, lakehouse-first, official-source materialization architecture

- Status: CONFIRMED team architecture direction, 2026-09-14, explicitly requested by Çağatay. This docs-only decision grants no source access, deployment/egress permission or implementation readiness.
- Rationale: The four-series vertical slice proves correctness but does not define final product scope. Prepared observations are the fast, reliable path; a broader trusted catalog enables unseen-series discovery, and approved reusable source adapters can fill known materialization gaps. Generic web discovery remains a separate trust domain.
- Coverage: Start with housing-credit outstanding balance, housing/mortgage interest rate, CPI/TÜFE and national KFE, approximately 2021-01–2026-06, with unresolved component/rate/base choices explicit. Expand to safely representable structured BDDK Monthly/Weekly/FinTürk financial measures (loans including consumer/vehicle/commercial/SME, deposits, NPL, rates/ratios, supported TP/YP/TOTAL, bank-group/geography dimensions) and relevant EVDS rates, indices, macro/banking families. This is neither a four-series ceiling nor an obligation to ingest every byte; exact broad-prepared coverage remains open.
- Catalog: Map natural-language concept → official ID/canonical selector candidates → trusted metadata/ambiguity → availability → routing. Preserve provider, concept/family, labels/aliases, frequency, unit/scale, stock/flow/rate/index, cumulative and aggregation rules, base year, archive state, coverage and provenance. Conceptual availability distinguishes prepared/materialized, fetchable through an approved official adapter, unresolved and unavailable/unsupported. These are target capabilities, not new fields/enums in the current CatalogRecord. Unresolved identity is never promoted to fetchable by ranking or model output.
- BDDK identity: Delivered bounded M3-05 uses `BDDK:selector:v1:<SHA256>` over provider, bulletin_family, table, row, bank_group, presentation_currency, value_dimension and geography. This is an internal canonical selector key, not a BDDK-native series code; period/retrieval time belong to observations/snapshots. General M3-05 stays PARTIAL; TP/YP/TOTAL and stock/disbursement ambiguity remains unresolved unless explicitly supported.
- Routing: Trusted candidate + required semantic inspection + requested-window availability check → lakehouse on a usable prepared hit. A known missing series/window may use a registered official adapter only when identity/semantics, bounded request contract and environment/source policy permit it; validate and materialize/version before analytical use, then reuse through lakehouse. Missing policy, adapter, valid source evidence or sufficient semantics → clarification/abstention. No arbitrary URL/search fallback, invented endpoint/series or new planner tool is authorized.
- Reusable adapters: Own official endpoint/request shape, selector/series mapping, response validation, source parsing, semantic declarations and provenance. Reuse common safe networking, TLS/bounds, parser, bronze/silver/gold, hashing, lineage and security primitives. Support initial preparation, broader pre-materialization, policy-permitted cache misses and later refresh; housing and CPI/KFE/rate cases are first verified use cases, not hardcoded adapter limits. These adapters are not delivered.
- Lifecycle target: DISCOVER → FETCH → SNAPSHOT → PARSE → VALIDATE → MATERIALIZE → VERSION → QUERY → REFRESH. Snapshot hashes, selector/request, retrieval/release metadata, parser/semantic policy and transformation evidence must identify reproducible input/output versions. Same official input content, selector and parser/semantic policy should produce the same content version or an idempotent no-op; another retrieval timestamp alone is not new financial content. Refresh can add periods or reveal corrected history, metadata/archive changes; preserve previous snapshots/versions and resolve revisions explicitly. No silent overwrite of trusted historical evidence, no new scheduler, and no completed vintage/manifest system is claimed.
- Publication boundaries: Materialization must validate a staged dataset before publishing a usable version/availability pointer; failed fetch/validation leaves prior trusted versions intact. This target is separate from M5-21's delivered accepted-turn workspace publication. A fetched dataset is not proof of an analytical claim; M8-21 result-to-execution binding and all final gates remain required.
- Prepared hot path: Broad preparation improves latency, demo reliability, repeatability, stable provenance and deterministic benchmarking across the requested 2021-01–2026-06 range, with fewer runtime network dependencies and less exposure to official-site outage/layout drift. Policy-permitted materialization complements that path; it is not guaranteed demo-time egress.
- Storage: Parquet is persistent analytical data/artifact format; DuckDB is an embedded compute/query engine, not a hosted database service. Dataset/object storage should support a local persistent filesystem/volume and, if justified/available, S3-compatible object storage for bronze snapshots, Parquet, manifests and versioned datasets. AWS S3 is not selected; S3-compatible integration, deployment durability and credentials are unresolved/unimplemented.
- Trust domains: Prepared official catalog datasets are persistent/versioned target state. Uploaded CSV/XLSX, PDF, arbitrary authorized URLs and BIST/IMF/other documents are session-scoped external artifacts; common parser/storage primitives do not promote them into permanent official catalog series. `web_search` remains general discovery behind SearchBackend; SearXNG is a preferred compatibility candidate, not integrated/live accepted, with upstream network/privacy policy open. `web_url` remains a specific authorized-document path; Crawl4AI is optional future extraction evaluation only. Search results still confer no fetch authority.
- Hybrid target: Preserve DEC-130's Turkish normalization, reviewed aliases, metadata filters, lexical/BM25 plus required dense retrieval using `kkbhackathon2026/Qwen3-Embedding-8B`; measured dimension 4096 (DEC-129/M4-12). Current catalog_search is aliases/filters/bounded BM25 only. Dense retrieval is not optional to final hybrid acceptance and is not implemented. RRF/reranking remain benchmark-gated.
- Vector product refinement: Supersede only the mandatory LanceDB index choice in DEC-130 and inherited DEC-115/124/133 wording. No vector product is selected now. A small/moderate catalog may use a versioned embedding cache keyed by series/concept ID, catalog text hash, model ID and dimension, with embeddings and deterministic cosine similarity. Benchmark a dedicated index such as LanceDB only when scale/latency justifies it. Financial observation values remain in DuckDB/Parquet; vector retrieval concerns catalog descriptions, aliases, concepts and semantic discovery. No dependency change is authorized by this decision.
- Evaluation: Expand beyond the four concepts: prepared known/unseen concepts, known-but-unmaterialized series, ambiguity/unknown semantics, permitted cache-miss materialization and reuse, refresh/new periods, historical revisions, Turkish paraphrases and lexical-versus-hybrid behavior. Preserve M13-09 independent holdout, numeric oracles and explicit abstention; no benchmark result is implied.
- Relationship: DEC-135's eight planner target names and mandatory correctness harness remain valid. DEC-136 remains valid for preparation/lakehouse-first runtime; this refines its final coverage, optional operational-refresh-only limitation and sequencing with controlled official cache-miss materialization and versioned refresh. DEC-112/117 storage/workspace choices, DEC-129/131 organizer constraints, DEC-134 search acceptance and current M5-21/M8-21/weekly M12-08 protections remain in force. Original decisions and historical source inventories remain intact.
- Consequences: [ARCHITECTURE](ARCHITECTURE.md#official-data-preparation-and-demo-runtime) owns contracts/routing, [ROADMAP](ROADMAP.md#ordered-next-safe-tasks) the staged priorities without READY promotion, and [OPEN_QUESTIONS](DECISIONS.md#open_questions-dec-137-unresolved-materialization-and-storage-policy) unresolved source-use/retention, demo egress/fetch, storage, broad coverage, vector implementation and vintage policy. No implementation task is started.

<a id="dec-137-prepared-pool-refinement"></a>
#### Current refinement — prepared-pool demo priority and catalog vector layer (2026-09-14)

Confirmed team priority refinement, explicitly requested by Çağatay after M3-06's offline delivery (#134/#135). The original DEC-137 record above remains historical and valid as the scalable architecture; this subsection owns current hackathon priority. It grants no organizer/source permission, new implementation or completed dataset acceptance.

- **Primary / demo-critical:** build and validate a broad, safely supported BDDK/EVDS prepared data pool before questions arrive: trusted adapters → immutable raw/bronze snapshots → validation/normalization → canonical silver observations → required gold analytical materializations → prepared DuckDB + Parquet lakehouse. Runtime uses user → planner → catalog_search → trusted prepared candidate → lakehouse → guarded transforms/analytics → mandatory correctness harness → verifier → accepted answer/table/chart. Mandatory checks run before dependent use; bronze ancestry alone is not analytical truth. The normal structured official-data path does not fetch BDDK/EVDS at question time. Financial-source network independence does not imply offline Kloudeks planning or query embeddings.
- **First vertical slice, not final coverage:** housing-credit balance, housing/mortgage rate, CPI/TÜFE and national KFE around 2021-01–2026-06. After the first real E2E slice works, broaden hackathon-relevant prepared official coverage as safely practical. Unknown identities/semantics remain UNKNOWN; neither every source byte nor unsupported calendars are promised.
- **Reusable adapters now:** build the prepared pool and support later controlled refresh through the same trusted identity/request/parser/provenance/materialization primitives. M3-06 is reusable infrastructure, not a one-off housing download. Its bounded offline slice is delivered; overall M3-05/M3-06 remain PARTIAL, with live BDDK/CA and real dataset preparation unaccepted. Minimal content identity, revision refusal and trusted publication protections apply now; sophisticated refresh/vintage orchestration is later work.
- **Scalability, not a core three-turn prerequisite:** a catalog-known unmaterialized series may later use a policy-approved official adapter → validate → materialize/version → reuse lakehouse. Runtime official-source cache-miss materialization, sophisticated refresh/vintage orchestration and object-storage optimization are not current demo blockers and are not implemented by this refinement. Demo prepared-pool misses may clarify or abstain; no generic web fetch fallback or invented coverage.
- **Required final catalog retrieval:** shared Turkish normalization + reviewed aliases + metadata filters + BM25/lexical retrieval + `kkbhackathon2026/Qwen3-Embedding-8B` dense retrieval, dimension **4096**, through Kloudeks. Current M13-04 remains lexical/BM25 only; dense and full hybrid acceptance are not delivered. Dense is not optional to the final architecture.
- **Separate vector-search layer:** the intended dense architecture includes a catalog vector DB/index boundary for storing/indexing/searching embeddings. Conceptual records bind official series/canonical selector ID, concept/family, normalized catalog/search text, text/content hash, model ID, dimension, vector and snapshot/version metadata. Runtime combines BM25 candidates with Qwen query embedding → vector similarity candidates, applies metadata constraints and returns a bounded candidate set. These are architectural records, not a new implemented schema. Financial observations never belong in this vector layer; bronze/silver/gold and analytical values belong to the DuckDB + Parquet lakehouse.
- **Product remains unselected:** LanceDB is a strong candidate and the preferred dedicated index to benchmark first. A small catalog may start with exact cosine over a versioned embedding cache; the logical vector-search responsibility remains explicit without requiring a separate service. Select a dedicated product only from catalog scale, latency, deployment simplicity, benchmark quality and dependency cost. No vector DB/index is implemented, and no PostgreSQL/pgvector service is justified or added by this decision. Scaling beyond measured need remains non-blocking; the required dense retrieval capability does not.
- **Separate web path:** web_search → SearchBackend for general discovery; SearXNG remains a candidate, not integrated/live accepted. web_url handles a specific authorized URL/document. Neither is the normal structured BDDK/EVDS data path. Source-use, retention, deployment and network questions remain open.
- **Execution guidance:** prioritize BDDK live acceptance/preparation; EVDS trusted metadata/ingestion; prepared pool; four-series real slice; organizer Turn 1; hybrid retrieval/vector baseline; table_transform; multi-turn grounding; mandatory inspection/quality integration; full three-turn E2E; broader prepared coverage; web acceptance; API/UI/deployment/rehearsal. This is priority guidance, not a READY queue or permission to defer correctness/security prerequisites. Existing checkboxes and bounded completion records remain authoritative.

> Refinement (2026-09-14): [DEC-138](#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git) moves deflation and table_transform ahead of dense retrieval and selects LanceDB; the rest of this execution guidance stands.

### DEC-138 — Handback priorities, LanceDB catalog index and no prepared data in Git

- Status: CONFIRMED team decisions, 2026-09-14, by Eray after Çağatay handed the project back (no other teammate active). Grants no organizer permission and claims no implementation.
- Context: The organizer's reference process (kick-off deck p.11) asks, after Turn 1, to inflation-adjust only the housing-credit column without breaking the table (Turn 2) and to add KFE as a new column (Turn 3). Deflation/rebasing (M2-14/15) and table_transform (M5-20) are absent, and the DEC-137 refinement sequence placed dense retrieval before them without naming deflation. Six development days remain to 20 September. M3-06 live BDDK acceptance and the 2021-01–2026-06 housing preparation passed on 2026-09-14 (PR #138).
- **Sequencing:** after EVDS metadata/ingestion, the four-series preparation and organizer Turn 1, deliver explicit index rebasing/deflation (M2-14/15, with M6-13 where needed) and table_transform with multi-turn table grounding (M5-20 and remaining M5 references) **before** hybrid dense retrieval (M13-05). Dense retrieval stays required for DEC-130 final hybrid acceptance; only its order changes. Mandatory correctness/security prerequisites are not deferred.
- **Vector index:** **LanceDB is selected** as the catalog vector index for M13-05. This supersedes "no vector product is selected" and the exact-cosine-first baseline in DEC-137 and its refinement; the kick-off deck lists LanceDB among the expected open-source libraries, and DEC-124 already allowlists `lancedb`. It is added to `pyproject.toml` only by the implementing task, with a pinned version, audit and deterministic ranking/failure tests. Vectors hold catalog representations (IDs, concepts, aliases, normalized text/hash, model and dimension 4096, snapshot version); financial observations stay in DuckDB + Parquet. No PostgreSQL/pgvector.
- **Prepared data storage:** retrieved official responses and prepared lakehouse contents are not committed to Git. They live in ignored operator-local roots (`data/processed/lakehouse`) and reach the demo through deployment preparation. This is team policy; organizer redistribution/retention (Q-DATA-03) remains open.
- **Source retrieval:** Eray authorized bounded official BDDK retrieval for preparation (applied in M3-06, 2026-09-14) and the move to EVDS trusted metadata/ingestion; each live run stays bounded and recorded in its task. Organizer-level Q-DATA-01/Q-NET-01 remain open.
- **Deferred for re-evaluation (resolved by [DEC-139](#dec-139--kullanılan-konut-kredisi-means-the-outstanding-balance), 2026-09-14):** the Turn 1 reading of "kullanılan toplam konut kredisi" (outstanding stock versus disbursement) and TP/YP/TOTAL presentation. The CPI index/base-year choice for Turn 2 is made from metadata evidence in the EVDS task and recorded there. A `dev -> main` promotion before 20 September is to be scheduled; it is not authorized here.
- Consequences: [ROADMAP](ROADMAP.md#ordered-next-safe-tasks) reorders its priority table; [OPEN_QUESTIONS](DECISIONS.md#history-q-team-06--vector-cacheindex-implementation) Q-TEAM-06 is answered. DEC-135's planner/harness roles, DEC-136/137 preparation architecture and the M5-21/M8-21/M12-08 protections are unchanged.

### DEC-139 — "Kullanılan konut kredisi" means the outstanding balance

- Status: CONFIRMED team decision, 2026-09-14, by Eray. Resolves the Turn 1 reading deferred in DEC-138; grants no organizer permission.
- Decision: in the organizer's Turn 1 question, "Türkiye'de kullanılan toplam konut kredileri" is the BDDK Monthly Bulletin table 4 row 2 (`Tüketici Kredileri - Konut`), Sektör (10001), TL presentation, **TOTAL** component — the month-end **outstanding stock** (`BDDK:selector:v1:fa6e3c79…0f66`). Answers present it as the housing-credit balance in use without a "does not answer the question" disclaimer.
- Still true and still stated: it is a stock, so a month-over-month change is a net change in the balance, not new lending or disbursement; no disbursement series is prepared or implied. TP/YP components stay separate series and are not the default.
- Consequences: the reviewed series name and writer guidance may drop wording that suggests the stock does not answer "kullanılan"; nothing is re-ingested. DEC-136/137 semantics, the BDDK source inventory and the stock limitations are unchanged.

### DEC-140 — Strict source typing at the fast PR boundary

- Status: engineering maintenance in Arda's delegated development scope, 2026-09-14, PR #151; effective when merged.
- Evidence: the earlier M0-08 release cleared typing, but later code accumulated 64 errors in six files while `make pr` stayed green. Checking all 86 source files takes about three seconds locally; the ordinary unit suite takes about three minutes. Checking only changed modules misses errors introduced at their consumers.
- Decision: include `mypy src` in `make pr` and its Windows equivalent after Ruff checks. Keep strict mode enabled. `make quick` and targeted edit-time checks remain lightweight. The full release gate still owns all-test execution, dependency audit and main promotion; this is not a per-edit full/release gate.
- Rejected: suppressing module errors or leaving the inexpensive contract check until the final release. Keep the existing narrow third-party typing exceptions documented; add no blanket ignore or new runtime dependency.
- Consequences: a new type error must be fixed before merging into dev. This amends the fast PR placement described in DEC-109/AGENTS, without altering organizer rules, runtime behavior or authorization boundaries.

<a id="dec-141-organizer-verbal-criteria"></a>

### DEC-141 — Organizer verbal criteria relayed by Çağatay

- Status: CONFIRMED as organizer-reported criteria, relayed by Çağatay on 2026-09-14 in the documentation-reconciliation request. The underlying organizer communication/transcript was not independently verified; no scoring weights or numeric judging thresholds were supplied.
- **Development versus runtime:** development coding assistants such as Cursor, Claude Code, Codex and Gemini are allowed (consistent with Q-DEV-01). The open-weight restriction applies to the delivered/runtime/demo harness: use allowed models through Kloudeks under DEC-002/129/131, never Codex/Claude/Gemini/OpenAI-hosted agent reasoning as a runtime analyst. This does not change the explicitly Kloudeks-configured SDK allowance.
- **Own harness and smaller-model usefulness:** the team must build its own harness. The reported judging intent is that deterministic/custom logic carries as much work as possible so the system remains useful with a smaller allowed open-weight model. DEC-101/113's typed planning, deterministic tools and custom validation/execution/gating support this criterion; their existence does not prove smaller-model acceptance.
- **Domain genericity — historical organizer relay, retained as provenance:** the core should remain reusable when BDDK/EVDS is replaced by a substantially different dataset/domain. DEC-001/103's source-adapter separation is necessary but does not establish cross-domain acceptance; finance-specific semantics and prompts must not be treated as universal contracts.
- **Current scope clarification (2026-09-14, relayed by Çağatay):** Genericity means avoiding hardcoding to one organizer question, BDDK table, EVDS series or exact financial schema. Current acceptance: add a new supported financial source / dataset / schema through reviewed catalog metadata and adapter/policy configuration without rewriting the core lakehouse, workspace, execution, lineage, verifier or API architecture. Finance-specific adapters, stock/flow/rate/index semantics, cumulative rules, deflation, KFE, guards/transforms and catalog mappings may remain finance-specific. Healthcare support, arbitrary cross-domain adapters and a universal data platform are not product requirements; the historical relay above is not a cross-domain implementation mandate.
- **Own lakehouse:** ready-made/managed lakehouse shortcuts, including Snowflake-style outsourcing, must not replace the team's lakehouse/harness architecture (DEC-003/112). This records the architecture criterion, not an invented ban on every hosting or infrastructure service.
- **Secrets:** committing API keys/secrets is negative even in a private repository. DEC-129 and SECURITY's existing prohibition still applies; private visibility is no exception.
- **Chained tables:** preserve the existing table, transform only requested columns, add columns without destroying the prior table, and continue from the intended current result. Immutable history alone does not satisfy this: UI selection must bind the following question to the intended owned result/version. Current display-only selection and remaining dependency invalidation are acceptance gaps, not completed behavior.
- Consequences: apply these criteria to current architecture and evaluation under DEC-135's mandatory harness boundaries. Record delivered slices and remaining acceptance separately in ROADMAP; this entry changes no runtime behavior and grants no live-call or merge authorization.

### DEC-142 — Catalog query embedding policy and reviewed-match combination

- Status: CONFIRMED team decision, 2026-09-15, by Eray (approves PROP-07 and PROP-08 after the M13-09 evidence in PR #178). Grants no live call beyond the task authorization recorded in ROADMAP.
- **Query policy:** catalog dense retrieval embeds passages unchanged and queries as `Instruct: <task>\nQuery:<text>` (`qwen3-instruct-query-v1`, Qwen3-Embedding model-card convention). M13-09 measured dense hit@1 0.8718 against 0.7179 for unchanged queries on 44 reviewed cases. Q-K-05 (the platform's own convention) remains open; a Kloudeks answer that contradicts this is a revisit trigger, not an automatic change.
- **Combination:** hybrid candidates keep the alternating lexical-first order only when a reviewed alias or phrase matched the query, and alternate dense-first otherwise (`reviewed-match-order-v1`). Archive tiering, the reviewed-concept eligibility restriction, fixed stage budgets, clarification requirement and explicit lexical degradation are unchanged. No score arithmetic, fusion or reranking is introduced (M13-06/07 remain benchmark-gated).
- **Evidence rule:** the M13-09 holdout was inspected when PROP-08 was proposed, so it becomes development data. A gain claim for this combination needs a fresh holdout written before any run on it; the measured result is recorded in EVALUATION whether or not it confirms the gain.
- Evidence after adoption (M13-05, #179, fresh holdout): hybrid hit@1 0.684 vs 0.579 for the alternating baseline (2 wins, 0 losses) and 0.842 for dense-only; the remaining gap comes from broad multi-series concepts keeping lexical order and the archive tier ([EVALUATION](EVALUATION.md#m13-05-fresh-holdout-2026-09-15)). Changing either is a new decision that needs another fresh holdout.
- Consequences: the prepared runtime may configure the dense stage with this policy and combination when an operator supplies a matching local index generation; without it, retrieval stays lexical. DEC-130 hybrid acceptance, DEC-138 LanceDB selection and the untrusted-discovery boundary of `catalog_search` are unchanged.

### DEC-143 — Similarity-only catalog results are unresolved candidates

- Status: CONFIRMED task decision, 2026-09-15, by Çağatay through the delegated M13-14 catalog-quality iteration. It grants no live call or broader retrieval redesign.
- **Policy:** a nonempty BM25 or dense/hybrid result with no reviewed alias or reviewed phrase match is `PARTIAL`, not `MATCH`. The ranked candidates remain visible as untrusted discovery metadata so the caller can clarify; this status does not declare the request unsupported or select a series. A reviewed match may remain `MATCH` only when its mapped semantics are not otherwise partial/unresolved.
- **Scope:** candidate identities, scores, stage order, DEC-142 combination, archive tier, filters, limits, `NO_MATCH`, `UNRESOLVED` and `FILTERED_OUT` are unchanged. No similarity threshold, stopword list, query-specific rule, alias addition, reranker or score fusion is introduced.
- **Evidence rule:** the focused M13-14 holdout was committed before its first retrieval run and is evaluation-only. On its 16 unseen cases, eight supported rankings remain top-1 correct while eight unsupported intents move from 0/8 to 8/8 acceptable clarification status; candidate rankings are identical before and after. See [EVALUATION](EVALUATION.md#m13-14-catalog-similarity-safety-2026-09-15).
- Consequences: `MATCH` now means the query has reviewed concept evidence, not merely lexical/vector proximity. The planner, API, prepared pool, embeddings and archive-intent policy are unchanged.

### DEC-144 — Explicit reviewed qualifiers refine catalog candidate order

- Status: CONFIRMED task decision, 2026-09-15, by Çağatay through M13-15. It grants no live call, new catalog identity, alias change or broader retrieval redesign.
- **Policy:** After BM25 ordering or DEC-142 stage interleaving, apply one stable deterministic post-order using only explicit query qualifiers that have typed/reviewed candidate counterparts: amount/rate kind, new-credit versus outstanding-portfolio rate basis, inclusion/exclusion wording, currency/component, base year and archive intent. A semantic contradiction ranks after compatible or unknown metadata; compatible declarations rank ahead of unknowns; the incoming order remains the final tie-break. This step never creates/removes candidates, alters BM25/cosine scores, or changes reviewed concept eligibility.
- **Archive boundary:** `include_archived=false` still excludes archives. When archives are opted in, explicit archive intent may rank them first; otherwise archived records remain after non-archived records. The current snapshot declares its other records UNKNOWN rather than ACTIVE, so the policy makes no active-status claim.
- **Safety:** DEC-143 status is unchanged. Similarity-only candidates remain `PARTIAL`; every nonempty result remains clarification-required. Under-specified multi-series concepts retain all reviewed alternatives instead of manufacturing a primary. The vocabulary is a bounded qualifier policy, not a set of question-to-series aliases, and runtime never reads evaluation cases.
- **Evidence:** The 22-case holdout was committed at `b2f2098` before its first run. Offline lexical hit@1/MRR improved 0.7368/0.8333 to 1.0/1.0, Recall@5/10 improved 0.9474/0.9474 to 1.0/1.0, no-answer status acceptance stayed 1.0 and archive leaks stayed zero. Previously seen N07 and N09 moved rank 2→1. N18 stayed `PARTIAL` with no BDDK balance candidate because post-ordering does not expand lexical generation. See [EVALUATION](EVALUATION.md#m13-15-catalog-quality-hardening-2026-09-15).
- Consequences: DEC-142 still owns initial lexical/dense interleaving and DEC-143 owns resolution status. A live dense measurement is still required before claiming real-embedding gains; no embedding/source/search request was made for this decision.

### DEC-145 — A points or index header unit names an index level for document columns

- Status: CONFIRMED team decision, 2026-09-17, by Eray (option 1 of three offered after PR #224). Grants no live fetch or organizer permission.
- Context: M7-14 `add_document_column` reads a fetched table column with strict rules; a document never states stock/flow meaning, so the column was recorded as unknown and `table_co_movement` (stock, rate or index columns only) refused it. That blocked the organizer-style follow-up of comparing a URL index such as BIST 100 with a prepared series.
- Decision: when the value header's trailing parentheses state points or index (`(Puan)`, `(Points)`, `(Endeks)`, `(Index)`) at scale one, the added column is an **index level**; the transformation records `measure_source: column header unit` and the limitation says nothing else was inferred. Every other column — currency, percent, counts, scaled points — keeps stock/flow unknown and stays out of comparisons that need a measure.
- Rejected: a planner-supplied measure argument (a correctness choice in model discretion; the #212 opt-out lesson), and leaving document columns display-only.
- Consequences: `_document_value` also reads `(Endeks)`/`(Index)` as a unit for literal cells; DEC-104/132 guards and the unknown-unit refusal are unchanged. Revisit when reviewed metadata for a document source can state its measure directly.

### DEC-146 — A percent header unit names a rate for document columns

- Status: CONFIRMED team decision, 2026-09-17, by Eray (chosen while approving the M10-04 document-table design). Extends DEC-145; grants no live fetch or organizer permission.
- Decision: when a document column's value header states `(%)` at scale one, the column is a **rate**; the transformation records `measure_source: column header unit` and the limitation says a share or percentage change would read the same way. DEC-145's points/index → index rule is unchanged; a scaled percent (`(Milyon %)`) and every other unit keep stock/flow unknown.
- Consequence: document percent columns (interest, inflation-like rates) can enter `table_co_movement`, which accepts stock, rate and index columns; deflation still requires a currency stock or flow and never accepts a document column. The reviewer should read a percent column's limitation before interpreting a comparison.
- Rejected: leaving percent columns unknown (the recommended default), and letting the planner declare a measure.

### DEC-147 — Document CSV separators are detected, and month row labels give a cell its month

- Status: CONFIRMED team decision, 2026-09-17, by Eray (three options approved while scoping the M10-04 reader gaps measured in the [bounded live document run](EVALUATION.md#m10-04-live-documents-2026-09-17)). Changes M1-06's explicit-declaration rule on the document path only; grants no live fetch or organizer permission.
- Context: the planner never sees a document's bytes, so an uploaded or prompt-address `;` CSV was refused unless the question named its separator (U1/U2), and a `2025-12` row label set no period, so an answer naming December 2025 was withheld (U2b).
- Decision (separator): `load_document` (web_url, `add_document_column`, uploads) detects an undeclared CSV separator inside the bounded parser worker. On a leading prefix, each of `,` `;` tab `|` is a candidate when the strict structure check passes on the complete records with one width of at least two; exactly one candidate is used and must still parse the whole file. None or several keep `PARSING_DECLARATION_REQUIRED`. A declared separator that contradicts the single candidate is refused as `DELIMITER_CONFLICT`; with no single candidate a declaration is used as before. Document table/column evidence records the separator and whether it was declared or detected. `load_csv` keeps the strict M1-06 default for any other caller.
- Why it cannot choose a wrong reading silently: the checked prefix records are exactly the first records of the whole text under each separator, so a separator refused there is refused on the whole file; one candidate that parses the whole file is its only reading. Too few complete records leaves the choice undecided.
- Decision (month cells): in cell mode a month-form row label (`YYYY-MM`, `MM.YYYY`, Turkish/English month name with year) sets that calendar month, with a limitation that the document does not say whether the value is a month-end level, an average or a total. Full-date labels keep their single-day period; year labels set none. Row matching equates one month written in different forms, never a day with a month and never a cell that reads as a number (`12.2025`).
- Rejected: declared separators always winning (a planner guess could split a table wrongly); detection on the strict loader default; first/last-day dates becoming months in cell mode (a daily row cannot be told from a monthly one there).
- Consequences: DEC-104/132 guards, the literal cell proof (which now also re-checks the recorded month) and table-mode month rules are unchanged. Text-layout PDF tables and year-less month labels (`kmp_au.pdf`) remain a separate reader decision.

### DEC-148 — Text-layout PDF tables, year context, table digit convention and special rows

- Status: CONFIRMED team decision, 2026-09-17, by Eray (four options chosen after an offline inspection of the organizer's Borsa İstanbul `kmp_au.pdf`). Extends DEC-147 for every document reader; grants no live fetch or organizer permission.
- Context: the organizer's example PDF sets its gold trading table out with text and filled cells, not ruling lines. Its months carry no year (`Ocak / January`, year only in the title), its header has TL/USD/EUR/TOPLAM group cells over bilingual leaf headers, figures such as `13.837` kg are ambiguous alone, and it ends with a `TOPLAM / TOTAL` row and zero placeholders for months not yet published. The ruled-table reader returned one headerless column.
- Decision (layout tables): the PDF worker reconstructs unruled numeric tables from word positions — rows by baseline, value columns by the right edges at least two numbers share, a left label run, header runs ending on a column edge (up to four lines within 1.5 row pitches). A number that fits no column or two, or a text cell breaking a row, leaves the block unread. A group label binds to the columns a drawn header cell around it covers, and only if that cell holds no column header; without such a cell groups are not used. Bilingual `A/B` names match either side and composite names match group + leaf, still requiring exactly one column. Grids drawn only by filled rectangles are shading: they hide no words and are dropped where they overlap a layout table, as is a one-column fragment.
- Decision (year): a month name without a year takes the single distinct year stated in the page text above the table; failing that, a planner `year` argument accepted only when that year appears as its own number in the user's question (`YEAR_NOT_IN_QUESTION` before any fetch). A different planner year than the document's is `YEAR_CONFLICT`; several document years give no period.
- Decision (digits): a table in which some text cell reads only with Turkish grouping and none only with English (or the reverse) reads its ambiguous `1.234`/`1,234` figures in that convention; contradicting or no evidence keeps `AMBIGUOUS_NUMBER`. Dates and month labels are no evidence; unambiguous figures never change.
- Decision (special rows): table mode skips closed-list total rows (`Toplam`, `Total`, `Genel Toplam`, `Grand Total`, and `A / B` pairs of them) with a warning; a period ending after the document's retrieval or upload date is not an observation — dropped with `FUTURE_PERIOD` in table mode, refused in cell mode.
- Recording: table/column evidence records the year and its source, the convention when it decided a figure and skipped-row counts; cell results name the year source in `period_source` and limitations.
- Rejected: geometric group assignment (on the organizer file itself it binds EUR trade counts to TOPLAM), parenthesised-title-only years, keeping ambiguous figures refused, and keeping not-yet-published zeros as observations.
- Consequences: DEC-104/132 guards and the literal cell proof are unchanged. Tables with left-aligned numbers, centred headers without drawn cells, text columns among the numbers or year column headers still stay unread; OCR text still never becomes a cell.

### DEC-149 — OCR tables count only through a column-total check

- Status: CONFIRMED team decision, 2026-09-17, by Eray (two options chosen after the [Q-K-01 OCR probe](EVALUATION.md#q-k-01-ocr-probe-2026-09-17)). Applies DEC-119's schema and total/consistency requirement to OCR; grants no live call by itself.
- Context: the DEC-129 OCR model is reachable and returned the organizer's gold trading page as an HTML table with row/column spans, all 94 numeric cells equal to the text layer. Under DEC-119 OCR text was never usable, so serving OCR alone would change no answer.
- Decision: `--enable-ocr` (served API and rehearsal launcher, the latter with its own reserved, content-free OCR ceiling) passes the OCR model to `web_url` and `add_document_column` for PDF pages without a text layer; M7-11 page/pixel/byte bounds are unchanged. A bounded parser reads OCR `<table>` blocks — spans expanded into a rectangle, ragged/nested/over-budget tables skipped, leading rows without numbers as up to four header rows giving DEC-148 group + leaf names, years from the OCR text before the table. An OCR column counts only when the table holds exactly one closed-list total row and the column's other readable cells (at least two) sum to that row within rounding: at most one half of the last printed digit per summed cell. Other columns are left out in table mode and refused in cell mode (`OCR_NOT_VALIDATED`); a table without a total row yields no OCR value.
- Recording: table/column evidence carries `extraction: ocr` and `validation: column total`, the cell lineage an `extraction` attribute, the proof document `extraction: "ocr"`, and results a limitation naming OCR and the check.
- Rejected: exact equality (the organizer page's own kilogram totals differ by one from their rounded parts), and quoting unchecked OCR cells with a warning.
- Consequences: DEC-104/132 guards and the literal cell proof are unchanged; OCR text outside a checked table never becomes a number. Scanned tables without a total row still abstain; native text layers are always read first.

### DEC-150 — Prompt-address authority: same-site link follow and script endpoint datasets

- Status: CONFIRMED team decision, 2026-09-17, by Arda (implemented with Claude Code on branch `feature/generic-acquisition-chat-reply`).
- Context: `web_url` previously accepted only the literal user-written address. Real-world financial pages (e.g. Borsa İstanbul gold trading, XTUMY) link to PDFs and expose data through same-site JSON endpoints filled from the page path. The planner cannot supply addresses (DEC-132); extending authority must stay within the user's explicit page scope.
- Decision: a user-written address also authorizes (a) one hop to a same-registrable-domain link whose text or filename appears in the page bytes (`follow="<link text or file>"`), and (b) same-site JSON endpoints declared in the page's own same-site scripts, filled only with the page path's last segment (`follow="endpoint_N"`). Every request still goes through `safe_fetch`; the planner never supplies an address. Authority is scoped to exactly one hop and one registrable domain.
- Evidence: `test_page_links.py` (same-site link extraction and negative cases), `test_address_outline.py` (page outline and endpoint discovery), `test_script_page_dataset.py` (script endpoint dataset reading).
- Rejected: allowing the planner to supply arbitrary URLs; multi-hop link following; cross-domain link following.
- Consequences: DEC-132 safe_fetch boundary unchanged. SECURITY.md URL/file section updated. The planner's address_outline tool provides link/endpoint headers without values.
- Amendment (2026-09-18, second reviewer): the decision was CONFIRMED by its implementer alone; a second reviewer approved it on the condition that the delegation boundary is the **origin** (scheme, host and port), not the registrable domain, because one domain can hold a subdomain nobody vetted. Written conditions: one hop to a link actually present in the page; a same-origin JSON endpoint written in the page's own static script text, with no JavaScript executed and no endpoint guessed, only the documented template field filled with the page path's last segment; every request revalidated by `safe_fetch` (DNS/IP, redirect, TLS, byte/time/media limits), GET only, no cookie or credential; a **delegated** request may not be redirected out of its origin, while the person's own address may redirect and the page it ends on becomes that origin; one level only, so nothing is discovered from the second page; the planner supplies no address, only targets deterministically provable from the person's address. Allowed media types: PDF, CSV, XLSX, static HTML, JSON, and the page's own script files (read as text, never executed). Implementation: `origin_of`/`same_origin` in `url_targets`, `FetchRequest.stay_within_origin`, `TargetReason.CROSS_ORIGIN`. Measured before narrowing: every script of `borsaistanbul.com/endeks/xu100` is on the page's own origin, so the BIST case still works.

### DEC-151 — Operation-scoped semantic checks replace table-level refusal

- Status: CONFIRMED team decision, 2026-09-17, by Arda (implemented with Claude Code on branch `feature/generic-acquisition-chat-reply`).
- Context: previously, any unresolved semantic field (e.g. unit not stated on a document column) caused the entire table to be refused. This prevented legitimate operations on other columns with fully resolved semantics.
- Decision: semantic checks are scoped to the columns an operation actually uses (`add_series`, `align`, `filter`, `rebase`, `table_co_movement`). A column with unresolved unit can coexist in a table; operations that touch it declare the unresolved status. The answer gate is unchanged: unresolved figures are never quoted in final answers. For cumulative behavior on undeclared columns, `detect_cumulative` with NONE/HIGH outcome is used and the result is labeled `inferred`.
- Rejected: removing semantic checks entirely; allowing unresolved figures in answers.
- Consequences: document columns without a stated unit are kept (`column_units` from the user's question records provenance). DEC-104 answer gate unchanged.

### DEC-152 — Plan contract: conversational reply and budget increase

- Status: CONFIRMED team decision, 2026-09-17, by Arda (implemented with Claude Code on branch `feature/generic-acquisition-chat-reply`).
- Context: conversational messages ("Merhaba", "bu sonuç ne demek") forced the planner into plan/clarification, producing awkward abstentions. The system needed a lightweight response path without tool execution.
- Decision: `AnalyticalPlan.reply` added to the plan contract; exactly one of `steps`, `clarification`, or `reply` is set. `REPLY_INSTRUCTIONS` and the last 6 turns of conversation history are included in the initial planning call only (not continuation), so the #237 continuation budget test still holds. A reply cannot be issued when the message contains a URL or document attachment (guarded by `PlanRejected`). `Budget.max_steps` raised from 8 to 12 to accommodate multi-step acquisition workflows.
- Rejected: adding a separate router tool or pre-classifier; sending history to continuation calls; unlimited step budget.
- Consequences: no tool execution or publication occurs on a reply. Selected table is preserved across conversational turns. The continuation prompt budget (#237) is unaffected.

### DEC-153 — Capabilities follow their configuration, and the agent reads continuation itself

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code).
- Context: two switches asked the operator and the analyst to state what the system already knows. `--enable-ocr` had to be remembered next to `KLOUDEKS_OCR_MODEL`, `--enable-uploads` next to a product requirement, and the client's "continue with the selected table" checkbox made the person declare, before every message, whether it continued the previous request. A control whose answer is derivable is a control that will be set wrongly.
- Decision: on the served API, OCR is on exactly when the DEC-129 OCR model is configured (`--no-ocr` refuses it), and uploads are admitted by default (`--no-uploads` refuses them); readiness JSON keeps reporting both. Network egress stays opt-in under `--enable-web-url`: it is a boundary decision, not a configuration fact. The client no longer pins a table or states `is_continuation`: the planner is shown every table the conversation published (names, producer, coverage, column labels; never values), so it chooses. With a clarification pending and no stated `is_continuation`, a short message is read as its answer and a message that asks something of its own at request length (ends with `?`, at least six words) replaces it; the reading and who made it are recorded in the turn's trace (`clarification`, `clarification_decided_by`). `Question.selected_result_id` and `is_continuation` stay in the API for callers that want to pin explicitly.
- Rejected: defaulting network egress on with the same argument; a model call to classify continuation (cost and non-determinism on every turn); keeping the checkbox as an "advanced" control.
- Consequences: DEC-149's `--enable-ocr` and M10-04's `--enable-uploads` are superseded as switches, not as rules — the OCR column-total check and the upload admission checks are unchanged. The rehearsal launcher (`tests/manual/live_client.py`) keeps `--enable-ocr --max-ocr-requests N`, because there the flag reserves a live request ceiling rather than declaring a capability.

### DEC-154 — Published tables are written to gold; cumulative columns convert only by declaration

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code).
- Context: `gold_cells` (M12-13) and `lakehouse.cumulative.to_flow` (M2-16) existed but nothing called them at runtime. Gold stayed empty, so the verifier's store recheck could reach only `silver_observations` and a derived column (deflated, joined, rebased) was checkable against context alone. Every analytic refused a cumulative series with "convert it to flow first", and no operation could convert.
- Decision: after a turn's answer is gated and its table published, the runner writes the table's period columns to `gold_cells` under the workspace name, each column with a lineage node deriving from the result's own node (`gold_from_result`). A result that is not period-shaped, mixes frequencies or has no lineage node is not written; the trace records `gold.materialized`, `gold.skipped` or `gold.refused`. Gold never carries semantics: SQL over it returns inspection rows, and units and scales still come only from `silver_series`. `table_transform` gains `to_flow`: it adds a per-period flow copy of one column whose series the store declares `yearly_reset` or `since_inception`; a period without an adjacent predecessor stays empty, and a column declared `none` or `unknown` is refused rather than differenced.
- Rejected: writing gold before the gate (this turn's claims would bind to cells it wrote itself); inferring the cumulative kind from the values; filling the first period with the cumulative value.
- Consequences: the reviewed catalog currently declares no cumulative series, so `to_flow` refuses on the prepared pool today and becomes useful as acquisition registers declared cumulative series. Tests: `test_gold_runtime.py`, `test_to_flow.py`.

### DEC-155 — A reviewed EVDS series outside the prepared pool is fetched on first use

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code; operator switch, off by default).
- Context: the planner discovers series in the reviewed catalog, but the served runtime could only compute over the prepared pool. A catalog candidate outside the pool ended the turn with `not_prepared`, although `evds_series.REVIEWED_SERIES` and `ingest_series` already fetch, parse and store exactly those series offline. The product brief requires the agent to reach official data it does not yet hold without inventing identifiers or endpoints.
- Decision: `--enable-official-acquisition` wraps the per-turn `PreparedSeriesInspector` in `AcquiringInspector`. Only a `not_prepared` verdict for an id `EVDS:<code>` whose code is in the reviewed registry triggers `ingest_series` into the session's own lakehouse — never the prepared seed — over the operator's fixed window (ten years to the clock's date; silver keeps one immutable batch per series, so a per-question window would conflict). The same inspector then re-inspects against the same catalog record, so a fetch makes a series present, never consistent by itself. Each series is attempted at most once a turn, a turn starts at most three fetches, and every attempt is a trace event `acquisition.<code>` with the window and counts. Readiness JSON reports `official_acquisition`; `/v1/health` lists the capability and the settings panel shows it.
- Rejected: a planner-visible acquisition tool with a code or URL argument (the model would choose transport inputs); a question-derived window; fetching into the prepared seed; BDDK bulletin selectors in this slice (their operator path is separate and needs its own review).
- Consequences: unreviewed EVDS codes, BDDK selectors and catalog series with unresolved semantics are refused with the inspector's existing reasons and no request. Every fetch is a live public request, so live acceptance needs its own approval; offline evidence is `tests/unit/test_official_acquisition.py` (15 tests: strict loader path, one attempt per series, budget, transport failure, malformed response, inspector pass-through, served turn with trace, switch off, readiness and health).

### DEC-156 — Cooperative turn cancellation, table export and a 1–5 answer score

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code); closes three items of the M5-20-FLOW handover (real cancellation, export, 1–5 feedback scoring).
- Context: a turn could not be stopped once admitted, a published table could only be read on screen, and feedback was up/down with reasons but no graded score.
- Decision: `POST /v1/sessions/{id}/turns/{turn_id}/cancel` (202, returns the turn) raises a per-turn flag carried in a context variable (`agent/cancellation.py`). Checkpoints sit before every planner call, before every tool step and before the writer call; a request already in flight is never interrupted. A cancelled turn ends `failed` with error `cancelled`, publishes nothing, and its run is stored with status `cancelled` and a `turn.cancelled` event naming the checkpoint. Cancelling a finished turn changes nothing. The web client shows a stop button while a turn is pending. Export is client-side from the validated published cells: an RFC CSV, a Turkish-Excel CSV (`;`, decimal comma, UTF-8 BOM) and an evidence package (question, answer, version, every cell, proof); text fields that a spreadsheet would evaluate are written as text, numbers keep full precision and empty cells stay empty. Feedback gains an optional `score` 1–5; stores created earlier are migrated in place and their ratings keep no score.
- Rejected: killing the worker thread; a server-side export route (the browser already holds the verified cells, and a route would widen the boundary); an XLSX dependency.
- Consequences: new error code `cancelled` and run status `cancelled` in both contracts. Tests: `test_cancellation.py` (held provider cancelled mid-turn, finished turn, stranger and unknown turn, checkpoint semantics), `test_feedback.py` score and migration cases, web `export.test.ts` and the proxy cancel-route test.

### DEC-157 — An editable, versioned knowledge base layered over the reviewed catalog

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code).
- Context: the team asked that everything the agent knows be visible and manageable — add, change and remove data and catalog entries — without losing what earlier answers rested on. The reviewed catalog and prepared pool are content-hashed evidence read by the inspector, the dense index and every proof; editing them in place would silently change the ground under published answers.
- Decision: a separate append-only store (`knowledge.sqlite` under the state root, `knowledge/store.py`) holds two kinds of entry. **User datasets**: numbers a person supplies — pasted month rows or one column of a table already uploaded to their conversation, read by the same strict loaders with every refusal kept except the header unit — together with the meaning they *declare* (unit, scale, monthly/quarterly/annual frequency, stock/flow/rate/index, cumulative kind, aggregation, base year, aliases). Every save is a new version with its own series id `USER:<slug>.v<N>`; saying the same thing again is not a version. **Series notes** on reviewed series: archive/restore, search aliases, a note. "Delete" is archiving everywhere: the entry leaves discovery and computation, its history stays and it can be restored. Each turn applies the store as `effective_snapshot`: archived reviewed series get status ARCHIVED (search skips them, the inspector refuses them); aliases become user concepts; active datasets become catalog series with provider USER, a `user-declared` source and a "not reviewed" note, and are loaded into that conversation's own lakehouse (never the seed) through bronze/silver like any series, so the unchanged inspector checks their stored declaration against their record. With an empty store the reviewed snapshot is returned as-is (same digest). When entries exist the dense index no longer matches the digest, so that turn's discovery is lexical, and the trace event `knowledge.applied` says so with the catalog digest and datasets loaded. API (owner key required, author recorded): `GET /v1/knowledge`, `GET/POST /v1/knowledge/datasets[/{slug}]`, `POST …/{slug}/archive|restore`, `GET/POST /v1/knowledge/series/{id}/notes`; only the dataset save route accepts a body up to 1 MiB. The web client adds a "Bilgi tabanı" panel with filters (prepared, fetchable, catalog only, mine, archive), per-entry detail, archive/restore, alias and note editing with history, and a dataset form.
- Rejected: editing the reviewed snapshot or prepared pool; hard delete; inferring a dataset's unit from its caption; rebuilding the dense index per edit.
- Visibility: `GET /v1/knowledge/series/{id}/values` shows a prepared series' stored observations, read from the verified seed with a read-only DuckDB connection so that looking can never change what later sessions copy (the seed manifest is asserted unchanged in `test_knowledge_api.py`).
- Consequences: a user-declared cumulative kind makes `to_flow` reachable for that dataset, recorded as the person's declaration (the provenance route Eray's M5-20 gap note named). Weekly datasets carry their anchor weekday (`weekly_anchor`, required for and only for weekly data) and every period must end on it; pasted weekly rows give the full period-end date. Tests: `test_knowledge_base.py` (17: versions, archive/restore, refusals, snapshot identity, search, archive refusal, alias disambiguation, inspector, served turn on a user dataset, served refusal on an archived series), `test_knowledge_api.py` (11), web `knowledge.test.ts` (3).

### DEC-158 — SearXNG as the web_search backend, and search results shown as a fixed list

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code); the concrete backend DEC-134 left to a later selection. DEC-134's release requirement stands: a live, hidden-like search smoke must still pass before production search is claimed.
- Context: `web_search` had a provider-neutral contract and no backend, and even with one its results could not reach the person: a plan whose only successful step was a search ended "no tool produced an analytical result".
- Decision: `tools/searxng.py` implements `SearchBackend` over a SearXNG instance's JSON API (`/search?q=…&format=json`). It is operator configuration (`--searxng-url`), not a planner argument. The request goes through `safe_fetch` — the supervised transport every other outbound read uses, keeping DEC-002's single raw HTTP client in the Kloudeks module — with no redirects, a deadline and a 1 MiB body ceiling. Because `safe_fetch` refuses loopback and private destinations, the instance must be reachable at a public address; a loopback instance would need its own reviewed exception; only `title`, `url`, `content` and `publishedDate` are read, a result without a title or URL is dropped, and the instance's error text is never surfaced. SearXNG needs no API key, so no credential enters the process. When a turn's successful steps produced search candidates and no analytical result, the answer is a deterministic list — header, one `- title — domain: address` line per candidate, a footer asking the person to write an address in the question for `web_url` to read — passed through the same gate as a conversational reply, so a line whose title carries a figure nothing verified is withheld whole. No writer call is made and no snippet reaches the model. Readiness JSON reports `web_search`, health lists it, and the settings panel shows it.
- Rejected: letting search results authorize `web_url`; model-written summaries of snippets; a commercial API needing a key in the operator environment.
- Consequences: `test_web_search_tool.py::test_injection_is_inert_and_search_cannot_support_a_numeric_answer` no longer expects an abstention; it now asserts the injected numeric title is withheld from the listing, alongside the unchanged no-writer and no-snippet-in-prompt checks. Tests: `test_searxng.py` (15).

### DEC-159 — Official acquisition is on by default, covers BDDK, and what is fetched is kept

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code); amends DEC-155.
- Context: Arda asked why a catalog candidate outside the prepared pool should ever be refused instead of fetched and added to what the agent knows. Under DEC-155 acquisition was opt-in, EVDS only, and a fetched series lived in one conversation's lakehouse and was fetched again by the next.
- Decision: acquisition is on unless `--no-official-acquisition`. Reviewed BDDK monthly housing selectors (TL, FX, total) gain a route through `ingest_monthly` over a fixed 24-month window ending three months before the clock's month (the bulletin's publication lag; a month not yet published fails the batch, never fills it). The EVDS window now ends at the last whole month on or before the clock's date — a mid-month window was refused by the EVDS request contract and would have raised inside a turn; any request the reviewed contract refuses is now an `acquisition.refused` outcome, not a crash. An `AcquisitionStore` under `<state-root>/acquired/` keeps each successful raw response by request fingerprint and replays it through the same parser, so another conversation or a restart does not refetch within the same window, and it logs when each series was fetched; the knowledge-base listing shows that time and marks every series with a reviewed route as fetchable. Trace events carry `from_store`.
- Still refused, deliberately: catalog series whose unit, scale, frequency or stock/flow meaning is unknown (computing on them would be guessing — a person can declare one in the knowledge base, DEC-157), EVDS codes outside the reviewed registry, and BDDK selectors outside the reviewed housing scope.
- Tests: `test_official_acquisition.py` (22, including the mid-month regression, BDDK month-by-month fetch, kept bytes replayed for a second lakehouse with no new request, a new month refetching, and failed fetches not kept), `test_knowledge_api.py` listing case.

### DEC-160 — Bounded table context, evidence graph, per-turn traces and recovery from a reset server

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code); closes the remaining M5-20-FLOW handover items for context compaction and the evidence graph, and makes live tracing reachable.
- Decision: (1) The earlier-results block the planner sees has a budget (`MAX_WORKSPACE_PROMPT_CHARS`, 6000). Newest tables are described in full; over budget, older ones keep a one-line entry (name, producer, coverage, "labels omitted") so every table stays reachable by name, a table is compacted only when that actually shortens it, and publication order is kept. Values never enter this block. (2) A result's recorded proof is drawn as an SVG graph (sources and documents → steps → this result) from the proof's own `inputs`; nothing is inferred and no drawing library is added. (3) "İşlem ayrıntıları" opens that turn's own run rather than the newest one (it previously showed the latest run under every turn), and a running turn offers "Canlı izle", which follows its events as they are stored. (4) A browser key the server does not know (another state root) is replaced instead of surfacing as "forbidden", and a tab whose session the server no longer has is reset with a stated reason instead of showing broken turns.
- Tests: `test_conversation_context.py` budget case, web `proof.test.ts` graph cases, `client.test.ts` key recovery; verified in the browser against a local scripted rehearsal (stop mid-turn, live watch, graph, recovery after a server reset).

### DEC-161 — Complete traces, declared semantics for every proven row, and catalog bounds that are guards

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code), from a bounded live Kloudeks run (thinking on) whose traces were read in full.
- Findings that drove it: (1) the writer call was untimed and its prompt, token counts and the model's reasoning were not recorded, and tool outputs were stored as Python text; a 1–2 sentence answer took up to 378 s, and a continuation up to 900 s (timeout) at about 7.5 tokens/s with 700–2000 reasoning tokens per call; (2) a lakehouse table whose SQL omitted `s.observation` was published as an "unknown" measure, so the next turn's deflation refused it; (3) the planner was told both "plan analysis directly" and "you MUST first plan catalog_search"; (4) the writer restated an unrelated earlier comparison and, when every value was tabled, wrote that the question was not covered; (5) earlier tables were described to the planner only by selector hashes; (6) the catalog schema allowed 40 series with 37 reviewed, so a fourth knowledge-base dataset would invalidate every turn's catalog, and search output could not report more than 40 candidates.
- Decision: (1) Every model call is a timed span with its full prompt messages, `prompt_tokens`/`completion_tokens`/`reasoning_tokens` and a `model.reasoning` event holding the reasoning text; tool outputs are stored as JSON; `KLOUDEKS_PLANNER_THINKING` and `KLOUDEKS_WRITER_THINKING` exist and both default to on — the model does the planning and the writing, and no model call is replaced by code. (2) A lakehouse row whose `series_id` is a proven stored identity takes any unit, scale, frequency, anchor and stock/flow kind the query did not select from that series' `silver_series` declaration; `silver_observations` alone is a provable source; any metadata a query does select must still equal the stored value. (3) With discovery required, the contradicting "plan analysis directly" sentence is not sent. (4) The writer is told, when every value is in the table the reader sees, that the table is the answer (it had written "not covered" beside a 24-row table); it still sees earlier published tables, which follow-ups may cite — its restating an unrelated earlier comparison stays open. (5) Series are named for the planner by `series_display_name`, generated from the turn's catalog record (provider, title, labels, unit, frequency, kind), so reviewed, fetched and user-declared series are named the same way with no list kept by hand. (6) Catalog sizes are bounded by `MAX_CATALOG_SERIES` (10 000) and related guards, shared by the catalog, vectors, search output, knowledge API and web contract; active user datasets may use half.
- Rejected: writing comparison answers in code instead of the writer call (reverted — the competition's model must do the work); a hand-kept name list for the workspace outline.
- Tests: `test_kloudeks_provider.py` usage/reasoning and thinking switches, `test_series_inspection.py` omitted-declaration and observations-only cases, `test_conversation_context.py` catalog-named outline, `test_knowledge_base.py` 60 datasets over the production catalog, web `proxy.test.ts` trace ceiling and step route.

### DEC-162 — A browser narrows its own runtime; only the operator widens it

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code). The settings page was read-only and said so.
- Decision: `GET`/`PATCH /v1/settings`, keyed by the browser's owner key, expose two kinds of choice. (1) Restrictable capabilities — `document_upload`, `document_ocr`, `official_acquisition`, `web_search`, `web_url` — may be switched **off** for that owner's own turns and switched back on. Naming a capability the operator did not enable is refused (422), so a browser can never widen what this deployment may do; that stays the operator's command line. (2) `history_turns`, the number of earlier turns the planner is shown, between zero and the built-in ceiling. Choices are stored per owner in the conversation store and applied per turn: an upload is refused at admission, and the turn's registry leaves out the tools the owner switched off, skips acquisition and truncates the history block. A turn carries the owner's choices only when they made one, so a runtime with nothing to apply keeps its existing call.
- Reason: The operator owns the deployment's authority and the person owns their own session. Turning a capability off is always safe; turning one on is the operator's decision, and expressing it in the browser would make the browser part of the security boundary.
- Rejected: a settings page that documents flags nobody can change; browser-set model or verification switches, which would let a session weaken correctness; storing settings in the browser, where the server could not apply them.
- Tests: `test_settings_api.py` — the page lists only what this deployment offers, a capability switches off and back on and survives a reread, a capability the operator did not enable is refused, history is bounded by the ceiling, a switched-off upload is refused for that owner only, and a turn carries settings only when the owner made a choice.

### DEC-163 — A vector generation covers one catalogue, and the knowledge base can have its own

- Status: CONFIRMED team decision, 2026-09-18, by Arda (implemented with Claude Code), from reading what the knowledge page's catalogue trial actually ran.
- Findings that drove it: (1) the trial called lexical `search_catalog` while a turn calls the two-stage `search_hybrid_catalog`, so the page did not show what the agent finds; (2) the prepared runtime offered the dense stage only when the catalogue object *was* the reviewed one (`catalog is self._catalog`), so the first knowledge-base dataset or alias turned meaning-based retrieval off for every later turn, silently and with no way back; (3) nothing could build vectors again, so a user dataset's title, description and aliases were never reachable by meaning — only by word overlap; (4) the generation manifest allowed 40 rows and search output 40 candidates, so a catalogue with reviewed series plus a few user datasets could not be indexed or reported at all.
- Decision: (1) The catalogue trial runs the deployment's own retrieval — hybrid when an index is configured — and reports `retrieval_mode`, `dense_status`, `dense_failure`, the embedding model and the input policy, so a catalogue the vectors no longer cover is visible instead of quietly lexical. (2) A generation is offered to the catalogue whose **digest** it carries, reviewed or with the knowledge base applied (`_dense_for`), not to one particular object. (3) `GET /v1/knowledge/index` reports the generation in use (model, input policy, dimension, digest, coverage and the entries it is missing) and `POST /v1/knowledge/index` builds the vectors again for the catalogue in use now, with the same model, the same input policy and the same dimension — none of which the browser can choose. The build calls the embedding model once per catalogue entry, so it runs on one background thread, one at a time, and the page polls the status. Generations stay immutable and are named by the catalogue digest they cover: an earlier one is reopened rather than embedded again, and a failed build leaves the generation in use untouched. A new generation is installed for later turns only after it verifies against the catalogue it was built for; the turn already running keeps the stage it started with. (4) Row and candidate bounds are `MAX_CATALOG_SERIES`, the catalogue's own bound, not 40.
- Reason: The meaning-based stage is what makes a question in a person's own words find the right series. A knowledge base that cannot be embedded is a knowledge base the agent can only stumble on by shared words — and a retrieval that silently degrades is worse than one that says so.
- Rejected: embedding user entries into the reviewed generation (a generation covers one exact catalogue, and the reviewed digest must stay verifiable); rebuilding inside the request (minutes of embedding on the HTTP path); letting the browser choose the model, the policy or the dimension (they are the deployment's, and a mislabelled vector cannot be detected later).
- Tests: `test_knowledge_api.py` — a trial runs both stages and names them; a knowledge-base entry makes the trial report `lexical_degraded` / `snapshot_mismatch`; the vectors can be built again for the changed catalogue, after which coverage is complete, the runner's discovery uses the new generation, and the new entry is found by the hybrid trial.

### DEC-164 — A national series is the default when no place is named; a completion ceiling guards runaway generation

- Status: CONFIRMED team decision, 2026-09-19, by Arda (implemented with Claude Code), from the 2026-09-18 live `edge` run where an unqualified "konut fiyat endeksi" abstained with a four-way regional clarification (X4) and a continuation spent 7,897 reasoning tokens.
- Decision (geography): reviewed geography becomes a deterministic reranking dimension, using only the reviewed metadata and the query text — never a hand-kept list of cities. A candidate whose declared geography the question names is preferred; when the question asks for regional series generically ("bölgesel", "il bazında", "regional", …) a regional variant is preferred and the national series is demoted; otherwise a series with no declared geography, or the national series (the one country this catalog covers) the person did not name, is the neutral default, and a regional variant the person did not ask for is demoted below it. So an unqualified "konut fiyat endeksi" reads as Türkiye and does not abstain, while "İstanbul konut fiyat endeksi" and "bölgesel konut fiyat endeksi serileri" resolve to the right variants. A national series is never ranked below an ordinary placeless one.
- Decision (completion ceiling): `KLOUDEKS_MAX_OUTPUT_TOKENS` bounds the tokens one completion may generate, applied to every chat call. It is a memory/safety ceiling on runaway generation, not a latency knob: the default (16,384) is well above the most a real reasoning-plus-answer call has ever needed (7,897 reasoning tokens observed), and a value below 4,096 is refused so a legitimate call is never truncated. This follows the standing rule that a bound exists only for memory safety, never as an arbitrary small limit.
- Rejected: a hand-kept province list (the reviewed geography is enough, and the country is a single reviewed concept); a small per-call `max_tokens` that would trade correctness for latency by truncating a slow-but-correct answer; a prompt instruction to the planner to pick the national default (the harness ranks it deterministically instead of leaving it to model discretion).
- Tests: `test_catalog_ranking.py` (place-free query prefers the national series, naming a city promotes its variant, a generic regional query demotes the national one); the M13-09 quality/safety holdouts still match their recorded evidence; `test_kloudeks_provider.py` (the ceiling is sent and a value below the floor is refused).

### DEC-165 — The catalog says whether its first candidate is the default; a plan may chain a fetch and a transform; a plan that did not run whole is never ACCEPTED

- Status: CONFIRMED team decision, 2026-09-19, by Arda (implemented with Claude Code), from the E1 trace review: one question ("2021–2025 konut kredisi bakiyesini aylık getir, TÜFE ile Aralık 2025 fiyatlarına göre enflasyondan arındır.") abstained in one live run (22:46, "İstenen veri serisi bulunamadı") and was accepted with a false sentence in another (17:39). The two traces were read event by event; each finding below names the event that showed it.
- Findings: (1) `clarification_required` is true on every catalog output — it means "a candidate is never a verified selection" — and the discovery instructions told the planner never to pick the top candidate for its rank alone, so whether the planner used the obvious total balance or asked "TP mi YP mi?" was left to the model: over-abstention was non-deterministic, and the "untrusted metadata" warning every output carries was not the cause. (2) The abstained run had merged the request into a stale pending clarification about İstanbul (`turn.received: pending_clarification=true, clarification=merged`), because a new question had to end in "?" and the Turkish request is an imperative; the planner then searched İstanbul and clarified `missing_series`. (3) The accepted run planned `lakehouse` → `table_transform.deflate(source="fetch_housing")`; validation passed, the deflate step failed at run time with `workspace_reference` because `source` resolved published tables only, nothing was published, and the writer still described the raw balances as "enflasyondan arındırılmış": every number bound to the raw values, so the gate accepted a false description.
- Decision (top_candidate): every catalog result carries `top_candidate` ∈ {`unambiguous`, `ambiguous`, `none`}, computed from reviewed metadata only. `unambiguous`: the reviewed-intent order puts the first candidate strictly first and every shown candidate shares a reviewed concept or family with it. `ambiguous`: the top two tie on an axis the request did not name, or the candidates span unrelated concepts. `none`: nothing matched. The reviewed-intent order gains two defaults beside DEC-164's national-over-regional: the aggregate over its TP/YP columns when the question names no currency (a reviewed `TP`/`YP`/`TOTAL` label declares a column; a denomination in a title such as "(TL, Akım, %)" does not), and, as the last tiebreak, the newest base year over an older base of the same concept when none is named. The intent vocabulary matches the inflected Turkish forms of its core nouns as whole words ("bakiyesini", "faizini"), never stems. The planner is told what the signal means: `unambiguous` → use that candidate when its declared semantics fit the question, without asking; `ambiguous` → settle the differing axis (balance/rate, TL/FX, place, base year, scope) from the question's own words and clarify, naming that axis, only when the question does not say; `none` → clarify or say the series is not available; never clarify because a candidate is merely ranked. `clarification_required` keeps its meaning and its tests. The knowledge page's catalogue trial shows the same signal.
- Decision (a request is not a reply): after a pending clarification a message is a new request when it starts with a new-question prefix, changes the selected table, ends in "?" with at least six words, has more than nine words and more than one clause (comma or semicolon), or has more than fourteen words. A one-clause reply of ten words ("BDDK Aylık Bülten toplam bakiyeyi Mayıs-Haziran 2026 dönemi için kullan.") stays a reply. The planner's system prompt adds that a clarification which is a complete request of its own replaces the original.
- Decision (same-plan tables): a table argument (`source`, a join's `other`) names a published result or the `step_id` of an earlier step of the same plan. Given the workspace names, the validator refuses at planning time — listing the published names — a name that is neither, requires a same-plan step to be declared in `depends_on`, and refuses a discovery step or the step itself as a table; the tool then reads the declared step's result from the execution context and records it as a `step` input, the way `input_step` already is recorded. The argument descriptions say so, so the planner is told the rule rather than left to discover it by failing.
- Decision (incomplete plans): the writer receives, in its own system data turn before the question, the steps that failed or never ran, and is told not to narrate their operation as done but to say, without figures, that the operation was not applied in this turn and the values shown are the untransformed ones; and when any step did not succeed, an ACCEPTED answer is capped to QUALIFIED with the missing steps named as a limitation (a notice in the client). Publication was already refused for such turns; the answer's status now says so too.
- Reason: correctness is the elimination criterion. A deterministic default the harness can compute must not be left to a small model's discretion, and a sentence the gate cannot fault is still wrong when the operation it describes never ran.
- Rejected: redefining `clarification_required` (its "never a verified selection" meaning and twenty-plus tests); a prompt-only fix (the flag would stay always-true and the abstention would stay random); the tool silently substituting another table; a model call to classify reply versus request (the harness rule is cheap and traceable, and the planner instruction covers the remainder); stemming the intent vocabulary ("bazı", "yeniden" would become base-year and new-credit intents).
- Tests: `test_catalog_ranking.py` (reviewed defaults make the first candidate unambiguous, ties stay ambiguous, no candidates → none, inflected words carry the stem's intent, a title denomination is not a component), `test_hybrid_catalog.py` (the merged order carries the signal; the DEC-142 interleave is refined, not replaced), `test_catalog_continuation.py` (the planner's feedback carries it; the continuation prompt stays below the legacy dump), `test_knowledge_api.py` (the trial shows it), `test_new_question_detection.py` (the reply/request table and the E1 turn sequence), `test_same_plan_tables.py` (validator messages; the tool reads a declared step; a fetch-then-rebase turn publishes), `test_incomplete_plan.py` (a failed deflate reaches the writer as a note, the answer is QUALIFIED, nothing is published). The M13-09 quality and safety holdouts still match their recorded evidence.

## Proposed decisions

Candidates below are not approved selections. Compare options in a bounded task; do not silently promote a proposal to CONFIRMED.

| ID | Proposal | Alternatives / evidence needed | Owner | Next action |
| --- | --- | --- | --- | --- |
| PROP-01 | RESOLVED by DEC-113 | Custom bounded loop selected; LangGraph and other frameworks rejected | Eray | None; implement in M5 |
| PROP-02 | RESOLVED by DEC-112 | DuckDB with Parquet and Pandas selected; Polars rejected | Eray | None; implement in M12 |
| PROP-03 | RESOLVED by DEC-123 | FastAPI with SSE behind Next.js selected; Streamlit retained as a recorded fallback | Eray | None; implement in M10 |
| PROP-04 | PROPOSED: retry and latency budgets | Exact counts/timeouts depend on platform limits and baseline measurements | Unassigned | Obtain Q-K-04 and measure before fixing limits |
| PROP-05 | RESOLVED by DEC-120 | Lagged correlation and Granger with mandatory stated limits; stronger identification rejected for this data | Eray | None; implement in M6 |
| PROP-06 | RESOLVED by DEC-134: provider abstraction approved | Concrete production adapter deferred; live acceptance still blocked | Çağatay | M7-22 offline implementation, then separately triaged production acceptance |
| PROP-07 | RESOLVED by [DEC-142](#dec-142--catalog-query-embedding-policy-and-reviewed-match-combination) | Model-card query policy `qwen3-instruct-query-v1` selected from M13-09 evidence; Q-K-05 still unanswered | Eray | Wire into the prepared runtime (M13-05) |
| PROP-08 | RESOLVED by [DEC-142](#dec-142--catalog-query-embedding-policy-and-reviewed-match-combination) | Reviewed-match order selected; gain claim requires the fresh holdout | Eray | Evaluate on development and the fresh holdout (M13-06) |

### Web search provider decision (M7-21)

Historical proposal: PR #113 initially required a named provider and official API contract before M7-22. Çağatay explicitly replaced that prerequisite with [DEC-134](#dec-134--provider-neutral-web-search-with-mandatory-live-acceptance): approve the provider abstraction now, defer the real adapter to a separately authorized production acceptance task. No provider, endpoint, auth scheme, credential presence or quota is implied. Live production search remains NOT RUN / BLOCKED; Q-NET-01/02 are not resolved.

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


## Open Questions

Active unresolved questions, including partially answered entries with their remaining scope. Fully answered records are preserved separately; question IDs and provenance are unchanged.

<a id="open_questions-actionable-open-questions"></a>

### Actionable open questions

This file owns unresolved external/team questions and their evidence. [DECISIONS](DECISIONS.md) owns confirmed choices; [ROADMAP](ROADMAP.md) owns blocked/ready tasks. A temporary assumption is a planning aid, not organizer permission or an implementation fact.

Snapshot: 2026-09-10. Two organizer **primary documents** were reviewed on this date: the kick-off deck of 7 September 2026 and the `MIA · Hackathon Rehberi` integration guide received over Slack, together with the team's MIA API key. [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) owns the brief's schedule/delivery/demo-input constraints and the 2026-09-10 amendment to [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the literal OCR/embedding request contracts. Q-DEMO-01, Q-INFRA-01, Q-NET-02, Q-DATA-01 and Q-DEV-02 gained real evidence below and are narrowed rather than closed. **Q-DEV-01 is ANSWERED (2026-09-10): coding assistants are permitted as development tools, and the Kloudeks-only runtime restriction is unaffected.** The five team-decision questions Q-TEAM-01 through Q-TEAM-05 are **ANSWERED** by M0-ARCH and recorded in DECISIONS; those five choices are no longer blockers. Task-level proof/result schemas, reviewed concept-family membership and measured thresholds remain proposals until reviewed; they do not reopen those answered questions. Official Kloudeks integration information relayed by Çağatay on 2026-09-09 answers endpoint/authentication, model availability and image-input limits; [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the exact capability contract. Q-K-01/02/05 are narrowed below. Other organizer categories have no newly recorded answers and remain open; suggested lanes are not assignments.

The organizer questions are now the project's only external blockers, and several of them gate long-lead work: unexercised OCR access (Q-K-01), capacity (Q-K-02/04) and capability guarantees (Q-K-03) constrain their respective live acceptance. Ordinary compatible text transport can be built against the confirmed contract with local schema validation; no native tool/JSON guarantee is needed for that path. Q-K-05 retains configuration questions for the now-required dense baseline and optional dedicated-reranker availability under DEC-130 (DEC-127/115 are SUPERSEDED); Q-NET-01/02 gate the `web_search` and `web_url` tools, Q-DATA-01 gates live source retrieval, and Q-INFRA-01 can override DEC-126. Ask them early rather than near the delivery date.

<a id="open_questions-dec-137-unresolved-materialization-and-storage-policy"></a>

### DEC-137 unresolved materialization and storage policy

[DEC-137](DECISIONS.md#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) records team architecture direction, not organizer answers. The original dated organizer evidence below is preserved. Still unresolved: Q-INFRA-01/02 (Kloudeks/demo S3-compatible object-storage availability, persistent-volume lifetime, credentials/runtime access); Q-DATA-01/03 (source-use, redistribution and retention); Q-NET-01 with Q-DATA-01 (demo egress and whether on-demand official BDDK/EVDS materialization is permitted); Q-NET-01/02 and the M7 production record (SearXNG/upstream search policy); Q-DATA-04 (authoritative semantics/revisions). No AWS/S3 provider is selected. Vector product choice is answered by DEC-138; remaining embedding-policy questions are Q-K-05. No live acceptance is implied.

The [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes the broad prepared pool demo-critical and question-time official materialization a later extension. Preparation permission, trusted identity/semantics and minimum revision-conflict safeguards still matter now; unresolved runtime official-fetch permission and sophisticated vintage/index/object-storage scaling are not core three-turn prerequisites. This is team priority, not a new organizer answer.

Internal questions Q-TEAM-07/08 below concern exact broader prepared coverage and refresh/vintage selection policy. These are team decisions, not organizer permissions; [Q-TEAM-06](DECISIONS.md#history-q-team-06--vector-cacheindex-implementation) is answered by DEC-138 (LanceDB), Q-TEAM-07/08 remain OPEN. Known embedding dimension is 4096 from M4-12; no new live call is needed to re-establish it.

Fully answered Q-DEV-01 and Q-TEAM-01..06 are preserved in [HISTORY](ROADMAP.md#history-historical-handbacks-and-answered-questions); partially answered questions stay here with their remaining scope.

<a id="open_questions-how-to-use-this-list"></a>

### How to use this list

- Claim the relevant question, obtain an answer, and record a dated message/document/reference without secrets or private payloads.
- Check a question only when the answer/evidence is recorded and its affected roadmap blockers are updated. A question being sent is not a resolved question.
- `Can we proceed before answer?` applies to the **blocked slice named in that entry**. Independent synthetic work may still proceed even when the answer is NO.
- Use Status: OPEN, WAITING (asked, no answer), ANSWERED, or DEFERRED. Add actual owner and next follow-up date when someone accepts the question; no automated messaging is implied.
- Once fully answered, preserve the complete question/evidence in HISTORY and link its decision; remove it from this active list.
- Do not ask organizers for every internal implementation preference. The team-decision section is resolved by teammates and recorded as an ADR.

<a id="open_questions-priority-queue"></a>

### Priority queue

| Priority | Questions | Why now | Independent work while waiting |
| --- | --- | --- | --- |
| Ask on Slack now | Q-NET-02, Q-DATA-01, Q-NET-01 | URL/source permission gates the confirmed demo-day capability and live source retrieval | Safe-fetch boundary, parsers, offline provider/tool integration |
| First available organizer contact | Q-K-02/03/04, Q-DATA-02, Q-DEMO-01 | Determine capacity, guarantees and remaining demo format | Synthetic contracts/oracles, conservative local budgets |
| Remaining model configuration | Q-K-01 OCR access; Q-K-05 prefix/batch/token limits | Chat/embedding smoke and 4096 dimension already measured in M4-12; do not repeat as an unresolved dimension question | Offline bounded contracts; separately authorized live acceptance where still needed |
| Before private data or deployment | Q-DATA-03, Q-INFRA-01/02, Q-COMP-01, Q-DEMO-02/03 | Determine retention, environment, session/fallback rules | Credential-free unit tests, operator-flow design |
| Before final scope/experiments | Q-K-04/05, Q-DEV-02, Q-JUDGE-01/02, Q-COMP-02, Q-DATA-04 | Avoid unsupported tooling/scoring/resource assumptions | Core deterministic baseline |
| ~~Before affected implementation choice~~ | Q-TEAM-01/02/03/04/05 — **ANSWERED 2026-09-09** | Resolved by M0-ARCH; see DEC-112, DEC-113, DEC-117, DEC-120, DEC-123 | No longer blocking; implementation may proceed |

<a id="open_questions-kloudeks"></a>

### Kloudeks



<a id="open_questions-q-k-01--endpoint-authentication-and-credential-delivery"></a>

#### Q-K-01 — Endpoint, authentication, and credential delivery

- [x] Record the official endpoint, MIA-key authentication and compatible-client contract in [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy).
- [x] Obtain the team's MIA API key. Delivered over Slack on 2026-09-10 and stored **only** in the operator-local, git-ignored `.env`. The key value is not recorded here, in DECISIONS, or anywhere in Git.
- [x] Exercise one authorized live request to prove the key actually authenticates against the confirmed endpoints; never record the key itself. Done for chat and embedding on 2026-09-11 (M4-12, DEC-129); OCR not called.
- Remaining question: none. The OCR model (`kkbhackathon2026/Unlimited-OCR`) is reachable on this account: the owner-authorized probe on 2026-09-17 returned three complete OCR responses ([evidence](EVALUATION.md#q-k-01-ocr-probe-2026-09-17)). Chat and embedding authenticated in the 2026-09-11 smoke.
- Why it matters: Possessing a key is not proof of access. Per DEC-129 a `401`/`403` would mean an invalid key, a model this account cannot reach, or a mis-cased model identifier — three different failures that only a live call distinguishes.
- Blocks which milestone? M4-12 live smoke and M11 live demo access; no longer the endpoint/auth design of M4-07.
- Can we proceed before answer? YES for bounded transport implementation and fake-transport tests; NO for claiming live authentication passed.
- Temporary assumption: Use only the confirmed Kloudeks destination and the operator-supplied secret; no hosted fallback under any error, including `429`.
- Owner: Unassigned; the live smoke is M4-12 work and needs explicit authorization, not a side effect of another task.
- Status: ANSWERED — endpoint/auth/SDK, key provisioning, live chat/embedding authentication (2026-09-11) and OCR access (2026-09-17). OCR text still becomes no cell without DEC-119 validation.
- Answer / evidence: Official guidance relayed by Çağatay 2026-09-09, verified against the primary MIA guide 2026-09-10; DEC-129. Key provisioned 2026-09-10. Live smoke 2026-09-11 11:35 +0300 (M4-12, explicitly authorized): chat and embedding succeeded through the M4-07 transport; no key or model text recorded.

<a id="open_questions-q-k-02--available-models-and-context-capacity"></a>

#### Q-K-02 — Available models and context capacity

- [x] Record exact main chat/text/vision, embedding and OCR model IDs plus confirmed image-count limits in [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy).
- [ ] Record context window and general maximum output tokens beyond example-specific values. The primary guide's only figure is the OCR example's `max_tokens=8192`, which is an example setting rather than a documented ceiling.
- Remaining question: What context/output-token capacity applies to each confirmed model? Example settings are not guaranteed maxima.
- Why it matters: Bounded prompts and output budgets must fit the platform; availability is not a capacity measurement.
- Blocks which milestone? M4/M5 validated context sizing and M11 capacity claims, not model-ID selection or offline integration.
- Can we proceed before answer? YES using confirmed IDs and conservative configurable local budgets; NO for promising undocumented limits.
- Temporary assumption: Use the documented image counts; do not infer token limits, a cheaper router model or native tool/JSON support.
- Owner: Unassigned; suggested lane B.
- Status: OPEN only for remaining capacity; model availability and listed image limits ANSWERED.
- Answer / evidence: Official guidance relayed by Çağatay, 2026-09-09; DEC-129. General context/output limits were not supplied.

<a id="open_questions-q-k-03--structured-output-and-tool-calling"></a>

#### Q-K-03 — Structured output and tool calling

- [ ] Record native function/tool calling, JSON-schema support, and response-format behavior.
- Question: Does Kloudeks expose native tool calling or guaranteed structured JSON, and which schema features/error responses are supported?
- Why it matters: Determines provider parsing/repair approach without weakening local validation.
- Blocks which milestone? Enabling native function/tool calling or guaranteed structured-output mode in M4/M5; does not block ordinary text requests with strict local parsing/repair.
- Can we proceed before answer? YES for the confirmed compatible text transport with strict local schemas and malformed-output fixtures; NO for asserting or relying on native tool/JSON guarantees.
- Temporary assumption: No guarantee of native structured output; model results must validate locally in all cases.
- Owner: Unassigned; suggested lane B.
- Status: OPEN.
- Answer / evidence: DEC-129 confirms OpenAI-compatible transport, not native function/tool calling or guaranteed JSON/JSON-schema. The primary guide's `vllm_xargs` parameter shows a vLLM-based server behind the endpoint — an **observation about the stack, not a capability guarantee**. vLLM builds commonly expose guided decoding, but nothing organizer-supplied states that this deployment enables it, so `structured_output` stays false and the local repair loop stays the default. Probing it is a question for Slack or an authorized live smoke, not an inference.

<a id="open_questions-q-k-04--quotas-timeouts-and-retry-behavior"></a>

#### Q-K-04 — Quotas, timeouts, and retry behavior

- [x] Record the documented error semantics: `401`/`403` for an invalid key or unreachable/mis-cased model, `429` for a rate or quota limit, with the guide directing a wait per the error message or a question to the organizer team (DEC-129, 2026-09-10 amendment).
- [ ] Record the actual request/token/concurrency limits, timeouts, and permitted retry behavior behind that `429`.
- Question: What rate/token/request limits, timeouts, concurrency rules, and retry guidance apply during development and the demo? Knowing that `429` exists does not give a number to budget against.
- Why it matters: Exact attempt/deadline budgets and latency expectations need real constraints.
- Blocks which milestone? M4 transport budgets; M5 bounded live loop; M9 live latency thresholds; M11 capacity rehearsal.
- Can we proceed before answer? YES for configurable bounded behavior and offline tests; NO for claiming quotas or a validated live SLA.
- Temporary assumption: Use conservative configurable limits in later implementation, measure them, and do not assume unlimited calls.
- Owner: Unassigned; suggested lane B with C measurement.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-q-k-05--embeddings-and-rerankers"></a>

#### Q-K-05 — Embeddings and rerankers

- [x] Record the official embedding model and endpoint in [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy).
- [x] Record the literal embedding request shape: `/v1/embeddings` with `encoding_format="float"`, a single-string `input` in the official example, vector read from `data[0].embedding` (DEC-129, 2026-09-10 amendment).
- [x] Measure the vector dimension: **4096**, from the first authorized live call (2026-09-11, M4-12; DEC-129).
- [ ] Resolve the query/passage prefix convention, batch/token limits and whether a dedicated reranker is available.
- Remaining question: What are those embedding configuration/limit details, and can a dedicated reranker be provided? General request/rate/concurrency limits remain Q-K-04.
- Why it matters: Availability alone does not define a valid index/configuration or establish retrieval quality.
- Blocks which milestone? M13-05 dense-baseline configuration (remaining prefix/limits; dimension 4096 established) and optional dedicated-reranker use under M13-07. Lexical work, contracts and offline benchmark design can proceed; full hybrid acceptance requires both retrieval paths. Dense use itself is confirmed by DEC-130, not gated on lexical failure.
- Can we proceed before answer? YES for lexical work and hybrid contracts/benchmark design; use the measured 4096 dimension and do not invent prefix values or claim complete hybrid integration while those prerequisites remain unresolved.
- Temporary assumption: Keep DEC-130's mandatory lexical+dense baseline and measured activation policy for RRF/reranking/extra stages. Do not copy an E5 prefix convention onto the confirmed Qwen model. The supplied list's omission of a dedicated reranker is not proof one can never be offered.
- Owner: Unassigned; suggested lane B.
- Status: OPEN only for remaining embedding details/dedicated reranker; embedding availability ANSWERED.
- Answer / evidence: Official guidance relayed by Çağatay, 2026-09-09; DEC-129. Dimension measured as 4096 on 2026-09-11 (M4-12). No prefix convention or dedicated-reranker answer supplied. M13-09 (2026-09-15) showed batched `input` lists of 16 passages work (37 passages in 3 requests, about 1.8 s) and measured two local query policies (PROP-07); a fresh holdout in M13-05 (#179) confirmed the instruct query policy (dense hit@1 0.842 vs 0.737), now selected by DEC-142 for the prepared runtime. This is an internal measurement, not the platform's answer.

<a id="open_questions-organizer-infrastructure"></a>

### Organizer infrastructure



<a id="open_questions-q-infra-01--runtimedeployment-environment"></a>

#### Q-INFRA-01 — Runtime/deployment environment

- [x] Record the delivery form and the demo-day runtime expectation: teams develop in their own environment, keep code in a **private GitHub repository** and deliver by granting KKB access; on Final Day a **solution deployed and running live** is expected (DEC-131).
- [ ] Record OS/runtime/container/port/storage constraints for that live deployment, and who hosts it.
- Question: The brief requires a live deployed solution but names no hosting environment. Do we host it ourselves, and what OS, Python/package installation, container, port and filesystem restrictions apply? Is S3-compatible/object storage available in Kloudeks/the demo environment; what credentials and runtime access model apply? No vendor or AWS S3 selection is inferred.
- Why it matters: Determines reproducible setup, parser availability, and UI delivery. "Deployed and live" is now a confirmed requirement rather than an assumption, which makes the hosting answer more urgent, not less.
- Blocks which milestone? M0 final setup validation, M10 deployment choice, M11 rehearsal environment.
- Can we proceed before answer? YES for local Python >=3.12 contracts/tests and for the DEC-126 single-VM target; NO for claiming deployment compatibility with an unstated environment.
- Temporary assumption: We provide the host ourselves under DEC-126 until told otherwise; no GPU requirement is inferred. DEC-126 yields to an organizer-supplied environment if one is named.
- Owner: Unassigned; suggested lane B / organizer liaison.
- Status: OPEN for environment/hosting constraints; delivery form and the live-deployment requirement are ANSWERED.
- Answer / evidence: Kick-off deck, 7 September 2026, reviewed 2026-09-10; DEC-131.

<a id="open_questions-q-infra-02--storage-lifetime-and-isolation"></a>

#### Q-INFRA-02 — Storage lifetime and isolation

- [ ] Record local disk limits, reset behavior, persistence lifetime, and private-data cleanup requirements.
- Question: What survives process restart, demo questions, or session reset, and what storage/cleanup/isolation requirements apply? Are persistent volumes available, and what are their lifetime/size/durability guarantees for versioned official datasets versus session artifacts?
- Why it matters: Workspace semantics must match actual retention/durability expectations.
- Blocks which milestone? M5 persistence acceptance, M10 reset/session behavior, M11 cleanup/restart demonstration.
- Can we proceed before answer? YES for explicit in-process state and synthetic tests; NO for promised restart durability/private retention.
- Temporary assumption: The merged workspace persists definition/binding/history tables, but result durability, cleanup and cross-session retention are not established. Do not commit or retain organizer data based on an assumption.
- Owner: Unassigned; suggested lane B with C operator requirements.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-datasets"></a>

### Datasets



<a id="open_questions-q-data-01--bddkevds-and-provided-source-access"></a>

#### Q-DATA-01 — BDDK/EVDS and provided source access

- [x] Record the brief's named source scope: BDDK `Haftalık Bülten`, `Aylık Bülten` and `FinTürk - İllere Göre`, plus EVDS `tumSeriler`, all bounded to **January 2021 – June 2026** (DEC-131). BDDK is described as weekly/monthly and EVDS as daily/weekly/monthly, matching the [BDDK](BDDK_SOURCE.md) and [EVDS](EVDS_SOURCE.md) inventories.
- [ ] Record approved access/formats, access requirements, and source-use permissions. A named dataset is not granted access.
- Question: How may initial/broad BDDK/EVDS preparation, incremental refresh and on-demand official materialization for trusted catalog misses access official sources? Is demo-time official fetch permitted, with what rates/retention restrictions, and which metadata/revision conventions are authoritative? DEC-137 keeps prepared data as the hot path; it does not grant these permissions.
- Why it matters: Scoped ingestion adapters and semantic mappings require confirmed inputs; familiar source names do not prove access.
- Blocks which milestone? M3 official-source preparation and semantic acceptance; M11 representative analysis of the prepared official dataset.
- Can we proceed before answer? NO for source-specific live acceptance; YES for generic ingestion and synthetic source-shaped fixtures.
- Temporary assumption: BDDK/EVDS are confirmed intended sources but not the only possible ones; the brief also requires reading arbitrary prompt-supplied URLs (Q-NET-02). PR #21/#22 source inventories record observed endpoints/series metadata, not organizer-approved runtime access or redistribution. Do not invent missing request payloads, permissions or auth requirements. The 2021-01 – 2026-06 window is a scope bound, not a permission.
- Owner: Unassigned; suggested lane A.
- Status: OPEN for access permission; the named source list and date window are ANSWERED.
- Answer / evidence: Kick-off deck, 7 September 2026, reviewed 2026-09-10; DEC-131. No access or redistribution permission recorded.

<a id="open_questions-q-data-02--hidden-formats-schema-variation-and-size"></a>

#### Q-DATA-02 — Hidden formats, schema variation, and size

- [ ] Record required file formats, maximum sizes, languages/encodings, and expected schema variation.
- Question: Can hidden inputs contain CSV/XLSX/multi-sheet workbooks, HTML, PDF/scanned PDF, images, unknown schemas, or unusually large files?
- Why it matters: Defines required parsers, limits, OCR scope, and adversarial coverage.
- Blocks which milestone? M1/M7 final format scope, M9 required coverage, M11 support claims.
- Can we proceed before answer? YES for bounded CSV/XLSX baseline and explicit unsupported-format behavior; NO for claiming full hidden-format coverage.
- Temporary assumption: CSV/XLSX first; PDFs with a text layer are extracted offline (M7-09), HTML is planned. Vision/OCR availability is confirmed by DEC-129; required input scope and safe document/OCR implementation remain separate questions. All enabled parsers need tested limits.
- Owner: Unassigned; suggested lane A with C coverage.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-q-data-03--caching-retention-and-redistribution"></a>

#### Q-DATA-03 — Caching, retention, and redistribution

- [ ] Record permitted local cache/retention/export/fixture use and cleanup requirements.
- Question: May organizer datasets and derived results be cached locally, included in a demo fallback, exported, or committed/shared, and for how long?
- Why it matters: Determines legal/organizer permission for data handling and fallback artifacts; permission cannot be inferred from access.
- Blocks which milestone? M1 private storage, M3/M7 cache, M10/M11 fallback/exports, SEC-DATA-01.
- Can we proceed before answer? NO for private retention/redistribution/fallback use; YES with synthetic fixtures and explicitly permitted public-safe data.
- Temporary assumption: Do not commit organizer/private data or assume cache/fallback permission. Team policy ([DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git), 2026-09-14): prepared official BDDK/EVDS data stays in ignored operator-local roots and ships through deployment, never Git; this is not an organizer answer.
- Owner: Unassigned; suggested lane A / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded; link the actual permission and scope when received.

<a id="open_questions-q-data-04--authoritative-semantics-and-revisions"></a>

#### Q-DATA-04 — Authoritative semantics and revisions

- [ ] Record who resolves missing/conflicting units, stock-flow/reset rules, and historical revisions.
- Question: Is an authoritative data dictionary/release vintage supplied, and how should we handle missing semantics or contradictory revised observations during judging?
- Why it matters: Prevents silently selecting a convenient interpretation to produce a number.
- Blocks which milestone? M2/M3 disputed source mappings; M9 oracle adjudication.
- Can we proceed before answer? YES with explicit unknowns and hand-specified synthetic semantics; NO for unsupported source-specific conversions.
- Temporary assumption: Preserve unknowns and vintages; clarify/abstain where required meaning is missing.
- Owner: Unassigned; suggested lane A with C oracle review.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-external-internet--network"></a>

### External internet / network



<a id="open_questions-q-net-01--demodevelopment-internet-access"></a>

#### Q-NET-01 — Demo/development internet access

- [ ] Record outbound network, DNS, proxy, firewall, and package-install access for each environment.
- Question: Is internet access available to the application during development and demo, and through which DNS/proxy/firewall restrictions? Does demo egress permit policy-bounded official BDDK/EVDS cache-miss materialization, and which upstream engines may a self-hosted search backend contact? Self-hosting alone does not answer privacy/egress policy.
- Why it matters: Live retrieval/provider setup and reproducibility depend on actual connectivity.
- Blocks which milestone? M3/M4/M7 live paths and M11 network rehearsal.
- Can we proceed before answer? NO for promised live-source availability; YES for offline tools and fake transports.
- Temporary assumption: No guaranteed external internet; do not enable an unrestricted fallback fetch path.
- Owner: Unassigned; suggested lane B / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-q-net-02--allowed-external-source-urls"></a>

#### Q-NET-02 — Allowed external source URLs

- [x] Record that reading **prompt-supplied URLs is a required demo-day capability**, not an optional extra: on Final Day URLs are handed to the system inside the prompt and meaning must be extracted from PDF, Excel, image and text content there. The brief illustrates this with the `borsaistanbul.com` precious-metals market-data page (values from its gold-transactions PDF) and the `xtumy` index page (BIST 100 daily/monthly change) (DEC-131).
- [ ] Record whether arbitrary public URLs are permitted or an organizer-approved allowlist applies, including redirect destinations.
- Question: The requirement to read prompt-supplied URLs is confirmed, but its boundary is not. May the app fetch any public HTTP(S) address, or only approved domains?
- Why it matters: Product capability policy is additional to technical SSRF protection. The two named pages are **examples of a capability, not an allowlist and not a promise those URLs appear** — building only for them would fail an unseen address on the day.
- Blocks which milestone? M7 live retrieval exposure and M11 supported-source claims; M3 source access is Q-DATA-01.
- Can we proceed before answer? YES for the safe-fetch boundary, parsers and negative tests, which are now clearly required work; NO for enabling unrestricted fetching in a delivered build.
- Temporary assumption: Build for an arbitrary public HTTPS address behind the M7 safe-fetch boundary, keep the enable switch operator-controlled, and never relax the private/metadata/loopback blocks. Do not hard-code the two example URLs into the product.
- Owner: Unassigned; suggested lane B with A source needs.
- Status: OPEN for the permission boundary; the capability requirement itself is ANSWERED.
- Answer / evidence: Kick-off deck, 7 September 2026, reviewed 2026-09-10; DEC-131.

<a id="open_questions-demo-format"></a>

### Demo format



<a id="open_questions-q-demo-01--timing-format-and-user-interaction"></a>

#### Q-DEMO-01 — Timing, format, and user interaction

- [x] Record the event dates and the real preparation window: kick-off **7 September 2026**; online development over Slack **7–20 September 2026**; top-10 announcement **5 October 2026**; **Final Day 17 October 2026** with jury presentations (DEC-131). The development deadline is **20 September**, not the informal "8–9 day" window previously assumed.
- [ ] Record demo duration, the required interface, and who enters the questions on Final Day.
- Question: How long is each team's slot, and will judges operate the app themselves, upload files, or ask live follow-ups?
- Why it matters: The dates are now fixed, so the remaining unknowns are interaction and latency budgets. Two separate gates exist: the **repository reviewed after 20 September** and the **live demo on 17 October** — work that only serves the second must not displace the first.
- Blocks which milestone? M10 UI/delivery acceptance and M11 timed rehearsal; the schedule itself is no longer provisional.
- Can we proceed before answer? YES for backend/flow specification; NO for final demo-format assumptions.
- Temporary assumption: Prepare one clear analysis/evidence/follow-up path operable by someone who did not build it, since the brief says teams produce output from inputs handed to them on the day.
- Owner: Unassigned; suggested lane C.
- Status: OPEN for demo format/interaction; dates and the preparation window are ANSWERED.
- Answer / evidence: Kick-off deck, 7 September 2026, reviewed 2026-09-10; DEC-131.

<a id="open_questions-q-demo-02--multi-turn-state-and-reset-semantics"></a>

#### Q-DEMO-02 — Multi-turn state and reset semantics

- [ ] Record whether state persists between questions, users, runs, or restarts, and how reset is expected to work.
- Question: What exactly is retained between demo turns, and must the system restore an analysis after process restart or user change?
- Why it matters: Explicit workspace state is required, but durable storage may not be.
- Blocks which milestone? M5/M10 final session/persistence behavior; M11 operator reset/restart script.
- Can we proceed before answer? YES for same-session explicit workspace; NO for a claim of required/working restart persistence.
- Temporary assumption: Preserve same-workspace analytical state; do not promise cross-session durability.
- Owner: Unassigned; suggested lane C with B implementation.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-q-demo-03--permitted-fallback-and-demonstration-assets"></a>

#### Q-DEMO-03 — Permitted fallback and demonstration assets

- [ ] Record whether local fixture/cache fallback, recorded screens, or preloaded data are permitted and how they must be labeled.
- Question: What fallback is allowed if live source/provider access fails, and which prepared demo assets may be used?
- Why it matters: Reliable recovery must remain honest about live versus synthetic/cached behavior.
- Blocks which milestone? M10 fallback UI and M11 outage rehearsal acceptance.
- Can we proceed before answer? NO for treating prepared assets as an approved demo fallback; YES for synthetic development/recovery tests.
- Temporary assumption: No silent fixture substitution or claim that a cache is live; no presumed fallback permission.
- Owner: Unassigned; suggested lane C.
- Status: OPEN for fallback permission. DEC-136 distinguishes prepared official observations from replacing real on-day analysis with prepared answers or fixtures.
- Answer / evidence: The kick-off deck requires running the real scenario on Final Day and producing output from **inputs supplied on the day**, from a live deployed solution (DEC-131). The original review treated this as evidence against prepared-asset substitution. DEC-136 clarifies that a prepared official observation dataset is the intended normal analytical input, not a canned-answer/recorded-screen/synthetic substitute. The brief does not settle outage fallback permission, so the question stays open. Coordinate data permission with Q-DATA-03.

<a id="open_questions-allowed-development-tooling"></a>

### Allowed development tooling



<a id="open_questions-q-dev-02--external-tools-libraries-and-code-disclosure"></a>

#### Q-DEV-02 — External tools, libraries, and code disclosure

- [x] Record the stated technology expectations: **Python is the main development language** with no second backend language unless specifically needed, the frontend framework is free, **open-weights** models are expected (the deck names Qwen, Mistral, gpt-oss, Kimi) and **open-source libraries** are expected, with `pypdf`, Pandas, DuckDB, Plotly and LanceDB named explicitly (DEC-131). This corroborates the existing DEC-112/124/130 stack and authorizes no new dependency.
- [ ] Record restrictions on packages, development-time internet/tools, external services, and required attribution/disclosure.
- Question: Are there restrictions on third-party libraries, development services, pre-existing code, or generated assets beyond the known runtime constraints? "Open-source libraries are expected" is an expectation, not a published allowlist.
- Why it matters: Avoid adopting tooling/assets that cannot be used in the submitted product.
- Blocks which milestone? M0 setup policy, optional M7 extraction dependencies, M10 assets, M11 submission review.
- Can we proceed before answer? YES with the existing minimal declared stack and explicit hard constraints; NO for claiming unrestricted additional tooling permission.
- Temporary assumption: Add no speculative service dependency; record concrete package needs and ask before assuming event allowance. Prefer the explicitly named libraries where they fit, since they are known-acceptable.
- Owner: Unassigned; suggested organizer liaison with B technical input.
- Status: OPEN for restrictions/disclosure; language and library/model expectations are ANSWERED.
- Answer / evidence: Kick-off deck, 7 September 2026, reviewed 2026-09-10; DEC-131.

<a id="open_questions-scoring--judging"></a>

### Scoring / judging



<a id="open_questions-q-judge-01--rubric-and-unsupported-answer-handling"></a>

#### Q-JUDGE-01 — Rubric and unsupported-answer handling

Known qualitative criteria: [DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria) records Çağatay's 2026-09-14 organizer relay: development assistants allowed; allowed open-weight/Kloudeks runtime only; own harness with minimal model dependence; cross-domain genericity; own lakehouse rather than managed substitution; no committed secrets even in private Git; chained table preservation and intended-result continuation. No transcript-independent verification or scoring weights are claimed. The quantitative rubric below remains open.

- [ ] Record scoring weights, required use cases, numeric tolerances, and treatment of clarification/abstention/causality.
- Question: How are correctness, evidence, recovery, latency, UI, and unsupported/causal answers scored, and are hidden-case categories or tolerances specified?
- Why it matters: Determines final acceptance thresholds and rational scope cuts without gaming unknown criteria.
- Blocks which milestone? M9 final score thresholds and M11 go/no-go criteria.
- Can we proceed before answer? YES with category-based correctness metrics; NO for claiming organizer score thresholds.
- Temporary assumption: Prioritize correct, traceable results and honest abstention; do not invent weights or required pass percentages.
- Owner: Unassigned; suggested lane C.
- Status: OPEN.
- Answer / evidence: Qualitative criteria relayed by Çağatay are recorded in DEC-141; numerical weights/tolerances and a complete rubric remain unconfirmed.

<a id="open_questions-q-judge-02--submission-and-development-history-evidence"></a>

#### Q-JUDGE-02 — Submission and development-history evidence

- [ ] Record deliverables, repository visibility/access, history/review expectations, and submission deadline.
- Question: Which source/history/PR/benchmark/demo artifacts must be submitted, and how will development progression be reviewed?
- Why it matters: The team-reported review expectation needs an actionable submission contract.
- Blocks which milestone? M0 remote-sharing setup and M11 final submission/release packaging.
- Can we proceed before answer? YES with coherent local changes and safe records; NO for assuming publication/access requirements.
- Temporary assumption: Keep history understandable; no automatic commit/push/merge or private-data disclosure.
- Owner: Unassigned; suggested lane C / organizer liaison.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-compute--resources"></a>

### Compute / resources



<a id="open_questions-q-comp-01--provided-machine-and-resource-limits"></a>

#### Q-COMP-01 — Provided machine and resource limits

- [ ] Record CPU/RAM/disk/GPU availability and whether the team must use its own machine.
- Question: Will organizers provide a machine/GPU or require team hardware, and what CPU/RAM/disk/concurrency limits apply?
- Why it matters: Determines parser limits, local setup, and realistic latency/rehearsal conditions.
- Blocks which milestone? M0 environment acceptance, M7 resource limits, M10/M11 deployment/rehearsal.
- Can we proceed before answer? YES for bounded CPU-friendly baseline; NO for claiming resource compatibility or assuming a GPU.
- Temporary assumption: No dedicated GPU or distributed infrastructure; measure on the actual environment when known.
- Owner: Unassigned; suggested lane B.
- Status: OPEN.
- Answer / evidence: None recorded.

<a id="open_questions-q-comp-02--optional-traininginference-experiment-budget"></a>

#### Q-COMP-02 — Optional training/inference experiment budget

- [ ] Record permitted compute/time/quota for optional fine-tuning or retrieval experiments if a measured need appears.
- Question: If a baseline reveals a routing/retrieval weakness, are local training or additional inference experiments permitted and resourced?
- Why it matters: Prevents speculative fine-tuning work from consuming the delivery window.
- Blocks which milestone? Optional enhancements only; no baseline milestone.
- Can we proceed before answer? YES.
- Temporary assumption: No fine-tuning pipeline, vector infrastructure, or additional model topology is allocated by default.
- Owner: Unassigned; suggested lane B with C benchmark evidence.
- Status: OPEN; experiments DEFERRED until justified.
- Answer / evidence: None recorded.

<a id="open_questions-internal-team-choices--resolve-with-evidence-not-organizer-guesses"></a>

### Internal team choices — resolve with evidence, not organizer guesses



<a id="open_questions-q-team-07--broad-prepared-coverage-target"></a>

#### Q-TEAM-07 — Broad prepared coverage target

- Question: Which additional BDDK Monthly/Weekly/FinTürk and EVDS financial families, selectors, periods and coverage thresholds fit the deadline and source permissions after the first four-series vertical slice?
- Constraints: Approximately 2021-01–2026-06 is the initial analysis window; broader structured financial coverage must have trusted identity/semantics. Do not promise every source record or guess unsupported calendars/units.
- Owner: Unassigned. Status: OPEN. Blocks a claimed broad dataset acceptance scope, not the bounded first reusable adapter design.
- Evidence needed: reviewed catalog inventory, access/retention permission, measured ingestion/storage budget and independent coverage acceptance. No new task or READY state assigned.

<a id="open_questions-q-team-08--refresh-and-vintage-selection-policy"></a>

#### Q-TEAM-08 — Refresh and vintage selection policy

- Question: How should users/analyses select dataset versions when new periods, historical corrections, metadata or retirement/archive changes arrive, and what constitutes an idempotent no-op?
- Constraints: Same official content/selector/parser/semantic policy must be reproducible; preserve prior snapshots/versions and never silently overwrite trusted evidence. Source-authoritative interpretation still depends on Q-DATA-04; retention on Q-DATA-03.
- Owner: Unassigned. Status: OPEN. Blocks sophisticated M3/M12 version-selection/refresh acceptance, not a fixed validated prepared-pool demo with immutable snapshots and explicit conflict refusal. No scheduler is required or selected.
- Evidence needed: explicit content-version/manifest policy, revision/conflict fixtures, publication-failure preservation and requested-window behavior. Existing storage does not settle these decisions.


## Answered question records

Historical records retain original wording, ownership, revisions and limitations. They are not current status, new authorization or active claims.

<a id="q-team-06--vector-cacheindex-implementation"></a>
<a id="history-q-team-06--vector-cacheindex-implementation"></a>

### Q-TEAM-06 — Vector cache/index implementation

- Question: Does measured catalog size/latency justify a dedicated index, or is a versioned embedding cache with deterministic cosine similarity sufficient?
- Historical constraints (before DEC-138): Required hybrid retrieval is decided; the vector product is not. Key by series/concept ID, catalog text hash, model ID and measured dimension 4096; never store observation values as vectors. A dedicated catalog vector-search layer is intended, but no product/index is implemented. LanceDB is the strong/preferred dedicated-index candidate to benchmark first; exact cosine over a versioned embedding cache may be the small-catalog baseline. No PostgreSQL/pgvector service without a later explicit justification.
- Owner: Eray (original decision). Status: **ANSWERED (2026-09-14) by [DEC-138](DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git): LanceDB is the catalog vector index.** PRs #153/#154 delivered pinned LanceDB 0.38.0, bounded local search and optional combined candidates. Prepared runtime still uses lexical retrieval without real Qwen embedding injection; input-policy/limit review and live semantic-quality acceptance remain unfinished. The question and pre-DEC-138 constraints above are historical.
- Evidence needed: versioned catalog scale, cold/warm latency, deployment simplicity, benchmark quality, dependency cost, deterministic ranking and failure tests. DEC-137 supersedes only the prior mandatory product choice; its dated refinement prioritizes required hybrid retrieval while deferring dedicated-index scaling beyond measured need.

<a id="q-team-05--workspace-persistence-and-reference-storage"></a>
<a id="history-q-team-05--workspace-persistence-and-reference-storage"></a>

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

<a id="q-team-04--causality-implementation-and-prerequisites"></a>
<a id="history-q-team-04--causality-implementation-and-prerequisites"></a>

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

<a id="q-team-03--frontend-framework"></a>
<a id="history-q-team-03--frontend-framework"></a>

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

<a id="q-team-02--analyticalparsing-engine"></a>
<a id="history-q-team-02--analyticalparsing-engine"></a>

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

<a id="q-team-01--orchestration-mechanism"></a>
<a id="history-q-team-01--orchestration-mechanism"></a>

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

<a id="q-dev-01--coding-assistants-during-development"></a>
<a id="history-q-dev-01--coding-assistants-during-development"></a>

### Q-DEV-01 — Coding assistants during development

- [x] Record organizer policy on coding assistants used only to build the product. **ANSWERED 2026-09-10: coding assistants are permitted as development tools.**
- Question (resolved): Are Codex/Claude Code or other coding assistants permitted strictly as development tools while runtime uses only Kloudeks, and is disclosure required?
- Why it matters: Development-tool permission is separate from the confirmed runtime restriction, and the kick-off deck's wording did not clearly keep them separate. The repository is built with assistant help, so an unfavourable reading would have been a compliance problem discovered at submission.
- Blocks which milestone? Nothing further; the development workflow and M11 submission are unblocked on this point.
- Can we proceed before answer? Resolved — assistant-assisted development may proceed.
- Standing constraint: **the runtime restriction is untouched by this answer.** Permission covers assistants used to write the product; the delivered product still reaches an LLM only through Kloudeks under DEC-002/DEC-129/DEC-131. No assistant, and no model an assistant runs on, may appear in a runtime path, a dependency or a delivered request.
- Owner: Eray (obtained the answer).
- Status: **ANSWERED** for development use; the runtime ban is unchanged and remains a hard constraint.
- Answer / evidence: The team is permitted to use coding assistants as development tools — relayed by Eray on 2026-09-10. This resolves the ambiguity recorded the same day: the kick-off deck answers "may we use cloud AI services?" with no, prohibits third-party LLM API services, and adds (deck, 7 September 2026): "Geliştirme süreçlerinde yalnızca Kloudeks platformu üzerinden erişilebilen açık kaynaklı dil modelleri kullanılmalıdır." That sentence governs the **models the delivered product calls**, not the tools used to write it. Attach the underlying organizer message reference and its date to this entry if one is available, so the record does not rest on a relay alone.
- Disclosure: no disclosure requirement was reported. If the organizers later ask for one, this entry and the Git history are the evidence; do not retrofit attribution selectively.
