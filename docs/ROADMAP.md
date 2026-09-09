# Mission / success criteria

Deliver an evidence-backed financial analyst in an 8–9 day hackathon window. A teammate must be able to load a supported unfamiliar source, ask a financial question, inspect a typed plan, receive deterministically computed results, and trace every material claim to data, transformations, and validation. A follow-up question must reuse explicit analysis state correctly.

Demo acceptance requires all of these observable outcomes:

- [ ] Load a supported unfamiliar CSV/XLSX schema without source-specific changes to the core.
- [ ] Complete a representative BDDK/EVDS analysis when access is confirmed, or use an explicitly permitted, clearly labeled fixture/cache fallback.
- [ ] Generate and validate a plan through the confirmed Kloudeks path; no third-party runtime LLM dependency.
- [ ] Align dates/frequencies/units and stock/flow/cumulative semantics explicitly; abstain or clarify when meaning is insufficient.
- [ ] Compute a change/comparison and an association/lag analysis with deterministic tools; do not turn association into a causal claim.
- [ ] Show a table/chart and a trace from each material result to source, transformation, and verification.
- [ ] Add a series or change a date range in a follow-up without losing prior state or showing stale results.
- [ ] Reject invalid tools/arguments and hostile supported inputs; recover within configured limits from a recoverable failure.
- [ ] Run the agreed benchmark and operator rehearsal with recorded results, known limitations, and permitted fallback behavior.

This file owns **execution truth**. [ARCHITECTURE](ARCHITECTURE.md) owns technical structure, [EVALUATION](EVALUATION.md) correctness measurement, [SECURITY](SECURITY.md) controls, [DECISIONS](DECISIONS.md) choices/reasons, [OPEN_QUESTIONS](OPEN_QUESTIONS.md) unknowns, and [AGENTS](../AGENTS.md) coding-agent behavior.

# Current project status

