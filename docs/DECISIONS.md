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

## Proposed decisions

Candidates below are not approved selections. Compare options in a bounded task; do not silently promote a proposal to CONFIRMED.

| ID | Proposal | Alternatives / evidence needed | Owner | Next action |
| --- | --- | --- | --- | --- |
| PROP-01 | Minimal bounded orchestration | Custom loop vs LangGraph/other framework; compare a typed plan, repair, workspace update | Unassigned | Resolve Q-TEAM-01 |
| PROP-02 | Lightweight analytical engine | Pandas, Polars, DuckDB, or another justified option; parsing/date alignment/install cost | Unassigned | Resolve Q-TEAM-02 before adding dependency |
| PROP-03 | Minimal plan/results/evidence UI | Framework depends on demo environment and operator needs | Unassigned | Resolve Q-DEMO-01 and Q-TEAM-03 |
| PROP-04 | Retry and latency budgets | Exact counts/timeouts depend on platform limits and baseline measurements | Unassigned | Obtain Q-K-04 and measure before fixing limits |
| PROP-05 | Causality capability with prerequisites | Method, sample size, assumptions, and abstention need statistical review | Unassigned | Resolve Q-TEAM-04; association/abstention can proceed |

## Deferred decisions

| Topic | Status | Why deferred | Revisit trigger |
| --- | --- | --- | --- |
| Router fine-tuning | DEFERRED; no training approach selected | No measured routing baseline or confirmed resources | Persistent routing errors after simpler fixes, plus time/compute |
| Vector DB / embeddings / reranking | DEFERRED; no engine selected | Retrieval scale/platform capability unknown | Discovery benchmark demonstrates need and Q-K-05 answered |
| Multi-agent topology | DEFERRED; none selected | Added coordination cost is not justified | A bounded independent role measurably improves results |
| Workspace persistence backend | DEFERRED; state semantics still required | Demo durability requirements unknown | Q-INFRA-02 and Q-DEMO-02 answered |
| GPU/training deployment | DEFERRED | Resource availability/need unknown | Q-COMP-01 answered and workload requires it |
| Enterprise security infrastructure | DEFERRED | Outside 8–9 day scope | Concrete production/organizer requirement |

Exact Kloudeks endpoint/auth/model is **UNDECIDED and externally blocked**, not a preference to settle by guessing. Orchestration framework, analytical engine, frontend framework, and exact causality implementation also remain UNDECIDED.

## Maintenance

Add an ADR when a constraint or choice actually changes. Use the fields above and link the answer, experiment, or PR. Keep rejected alternatives brief. Update OPEN_QUESTIONS for unresolved issues and ROADMAP for implementation progress.
