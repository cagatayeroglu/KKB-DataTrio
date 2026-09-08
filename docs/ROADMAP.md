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
| 1 | M0-01 | BLOCKED — core inputs are in a local stash, not delivered in `dev` | Obtain authorized task inputs, then validate without redesign |
| 2 | M4-01 | BLOCKED — provider stub/test inputs are not delivered in `dev` | Obtain authorized inputs; live transport remains separately blocked |
| 3 | M9-01 | BLOCKED — evaluation schema/fixtures are not delivered in `dev` | Obtain authorized inputs; do not claim a scoring runner exists |
| 4 | M0-04 | DONE — [PR #3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) merged into `dev` at `ddcb5a7`; validated tree preserved | Ignore/config implementation and merge evidence recorded under M0-04 |
| 5 | M1-01 | DONE — [PR #4](https://github.com/cagatayeroglu/KKB-DataTrio/pull/4) merged at `cbb51ad`; validated tree unchanged | Generic result specification delivered |
| 6 | M1-02 | PARTIAL — Çağatay; `feature/m1-02-file-admission-policy`; [PR #5](https://github.com/cagatayeroglu/KKB-DataTrio/pull/5) | Guards, targeted tests and both fast gates pass; authorized merge pending |

READY requires satisfied prerequisites, no active owner, and the fresh-`dev` workflow below. M0-01, M4-01, and M9-01 need separately authorized Day 0 code delivery/recovery and a configured Python >=3.12 environment before returning to READY. Preserve the stash; never apply it to a documentation branch. A task explicitly covering that code may recover only its required files onto its fresh branch from latest `dev`, documenting origin. Without those inputs, choose the first independent eligible unclaimed entry; M0-04 and M1-01 have merged; M1-02 was re-evaluated as eligible and is now claimed. Never reuse `feature/day0-core` for unrelated work or invent validation to unblock the queue.

| Queued task | Task-specific acceptance once eligible |
| --- | --- |
| M0-01 | Existing core unit tests and core/test-file lint pass; record exact commands/results and unresolved gaps; no contract redesign |
| M4-01 | Existing provider unit tests and provider/test-file lint pass; record environment parsing, masked representation, and pending-error coverage; live transport remains blocked |
| M9-01 | Existing evaluation-schema test and evaluation/test-file lint pass; record schema-only validation; do not claim analytical execution or numeric scoring |
| M0-04 | Ignore rules and placeholder-only config exist; safe synthetic checks prove secrets/private/generated paths are ignored and the example remains trackable |
| M1-01 | A reviewed specification covers the listed result fields, unknown semantics, and testable examples; no engine selection or runtime contract change is implied |

No application validation is requested as part of the present documentation-only task. These are handoffs for subsequent work. If a READY task reveals a missing runtime/tooling prerequisite, record it rather than claiming success or installing dependencies without considering the task scope.

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
| [M1](#m1) | Generic ingestion/profiling | NOT STARTED; M1-01 READY | Days 1–2 |
| [M2](#m2) | Financial semantics/normalization | NOT STARTED | Days 2–3 |
| [M3](#m3) | BDDK/EVDS integration | BLOCKED for live access; fixtures can proceed after M1 | Days 1–5 as access permits |
| [M4](#m4) | Kloudeks | PARTIAL; live transport BLOCKED | Days 0–3 as access permits |
| [M5](#m5) | Planning/routing/workspace | PARTIAL — schemas/protocols only | Days 1–3 |
| [M6](#m6) | Deterministic analytics | NOT STARTED | Days 2–4 |
| [M7](#m7) | URL/documents/external inputs | NOT STARTED; live policy unresolved | Day 5 |
| [M8](#m8) | Verification/evidence/provenance | PARTIAL — record models only | Days 2–6 |
| [M9](#m9) | Evaluation/adversarial benchmark | PARTIAL — schema and three cases only | Days 0–6, then continuously |
| [M10](#m10) | UI/demo workflow | BLOCKED for framework/environment choice | Day 7; operator design can precede |
| [M11](#m11) | Hardening/rehearsal | NOT STARTED; upstream acceptance required | Days 8–9 |

## Dependency and scope policy

The critical path is M0 contracts -> M1 ingestion -> M2 minimum semantics -> M5 execution + M6 basic change -> M8 evidence -> M10 demo -> M11. M4 live access is required for the final live model path. M9 develops alongside each feature; do not wait until Day 6 to define expected outputs. M3/M7 depend on safe boundaries and source permissions. Milestone dependencies below name required subsets, not a requirement to finish every optional task upstream.

If behind schedule, cut fancy UI, optional image/exotic formats, router fine-tuning, advanced causality methods, deep observability, and extra agents. Keep typed plans, semantic correctness, evidence, safe inputs, and regressions. Record each cut and its demo consequence. Never advertise a cut/blocked format or live integration as supported.

<a id="m0"></a>
# M0 — Repository & development foundation

Status: PARTIAL. Tracked package/build/check definitions plus unvalidated Day 0 core work preserved in a local stash; only the original documentation task is DONE.

## Objective

Establish a safe, fast baseline and shared contracts that three teammates can extend without losing in-progress work.

## Dependencies

Local checkout and Python >=3.12 for later application validation. No live Kloudeks access is needed for the stub/contracts. Remote changes require explicit authorization.

## Tasks

- [ ] M0-01 — Status: BLOCKED. Core models/interfaces and `tests/unit/test_core_models.py` require separately authorized recovery/delivery from the local Day 0 stash. Then run targeted tests/lint on a fresh task branch; keep PARTIAL until merged into `dev`.
- [ ] M0-02 — Add targeted coverage for duplicate/self dependencies, invalid outcome combinations, and workspace serialization as needed; keep schema changes distinct from validation-only work.
- [ ] M0-03 — Validate the tracked package smoke test and existing `make quick` baseline; record unavailable tooling/failures honestly.
- [x] M0-04 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-04-local-config-hygiene`. Local ignore rules and placeholder-only `.env.example` passed targeted validation without real credentials; [PR #3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) merged into `dev` at `ddcb5a7`, with the validated tree unchanged.
- [ ] M0-05 — Reconcile provisional Kloudeks variable names with the stub; label them local conventions until Q-K-01 is answered.
- [ ] M0-06 — Inspect repository privacy, branch protection, and remote CI only in an authorized setup task; local branches alone do not prove remote settings.
- [ ] M0-07 — Add a fast feature-to-dev CI workflow in a later authorized task; no workflow exists in this snapshot.
- [ ] M0-08 — Add the separate manual/release full gate without making it run after every edit.
- [ ] M0-09 — Confirm synthetic/public-safe fixture policy and document where local private inputs may be stored before accepting them.
- [ ] M0-10 — Document an actual successful setup command/result on a teammate's Python >=3.12 environment.
- [ ] M0-11 — Record the validated core contract baseline and named editor/reviewer before shared contract changes.
- [ ] M0-12 — Run targeted/quick checks and the fast PR gate for foundation work, including boundary/contract negative tests; full checks belong to checkpoint gates or explicit requests.
- [ ] M0-13 — Record implementation evidence and the next ready task after validation.
- [x] M0-DOC — Status: DONE. Documentation checks passed; [PR #1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) merged both documentation commits into `dev` at `fe5d44a`; evidence recorded below.
- [ ] M0-HANDOFF — Status: PARTIAL. Document startup with zero chat history, visible task claims, ownership transfer, concise handoffs, and merge-based DONE. Owner: Codex for the initiating repository owner; Branch: `docs/team-handoff-protocol` from `fe5d44a`. Acceptance: the startup prompt selects an eligible unowned READY task using Git/PR history and targeted docs, preserves unrelated work, and stops on unresolved ownership/decisions; document checks pass and PR merges into `dev` before DONE.

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

### M0-HANDOFF active record

- Status: PARTIAL — document validation passed; awaiting PR review/merge
- Owner: Codex for the initiating repository owner; Eray/Arda unassigned
- Branch: `docs/team-handoff-protocol`; base `fe5d44ab74e60633ef52c5ba4de7a5a5ca8fa083`
- PR: [#2](https://github.com/cagatayeroglu/KKB-DataTrio/pull/2) — open, `docs/team-handoff-protocol` -> `dev`; no merge authorized for this second PR
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

Status: PARTIAL — M1-01 specification merged; M1-02 admission guards await integration. No loader/profile implementation is established. The Day 0 SourceAdapter protocol remains stash-only, not delivered in `dev`.

## Objective

Turn supported unfamiliar tables into bounded, profiled data references with explicit semantics and provenance.

## Dependencies

M0 validated contracts for implementation; Q-TEAM-02 for engine dependency selection. Contract examples and synthetic fixture design can proceed before the engine decision. File exposure requires SEC-FILE-01/02.

## Tasks

- [x] M1-01 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-01-ingestion-profile-spec`. Specify the ingestion/profile result contract: data reference, source reference, columns/types, row count, date/numeric candidates, missingness, and unresolved semantics. [Specification and synthetic examples](INGESTION_PROFILE.md) validated; PR #4 merged into `dev` at `cbb51ad`, with the validated tree unchanged.
- [ ] M1-02 — Status: PARTIAL. Owner: Çağatay; Branch: `feature/m1-02-file-admission-policy`. Specify extension/MIME/content checks, byte/row/column limits, and storage paths before implementing loaders.
- [ ] M1-03 — Select the analytical/parsing dependency only after the team records Q-TEAM-02/DECISIONS outcome.
- [ ] M1-04 — Add a synthetic UTF-8 CSV fixture with date, numeric, text, and missing values.
- [ ] M1-05 — Add alternate delimiter, quoted field, BOM/encoding, and decimal/thousands-separator fixtures with explicit expected parsing.
- [ ] M1-06 — Implement bounded CSV parsing; record which delimiter/encoding was used and reject ambiguous parsing safely.
- [ ] M1-07 — Detect date-like columns without silently choosing between ambiguous day/month interpretations.
- [ ] M1-08 — Detect numeric columns and report coercion failures without dropping rows silently.
- [ ] M1-09 — Add single-sheet and multi-sheet XLSX fixtures; list sheets and require explicit selection when ambiguous.
- [ ] M1-10 — Implement XLSX loading with formula/macro and expansion limits from SECURITY.
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

- Status: PARTIAL — implementation, targeted validation and both fast gates passed; merge into `dev` still required
- Owner: Çağatay
- Branch: `feature/m1-02-file-admission-policy`; original base `cbb51adbbdcdab48d17efdc72d104867b4f7295c`; merged updated `origin/dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003` without conflicts or history rewriting
- PR: [#5](https://github.com/cagatayeroglu/KKB-DataTrio/pull/5) — open into `dev`; user authorized merge after scope/conflict review and passing local fast gates
- Commit: `b014b15de87a0d935f32f50ba7b58c24fbebf92e` implements guards/tests/policy; claim/M1-01 bookkeeping `f0e7d173bc1a5d7667a9b8fa4db4e99874d0d268`; dev-sync merge `22d0fca5f321b486f051a7ec5b790896375e3053`; M1-02 merge evidence pending
- Readiness: M1-01 is merged; no owner or competing open PR/remote task branch found before/after publication. The explicit task request authorized executable policy/guards and synthetic tests for the ROADMAP's admission/limits/storage objective. Standalone guards need no analytical engine or shared core-type integration.
- Tests: PASS (2026-09-08, Python 3.12.2) after dev sync: `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_policy.py` — 70 passed in 0.06s (0.97s wall). `make quick` — 117 passed in 3.08s (3.76s wall); `make pr` — 117 passed in 3.11s (3.95s wall), including repository Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Tools used temporary environments; dependencies unchanged. Relevant document/diff checks passed; no full/release checks run.
- Fast gate: PASS — both `make quick` and `make pr`. Pre-existing formatting in `tests/unit/test_smoke.py` and `scripts/check_secrets.py` was fixed separately by [PR #6](https://github.com/cagatayeroglu/KKB-DataTrio/pull/6), merged into `dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003`. Those files are identical to updated `dev` and absent from PR #5's diff. CI remains unconfigured (0 checks, not a CI pass).
- Evidence: [FILE_ADMISSION](FILE_ADMISSION.md) documents [standalone guards](../src/kkb_agent/ingestion_policy.py) and [synthetic negative tests](../tests/unit/test_ingestion_policy.py): metadata before reads, bounded bytes, CSV text/XLSX envelope checks, limit helpers, sanitized M1-01 rejection shape, generated private staging and cleanup. Admission preserves input bytes and makes no semantic inference.
- Limitations: No loaders/profile/API exposure. XLSX checks inspect metadata without extracting XML/cells; later loaders must enforce actual expansion, row/cell/time bounds and content rules. Row/column/field/profile helpers require loader integration; the 5-second parser budget is configuration only. Storage is transient under an operator-owned root, not a retention/backend decision.
- Blocker: none for M1-02; the separate baseline formatting fix resolved the fast-gate failure. Engine selection and validated M0 contracts remain prerequisites for later loader integration, not this independent policy scope.
- Handoff: Verify PR #5 scope and mergeability, perform the authorized merge, then record verified completion on a fresh documentation branch. M1-03 still needs Q-TEAM-02; M1-04 is the next eligible independent task (synthetic UTF-8 CSV fixture with expected values), subject to a fresh ownership check. Do not start it in this closure task. Keep the Day 0 stash unapplied.

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

Status: BLOCKED for live adapters — Q-DATA-01 and Q-NET-01/02. Offline adapter fixtures can proceed after M1.

## Objective

Support likely financial sources through the generic adapter contract without making them prerequisites for all analyses.

## Dependencies

M1 adapter/ingestion contract, M2 relevant semantics, M7 safe fetch before live retrieval, confirmed access/permissions. Do not invent endpoints, credentials, or series IDs.

## Tasks

- [ ] M3-01 — Obtain source access, approved endpoints/formats, credential requirements, and redistribution rules; record Q-DATA-01 evidence.
- [ ] M3-02 — Identify representative BDDK datasets and source-published frequency/unit/stock-flow semantics with exact references.
- [ ] M3-03 — Identify representative EVDS series and date/unit/revision metadata with exact references.
- [ ] M3-04 — Create synthetic source-shaped discovery/inspection/load fixtures without private source payloads.
- [ ] M3-05 — Implement BDDK discovery/inspection mapping to the common contract.
- [ ] M3-06 — Implement BDDK load/selection through bounded approved retrieval.
- [ ] M3-07 — Implement EVDS discovery/inspection mapping to the same contract.
- [ ] M3-08 — Implement EVDS load/date-range selection through bounded approved retrieval.
- [ ] M3-09 — Preserve series IDs, titles, source release/vintage information, retrieval time, and limitations.
- [ ] M3-10 — Test similarly named wrong-series candidates and require explicit resolution of ambiguity.
- [ ] M3-11 — Test changed columns, unavailable series, empty ranges, historical revisions, and rate/source failures.
- [ ] M3-12 — Keep authentication out of source locators, evidence, logs, and fixture files.
- [ ] M3-13 — Validate at least one cross-source comparison with confirmed unit/frequency policies.
- [ ] M3-14 — Verify an unfamiliar generic file still works without either named adapter.
- [ ] M3-15 — Run targeted adapter/network-boundary tests, lint, and the fast PR gate; record permitted live smoke separately from offline validation.
- [ ] M3-16 — Record source support, access blockers, permission evidence, and next integration task.

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

Validated M0 contracts; synthetic provider double or M4 live provider; at least one deterministic fixture tool for the first slice. Resolve Q-TEAM-01 before framework adoption; no framework is required to specify tests.

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
- Handoff: After M0-01, start M5-01/03 around a deterministic fixture tool; handle Q-TEAM-01 before framework adoption.

## Handoff notes

Do not claim “typed plans implemented” means execution is safe. Keep structural, registry/argument, semantic, and capability validation separately observable in tests and failure reports.

<a id="m6"></a>
# M6 — Deterministic analytics

Status: NOT STARTED.

## Objective

Produce reproducible financial/statistical results with stated prerequisites, sample counts, and limitations.

## Dependencies

M1 data references, M2 operation-specific semantic policies, M5 tool registration, M8 evidence-record interface. Exact advanced causality method depends on Q-TEAM-04; basic descriptive tools do not.

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
- [ ] M6-11 — Resolve exact causality method/prerequisites in Q-TEAM-04 before implementing a causal/statistical test.
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

Status: BLOCKED for implementation choice — Q-TEAM-03 and Q-DEMO-01. Operator-flow specification can proceed.

## Objective

Let a teammate demonstrate the analysis, inspect evidence, and recover from expected failures without backend knowledge.

## Dependencies

A minimal M1/M4/M5/M6/M8 slice for live integration; confirmed demo environment/frontend choice. Wireframes and operator scripts can be specified earlier without choosing a framework.

## Tasks

- [ ] M10-01 — Specify operator steps: load/select source, ask question, inspect plan, inspect result/evidence, follow up, recover/reset.
- [ ] M10-02 — Confirm demo time, environment, audience interaction, and allowed fallback assets in Q-DEMO-01/02/03.
- [ ] M10-03 — Choose the frontend approach through Q-TEAM-03; record installation/runtime consequences.
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