Latest verification (2026-09-09): M1-10 is DONE — [PR #16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) merged into `dev` at `400fe58f49e2c9513f77799090030313dcc55088`, with the validated tree unchanged. [PR #17](https://github.com/cagatayeroglu/KKB-DataTrio/pull/17) then promoted `dev` to `main` at `722c2afaea419e5b270a8531bcd6690d44e53027`; both branches now hold the same tree, every task branch is deleted and no PR is open. No task is claimed or IN PROGRESS. Delivered runtime scope is file admission, bounded XLSX loading and the minimal core contracts; no CSV loader, profiler, adapter registry, provider, planner, analytics tool or UI exists. The older snapshot below is historical; current task records supersede it.

Architecture frozen (2026-09-09, M0-ARCH): the technology stack is decided and recorded as DEC-112 through DEC-126, and [Q-TEAM-01 through Q-TEAM-05](OPEN_QUESTIONS.md#priority-queue) are ANSWERED. DuckDB with Parquet and Pandas is the engine and lakehouse; orchestration is a custom bounded loop; retrieval is LanceDB with DuckDB FTS, RRF and an alias dictionary; the workspace is an artifact DAG in DuckDB; provenance is a typed lineage graph gating a verifier; causality reports association with stated limits; the six brief-named tools carry Pydantic schemas and restricted text-to-SQL; the front end is Next.js over FastAPI with SSE. Two milestones were added for work the previous plan had no home for: [M12](#m12) lakehouse and medallion normalization, and [M13](#m13) semantic catalog and retrieval. **No decision below is implemented code** — every one of them still has to be built.

The internal blockers are now gone; the remaining ones are organizer answers. Q-K-01/02/03 gate every live model path, Q-K-05 gates the dense half of retrieval, Q-NET-01/02 gate the `web_search` and `web_url` tools, Q-DATA-01 gates live source retrieval, and Q-INFRA-01 can override DEC-126. These have external latency, so ask them now rather than when the affected task starts.

Release-gate finding (2026-09-09, Eray): the promoted tree does **not** pass `make full`. `pytest -q` (245 passed), `ruff format --check`, `ruff check`, Bandit and `scripts/check_secrets.py` pass, but `mypy src` reports 14 strict errors — 11 in [xlsx_loader.py](../src/kkb_agent/xlsx_loader.py), 2 in [_xlsx_package.py](../src/kkb_agent/_xlsx_package.py) and 1 missing-stub error in [xlsx_sheets.py](../src/kkb_agent/xlsx_sheets.py). PR #17 merged `dev` into `main` without that gate passing, so `main` is a convenience checkpoint rather than a release-validated tree. Tracked as M0-08; do not describe `main` as release-validated until it closes.

Snapshot: **2026-09-08**, after PR #1 merged into `dev` and the local Day 0 files were preserved in a stash. Days below are relative workdays, not confirmed event dates. Recheck Git/PR state on each new session; this snapshot is not a branch-switch instruction.

| Item | Last verified observation |
| --- | --- |
| Current phase | Day 0 foundation; core implementation in progress |
| Active branch | `docs/team-handoff-protocol`, created from updated `dev` at `fe5d44a`; M0-HANDOFF is the active documentation task |
| Current milestone | M0; partial scaffolding also supports M4, M5, M8, M9 |
| Integration state | PR #1 merged; local `dev` was fast-forwarded to verified `origin/dev` at `fe5d44a`. Repository protection/privacy settings were not audited |
| Baseline before documentation edits | `429ea40` — `Add files via upload`; not validation evidence for untracked Day 0 work |
| Initial drafting worktree | Tracked diff and staging area were empty before the documentation rewrite; this is historical baseline evidence |
| In-progress files | All 11 Day 0 files are preserved in the local stash documented under M0; absent from this documentation branch and from shared Git delivery |
| Validation baseline | Source/test files inspected, **application tests and lint NOT RUN in this documentation task**; no passing result established for this snapshot |
| Missing foundation artifacts | `.gitignore`, `.env.example`, and `.github/` workflows absent. PR #1 showed 0 checks because no workflows existed at either base or head; Actions showed its initial setup page. CI implementation remains M0-07 |
| Runtime completeness | No implemented ingestion adapter, registry/executor, analytics, safe fetch, verifier, or UI found in the inspected source tree |
| Documentation | M0-DOC DONE: [PR #1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) merged `adeb692` and `4804d05` into `dev` at `fe5d44a`; document checks passed |

**Known blockers:** live Kloudeks integration needs Q-K-01/02/03; live BDDK/EVDS paths need Q-DATA-01 and network rules Q-NET-01/02; demo environment and cache/persistence rules need Q-INFRA-01/02 and Q-DATA-03. Missing answers block their live paths, not synthetic/offline foundation work.

**Major team choices still open:** orchestration framework, analytical engine, frontend framework, exact causality method, provider model, and persistence backend. Router fine-tuning, vector DB, and multi-agent topology remain deferred. See DECISIONS before adopting any of these.

**Completion boundary:** M0-DOC is DONE with merge and document-check evidence. M0-HANDOFF remains unfinished until its own PR is merged and evidence updated. No Day 0 runtime delivery or passing runtime validation is established. Local/feature-branch work remains PARTIAL / IN PROGRESS until merged into `dev` with required validation passed and roadmap evidence updated.

**Shared-delivery boundary:** the 11 Day 0 files under `src/kkb_agent/core/`, `src/kkb_agent/providers/`, `src/kkb_agent/evaluation/`, `benchmarks/cases/`, and the three new unit tests are now local-stash-only and excluded from both documentation PRs. Later milestone notes about those files describe the original inspected draft, not current shared implementation. A fresh clone cannot recover another clone's stash; obtain separately authorized code delivery before resuming tasks that require it.

## Ordered next safe tasks

For a general “continue,” use the first eligible unchecked READY task with no active owner or published branch/PR claim. This queue points to canonical task checkboxes below; do not maintain a second set of completion boxes here. Recheck actual state and claim the task before starting. A user-specified task overrides ordering, not blockers or confirmed decisions. After M0-HANDOFF merges, a fresh clone's first eligible task is M0-04 unless a teammate has claimed it or newer evidence changes the queue.

| Order | Task | Status / start condition | Expected handoff |
| --- | --- | --- | --- |
| 1 | M0-01 | DONE — [PR #13](https://github.com/cagatayeroglu/KKB-DataTrio/pull/13) merged at `4e10b14`; validated tree unchanged | Minimal source/semantic/evidence contracts are shared; deferred architecture remains undelivered |
| 2 | M4-01 | BLOCKED — provider stub/test inputs are not delivered in `dev` | Obtain authorized inputs; live transport remains separately blocked |
| 3 | M9-01 | BLOCKED — evaluation schema/fixtures are not delivered in `dev` | Obtain authorized inputs; do not claim a scoring runner exists |
| 4 | M0-04 | DONE — [PR #3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) merged into `dev` at `ddcb5a7`; validated tree preserved | Ignore/config implementation and merge evidence recorded under M0-04 |
| 5 | M1-01 | DONE — [PR #4](https://github.com/cagatayeroglu/KKB-DataTrio/pull/4) merged at `cbb51ad`; validated tree unchanged | Generic result specification delivered |
| 6 | M1-02 | DONE — [PR #5](https://github.com/cagatayeroglu/KKB-DataTrio/pull/5) merged into `dev` at `e2287f7`; validated tree unchanged | Admission policy/guards and passing fast gates delivered |
| 7 | M1-04 | DONE — [PR #8](https://github.com/cagatayeroglu/KKB-DataTrio/pull/8) merged at `0d4ecf9`; validated tree unchanged | Synthetic UTF-8 fixture and exact-table test delivered |
| 8 | M1-05 | DONE — [PR #9](https://github.com/cagatayeroglu/KKB-DataTrio/pull/9) merged at `a548a54`; validated tree unchanged | CSV edge fixtures, declarations and passing fast gates delivered |
| 9 | M1-09 | DONE — [PR #11](https://github.com/cagatayeroglu/KKB-DataTrio/pull/11) merged into `dev` at `3e70542`; validated tree unchanged | XLSX fixtures/discovery/selection and passing fast gates delivered |
| 10 | M1-10 | DONE — [PR #16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) merged into `dev` at `400fe58`; validated tree unchanged | Bounded XLSX loading delivered; CSV loading, profiling and provenance integration remain open |
| 11 | M0-08 | READY — unassigned on 2026-09-09; `make full` fails `mypy src` on the current `dev`/`main` tree | Green release gate, or an explicitly recorded typed-boundary exception, before the next `dev -> main` promotion |
| 12 | M0-ARCH | Status in its [active record](#m0-arch-active-record); architecture and stack decisions | DEC-112 through DEC-126 recorded, Q-TEAM questions closed, M12 and M13 added |
| 13 | M1-03 | READY — unassigned; unblocked by DEC-112/DEC-124 once M0-ARCH merges | Runtime manifest reconciled with the decided stack; no loader behaviour change |

READY requires satisfied prerequisites, no active owner, and the fresh-`dev` workflow below. M0-01, M0-07 and M1-01/02/04/05/09/10 are merged; Python >=3.12 is available. The 2026-09-09 rescan found no remote task branch, no open PR and no published claim, so nothing is owned. M0-08 was promoted on the concrete failing-gate evidence above, and M1-03 becomes READY once M0-ARCH merges, since DEC-112 and DEC-124 supply the manifest it was waiting for. M1-11 is the next M1 candidate but stays untriaged rather than being silently promoted. No engine blocker remains anywhere in M1, M2, M6 or M12; M4-01/M9-01 still need separate authorization/delivery, and M4 live transport still needs Q-K-01/02/03. The original stash remains intact. Older READY mentions for completed tasks do not describe the current queue. Recheck ownership before claiming; never reuse a merged branch or invent validation to unblock work.

| Queued task | Task-specific acceptance once eligible |
| --- | --- |
| M0-01 | Selectively recover/simplify only the reviewed source/semantic/evidence primitives under the explicit M0-01 authorization; focused construction, rejection, unknown, provenance and state-isolation tests plus fast gates pass; no agent architecture |
| M4-01 | Existing provider unit tests and provider/test-file lint pass; record environment parsing, masked representation, and pending-error coverage; live transport remains blocked |
| M9-01 | Existing evaluation-schema test and evaluation/test-file lint pass; record schema-only validation; do not claim analytical execution or numeric scoring |
| M0-04 | Ignore rules and placeholder-only config exist; safe synthetic checks prove secrets/private/generated paths are ignored and the example remains trackable |
| M1-01 | A reviewed specification covers the listed result fields, unknown semantics, and testable examples; no engine selection or runtime contract change is implied |
| M1-10 | Delivered; exact objective, bounds and validation are in the [M1-10 completion record](#m1-10-completion-record) |
| M0-08 | `make full` passes on `dev`, or each remaining strict-typing gap is recorded as an explicit, reviewed exception with its reason; no new dependency or loader behaviour change |

Queue re-evaluation after PR #11 (2026-09-08): no open/draft PR claim and no new remote task claim was found. M0-07 is unchecked **untriaged backlog, not READY**; no CI workflow exists. Its documented local checkout/Python >=3.12 prerequisites are available and the local fast gate is already validated, but it has no READY/ownership record. No unresolved architecture or organizer answer was identified for the narrow fast-CI scope. Under AGENTS' explicit READY selection rule and this task's stop condition, no new implementation was claimed. M0-03's smoke/quick behavior is already covered by recorded passing gates; its unchecked box is a bookkeeping gap, not evidence of a failing baseline. Other untriaged M0 boxes were not silently promoted to READY or marked DONE.

| Immediate blocker / candidate | Required next action | Blocker category |
| --- | --- | --- |
| M0-01, then downstream core consumers | Minimal baseline delivered by PR #13; re-evaluate each consumer's own prerequisites, without restoring deferred abstractions | Resolved for the delivered subset; no blanket downstream READY promotion |
| M4-01 / M9-01 | Separately deliver/review preserved provider/evaluation inputs; synthetic work needs no live credentials | d, then c; live M4 additionally needs b: Q-K-01/02/03 |
| M1-03 and engine-dependent ingestion | Resolved by DEC-112; M1-03 is now dependency reconciliation, and M1-06/07/08 have no remaining engine blocker | Resolved |
| M1-10 | DONE; PR #16 merged at `400fe58` with passing targeted tests and fast gates | Resolved |
| M0-08 / `main` release validation | Make `make full` pass, or record reviewed typed-boundary exceptions, before the next `dev -> main` promotion | Defect in already merged code; no organizer answer or team choice needed |
| M0-07 | DONE; PR #15 merged at `5f93df7` with a passing Fast PR gate | Resolved; generic foundation phase is complete by team direction |
| Live sources / demo paths | Obtain the recorded Kloudeks, data/network, environment and cache/persistence answers; retain separate unresolved framework choices | b: organizer answers (Q-K-01/02/03, Q-DATA-01/03, Q-NET-01/02, Q-INFRA-01/02); a: team choices in DECISIONS |

M0-01, M0-07 and M1-10 are delivered and merged; their records are below. No task is claimed. Preserve the stash and recheck ownership before subsequent work.

The PR #11 scan is historical; M0-01 completion and the requested post-PR #13 M1-10 review supersede its affected entries. M0-01 application validation is recorded below. If a READY task reveals a missing prerequisite, record it rather than claiming success.

# Team Handoff Protocol

## Repository Git workflow

CONFIRMED in DEC-109. Persistent branches: `main` = stable/demo-ready checkpoint; `dev` = shared integration. Never implement on or push directly to either branch.

Every meaningful implementation task starts from latest `dev` on a separate short-lived branch. Inspect/preserve existing Git work, fetch the verified remote, switch to/update `dev` with a fast-forward-only pull, verify it matches the fetched tip, then create the task branch. If existing work or divergence prevents a safe update, isolate the task from latest `dev` or record the blocker; do not reset/discard work or use stale integration state.

Prefer `feature/<milestone>-<task>`, `fix/<short-description>`, or `docs/<short-description>`. Examples: `feature/m1-csv-ingestion`, `feature/m2-frequency-alignment`, `fix/url-fetch-timeout`.

Implement only that task -> targeted checks -> relevant roadmap evidence -> clear commit -> normal task-branch push -> PR into `dev`. Codex may perform these normal Git/terminal operations for assigned tasks. An open or approved PR is still PARTIAL until merge. After review and verified merge, delete the short-lived branch only when no unmerged work or active checkout would be lost. The next task starts from freshly updated `dev`, never the previous feature branch. A base on another unfinished feature branch requires an explicit documented instruction/dependency.

Codex does not merge its own PR without explicit instruction, push directly to `dev`/`main`, or force-push shared branches. PR #1 used `feature/day0-core` by explicit exception; the subsequent M0-HANDOFF task uses a fresh branch from merged `dev`.

| Stage | Gate / result |
| --- | --- |
| Normal task | Targeted tests/lint or `make quick`; document-only tasks use diff/link/status checks |
| Task branch -> `dev` | Fast PR gate (`make pr` for code); review, merge, and recorded evidence before DONE/[x] |
| `dev` -> `main` | Full/release gate, approximately every 3–4 days or an important stable milestone, only when integrated `dev` is demo-ready |

Do not update `main` after every task or promote an unstable state because the date arrived. AGENTS/DEC-109 own gate placement; targeted negative tests still apply to security/contract changes. Full/release checks are reserved for checkpoint gates or explicit requests.

## Checkbox and status rules

- `[ ]` means unfinished, including READY, IN PROGRESS, PARTIAL, BLOCKED, and untriaged backlog.
- `[x]` means implementation is **merged into `dev`** and required targeted validation has passed. Documentation tasks require verified edits and merge too. Record actual merge evidence; a local file, commit, push, or approved PR alone is insufficient.
- Allowed task states: `Status: READY`, `Status: IN PROGRESS`, `Status: BLOCKED`, `Status: PARTIAL`, and `Status: DONE`. Legacy COMPLETE means DONE only with verified evidence; NOT STARTED remains a backlog/milestone description, not an active task state or authorization to begin.
- READY has satisfied prerequisites and no active owner. PARTIAL / IN PROGRESS includes work only local/on a task branch, even if validation passes. BLOCKED names its dependency/question and unblocking action. DONE requires implementation, passed required validation, PR merge into `dev`, and updated roadmap evidence.
- A file's existence, a test definition, a model protocol, or a desired diagram is not runtime acceptance evidence.
- Mark a milestone COMPLETE only when its in-scope task implementations are merged into `dev` and acceptance/required validation pass. Optional/deferred tasks stay unchecked and explicitly scoped out with a reason; do not check them merely because they were cut.

## Claim, work, hand off

1. Pull latest `dev` safely, read current status/relevant milestone, select an eligible READY task, and create its fresh branch. Never implement directly on `dev`.
2. Inspect active branch/draft/open PR claims as well as `dev`'s ROADMAP. Set `Status: IN PROGRESS`, actual Owner, Branch, and Task ID under the relevant milestone. Publish this small claim commit and draft PR before implementation; a local-only claim cannot coordinate teammates. Recheck claims after publication. A collision or inaccessible claim state blocks overlapping work until ownership is confirmed; no automatic takeover. See [claiming rules](../AGENTS.md#task-claiming-and-ownership).
3. Implement that task, run relevant targeted/fast PR checks, and record validation and remaining limitations.
4. Keep the checkbox unchecked/PARTIAL, update only that task's evidence/blocker/handoff, commit, push its branch, and update the same PR into `dev` for review. Fill real Commit/PR references once available; never invent a future SHA.
5. After an authorized merge, the next task owner verifies the implementation is in updated `dev` and its required checks passed, then records DONE/[x] plus merge evidence in a small update on a fresh task/docs branch. Do not pre-check an unmerged implementation or push bookkeeping directly to `dev`.
6. Clean up the merged short-lived branch safely. Start subsequent work from newly updated `dev`. If stopping before merge, leave PARTIAL / IN PROGRESS, exact next action, and PR/blocker status.

A stopping handoff states what works, what remains, exact branch, targeted tests/results, known failure/blocker, and recommended next action. A few lines suffice. PR/commit/benchmark fields can remain `—` until they exist. Do not imply a commit or remote check happened. Link a safe result artifact when available; omit sensitive input content.

Every task supports the following compact record. Copy it under the relevant milestone for active work; do not create boilerplate for every untouched task or overwrite another task's evidence. Existing milestone records remain summaries. Update top-level status only when the phase, critical blocker, or queue actually changes.

```text
Task: actual roadmap ID
Status: READY / IN PROGRESS / BLOCKED / PARTIAL / DONE
Owner: actual teammate or agent task owner
Branch: actual task branch; record dev base revision when useful
PR: URL/number + review/merge state, or pending
Commit: implementation revision + merge evidence when available, or pending
Tests: exact command and result, or NOT RUN with reason
Blocker: exact missing dependency/answer, or none
Handoff: what works; what remains; next action, prerequisites, and any local-only files
```

Before merge, commit/push the record with PARTIAL status. After the implementation merge, verify the actual merged revision or PR record (including squash merges) rather than assuming a feature SHA must appear unchanged in `dev`. A completion-bookkeeping PR records an already merged implementation; it does not require an endless chain of new completion tasks.

Illustrative example only; this is not current project evidence:

```markdown
Completed:
- [x] CSV parser and basic profiling
- [x] Malformed-file negative tests
Evidence:
- Status: DONE — implementation reviewed and merged into dev; evidence updated
- Owner: Example teammate
- Branch: feature/m1-csv-ingestion (deleted after merge)
- Tests: <exact targeted command> — 14 passed
- PR: #12 — merged into dev; merge revision recorded in the real task record
- Commit: <actual implementation/merge revision in a real record>
Remaining:
- [ ] XLSX multi-sheet handling
- [ ] Size-limit cases
Handoff: Pull latest dev and create a new task branch for M1-09 using that contract.
```

## Three-person coordination

Suggested rotating slots, **not assigned teammates**:

| Slot | Primary lane | Review partner | Handoff artifact |
| --- | --- | --- | --- |
| A — data | M1/M2/M3 and extraction inputs to M7 | B for contract changes | Fixtures, contracts, normalization expectations |
| B — runtime | M0/M4/M5 and workspace integration | C for failure cases | Typed plans, tool runs, recoverability behavior |
| C — correctness/demo | M8/M9/M10 and rehearsal coordination | A for numerical oracles | Expected results, scorecard, operator steps |

Everyone contributes to M6/M7/M11 where needed. At each workday's start, spend a few minutes claiming one task per person and identifying dependencies; at stop, leave the short record above. Select actual owners before work. Do not add a meeting/reporting ceremony to every Codex prompt. Shared contracts get one active editor and a named reviewer; other teammates work on independent fixtures or consumers.

Do not start another teammate's IN PROGRESS task; PARTIAL/BLOCKED ownership remains active until explicitly released/transferred. Independent tasks use separate fresh branches from latest `dev`; prefer waiting for dependency merge over stacking. Explicitly authorized stacked work must record its base, dependency PR, and integration plan.

Time passed is not abandonment evidence. For takeover, inspect the branch/PR and Handoff, confirm activity with the owner/team, and record the old/new owner plus confirmation and retained work. If confirmation is unavailable, preserve the assignment and choose independent work. Git/PR claims are visible records, not atomic locks; simultaneous claims require a short ownership confirmation, not a silent overwrite. No fixed Eray/Arda assignment or automatic stale timeout is assumed.

# Milestone overview

## Relative 8–9 day execution plan

Day 0 is bootstrap before the eight delivery days. If bootstrap must fit within eight total calendar days, combine Day 0 and Day 1 and reduce optional scope; do not pretend the schedule gained a day. Day 9 is contingency only if the organizer allows it.

| Workday | Slot A focus | Slot B focus | Slot C focus | Daily observable exit |
| --- | --- | --- | --- | --- |
| 0 | Inspect contracts/fixture needs | Validate M0/M4 scaffolding | Validate M9 schema; establish handoff | Core baseline result recorded, unanswered access questions queued |
| 1 | M1 safe CSV/XLSX path | M5 registry/executor baseline; provider questions | M9 numeric oracles and M8 evidence requirements | Synthetic data can load into a common contract |
| 2 | M2 basic unit/frequency policies | M5 plan/workspace path + M6 basic change; M4 live access if unblocked | M8 minimal verification; M9 first smoke runner | Thin slice: load -> deterministic change -> evidence, with provider double if necessary |
| 3 | M2 cumulative/stock-flow cases; M3 if unblocked | Wire M4/M5 and bounded repair | Adversarial semantics regression | Agreed normalization cases pass with explicit transformations |
| 4 | M6 association/lag inputs | M6 tools and typed outputs | Statistical oracles and claim checks | Representative analysis works end-to-end with causal discipline |
| 5 | M7 safe extraction; M3 integration | M7 safe-fetch integration | Hostile-file/URL/prompt cases | Second supported source joins an existing analysis safely |
| 6 | Fix measured data errors | M8 integration and runtime failures | M9 expanded corpus/scorecard | Failure categories and benchmark baseline are reproducible |
| 7 | Source/demo-data review | M10 UI integration and measured latency | Independent operator rehearsal | Another teammate runs the demo and finds evidence without assistance |
| 8 | Fix highest-impact regressions | M11 full gate and dependency freeze | Full evaluation/security review/rehearsal | Reproducible demo candidate and honest limitations; release only if authorized |
| Optional 9 | Measured blockers only | Measured blockers only | Repeat changed-path rehearsal | No architecture rewrite or speculative feature addition |

| Milestone | Scope | Current status | Target window |
| --- | --- | --- | --- |
| [M0](#m0) | Repository and development foundation | PARTIAL | Day 0 |
| [M1](#m1) | Generic ingestion/profiling | PARTIAL — admission, fixtures and bounded XLSX loading merged | Days 1–2 |
| [M2](#m2) | Financial semantics/normalization | NOT STARTED | Days 2–3 |
| [M3](#m3) | BDDK/EVDS integration | BLOCKED for live access; fixtures can proceed after M1 | Days 1–5 as access permits |
| [M4](#m4) | Kloudeks | PARTIAL; live transport BLOCKED | Days 0–3 as access permits |
| [M5](#m5) | Planning/routing/workspace | NOT STARTED; mechanism decided in DEC-113/DEC-117 | Days 1–3 |
| [M6](#m6) | Deterministic analytics | NOT STARTED | Days 2–4 |
| [M7](#m7) | URL/documents/external inputs | NOT STARTED; live policy unresolved | Day 5 |
| [M8](#m8) | Verification/evidence/provenance | PARTIAL — record models only | Days 2–6 |
| [M9](#m9) | Evaluation/adversarial benchmark | PARTIAL — schema and three cases only | Days 0–6, then continuously |
| [M10](#m10) | UI/demo workflow | NOT STARTED; framework decided in DEC-123, hosting still Q-INFRA-01 | Day 7; operator design can precede |
| [M11](#m11) | Hardening/rehearsal | NOT STARTED; upstream acceptance required | Days 8–9 |
| [M12](#m12) | Lakehouse and medallion normalization | NOT STARTED; unblocked by DEC-112 | Days 1–4 |
| [M13](#m13) | Semantic catalog and retrieval | NOT STARTED; unblocked by DEC-115/DEC-116 | Days 2–5 |

## Dependency and scope policy

The critical path is M0 contracts -> M1 ingestion -> M12 lakehouse and semantics -> M13 catalog -> M5 execution + M6 basic change -> M8 evidence -> M10 demo -> M11. M2 is the specification half of the normalization work that M12 implements against the chosen engine; they are worked together, not sequentially. M4 live access is required for the final live model path. M9 develops alongside each feature; do not wait until Day 6 to define expected outputs. M3/M7 depend on safe boundaries and source permissions. Milestone dependencies below name required subsets, not a requirement to finish every optional task upstream.

M12 is where correctness is won or lost. Cumulative handling, frequency alignment and unit normalization decide whether every downstream number is right; no other milestone can compensate for an error there. Prefer a thin vertical slice through the whole path early — one series, loaded, normalized, queried, answered with evidence — over completing any single milestone horizontally.

If behind schedule, cut fancy UI, optional image/exotic formats, router fine-tuning, advanced causality methods, deep observability, and extra agents. Keep typed plans, semantic correctness, evidence, safe inputs, and regressions. Record each cut and its demo consequence. Never advertise a cut/blocked format or live integration as supported.

<a id="m0"></a>
# M0 — Repository & development foundation

Status: PARTIAL. Tracked package/build/check definitions plus unvalidated Day 0 core work preserved in a local stash; only the original documentation task is DONE.

## Objective

Establish a safe, fast baseline and shared contracts that three teammates can extend without losing in-progress work.

## Dependencies

Local checkout and Python >=3.12 for later application validation. No live Kloudeks access is needed for the stub/contracts. Remote changes require explicit authorization.

## Tasks

- [x] M0-01 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-01-core-contracts`. Selectively reviewed/recovered the minimum ingestion/provenance core contracts and focused `tests/unit/test_core_models.py` cases; targeted tests/lint and fast gates passed. PR #13 merged into `dev` at `4e10b14`, with the validated tree unchanged. Deferred protocols/planner/workspace/provider/evaluation code is outside this delivery.
- [ ] M0-02 — Add targeted coverage for duplicate/self dependencies, invalid outcome combinations, and workspace serialization as needed; keep schema changes distinct from validation-only work.
- [ ] M0-03 — Validate the tracked package smoke test and existing `make quick` baseline; record unavailable tooling/failures honestly.
- [x] M0-04 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-04-local-config-hygiene`. Local ignore rules and placeholder-only `.env.example` passed targeted validation without real credentials; [PR #3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) merged into `dev` at `ddcb5a7`, with the validated tree unchanged.
- [ ] M0-05 — Reconcile provisional Kloudeks variable names with the stub; label them local conventions until Q-K-01 is answered.
- [ ] M0-06 — Inspect repository privacy, branch protection, and remote CI only in an authorized setup task; local branches alone do not prove remote settings.
- [x] M0-07 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-07-fast-ci`. Add a fast feature-to-dev CI workflow; required checks and handoff are in the active record below. PR #15 merged at `5f93df7`; validated tree unchanged.
- [ ] M0-08 — Status: READY. Owner: unassigned. The [Makefile](../Makefile) `full` target already exists and is correctly kept out of the per-edit loop, but it does not pass: `mypy src` reports 14 strict errors in the merged XLSX code. Make the release gate green, or record reviewed exceptions, before the next `dev -> main` promotion. Evidence: [M0-08 active record](#m0-08-active-record).
- [ ] M0-09 — Confirm synthetic/public-safe fixture policy and document where local private inputs may be stored before accepting them.
- [ ] M0-10 — Document an actual successful setup command/result on a teammate's Python >=3.12 environment.
- [ ] M0-11 — Record the validated core contract baseline and named editor/reviewer before shared contract changes.
- [ ] M0-12 — Run targeted/quick checks and the fast PR gate for foundation work, including boundary/contract negative tests; full checks belong to checkpoint gates or explicit requests.
- [ ] M0-13 — Record implementation evidence and the next ready task after validation.
- [ ] M0-ARCH — Status: IN PROGRESS. Owner: Eray; Branch: `docs/m0-arch-stack-decisions` from `dev` `8197829`. Freeze the architecture and stack: record the analytical engine, orchestration, catalog/retrieval, workspace, lineage, verifier, causality, tool surface, provider interface, frontend/API, dependency policy, package layout and deployment topology as decisions; close the Q-TEAM questions they answer; add the lakehouse and semantic-catalog milestones. Evidence: [M0-ARCH active record](#m0-arch-active-record).
- [x] M0-DOC — Status: DONE. Documentation checks passed; [PR #1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) merged both documentation commits into `dev` at `fe5d44a`; evidence recorded below.
- [x] M0-HANDOFF — Status: DONE. [PR #2](https://github.com/cagatayeroglu/KKB-DataTrio/pull/2) merged into `dev` at `a5d6ee8`; the record below was left stale at PARTIAL and is corrected by this task. Document startup with zero chat history, visible task claims, ownership transfer, concise handoffs, and merge-based DONE. Owner: Codex for the initiating repository owner; Branch: `docs/team-handoff-protocol` from `fe5d44a`. Acceptance: the startup prompt selects an eligible unowned READY task using Git/PR history and targeted docs, preserves unrelated work, and stops on unresolved ownership/decisions; document checks pass and PR merges into `dev` before DONE.

## Acceptance criteria

A teammate can install the declared development environment, run recorded quick checks without live credentials, locate contract/fixture ownership, and identify the next task. Ignore/config/CI behavior is verified before claiming the repository foundation complete. M0-DOC alone does not satisfy this milestone.

## Evidence / implementation record

- Status: PARTIAL for M0; M0-DOC DONE; runtime tasks remain unvalidated.
- Owner: Unassigned for runtime; Codex prepared M0-DOC documentation.
- Branch: `feature/day0-core` for merged M0-DOC; new documentation work uses `docs/team-handoff-protocol`.
- PR: [#1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) — merged into `dev` on 2026-09-08 after docs-only/conflict verification and explicit user merge authorization; no independent teammate review claimed.
- Commit: `adeb6928d3000977d1f1f2e2a0bb8bb4a2aa9129` and `4804d054576943691d0ebe2b7aecace5c05ef422` are ancestors of verified `dev` merge `fe5d44ab74e60633ef52c5ba4de7a5a5ca8fa083`; merged tree matches reviewed head.
- Tests: M0-DOC document checks PASS (2026-09-08): diff review, `git diff --check`, local/tracked-tree links and anchors, checkbox/task/record checks, and preservation of non-document files. PR scope and `git diff --check origin/dev...feature/day0-core` rechecked before merge. Application tests/lint NOT RUN; no tooling installed.
- Benchmark: NOT RUN; runner absent.
- Notes: Core/provider/evaluation Day 0 drafts and tests are stash-only; [Makefile](../Makefile) defines `quick`, `pr`, `full`. PR #1 had 0 checks because `.github/workflows` was absent on both base/head; Actions displayed initial workflow setup. No CI/settings/permission changes made; M0-07 remains open, and 0 checks is not a CI PASS.
- Known limitations: No passing implementation validation established; ignore/config files and CI workflows missing.
- Handoff: Review M0-HANDOFF's documentation PR into `dev`, then start the next unowned READY task from freshly updated `dev`. M0-04 is first for a fresh clone; M0-01/M4-01/M9-01 require separate Day 0 delivery. Keep that code outside documentation PRs.

### M0-01 active record

- Status: DONE — authorized PR #13 merge into `dev` verified on 2026-09-08; required validation passed and the merged tree is unchanged
- Owner: Çağatay
- Branch: `feature/m0-01-core-contracts`; fresh base `8b7421af3840856462795a018dc5ed6d133aaeaa` after PR #12 merged
- PR: [#13](https://github.com/cagatayeroglu/KKB-DataTrio/pull/13) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: claim/classification `7fc659083ac580ef892d6a1f13b8325dcda1e949`; implementation `14f25a21f149682c8ca890f8f01e388afe154756`; validated head `4798e42167f911d89bf763be010d11edee02536b`; merge `4e10b1437eb7df6c6df5f2e728f644c8d5c8852a` contains that head with an identical tree. Completion bookkeeping uses fresh `docs/m0-01-completion-m1-10-readiness` from updated `dev`
- Readiness: Explicit user authorization on 2026-09-08 resolves M0-01's recovery blocker. Python 3.12.2 and the declared Pydantic dependency are available; confirmed DEC-103/104 support minimal source/semantics/evidence primitives without choosing an engine or agent architecture. No competing open PR or remote task claim found before and after draft publication. M1-09 DONE is present in merged `dev`.
- Objective / acceptance: Review/selectively deliver the required core inputs and focused tests from the preserved Day 0 work. Validate construction/rejection, explicit unknowns, provenance serialization and independent mutable defaults, plus touched-code lint, `make quick` and `make pr`. The user's explicit simplification scope supersedes the older validation-only/no-redesign handoff for this task; it does not authorize later architecture work.
- Preservation: Read all 11 blobs via `git show` from `49d3fd30cc56b5ca928976d22e3b993960650c85^3` before writing code; tracked/index stash diffs are empty. No stash apply/pop/drop or modification. Only the reviewed classes/test cases below were copied into the fresh branch; the original stash object and all 11 blobs remain intact.

| Preserved path / logical component | Classification before recovery | Reason / action |
| --- | --- | --- |
| `src/kkb_agent/core/models.py` — base, SourceRef, Frequency/StockFlow, DataContract, TransformationRecord, ValidationOutcome, EvidenceRecord | A KEEP primitives / B SIMPLIFY file | Preserve source/semantic/evidence fields required by generic ingestion; strengthen focused value validation, remove unused confidence/aggregation fields. No executable behavior inferred from records. |
| `src/kkb_agent/core/models.py` — PlanStep, AnalyticalPlan, ToolResult/ToolStatus, AnalysisWorkspace; aggregation/confidence fields | C DEFER | Current admission/sheet-selection work does not require these exact abstractions; planner, tool, workspace and richer normalization contracts belong to later tasks. |
| `src/kkb_agent/core/__init__.py` | B SIMPLIFY | Export only the retained minimum primitives. |
| `src/kkb_agent/core/interfaces.py` | C DEFER | SourceAdapter's fixed async/discovery/profile API, AnalyticalTool and LLMProvider protocols are not needed for this delivery. |
| `tests/unit/test_core_models.py` | B SIMPLIFY | Retain unknown/extra-field checks; add focused retained-contract invariants; defer plan/tool cases with their models. |
| `src/kkb_agent/providers/__init__.py`, `src/kkb_agent/providers/kloudeks.py`, `tests/unit/test_kloudeks_provider.py` | C DEFER | M4-specific configuration/stub tests; no provider functionality in M0-01. |
| `src/kkb_agent/evaluation/__init__.py`, `src/kkb_agent/evaluation/models.py`, `benchmarks/cases/synthetic.json`, `tests/unit/test_evaluation.py` | C DEFER | M9 schema/corpus/tests are not core ingestion prerequisites. |
| Permissive string/number-to-boolean cumulative coercion; claims that structural records alone establish validated tool execution or replayability | D REJECT behavior/claims | Preserve unknown versus explicit false; no unimplemented execution/verification guarantees. No whole preserved file needs rejection. |

- Delivered: [models](../src/kkb_agent/core/models.py), [public exports](../src/kkb_agent/core/__init__.py), and [focused tests](../tests/unit/test_core_models.py). Public contracts are SourceRef, DataContract, TransformationRecord, EvidenceRecord and Frequency/StockFlow/ValidationOutcome enums; the shared validation base and nonblank text constraint are internal. No `core/interfaces.py`, planner/workspace/tool result, provider or evaluation files were recovered.
- Tests: PASS (2026-09-08, Python 3.12.2/Pydantic 2.13.4): `PYTHONPATH=/private/tmp/kkb-m109-deps:src python3.12 -m pytest -q tests/unit/test_core_models.py` — 52 passed in 0.04s (0.76s wall); touched-core/test Ruff format/lint passed; `make quick` — 193 passed in 3.67s (4.50s wall); `make pr` — 193 passed in 3.48s (4.33s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Gates used the same Python/PYTHONPATH with the previously approved openpyxl temporary target. No dependency changes or full/release checks. CI remains unconfigured (0 checks, not a CI pass). Relevant diff, links, scope and stash-preservation checks passed.
- Invariants: Required text is typed/nonblank without trimming; extras and invalid enum values are rejected. Nullable semantics stay None/null; frequency/stock-flow UNKNOWN serializes as `unknown`; cumulative accepts only None/False/True, without coercion. Supplied retrieval time must be timezone-aware; no timestamp/hash default is invented. Transformation lineage requires input/output references and JSON-compatible finite parameters. Evidence starts NOT_RUN. Provenance/metadata round-trip, fresh mutable defaults and reused-source isolation pass.
- Limitations: These are structural records, not a loaded M1 profile, semantic inference, transformer, verifier or complete evidence-chain check. None/null semantics require explicit mapping if a future profile uses the M1-01 `unknown` string representation. Source locators are untrusted metadata, never opened; safe storage/fetch remains the consumer's responsibility. Pydantic validates field assignment but not in-place list/dict mutation: revalidate at boundaries (covered by tests). Declared known semantics/outcomes still require independent evidence; deferred plan/tool/workspace/M4/M9 functionality is not delivered.
- Blocker: none for this scope. Deferred components and unresolved Q-TEAM/organizer decisions remain deferred.
- Merge verification: PR #13 is closed/merged; fetched `origin/dev` and fast-forwarded local `dev`. The full tree matches the validated head, preserving the recorded 52 targeted / 193 quick / 193 PR test evidence. Application gates were not rerun for this documentation-only completion/readiness update; diff, links, status and Git preservation checks passed.
- Handoff: M0-01 is delivered. M1-10 is READY and unclaimed under the scope below; no implementation started. M0-11 still owns naming an editor/reviewer before shared contract changes; consuming the delivered primitives does not require recovering the deferred protocols. M1-03/CSV engine work still needs Q-TEAM-02, M4-01/M9-01 need separate recovery authorization, and M0-02 plan/tool/workspace cases remain deferred. Keep the original stash intact.

### M0-04 active record

- Status: DONE — targeted validation passed; PR #3 merge and identical integrated tree verified on 2026-09-08
- Owner: Çağatay
- Branch: `feature/m0-04-local-config-hygiene`; base `a5d6ee8ab8bb5a109558b7053f4060e91c7bb8f1` after PR #2 merged
- PR: [#3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) — merged into `dev` after scope/conflict review and explicit user authorization; 0 CI checks expected until M0-07, not a CI pass
- Commit: `17b53a67147fdcd044adb739d38b0f144355afd6` implements ignore/config hygiene and its tests; merge `ddcb5a74e90468c499246bf2bb7fed170391a7d5` contains validated PR head `8863edd3d1717cbffaf3fdeda15caabb4da7bd94` with an identical tree, so recorded targeted validation remains applicable
- Tests: PASS (2026-09-08, Python 3.12.2): `python3.12 -m pytest -q tests/unit/test_repository_hygiene.py` — 46 passed in 3.24s. `ruff check tests/unit/test_repository_hygiene.py` — all checks passed; `ruff format --check tests/unit/test_repository_hygiene.py` — 1 file already formatted (Ruff 0.8.6 via a temporary `uv tool run --from ruff==0.8.6` environment; repository dependencies unchanged). `git diff --cached --check` passed for implementation files. Targeted tests/lint cover this config-only task; `make quick`, full/security/release checks not run.
- Evidence: Synthetic temporary Git repositories verify that secrets/private/generated paths stay out of normal staging while the root `.env.example`, source, tests, and synthetic fixtures remain trackable. All example values are blank; provisional Kloudeks names remain subject to M0-05 and organizer answers. No environment loader, provider transport, CI, or runtime contract was added.
- Blocker: none for this scope; dependencies and remote claims checked before/after publication. No unresolved decision or Day 0 stash input required.
- Handoff: M0-04 is delivered in `dev`; this post-merge record follows AGENTS.md. M1-01 was selected on a fresh branch from updated `dev`. The Day 0 preservation stash remains unchanged/unapplied.

### M0-07 active record

- Status: DONE — PR #15 merged on 2026-09-08 at `5f93df71b2ddefab7fb668f0daca89fddfb4f068`; full tree matches validated head `46fb2efcc0767a6796a503266dbd1e7de7653dfb`
- Owner: Çağatay
- Branch: `feature/m0-07-fast-ci`; fresh base `dcebf96f9c27b78ac9947850c21762cf3629c869` after authorized PR #14 merge
- PR: [#15](https://github.com/cagatayeroglu/KKB-DataTrio/pull/15) — merged into `dev` after authorized scope/conflict/green-check verification
- Commit: claim `820075edb095151ab9492585e90707c4f8740a9f`; implementation `a55d1189dd99c89cc486188b5cfdd3f6d3fff467`; subsequent documentation-only commit records this observation
- Objective: Add a fast feature-to-dev CI workflow.
- Readiness: READY triage passed on 2026-09-08, then claimed under explicit user authorization to prioritize M0-07 before M1-10. Python >=3.12, the dependency manifest and existing `make install-dev`/`make pr` commands are available. No unresolved architecture/organizer answer or Day 0 recovery is needed; no competing open/draft PR or remote task claim found. This record supersedes the historical untriaged M0-07 queue note only.
- Acceptance: PRs targeting `dev` trigger one fast job for checkout, supported Python, repository dependency installation, Ruff format/lint, unit tests, Bandit and the repository secret scan. Reuse Makefile commands, simple dependency caching, read-only contents permission and cancellation of superseded PR runs. Validate configuration and local `make quick`/`make pr`; observe a real GitHub check without waiting indefinitely. No live credentials, release gate or application functionality.
- Implementation: [Fast PR workflow](../.github/workflows/fast-pr.yml) runs one Python 3.12 job on Ubuntu 24.04 for `pull_request` targeting `dev`, reusing `make install-dev` and `make pr`. Official checkout/setup-python actions are pinned to verified v7 commit IDs; pip cache follows `pyproject.toml`. Token permission is `contents: read`, checkout does not persist credentials, superseded runs for the same PR cancel, and the job has a five-minute ceiling (normal target <=3 minutes). No application/Makefile/dependency changes.
- Tests: PASS (2026-09-08): existing PyYAML parsed workflow; reviewed trigger, job, read-only permissions, cache, concurrency, pinned Action refs and Makefile command expansion. `make quick` — 193 passed in 4.53s (5.48s wall); `make pr` — 193 passed in 3.72s (4.52s wall), Ruff format/lint, Bandit and repository secret scan passed. Used Python 3.12.2, Ruff 0.8.6, Bandit 1.7.10 and the existing temporary openpyxl environment; CI will install declared dependencies on its runner. No added local validation tooling, full/release checks or live credentials. Diff/link checks passed. GitHub configuration execution is verified by the actual run, not by YAML parsing alone.
- Remote check: `Fast PR / Fast PR gate (pull_request)` PASS in 24s on validated head `46fb2ef`; [run](https://github.com/cagatayeroglu/KKB-DataTrio/actions/runs/34258035802). Local quick/pr each passed 193 tests; merge preserved the validated tree. CI workflow exists on `dev`.
- Blocker: none for delivered M0-07
- Handoff: The team considers the generic repository/foundation phase complete after this merge. Continue the explicitly assigned M1-10; do not manufacture more foundation/security/documentation tasks or mark unrelated backlog boxes DONE. `main` and the original Day 0 stash remain untouched.

### M0-08 active record

- Status: READY — unowned; promoted on 2026-09-09 on reproducible failing-gate evidence
- Owner: unassigned
- Branch: —
- PR: —
- Commit: —
- Objective: Make the existing `dev -> main` release gate pass, so that promoting `dev` to `main` means something.
- Finding: `make full` fails on `dev` `400fe58` and on `main` `722c2af`. `mypy src` reports 14 strict errors: [xlsx_loader.py](../src/kkb_agent/xlsx_loader.py) 11 (missing return/parameter annotations, `Any` returns, bare `dict` generics, a `str | None` index, and an untyped `openpyxl` import), [_xlsx_package.py](../src/kkb_agent/_xlsx_package.py) 2 (unchecked `re.Match | None` index; an incompatible handler assignment), and [xlsx_sheets.py](../src/kkb_agent/xlsx_sheets.py) 1 (untyped `openpyxl` import). `pyproject.toml` sets `strict = true`, so this is a real gate failure, not configuration drift.
- Scope note: the `full` half of M0-08's original wording is already satisfied — the target exists in the [Makefile](../Makefile), CI only runs `make pr`, and no per-edit full check was added. What remains is making that target pass.
- Acceptance: `make full` passes on a fresh checkout of `dev`, or each remaining error is recorded here as an explicit reviewed exception with its reason. Add `types-openpyxl` (typing-only, development extra) or a scoped, justified `openpyxl` ignore rather than relaxing `strict`. No loader behaviour change, no new runtime dependency, no relaxation of repository-wide typing without a recorded decision.
- Tests: NOT RUN for a fix; the failing baseline above was reproduced on 2026-09-09 with Python 3.12.5 and mypy 1.20.2 from the declared development extra.
- Blocker: none; no organizer answer or team choice is required.
- Handoff: `main` currently carries an unmet release gate. Either close this task before the next `dev -> main` promotion, or record explicitly in the promotion PR that the full gate was knowingly skipped. Do not describe `main` as release-validated in the meantime.

### M0-ARCH active record

- Status: PARTIAL — content complete and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `docs/m0-arch-stack-decisions`; fresh `dev` base `8197829512926b6eb9c896ecfda6cac98f2dfb90`
- PR: [#19](https://github.com/cagatayeroglu/KKB-DataTrio/pull/19) -> `dev`; draft claim published before content work
- Commit: claim `aba7360`; content commits recorded in the PR
- Objective: Freeze the architecture and technology stack so that M1 onward stops waiting on unresolved team choices, and record every choice with its reason and rejected alternatives.
- Scope: documentation only — DECISIONS, OPEN_QUESTIONS, ARCHITECTURE, ROADMAP and the README repository guide, plus three inbound anchor fixes caused by renaming DEC-111. No `pyproject.toml`, dependency, directory or code change.
- Delivered: [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse) engine and lakehouse, [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) orchestration, [DEC-114](DECISIONS.md#dec-114--pandas-with-calamine-for-operator-fetched-bulk-spreadsheets) bulk spreadsheets, [DEC-115](DECISIONS.md#dec-115--hybrid-series-retrieval-over-lancedb-and-duckdb-fts) retrieval, [DEC-116](DECISIONS.md#dec-116--alias-dictionary-single-turkish-normalizer-and-a-measured-recall-floor) aliases and recall floor, [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag) workspace DAG, [DEC-118](DECISIONS.md#dec-118--lineage-graph-as-the-provenance-substrate) lineage, [DEC-119](DECISIONS.md#dec-119--verifier-gates-the-answer) verifier, [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits) causality, [DEC-121](DECISIONS.md#dec-121--six-brief-named-tools-with-typed-schemas-and-restricted-sql) tools, [DEC-122](DECISIONS.md#dec-122--llmprovider-interface-and-structured-output-fallback) provider, [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end) API and front end, [DEC-124](DECISIONS.md#dec-124--dependency-manifest-and-excluded-technologies) dependencies, [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) layout, [DEC-126](DECISIONS.md#dec-126--single-vm-deployment-with-docker-compose) deployment. DEC-111 narrowed to the untrusted XLSX boundary. Q-TEAM-01 through Q-TEAM-05 closed. M12 and M13 added with their task lists.
- Tests: documentation tier. Full diff review; `git diff --check` clean; a link and anchor pass over all tracked Markdown — 158 local links, 240 roadmap checkboxes, 227 unique task IDs, no broken file or anchor target. No application checks run and none required: no code, dependency or configuration file is touched.
- Blocker: none. Q-K-05 constrains the dense half of DEC-115 and Q-INFRA-01 can override DEC-126, but neither blocks recording the decisions.
- Handoff: Every architecture choice is now recorded with its reason and rejected alternatives, so no implementation task needs to reopen one. Nothing here is built. After merge, the first implementation task is M1-03 — reconcile `pyproject.toml` with the DEC-124 manifest and create the DEC-125 package directories — followed by a thin vertical slice through M12: one real series into `bronze`, normalized into `silver`, queried through DuckDB, answered with lineage. Ask the organizer questions named in the status section in parallel; they have external latency and gate M4, M7 and M13's dense half.

### M0-HANDOFF active record

- Status: DONE — merged into `dev` at `a5d6ee8`; corrected on 2026-09-09 by the M1-10 completion task after Git showed the merge
- Owner: Codex for the initiating repository owner; Eray/Arda unassigned
- Branch: `docs/team-handoff-protocol`; base `fe5d44ab74e60633ef52c5ba4de7a5a5ca8fa083`
- PR: [#2](https://github.com/cagatayeroglu/KKB-DataTrio/pull/2) — merged, `docs/team-handoff-protocol` -> `dev` at `a5d6ee8`; branch deleted
- Commit: `0f73cbb077f0e091cbffe17be213e18fb6c723e4` implements the protocol; the PR head also includes this handoff-reference update
- Tests: PASS (2026-09-08): full relevant diff/contradiction review, `git diff --check`, Python standard-library link/anchor/task/evidence checks (57 tracked local links, 198 unique task IDs including only one new ID), fresh-`dev` ancestry, and stash hash preservation. Application/security/full checks NOT RUN by task scope
- Blocker: none for documentation; no CI workflow exists
- Handoff: Startup/claim/transfer rules and M0-DOC merge evidence are documented and validated. Review PR #2; merge remains required for M0-HANDOFF DONE. Then recheck claims and take M0-04 on a fresh branch from latest `dev`. This task's explicit Phase F opened its PR after document validation; subsequent implementation tasks use early draft claim PRs.

## Handoff notes

Preservation verified on 2026-09-08 in the originating KKB-DataTrio clone: named stash `day0-local-preservation-before-team-handoff-2026-09-08`, initially `stash@{0}`, stable object `49d3fd30cc56b5ca928976d22e3b993960650c85`. Its untracked tree (`^3`) contains exactly 11 files, all SHA-256 hashes equal to the pre-stash files. The stash remains unapplied; it is not pushed or present in a teammate's fresh clone. Stash ordinals can change, so locate by name/object rather than trusting `stash@{0}` later.

For a separately authorized Day 0 task only, first create a fresh runtime branch from updated `dev` and check for collisions. Inspect paths with `git ls-tree -r --name-only 49d3fd30cc56b5ca928976d22e3b993960650c85^3`; recover only the selected task's inputs from that tree. Full recovery, when the task explicitly covers all 11 files, uses `git stash apply 49d3fd30cc56b5ca928976d22e3b993960650c85`. Keep the stash until recovery is verified; do not pop/drop it or apply it to this documentation branch. No application file has been committed in either documentation delivery.

M0-01 starting commands for a configured Python >=3.12 development environment (not executed in this documentation task):

```bash
python -m pytest -q tests/unit/test_core_models.py
ruff check src/kkb_agent/core tests/unit/test_core_models.py
```

Record failures/tooling gaps and keep the task unchecked if either command fails. Do not use this small validation-only task to redesign shared contracts.

<a id="m1"></a>
# M1 — Generic data ingestion/profiling

Status: PARTIAL — M1-01 specification, M1-02 admission guards, M1-04/M1-05 CSV fixtures, M1-09 XLSX fixtures/sheet selection and M1-10 bounded XLSX loading are merged into `dev`. No CSV loader, profiler or adapter registry is established. The Day 0 SourceAdapter protocol remains stash-only, not delivered in `dev`.

## Objective

Turn supported unfamiliar tables into bounded, profiled data references with explicit semantics and provenance.

## Dependencies

M0 validated contracts for implementation. The engine question is closed by [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse), so M1-03 and the loader tasks below are no longer blocked. File exposure requires SEC-FILE-01/02.

## Tasks

- [x] M1-01 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-01-ingestion-profile-spec`. Specify the ingestion/profile result contract: data reference, source reference, columns/types, row count, date/numeric candidates, missingness, and unresolved semantics. [Specification and synthetic examples](INGESTION_PROFILE.md) validated; PR #4 merged into `dev` at `cbb51ad`, with the validated tree unchanged.
- [x] M1-02 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-02-file-admission-policy`. Specify extension/MIME/content checks, byte/row/column limits, and storage paths before implementing loaders.
- [ ] M1-03 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m1-03-runtime-dependencies`. Reconcile `pyproject.toml` with the DEC-124 manifest: add `duckdb`, `pandas>=2.2`, `pyarrow` and `python-calamine` as runtime dependencies, keep `openpyxl` for the untrusted path, and record the resulting environment. No loader behaviour change. Evidence: [M1-03 active record](#m1-03-active-record).
- [x] M1-04 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-04-synthetic-csv-fixture`. Add a synthetic UTF-8 CSV fixture with date, numeric, text, and missing values.
- [x] M1-05 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-05-csv-edge-fixtures`. Add alternate delimiter, quoted field, BOM/encoding, and decimal/thousands-separator fixtures with explicit expected parsing.
- [ ] M1-06 — Implement bounded CSV parsing; record which delimiter/encoding was used and reject ambiguous parsing safely.
- [ ] M1-07 — Detect date-like columns without silently choosing between ambiguous day/month interpretations.
- [ ] M1-08 — Detect numeric columns and report coercion failures without dropping rows silently.
- [x] M1-09 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-09-xlsx-fixtures`. Add single-sheet and multi-sheet XLSX fixtures; list sheets and require explicit selection when ambiguous.
- [x] M1-10 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-10-bounded-xlsx-loading`, merged and deleted. Implement XLSX loading with formula/macro and expansion limits from SECURITY. [PR #16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) merged into `dev` at `400fe58`, with the validated tree unchanged. Evidence: [completion record](#m1-10-completion-record).
- [ ] M1-11 — Record original filename as metadata, retrieval/ingestion timestamp, source identity, and safe data reference; never treat the filename as a destination path.
- [ ] M1-12 — Profile row/column counts, missingness, duplicate dates, date range, and frequency candidates; preserve unknowns.
- [ ] M1-13 — Return structured failures for empty CSV, header-only data, malformed rows, corrupt XLSX, and unsupported type.
- [ ] M1-14 — Test byte/row/column limits and mismatched extension/content before parser invocation.
- [ ] M1-15 — Add changed-column-name/unfamiliar-schema cases using the same adapter result contract.
- [ ] M1-16 — Test provenance survives ingestion and no private payload appears in error logs.
- [ ] M1-17 — Run targeted ingestion/profiling and file-boundary negative tests, touched-code lint, and the fast PR gate; reserve full checks for checkpoints or explicit requests.
- [ ] M1-18 — Record supported formats, limits, evidence, and the next normalization task.

## Acceptance criteria

Known fixtures produce exact expected row counts/types/source references. Ambiguous semantics remain unresolved. Empty, malformed, oversized, and mismatched files produce bounded structured failures. At least one unfamiliar CSV and multi-sheet XLSX fixture uses the same core contract without source-name conditionals.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; ingestion tests not implemented.
- Benchmark: Planned file/schema cases in EVALUATION.
- Notes: The Day 0 SourceAdapter protocol is stash-only, not shared CSV/XLSX support. M1-01 specifies observable results without changing runtime interfaces.
- Known limitations: Engine and parser limits not chosen; no safe file boundary.
- Handoff: M1-01 can specify examples now; implementation follows validated M0 contracts and engine decision.

### M1-01 active record

- Status: DONE — specification/example checks passed; authorized PR #4 merge verified on 2026-09-08
- Owner: Çağatay
- Branch: `feature/m1-01-ingestion-profile-spec`; base `ddcb5a74e90468c499246bf2bb7fed170391a7d5` after PR #3 merged
- PR: [#4](https://github.com/cagatayeroglu/KKB-DataTrio/pull/4) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: `de93177236ca015ae4172541ea92f91b700a3013` adds the specification; claim/M0-04 merge bookkeeping `ee868c43b03e1c9ee7ac9ee92c07bc110a4712fe`; merge `cbb51adbbdcdab48d17efdc72d104867b4f7295c` contains validated head `cb753864905f0534999da07f9331e7b41525d793` with an identical tree
- Tests: PASS (2026-09-08): full relevant diff/status/contract review; `python3.12 /private/tmp/kkb-m101-doc-check.py` (temporary standard-library document checker) parses the inline CSV/JSON and verifies 3 rows/3 columns, exact counts/missingness, candidate coverage, unknown-semantic records, date/number ambiguity oracles, local links/anchors and unique task IDs. Eleven edge-case expectations reviewed against the result rules, including header-only rejection required by M1-13. `git diff --cached --check` passed for the specification. Documentation-only task: application tests, `make quick`, full/security/release checks not run; 0 CI checks expected until M0-07.
- Evidence: [INGESTION_PROFILE](INGESTION_PROFILE.md) defines generic result/column fields, accepted versus selection-required/rejected outcomes, explicit uncertainty, bounded reporting, one complete synthetic example and 11 edge cases. No runtime behavior is claimed by these document checks.
- Limitations: Result specification delivered; numerical file/parser caps and storage policy belong to M1-02. Engine choice and validated M0 contracts remain prerequisites for runtime integration. No loaders, shared runtime types, framework/database choice, or Day 0 stash recovery.
- Blocker: none for this specification scope; no competing open PR/remote branch claim found before or after publication. Runtime prerequisites remain unresolved as above.
- Handoff: M1-01 is delivered. M1-02 was re-evaluated after merge: the policy/guard scope can proceed without engine selection or stash-only core types; ownership was checked and the fresh branch claimed. Keep the Day 0 stash unapplied.


### M1-02 active record

- Status: DONE — authorized PR #5 merge into `dev` verified on 2026-09-08; targeted validation and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-02-file-admission-policy`; original base `cbb51adbbdcdab48d17efdc72d104867b4f7295c`; merged updated `origin/dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003` without conflicts or history rewriting
- PR: [#5](https://github.com/cagatayeroglu/KKB-DataTrio/pull/5) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: implementation `b014b15de87a0d935f32f50ba7b58c24fbebf92e`; dev-sync `22d0fca5f321b486f051a7ec5b790896375e3053`; validated PR head/evidence `b03b120bb1071c352db493831cfa79aa19bd3ea6`; merge `e2287f70bc07ccec191eba5df84584e1df2b3836` contains that head with an identical tree. Completion bookkeeping is on fresh `docs/m1-02-completion` from this updated `dev`.
- Readiness: M1-01 is merged; no owner or competing open PR/remote task branch found before/after publication. The explicit task request authorized executable policy/guards and synthetic tests for the ROADMAP's admission/limits/storage objective. Standalone guards need no analytical engine or shared core-type integration.
- Tests: PASS (2026-09-08, Python 3.12.2) after dev sync: `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_policy.py` — 70 passed in 0.06s (0.97s wall). `make quick` — 117 passed in 3.08s (3.76s wall); `make pr` — 117 passed in 3.11s (3.95s wall), including repository Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Tools used temporary environments; dependencies unchanged. Relevant document/diff checks passed; no full/release checks run.
- Fast gate: PASS — both `make quick` and `make pr`. Pre-existing formatting in `tests/unit/test_smoke.py` and `scripts/check_secrets.py` was fixed separately by [PR #6](https://github.com/cagatayeroglu/KKB-DataTrio/pull/6), merged into `dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003`. Those files are identical to updated `dev` and absent from PR #5's diff. CI remains unconfigured (0 checks, not a CI pass).
- Evidence: [FILE_ADMISSION](FILE_ADMISSION.md) documents [standalone guards](../src/kkb_agent/ingestion_policy.py) and [synthetic negative tests](../tests/unit/test_ingestion_policy.py): metadata before reads, bounded bytes, CSV text/XLSX envelope checks, limit helpers, sanitized M1-01 rejection shape, generated private staging and cleanup. Admission preserves input bytes and makes no semantic inference.
- Limitations: No loaders/profile/API exposure. XLSX checks inspect metadata without extracting XML/cells; later loaders must enforce actual expansion, row/cell/time bounds and content rules. Row/column/field/profile helpers require loader integration; the 5-second parser budget is configuration only. Storage is transient under an operator-owned root, not a retention/backend decision.
- Blocker: none for M1-02; the separate baseline formatting fix resolved the fast-gate failure. Engine selection and validated M0 contracts remain prerequisites for later loader integration, not this independent policy scope.
- Handoff: M1-02 is delivered; no implementation changes were needed after the separate baseline fix. M1-03 still needs Q-TEAM-02. M1-04 is READY for a synthetic UTF-8 CSV fixture with date/numeric/text/missing values and explicit expected values/counts, preserving unknown semantics. No open PR or remote task-branch claim existed at the 2026-09-08 handoff check; recheck before claiming from latest `dev`. M1-04 is unassigned and not started. The Day 0 stash remains unchanged and unapplied.

### M1-03 active record

- Status: PARTIAL — implemented and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/m1-03-runtime-dependencies`; fresh `dev` base `c4506c8`
- PR: [#20](https://github.com/cagatayeroglu/KKB-DataTrio/pull/20) -> `dev`; draft claim published before implementation
- Commit: claim `60264e7`; implementation recorded in the PR
- Objective: Put the decided ingestion and analytics engine into the runtime manifest, and prove the environment actually works rather than only declaring it.
- Implementation: [pyproject.toml](../pyproject.toml) gains `duckdb>=1.1,<2`, `pandas>=2.2,<3`, `pyarrow>=17,<22` and `python-calamine>=0.2,<1`, each commented with the decision that requires it; `openpyxl` and `pydantic` stay and are commented likewise. [tests/unit/test_runtime_environment.py](../tests/unit/test_runtime_environment.py) verifies the environment against the values this project actually handles rather than asserting that imports succeed.
- Manifest interpretation: DEC-124's list is the **allowlist**, not a required installation set. `pyproject.toml` may hold a subset of it and never a superset. The remaining entries — `lancedb`, `networkx`, `statsmodels`, `ruptures`, `scipy`, `plotly`, `kaleido`, `pypdf`, `pdfplumber`, `httpx`, `tenacity`, `diskcache`, `json-repair`, `fastapi` — are added by the milestone that first uses them, so an unused library never appears in a dependency audit or slows CI before it earns its place. Adding one from the allowlist needs no new decision; adding anything outside it does.
- Tests: PASS (2026-09-09; Python 3.12.5, DuckDB 1.5.5, pandas 2.3.3, PyArrow 21.0.0, openpyxl 3.1.5, Pydantic 2.13.5). `pytest -q tests/unit/test_runtime_environment.py` — 9 passed in 1.06s. `make pr` equivalent — Ruff 0.16.6 format and lint clean over 20 files, 254 passed in 7.62s, Bandit 1.9.4 clean, secret scan clean. `mypy src` still reports the same 14 pre-existing errors, unchanged by this task; M0-08 still owns them.
- Coverage note: the tests assert the cases that would silently corrupt M12 — a blank measure that becomes `0.0`, Turkish text mangled by a different reader, a NULL that survives Parquet as a zero, decimal drift on a money column, and worksheet order being guessed. One test loads the same fixture through both the DEC-111 untrusted loader and the DEC-114 bulk reader and asserts they agree cell by cell, so the two ingestion routes cannot diverge unnoticed.
- Blocker: none.
- Handoff: The lakehouse engine is installed and verified; nothing uses it yet. No package directory was created — [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) says modules appear when a task actually needs them, and empty packages would be scaffolding for its own sake. Next is the first M12 slice: [M12-01](#m12) through M12-03, writing a real retrieved artifact into `bronze` and one normalized series into `silver` with explicit semantics. M0-08 remains READY and unowned.

### M1-04 active record

- Status: DONE — authorized PR #8 merge into `dev` verified on 2026-09-08; fixture validation and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-04-synthetic-csv-fixture`; base `64851f51172e47beef21a99cc6a0ae30ebb38a35` after PR #7 merged into `dev`
- PR: [#8](https://github.com/cagatayeroglu/KKB-DataTrio/pull/8) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: `72467db38c86caaa26b9554b177b3ca821da80a7` adds the fixture/test; validated PR head `01bc098d21fb8b1cf4080e5c71f9186789040387`; merge `0d4ecf946a3a74e1b995fadeb75e4e11fb121184` contains that head with an identical tree. Completion bookkeeping is recorded on the fresh M1-05 branch.
- Readiness: M1-01/M1-02 are merged and M1-02 DONE evidence is preserved. No competing open PR or remote task-branch claim found before/after claim publication on 2026-09-08. Fixture design is explicitly independent of Q-TEAM-02; M1-03 remains blocked and unstarted.
- Tests: PASS (2026-09-08, Python 3.12.2): `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_fixture.py` — 1 passed in 0.00s (0.73s wall); `make quick` — 118 passed in 3.12s (3.64s wall); `make pr` — 118 passed in 3.03s (3.86s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Fixture content also matches the existing specification example exactly. Relevant document links/status/commit references and diff checks passed. No full/release checks; CI remains unconfigured (0 checks, not a CI pass).
- Evidence: [Synthetic CSV](../tests/fixtures/ingestion/synthetic_utf8.csv) and [exact-table test](../tests/unit/test_ingestion_fixture.py). Three data rows plus header; `as_of` has three ISO date strings, `measure` has `100`, empty, `125`, and `label` has `A`, `B`, `C`. The test verifies presence, strict UTF-8 decoding, exact header/row order/width/values and the empty numeric cell.
- Scope: This is the existing synthetic example in [INGESTION_PROFILE](INGESTION_PROFILE.md): comma delimiter, header, empty field missing, dot decimal, no thousands separator, trimming or imputation. Counts and values are fixture expectations, not an implemented profile. Unit/frequency/time-role/stock-flow/cumulative/reset semantics remain unknown.
- Limitations: One static UTF-8 fixture only; the original example uses ASCII characters, a valid UTF-8 subset. No loader/profile, engine decision, alternate delimiter/BOM/locale fixtures, source-specific logic, dependency or runtime changes.
- Blocker: none in M1-04 scope; Day 0 stash is not required and remains unchanged/unapplied.
- Handoff: M1-04 is delivered. M1-05 was re-evaluated after merge: its fixture-only scope is independent of the engine decision; ownership was checked and the fresh branch claimed. M1-03 remains blocked on Q-TEAM-02. Preserve the Day 0 stash.

### M1-05 active record

- Status: DONE — authorized PR #9 merge into `dev` verified on 2026-09-08; targeted fixture tests and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-05-csv-edge-fixtures`; base `0d4ecf946a3a74e1b995fadeb75e4e11fb121184` after PR #8 merged into `dev`
- PR: [#9](https://github.com/cagatayeroglu/KKB-DataTrio/pull/9) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: implementation `bd34c1102e2c775dbe5892def54a44d6a9697519`; validated PR head `21aa686dd8ae63814e31d605dbbc5470d40a2387`; merge `a548a54291625888d482b59ba1947977e545cfac` contains that head with an identical tree. Completion bookkeeping is on fresh `docs/m1-05-completion` from updated `dev`.
- Readiness: Previously untriaged checkbox verified READY after M1-04 merge: M1-01 specification, M1-02 admission policy and M1-04 base fixture are delivered. No competing open PR or remote task-branch claim found before/after publication. The milestone explicitly permits fixture design before Q-TEAM-02; no unresolved architecture choice is needed.
- Tests: PASS (2026-09-08, Python 3.12.2): `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_csv_edge_fixtures.py` — 4 passed in 0.01s (0.78s wall); `make quick` — 122 passed in 2.90s (3.54s wall); `make pr` — 122 passed in 2.94s (3.80s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Relevant links/status/commit references and diff checks passed. No full/release checks; CI remains unconfigured (0 checks, not a CI pass).
- Evidence: [Fixture declarations](../tests/fixtures/ingestion/CSV_EDGE_CASES.md) link all four synthetic CSVs and document their exact interpretation; [four parameterized tests](../tests/unit/test_csv_edge_fixtures.py) pin presence, BOM flag, LF/UTF-8 decoding, header/order/width and every string cell. Cases cover semicolon delimiter, quoted commas/escaped quotes/embedded LF, UTF-8 BOM with `Örnek`/`çığ`, and both comma/dot numeric ambiguity.
- Scope: Numeric strings `1,234`/`2,345` and `1.234`/`2.345` remain unchanged. Each column has two documented decimal/grouping interpretations; none is selected. Empty cells remain missing and financial semantics remain unknown.
- Limitations: Fixture oracles only, using stdlib CSV inside tests. No runtime loader/profile, numeric normalization, engine/dependency/CI change, source-specific logic or private data.
- Blocker: none in M1-05 scope; M1-03 remains blocked on Q-TEAM-02. The Day 0 stash remains unchanged and unapplied.
- Handoff: M1-05 is delivered. M1-03 remains blocked on Q-TEAM-02; M1-06/07/08 retain the milestone's unresolved validated M0 contracts/engine prerequisites. M1-09 was checked next and stopped before claiming because no suitable XLSX-writing dependency is declared. See its blocker record; no substitute task was started.

### M1-09 active record

- Status: DONE — authorized PR #11 merge into `dev` verified on 2026-09-08; required validation passed and the merged tree is unchanged
- Owner: Çağatay
- Branch: `feature/m1-09-xlsx-fixtures`; fresh base `eb0922c6249d558248bc98341ed367e646beceef` after PR #10 merged
- PR: [#11](https://github.com/cagatayeroglu/KKB-DataTrio/pull/11) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: claim/decision `61219af177aa92b0e29f84120a90b71db2d46811`; implementation `e1c269f768f196f56d8acb0fbc6c96d5cff665bd`; validated head `d69a9176bd09b5cb70a202b267691ef026c4205e`; merge `3e705423b315c60f7c6da96825892f5279b54bcc` contains that head with an identical tree. Completion bookkeeping uses fresh `docs/m1-09-completion` from updated `dev`
- Readiness: M1-01/02/04/05 are delivered; M1-05 is DONE in updated `dev`. No competing open PR or remote task-branch claim found before/after publication on 2026-09-08. Explicit team approval of `openpyxl>=3.1,<4` is recorded in [DEC-111](DECISIONS.md#dec-111--openpyxl-for-the-untrusted-xlsx-boundary), resolving the previous writer blocker without deciding Q-TEAM-02.
- Dependency: Added `openpyxl>=3.1,<4` to normal runtime dependencies in [pyproject.toml](../pyproject.toml), using the existing manifest style. No existing lock file, no lock change/new strategy. Validation used openpyxl 3.1.5 with its required et-xmlfile 2.0.0 in a temporary environment; no second XLSX library added to the project.
- Tests: PASS (2026-09-08, Python 3.12.2): `python3.12 -m pytest -q tests/unit/test_xlsx_fixtures.py` with `PYTHONPATH=/private/tmp/kkb-m109-deps:src` — 19 passed in 1.05s (2.83s wall); `make quick` — 141 passed in 3.50s (4.36s wall); `make pr` — 141 passed in 3.41s (4.25s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Both gates used the same Python/dependency environment. All three fixture worksheets were reopened/rendered and visually checked; relevant links/status/diff checks passed. No full/release gate. CI remains unconfigured (0 checks is not a CI pass).
- Evidence: [Fixture declarations](../tests/fixtures/ingestion/XLSX_CASES.md), [generator](../scripts/generate_xlsx_fixtures.py), [targeted tests](../tests/unit/test_xlsx_fixtures.py), and [selection helper](../src/kkb_agent/xlsx_sheets.py). Exact sheet order/types/cells, date/numeric/text/missing values, UTF-8 text, ordinary XLSX package, repeatable generation, existing admission compatibility and selection edge cases are verified.
- Scope: `single_sheet.xlsx` has `Observations` (3 data rows, 3 columns); `multi_sheet.xlsx` adds `Categories` (2 rows, 2 columns). The helper lists worksheets in workbook order, preserves hidden-sheet ambiguity, excludes chart-only tabs and selects only an unambiguous single worksheet or an explicit exact name. Multiple sheets return `needs_input`/`SELECTION_REQUIRED`; invalid names return `needs_input`/`UNKNOWN_SHEET`; no worksheet returns `rejected`/`NO_WORKSHEETS`.
- Limitations: Helper accepts an already-open openpyxl workbook and reads no cells. Selection success is not a loaded table or `ok` profile. The future loader owns safe opening/closing, resource limits, corrupt-file handling and adapter integration. No full loader, profile, formulas/macros/external-link resolution, financial inference, real source data, analytical engine or CI implementation. Fixture bytes are repeatable with the same toolchain; supported library versions may serialize differently.
- Blocker: none for delivered M1-09. The Day 0 stash remains unchanged and unapplied.
- Historical PR #12 handoff: M1-09 was delivered with unchanged validated tree; the then-current global scan found no READY task. Its M0-01/M1-10 blockers are superseded by the post-PR #13 readiness record below. M1-03 remains blocked on Q-TEAM-02; no M1-09 implementation or validation was changed in this recheck.

### M1-10 completion record

- Status: DONE — [PR #16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) merged into `dev` on 2026-09-08 at `400fe58f49e2c9513f77799090030313dcc55088`; the merged tree matches validated head `4921d99`. Branch deleted; verified on 2026-09-09
- Owner: Çağatay
- Branch: `feature/m1-10-bounded-xlsx-loading`; fresh `dev` base `5f93df71b2ddefab7fb668f0daca89fddfb4f068`
- PR: [#16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) -> `dev`; draft claim published before implementation
- Commit: claim `ac1b681`; implementation `7a94c11666a53ffccd0bf8d604846adb07b56dc7`; subsequent scoped fix records the final validation below
- Objective: Implement XLSX loading with formula/macro and expansion limits from SECURITY.
- Dependencies satisfied: M0-01's [minimal data/source contracts](../src/kkb_agent/core/models.py), M1-01 [result specification](INGESTION_PROFILE.md), M1-02 [admission policy and configured guards](FILE_ADMISSION.md), and M1-09 [synthetic fixtures](../tests/fixtures/ingestion/XLSX_CASES.md)/[sheet selection](../src/kkb_agent/xlsx_sheets.py) are merged. [DEC-111](DECISIONS.md#dec-111--openpyxl-for-the-untrusted-xlsx-boundary) approves `openpyxl>=3.1,<4`, present in the runtime manifest. Q-TEAM-02 remains unresolved but does not block this already-approved XLSX parser; no analytical engine choice is needed.
- Ownership: READY/unowned dependencies reverified after PR #15 merge; no competing open/draft PR or remote task claim before publication, and only PR #16 found after publication. No unresolved team/organizer decision or stash recovery needed.
- Acceptance: Load the selected synthetic worksheet with exact values/types/counts and source/sheet identity; preserve explicit unknown semantics and ambiguous selection without silently choosing a sheet. Reuse admission before parsing and enforce actual ZIP expansion, entry/sheet/row/column/cell/field and parser-time bounds from M1-02 while reading, including corrupt XML/ZIP/relationships. Make formula/cached-value handling explicit without claiming recalculation/freshness; never execute formulas/macros or resolve external links. Return bounded sanitized failures, with no usable partial-table reference. Add small synthetic positive/negative tests with rejection and resource-limit instrumentation under [SEC-FILE-01](SECURITY.md#sec-file-01--file-admission-and-safe-storage)/[02](SECURITY.md#sec-file-02--parser-and-document-resource-limits); run targeted tests/touched-code lint, `make quick` and `make pr`.
- Implementation: [load_xlsx](../src/kkb_agent/xlsx_loader.py), [streamed package validation](../src/kkb_agent/_xlsx_package.py) and [synthetic regressions](../tests/unit/test_xlsx_loader.py). `load_xlsx(stream, filename=..., content_type=..., source=SourceRef(...), selection=None, limits=...)` returns `loaded`/`needs_input`/`rejected`; only `loaded` contains an in-memory table with an opaque data reference, existing DataContract, source/sheet fragment identity, ordered headers/column IDs and exact typed rows. This is not an M1-01 full profile or a reference registry; callers own registration/retention. First row is header; internal blanks stay None, duplicate/empty labels keep ordinal IDs, text dates/numbers are not coerced, and financial semantics stay explicitly unknown. Native Excel date/time styles use openpyxl without inferring business time semantics.
- Bounds / policy: Reuse M1-02 admission before the worker. Stream every package part to EOF for actual expansion/CRC/XML checks; enforce entry/sheet/grid/field budgets, safe internal relationship targets and actual ordered cell coordinates rather than declared dimensions. XML nesting is capped at 64 and nodes per part at `8 * max_cells + 100000`. Materialized/serialized table output also uses `max_expanded_bytes` (50 MiB default). Formula cells and cached values, defined names, DTD/entities, macros, external relationships, merged cells, cell errors and non-XML embedded/image parts are conservatively rejected; no recalculation or freshness claim. A fixed spawn worker is terminated/killed and reaped at `max_parser_seconds` (5 seconds default), with private generated output removed on success/failure; Linux additionally caps address space at max(512 MiB, 8 * expanded-byte budget). No user/model-provided executable target or filesystem path.
- Tests: PASS (2026-09-08; Python 3.12.2, openpyxl 3.1.5, existing temporary dependency environment): `python3.12 -m pytest -q tests/unit/test_xlsx_loader.py` with `PYTHONPATH=/private/tmp/kkb-m109-deps:src` — 52 passed in 4.97s (5.70s wall) with optional openpyxl LXML/DEFUSEDXML backends disabled to exercise the standard-library path used by CI. `make quick` — 245 passed in 9.54s (10.56s wall), using the existing local backend; `make pr` — 245 passed in 9.67s (11.15s wall) with those optional backends disabled, plus Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret scan. Tests cover exact fixtures/provenance/unknowns, ambiguous sheets, false dimensions, sparse gaps, empty/corrupt data, path/MIME rejection before worker start, formulas/caches, DTD/encoding/suffix bypass, relationships, actual expansion/output exhaustion, worker crash/timeout/reaping and private-output cleanup. No full/release checks, new dependencies or fixture changes.
- Remote check: Fast PR triggered on `7a94c11`; [first implementation run](https://github.com/cagatayeroglu/KKB-DataTrio/actions/runs/34260756751) failed on a new synthetic test that assumed one XML empty-tag spelling. Reproduced locally with `OPENPYXL_LXML=False`; fixed test generation to set explicit cell types through openpyxl and verified cached-formula fixture content for either writer. The next run exposed a Ruff-version layout difference in the same test helper; simplified that helper without changing its assertion. Both local fast gates pass; inspect the new head's Fast PR check on PR #16 before merge. No CI/dependency change was needed.
- Blocker: none in the delivered bounded XLSX scope. Q-TEAM-02 still blocks engine selection, not this DEC-111 parser. The strict-typing gap this code leaves in `make full` is tracked separately as M0-08, not as an M1-10 regression.
- Post-merge verification (2026-09-09, Eray): merge inspected on freshly fetched `dev`; branch `feature/m1-10-bounded-xlsx-loading` deleted locally and remotely, no open PR remains. Independent revalidation on the merged tree with a clean Python 3.12.5 virtual environment and the declared dependencies (Ruff 0.16.6, Bandit 1.9.4, mypy 1.20.2, openpyxl 3.1.5): `ruff format --check src tests scripts` — 19 files already formatted; `ruff check src tests scripts` — all checks passed; `pytest -q tests/unit --disable-warnings --maxfail=1` — 245 passed in 6.51s; `bandit -q -r src` — clean; `python scripts/check_secrets.py` — clean. `pytest -q` over the whole suite — 245 passed. `mypy src` — 14 errors, recorded under M0-08. `make pr` therefore passes and `make full` does not.
- Limitations / handoff: Caller controls input-stream I/O timeout and trusted source identity; parser deadline covers the worker, with bounded startup/cleanup/output handling overhead. Spawn callers need the standard main-module guard. No shared core contract change, full profiler, CSV loader, adapter registry/persistence, planner/provider/UI, new foundation task or stash recovery. M1-11 (filename/time/source/safe-reference integration) remains the next M1 candidate to triage; it is not claimed or promoted READY. M1-03 remains blocked on Q-TEAM-02.


## Handoff notes

Do not derive unit or stock/flow meaning from a numeric dtype. A parser can load a table while normalization remains blocked. Coordinate contract additions with the M0 editor, and send semantic fixtures to M2/M9.

<a id="m2"></a>
# M2 — Financial data semantics & normalization

Status: NOT STARTED. DataContract has fields for some semantics; transformation tools are absent.

## Objective

Ensure comparisons mean what they claim across time, scale, cumulative conventions, and financial measures.

## Dependencies

M1 contracts/data references; selected analytical engine; M8 evidence-record shape from M0. Source-specific semantic confirmation comes from M3 or user-supplied metadata.

## Tasks

- [ ] M2-01 — Specify required metadata for each operation and return explicit unknown-semantics errors when insufficient.
- [ ] M2-02 — Define date parsing, period labels, timezone/calendar conventions, and inclusive/exclusive range behavior.
- [ ] M2-03 — Detect and report missing periods and duplicate dates; require a documented duplicate/revision policy.
- [ ] M2-04 — Implement exact date intersection/union selection with explicit missing-value treatment and observed sample counts.
- [ ] M2-05 — Implement frequency comparison without assuming equal row spacing means a known reporting calendar.
- [ ] M2-06 — Define stock aggregation as a source-supported end-of-period policy; test boundary/missing final observations.
- [ ] M2-07 — Define flow aggregation over compatible periods; reject partial-period sums unless explicitly labeled.
- [ ] M2-08 — Test daily-to-weekly and weekly-to-monthly alignment, including weeks crossing month boundaries.
- [ ] M2-09 — Implement unit/scale conversion for TRY, thousand TRY, million TRY with recorded factors.
- [ ] M2-10 — Implement percentage/decimal/basis-point conversions; distinguish percentage-point from relative percent change.
- [ ] M2-11 — Implement non-reset cumulative-to-flow differences; require the preceding baseline for the first derived period.
- [ ] M2-12 — Implement yearly-reset cumulative conversion; test January/reset boundaries and missing prior periods.
- [ ] M2-13 — Preserve revisions and source vintages; do not collapse conflicting historical observations silently.
- [ ] M2-14 — Define index base-year compatibility and explicit rebasing; reject incompatible series without a valid overlap/reference.
- [ ] M2-15 — Implement deflation only with confirmed price-index/base/unit metadata and an explicit reference period.
- [ ] M2-16 — Record every transformation's parameters, inputs, output, assumptions, and limitations in workspace/evidence.
- [ ] M2-17 — Add identity/round-trip/hand-calculated fixtures and negative tests for unknown unit/frequency/reset semantics.
- [ ] M2-18 — Run targeted normalization tests and touched-code lint; add relevant smoke cases once the runner exists.
- [ ] M2-19 — Record which operation policies are supported and which still require clarification.

## Acceptance criteria

Hand-calculated fixtures match per-case tolerances; no unrecorded interpolation, aggregation, scaling, or deflation occurs. Unknown semantics fail before material computation. Every derived series identifies the exact source periods and transformation parameters.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; normalization tools/tests absent.
- Benchmark: Planned semantics catalog in EVALUATION.
- Notes: DataContract defaults unknown frequency/stock-flow and nullable cumulative/unit values; this does not enforce operation prerequisites.
- Known limitations: No transformation implementation or semantic policy acceptance yet.
- Handoff: Start M2-01 after M1 contract review; pair each policy with an independent numeric oracle.

## Handoff notes

Do not choose “sum” or “last” from frequency alone. Keep source vintage separate from ingestion time. Treat proposed semantic fields as contract changes when implemented, with the appropriate gate.

<a id="m3"></a>
# M3 — BDDK / EVDS integration

Status: PARTIAL — both sources are inventoried against the live services: [BDDK_SOURCE](BDDK_SOURCE.md) and [EVDS_SOURCE](EVDS_SOURCE.md) record their transports, units, frequencies and measured semantics. Live adapters remain BLOCKED on Q-DATA-01 and Q-NET-01/02.

## Objective

Support likely financial sources through the generic adapter contract without making them prerequisites for all analyses.

## Dependencies

M1 adapter/ingestion contract, M2 relevant semantics, M7 safe fetch before live retrieval, confirmed access/permissions. Do not invent endpoints, credentials, or series IDs.

## Tasks

- [ ] M3-01 — Obtain source access, approved endpoints/formats, credential requirements, and redistribution rules; record Q-DATA-01 evidence.
- [ ] M3-02 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m3-02-bddk-source-inventory`. Identify representative BDDK datasets and source-published frequency/unit/stock-flow semantics with exact references. Evidence: [M3-02 active record](#m3-02-active-record).
- [ ] M3-03 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m3-03-evds-source-inventory`. Identify representative EVDS series and date/unit/revision metadata with exact references. Evidence: [M3-03 active record](#m3-03-active-record).
- [ ] M3-04 — Create synthetic source-shaped discovery/inspection/load fixtures without private source payloads.
- [ ] M3-05 — Implement BDDK discovery/inspection mapping to the common contract.
- [ ] M3-06 — Implement BDDK load/selection through bounded approved retrieval. The endpoints, parameters and response shapes are in [BDDK_SOURCE](BDDK_SOURCE.md); the adapter must also supply BDDK's missing intermediate CA in an explicit trust bundle rather than disabling verification.
- [ ] M3-07 — Implement EVDS discovery/inspection mapping to the same contract. Use the keyless catalog endpoints in [EVDS_SOURCE](EVDS_SOURCE.md); never hard-code series codes, filter archived datagroups, and carry each series' published aggregation flags through to the contract.
- [ ] M3-08 — Implement EVDS load/date-range selection through bounded approved retrieval. Capture the `fe` and `serieList/baslangicBitis` POST payloads from the browser first — they are not documented. Parse the comma decimal separator explicitly and take `UNIXTIME` over the ambiguous `DD-MM-YYYY` label; request original observations at native frequency rather than server-side conversions.
- [ ] M3-09 — Preserve series IDs, titles, source release/vintage information, retrieval time, and limitations.
- [ ] M3-10 — Test similarly named wrong-series candidates and require explicit resolution of ambiguity. The fixture is real and recorded in [EVDS_SOURCE](EVDS_SOURCE.md): `TP.KBK.TRY.18` and `TP.KTF12` differ only by a comma, and `TP.BKR.TRY.18` and `TP.KKP.TRY.18` are identically named.
- [ ] M3-11 — Test changed columns, unavailable series, empty ranges, historical revisions, and rate/source failures.
- [ ] M3-12 — Keep authentication out of source locators, evidence, logs, and fixture files.
- [ ] M3-13 — Validate at least one cross-source comparison with confirmed unit/frequency policies.
- [ ] M3-14 — Verify an unfamiliar generic file still works without either named adapter.
- [ ] M3-15 — Run targeted adapter/network-boundary tests, lint, and the fast PR gate; record permitted live smoke separately from offline validation.
- [ ] M3-16 — Record source support, access blockers, permission evidence, and next integration task.

### M3-03 active record

- Status: PARTIAL — inventory complete and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/m3-03-evds-source-inventory`; fresh `dev` base `35eda16`
- PR: [#22](https://github.com/cagatayeroglu/KKB-DataTrio/pull/22) -> `dev`; draft claim published before implementation
- Commit: claim `34b1025`; inventory recorded in the PR
- Objective: Establish how TCMB EVDS is accessed and what it publishes for the series the reference scenario needs, with exact series codes as references rather than hard-coded constants.
- Scope: read-only inspection of the published service and a written inventory. No adapter implementation, no credential committed, no retrieved payload committed.
- Delivered: [EVDS source inventory](EVDS_SOURCE.md) covering access, the catalog endpoints, per-series metadata, frequencies, archived and base-year variants, and the observation response shape.
- Key findings: the documented `evds2.tcmb.gov.tr/service/evds` API is **gone** — every path 302s to EVDS3 — so published API-key instructions are stale and the "has the key been obtained" question may have no answer to obtain. EVDS3 exposes a **keyless** internal API at `/igmevdsms-dis/` whose catalog is 154 categories and 678 datagroups. **EVDS publishes the aggregation policy per series** (`DEFAULT_AGG_METHOD`, `SUMABLE`, `AVGABLE`, ...), so M12-09's metadata-driven policy is read rather than authored for these series; every rate carries `SUMABLE: 0`. The catalog declares **nine frequencies**, including separate Friday and Wednesday weekly anchors and `İŞ GÜNÜ` distinct from `GÜNLÜK`. 228 of 678 datagroups are archived and rank in ordinary searches.
- Demo-critical finding: `konut kredisi` returns four series — `TP.KBK.TRY.18` and `TP.KTF12` (weekly Friday, Akım) and `TP.BKR.TRY.18` and `TP.KKP.TRY.18` (monthly, Stok). The first two differ **only by a comma** in their display names and the last two are identically named, so no ranking method can separate them from text. This is the M3-10 wrong-near-match case, arriving in the demo's very first series.
- Cross-source consequence: BDDK publishes housing credit monthly while the EVDS flow rate is weekly-Friday, and no monthly variant of the flow rate exists. Frequency alignment is a prerequisite for the reference scenario, not an optimization.
- Parsing hazard: observation values arrive as **strings with a comma decimal separator** (`"46,750"` is 46.75). Reading that comma as a thousands separator is a 1000x error that still charts plausibly. Dates are `DD-MM-YYYY` and ambiguous below the thirteenth; `UNIXTIME` is present and should be authoritative.
- Evidence: catalog and two series lists retrieved and inspected, roughly a dozen requests. Counts quoted in the inventory were computed from the retrieved catalog, not transcribed.
- Tests: documentation tier. Full diff review; `git diff --check` clean; link and anchor pass over all tracked Markdown. No application checks apply — no code, dependency or configuration file is touched.
- Data handling: responses written to the ignored `data/raw/evds/` path and **not** committed. EVDS terms of use were not reviewed; M3-01 should read them before any scheduled retrieval.
- Blocker: none for inspection. The two POST payloads (`fe`, `serieList/baslangicBitis`) were not captured and must be read from the browser network panel when implementing M3-08.
- Handoff: both source inventories now exist, so M12 can be written against measured behaviour on both sides of the reference scenario. Natural next step is the first M12 slice using the series named here. M3-04 synthetic fixtures should now be shaped like these real responses, including the comma decimal and the weekly Friday anchor.

### M3-02 active record

- Status: PARTIAL — inventory complete and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/m3-02-bddk-source-inventory`; fresh `dev` base `33e3bc2`
- PR: [#21](https://github.com/cagatayeroglu/KKB-DataTrio/pull/21) -> `dev`; draft claim published before implementation
- Commit: claim `153a70a`; inventory recorded in the PR
- Objective: Establish what the BDDK bulletins actually publish — retrieval mechanism, table set, units, frequency and cumulative behaviour — with exact references, so M12's normalization rules are written against the real source rather than an assumed shape.
- Scope: read-only inspection of public published data and a written inventory. No adapter implementation, no retrieved payload committed, no credential involved.
- Delivered: [BDDK source inventory](BDDK_SOURCE.md) covering the monthly, weekly and FinTürk bulletins — transports, parameters, response shape, table lists, declared units and observed cumulative behaviour.
- Key findings: the three sources differ in transport, frequency **and scale**. FinTürk is quarterly and denominated in **Bin TL** while the monthly and weekly bulletins are **Milyon TL**, so joining them without reading each declared unit is a silent 1000x error. Cumulative behaviour is per table, not per source: monthly table 4 is a stock that decreases in 8 of 65 steps, while table 2 resets at all five observed January boundaries. The reference scenario's "kullanılan konut kredisi" maps to a stock, not disbursement, so it needs clarification rather than a lookup.
- Evidence: all 66 periods from 2021/1 to 2026/6 retrieved for monthly tables 2 and 4 with zero errors, 134 responses inspected. Values quoted in the inventory come from those responses. Retrieval used the published site at roughly three requests per second.
- Retrieval blocker found: `www.bddk.org.tr` omits its intermediate CA, so `httpx` against certifi fails with `CERTIFICATE_VERIFY_FAILED`. M3-06 must supply the missing issuer in an explicit trust bundle, and the demo environment must reproduce it. Disabling verification is not an acceptable resolution.
- Tests: documentation tier. Full diff review; `git diff --check` clean; link and anchor pass over all tracked Markdown. No application checks apply — no code, dependency or configuration file is touched. The quoted figures were read directly from the retrieved responses, not transcribed by hand.
- Data handling: responses were written to the ignored `data/raw/bddk/` path and are **not** committed; `git check-ignore` confirms `.gitignore:15` covers them. Redistribution remains Q-DATA-03.
- Blocker: none for inspecting published data. M3-01 access terms (Q-DATA-01) still gate a live retrieval adapter.
- Handoff: M12's normalization rules can now be written against measured behaviour. The next natural task is M3-03, the same inspection for EVDS, since the reference scenario needs the mortgage rate series and EVDS access may need a key. Revision behaviour, USD variants, the other 15 monthly tables and bank-group breakdowns remain uninspected.

## Acceptance criteria

Each enabled adapter returns the common contract and traceable source metadata, rejects wrong/ambiguous selections, and handles empty/outage paths. A confirmed permitted live sample is distinguished from synthetic testing. Generic ingestion works independently.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; adapters absent.
- Benchmark: Source-selection and schema-drift cases planned.
- Notes: BDDK/EVDS are intended integrations, not current supported runtime sources.
- Known limitations: Access, endpoint details, network rules, and data permissions unconfirmed.
- Handoff: Resolve M3-01 externally; use M3-04 after M1 for independent progress.

## Handoff notes

Answer Q-DATA-01 in OPEN_QUESTIONS; do not scatter endpoint assumptions across code or docs. No live network path is enabled before M7's safe-fetch control acceptance.

<a id="m4"></a>
# M4 — LLM / Kloudeks integration

Status: PARTIAL — non-networking stub exists. Live transport Status: BLOCKED on Q-K-01/02/03.

## Objective

Provide replaceable, bounded structured generation and synthesis using only confirmed Kloudeks runtime access.

## Dependencies

M0 contracts for offline validation; organizer endpoint/auth/model contract for live transport; SEC-KEY-01 and SEC-KLO-01 before real credentials/network behavior.

## Tasks

- [ ] M4-01 — Status: BLOCKED. Provider stub/tests are local-stash-only; obtain separately authorized task inputs before targeted tests/lint. Record environment parsing, SecretStr representation, and explicit pending-error behavior; live transport remains separately blocked.
- [ ] M4-02 — Cover every stub method's non-networking failure path, not only synthesis, with synthetic inputs.
- [ ] M4-03 — Record confirmed endpoint/authentication/credential-delivery details in Q-K-01 without recording secrets.
- [ ] M4-04 — Record model IDs, context limits, tool/JSON capabilities, and rate/timeout quotas in Q-K-02/03/04.
- [ ] M4-05 — Define capability reporting and structured-output fallback using confirmed platform features.
- [ ] M4-06 — Implement environment-based configuration validation and safe missing/invalid-config errors.
- [ ] M4-07 — Implement bounded organizer-approved transport behind LLMProvider; no hidden fallback to another provider.
- [ ] M4-08 — Parse structured output into the requested schema; reject extra/malformed fields and unsupported tool arguments.
- [ ] M4-09 — Add synthetic provider doubles for success, malformed JSON, refusal, timeout, rate limit, and unavailable model.
- [ ] M4-10 — Configure bounded retries/deadlines based on limits; separate transient transport failures from invalid-plan repair.
- [ ] M4-11 — Test credentials and sensitive prompts never appear in logs/errors/evidence.
- [ ] M4-12 — Measure one permitted live structured-generation request and record model/config metadata without secrets.
- [ ] M4-13 — Run targeted provider/transport/auth negative tests, lint, and the fast PR gate; keep live smoke separate from credential-free unit CI.
- [ ] M4-14 — Record offline versus live validation and any model-capability limitation.

## Acceptance criteria

Offline tests require no credentials/network. Live integration uses the confirmed Kloudeks route, validates responses, honors budgets, and produces sanitized structured failures. A pending stub cannot be counted as live acceptance.

## Evidence / implementation record

- Owner: Unassigned; suggested lane B.
- Branch: `feature/day0-core` for existing untracked stub.
- PR: —
- Commit: — for stub.
- Tests: `tests/unit/test_kloudeks_provider.py` exists locally/untracked; NOT RUN here.
- Benchmark: No provider benchmark executed.
- Notes: `src/kkb_agent/providers/kloudeks.py` reads provisional environment names and raises `KloudeksIntegrationPendingError`; no transport is implemented.
- Known limitations: `AnyHttpUrl` parsing is not a safe-network boundary; SecretStr representation is not comprehensive logging redaction.
- Handoff: M4-01 is ready; keep M4-07 blocked until organizer answers and security prerequisites are satisfied.

## Handoff notes

Do not infer OpenAI-compatible transport from a desired interface or invent an auth header. Synthetic doubles support planner work while external answers are pending.

<a id="m5"></a>
# M5 — Planning / tool routing

Status: PARTIAL — plan/workspace models and tool/provider protocols exist; registry, planner, executor, and multi-turn service are absent.

## Objective

Turn requests into validated tool runs and explicit state transitions with bounded repair.

## Dependencies

Validated M0 contracts; synthetic provider double or M4 live provider; at least one deterministic fixture tool for the first slice. The orchestration mechanism is settled by [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) and the workspace shape by [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag); no framework is required to specify tests.

## Tasks

- [ ] M5-01 — Define a minimal request -> plan -> validation -> execution -> verification lifecycle fixture.
- [ ] M5-02 — Resolve orchestration choice based on the bounded lifecycle; record the team decision before adding a framework.
- [ ] M5-03 — Implement a tool registry with unique system-owned names and argument schemas.
- [ ] M5-04 — Reject unknown tool names and validate per-tool arguments, rather than trusting the plan's generic argument dictionary.
- [ ] M5-05 — Validate dependency order, input/output reference existence, workspace ownership, and declared output type.
- [ ] M5-06 — Expose only relevant tool descriptions and source metadata to the planner.
- [ ] M5-07 — Implement deterministic format routing and metadata-based narrowing before semantic model routing.
- [ ] M5-08 — Generate a constrained AnalyticalPlan using the provider boundary; separate source content from system instructions.
- [ ] M5-09 — Execute the smallest valid plan using registered deterministic tools and structured ToolResult outcomes.
- [ ] M5-10 — Preserve explicit selected sources, contracts, derived references, assumptions, transformations, evidence, and tool results between turns.
- [ ] M5-11 — Add a series/change-date-range follow-up using existing workspace references.
- [ ] M5-12 — Invalidate/recompute dependent results when a selection or assumption changes; preserve historical lineage.
- [ ] M5-13 — Bound plan repairs, tool retries, steps, and total request deadline; abort repeated identical invalid plans.
- [ ] M5-14 — Distinguish clarification, unsupported request, recoverable outage, partial result, and terminal failure in the orchestration layer.
- [ ] M5-15 — Test invalid names/arguments/dependencies, stale references, partial tool failure, and failed-turn state preservation.
- [ ] M5-16 — Test injected source text cannot authorize a tool, URL, file path, or code execution.
- [ ] M5-17 — Run targeted planner/executor contract and negative tests, lint, and the fast PR gate; reserve full checks for checkpoints or explicit requests.
- [ ] M5-18 — Record supported lifecycle/turn operations, limits, validation, and next tool integration.

## Acceptance criteria

A synthetic request executes a typed plan through a registry and retains explicit workspace state. Invalid/unsafe calls fail before execution. Repairs stop at configured bounds. Failed turns do not silently overwrite previously verified results; stale derived results cannot be reused after changed assumptions.

## Evidence / implementation record

- Owner: Unassigned; suggested lane B.
- Branch: `feature/day0-core` for existing untracked models/protocols.
- PR: —
- Commit: — for scaffold.
- Tests: Some structural plan tests exist under M0; no registry/executor/multi-turn tests verified.
- Benchmark: Planner-failure and multi-turn cases planned.
- Notes: `AnalyticalPlan` currently checks ordered unique dependencies; `PlanStep.arguments` remains a generic JSON dictionary.
- Known limitations: A nonempty tool-name string is not allowlist validation; workspace model is not a persistence/service implementation.
- Handoff: After M0-01, start M5-01/03 around a deterministic fixture tool. The loop is our own code under DEC-113 and the workspace is the DuckDB artifact DAG of DEC-117; no framework evaluation is needed.

## Handoff notes

Do not claim “typed plans implemented” means execution is safe. Keep structural, registry/argument, semantic, and capability validation separately observable in tests and failure reports.

<a id="m6"></a>
# M6 — Deterministic analytics

Status: NOT STARTED.

## Objective

Produce reproducible financial/statistical results with stated prerequisites, sample counts, and limitations.

## Dependencies

M1 data references, M2 operation-specific semantic policies, M5 tool registration, M8 evidence-record interface. The causality method is fixed by [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits); basic descriptive tools do not.

## Tasks

- [ ] M6-01 — Define result schemas for values, units, periods, sample counts, warnings, and evidence references.
- [ ] M6-02 — Implement absolute change and relative change with explicit denominator/zero handling.
- [ ] M6-03 — Implement period comparison with exact date selection and transparent missing observations.
- [ ] M6-04 — Add hand-calculated change fixtures including negative values, zeros, and empty ranges.
- [ ] M6-05 — Choose/document a simple change/anomaly baseline and its minimum-sample/parameter policy.
- [ ] M6-06 — Implement the chosen anomaly/change method with deterministic output and recorded parameters.
- [ ] M6-07 — Implement association on aligned observations; report method, sample count, and missing-value policy.
- [ ] M6-08 — Reject or explicitly flag too few observations and constant series; avoid invalid/undefined statistics.
- [ ] M6-09 — Implement lag analysis with a clear lag sign, bounded search window, and per-lag sample counts.
- [ ] M6-10 — Test non-stationary/spurious-correlation examples and prevent an association result becoming causal prose.
- [ ] M6-11 — Implement the DEC-120 causality tool: lagged cross-correlation and Granger tests via `statsmodels`, with mandatory printed limitations and no "X causes Y" phrasing.
- [ ] M6-12 — Implement supported causality method only if justified/time permits; otherwise record explicit scope cut and abstention behavior.
- [ ] M6-13 — Reuse M2 deflation with reference-period evidence; never compare nominal and real measures silently.
- [ ] M6-14 — Generate deterministic table/chart data from tool outputs; formatting must not recompute material values through the model.
- [ ] M6-15 — Test numeric oracles, tolerances, warning semantics, and source/transformation links.
- [ ] M6-16 — Run targeted analytics tests/lint and relevant smoke cases; record per-tool support and next task.

## Acceptance criteria

Material numbers match independent expected values within stated per-case tolerances. Unsupported/undefined statistics return explicit outcomes. Lag direction, periods, units, sample counts, and assumptions are visible. Causal language is limited to what the selected method and evidence support.

## Evidence / implementation record

- Owner: Unassigned; lanes A/B with C reviewing oracles.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; analytics absent.
- Benchmark: Change and correlation fixture questions exist, but contain no numeric oracle or executing runner yet.
- Notes: A three-point fixture may test arithmetic, not a robust inferential conclusion.
- Known limitations: Engine and statistical-method policies unresolved.
- Handoff: Start M6-01/02 once minimum M2 semantics and M5 registry are usable.

## Handoff notes

Do not wait for advanced causality to deliver a tested change/association path. Review expected numbers independently of the implementation; identical formulas copied into tests are weak evidence.

<a id="m7"></a>
# M7 — External source / URL / document ingestion

Status: NOT STARTED. Live source policy is unresolved; safe-boundary tests/design can proceed independently.

## Objective

Add a second supported external source without allowing hostile content, URLs, or files to control execution.

## Dependencies

M1 ingestion contract, M2 relevant semantics, SEC-URL-01 and SEC-FILE-01/02 before exposure, Q-NET-01/02 for live access. PDF/image scope depends on Q-DATA-02 and extraction capability.

## Tasks

- [ ] M7-01 — Define one source safe-fetch API and structured outcomes; configure limits before implementing retrieval.
- [ ] M7-02 — Validate HTTP(S), reject credentials in URLs, and block loopback/private/link-local/metadata targets including IPv6.
- [ ] M7-03 — Validate DNS results and the actual connection destination; reject mixed public/private resolution and rebinding hazards.
- [ ] M7-04 — Handle redirects explicitly; revalidate every destination, cap hops, and avoid forwarding credentials across origins.
- [ ] M7-05 — Bound connect/read/total time, response/decompressed bytes, and content-type routing; do not buffer unlimited responses.
- [ ] M7-06 — Add negative tests for forbidden addresses/schemes, redirects, misleading content headers, and oversized/slow streams.
- [ ] M7-07 — Extract HTML tables/text with source fragment identifiers; ignore embedded instructions/scripts as authority.
- [ ] M7-08 — Route downloaded CSV/XLSX through the same local file guards and parser contracts as uploads.
- [ ] M7-09 — Implement bounded PDF text/table extraction if in required scope; retain page/table coordinates and extraction warnings.
- [ ] M7-10 — Handle scanned/unreadable PDFs explicitly; do not silently invent table cells.
- [ ] M7-11 — Decide image/OCR support only after input requirements and permitted capability are known; keep unsupported input errors usable meanwhile.
- [ ] M7-12 — Preserve filename/URL/page/sheet/cell metadata as untrusted provenance, with sensitive locator parts removed.
- [ ] M7-13 — Test malicious HTML, PDF text, and spreadsheet-cell instructions cannot change tool authority or trigger exfiltration.
- [ ] M7-14 — Add an external series to an existing workspace and verify prior state/evidence remain intact.
- [ ] M7-15 — Test changed schemas, missing tables, parser failure, unavailable source, and contradictory source metadata.
- [ ] M7-16 — Run targeted boundary/extraction negative tests, lint, and the fast PR gate; record limits, supported formats, and restrictions; reserve full checks for checkpoints or explicit requests.

## Acceptance criteria

Every enabled external retrieval uses the central boundary, including redirects and source adapters. All enabled parsers receive bounded validated content. Material extracted values retain source locations and validation status. Unsupported/ambiguous extraction results cannot become verified numerical claims.

## Evidence / implementation record

- Owner: Unassigned; lanes A/B, C owns adversarial fixtures.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; fetch/parser boundaries absent.
- Benchmark: External-format and injection catalog planned.
- Notes: Local file ingestion is not permission to fetch arbitrary URLs.
- Known limitations: No URL/document runtime support; internet rules, format scope, OCR capability unknown.
- Handoff: Build M7-01/02 against fake transport after contract review; enable live paths only after controls and policy are confirmed.

## Handoff notes

Model-suggested URLs still need full validation. If network-safe enforcement cannot be guaranteed, leave the live capability disabled and record the limitation; do not substitute an unrestricted HTTP client.

<a id="m8"></a>
# M8 — Verification / evidence / provenance

Status: PARTIAL — SourceRef, TransformationRecord, EvidenceRecord and workspace evidence fields exist; ledger service/verifier are absent.

## Objective

Prevent unsupported claims from reaching the answer and make accepted results reproducible from recorded inputs.

## Dependencies

Validated M0 record models; M1 source references; M5 tool runs; M2/M6 outputs as they become available. Minimal source/change verification starts before the full analytics catalog.

## Tasks

- [ ] M8-01 — Define material-claim types and their minimum source/run/period/column/transformation/validation requirements.
- [ ] M8-02 — Validate existing evidence models with targeted tests, including NOT_RUN defaults and unresolved references.
- [ ] M8-03 — Implement evidence registration and stable IDs tied to workspace/tool runs.
- [ ] M8-04 — Validate source, input/output, tool-run, and transformation references resolve; reject orphan evidence.
- [ ] M8-05 — Attach lineage at ingestion, transformation, and analytical execution time, not only during synthesis.
- [ ] M8-06 — Implement deterministic verification for basic change/numeric results against preserved input references.
- [ ] M8-07 — Verify units, periods, sample counts, and transformation prerequisites alongside values.
- [ ] M8-08 — Distinguish passed, failed, and not-run validation; partial results must identify exactly which claims are supported.
- [ ] M8-09 — Detect conflicting sources/vintages and surface the disagreement instead of choosing silently.
- [ ] M8-10 — Gate answer assembly so unsupported claims are omitted, qualified, or answered with abstention.
- [ ] M8-11 — Keep source citations separate from computation verification; a URL alone cannot prove a calculation.
- [ ] M8-12 — Test stale evidence after changed dates/assumptions and invalidate dependent claims.
- [ ] M8-13 — Render concise evidence summaries with safe locators and limitations for M10.
- [ ] M8-14 — Test missing source/run/transformation links, altered numeric output, and unsupported causal statements.
- [ ] M8-15 — Run targeted evidence/verifier/contract tests, lint, and the fast PR gate when changing shared models.
- [ ] M8-16 — Record verified claim types, evidence gaps, and the next tool needing verification.

## Acceptance criteria

For each supported material claim, a teammate can resolve source -> inputs -> transformation/tool run -> validation -> displayed value. Corrupt/missing/stale evidence prevents a verified answer. Verifier failures are visible and cannot be repaired by changing model prose alone.

## Evidence / implementation record

- Owner: Unassigned; suggested lane C with B integration.
- Branch: `feature/day0-core` for existing untracked record models.
- PR: —
- Commit: — for scaffold.
- Tests: Evidence/workspace behavior not established by a passing run.
- Benchmark: Evidence completeness/claim abstention cases planned.
- Notes: Current EvidenceRecord requires a source list but allows no tool run and defaults validation to NOT_RUN; extra verifier rules are still needed.
- Known limitations: No ledger service, referential checks, recomputation, or answer gate.
- Handoff: Begin M8-01/02 after core review; integrate one verified change claim before broadening methods.

## Handoff notes

Do not equate an evidence object with validated evidence. Keep original observations and derivations distinguishable, and avoid storing full private payloads in provenance records.

<a id="m9"></a>
# M9 — Evaluation / adversarial benchmark

Status: PARTIAL — benchmark schema, three synthetic cases, and one schema-loading test exist; no runner/numeric scorecard.

## Objective

Make correctness and recovery measurable early, with independent expected results and category-level regression evidence.

## Dependencies

M0 schema validation for the existing fixture; executable tools for behavioral scoring. Synthetic case/oracle design can run independently of live provider access.

## Tasks

- [ ] M9-01 — Status: BLOCKED. Evaluation schema/test/fixture files require separate delivery from the local stash; then run targeted tests/lint and record exactly what schema loading validates.
- [ ] M9-02 — Add explicit numeric expected outputs, units/periods, tolerances, expected abstentions, and multi-turn state assertions to the case design.
- [ ] M9-03 — Define source/series/tool/plan/numeric/semantics/evidence/recovery/latency metrics using EVALUATION.
- [ ] M9-04 — Implement a deterministic runner with case selection, stable IDs, seeded fixtures, and structured failure categories.
- [ ] M9-05 — Add an EVAL-SMOKE subset spanning change, unknown semantics, alignment, invalid tool, evidence failure, and follow-up state.
- [ ] M9-06 — Add machine-readable per-case outcomes and category denominators; distinguish unsupported, failed, not-run, and not-applicable.
- [ ] M9-07 — Test scorer behavior against deliberately wrong numbers, missing evidence, and false abstentions.
- [ ] M9-08 — Add daily/weekly/monthly, stock/flow, cumulative/reset, scale/rate, duplicates/missing/revision cases.
- [ ] M9-09 — Add CSV/XLSX/multi-sheet and changed-schema cases; include optional formats only with explicit support/abstention expectations.
- [ ] M9-10 — Add invalid-tool/argument, timeout, empty-result, outage, malformed-model, and repeated-repair cases.
- [ ] M9-11 — Add source-text injection cases for HTML, PDF, and spreadsheet cells without external exfiltration endpoints.
- [ ] M9-12 — Add spurious-correlation, too-few-observations, lag, non-stationarity, nominal/real, and causal-abstention cases.
- [ ] M9-13 — Add multi-turn add-series/date-change/deflation/assumption-correction cases with workspace assertions.
- [ ] M9-14 — Build toward 50–100 distinct adversarial cases; track coverage gaps rather than padding case counts.
- [ ] M9-15 — Reserve a teammate-authored holdout set; do not tune prompts on every case and then call it hidden performance.
- [ ] M9-16 — Record cold/warm and offline/live latency separately; capture model/config/case-set versions and actual runner commands.
- [ ] M9-17 — Define demo release thresholds after a measured baseline; do not invent a current pass rate or latency SLA.
- [ ] M9-18 — Run targeted runner/scorer tests/lint and smoke at feature gates; EVAL-FULL only at release/demo gates or explicit request.
- [ ] M9-19 — Record scorecard, highest-impact failures, and the next regression case.

## Acceptance criteria

The runner executes tools and compares independent expected results, rather than merely validating JSON. Reports expose denominators, failing cases/categories, evidence/abstention errors, and latency conditions. Each fixed material bug becomes a minimized regression. The final agreed corpus and thresholds are recorded, not assumed from its size.

## Evidence / implementation record

- Owner: Unassigned; suggested lane C.
- Branch: `feature/day0-core` for existing untracked scaffold.
- PR: —
- Commit: — for scaffold.
- Tests: `tests/unit/test_evaluation.py` exists; NOT RUN here.
- Benchmark: NOT RUN; `benchmarks/cases/synthetic.json` has `monthly-change`, `unknown-frequency`, and `simple-correlation` cases only.
- Notes: `src/kkb_agent/evaluation/models.py` defines case inputs and required tools/evidence/warnings; no numeric expected result, runner, or aggregate scorecard exists.
- Known limitations: Case-file schema validity would not establish analytical correctness. No `eval-smoke`/`eval-full` Make targets exist.
- Handoff: M9-01 is ready. Then design independent oracles and scorer behavior before expanding case count.

## Handoff notes

Update the command registry in EVALUATION when a runner actually exists. Keep live network tests out of ordinary deterministic smoke. Share failed case IDs and categories, not long raw model/input dumps.

<a id="m10"></a>
# M10 — UI / demo workflow

Status: NOT STARTED. Framework settled by [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end); hosting still depends on Q-INFRA-01 and demo format on Q-DEMO-01. Operator-flow specification can proceed.

## Objective

Let a teammate demonstrate the analysis, inspect evidence, and recover from expected failures without backend knowledge.

## Dependencies

A minimal M1/M4/M5/M6/M8 slice for live integration; confirmed demo environment/frontend choice. Wireframes and operator scripts can be specified earlier without choosing a framework.

## Tasks

- [ ] M10-01 — Specify operator steps: load/select source, ask question, inspect plan, inspect result/evidence, follow up, recover/reset.
- [ ] M10-02 — Confirm demo time, environment, audience interaction, and allowed fallback assets in Q-DEMO-01/02/03.
- [ ] M10-03 — Scaffold the DEC-123 client in `web/` — Next.js, Tailwind, shadcn/ui, TanStack Table, react-plotly.js, React Flow — against the agreed API contract; record installation and runtime consequences.
- [ ] M10-04 — Implement source upload/selection UI through validated backend boundaries.
- [ ] M10-05 — Show workspace source selections, assumptions, and unresolved semantics clearly.
- [ ] M10-06 — Show plan/progress and bounded failure states without exposing provider internals or secrets.
- [ ] M10-07 — Render deterministic table/chart outputs with units, periods, sample counts, and limitations.
- [ ] M10-08 — Add claim-level evidence/source/transformation/validation inspection.
- [ ] M10-09 — Support add-series and date-range follow-ups; make stale/recomputed results visible.
- [ ] M10-10 — Present clarification/abstention and unsupported-format errors as actionable operator steps.
- [ ] M10-11 — Add cancellation/reset semantics without mixing workspaces or deleting evidence unexpectedly.
- [ ] M10-12 — Measure latency by stage and optimize demonstrated bottlenecks; label permitted cached results and their vintage.
- [ ] M10-13 — Test one happy path, one clarification, one tool/source failure, and a multi-turn correction through the UI.
- [ ] M10-14 — Have a different teammate run the operator script and record friction/failures.
- [ ] M10-15 — Record UI validation, supported flows, and next rehearsal fix.

## Acceptance criteria

An uninstructed teammate can run the agreed demo script, inspect evidence, understand a failure, and complete a follow-up. Displayed values come from tool results. Framework choice and any fallback/cache are explicit; no unsupported live capability is implied.

## Evidence / implementation record

- Owner: Unassigned; suggested lane C with B integration.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; UI absent.
- Benchmark: Operator rehearsal not run.
- Notes: Backend contracts should drive UI; no frontend framework selected.
- Known limitations: Demo environment/duration, session persistence, and fallback permission unknown.
- Handoff: Specify M10-01 without committing to a framework; resolve M10-02/03 before implementation.

## Handoff notes

Do not use a polished screen to hide unsupported analysis or evidence gaps. Prefer one complete operator path over many incomplete screens.

<a id="m11"></a>
# M11 — Final hardening / rehearsal

Status: NOT STARTED. Final candidate, accepted scope, and release authorization required.

## Objective

Freeze a reproducible demo candidate, fix measured failure paths, and record an honest go/no-go decision.

## Dependencies

Accepted in-scope M0–M10 behavior, agreed evaluation thresholds, confirmed demo rules and environment, and authorized release actions. Do not invoke this milestone's checks during ordinary work.

## Tasks

- [ ] M11-01 — Confirm final supported sources/formats/tools and explicit cuts against demo/judging requirements.
- [ ] M11-02 — Record candidate revision plus any dirty/untracked changes; establish a reproducible authorized candidate before final scoring.
- [ ] M11-03 — Freeze dependency/config choices and document setup on the actual demo environment.
- [ ] M11-04 — Run `make full` at the final gate; record exact results and reviewed failures.
- [ ] M11-05 — Run the implemented EVAL-FULL corpus separately; compare categories/denominators with the prior baseline.
- [ ] M11-06 — Complete the applicable final-demo controls in SECURITY; disabled capabilities must be explicitly recorded.
- [ ] M11-07 — Rehearse cold start, main question, multi-turn follow-up, and unfamiliar supported-source scenario.
- [ ] M11-08 — Rehearse source outage/provider timeout/invalid input with bounded recovery and visible limitations.
- [ ] M11-09 — Verify permitted fallback/cache assets, source vintage labels, and offline behavior; do not invent organizer permission.
- [ ] M11-10 — Review logs/artifacts/screens for credential and private-data exposure; remove unauthorized retained data.
- [ ] M11-11 — Fix highest-impact measured failures, add regressions, and rerun affected checks; broaden only when the changed boundary requires it.
- [ ] M11-12 — Have a teammate who did not implement the final path run the complete script within confirmed demo time.
- [ ] M11-13 — Record go/no-go, unresolved risks, known limitations, and rollback/fallback operator instructions.
- [ ] M11-14 — Prepare a stable `dev -> main` checkpoint PR approximately every 3–4 days or at an important stable milestone; require full/release checks and demo-ready integrated state. Record PR/check status; merge only with explicit applicable authorization.
- [ ] M11-15 — Use optional Day 9 only for measured blockers and final changed-path rehearsal.
- [ ] M11-16 — Record final evidence and operator handoff.

## Acceptance criteria

The candidate is reproducible, applicable full checks and benchmark meet recorded thresholds, critical security/semantic/evidence failures are resolved, and another teammate completes the script. Unmet required acceptance means no-go or an explicitly agreed reduced scope; never convert a failed required item to complete.

## Evidence / implementation record

- Owner: Unassigned; all lanes with one named release coordinator before the gate.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; final checks explicitly out of scope for this documentation task.
- Benchmark: NOT RUN; full runner/corpus not yet available.
- Notes: `make full` is an application/static/security gate, not EVAL-FULL or rehearsal.
- Known limitations: No demo-ready implementation or measured release threshold established.
- Handoff: Remain on ordinary feature work until a candidate meets prerequisite acceptance; do not run release checks preemptively.

## Handoff notes

Keep the final record compact but reproducible: revision, environment, commands/results, scorecard reference, limitations, operator script, and permitted fallback. Publishing/merging is not implied by completion of local checks.

<a id="m12"></a>
# M12 — Lakehouse and medallion normalization

Status: NOT STARTED. Unblocked by [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse); no lakehouse code exists.

## Objective

Turn retrieved BDDK and EVDS sources into analysis-ready facts on a canonical time spine, with unit, frequency, stock/flow and cumulative semantics recorded explicitly rather than inferred. This milestone decides whether every downstream number is correct.

## Dependencies

M0-01 contracts and M1 loading for input; DEC-112 for the engine, DEC-114 for bulk spreadsheet reading, DEC-118 for lineage writes. M2 owns the normalization policy specifications this milestone implements. Live retrieval needs M3 and Q-DATA-01; synthetic and already-downloaded fixtures need neither.

## Tasks

- [ ] M12-01 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Create the DuckDB database and the `bronze`/`silver`/`gold` Parquet layout with a documented schema per layer; commit the database definition, which is a required deliverable. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [ ] M12-02 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Write every retrieved artifact to `bronze` with its bytes, SHA-256, source locator and retrieval timestamp; never edit a bronze object in place. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [ ] M12-03 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Define the `silver` series row shape: series ID, period, value, unit, scale, frequency, stock/flow, cumulative behaviour, source vintage, and an explicit unknown for each semantic that is genuinely unknown. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [ ] M12-04 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement the canonical time spine and period labelling, with inclusive/exclusive range behaviour and timezone/calendar conventions stated once. Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [ ] M12-05 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement cumulative detection: distinguish a series cumulative since first publication, a series that resets each January, and a plain flow series, and report low confidence rather than guessing. Detection is **per series, not per source** — [BDDK_SOURCE](BDDK_SOURCE.md) shows monthly table 4 is a stock and table 2 resets every January, in the same bulletin. Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [ ] M12-06 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement non-reset cumulative-to-flow differencing, requiring the preceding baseline for the first derived period. **No merge without unit tests.** Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [ ] M12-07 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement yearly-reset cumulative conversion with January and missing-prior-period boundary cases. **No merge without unit tests.** Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [ ] M12-08 — Status: IN PROGRESS. Owner: Eray; Branch: `feature/m12-08-frequency-alignment`. Implement frequency alignment for daily, weekly and monthly sources, including weeks that cross a month boundary; do not assume equal row spacing implies a known reporting calendar. Key on the declared frequency: EVDS publishes nine, including separate Friday and Wednesday weekly anchors and `İŞ GÜNÜ` distinct from `GÜNLÜK`. The reference scenario needs a weekly-Friday rate joined to a monthly stock, so this is on the critical path. Evidence: [M12-08 active record](#m12-08-active-record).
- [ ] M12-09 — Store the aggregation policy in each series' metadata — stock to period end, flow summed, rate by its recorded rule — and read it from metadata rather than branching on the series name in code. EVDS already publishes this per series (`DEFAULT_AGG_METHOD`, `SUMABLE`, `AVGABLE`, ...); carry those flags through instead of re-deriving them, and honour `SUMABLE: 0`.
- [ ] M12-10 — Implement unit and scale normalization for TRY, thousand TRY and million TRY with the applied factor recorded; make unit a required field and reject a series without one. This is not hypothetical: FinTürk publishes Bin TL while the monthly and weekly bulletins publish Milyon TL, and the unit appears only in a caption or a display label.
- [ ] M12-11 — Implement percentage, decimal and basis-point conversion, distinguishing percentage points from relative percent change.
- [ ] M12-12 — Preserve revisions and source vintages; never collapse conflicting historical observations silently.
- [ ] M12-13 — Build `gold` joins on the canonical spine with explicit missing-value treatment and observed sample counts.
- [ ] M12-14 — Write lineage nodes and edges for every transformation in this milestone; a produced cell without lineage fails review.
- [ ] M12-15 — Add hand-calculated fixtures for each cumulative, aggregation, frequency and unit rule, plus negative tests for unknown unit, unknown frequency and unknown reset behaviour.
- [ ] M12-16 — Run targeted normalization tests and touched-code lint; record which policies are implemented and which still need source confirmation.
- [ ] M12-17 — Handle index base-year variants explicitly: the consumer price index exists as 2003=100 and 2025=100, the housing price index as 2010=100, 2017=100 and current. Parse the base from the title, require an explicit reference period, and verify overlap before rebasing.

### M12-08 active record

- Status: IN PROGRESS — claim published before implementation
- Owner: Eray
- Branch: `feature/m12-08-frequency-alignment`; fresh `dev` base `e628169`
- PR: pending
- Commit: pending
- Objective: Reduce a higher-frequency series onto a lower-frequency spine using the aggregation its source declares, reporting how much of each target period was actually observed instead of hiding a thin month behind a confident number.
- Scope: alignment as pure functions. No retrieval, no lineage writing, no gold joins.
- Tests: pending.
- Blocker: none.
- Handoff: pending.

### M12-04..07 active record

- Status: PARTIAL — implemented and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/m12-05-cumulative-semantics`; fresh `dev` base `26e801d`
- PR: [#24](https://github.com/cagatayeroglu/KKB-DataTrio/pull/24) -> `dev`; draft claim published before implementation
- Commit: claim `4900c43`; implementation recorded in the PR
- Objective: Make cumulative series usable and safe — a canonical period spine, detection that distinguishes the accumulation behaviours measured in the BDDK bulletin, and conversion to flow that refuses rather than guesses.
- Scope: period arithmetic and cumulative semantics as pure functions over observations. No retrieval, no lineage writing, no gold joins, no frequency alignment.
- Implementation: [lakehouse/periods.py](../src/kkb_agent/lakehouse/periods.py) generates the canonical spine so two series that both call themselves monthly cannot disagree about which day a month ends on; [lakehouse/cumulative.py](../src/kkb_agent/lakehouse/cumulative.py) holds `detect_cumulative` and `to_flow`.
- Detection is deliberately unable to answer some questions. A fall outside January rules accumulation out with high confidence. A fall at every observed January boundary rules yearly reset in, at high confidence from two boundaries and low from one. A series that only ever rises returns **UNKNOWN with low confidence and a stated reason**: a since-inception cumulative and a growing stock are identical in the values, and the measured housing-credit series is exactly that case for months at a time. Resolving it needs source metadata, not arithmetic.
- Conversion refuses more than it computes. `to_flow` takes the **declared** kind, never a verdict, so a low-confidence guess cannot authorize a transformation. A yearly-reset January is returned as the published value because the year restarts there; the cross-boundary difference — which would have been −852,934 for net profit at 2026-01 — is never produced. A period with no usable predecessor, a gap in the spine or a missing input comes back `None` rather than a number spanning two periods or an implicit zero. A since-inception series needs an explicit baseline for its first period and returns `None` without one.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_cumulative.py` — 32 passed. Full gate: Ruff 0.16.6 format and lint clean over 27 files, `pytest -q tests/unit` — 322 passed in 8.57s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the new modules are strict-clean and M0-08 still owns the XLSX ones.
- Fixtures are real. Every series in the tests is published BDDK data quoted from the M3-02 retrieval: the housing-credit stock over its falling 2023/7–2024/3 stretch, the same stock rising monotonically through January 2026, and net profit across two real reset boundaries. Synthetic numbers would not have produced the case that matters, which is a genuine stock that looks cumulative.
- Two tests failed first and both were the test's fault, not the code's. One expected high confidence from a window containing a single January boundary; the code was right to say low, so the fixture was widened to two real boundaries. The other built a mixed-reset case too short to judge at all. Bandit then rejected a type-narrowing `assert`, correctly — asserts vanish under `-O` — so the loop was restructured to filter missing values up front instead.
- Blocker: none.
- Handoff: cumulative series can now be converted safely, and a stock can no longer be differenced into a fake disbursement series by accident. Nothing is persisted or attributed yet: `to_flow` returns observations and writes no lineage, which M12-14 and DEC-118 still require. Next is M12-08 frequency alignment, where the weekly Friday-anchored rate from EVDS meets the monthly stock from BDDK — the reference scenario needs that join and no monthly variant of the rate exists.

### M12-01/02/03 active record

- Status: PARTIAL — implemented and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/m12-01-lakehouse-foundation`; fresh `dev` base `074a874`
- PR: [#23](https://github.com/cagatayeroglu/KKB-DataTrio/pull/23) -> `dev`; draft claim published before implementation
- Commit: claim `abd078b`; implementation recorded in the PR
- Objective: Build the medallion container the rest of M12 writes into — the DuckDB database, an immutable bronze layer, and a silver layer that refuses to store a series whose semantics are not recorded.
- Scope: storage and semantics only. No source adapter, no retrieval, no cumulative conversion, no frequency alignment, no gold joins.
- Implementation: [lakehouse/store.py](../src/kkb_agent/lakehouse/store.py) and [lakehouse/semantics.py](../src/kkb_agent/lakehouse/semantics.py). `open_lakehouse(root)` creates `bronze/`, `silver/`, `gold/` and `kkb.duckdb`, and applies the schema in `SCHEMA` — that constant is the database definition the deliverable list asks for. `record_artifact` stores a payload under the SHA-256 of its bytes; `register_series` admits a series only if its semantics resolve; `append_observations` validates every period against the declared calendar before writing any of them; `export_silver` writes the silver tables to Parquet.
- Design rules worth keeping: bronze is addressed **by content**, so re-recording identical bytes is a no-op and two payloads can never collide on one id — history cannot be rewritten by a re-fetch. `read_artifact` re-hashes on the way out, so an edited file on disk is caught rather than served. Silver refuses a series with an unknown unit, scale, frequency, observation kind or accumulation behaviour, and refuses a re-registration that changes any of them underneath rows already validated against the old declaration. An observation batch is all-or-nothing.
- Core vocabulary extended: `Frequency` gained `BUSINESS_DAY`, `TWICE_MONTHLY` and `SEMIANNUAL`; `StockFlow` gained `RATE` and `INDEX`; new `WeeklyAnchor`, `Scale`, `CumulativeKind` and `Aggregation`. Every change is **additive** — no member removed or renamed — and each is driven by measured evidence: EVDS declares nine frequencies with two weekly anchors, BDDK publishes in million TRY while FinTürk publishes in thousand, and one BDDK bulletin contains three distinct accumulation behaviours that a boolean cannot express. Negative tests cover the new invariants. This is a shared contract change; [M0-11](#m0)'s editor/reviewer nomination remains open and unaddressed by this task.
- Tests: PASS (2026-09-09; Python 3.12.5, DuckDB 1.5.5). `pytest -q tests/unit/test_lakehouse.py` — 36 passed in 0.70s. Full gate: Ruff 0.16.6 format and lint clean over 24 files, `pytest -q tests/unit` — 290 passed in 8.59s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged** from the pre-existing baseline; the new modules are strict-clean and M0-08 still owns the XLSX ones.
- Coverage note: tests use the real published shapes rather than invented ones — a monthly stock in million TRY with the actual 2026/4–2026/6 housing-credit values, and a weekly Friday-anchored rate. The negative cases are the failures that would corrupt later work: a Thursday observation admitted into a Friday-anchored series, a Friday date accepted by a Wednesday anchor, a quarter ending in month 5, a month ending on the 29th, a re-registration that quietly changes million to thousand, a missing value that must stay NULL rather than become zero, and a partially valid batch that must write nothing.
- One rule was wrong and a test caught it: the first draft refused any series whose `cumulative` was not `NONE` unless it was a flow, which also refused `UNKNOWN`. `UNKNOWN` is not a claim that a series accumulates; only `SINCE_INCEPTION` and `YEARLY_RESET` are. Fixed, and `require_resolved()` still refuses the unknown at promotion time.
- Layout note: adds a `lakehouse` package, which is not in DEC-125's enumeration. [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) is amended to say that list names the packages the architecture sketch implied rather than a ceiling, and that a package mapping to a numbered ARCHITECTURE component may be added with its task.
- Blocker: none.
- Handoff: the container exists and refuses meaningless data; nothing normalizes yet. Next is M12-04 (canonical time spine) followed by M12-05/06/07, where the measured BDDK behaviour becomes hand-calculated fixtures: table 4 is a stock that must not be differenced into "disbursement", and table 2 resets every January so its within-year first difference is the monthly flow while January's published value is already the month. After that, M12-08 alignment for the weekly-Friday rate against the monthly stock, which the reference scenario needs.

## Acceptance criteria

A known synthetic bulletin with a January reset converts to the hand-calculated flow series exactly. A daily and a monthly series align on the canonical spine with correct sample counts. A series with unknown unit or unknown reset behaviour is rejected or surfaced as unknown, never silently normalized. Every value in `gold` traces to a `bronze` object through recorded transformations.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; no implementation.
- Benchmark: Planned semantic cases in EVALUATION.
- Known limitations: Real BDDK format variation across the 2021–2026 window is not yet inspected; task estimates assume it is worse than the current fixtures suggest.
- Handoff: Start from M12-01 through M12-03 on synthetic fixtures; real-source inspection belongs to M3-02/M3-03 and can proceed in parallel.

## Handoff notes

Do not infer unit or stock/flow meaning from a numeric dtype. A parsed table is not a normalized series. When cumulative behaviour is ambiguous, surface both interpretations or ask; a silently chosen one is indistinguishable from a correct one until the demo.

<a id="m13"></a>
# M13 — Semantic catalog and retrieval

Status: NOT STARTED. Unblocked by [DEC-115](DECISIONS.md#dec-115--hybrid-series-retrieval-over-lancedb-and-duckdb-fts) and [DEC-116](DECISIONS.md#dec-116--alias-dictionary-single-turkish-normalizer-and-a-measured-recall-floor); embedding model still needs Q-K-05.

## Objective

Let a Turkish financial question find the right series without hard-coded codes, and prove the retrieval works with a measurement rather than an assumption.

## Dependencies

M12 series metadata for content; DEC-122's `embed` method for vectors, which needs Q-K-05 for the model and its prefix convention. The alias dictionary, the normalizer, the BM25 index and the evaluation pairs need none of that and can proceed first.

## Tasks

- [ ] M13-01 — Define the catalog record: series ID, Turkish title, unit, frequency, source, coverage range and sample values.
- [ ] M13-02 — Pull the EVDS series catalog from its endpoint and index it; never hard-code series codes anywhere in the system.
- [ ] M13-03 — Implement one Turkish normalization function — dotted and dotless i, case folding, diacritic removal — and use it for both indexing and querying; add a test that fails if the two paths ever diverge.
- [ ] M13-04 — Build the DuckDB full-text index over catalog metadata for BM25 retrieval.
- [ ] M13-05 — Build the LanceDB collection for series metadata; keep the embedding call behind the provider interface so a blocked Q-K-05 does not block the rest.
- [ ] M13-06 — Implement reciprocal rank fusion over the lexical and dense result sets.
- [ ] M13-07 — Implement listwise reranking: hand twenty candidates to a small model, take the best five back as validated JSON.
- [ ] M13-08 — Write the alias dictionary of roughly fifty concepts mapped to series identifiers; an exact hit bypasses retrieval entirely.
- [ ] M13-09 — Write fifty question-to-series evaluation pairs by hand and measure recall@10; record the number.
- [ ] M13-10 — Add the second LanceDB collection for document chunks retrieved by the `web_url` tool.
- [ ] M13-11 — Test near-identical series titles: the system must resolve the ambiguity explicitly rather than pick the higher score.
- [ ] M13-12 — Record measured recall, the weighting in use, and which part of the pipeline each failure came from.

## Acceptance criteria

A recall@10 number exists and is recorded, not asserted. An exact alias term returns its series without touching the vector index. Two similarly named series produce an explicit resolution step rather than a silent choice. Every returned candidate carries its unit and frequency, so the caller cannot use it without knowing its semantics.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A or C.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; no implementation.
- Benchmark: The fifty pairs from M13-09 become a retrieval case set in EVALUATION.
- Known limitations: Embedding model, vector dimension, batch limits and any query/passage prefix are unresolved (Q-K-05). A wrong prefix convention silently halves recall on an E5-family model.
- Handoff: M13-03, M13-04, M13-08 and M13-09 need no model access; do them first, then measure what the dense half actually adds.

## Handoff notes

Do not trust embedding quality on Turkish financial vocabulary without the measurement. If measured recall is weak, move weight to BM25 and the alias dictionary; that is a supported outcome, not a failure to work around. A retrieval score is never evidence of correct semantics — the unit and frequency on the record are.
