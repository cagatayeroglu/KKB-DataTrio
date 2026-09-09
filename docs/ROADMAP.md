# Mission / success criteria

Deliver an evidence-backed financial analyst by the organizer's **20 September 2026** development deadline, with a live demo on **17 October 2026** for teams that advance ([DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope)). A teammate must be able to load a supported unfamiliar source, ask a financial question, inspect a typed plan, receive deterministically computed results, and trace every material claim to data, transformations, and validation. A follow-up question must reuse explicit analysis state correctly.

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

# Current Project Status

- Last verified `origin/dev`: **`0dbeef12733ea854acbef88e880815a86b583078`** (PR #39).
- Verification: **2026-09-10**, after PR #39 merge; local `dev` fast-forwarded to `origin/dev`, `origin` carries only `dev` and `main` so no task branch or draft claim is outstanding, and `.env` is untracked and ignored. The previous header still named `dfcd7c5`/PR #38 and is corrected here.
- Schedule: **Day 4 of the confirmed 7–20 September 2026 development window** ([DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope)); 11 days remain to the reviewed-repository deadline. Final Day is 17 October 2026. The earlier "8–9 day" figure was an internal estimate, never an organizer date.
- Phase: Foundation available; complete the **first real end-to-end slice**. The offline planner/registry/executor, lakehouse SQL tool, definition DAG and numeric-binding verifier exist. Real-source ingestion, complete result/workspace/proof integration and live Kloudeks remain delivery work.
- Active task: **organizer primary-source documentation sync / Eray / IN PROGRESS**, `docs/organizer-brief-mia-sync`; documentation only, no implementation task claimed. M7-05 and M7-06 direct-GET negative coverage are DONE from merged PR #38. M3-06 is not started: Q-DATA-01 and Q-NET-01/02 remain OPEN and block live execution. The independent READY queue is unchanged.
- Product/retrieval documentation synchronization: **DONE**, PR [#34](https://github.com/cagatayeroglu/KKB-DataTrio/pull/34) merged into `dev` at `41e302c`; final content `e2029ea`, document checks and Fast PR gate PASS (55s). DEC-129/130 and the reconciled current status are present in the merged tree.
- Organizer primary-source synchronization: **PARTIAL** — implemented, unchecked until merged. Owner Eray; Branch `docs/organizer-brief-mia-sync`; PR pending. Records [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) (kick-off calendar, delivery form, demo-day input scope, technology expectations) and amends DEC-129 with the primary MIA guide's literal OCR/embedding contracts and error semantics; narrows Q-K-01/04/05, Q-DATA-01, Q-DEMO-01, Q-INFRA-01, Q-NET-02, Q-DEV-02 and sharpens Q-DEV-01. Documentation and the `.env.example` template only; no runtime behaviour, dependency or test-policy change. `.env.example` values stay blank so `test_environment_template_has_only_blank_values` needed no exception. Tests: `make quick` 892 passed / 16.36s; `make pr` 892 passed / 16.07s with Ruff format/lint, Bandit and secret scan clean; internal Markdown link/anchor check 0 broken.
- Fast gate: M7-05 delivery on PR #38 — **340 targeted / 892 unit tests PASS**, `make quick` 17.30s, `make pr` 16.73s including Ruff format/lint, Bandit and secret scan (Python 3.12.2). Final-head GitHub Fast PR gate PASS (59s), verified before merge. These are existing delivery results; no application checks rerun for this documentation-only closure.
- Known failing gate: **M0-08** — 14 strict mypy errors reported through PR #32, originating in the XLSX modules. Full/release validation is not established. Do not infer a green release from a green `make pr`; no full/release checks run in this task.
- Critical implementation gaps: CSV/profile and source adapters; source POST/trust configuration and redirect following; typed financial results/run/snapshot identity; workspace stale-result rejection/recomputation and loop integration; second-path verifier and answer gate; catalog retrieval; remaining `web_search`, `web_url`, `anomaly`, `causality`, `change_detection`; **document extraction behind `web_url` (HTML/PDF/XLSX/image), now a confirmed demo-day requirement**; benchmark runner; API/UI/deployment.
- External blockers (organizer primary-source review 2026-09-10): [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) now also records the **literal OCR request contract, the embedding call shape and the documented `401`/`403`/`429` semantics** from the primary MIA guide. The MIA API key is **provisioned** and held only in the operator-local ignored `.env`; Q-K-01 is narrowed to an unexercised live smoke. Q-K-02/03/04 still cover context/output capacity, native tool/JSON guarantees and the numbers behind `429`; a `vllm_xargs` parameter reveals a vLLM server but guarantees no structured-output feature. Q-K-05 needs the **vector dimension measured** from the first authorized live call, not asked. Q-DEMO-01, Q-INFRA-01, Q-NET-02, Q-DATA-01 and Q-DEV-02 gained real answers from [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) and are narrowed. **Q-DEV-01 is now the most urgent question**: the kick-off deck's development-process wording is genuinely ambiguous about coding assistants and must be asked on Slack, not assumed. Q-DATA-03, Q-NET-01, Q-INFRA-02 and Q-DEMO-02/03 remain open. Q-TEAM-01..05 were answered in PR #19.
- Confirmed scope changes from [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope): reading **prompt-supplied URLs (PDF/Excel/image/text) is a required demo-day capability**, not an optional M7 extra; a **live deployed** solution is expected on Final Day; delivery is by granting KKB access to the private repository; both sources are bounded to **2021-01 – 2026-06**.
- Current direction: [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline) supersedes DEC-127 with initial lexical + dense hybrid retrieval; DEC-115 remains historical/SUPERSEDED. [DEC-128](DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence) records product direction. Neither claims implementation. Core ingestion/results/workspace/verifier/live provider/required tools precede broad differentiation.

## Ordered next safe tasks

All READY entries below are unowned, with Branch/PR/Commit **—**, Tests **NOT RUN for that task**, and no published claim at verification. Completed M7-05/06 are recorded below and excluded from this queue; no new task is claimed by this closure. Recheck claims immediately before starting. This is the single selection queue; unchecked backlog elsewhere is not implicitly READY.

| Order | Task / status | Satisfied prerequisites | Acceptance / handoff |
| --- | --- | --- | --- |
| 1 | **M6-01 — READY** | Core records, M5 registry and M6-20 lakehouse result exist; DEC-112/119/128 confirm deterministic/evidence direction | Define the narrow result schema for values, units, periods, sample counts, warnings and evidence references. Keep unresolved semantics explicit; test serialization and invalid/missing metadata. Specify how run/result identity will connect to M5/M8; do not implement a broad proof engine here. Unblocks actual tool/workspace/verifier integration. |
| 2 | **M1-06 — READY** | M1-01/02/03/04/05 and core contracts merged; engine decision settled | Bounded CSV parsing with explicit delimiter/encoding and ambiguity rejection, synthetic fixture oracles, targeted limits/negative tests and fast PR gate. No source-specific logic. |
| 3 | **M3-04 — READY** | Both source inventories and generic ingestion specification merged | Small synthetic source-shaped discovery/inspection/load fixtures; preserve comma decimals, native cadence and unknown semantics; test content without live calls/private payloads. |
| 4 | **M13-01 — READY** | Series metadata and source inventories exist; DEC-130 fixes hybrid baseline direction | Catalog record with identity/title/unit/frequency/source/coverage/sample values plus explicit unknown/archived metadata. Test round-trip and ambiguity; no live catalog fetch or embeddings. |
| 5 | **M13-03 — READY** | Confirmed DEC-116/130; no model/source access needed | One shared Turkish normalizer, preserved original labels and deterministic case/diacritic fixtures proving query/index agreement. |
| 6 | **M0-08 — READY** | Reproduced release-gate failure; existing full target | Narrow typing fix or reviewed exceptions under its record, before the next checkpoint. Independent release prerequisite, not a reason to create more foundation work. |

M13 alias/holdout authoring follows the catalog record so identifiers, versions and reviewed concept families are stable. M9-01 retains its explicit Day 0 review/delivery blocker; no stash recovery is authorized here. Remaining PARTIAL scopes below are **not automatically released for takeover**; request the recorded owner's handoff before resuming.

## Reconciled merge evidence

The following ledger records delivered revisions, not another active queue. All PRs below merged into `dev`; implementations and validation detail remain in their owning milestone records. In delivery records, original objectives, readiness-at-start, validation and previous handoffs are historical; reconciled Status/Blocker fields and the queue above control current selection. A merge does not complete acceptance that the code still lacks.

| PR / merge | Delivered scope | Completion reconciliation |
| --- | --- | --- |
| [#16](https://github.com/cagatayeroglu/KKB-DataTrio/pull/16) `400fe58`; [#18](https://github.com/cagatayeroglu/KKB-DataTrio/pull/18) `8197829` | Bounded XLSX + completion | M1-10 DONE; 52 targeted / 245 unit at delivery |
| [#19](https://github.com/cagatayeroglu/KKB-DataTrio/pull/19) `c4506c8` | Architecture decisions / answered Q-TEAM | M0-ARCH DONE; document checks recorded; DEC-115 superseded by DEC-127, now governed by DEC-130 |
| [#20](https://github.com/cagatayeroglu/KKB-DataTrio/pull/20) `33e3bc2` | Runtime dependencies | M1-03 DONE; dependency/fast validation recorded |
| [#21](https://github.com/cagatayeroglu/KKB-DataTrio/pull/21) `35eda16`; [#22](https://github.com/cagatayeroglu/KKB-DataTrio/pull/22) `074a874` | BDDK/EVDS inventories | M3-02/03 DONE; document/source observations, no live runtime adapters |
| [#23](https://github.com/cagatayeroglu/KKB-DataTrio/pull/23) `26e801d`; [#24](https://github.com/cagatayeroglu/KKB-DataTrio/pull/24) `e628169` | Store/semantics; periods/cumulative | 36 then 32 targeted tests; see M12 acceptance gaps below |
| [#25](https://github.com/cagatayeroglu/KKB-DataTrio/pull/25) `d01edf1`; [#26](https://github.com/cagatayeroglu/KKB-DataTrio/pull/26) `726f97a` | Weekly-to-monthly alignment; gold/lineage | 22 then 23 targeted tests; daily alignment/full transformation recording remain incomplete |
| [#27](https://github.com/cagatayeroglu/KKB-DataTrio/pull/27) `69ff1d2` | Offline provider boundary | 48 targeted / 415 unit; live capability acceptance remains blocked |
| [#28](https://github.com/cagatayeroglu/KKB-DataTrio/pull/28) `1fa48b8`; [#29](https://github.com/cagatayeroglu/KKB-DataTrio/pull/29) `dcefc5b` | Plan/registry/executor; workspace definitions | 30 then 22 targeted; counts bounded, full request deadline/reference/recompute integration incomplete |
| [#30](https://github.com/cagatayeroglu/KKB-DataTrio/pull/30) `99894f3` | Database definition/entry point | 8 targeted / 475 unit; M12-DB record left untouched as explicitly requested |
| [#31](https://github.com/cagatayeroglu/KKB-DataTrio/pull/31) `6b1ee47` | Restricted lakehouse tool | M6-20 DONE for its stated SQL boundary scope; 39 targeted / 515 unit |
| [#32](https://github.com/cagatayeroglu/KKB-DataTrio/pull/32) `ec1d783` | Numeric matching + optional query lineage | 37 targeted / 552 unit; M8 remains PARTIAL with exact proof gaps below |
| [#33](https://github.com/cagatayeroglu/KKB-DataTrio/pull/33) `27dab85` | Initial status reconciliation | Documentation only; superseded current-summary wording reconciled here |

Historical checkpoint: PR #17 promoted `dev -> main` at `722c2af`; it is not evidence of a passing full gate. This docs task does not modify either local or remote `main`. Historical Day 0 recovery evidence remains in M0; stash-only files are never a shared delivery.

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

<a id="relative-execution-plan-anchored-to-the-confirmed-calendar"></a>
## Relative execution plan, anchored to the confirmed calendar

The organizer calendar is fixed by [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope): kick-off **7 September 2026**, online development **7–20 September 2026**, top-10 announcement **5 October 2026**, Final Day **17 October 2026**. The relative day numbers below predate that record and were an internal 8–9 day estimate; they are kept because milestones reference them, and mapped to real dates here.

| Relative day | Calendar date | Note |
| --- | --- | --- |
| Day 0 | 7 September | Kick-off and bootstrap |
| Day 1–3 | 8–10 September | Delivered through PR #39; today is 10 September |
| Day 4–8 | 11–15 September | Original plan's remaining slots |
| Slack 9–13 | 16–20 September | **Not free contingency.** Reserve for the vertical slice, live Kloudeks, the required tools and rehearsal |
| Deadline | **20 September** | Repository reviewed as delivered; no further development window is promised |
| — | 5 October | Top-10 announcement |
| Demo | **17 October** | Live deployed solution; organizer-supplied inputs on the day |

The real window is longer than the original estimate, which removes the "combine Day 0 and Day 1" compression the earlier plan assumed. It is **not** authorization to widen scope: the core-first sequence below is unchanged, and the extra days go to the vertical slice, the six required tools and rehearsal. Two gates exist, and they are not the same deliverable — what is reviewed after **20 September is the repository**, while **17 October is the live demo**. Demo-only polish must never displace the reviewed slice.

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
| 16–20 Sep | Close the vertical slice | Live Kloudeks + remaining brief tools | `web_url` document extraction; rehearsal | A reviewable repository at the 20 September deadline |

| Milestone | Scope | Target window |
| --- | --- | --- |
| [M0](#m0) | Repository and development foundation | Day 0 |
| [M1](#m1) | Generic ingestion/profiling | Days 1–2 |
| [M2](#m2) | Financial semantics/normalization | Days 2–3 |
| [M3](#m3) | BDDK/EVDS integration | Days 1–5 as access permits |
| [M4](#m4) | Kloudeks | Days 0–3 as access permits |
| [M5](#m5) | Planning/routing/workspace | Days 1–3 |
| [M6](#m6) | Deterministic analytics | Days 2–4 |
| [M7](#m7) | URL/documents/external inputs | Day 5; document extraction is required demo-day scope under DEC-131, not optional |
| [M8](#m8) | Verification/evidence/provenance | Days 2–6 |
| [M9](#m9) | Evaluation/adversarial benchmark | Days 0–6, then continuously |
| [M10](#m10) | UI/demo workflow | Day 7; operator design can precede |
| [M11](#m11) | Hardening/rehearsal | Days 8–9 |
| [M12](#m12) | Lakehouse and medallion normalization | Days 1–4 |
| [M13](#m13) | Semantic catalog and retrieval | Days 2–5 |

## Dependency and scope policy

**Core first:** permitted source ingestion, the existing lakehouse tool, M6-01 deterministic result contracts, M5 workspace/result integration, M8 verifier/proof gate, M4 live Kloudeks and required brief tools. Do not delay that slice for differentiation. [DEC-128](DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence) is sequenced through existing tasks: premise validation after M2 semantics + M6 comparisons; finance semantic guard through M2/M12 operation policies; catalog-bounded relationship discovery after M13 baseline/families + permitted catalog + guard + M6 methods; relationship stability after aligned validated analytics; Why/proof presentation after M6/M5/M8 run/snapshot/recompute acceptance. M9 owns independent behavioral tracks. None is automatically READY from product approval.

DEFER / CUT IF BEHIND: Leading Indicator Miner, research-grade regime segmentation, causal event attribution, graph-heavy proof UI, recursive challenge/debate and mandatory RRF/reranking/extra vector infrastructure. Dense retrieval remains initial hybrid baseline under DEC-130. Bounded deterministic robustness is optional; official-source web context is contextual, not causal proof.


The critical path is M0 contracts -> M1 ingestion -> M12 lakehouse and semantics -> M13 catalog -> M5 execution + M6 basic change -> M8 evidence -> M10 demo -> M11. M2 is the specification half of the normalization work that M12 implements against the chosen engine; they are worked together, not sequentially. M4 live access is required for the final live model path. M9 develops alongside each feature; do not wait until Day 6 to define expected outputs. M3/M7 depend on safe boundaries and source permissions. Milestone dependencies below name required subsets, not a requirement to finish every optional task upstream.

M12 is where correctness is won or lost. Cumulative handling, frequency alignment and unit normalization decide whether every downstream number is right; no other milestone can compensate for an error there. Prefer a thin vertical slice through the whole path early — one series, loaded, normalized, queried, answered with evidence — over completing any single milestone horizontally.

If behind schedule, cut fancy UI, optional image/exotic formats, router fine-tuning, advanced causality methods, deep observability, and extra agents. Keep typed plans, semantic correctness, evidence, safe inputs, and regressions. Record each cut and its demo consequence. Never advertise a cut/blocked format or live integration as supported.

<a id="m0"></a>
# M0 — Repository & development foundation

Status: PARTIAL for the full milestone checklist; the generic development foundation is delivered (core/config/fast CI). M0-08 is a release-gate prerequisite; privacy/protection and reviewer nomination remain separately unverified. Do not create more foundation tasks by default.

## Objective

Establish a safe, fast baseline and shared contracts that three teammates can extend without losing in-progress work.

## Dependencies

Local checkout and Python >=3.12 for later application validation. No live Kloudeks access is needed for the stub/contracts. Remote changes require explicit authorization.

## Tasks

- [x] M0-01 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-01-core-contracts`. Selectively reviewed/recovered the minimum ingestion/provenance core contracts and focused `tests/unit/test_core_models.py` cases; targeted tests/lint and fast gates passed. PR #13 merged into `dev` at `4e10b14`, with the validated tree unchanged. Deferred protocols/planner/workspace/provider/evaluation code is outside this delivery.
- [ ] M0-02 — Status: PARTIAL; plan/result/workspace tests exist in PR #28/#29, but duplicate dependency and end-to-end serialization/reference coverage need review. Add targeted coverage for duplicate/self dependencies, invalid outcome combinations, and workspace serialization as needed; keep schema changes distinct from validation-only work.
- [x] M0-03 — Status: DONE. Merged smoke test and fast baseline validated by PR #15 and subsequent fast gates (latest PR #32: 552 unit).
- [x] M0-04 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-04-local-config-hygiene`. Local ignore rules and placeholder-only `.env.example` passed targeted validation without real credentials; [PR #3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) merged into `dev` at `ddcb5a7`, with the validated tree unchanged.
- [ ] M0-05 — Status: PARTIAL — offline variable-name/config half delivered in PR #27; endpoint/auth uncertainty removed by DEC-129. Remaining implementation reconciliation belongs with M4-07: map existing local configuration to the official client without changing secret hygiene. Environment names are repository conventions, not organizer-mandated names; no runtime change or new claim in this docs PR.
- [ ] M0-06 — Inspect repository privacy, branch protection, and remote CI only in an authorized setup task; local branches alone do not prove remote settings.
- [x] M0-07 — Status: DONE. Owner: Çağatay; Branch: `feature/m0-07-fast-ci`. Add a fast feature-to-dev CI workflow; required checks and handoff are in the active record below. PR #15 merged at `5f93df7`; validated tree unchanged.
- [ ] M0-08 — Status: READY. Owner: unassigned. The [Makefile](../Makefile) `full` target already exists and is correctly kept out of the per-edit loop, but it does not pass: `mypy src` reports 14 strict errors in the merged XLSX code. Make the release gate green, or record reviewed exceptions, before the next `dev -> main` promotion. Evidence: [M0-08 active record](#m0-08-active-record).
- [x] M0-09 — Status: DONE. Synthetic/private fixture policy and ignored storage locations documented and validated in PR #3/#4; organizer retention permission remains external, not assumed.
- [ ] M0-10 — Document an actual successful setup command/result on a teammate's Python >=3.12 environment.
- [ ] M0-11 — Record the validated core contract baseline and named editor/reviewer before shared contract changes.
- [x] M0-12 — Status: DONE. Foundation targeted/fast gates recorded in M0-01/04/07; full checks remain checkpoint-only.
- [x] M0-13 — Status: DONE. Foundation evidence and subsequent READY-task handoffs recorded through PR #14/#15.
- [x] M0-ARCH — Status: DONE — merged/validated (PR #19 / c4506c8, document validation). Owner: Eray; Branch: `docs/m0-arch-stack-decisions` from `dev` `8197829`. Freeze the architecture and stack: record the analytical engine, orchestration, catalog/retrieval, workspace, lineage, verifier, causality, tool surface, provider interface, frontend/API, dependency policy, package layout and deployment topology as decisions; close the Q-TEAM questions they answer; add the lakehouse and semantic-catalog milestones. Evidence: [M0-ARCH active record](#m0-arch-active-record).
- [x] M0-DOC — Status: DONE. Documentation checks passed; [PR #1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) merged both documentation commits into `dev` at `fe5d44a`; evidence recorded below.
- [x] M0-HANDOFF — Status: DONE. [PR #2](https://github.com/cagatayeroglu/KKB-DataTrio/pull/2) merged into `dev` at `a5d6ee8`; the record below was left stale at PARTIAL and is corrected by this task. Document startup with zero chat history, visible task claims, ownership transfer, concise handoffs, and merge-based DONE. Owner: Codex for the initiating repository owner; Branch: `docs/team-handoff-protocol` from `fe5d44a`. Acceptance: the startup prompt selects an eligible unowned READY task using Git/PR history and targeted docs, preserves unrelated work, and stops on unresolved ownership/decisions; document checks pass and PR merges into `dev` before DONE.

## Acceptance criteria

A teammate can install the declared development environment, run recorded quick checks without live credentials, locate contract/fixture ownership, and identify the next task. Ignore/config/CI behavior is verified before claiming the repository foundation complete. M0-DOC alone does not satisfy this milestone.

## Evidence / implementation record

Foundation deliveries and validation: M0-01 (#13), M0-04 (#3), M0-07 (#15), M0-ARCH (#19), M0-DOC (#1), M0-HANDOFF (#2). The original Day 0 scaffold was not validated by PR #1; ignore/config and CI were delivered later. M0-08 remains a release prerequisite; M0-06 remote settings and M0-11 reviewer nomination are not proven by local branches. Historical original documentation commits: `adeb6928d3000977d1f1f2e2a0bb8bb4a2aa9129`, `4804d054576943691d0ebe2b7aecace5c05ef422`, merged at `fe5d44a`; diff/link/status checks passed. PR #1 had zero checks before CI existed; that is not today's CI state.


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
- Tests: PASS (2026-09-08, Python 3.12.2/Pydantic 2.13.4): `PYTHONPATH=/private/tmp/kkb-m109-deps:src python3.12 -m pytest -q tests/unit/test_core_models.py` — 52 passed in 0.04s (0.76s wall); touched-core/test Ruff format/lint passed; `make quick` — 193 passed in 3.67s (4.50s wall); `make pr` — 193 passed in 3.48s (4.33s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Gates used the same Python/PYTHONPATH with the previously approved openpyxl temporary target. No dependency changes or full/release checks. At that delivery, CI was unconfigured (0 checks, not a CI pass); PR #15 subsequently added CI. Relevant diff, links, scope and stash-preservation checks passed.
- Invariants: Required text is typed/nonblank without trimming; extras and invalid enum values are rejected. Nullable semantics stay None/null; frequency/stock-flow UNKNOWN serializes as `unknown`; cumulative accepts only None/False/True, without coercion. Supplied retrieval time must be timezone-aware; no timestamp/hash default is invented. Transformation lineage requires input/output references and JSON-compatible finite parameters. Evidence starts NOT_RUN. Provenance/metadata round-trip, fresh mutable defaults and reused-source isolation pass.
- Limitations: These are structural records, not a loaded M1 profile, semantic inference, transformer, verifier or complete evidence-chain check. None/null semantics require explicit mapping if a future profile uses the M1-01 `unknown` string representation. Source locators are untrusted metadata, never opened; safe storage/fetch remains the consumer's responsibility. Pydantic validates field assignment but not in-place list/dict mutation: revalidate at boundaries (covered by tests). Declared known semantics/outcomes still require independent evidence; deferred plan/tool/workspace/M4/M9 functionality is not delivered.
- Blocker: none for this scope. Deferred components and unresolved Q-TEAM/organizer decisions remain deferred.
- Merge verification: PR #13 is closed/merged; fetched `origin/dev` and fast-forwarded local `dev`. The full tree matches the validated head, preserving the recorded 52 targeted / 193 quick / 193 PR test evidence. Application gates were not rerun for this documentation-only completion/readiness update; diff, links, status and Git preservation checks passed.
- Previous handoff (historical; current queue controls selection): M0-01 is delivered. M1-10 is READY and unclaimed under the scope below; no implementation started. M0-11 still owns naming an editor/reviewer before shared contract changes; consuming the delivered primitives does not require recovering the deferred protocols. M1-03/CSV engine work still needs Q-TEAM-02, M4-01/M9-01 need separate recovery authorization, and M0-02 plan/tool/workspace cases remain deferred. Keep the original stash intact.

### M0-04 active record

- Status: DONE — targeted validation passed; PR #3 merge and identical integrated tree verified on 2026-09-08
- Owner: Çağatay
- Branch: `feature/m0-04-local-config-hygiene`; base `a5d6ee8ab8bb5a109558b7053f4060e91c7bb8f1` after PR #2 merged
- PR: [#3](https://github.com/cagatayeroglu/KKB-DataTrio/pull/3) — merged into `dev` after scope/conflict review and explicit user authorization; 0 CI checks expected until M0-07, not a CI pass
- Commit: `17b53a67147fdcd044adb739d38b0f144355afd6` implements ignore/config hygiene and its tests; merge `ddcb5a74e90468c499246bf2bb7fed170391a7d5` contains validated PR head `8863edd3d1717cbffaf3fdeda15caabb4da7bd94` with an identical tree, so recorded targeted validation remains applicable
- Tests: PASS (2026-09-08, Python 3.12.2): `python3.12 -m pytest -q tests/unit/test_repository_hygiene.py` — 46 passed in 3.24s. `ruff check tests/unit/test_repository_hygiene.py` — all checks passed; `ruff format --check tests/unit/test_repository_hygiene.py` — 1 file already formatted (Ruff 0.8.6 via a temporary `uv tool run --from ruff==0.8.6` environment; repository dependencies unchanged). `git diff --cached --check` passed for implementation files. Targeted tests/lint cover this config-only task; `make quick`, full/security/release checks not run.
- Evidence: Synthetic temporary Git repositories verify that secrets/private/generated paths stay out of normal staging while the root `.env.example`, source, tests, and synthetic fixtures remain trackable. All example values are blank; provisional Kloudeks names remain subject to M0-05 and organizer answers. No environment loader, provider transport, CI, or runtime contract was added.
- Blocker: none for this scope; dependencies and remote claims checked before/after publication. No unresolved decision or Day 0 stash input required.
- Previous handoff (historical; current queue controls selection): M0-04 is delivered in `dev`; this post-merge record follows AGENTS.md. M1-01 was selected on a fresh branch from updated `dev`. The Day 0 preservation stash remains unchanged/unapplied.

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
- Previous handoff (historical; current queue controls selection): The team considers the generic repository/foundation phase complete after this merge. Continue the explicitly assigned M1-10; do not manufacture more foundation/security/documentation tasks or mark unrelated backlog boxes DONE. `main` and the original Day 0 stash remain untouched.

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
- Previous handoff (historical; current queue controls selection): `main` currently carries an unmet release gate. Either close this task before the next `dev -> main` promotion, or record explicitly in the promotion PR that the full gate was knowingly skipped. Do not describe `main` as release-validated in the meantime.

### M0-ARCH active record

- Status: DONE — documented scope merged and document checks recorded
- Owner: Eray
- Branch: `docs/m0-arch-stack-decisions`; fresh `dev` base `8197829512926b6eb9c896ecfda6cac98f2dfb90`
- PR: [#19](https://github.com/cagatayeroglu/KKB-DataTrio/pull/19) — merged into `dev` at `c4506c8`; original claim publication retained in Git history
- Merge evidence: `c4506c8` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `aba7360`; content commits recorded in the PR
- Objective: Freeze the architecture and technology stack so that M1 onward stops waiting on unresolved team choices, and record every choice with its reason and rejected alternatives.
- Scope: documentation only — DECISIONS, OPEN_QUESTIONS, ARCHITECTURE, ROADMAP and the README repository guide, plus three inbound anchor fixes caused by renaming DEC-111. No `pyproject.toml`, dependency, directory or code change.
- Delivered: [DEC-112](DECISIONS.md#dec-112--duckdb-and-parquet-as-the-analytical-engine-and-lakehouse) engine and lakehouse, [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) orchestration, [DEC-114](DECISIONS.md#dec-114--pandas-with-calamine-for-operator-fetched-bulk-spreadsheets) bulk spreadsheets, [DEC-115](DECISIONS.md#dec-115--hybrid-series-retrieval-over-lancedb-and-duckdb-fts) retrieval, [DEC-116](DECISIONS.md#dec-116--alias-dictionary-single-turkish-normalizer-and-a-measured-recall-floor) aliases and recall floor, [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag) workspace DAG, [DEC-118](DECISIONS.md#dec-118--lineage-graph-as-the-provenance-substrate) lineage, [DEC-119](DECISIONS.md#dec-119--verifier-gates-the-answer) verifier, [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits) causality, [DEC-121](DECISIONS.md#dec-121--six-brief-named-tools-with-typed-schemas-and-restricted-sql) tools, [DEC-122](DECISIONS.md#dec-122--llmprovider-interface-and-structured-output-fallback) provider, [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end) API and front end, [DEC-124](DECISIONS.md#dec-124--dependency-manifest-and-excluded-technologies) dependencies, [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) layout, [DEC-126](DECISIONS.md#dec-126--single-vm-deployment-with-docker-compose) deployment. DEC-111 narrowed to the untrusted XLSX boundary. Q-TEAM-01 through Q-TEAM-05 closed. M12 and M13 added with their task lists.
- Tests: documentation tier. Full diff review; `git diff --check` clean; a link and anchor pass over all tracked Markdown — 158 local links, 240 roadmap checkboxes, 227 unique task IDs, no broken file or anchor target. No application checks run and none required: no code, dependency or configuration file is touched.
- Blocker: none for the merged decision-recording scope. DEC-115 and DEC-127 are SUPERSEDED; DEC-130 governs retrieval. Q-K-05 covers required dense-path configuration and optional reranker capabilities. Q-INFRA-01 can override the target deployment in DEC-126.
- Previous handoff (historical; current queue controls selection): Every architecture choice is now recorded with its reason and rejected alternatives, so no implementation task needs to reopen one. Nothing here is built. After merge, the first implementation task is M1-03 — reconcile `pyproject.toml` with the DEC-124 manifest and create the DEC-125 package directories — followed by a thin vertical slice through M12: one real series into `bronze`, normalized into `silver`, queried through DuckDB, answered with lineage. Ask the organizer questions named in the status section in parallel; they have external latency and gate M4, M7 and M13's dense half.

### M0-HANDOFF active record

- Status: DONE — merged into `dev` at `a5d6ee8`; corrected on 2026-09-09 by the M1-10 completion task after Git showed the merge
- Owner: Codex for the initiating repository owner; Eray/Arda unassigned
- Branch: `docs/team-handoff-protocol`; base `fe5d44ab74e60633ef52c5ba4de7a5a5ca8fa083`
- PR: [#2](https://github.com/cagatayeroglu/KKB-DataTrio/pull/2) — merged, `docs/team-handoff-protocol` -> `dev` at `a5d6ee8`; branch deleted
- Commit: `0f73cbb077f0e091cbffe17be213e18fb6c723e4` implements the protocol; the PR head also includes this handoff-reference update
- Tests: PASS (2026-09-08): full relevant diff/contradiction review, `git diff --check`, Python standard-library link/anchor/task/evidence checks (57 tracked local links, 198 unique task IDs including only one new ID), fresh-`dev` ancestry, and stash hash preservation. Application/security/full checks NOT RUN by task scope
- Blocker: none for the merged documentation scope; CI was added later in PR #15
- Previous handoff (historical; current queue controls selection): Startup/claim/transfer rules and M0-DOC merge evidence are documented and validated. Review PR #2; merge remains required for M0-HANDOFF DONE. Then recheck claims and take M0-04 on a fresh branch from latest `dev`. This task's explicit Phase F opened its PR after document validation; subsequent implementation tasks use early draft claim PRs.

## Handoff notes

Preservation verified on 2026-09-08 in the originating KKB-DataTrio clone: named stash `day0-local-preservation-before-team-handoff-2026-09-08`, initially `stash@{0}`, stable object `49d3fd30cc56b5ca928976d22e3b993960650c85`. Its untracked tree (`^3`) contains exactly 11 files, all SHA-256 hashes equal to the pre-stash files. The stash remains unapplied; it is not pushed or present in a teammate's fresh clone. Stash ordinals can change, so locate by name/object rather than trusting `stash@{0}` later.

This is historical preservation evidence, not a recovery instruction. M0-01 selectively delivered the required core records in PR #13; the offline provider was implemented fresh in PR #27. M9 drafts still require separately authorized selective review/delivery. Do not apply/drop/modify the stash for this docs task or treat it as a fresh clone's prerequisite for unrelated work.

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
- [x] M1-03 — Status: DONE — merged/validated (PR #20 / 33e3bc2, dependency and fast validation). Owner: Eray; Branch: `feature/m1-03-runtime-dependencies`. Reconcile `pyproject.toml` with the DEC-124 manifest: add `duckdb`, `pandas>=2.2`, `pyarrow` and `python-calamine` as runtime dependencies, keep `openpyxl` for the untrusted path, and record the resulting environment. No loader behaviour change. Evidence: [M1-03 active record](#m1-03-active-record).
- [x] M1-04 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-04-synthetic-csv-fixture`. Add a synthetic UTF-8 CSV fixture with date, numeric, text, and missing values.
- [x] M1-05 — Status: DONE. Owner: Çağatay; Branch: `feature/m1-05-csv-edge-fixtures`. Add alternate delimiter, quoted field, BOM/encoding, and decimal/thousands-separator fixtures with explicit expected parsing.
- [ ] M1-06 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Acceptance/dependencies: [ordered queue](#ordered-next-safe-tasks). Implement bounded CSV parsing; record which delimiter/encoding was used and reject ambiguous parsing safely.
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

Merged specification, admission, dependencies, CSV/XLSX fixtures and bounded XLSX loading are documented in the task records below. CSV parsing/profiling and adapter registration are not implemented. M1-06 is now READY after PR #20; no engine or limit choice blocks it. Existing M1-10 results are historical delivery evidence, not fresh tests in this docs task.


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
- Previous handoff (historical; current queue controls selection): M1-01 is delivered. M1-02 was re-evaluated after merge: the policy/guard scope can proceed without engine selection or stash-only core types; ownership was checked and the fresh branch claimed. Keep the Day 0 stash unapplied.


### M1-02 active record

- Status: DONE — authorized PR #5 merge into `dev` verified on 2026-09-08; targeted validation and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-02-file-admission-policy`; original base `cbb51adbbdcdab48d17efdc72d104867b4f7295c`; merged updated `origin/dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003` without conflicts or history rewriting
- PR: [#5](https://github.com/cagatayeroglu/KKB-DataTrio/pull/5) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: implementation `b014b15de87a0d935f32f50ba7b58c24fbebf92e`; dev-sync `22d0fca5f321b486f051a7ec5b790896375e3053`; validated PR head/evidence `b03b120bb1071c352db493831cfa79aa19bd3ea6`; merge `e2287f70bc07ccec191eba5df84584e1df2b3836` contains that head with an identical tree. Completion bookkeeping is on fresh `docs/m1-02-completion` from this updated `dev`.
- Readiness: M1-01 is merged; no owner or competing open PR/remote task branch found before/after publication. The explicit task request authorized executable policy/guards and synthetic tests for the ROADMAP's admission/limits/storage objective. Standalone guards need no analytical engine or shared core-type integration.
- Tests: PASS (2026-09-08, Python 3.12.2) after dev sync: `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_policy.py` — 70 passed in 0.06s (0.97s wall). `make quick` — 117 passed in 3.08s (3.76s wall); `make pr` — 117 passed in 3.11s (3.95s wall), including repository Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Tools used temporary environments; dependencies unchanged. Relevant document/diff checks passed; no full/release checks run.
- Fast gate: PASS — both `make quick` and `make pr`. Pre-existing formatting in `tests/unit/test_smoke.py` and `scripts/check_secrets.py` was fixed separately by [PR #6](https://github.com/cagatayeroglu/KKB-DataTrio/pull/6), merged into `dev` at `80fa088b1d3ea8cf2a4db5e73876190d61ddf003`. Those files are identical to updated `dev` and absent from PR #5's diff. At that delivery, CI was unconfigured (0 checks, not a CI pass); PR #15 subsequently added CI.
- Evidence: [FILE_ADMISSION](FILE_ADMISSION.md) documents [standalone guards](../src/kkb_agent/ingestion_policy.py) and [synthetic negative tests](../tests/unit/test_ingestion_policy.py): metadata before reads, bounded bytes, CSV text/XLSX envelope checks, limit helpers, sanitized M1-01 rejection shape, generated private staging and cleanup. Admission preserves input bytes and makes no semantic inference.
- Limitations: No loaders/profile/API exposure. XLSX checks inspect metadata without extracting XML/cells; later loaders must enforce actual expansion, row/cell/time bounds and content rules. Row/column/field/profile helpers require loader integration; the 5-second parser budget is configuration only. Storage is transient under an operator-owned root, not a retention/backend decision.
- Blocker: none for M1-02; the separate baseline formatting fix resolved the fast-gate failure. Engine selection and validated M0 contracts remain prerequisites for later loader integration, not this independent policy scope.
- Previous handoff (historical; current queue controls selection): M1-02 is delivered; no implementation changes were needed after the separate baseline fix. M1-03 still needs Q-TEAM-02. M1-04 is READY for a synthetic UTF-8 CSV fixture with date/numeric/text/missing values and explicit expected values/counts, preserving unknown semantics. No open PR or remote task-branch claim existed at the 2026-09-08 handoff check; recheck before claiming from latest `dev`. M1-04 is unassigned and not started. The Day 0 stash remains unchanged and unapplied.

### M1-03 active record

- Status: DONE — dependency scope merged and validated
- Owner: Eray
- Branch: `feature/m1-03-runtime-dependencies`; fresh `dev` base `c4506c8`
- PR: [#20](https://github.com/cagatayeroglu/KKB-DataTrio/pull/20) — merged into `dev` at `33e3bc2`; original claim publication retained in Git history
- Merge evidence: `33e3bc2` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `60264e7`; implementation recorded in the PR
- Objective: Put the decided ingestion and analytics engine into the runtime manifest, and prove the environment actually works rather than only declaring it.
- Implementation: [pyproject.toml](../pyproject.toml) gains `duckdb>=1.1,<2`, `pandas>=2.2,<3`, `pyarrow>=17,<22` and `python-calamine>=0.2,<1`, each commented with the decision that requires it; `openpyxl` and `pydantic` stay and are commented likewise. [tests/unit/test_runtime_environment.py](../tests/unit/test_runtime_environment.py) verifies the environment against the values this project actually handles rather than asserting that imports succeed.
- Manifest interpretation: DEC-124's list is the **allowlist**, not a required installation set. `pyproject.toml` may hold a subset of it and never a superset. The remaining entries — `lancedb`, `networkx`, `statsmodels`, `ruptures`, `scipy`, `plotly`, `kaleido`, `pypdf`, `pdfplumber`, `httpx`, `tenacity`, `diskcache`, `json-repair`, `fastapi` — are added by the milestone that first uses them, so an unused library never appears in a dependency audit or slows CI before it earns its place. Adding one from the allowlist needs no new decision; adding anything outside it does.
- Tests: PASS (2026-09-09; Python 3.12.5, DuckDB 1.5.5, pandas 2.3.3, PyArrow 21.0.0, openpyxl 3.1.5, Pydantic 2.13.5). `pytest -q tests/unit/test_runtime_environment.py` — 9 passed in 1.06s. `make pr` equivalent — Ruff 0.16.6 format and lint clean over 20 files, 254 passed in 7.62s, Bandit 1.9.4 clean, secret scan clean. `mypy src` still reports the same 14 pre-existing errors, unchanged by this task; M0-08 still owns them.
- Coverage note: the tests assert the cases that would silently corrupt M12 — a blank measure that becomes `0.0`, Turkish text mangled by a different reader, a NULL that survives Parquet as a zero, decimal drift on a money column, and worksheet order being guessed. One test loads the same fixture through both the DEC-111 untrusted loader and the DEC-114 bulk reader and asserts they agree cell by cell, so the two ingestion routes cannot diverge unnoticed.
- Blocker: none.
- Previous handoff (historical; current queue controls selection): The lakehouse engine is installed and verified; nothing uses it yet. No package directory was created — [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) says modules appear when a task actually needs them, and empty packages would be scaffolding for its own sake. Next is the first M12 slice: [M12-01](#m12) through M12-03, writing a real retrieved artifact into `bronze` and one normalized series into `silver` with explicit semantics. M0-08 remains READY and unowned.

### M1-04 active record

- Status: DONE — authorized PR #8 merge into `dev` verified on 2026-09-08; fixture validation and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-04-synthetic-csv-fixture`; base `64851f51172e47beef21a99cc6a0ae30ebb38a35` after PR #7 merged into `dev`
- PR: [#8](https://github.com/cagatayeroglu/KKB-DataTrio/pull/8) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: `72467db38c86caaa26b9554b177b3ca821da80a7` adds the fixture/test; validated PR head `01bc098d21fb8b1cf4080e5c71f9186789040387`; merge `0d4ecf946a3a74e1b995fadeb75e4e11fb121184` contains that head with an identical tree. Completion bookkeeping is recorded on the fresh M1-05 branch.
- Readiness: M1-01/M1-02 are merged and M1-02 DONE evidence is preserved. No competing open PR or remote task-branch claim found before/after claim publication on 2026-09-08. Fixture design is explicitly independent of Q-TEAM-02; M1-03 remains blocked and unstarted.
- Tests: PASS (2026-09-08, Python 3.12.2): `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_fixture.py` — 1 passed in 0.00s (0.73s wall); `make quick` — 118 passed in 3.12s (3.64s wall); `make pr` — 118 passed in 3.03s (3.86s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Fixture content also matches the existing specification example exactly. Relevant document links/status/commit references and diff checks passed. No full/release checks; At that delivery, CI was unconfigured (0 checks, not a CI pass); PR #15 subsequently added CI.
- Evidence: [Synthetic CSV](../tests/fixtures/ingestion/synthetic_utf8.csv) and [exact-table test](../tests/unit/test_ingestion_fixture.py). Three data rows plus header; `as_of` has three ISO date strings, `measure` has `100`, empty, `125`, and `label` has `A`, `B`, `C`. The test verifies presence, strict UTF-8 decoding, exact header/row order/width/values and the empty numeric cell.
- Scope: This is the existing synthetic example in [INGESTION_PROFILE](INGESTION_PROFILE.md): comma delimiter, header, empty field missing, dot decimal, no thousands separator, trimming or imputation. Counts and values are fixture expectations, not an implemented profile. Unit/frequency/time-role/stock-flow/cumulative/reset semantics remain unknown.
- Limitations: One static UTF-8 fixture only; the original example uses ASCII characters, a valid UTF-8 subset. No loader/profile, engine decision, alternate delimiter/BOM/locale fixtures, source-specific logic, dependency or runtime changes.
- Blocker: none in M1-04 scope; Day 0 stash is not required and remains unchanged/unapplied.
- Previous handoff (historical; current queue controls selection): M1-04 is delivered. M1-05 was re-evaluated after merge: its fixture-only scope is independent of the engine decision; ownership was checked and the fresh branch claimed. M1-03 remains blocked on Q-TEAM-02. Preserve the Day 0 stash.

### M1-05 active record

- Status: DONE — authorized PR #9 merge into `dev` verified on 2026-09-08; targeted fixture tests and both fast gates passed
- Owner: Çağatay
- Branch: `feature/m1-05-csv-edge-fixtures`; base `0d4ecf946a3a74e1b995fadeb75e4e11fb121184` after PR #8 merged into `dev`
- PR: [#9](https://github.com/cagatayeroglu/KKB-DataTrio/pull/9) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: implementation `bd34c1102e2c775dbe5892def54a44d6a9697519`; validated PR head `21aa686dd8ae63814e31d605dbbc5470d40a2387`; merge `a548a54291625888d482b59ba1947977e545cfac` contains that head with an identical tree. Completion bookkeeping is on fresh `docs/m1-05-completion` from updated `dev`.
- Readiness: Previously untriaged checkbox verified READY after M1-04 merge: M1-01 specification, M1-02 admission policy and M1-04 base fixture are delivered. No competing open PR or remote task-branch claim found before/after publication. The milestone explicitly permits fixture design before Q-TEAM-02; no unresolved architecture choice is needed.
- Tests: PASS (2026-09-08, Python 3.12.2): `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_csv_edge_fixtures.py` — 4 passed in 0.01s (0.78s wall); `make quick` — 122 passed in 2.90s (3.54s wall); `make pr` — 122 passed in 2.94s (3.80s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Relevant links/status/commit references and diff checks passed. No full/release checks; At that delivery, CI was unconfigured (0 checks, not a CI pass); PR #15 subsequently added CI.
- Evidence: [Fixture declarations](../tests/fixtures/ingestion/CSV_EDGE_CASES.md) link all four synthetic CSVs and document their exact interpretation; [four parameterized tests](../tests/unit/test_csv_edge_fixtures.py) pin presence, BOM flag, LF/UTF-8 decoding, header/order/width and every string cell. Cases cover semicolon delimiter, quoted commas/escaped quotes/embedded LF, UTF-8 BOM with `Örnek`/`çığ`, and both comma/dot numeric ambiguity.
- Scope: Numeric strings `1,234`/`2,345` and `1.234`/`2.345` remain unchanged. Each column has two documented decimal/grouping interpretations; none is selected. Empty cells remain missing and financial semantics remain unknown.
- Limitations: Fixture oracles only, using stdlib CSV inside tests. No runtime loader/profile, numeric normalization, engine/dependency/CI change, source-specific logic or private data.
- Blocker: none in M1-05 scope; M1-03 remains blocked on Q-TEAM-02. The Day 0 stash remains unchanged and unapplied.
- Previous handoff (historical; current queue controls selection): M1-05 is delivered. M1-03 remains blocked on Q-TEAM-02; M1-06/07/08 retain the milestone's unresolved validated M0 contracts/engine prerequisites. M1-09 was checked next and stopped before claiming because no suitable XLSX-writing dependency is declared. See its blocker record; no substitute task was started.

### M1-09 active record

- Status: DONE — authorized PR #11 merge into `dev` verified on 2026-09-08; required validation passed and the merged tree is unchanged
- Owner: Çağatay
- Branch: `feature/m1-09-xlsx-fixtures`; fresh base `eb0922c6249d558248bc98341ed367e646beceef` after PR #10 merged
- PR: [#11](https://github.com/cagatayeroglu/KKB-DataTrio/pull/11) — merged into `dev` after scope/conflict review and explicit user authorization; no separate teammate review claimed
- Commit: claim/decision `61219af177aa92b0e29f84120a90b71db2d46811`; implementation `e1c269f768f196f56d8acb0fbc6c96d5cff665bd`; validated head `d69a9176bd09b5cb70a202b267691ef026c4205e`; merge `3e705423b315c60f7c6da96825892f5279b54bcc` contains that head with an identical tree. Completion bookkeeping uses fresh `docs/m1-09-completion` from updated `dev`
- Readiness: M1-01/02/04/05 are delivered; M1-05 is DONE in updated `dev`. No competing open PR or remote task-branch claim found before/after publication on 2026-09-08. Explicit team approval of `openpyxl>=3.1,<4` is recorded in [DEC-111](DECISIONS.md#dec-111--openpyxl-for-the-untrusted-xlsx-boundary), resolving the previous writer blocker without deciding Q-TEAM-02.
- Dependency: Added `openpyxl>=3.1,<4` to normal runtime dependencies in [pyproject.toml](../pyproject.toml), using the existing manifest style. No existing lock file, no lock change/new strategy. Validation used openpyxl 3.1.5 with its required et-xmlfile 2.0.0 in a temporary environment; no second XLSX library added to the project.
- Tests: PASS (2026-09-08, Python 3.12.2): `python3.12 -m pytest -q tests/unit/test_xlsx_fixtures.py` with `PYTHONPATH=/private/tmp/kkb-m109-deps:src` — 19 passed in 1.05s (2.83s wall); `make quick` — 141 passed in 3.50s (4.36s wall); `make pr` — 141 passed in 3.41s (4.25s wall), including Ruff 0.8.6 format/lint, Bandit 1.7.10 and secret checks. Both gates used the same Python/dependency environment. All three fixture worksheets were reopened/rendered and visually checked; relevant links/status/diff checks passed. No full/release gate. At that delivery, CI was unconfigured; PR #15 subsequently added CI.
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

Status: PARTIAL — M12 delivers operation metadata, canonical period functions, cumulative conversions, weekly-to-monthly alignment and gold joins. Unit/rate conversions, revisions, rebasing/deflation and complete operation-to-proof integration remain. M2 policies and M12 implementations share the evidence below.

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
- [x] M2-11 — Status: DONE. Implemented and validated in M12-06, PR #24 / e628169; explicit baseline and missing predecessors tested.
- [x] M2-12 — Status: DONE. Implemented and validated in M12-07, PR #24 / e628169; January/reset/gap cases tested.
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

PRs #23–#26 deliver semantics, period/cumulative functions, weekly/monthly alignment and gold/lineage; their M12 records preserve targeted validation. M2-11/12 are delivered by the cumulative implementation. General date parsing, unit/rate conversion, revisions, rebasing/deflation and complete transformation integration remain. Reuse these modules; do not build a second normalization stack.


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
- [x] M3-02 — Status: DONE — merged/validated (PR #21 / 35eda16, inventory/document validation). Owner: Eray; Branch: `feature/m3-02-bddk-source-inventory`. Identify representative BDDK datasets and source-published frequency/unit/stock-flow semantics with exact references. Evidence: [M3-02 active record](#m3-02-active-record).
- [x] M3-03 — Status: DONE — merged/validated (PR #22 / 074a874, inventory/document validation). Owner: Eray; Branch: `feature/m3-03-evds-source-inventory`. Identify representative EVDS series and date/unit/revision metadata with exact references. Evidence: [M3-03 active record](#m3-03-active-record).
- [ ] M3-04 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Acceptance/dependencies: [ordered queue](#ordered-next-safe-tasks). Create synthetic source-shaped discovery/inspection/load fixtures without private source payloads.
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

- Status: DONE — inventory merged and document checks recorded
- Owner: Eray
- Branch: `feature/m3-03-evds-source-inventory`; fresh `dev` base `35eda16`
- PR: [#22](https://github.com/cagatayeroglu/KKB-DataTrio/pull/22) — merged into `dev` at `074a874`; original claim publication retained in Git history
- Merge evidence: `074a874` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
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
- Previous handoff (historical; current queue controls selection): both source inventories now exist, so M12 can be written against measured behaviour on both sides of the reference scenario. Natural next step is the first M12 slice using the series named here. M3-04 synthetic fixtures should now be shaped like these real responses, including the comma decimal and the weekly Friday anchor.

### M3-02 active record

- Status: DONE — inventory merged and document checks recorded
- Owner: Eray
- Branch: `feature/m3-02-bddk-source-inventory`; fresh `dev` base `33e3bc2`
- PR: [#21](https://github.com/cagatayeroglu/KKB-DataTrio/pull/21) — merged into `dev` at `35eda16`; original claim publication retained in Git history
- Merge evidence: `35eda16` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
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
- Previous handoff (historical; current queue controls selection): M12's normalization rules can now be written against measured behaviour. The next natural task is M3-03, the same inspection for EVDS, since the reference scenario needs the mortgage rate series and EVDS access may need a key. Revision behaviour, USD variants, the other 15 monthly tables and bank-group breakdowns remain uninspected.

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
- Previous handoff (historical; current queue controls selection): Resolve M3-01 externally; use M3-04 after M1 for independent progress.

## Handoff notes

Answer Q-DATA-01 in OPEN_QUESTIONS; do not scatter endpoint assumptions across code or docs. No live network path is enabled before M7's safe-fetch control acceptance.

<a id="m4"></a>
# M4 — LLM / Kloudeks integration

Status: PARTIAL — the [provider boundary](../src/kkb_agent/llm/provider.py) is delivered: three methods, environment-driven configuration, reported capabilities, strict structured-output validation with repair, and a scripted double that fails the way the platform is expected to. Live transport (M4-07) remains unimplemented. DEC-129 supplies the official endpoint/auth/models; remaining work includes the SDK-policy correction and bounded transport tests. Native tool/JSON guarantees are still unknown and are not prerequisites for ordinary text plus local schema validation; live acceptance requires provisioned access and recorded limits.

## Objective

Provide replaceable, bounded structured generation and synthesis using only confirmed Kloudeks runtime access.

## Dependencies

M0 contracts for offline validation; organizer endpoint/auth/model contract for live transport; SEC-KEY-01 and SEC-KLO-01 before real credentials/network behavior.

## Tasks

- [ ] M4-01 — Status: BLOCKED — original recovery scope retired in favor of [DEC-122](DECISIONS.md#dec-122--llmprovider-interface-and-structured-output-fallback), which fixes the interface directly. Recovering a Day 0 stub written before that decision would deliver the wrong shape, so the provider is written fresh; the stash stays intact and unapplied. Environment parsing, secret representation and pending-error behaviour are delivered under M4-06 and M4-09 instead.
- [ ] M4-02 — Cover every stub method's non-networking failure path, not only synthesis, with synthetic inputs.
- [ ] M4-03 — Status: PARTIAL — official endpoint/auth/client facts recorded in DEC-129, verified against the primary MIA guide 2026-09-10. The MIA API key is now **provisioned** and held only in the operator-local ignored `.env`; **live authentication has still not been exercised**, which is all that remains of narrowed Q-K-01. No secret value is recorded anywhere in this repository.
- [ ] M4-04 — Status: PARTIAL — exact model IDs and image-input counts recorded in DEC-129 (PR #34), extended 2026-09-10 with the literal OCR request contract, the embedding call shape and documented `401`/`403`/`429` semantics from the primary MIA guide. Remaining context/output limits, native tool/JSON guarantees and exact rate/concurrency/timeout numbers remain Q-K-02/03/04; embedding vector dimension remains Q-K-05 and is measurable from the first authorized live call.
- [ ] M4-05 — Status: PARTIAL — merged scope; remaining acceptance: Offline capability reporting exists; official text/vision, embedding and OCR availability is now DEC-129, but runtime integration and remaining capacity/native tool/JSON/embedding configuration acceptance are still unfinished. Owner: Eray; Branch: `feature/m4-provider-interface`. Define capability reporting and structured-output fallback using confirmed platform features. Evidence: [M4 provider record](#m4-provider-record).
- [x] M4-06 — Status: DONE — merged/validated (PR #27 / 69ff1d2, offline config tests). Owner: Eray; Branch: `feature/m4-provider-interface`. Implement environment-based configuration validation and safe missing/invalid-config errors. Evidence: [M4 provider record](#m4-provider-record).
- [ ] M4-07 — Implement bounded organizer-approved transport behind LLMProvider using DEC-129; no hidden fallback to another provider. Include the conflicting SDK-policy test/comment correction and destination/credential negative tests described below. This docs update does not claim, start or deliver transport.
- [x] M4-08 — Status: DONE — merged/validated (PR #27 / 69ff1d2, structured-output tests). Owner: Eray; Branch: `feature/m4-provider-interface`. Parse structured output into the requested schema; reject extra/malformed fields and unsupported tool arguments. Evidence: [M4 provider record](#m4-provider-record).
- [x] M4-09 — Status: DONE — merged/validated (PR #27 / 69ff1d2, scripted-provider tests). Owner: Eray; Branch: `feature/m4-provider-interface`. Add synthetic provider doubles for success, malformed JSON, refusal, timeout, rate limit, and unavailable model. Evidence: [M4 provider record](#m4-provider-record).
- [ ] M4-10 — Configure bounded retries/deadlines based on limits; separate transient transport failures from invalid-plan repair.
- [x] M4-11 — Status: DONE — merged/validated (PR #27 / 69ff1d2, credential/prompt redaction tests). Owner: Eray; Branch: `feature/m4-provider-interface`. Test credentials and sensitive prompts never appear in logs/errors/evidence. Evidence: [M4 provider record](#m4-provider-record).
- [ ] M4-12 — Measure one permitted live structured-generation request and record model/config metadata without secrets.
- [ ] M4-13 — Run targeted provider/transport/auth negative tests, lint, and the fast PR gate; keep live smoke separate from credential-free unit CI.
- [x] M4-14 — Status: DONE. Record offline versus live validation and any model-capability limitation. Evidence: PR #27 distinguishes 48 offline tests from blocked live transport/capabilities.

### M4 provider record

- Status: PARTIAL — offline boundary merged/validated; DEC-129 now confirms listed capabilities. M4-05 awaits runtime integration/remaining capability details; M4-07/12 await transport/policy correction and live measurement
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m4-provider-interface`; fresh `dev` base `726f97a`
- PR: [#27](https://github.com/cagatayeroglu/KKB-DataTrio/pull/27) — merged into `dev` at `69ff1d2`; original claim publication retained in Git history
- Merge evidence: `69ff1d2` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `4ae5127`; implementation recorded in the PR
- Original PR #27 objective (historical): Deliver the DEC-122 provider boundary so callers can be built/tested before the platform answers arrive. DEC-129 now supplies the listed transport/model facts.
- Scope: interface, configuration, structured-output fallback, synthetic doubles and redaction. **No live transport**. The former endpoint/model availability blockers were answered by DEC-129; the existing code has not been updated or live-tested against that guidance.
- Implementation: [llm/provider.py](../src/kkb_agent/llm/provider.py) holds the three-method protocol and the error taxonomy; [llm/config.py](../src/kkb_agent/llm/config.py) reads every platform value from the environment; [llm/structured.py](../src/kkb_agent/llm/structured.py) extracts, repairs and strictly validates model JSON; [llm/doubles.py](../src/kkb_agent/llm/doubles.py) is a scripted provider that runs the real repair loop and performs no networking.
- Model identifiers, base URL, capability flags, timeout and attempt budget come from environment configuration. DEC-129 now supplies official transport/model facts; configuration remains the boundary rather than hard-coded choices in callers. Configuration errors report setting names, not values. Source comments claiming all Q-K facts remain unknown are stale and require the later M4 correction below.
- Capabilities are reported, not assumed. `capabilities()` derives `embed` and `vision` from whether a model is configured, and `structured_output` defaults to **false**, so the repair loop is the default path until Q-K-03 says otherwise. A caller that needs embeddings finds out at configuration rather than at the first retrieval.
- Strict validation is the gate. Extra fields are rejected rather than ignored, because DEC-101 requires the schema to decide what may execute — a test feeds a plan carrying an unexpected `shell` field and asserts it is refused. On failure the loop appends the model's own answer plus a correction naming the fault and restating the schema, then retries within a bounded budget; an unchanged prompt tends to reproduce the same malformation.
- Redaction is tested, not assumed: prompt content and completion text are excluded from representations, the credential is a `SecretStr` and absent from both `repr` and configuration errors, and a schema violation reports field locations and error types without the offending values, which are model output derived from a prompt that may hold source rows.
- Required future M4-07 policy correction: [tests/unit/test_llm_provider.py](../tests/unit/test_llm_provider.py), `TestTheBoundaryHoldsTheLine.test_no_third_party_provider_appears_in_the_package` (lines 274–283 at verified dev), rejects the literal `openai` anywhere under `src/kkb_agent`, including a compliant import. This now conflicts with official DEC-129 guidance. Replace blanket SDK-name rejection with targeted exclusive-Kloudeks destination/no-hosted-fallback/credential tests while retaining the ban on third-party hosted LLM services. The test remains unchanged in this docs PR.
- Related unchanged source policy: [llm/provider.py](../src/kkb_agent/llm/provider.py) lines 3–10 states the client/import ban and old unknowns; [llm/config.py](../src/kkb_agent/llm/config.py) lines 3–6/22–23 and [llm/doubles.py](../src/kkb_agent/llm/doubles.py) lines 1–7 retain outdated unanswered-question comments. Correct them with the implementation follow-up. No live SDK client/dependency support is claimed here.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_llm_provider.py` — 48 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 39 files, `pytest -q tests/unit` — 415 passed in 8.60s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the `llm` package is strict-clean.
- The repository secret scan flagged a test constant named like a key, correctly. It was renamed to an obvious canary rather than excused: a control that has to be suppressed for the test proving it works is not a control. `json-repair` was added from the DEC-124 allowlist; [.env.example](../.env.example) now lists the real settings, which also closes the naming half of M0-05.
- Blocker: no missing endpoint/auth/model decision for ordinary compatible text transport. M4-07 still needs implementation/policy correction; M4-12 needs an operator-provisioned key and authorized live validation. Native tool/JSON guarantees and capacity/limit questions remain open. Recorded Eray ownership is not transferred; no M4 task is claimed by this docs follow-up.
- Previous handoff (historical; current queue controls selection): the planner, router and tools can now be written and exercised against a provider that fails the way the platform is expected to fail. The next lane is M5 — the DEC-113 planner/router/executor loop with a typed plan and a registry, built against the scripted provider. When Kloudeks answers arrive, the live transport slots in behind this interface and nothing above it changes.

## Acceptance criteria

Offline tests require no credentials/network. Live integration uses the confirmed Kloudeks route, validates responses, honors budgets, and produces sanitized structured failures. A pending stub cannot be counted as live acceptance.

## Evidence / implementation record

PR #27 delivers `llm/` protocol/config/structured parsing/doubles. No live transport exists. M4-05/07/12 still require runtime implementation/validation and the narrowed capability/access answers above. The old `providers/kloudeks.py` draft is preserved stash-only and superseded by DEC-122, not a file available in dev.


## Handoff notes

Use DEC-129's officially supplied compatible-client contract; do not invent native tool/JSON support, limits or embedding prefixes. Follow M4-07 for the SDK-policy correction and bounded transport on a separately claimed implementation branch after ownership is confirmed. Synthetic doubles remain the credential-free test path. **The OCR prompt/`extra_body` blocker is cleared**: DEC-129's 2026-09-10 amendment carries the literal organizer values, so OCR implementation now waits on bounded rendering/parsing and input scope, not on missing guidance. A key exists but no live call has been made; M4-12 remains a separately authorized step, and its first response should capture the embedding vector dimension for Q-K-05.

<a id="m5"></a>
# M5 — Planning / tool routing

Status: PARTIAL — typed plans, the tool registry, plan validation, the bounded executor, the planner repair loop and the [workspace artifact DAG](../src/kkb_agent/agent/workspace.py) are delivered and tested against the scripted provider. Deterministic format routing (M5-07) and the failure taxonomy (M5-14) remain.

## Objective

Turn requests into validated tool runs and explicit state transitions with bounded repair.

## Dependencies

Validated M0 contracts; synthetic provider double or M4 live provider; at least one deterministic fixture tool for the first slice. The orchestration mechanism is settled by [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) and the workspace shape by [DEC-117](DECISIONS.md#dec-117--analysis-workspace-as-a-persisted-artifact-dag); no framework is required to specify tests.

## Tasks

- [ ] M5-01 — Status: PARTIAL — merged scope; remaining acceptance: Plan/execute and a separately invoked verifier fixture exist; the Session lifecycle does not invoke verification. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Define a minimal request -> plan -> validation -> execution -> verification lifecycle fixture. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-02 — Status: DONE. Resolved by [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) on 2026-09-09: a custom planner -> router -> executor -> verifier state machine, with LangChain, LangGraph and Celery rejected. No framework is added.
- [x] M5-03 — Status: DONE — merged/validated (PR #28 / 1fa48b8, registry tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Implement a tool registry with unique system-owned names and argument schemas. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-04 — Status: DONE — merged/validated (PR #28 / 1fa48b8, argument/unknown-name negatives). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Reject unknown tool names and validate per-tool arguments, rather than trusting the plan's generic argument dictionary. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-05 — Status: PARTIAL — merged scope; remaining acceptance: Dependency validation exists; workspace/input/output ownership and declared output-type checks are missing. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Validate dependency order, input/output reference existence, workspace ownership, and declared output type. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-06 — Status: PARTIAL — merged scope; remaining acceptance: Registry descriptions are exposed; relevance narrowing and selected source metadata are not implemented. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Expose only relevant tool descriptions and source metadata to the planner. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-07 — Implement deterministic format routing and metadata-based narrowing before semantic model routing.
- [x] M5-08 — Status: DONE — merged/validated (PR #28 / 1fa48b8, scripted planning tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Generate a constrained AnalyticalPlan using the provider boundary; separate source content from system instructions. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-09 — Status: DONE — merged/validated (PR #28 / 1fa48b8, deterministic dispatch tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Execute the smallest valid plan using registered deterministic tools and structured ToolResult outcomes. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-10 — Status: PARTIAL — merged scope; remaining acceptance: Definition DAG persists parameters/references, but Session/tool-result/semantic-evidence integration is absent. Owner: Eray; Branch: `feature/m5-10-workspace-dag`. Preserve explicit selected sources, contracts, derived references, assumptions, transformations, evidence, and tool results between turns. Evidence: [M5 workspace record](#m5-workspace-record).
- [ ] M5-11 — Status: PARTIAL — merged scope; remaining acceptance: Synthetic definition follow-ups pass; an actual series/date follow-up through tool execution and immutable values is missing. Owner: Eray; Branch: `feature/m5-10-workspace-dag`. Add a series/change-date-range follow-up using existing workspace references. Evidence: [M5 workspace record](#m5-workspace-record).
- [ ] M5-12 — Status: PARTIAL — merged scope; remaining acceptance: Stale marking exists; refresh only rebinds definitions with old value_ref/lineage, and resolve allows stale reads. Actual recomputation/rejection remain. Owner: Eray; Branch: `feature/m5-10-workspace-dag`. Invalidate/recompute dependent results when a selection or assumption changes; preserve historical lineage. Evidence: [M5 workspace record](#m5-workspace-record).
- [ ] M5-13 — Status: PARTIAL — merged scope; remaining acceptance: Step/repair/retry counts and repeated-plan rejection pass; total deadline/cancellation are absent. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Bound plan repairs, tool retries, steps, and total request deadline; abort repeated identical invalid plans. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-14 — Distinguish clarification, unsupported request, recoverable outage, partial result, and terminal failure in the orchestration layer.
- [ ] M5-15 — Test invalid names/arguments/dependencies, stale references, partial tool failure, and failed-turn state preservation.
- [ ] M5-16 — Status: PARTIAL — merged scope; remaining acceptance: Unknown tools/extra arguments are refused; permitted-reference, URL/path and extraction-path authorization tests remain. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Test injected source text cannot authorize a tool, URL, file path, or code execution. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-17 — Status: DONE for the delivered scope. Run targeted planner/executor contract and negative tests, lint, and the fast PR gate; reserve full checks for checkpoints or explicit requests. Evidence: PR #28, 30 targeted / 445 unit tests and fast checks; future integration changes require their own checks.
- [x] M5-18 — Status: DONE for the delivered-scope handoff. Record supported lifecycle/turn operations, limits, validation, and next tool integration. Evidence: PRs #28/29 records below; incomplete runtime acceptance remains explicitly PARTIAL above.

### M5 workspace record

- Status: PARTIAL — merged/validated definitions; actual result integration, immutable values, stale-read rejection and recomputation remain M5-10/11/12
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m5-10-workspace-dag`; fresh `dev` base `1fa48b8`
- PR: [#29](https://github.com/cagatayeroglu/KKB-DataTrio/pull/29) — merged into `dev` at `dcefc5b`; original claim publication retained in Git history
- Merge evidence: `dcefc5b` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `5d10fad`; implementation recorded in the PR
- Objective: Implement the DEC-117 artifact DAG so a follow-up adds to the analysis instead of rebuilding it, and so changing an input invalidates exactly what depended on it.
- Scope: workspace state, derivation, invalidation and refresh, persisted in DuckDB. No UI, no verifier, no tool implementations.
- Implementation: [agent/workspace.py](../src/kkb_agent/agent/workspace.py). Artifact definition rows are content-addressed over their **definition** — kind, name, parameters and ordered input ids — so an identical redefinition is a no-op and a changed one mints a new artifact instead of mutating the old. A name is a slot; an artifact is what currently fills it. Three DuckDB tables hold artifacts, current bindings and per-name revision history.
- The organizer's three turns are the test structure. Turn one builds the table. Turn two adds a deflated column and a test asserts every pre-existing artifact id is **unchanged**. Turn three adds the housing price index and asserts the same. That is what "tabloyu bozmadan" has to mean mechanically: a table rebuilt each turn is how a value silently changes between two answers the user believes are the same table.
- Invalidation is exact and lazy. Changing the date range marks `konut_stok`, `konut_faiz` and `tablo` stale and leaves an unrelated column alone; the changed artifact itself is current, because it is the thing that changed. Dependents are **not** recomputed eagerly — whether they should be is the caller's decision, and doing it silently is how a stale result hides. `refresh` checks stale input bindings and `refresh_order` returns their order, but refresh retains the prior value_ref/lineage and performs no calculation; stale-read rejection and actual recomputation remain M5-12.
- Definition history remains readable after rebinding. It records which definition was active, not an immutable copy of historical result values; answering "what did this say before the range changed" still requires result snapshots.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_workspace.py` — 22 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 47 files, `pytest -q tests/unit` — 467 passed, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the workspace is strict-clean.
- Workspace name bindings are scoped by id; arbitrary artifact-ID reads and tool query scope are not a complete cross-workspace access boundary. A leftover no-op line in `refresh_order` was found and removed rather than left as decoration.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): the multi-turn mechanism holds definitions, not values; `value_ref` points at data rather than carrying it. This alone does not make values replayable. What it cannot yet do is compute anything, because no tool is implemented. The next step is the first real tool: `lakehouse` over the M12 gold tables, which turns a validated plan step into an artifact with a value and a lineage node.

### M5 loop record

- Status: PARTIAL — merged/validated; remaining M5-01/05/06/13/16 lifecycle, reference, narrowing, deadline and boundary criteria are listed above
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m5-plan-registry-executor`; fresh `dev` base `69ff1d2`
- PR: [#28](https://github.com/cagatayeroglu/KKB-DataTrio/pull/28) — merged into `dev` at `1fa48b8`; original claim publication retained in Git history
- Merge evidence: `1fa48b8` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `3d3da30`; implementation recorded in the PR
- Objective: Deliver the DEC-113 loop's first half — a typed plan, a registry that owns the names and argument schemas, validation that decides what may run, and a bounded executor.
- Scope: plan, registry, validation, execution and budgets against the scripted provider. Workspace state (M5-10/11/12) and the verifier are separate.
- Implementation: [agent/plan.py](../src/kkb_agent/agent/plan.py), [agent/registry.py](../src/kkb_agent/agent/registry.py), [agent/executor.py](../src/kkb_agent/agent/executor.py) and [agent/loop.py](../src/kkb_agent/agent/loop.py). No framework: the loop is a few dozen lines of our own code, as DEC-113 selected.
- The registry owns the names, and a name that is not registered does not exist. Registration is restricted to the six the brief fixes, so adding a seventh needs a decision rather than a commit. One definition produces both the description shown to the planner and the validation applied to what comes back, so the two cannot drift into the failure where a model is told about a parameter the executor will not accept.
- Validation refuses a plan whole rather than running its valid prefix; a partial answer nobody asked for is worse than a refusal. It checks the tool exists, that arguments satisfy that tool's own schema rather than a generic dictionary, that dependencies exist and are acyclic, that step ids are unique, and that the plan fits the step budget.
- Unknown-tool and extra-argument injection attempts are rejected in targeted tests; this is not complete prompt-injection protection. A test has the model **obey** an injected instruction and propose a `shell` tool; the registry has no `shell`, so the plan is refused before anything runs. A second test has it smuggle an undeclared `command` argument into a real tool, refused by that tool's schema. The question reaches the model only as a user turn, and a test asserts source-derived text never occupies a system turn.
- Bounds are everywhere and each is tested: step count, plan repairs, tool retries. A planner that proposes the **same** invalid plan twice is stopped immediately rather than allowed to spend the remaining budget on a loop it will not escape. A tool that raises becomes a categorized failure instead of aborting the run, and steps after a terminal failure are reported `not_run` rather than silently skipped.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_agent_loop.py` — 30 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 45 files, `pytest -q tests/unit` — 445 passed in 9.07s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the `agent` package is strict-clean.
- One test failed first and taught something worth keeping: it introspected the execution context with `vars()`, which raises on a slots dataclass, and the executor caught the exception and turned it into a tool failure exactly as designed. The test was wrong; the swallowing behaviour it accidentally exercised is correct and is now covered deliberately.
- M5-02 is marked DONE: the orchestration choice it asked for was resolved by DEC-113, and no framework is added.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): a question can now become a validated plan and a bounded run, against a provider that fails the way the platform is expected to. Nothing is persisted between turns and no tool does real work — the six registered names have no implementations yet. Next is M5-10/11/12, the DEC-117 workspace artifact DAG that makes a follow-up reuse prior state, and then the first real tool over the M12 lakehouse.

## Acceptance criteria

A synthetic request executes a typed plan through a registry and retains explicit workspace state. Invalid/unsafe calls fail before execution. Repairs stop at configured bounds. Failed turns do not silently overwrite previously verified results; stale derived results cannot be reused after changed assumptions.

## Evidence / implementation record

PR #28 delivers typed plans/registry/execution; #29 delivers workspace definitions; #32 adds optional tool-result lineage. Targeted counts and exact remaining criteria are in the two records above. Session does not automatically persist Workspace or run the verifier; result/output/reference validation and deadline/recompute integration remain.


## Handoff notes

Do not claim “typed plans implemented” means execution is safe. Keep structural, registry/argument, semantic, and capability validation separately observable in tests and failure reports.

<a id="m6"></a>
# M6 — Deterministic analytics

Status: PARTIAL — the [`lakehouse` tool](../src/kkb_agent/tools/lakehouse.py) is delivered with its five security gates. The five other brief-named tools have no implementation.

## Objective

Produce reproducible financial/statistical results with stated prerequisites, sample counts, and limitations.

## Dependencies

M1 data references, M2 operation-specific semantic policies, M5 tool registration, M8 evidence-record interface. The causality method is fixed by [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits); basic descriptive tools do not.

## Tasks

- [ ] M6-01 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Acceptance/dependencies: [ordered queue](#ordered-next-safe-tasks). Define result schemas for values, units, periods, sample counts, warnings, and evidence references.
- [ ] M6-02 — Implement absolute change and relative change with explicit denominator/zero handling.
- [ ] M6-03 — Implement period comparison with exact date selection and transparent missing observations.
- [ ] M6-04 — Add hand-calculated change fixtures including negative values, zeros, and empty ranges.
- [ ] M6-05 — Choose/document a simple change/anomaly baseline and its minimum-sample/parameter policy.
- [ ] M6-06 — Implement the chosen anomaly/change method with deterministic output and recorded parameters.
- [ ] M6-07 — Implement association on aligned observations; report method, sample count, and missing-value policy.
- [ ] M6-08 — Reject or explicitly flag too few observations and constant series; avoid invalid/undefined statistics.
- [ ] M6-09 — Implement lag analysis with a clear lag sign, bounded search window, and per-lag sample counts.
- [ ] M6-10 — Test non-stationary/spurious-correlation examples and prevent an association result becoming causal prose.
- [x] M6-20 — Status: DONE — merged/validated (PR #31 / 6b1ee47, 39 targeted SQL tests). Owner: Eray; Branch: `feature/m6-lakehouse-tool`. Implement the `lakehouse` tool as restricted text-to-SQL over gold under [DEC-121](DECISIONS.md#dec-121--six-brief-named-tools-with-typed-schemas-and-restricted-sql): parse the statement, allow only whitelisted tables, dry-run through `EXPLAIN`, then execute read-only with the engine's file, network and extension capabilities switched off. Evidence: [lakehouse tool record](#lakehouse-tool-record).
- [ ] M6-11 — Implement the DEC-120 causality tool: lagged cross-correlation and Granger tests via `statsmodels`, with mandatory printed limitations and no "X causes Y" phrasing.
- [ ] M6-12 — Implement supported causality method only if justified/time permits; otherwise record explicit scope cut and abstention behavior.
- [ ] M6-13 — Reuse M2 deflation with reference-period evidence; never compare nominal and real measures silently.
- [ ] M6-14 — Generate deterministic table/chart data from tool outputs; formatting must not recompute material values through the model.
- [ ] M6-15 — Test numeric oracles, tolerances, warning semantics, and source/transformation links.
- [ ] M6-16 — Run targeted analytics tests/lint and relevant smoke cases; record per-tool support and next task.

### Lakehouse tool record

- Status: DONE for M6-20 — merged/validated restricted SQL tool; full result/proof/SQL-resource acceptance is separate
- Owner: Eray
- Branch: `feature/m6-lakehouse-tool`; fresh `dev` base `99894f3`
- PR: [#31](https://github.com/cagatayeroglu/KKB-DataTrio/pull/31) — merged into `dev` at `6b1ee47`; original claim publication retained in Git history
- Merge evidence: `6b1ee47` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `e372c5f`; implementation recorded in the PR
- Objective: The first tool that does real work — restricted text-to-SQL over the analysis tables under the DEC-121 controls.
- Scope: the `lakehouse` tool and its security boundary, tracked as the new M6-20. No planner prompt changes, no other tools.
- Implementation: [tools/lakehouse.py](../src/kkb_agent/tools/lakehouse.py). Five gates, all of which a query must pass: one statement and it must be a SELECT, parsed by the engine rather than matched by a regular expression; no table functions, which is how SQL reaches the filesystem; only whitelisted tables, with CTEs the query defines itself excluded; an `EXPLAIN` dry run; and a database that cannot reach the filesystem, the network or an extension registry at all.
- One finding changed the design. DuckDB applies configuration **per database, not per connection**, so hardening a cursor locks the whole database and a second hardening call then fails. Opening a separate hardened read-only connection is also refused — DuckDB will not open one file under two configurations. So the sandbox moved to `open_lakehouse`, where it belongs, and [export_silver](../src/kkb_agent/lakehouse/store.py) now writes Parquet through PyArrow instead of `COPY ... TO`. The pipeline does its own file I/O in Python, so SQL never needs the capability back and the whole analysis database is permanently sandboxed rather than only during a tool call.
- The whitelist closes a gap the statement check misses: DuckDB reads `SELECT * FROM 'secrets.parquet'` as a base table named `secrets.parquet`, so an implicit file scan is refused by name rather than slipping through as an ordinary SELECT.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_lakehouse_tool.py` — 39 passed, most of them attacks: a statement hidden after a comment, eight non-SELECT verbs including `ATTACH`, `INSTALL` and `COPY ... TO`, four file-reading functions and one buried in a subquery, forbidden tables reached through a join and through a CTE, and the implicit file scan. Recorded fast checks: Ruff 0.16.6 clean over 52 files, `pytest -q tests/unit` — 515 passed, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**.
- Two findings were fixed rather than suppressed. Bandit flagged an interpolated table name in the export; the statements are now literal, so nothing from outside can reach that string by construction. It also flagged an `assert` used as a contract check in the tool — asserts vanish under `-O`, and a runtime guarantee that disappears in production is not a guarantee, so it is an explicit raise. An existing test that read an export back through `read_parquet` now reads it with PyArrow, which the sandbox forced and which independently proves the file is real Parquet.
- Blocker: none.
- Previous handoff (historical; current queue controls selection): a validated plan step can now run SQL against real data and get rows back, and the tested SQL escape paths are refused; resource/reference limitations remain in SECURITY. What is still missing between here and an answer: the tool returns rows but writes no lineage node, so a value it produces is not yet traceable — wiring that to DEC-118 is the next step, followed by the verifier that checks each number in the answer text against a cell.

## Acceptance criteria

Material numbers match independent expected values within stated per-case tolerances. Unsupported/undefined statistics return explicit outcomes. Lag direction, periods, units, sample counts, and assumptions are visible. Causal language is limited to what the selected method and evidence support.

## Evidence / implementation record

PR #31 delivers the lakehouse SQL tool; #32 adds optional query metadata lineage. Typed financial-result contracts are M6-01; no anomaly, causality or change_detection implementation exists. DEC-112/120 settled engine/method direction; specific numerical oracles and policies still require implementation evidence.


## Handoff notes

Do not wait for advanced causality to deliver a tested change/association path. Review expected numbers independently of the implementation; identical formulas copied into tests are weak evidence.

<a id="m7"></a>
# M7 — External source / URL / document ingestion

Status: PARTIAL — M7-01/02/03/05 DONE (PRs #35/36/37/38 merged); M7-06 negative coverage is DONE for the enabled direct-GET path. Redirect following remains deferred to M7-04; parsers/adapters and source/network permissions remain incomplete.

## Objective

Add a second supported external source without allowing hostile content, URLs, or files to control execution.

## Dependencies

M1 ingestion contract, M2 relevant semantics, SEC-URL-01 and SEC-FILE-01/02 before exposure, Q-NET-01/02 for live access. PDF/image scope depends on Q-DATA-02 and extraction capability.

## Tasks

- [x] M7-01 — Status: DONE. Owner: Çağatay; Branch: `feature/m7-01-safe-fetch-contract`; PR: [#35](https://github.com/cagatayeroglu/KKB-DataTrio/pull/35) merged at `9185730`; Commit: `64654e7`. Define one source safe-fetch API and structured outcomes; configure limits before implementing retrieval. Evidence: [M7-01 active record](#m7-01-active-record).
- [x] M7-02 — Status: DONE. Owner: Çağatay; Branch: `feature/m7-02-url-target-validation`; PR: [#36](https://github.com/cagatayeroglu/KKB-DataTrio/pull/36) merged at `2678613`; Commit: `be3a184`. Validate HTTP(S), reject credentials in URLs, and block loopback/private/link-local/metadata targets including IPv6. Evidence: [M7-02 active record](#m7-02-active-record).
- [x] M7-03 — Status: DONE. Owner: Çağatay; Branch: `feature/m7-03-dns-binding`; PR: [#37](https://github.com/cagatayeroglu/KKB-DataTrio/pull/37) merged at `2f9cde6`; Commit: `4ef4415`. Validate DNS results and the actual connection destination; reject mixed public/private resolution and rebinding hazards. Evidence: [M7-03 active record](#m7-03-active-record).
- [ ] M7-04 — Handle redirects explicitly; revalidate every destination, cap hops, and avoid forwarding credentials across origins.
- [x] M7-05 — Status: DONE. Owner: Çağatay; Branch: `feature/m7-05-bounded-http-fetch`; PR: [#38](https://github.com/cagatayeroglu/KKB-DataTrio/pull/38) merged at `dfcd7c5`; Commit: `bee17bd`. Bound connect/read/total time, response/decompressed bytes, and content-type routing; do not buffer unlimited responses.
- [x] M7-06 — Status: DONE for the current direct-GET boundary; delivered tests merged in PRs #36/37/38. Add negative tests for forbidden addresses/schemes, redirects, misleading content headers, and oversized/slow streams. Evidence: [M7-06 acceptance reconciliation](#m7-06-acceptance-reconciliation).
- [ ] M7-07 — Extract HTML tables/text with source fragment identifiers; ignore embedded instructions/scripts as authority.
- [ ] M7-08 — Route downloaded CSV/XLSX through the same local file guards and parser contracts as uploads.
- [ ] M7-09 — Implement bounded PDF text/table extraction if in required scope; retain page/table coordinates and extraction warnings.
- [ ] M7-10 — Handle scanned/unreadable PDFs explicitly; do not silently invent table cells.
- [ ] M7-11 — Vision/OCR capability is confirmed in DEC-129 and its **exact prompt/`extra_body` values are now recorded there** (2026-09-10 amendment), so that prerequisite is met. Supported document scope is also no longer open-ended: [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) confirms PDF, Excel, image and text at prompt-supplied URLs as required demo-day capability. Remaining work is bounded PDF-to-PNG rendering, parsing limits and untrusted layout-tag handling. Keep unsupported-input errors usable meanwhile; no OCR implementation is delivered.
- [ ] M7-12 — Preserve filename/URL/page/sheet/cell metadata as untrusted provenance, with sensitive locator parts removed.
- [ ] M7-13 — Test malicious HTML, PDF text, and spreadsheet-cell instructions cannot change tool authority or trigger exfiltration.
- [ ] M7-14 — Add an external series to an existing workspace and verify prior state/evidence remain intact.
- [ ] M7-15 — Test changed schemas, missing tables, parser failure, unavailable source, and contradictory source metadata.
- [ ] M7-16 — Run targeted boundary/extraction negative tests, lint, and the fast PR gate; record limits, supported formats, and restrictions; reserve full checks for checkpoints or explicit requests.

### M7-01 active record

- Status: DONE — PR #35 merged into `dev` at `91857304a8fa7e7780d74db22acedbba42860483`; merged tree matches validated delivery `5366de6`
- Owner: Çağatay
- Branch: `feature/m7-01-safe-fetch-contract`, from `dev` `41e302ce8959da480a8cecc826fd3ef39b6de899`
- PR: [#35](https://github.com/cagatayeroglu/KKB-DataTrio/pull/35) merged into `dev`; final Fast PR gate PASS (55s). Draft claim preceded implementation; no ownership collision.
- Commit: implementation `64654e7e87081f1ac15363d9b5db19d4fdd6c316`; claim `7c4bd164b8f93c450a9355d46026419390a80bc0`
- Objective: Define one source safe-fetch API and structured outcomes; configure limits before implementing retrieval.
- Delivered: [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py) provides typed immutable requests, success/failure outcomes, fixed error codes and validated locator/byte/time/redirect/media-type configuration. Uses existing `ContractModel` and M1 admission byte defaults. URLs and content are excluded from repr/ordinary exports; opaque source IDs link caller provenance. The entry point revalidates records and returns `NETWORK_DISABLED` (or locator `SIZE_LIMIT`) without DNS/socket I/O.
- Limits: operator defaults — 4096 URL characters, 10 MiB encoded/decoded HTTP body budgets, 3 redirects, 5s connect/read and 30s total. These are configuration contracts; M7-02..06 must enforce them during live retrieval. Accepted media types are explicit per request. Archive/parser budgets remain owned by M1.
- Readiness: M1 contract/admission and SEC-URL policy exist; the offline contract requires no model, live-source permission or unresolved architecture decision. User prioritizes the real-source path ahead of independent READY work. Teammate ownership is unchanged.
- Tests: PASS (2026-09-09; Python 3.12.2). `python -m pytest -q tests/unit/test_safe_fetch.py --disable-warnings --maxfail=1` — **67 passed in 0.42s**; touched-code Ruff PASS. `make quick` — **619 passed in 25.14s**, 25.92s wall. `make pr` — **619 passed in 13.34s**, 15.23s wall; Ruff format/lint, Bandit and secret scan PASS. No full/release or live-network checks run.
- Limitations: no HTTP transport, destination/DNS/redirect/stream enforcement, adapters, parsers or provider changes. Constructed success records are not proof of file admission, source permission or financial meaning; a synthetic CSV test explicitly passes the bytes through M1 admission. Do not log unfiltered Pydantic error dictionaries; only their sanitized text or fixed categories.
- Blocker: none for M7-01; M7-02..06 and Q-DATA-01/Q-NET-01/02 still gate live adapters.
- Handoff: Merge verified; M7-02 has been triaged and claimed below. Keep live transport disabled until the remaining controls and permissions are satisfied. M6-01 remains the first independent READY task; M0-08 typing debt remains visible. Do not interpret this contract delivery as a completed real-source vertical slice.

### M7-02 active record

- Status: DONE — PR #36 merged into `dev` at `26786133bb6344fd4492bd52bf7b823f22168b25`; merged tree equals validated delivery `4716b30`.
- Owner: Çağatay
- Branch: `feature/m7-02-url-target-validation`, from `dev` `91857304a8fa7e7780d74db22acedbba42860483`
- PR: [#36](https://github.com/cagatayeroglu/KKB-DataTrio/pull/36), `feature/m7-02-url-target-validation` -> `dev`, merged; final Fast PR gate PASS (44s); draft claim published before implementation and collision check repeated.
- Commit: `be3a184cd1d93db65fb18b8d52732c85677c5e27` (final implementation correction); initial implementation `c8b41f4`, claim `6064fbc`.
- Objective: Validate HTTP(S), reject credentials in URLs, and block loopback/private/link-local/metadata targets including IPv6.
- Readiness: Triaged READY after M7-01 merged and its final CI passed. Typed fetch contracts and SEC-URL-01 policy are available; no owner/open PR/remote claim or unresolved organizer/team decision blocks this offline task. The user explicitly selects this source-path prerequisite; M6-01 is not started.
- Acceptance: Deterministic URL/host/literal-IP validation; reject credentials, unsafe ports, local/private/link-local/metadata destinations and ambiguous IP forms; validate supplied resolution results and redirect destinations without HTTPS downgrade. Fixed rejection reasons; no live DNS/HTTP, TLS changes, adapters or tool orchestration. Actual DNS/connection binding and redirect execution remain M7-03/04.
- Delivered: [URL target policy](../src/kkb_agent/ingest/url_targets.py), integrated into [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py), with [policy tests](../tests/unit/test_url_targets.py) and updated [contract tests](../tests/unit/test_safe_fetch.py). Canonical authority, explicit fixed rejection reasons, literal/supplied DNS IP checks (including mixed results), relative redirect validation and HTTPS downgrade rejection. Safe diagnostics omit locators. Every fetch still refuses network I/O.
- Tests: PASS (2026-09-09, Python 3.12.2). `pytest -q tests/unit/test_safe_fetch.py tests/unit/test_url_targets.py --disable-warnings --maxfail=1` — **196 passed / 0.18s**; `make quick` — **748 passed / 15.29s**; `make pr` — **748 passed / 14.13s**, Ruff format/lint, Bandit and repository secret scan clean. `git diff --check` clean. No full/release checks or live network tests. Final delivery Fast PR gate PASS (44s), verified before merge.
- CI follow-up: Initial delivery `1d1c53e` failed on Python 3.12.14 because its parser rejected a malformed bracketed IPv6 authority earlier than local Python 3.12.2, yielding `MALFORMED_URL` instead of `INVALID_HOST`. `be3a184` standardizes that rejection and its exact test oracle; the URL remains blocked. Local targeted/fast checks above were rerun after the correction. Replacement delivery run PASS.
- Limitations: Only HTTP:80/HTTPS:443; DNS names must already be ASCII (IDNA form if needed), and IPv6 must be native public unicast in `2000::/3` outside blocked special ranges. Ambiguous/transition forms fail closed. Supplied DNS answers are data, not live resolution or a connection pin; unresolved names retain `addresses=None`. Redirect validation does not follow hops. Actual DNS/peer binding, redirects/loops, proxy behavior, streaming/content/deadline controls and TLS transport remain disabled/deferred; no adapter or financial semantics are introduced.
- Blocker: none for this offline validation scope; M7-03..06 and source/network permission still gate live fetch.
- Handoff: Merge verified; M7-03 triaged and claimed below for actual DNS-to-connection binding and rebinding rejection using this policy. Enforce the returned canonical destination at the future transport boundary; never treat URL validation alone as SSRF protection. M7-04 owns redirect execution/budgets; M7-05/06 own remaining bounded transport and integrated negatives. Real BDDK access still needs those controls, source/network permission and an explicit trusted CA bundle where needed, never disabled TLS verification. M6-01 remains independent and unclaimed; do not start it as part of this delivery.

### M7-03 active record

- Status: DONE — PR #37 merged into `dev` at `2f9cde6eb76b35cdf3f9ea1254157b23e032a379`; merged tree equals validated delivery `c3caa92`.
- Owner: Çağatay
- Branch: `feature/m7-03-dns-binding`, from `dev` `26786133bb6344fd4492bd52bf7b823f22168b25`
- PR: [#37](https://github.com/cagatayeroglu/KKB-DataTrio/pull/37), `feature/m7-03-dns-binding` -> `dev`; merged; final Fast PR gate PASS (48s). Claim published before implementation; no conflicting PR/remote claim on recheck.
- Commit: `4ef441593100fb4bc577a78a14798138ba2417a7` (implementation); claim `ad42699`.
- Objective: Validate DNS results and the actual connection destination; reject mixed public/private resolution and rebinding hazards.
- Readiness: Triaged READY after verified M7-02 merge and final CI PASS. Existing URL policy/fetch contracts and SEC-URL-01 provide prerequisites; no active owner, open PR or remote task claim, and no unresolved decision blocks this generic implementation with fake network tests. M6-01 is not started.
- Acceptance: Validate all resolver answers before connecting; connect an explicit numeric IPv4/IPv6 socket and verify the actual peer matches the chosen address/port. Keep TLS certificate and original-hostname verification. Reconnects and redirect targets use fresh resolution and the same binding path. Fixed structured failures; no independent hostname resolution by an HTTP client, implicit proxy, automatic redirects or live fetch activation.
- Approach: A small standard-library HTTPConnection subclass owns connection establishment; socket.connect receives only the checked numeric address, and ssl.create_default_context wraps it with the original hostname. No dependency/framework decision or DNS cache is introduced. Fake resolver/socket/TLS tests cover validation-to-connect changes and blocked IPv6.
- Delivered: [internal SourceConnection](../src/kkb_agent/ingest/_source_connection.py) owns initial/reconnect DNS and socket creation; all answers pass the existing target policy before one numeric address is selected. The peer IP/port is checked before TLS/HTTP and again after TLS. Original hostname/SNI and required certificate checks are preserved; redirects create fresh bound connections. Fixed FetchFailure outcomes include PEER_MISMATCH; failed sockets close without leaking raw exceptions. No runtime adapter calls this primitive; safe_fetch remains NETWORK_DISABLED.
- Tests: PASS (2026-09-09, Python 3.12.2). `pytest -q tests/unit/test_source_connection.py tests/unit/test_safe_fetch.py tests/unit/test_url_targets.py --disable-warnings --maxfail=1` — **243 passed / 0.30s** (47 new binding cases); `make quick` — **795 passed / 14.59s**; `make pr` — **795 passed / 14.51s**, Ruff format/lint, Bandit and secret scan clean. Fake DNS/socket [tests](../tests/unit/test_source_connection.py) use a real default SSLContext with a stubbed handshake and exercise the stdlib HTTP connect hook, IPv4/IPv6 rebinding, mixed answers, reconnect/redirect resolution, peer mismatch, failed TLS and cleanup/redaction. No live/full/release checks. Final delivery Fast PR gate PASS (48s), verified before merge.
- Limitations: Internal connection establishment only, not bounded HTTP retrieval. First validated address only; no address fallback/retry, pool or DNS-cache claims. Connect/read socket timeouts exist, but blocking OS DNS and the combined operation do not yet have an enforced wall-clock deadline (M7-05). DNS changes cannot redirect the already selected numeric socket; a reconnect/new redirect resolves and checks again. Trusts the OS socket/peer interface, retains TLS verification, and rejects proxy tunnels.
- Blocker: none for M7-03; merge and validation verified. Live content fetching still needs the controls below and Q-DATA-01/Q-NET-01/02 access confirmation.
- Handoff: Merge verified; M7-05 triaged READY and claimed below. M7-04 remains deferred while direct fetch rejects redirects. Before the first bounded byte fetch, M7-05 must wire this connection into safe_fetch with DNS/total deadlines, bounded HTTP headers/body/decompression and explicit content routing; M7-06 must prove the corresponding negative paths. Redirects need an explicit policy: reject all 3xx for a zero-hop first fetch, or complete M7-04 fresh binding/hop/loop limits and safe header handling before following any hop. A failing BDDK certificate chain requires an explicitly trusted CA bundle, never disabled verification. M7-08/file guards apply before parsing downloaded spreadsheets; HTML/PDF/OCR, workspace integration and broader extraction cases (M7-07/09..15) are not prerequisites for retrieving bounded bytes. Do not create enterprise hardening tasks or start M6-01.

### M7-05 active record

- Status: DONE — PR #38 merged into `dev` at `dfcd7c5d648b865561aba3a58f4d0b6a49cf9269`; merged tree equals validated delivery `c5c25d3`.
- Owner: Çağatay
- Branch: `feature/m7-05-bounded-http-fetch`, from `dev` `2f9cde6eb76b35cdf3f9ea1254157b23e032a379`
- PR: [#38](https://github.com/cagatayeroglu/KKB-DataTrio/pull/38), `feature/m7-05-bounded-http-fetch` -> `dev`; merged; final Fast PR gate PASS (59s). Draft claim published before implementation; no collision on post-publication PR/remote recheck.
- Commit: `bee17bd3b4e97430a92f88cb4a9f365b86d8fe1c` (implementation); claim `3972d7495922c705bea855835fb72b577f07a80e`.
- Objective: Bound connect/read/total time, response/decompressed bytes, and content-type routing; do not buffer unlimited responses.
- Readiness: Triaged READY after M7-03 merge and final Fast PR PASS. M7-01/02/03 contracts/policy/pinned sockets and SEC-URL-01 are available; no competing owner or unresolved decision blocks synthetic-test implementation. Explicit user priority selects this source path. M7-04 is not a prerequisite when every 3xx fails closed; live source/egress permissions remain separate.
- Acceptance: Actual direct bounded GET through the existing DNS-bound connection, connect/read and whole-operation deadlines (including blocking DNS), aggregate header/framing and encoded/decoded byte limits, strict accepted content type, structured sanitized failures. Reject redirects and unsupported transfer/content encodings; preserve verified TLS. No adapters, POST contract, parser, proxy or retry framework.
- Delivered: [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py) performs a direct GET through the unchanged M7-03 DNS/peer/TLS policy. A [fixed worker](../src/kkb_agent/ingest/_fetch_worker.py) owns the connection and [bounded HTTP response reader](../src/kkb_agent/ingest/_bounded_response.py); the [parent supervisor](../src/kkb_agent/ingest/_fetch_process.py) kills/reaps the child at DNS/connect or total timeout, with no abandoned resolver thread. Fixed interpreter/module, isolated Python, validated JSON on stdin, no shell/model command; output is a bounded result with fixed error categories. No dependencies added.
- Limits: 32 KiB aggregate status/header/chunk-framing budget; 16 KiB reads and independent 10 MiB encoded/decoded defaults. Connect 5s includes child startup/DNS/TCP/TLS; read 5s limits stalled socket I/O; total 30s never restarts. Deadlines use parent monotonic time; OS process-start/kill/reap scheduling overhead is not a hard real-time guarantee. Install the package in the active interpreter (`make install-dev`) so the isolated worker can import it.
- Formats: Explicit accepted media types only; Content-Length, connection-close and bounded chunked bodies; identity or single-member gzip with bounded output/checksum/EOF checks. Reject all 3xx even when max_redirects > 0, duplicate/ambiguous framing, interim/upgrade responses, chunk extensions/trailers, concatenated gzip, other encodings and truncated bodies. No silent numerical/financial normalization; bytes remain subject to downstream file/parser admission.
- Tests: PASS (2026-09-09, Python 3.12.2). `pytest -q tests/unit/test_bounded_fetch.py tests/unit/test_safe_fetch.py tests/unit/test_source_connection.py tests/unit/test_url_targets.py --disable-warnings --maxfail=1` — **340 passed / 4.54s**. `make quick` — **892 passed / 17.30s**. `make pr` — **892 passed / 16.73s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the three new modules PASS; CPython-private hooks have focused typeshed annotations and wire-level tests. [Tests](../tests/unit/test_bounded_fetch.py) cover exact/over byte and header limits, malformed/truncated/chunked/gzip responses, decompression bomb, timeout/cleanup, redacted failures, original TLS host and blocked targets; real local child processes simulate stalled DNS/body without internet. No live, full or release checks.
- Blocker: none for M7-05; merge and final-head Fast PR PASS verified. Source/network permissions still block live-source execution.
- Limitations: GET only; no source adapter/tool exposure, POST body, redirect following, auth/cookies, proxy, retry, parser or source-specific CA handling. M7-06 direct-fetch coverage is reconciled below; any new POST/redirect path must add its own targeted negative tests. Do not infer live-source permission or completed M7 from synthetic validation.
- Handoff: Merge verified; M7-06 is satisfied by existing merged tests without duplicate implementation. Stop here; M3-06 is not started while source/egress permission remains unresolved. First BDDK request still needs Q-DATA-01/Q-NET-01/02 source/egress approval and the explicit verified CA bundle documented in [BDDK_SOURCE](BDDK_SOURCE.md); no live TLS recheck was made here. Its bulletin data endpoints are POST, so M3-06 will need bounded generic POST/form support before actual data loading. Documented direct HTTPS endpoints do not establish a redirect requirement: M7-04 is needed only if following a 3xx is required. M7-07/08 apply when parsing HTML/files, not merely retrieving bounded bytes. M6-01, main and the Day 0 stash remain untouched.

### M7-06 acceptance reconciliation

- Status: DONE for the enabled direct-GET boundary; no new code/tests required.
- Owner: Çağatay (coverage review and existing delivery)
- Branch: test implementations in `feature/m7-02-url-target-validation`, `feature/m7-03-dns-binding` and `feature/m7-05-bounded-http-fetch`; bookkeeping on `docs/m7-05-m7-06-completion` from latest `dev`.
- PR / Commit: merged PRs [#36](https://github.com/cagatayeroglu/KKB-DataTrio/pull/36) (`be3a184`), [#37](https://github.com/cagatayeroglu/KKB-DataTrio/pull/37) (`4ef4415`) and [#38](https://github.com/cagatayeroglu/KKB-DataTrio/pull/38) (`bee17bd`); integrated at `dfcd7c5`.
- Tests: existing validated delivery — 340 targeted / 892 unit tests, `make quick`, `make pr` and final-head Fast PR PASS (59s). Merge tree equality preserves this evidence; no application tests rerun for bookkeeping.

| M7-06 requirement | Existing test/code evidence | Result |
| --- | --- | --- |
| Forbidden addresses/schemes | [URL policy tests](../tests/unit/test_url_targets.py): `test_invalid_urls_have_fixed_rejection_reasons`, `test_unsafe_literal_and_dns_addresses_are_rejected`; [boundary tests](../tests/unit/test_safe_fetch.py): `test_url_policy_precedes_worker_dispatch`. DNS/peer rejection also exercised through the worker. | Satisfied; blocked targets are not contacted |
| Redirects | [Bounded fetch tests](../tests/unit/test_bounded_fetch.py): `test_redirects_never_follow_or_resolve_location`; [binding tests](../tests/unit/test_source_connection.py): fresh redirect validation and HTTPS downgrade rejection. | Satisfied for zero-hop policy; following/loop execution remains M7-04 |
| Misleading content headers | `test_malformed_or_unsupported_metadata_rejected_before_body`, `test_malformed_headers_fail_closed`, `test_truncated_or_corrupt_payload_is_never_success` in bounded fetch tests. | Satisfied; explicit accepted types, framing/length checks |
| Oversized streams | `test_body_exact_limit_and_one_over`, `test_missing_length_is_bounded_and_can_finish_at_eof`, `test_decompressed_budget_applies_to_identity_and_gzip`, `test_oversized_header_fails_before_body`, chunk/encoded-size cases. | Satisfied; header, encoded and decoded budgets |
| Slow streams | `test_timeouts_return_fixed_outcomes_and_close_resources`, `test_real_child_is_killed_and_reaped_at_deadline_without_network`, `test_deadline_does_not_restart_after_connected_marker`. | Satisfied; connect/read/total failures and worker cleanup |

- Blocker: none for this coverage scope. This does not complete M7 parsers, redirect following or source access approval.
- Handoff: No duplicate generic security work. M3-06 still needs approved source/egress access, bounded POST/form support and an explicit verified CA bundle before the documented BDDK bulletin request. Tests for future POST/redirect capabilities belong with those changes; no live request or new task is started here.

## Acceptance criteria

Every enabled external retrieval uses the central boundary, including redirects and source adapters. All enabled parsers receive bounded validated content. Material extracted values retain source locations and validation status. Unsupported/ambiguous extraction results cannot become verified numerical claims.

## Evidence / implementation record

- Owner: Unassigned; lanes A/B, C owns adversarial fixtures.
- Branch: —
- PR: —
- Commit: —
- Tests: M7-01/02/03/05 delivery checks and M7-06 reconciliation PASS as recorded above; parser and live-source acceptance remain incomplete.
- Benchmark: External-format and injection catalog planned.
- Notes: Local file ingestion is not permission to fetch arbitrary URLs.
- Known limitations: Generic bounded direct GET is merged; source adapter/tool exposure and document/OCR runtime support remain incomplete. Vision/OCR availability and its literal request contract are both recorded in DEC-129; the former "obtain the OCR literals first" blocker is cleared. Required format scope is now confirmed by DEC-131 as PDF, Excel, image and text at prompt-supplied URLs. Demo internet/egress (Q-NET-01) and the URL permission boundary (Q-NET-02) remain unresolved, as do remaining request limits.
- Previous handoff (historical; current queue controls selection): Build M7-01/02 against fake transport after contract review; enable live paths only after controls and policy are confirmed.

## Handoff notes

Model-suggested URLs still need full validation. If network-safe enforcement cannot be guaranteed, leave the live capability disabled and record the limitation; do not substitute an unrestricted HTTP client.

<a id="m8"></a>
# M8 — Verification / evidence / provenance

Status: PARTIAL — lineage and a numeric-binding verifier shell are merged. Matching a number to any nearby stored value (or allowing context/year values) is not semantic/run/result verification. Second-path recomputation, stale/tampered-result rejection, complete claim identity and an integrated answer gate remain; see the verifier record.

## Objective

Prevent unsupported claims from reaching the answer and make accepted results reproducible from recorded inputs.

## Dependencies

Validated M0 record models; M1 source references; M5 tool runs; M2/M6 outputs as they become available. Minimal source/change verification starts before the full analytics catalog.

## Tasks

- [ ] M8-01 — Status: PARTIAL — merged scope; remaining acceptance: Numeric verdict types exist; claim-type/run/result/period/unit requirements are not enforced. Owner: Eray; Branch: `feature/m8-verifier`. Define material-claim types and their minimum source/run/period/column/transformation/validation requirements. Evidence: [verifier record](#verifier-record).
- [ ] M8-02 — Status: PARTIAL — merged scope; remaining acceptance: Core records and numeric matching have tests; unresolved source/run/transformation references are not rejected end to end. Owner: Eray; Branch: `feature/m8-verifier`. Validate existing evidence models with targeted tests, including NOT_RUN defaults and unresolved references. Evidence: [verifier record](#verifier-record).
- [ ] M8-03 — Implement evidence registration and stable IDs tied to workspace/tool runs.
- [ ] M8-04 — Validate source, input/output, tool-run, and transformation references resolve; reject orphan evidence.
- [ ] M8-05 — Attach lineage at ingestion, transformation, and analytical execution time, not only during synthesis.
- [ ] M8-06 — Implement deterministic verification for basic change/numeric results against preserved input references.
- [ ] M8-07 — Status: PARTIAL — merged scope; remaining acceptance: Value proximity is checked; unit/period/sample-count and transformation-prerequisite validation is missing. Owner: Eray; Branch: `feature/m8-verifier`. Verify units, periods, sample counts, and transformation prerequisites alongside values. Evidence: [verifier record](#verifier-record).
- [ ] M8-08 — Distinguish passed, failed, and not-run validation; partial results must identify exactly which claims are supported.
- [ ] M8-09 — Detect conflicting sources/vintages and surface the disagreement instead of choosing silently.
- [ ] M8-10 — Gate answer assembly so unsupported claims are omitted, qualified, or answered with abstention.
- [ ] M8-11 — Keep source citations separate from computation verification; a URL alone cannot prove a calculation.
- [ ] M8-12 — Test stale evidence after changed dates/assumptions and invalidate dependent claims.
- [ ] M8-13 — Render concise evidence summaries with safe locators and limitations for M10.
- [ ] M8-14 — Test missing source/run/transformation links, altered numeric output, and unsupported causal statements.
- [x] M8-15 — Status: DONE for the delivered numeric-binding scope. Run targeted evidence/verifier/contract tests, lint, and the fast PR gate when changing shared models. Evidence: PR #32, 37 targeted / 552 unit tests and fast checks; this is not full proof validation.
- [x] M8-16 — Status: DONE for the delivered-scope handoff. Record verified claim types, evidence gaps, and the next tool needing verification. Evidence: PR #32's limitations and the reconciled record below; second-path verification remains unimplemented.

### Verifier record

- Status: PARTIAL — merged/validated numeric matching; M8-01/02/07 and claim/run/snapshot/recompute/answer-gate acceptance remain
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m8-verifier`; fresh `dev` base `6b1ee47`
- PR: [#32](https://github.com/cagatayeroglu/KKB-DataTrio/pull/32) — merged into `dev` at `ec1d783`; original claim publication retained in Git history
- Merge evidence: `ec1d783` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `35ab8ea`; implementation recorded in the PR
- Objective: Close the evidence chain — the lakehouse tool records that a query ran, and the verifier binds every number in an answer to a stored cell before the answer may leave.
- Scope: query lineage, number extraction in the formats a Turkish answer uses, and cell binding. Second-path recomputation, the web cross-check and the vision rule stay unimplemented and are named as limitations rather than omitted quietly.
- Implementation: [agent/verifier.py](../src/kkb_agent/agent/verifier.py) and query recording in [tools/lakehouse.py](../src/kkb_agent/tools/lakehouse.py). `verify` extracts every quantity in an answer and binds it to a gold cell, a silver observation, a caller-justified context value or a year; anything left unbound **rejects the answer**. Not annotates — rejects. A gold match carries its lineage node; silver/context/year bindings need not. Matching uses value proximity, not claim-specific series/period/unit/run constraints.
- Numeric extraction tests include Turkish grouped `801.438` and decimal `46,75`, malformed grouping such as `1.23.456`, and identifiers such as `TP.KTF12`. The parser rejects malformed grouping, but a single separator followed by three digits can be interpreted as thousands without explicit locale/semantic context. That remaining ambiguity must not be presented as fully resolved.
- A real defect was found by a failing test. The first pattern matched only `\d{1,3}` before a group separator, so a plain number longer than three digits — `801438`, or any year — **matched nothing at all**. An unmatched number is one the verifier never checks, which is the worst possible failure for a gate whose entire job is to check numbers. The pattern now tries the grouped form first and falls back to a plain run of digits.
- Query provenance is deliberately **table-level** and says so in the node it writes. Deriving which individual cells produced an arbitrary SQL result needs a full column analyzer; claiming more than we compute would be worse than claiming less. The current verifier only finds a numerically close stored value; it does not establish exact claim/period/unit/run identity. Identical queries record one node; a rejected query records nothing.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_verifier.py` — 37 passed. Recorded fast checks: Ruff 0.16.6 clean over 54 files, `pytest -q tests/unit` — 552 passed, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**.
- End-to-end: one test runs a query through the tool, formats the returned value into a Turkish sentence, verifies that sentence, takes the lineage node the verdict names, and reads the original bronze bytes back through the graph. This validates a composed fixture lookup/ancestry path, not independent recomputation or an integrated Session answer gate.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): the PR #32 fixture composes SQL, numeric matching and source ancestry; full Session/workspace/verification integration remains incomplete; none of them is fed by a real adapter, because M3-05 through M3-08 are unwritten and the safe-fetch layer does not exist. The verifier's remaining DEC-119 rules — recomputing a headline metric on a second path, cross-checking against a searched source, and refusing model-extracted document content that fails a consistency check — are the next correctness work, and they are listed in the verdict's own limitations so nothing downstream can mistake this for full verification.

## Acceptance criteria

For each supported material claim, a teammate can resolve source -> inputs -> transformation/tool run -> validation -> displayed value. Corrupt/missing/stale evidence prevents a verified answer. Verifier failures are visible and cannot be repaired by changing model prose alone.

## Evidence / implementation record

PR #32 delivers a separately callable numeric-matching shell with 37 targeted tests, not a completed proof gate. Core EvidenceRecord defaults to NOT_RUN and permits an absent run. Missing/stale/altered input/result/run checks and second-path recomputation remain. Source ancestry alone cannot mark a material claim VERIFIED.


## Handoff notes

Do not equate an evidence object with validated evidence. Keep original observations and derivations distinguishable, and avoid storing full private payloads in provenance records.

<a id="m9"></a>
# M9 — Evaluation / adversarial benchmark

Status: BLOCKED for M9-01 delivery/review of preserved Day 0 drafts. No benchmark schema/corpus/runner is delivered in dev. Independent case/oracle design may proceed without applying the stash.

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

Historical Day 0 inspection recorded a case schema, three questions (`monthly-change`, `unknown-frequency`, `simple-correlation`) and a schema test in the named local stash. None is delivered in dev; no benchmark command, numerical runner or scorecard exists. M9-01 is BLOCKED on separately authorized review/delivery of that draft, not READY. Design independent oracles and the extended tracks in EVALUATION without applying the stash in this docs task.


## Handoff notes

Update the command registry in EVALUATION when a runner actually exists. Keep live network tests out of ordinary deterministic smoke. Share failed case IDs and categories, not long raw model/input dumps.

<a id="m10"></a>
# M10 — UI / demo workflow

Status: NOT STARTED. Framework settled by [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end); hosting still depends on Q-INFRA-01 and remaining demo format on Q-DEMO-01. [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) now confirms that Final Day expects a **deployed, running solution** producing output from organizer-supplied inputs — so deployment is a requirement, not a stretch goal, even though its environment is unstated. Operator-flow specification can proceed.

## Objective

Let a teammate demonstrate the analysis, inspect evidence, and recover from expected failures without backend knowledge.

## Dependencies

A minimal M1/M4/M5/M6/M8 slice for live integration; confirmed demo environment/frontend choice. Wireframes and operator scripts can be specified earlier without choosing a framework.

## Tasks

- [ ] M10-01 — Specify operator steps: load/select source, ask question, inspect plan, inspect result/evidence, follow up, recover/reset.
- [ ] M10-02 — Status: PARTIAL — dates are confirmed by DEC-131 (development to 20 September 2026; Final Day 17 October 2026) and a live deployed solution is required. Confirm the remaining demo duration, environment, audience interaction and allowed fallback assets in Q-DEMO-01/02/03 and Q-INFRA-01.
- [ ] M10-03 — Scaffold the DEC-123 client in `web/` — Next.js, Tailwind, shadcn/ui, TanStack Table, react-plotly.js; graph-heavy React Flow presentation is deferred under DEC-128 — against the agreed API contract; record installation and runtime consequences.
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
- Notes: DEC-123 selects the frontend/API stack; no implementation exists. DEC-128 defers graph-heavy proof UI.
- Known limitations: Demo environment/duration, session persistence, and fallback permission unknown.
- Previous handoff (historical; current queue controls selection): Specify M10-01 without committing to a framework; resolve M10-02/03 before implementation.

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
- Previous handoff (historical; current queue controls selection): Remain on ordinary feature work until a candidate meets prerequisite acceptance; do not run release checks preemptively.

## Handoff notes

Keep the final record compact but reproducible: revision, environment, commands/results, scorecard reference, limitations, operator script, and permitted fallback. Publishing/merging is not implied by completion of local checks.

<a id="m12"></a>
# M12 — Lakehouse and medallion normalization

Status: PARTIAL — the store, its semantics gate, cumulative handling, alignment, gold joins and lineage are delivered and tested against real published BDDK values; the schema is documented in [DATABASE](DATABASE.md). Not delivered: retrieval into bronze, revisions and vintages (M12-12), index rebasing (M12-17), and the unit and percentage conversions (M12-10/11).

## Objective

Turn retrieved BDDK and EVDS sources into analysis-ready facts on a canonical time spine, with unit, frequency, stock/flow and cumulative semantics recorded explicitly rather than inferred. This milestone decides whether every downstream number is correct.

## Dependencies

M0-01 contracts and M1 loading for input; DEC-112 for the engine, DEC-114 for bulk spreadsheet reading, DEC-118 for lineage writes. M2 owns the normalization policy specifications this milestone implements. Live retrieval needs M3 and Q-DATA-01; synthetic and already-downloaded fixtures need neither.

## Tasks

- [x] M12-01 — Status: DONE — merged/validated (PR #23 and #30 / 99894f3, storage and schema tests). Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Create the DuckDB database and the `bronze`/`silver`/`gold` Parquet layout with a documented schema per layer; commit the database definition, which is a required deliverable. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [x] M12-02 — Status: DONE — merged/validated (PR #23 / 26e801d, byte/hash preservation tests). Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Write every retrieved artifact to `bronze` with its bytes, SHA-256, source locator and retrieval timestamp; never edit a bronze object in place. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [ ] M12-03 — Status: PARTIAL — merged scope; remaining acceptance: Semantic row shape exists; versioned source vintages and revision-safe identity remain M12-12. Owner: Eray; Branch: `feature/m12-01-lakehouse-foundation`. Define the `silver` series row shape: series ID, period, value, unit, scale, frequency, stock/flow, cumulative behaviour, source vintage, and an explicit unknown for each semantic that is genuinely unknown. Evidence: [M12-01/02/03 active record](#m12-010203-active-record).
- [ ] M12-04 — Status: PARTIAL — merged scope; remaining acceptance: Weekly and month-based spines exist; daily/business-day/twice-monthly calendar coverage remains incomplete. Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement the canonical time spine and period labelling, with inclusive/exclusive range behaviour and timezone/calendar conventions stated once. Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [x] M12-05 — Status: DONE — merged/validated (PR #24 / e628169, detection/unknown tests). Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement cumulative detection: distinguish a series cumulative since first publication, a series that resets each January, and a plain flow series, and report low confidence rather than guessing. Detection is **per series, not per source** — [BDDK_SOURCE](BDDK_SOURCE.md) shows monthly table 4 is a stock and table 2 resets every January, in the same bulletin. Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [x] M12-06 — Status: DONE — merged/validated (PR #24 / e628169, baseline/gap tests). Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement non-reset cumulative-to-flow differencing, requiring the preceding baseline for the first derived period. **No merge without unit tests.** Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [x] M12-07 — Status: DONE — merged/validated (PR #24 / e628169, yearly-reset tests). Owner: Eray; Branch: `feature/m12-05-cumulative-semantics`. Implement yearly-reset cumulative conversion with January and missing-prior-period boundary cases. **No merge without unit tests.** Evidence: [M12-04..07 active record](#m12-0407-active-record).
- [ ] M12-08 — Status: PARTIAL — merged scope; remaining acceptance: Weekly-to-monthly alignment is tested; daily-source alignment and complete period-boundary coverage remain. Owner: Eray; Branch: `feature/m12-08-frequency-alignment`. Implement frequency alignment for daily, weekly and monthly sources, including weeks that cross a month boundary; do not assume equal row spacing implies a known reporting calendar. Key on the declared frequency: EVDS publishes nine, including separate Friday and Wednesday weekly anchors and `İŞ GÜNÜ` distinct from `GÜNLÜK`. The reference scenario needs a weekly-Friday rate joined to a monthly stock, so this is on the critical path. Evidence: [M12-08 active record](#m12-08-active-record).
- [ ] M12-09 — Store the aggregation policy in each series' metadata — stock to period end, flow summed, rate by its recorded rule — and read it from metadata rather than branching on the series name in code. EVDS already publishes this per series (`DEFAULT_AGG_METHOD`, `SUMABLE`, `AVGABLE`, ...); carry those flags through instead of re-deriving them, and honour `SUMABLE: 0`.
- [ ] M12-10 — Implement unit and scale normalization for TRY, thousand TRY and million TRY with the applied factor recorded; make unit a required field and reject a series without one. This is not hypothetical: FinTürk publishes Bin TL while the monthly and weekly bulletins publish Milyon TL, and the unit appears only in a caption or a display label.
- [ ] M12-11 — Implement percentage, decimal and basis-point conversion, distinguishing percentage points from relative percent change.
- [ ] M12-12 — Preserve revisions and source vintages; never collapse conflicting historical observations silently.
- [x] M12-13 — Status: DONE — merged/validated (PR #26 / 726f97a, gold join/coverage tests). Owner: Eray; Branch: `feature/m12-13-gold-and-lineage`. Build `gold` joins on the canonical spine with explicit missing-value treatment and observed sample counts. Evidence: [M12-13/14 active record](#m12-1314-active-record).
- [ ] M12-14 — Status: PARTIAL — merged scope; remaining acceptance: Gold/transform lineage can be supplied and traced; pure normalization functions do not enforce a record for every transformation, and a source ancestor is not a complete proof. Owner: Eray; Branch: `feature/m12-13-gold-and-lineage`. Write lineage nodes and edges for every transformation in this milestone; a produced cell without lineage fails review. Evidence: [M12-13/14 active record](#m12-1314-active-record).
- [ ] M12-15 — Add hand-calculated fixtures for each cumulative, aggregation, frequency and unit rule, plus negative tests for unknown unit, unknown frequency and unknown reset behaviour.
- [x] M12-16 — Status: DONE for the delivered policies. Run targeted normalization tests and touched-code lint; record which policies are implemented and which still need source confirmation. Evidence: PRs #23–#26 targeted results below; daily alignment, complete transformation recording and real-source metadata remain incomplete.
- [ ] M12-17 — Handle index base-year variants explicitly: the consumer price index exists as 2003=100 and 2025=100, the housing price index as 2010=100, 2017=100 and current. Parse the base from the title, require an explicit reference period, and verify overlap before rebasing.

### M12-13/14 active record

- Status: PARTIAL group — M12-13 DONE; M12-14 requires complete transformation-to-input recording beyond optional caller-supplied ancestry
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m12-13-gold-and-lineage`; fresh `dev` base `d01edf1`
- PR: [#26](https://github.com/cagatayeroglu/KKB-DataTrio/pull/26) — merged into `dev` at `726f97a`; original claim publication retained in Git history
- Merge evidence: `726f97a` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `53fe043`; implementation recorded in the PR
- Objective: Join normalized series onto one spine as gold, and make every produced cell traceable to the bronze bytes it came from.
- Scope: gold joins and the lineage graph. No retrieval, no verifier, no UI.
- Implementation: [lakehouse/lineage.py](../src/kkb_agent/lakehouse/lineage.py) and [lakehouse/gold.py](../src/kkb_agent/lakehouse/gold.py), with `Observation` moved to [records.py](../src/kkb_agent/lakehouse/records.py) so the layers can speak in observations without importing each other. Both schemas are applied by `open_lakehouse`, and an open lakehouse exposes `.lineage`.
- Lineage is content-addressed. A node id is a SHA-256 over its kind, label, sorted attributes and sorted upstream ids, so the same derivation reached twice is one node and a replayed pipeline converges on the same graph instead of duplicating it. An edge whose upstream does not exist is refused: an edge leading nowhere looks like provenance and is worse than none. `trace` walks ancestors breadth-first, `sources_of` filters them to bronze artifacts, and `missing_provenance` is meant to fail a build rather than warn.
- Gold enforces two rules. A period a series did not publish is **null** — absent and explicitly-missing are treated alike, and nothing is filled forward, because a flat line drawn from a fill is indistinguishable from a real one. And a column with no upstream lineage is **refused at construction**, so an untraceable column cannot reach a table; failing there is cheaper than discovering it in a demo. Coverage is recorded on the column node itself.
- End-to-end slice: a test assembles the reference scenario's shape — the monthly BDDK housing-credit stock beside the weekly EVDS rate reduced onto the same spine — then asserts every column reaches a source file, that the rate column's trace contains the reduction's exact parameters, that the stock column's trace contains no transform, and that the bronze bytes behind a persisted cell are still readable through the graph.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_gold_lineage.py` — 23 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 33 files, `pytest -q tests/unit` — 367 passed in 8.62s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the new modules are strict-clean.
- A circular import appeared and was fixed structurally rather than papered over. `store` needed the gold schema while `gold` needed `Observation` from `store`; moving the value type into its own dependency-free module removed the cycle without lazy imports in the hot path.
- One speculative method was written and removed. DEC-118 names a networkx export for graph layout, but nothing consumes it: `trace` answers every question the pipeline asks today, and the method would have meant an undeclared dependency serving dead code. A comment records where it belongs, and it arrives with the UI task that needs a layout.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): The PR #26 fixture linked bronze, silver, selected transformations and gold; remaining M12 acceptance is explicitly listed above. What is missing before an answer can be produced is everything above the data layer: no adapter fetches a real bulletin, no planner routes a question, no verifier checks a claim against a cell. The agreed next lane is M4, the Kloudeks provider interface, which can be built against a synthetic double while Q-K-01/02/03 remain unanswered.

### M12-08 active record

- Status: PARTIAL — merged/validated weekly-to-monthly scope; daily alignment and full requested-boundary coverage remain
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m12-08-frequency-alignment`; fresh `dev` base `e628169`
- PR: [#25](https://github.com/cagatayeroglu/KKB-DataTrio/pull/25) — merged into `dev` at `d01edf1`; original claim publication retained in Git history
- Merge evidence: `d01edf1` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `6bfa34d`; implementation recorded in the PR
- Objective: Reduce a higher-frequency series onto a lower-frequency spine using the aggregation its source declares, reporting how much of each target period was actually observed.
- Scope: alignment as pure functions. No retrieval, no lineage writing, no gold joins.
- Implementation: [lakehouse/alignment.py](../src/kkb_agent/lakehouse/alignment.py). `to_monthly` reduces a weekly series onto monthly periods; `assign_month` decides where a straddling week lands; `Coverage` reports observed against expected per target period.
- Two things are made explicit rather than assumed. **Which month a straddling week belongs to is a policy the caller must pass** — `BY_END` follows how the source labelled the week, `BY_MAJORITY` puts it where most of its days fell. Both are defensible, only one is right for a given question, and the tests show the two produce different February and March averages from the same input. **Coverage travels with the value**: a month averaged from one Friday and a month averaged from five are not the same claim, and the count is the only thing that distinguishes them once the number exists.
- Expected counts come from the canonical spine, not from what arrived, so a week missing from the middle is counted as missing rather than quietly shrinking the denominator. A month with no observations at all is omitted rather than emitted as zero, and its coverage still records the shortfall. Every input is validated against the declared anchor before any reduction, so an off-anchor date is named rather than surfacing later as an unexplained gap. `method` returns the operation, aggregation, assignment policy and anchor, which is what a transformation record will need under DEC-118.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_alignment.py` — 22 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 29 files, `pytest -q tests/unit` — 344 passed in 8.01s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; alignment is strict-clean.
- Fixtures use real weekly Friday observations read from an EVDS `fe` response during the M3-03 inspection. Their series identity was not resolved in the catalog, so the tests use them for genuine cadence and shape rather than as a claim about a named series; the file says so. The dates are what matter and they are real: January and February 2023 hold four Fridays and March holds five, and two of those weeks straddle a month boundary with most of their days on the earlier side.
- Two defects were found and fixed during the work. The off-anchor rejection originally surfaced as an unexplained spine mismatch, so inputs are now checked against the declared anchor first and the error names the offending date. Two mypy strict errors were introduced and removed before delivery — a loop variable shadowing an optional, and an untyped reducer table — so the M0-08 baseline is unchanged rather than grown.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): the reference scenario's inputs can now share a spine — a weekly Friday-anchored rate reduces onto the monthly stock it must be charted against. Still nothing is persisted or attributed: alignment returns observations and a method dictionary but writes no lineage, which M12-14 and DEC-118 require. The remaining M12 work before an end-to-end slice is M12-13 gold joins and M12-14 lineage.

### M12-04..07 active record

- Status: PARTIAL group — M12-05/06/07 DONE; M12-04 lacks the remaining calendar/spine coverage
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m12-05-cumulative-semantics`; fresh `dev` base `26e801d`
- PR: [#24](https://github.com/cagatayeroglu/KKB-DataTrio/pull/24) — merged into `dev` at `e628169`; original claim publication retained in Git history
- Merge evidence: `e628169` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `4900c43`; implementation recorded in the PR
- Objective: Make cumulative series usable and safe — a canonical period spine, detection that distinguishes the accumulation behaviours measured in the BDDK bulletin, and conversion to flow that refuses rather than guesses.
- Scope: period arithmetic and cumulative semantics as pure functions over observations. No retrieval, no lineage writing, no gold joins, no frequency alignment.
- Implementation: [lakehouse/periods.py](../src/kkb_agent/lakehouse/periods.py) generates the canonical spine so two series that both call themselves monthly cannot disagree about which day a month ends on; [lakehouse/cumulative.py](../src/kkb_agent/lakehouse/cumulative.py) holds `detect_cumulative` and `to_flow`.
- Detection is deliberately unable to answer some questions. A fall outside January rules accumulation out with high confidence. A fall at every observed January boundary rules yearly reset in, at high confidence from two boundaries and low from one. A series that only ever rises returns **UNKNOWN with low confidence and a stated reason**: a since-inception cumulative and a growing stock are identical in the values, and the measured housing-credit series is exactly that case for months at a time. Resolving it needs source metadata, not arithmetic.
- Conversion refuses more than it computes. `to_flow` takes the **declared** kind, never a verdict, so a low-confidence guess cannot authorize a transformation. A yearly-reset January is returned as the published value because the year restarts there; the cross-boundary difference — which would have been −852,934 for net profit at 2026-01 — is never produced. A period with no usable predecessor, a gap in the spine or a missing input comes back `None` rather than a number spanning two periods or an implicit zero. A since-inception series needs an explicit baseline for its first period and returns `None` without one.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_cumulative.py` — 32 passed. Recorded fast checks: Ruff 0.16.6 format and lint clean over 27 files, `pytest -q tests/unit` — 322 passed in 8.57s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**; the new modules are strict-clean and M0-08 still owns the XLSX ones.
- Fixtures are real. Every series in the tests is published BDDK data quoted from the M3-02 retrieval: the housing-credit stock over its falling 2023/7–2024/3 stretch, the same stock rising monotonically through January 2026, and net profit across two real reset boundaries. Synthetic numbers would not have produced the case that matters, which is a genuine stock that looks cumulative.
- Two tests failed first and both were the test's fault, not the code's. One expected high confidence from a window containing a single January boundary; the code was right to say low, so the fixture was widened to two real boundaries. The other built a mixed-reset case too short to judge at all. Bandit then rejected a type-narrowing `assert`, correctly — asserts vanish under `-O` — so the loop was restructured to filter missing values up front instead.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): cumulative series can now be converted safely, and a stock can no longer be differenced into a fake disbursement series by accident. Nothing is persisted or attributed yet: `to_flow` returns observations and writes no lineage, which M12-14 and DEC-118 still require. Next is M12-08 frequency alignment, where the weekly Friday-anchored rate from EVDS meets the monthly stock from BDDK — the reference scenario needs that join and no monthly variant of the rate exists.

### M12-DB active record

- Status: PARTIAL — implemented and validated on the task branch; unchecked until its PR merges into `dev`
- Owner: Eray
- Branch: `feature/database-definition`; fresh `dev` base `dcefc5b`
- PR: [#30](https://github.com/cagatayeroglu/KKB-DataTrio/pull/30) -> `dev`; draft claim published before implementation
- Commit: claim `0c0dc95`; implementation recorded in the PR
- Objective: Close M12-01's remaining half. The schema worked but was spread across four modules with no document, and the brief lists database definitions as a deliverable alongside the architecture drawings and the repository.
- Scope: a written definition, one entry point that applies every schema, and a test that keeps the two in step. No new tables, no behaviour change.
- Implementation: [DATABASE.md](DATABASE.md) documents all nine tables — every column, the invariant each one protects, the layout on disk and how the layers connect. [database.py](../src/kkb_agent/database.py) holds `TABLES` and `apply_schema`, the only thing that creates them; `open_lakehouse` now calls it, so the workspace tables arrive with the rest instead of being applied separately.
- The document is enforced rather than trusted. [test_database.py](../tests/unit/test_database.py) asserts every created table has a heading, every column appears in that table's own section, no documented table is fictional, each layer is introduced, applying the schema twice is a no-op, and every statement is `CREATE TABLE IF NOT EXISTS` — a bare `CREATE TABLE` would discard a demo-day database. A schema document nobody checks is worse than none, because it reads as authoritative while being wrong.
- Tests: PASS (2026-09-09; Python 3.12.5). `pytest -q tests/unit/test_database.py` — 8 passed. Full gate: Ruff 0.16.6 format and lint clean over 49 files, `pytest -q tests/unit` — 475 passed, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged**.
- Blocker: none.
- Handoff: M12-01's deliverable half is closed, and the document names what is still missing rather than implying completeness — catalog and alias tables arrive with M13, evaluation results with M9, and revisions remain unresolved because `silver_observations` permits one value per period and no restatement has been observed. Next is the first real tool, `lakehouse` over gold, which needs exactly this table list for its schema whitelist.

### M12-01/02/03 active record

- Status: PARTIAL group — M12-01/02 DONE (database definition completed in PR #30); M12-03 remains incomplete for source-vintage identity
- Owner: Eray (recorded delivery owner; no active PR found; confirm handoff before resuming remaining scope)
- Branch: `feature/m12-01-lakehouse-foundation`; fresh `dev` base `074a874`
- PR: [#23](https://github.com/cagatayeroglu/KKB-DataTrio/pull/23) — merged into `dev` at `26e801d`; original claim publication retained in Git history
- Merge evidence: `26e801d` is an ancestor of verified `dev`; tests below are historical delivery results, not new runs in this docs task.
- Commit: claim `abd078b`; implementation recorded in the PR
- Objective: Build the medallion container the rest of M12 writes into — the DuckDB database, an immutable bronze layer, and a silver layer that refuses to store a series whose semantics are not recorded.
- Scope: storage and semantics only. No source adapter, no retrieval, no cumulative conversion, no frequency alignment, no gold joins.
- Implementation: [lakehouse/store.py](../src/kkb_agent/lakehouse/store.py) and [lakehouse/semantics.py](../src/kkb_agent/lakehouse/semantics.py). `open_lakehouse(root)` creates `bronze/`, `silver/`, `gold/` and `kkb.duckdb`, and applies the shared schema through `database.py` after PR #30; [DATABASE](DATABASE.md) is the delivered definition. `record_artifact` stores a payload under the SHA-256 of its bytes; `register_series` admits a series only if its semantics resolve; `append_observations` validates every period against the declared calendar before writing any of them; `export_silver` writes the silver tables to Parquet.
- Design rules worth keeping: bronze is addressed **by content**, so re-recording identical bytes is a no-op and two payloads can never collide on one id — history cannot be rewritten by a re-fetch. `read_artifact` re-hashes on the way out, so an edited file on disk is caught rather than served. Silver refuses a series with an unknown unit, scale, frequency, observation kind or accumulation behaviour, and refuses a re-registration that changes any of them underneath rows already validated against the old declaration. An observation batch is all-or-nothing.
- Core vocabulary extended: `Frequency` gained `BUSINESS_DAY`, `TWICE_MONTHLY` and `SEMIANNUAL`; `StockFlow` gained `RATE` and `INDEX`; new `WeeklyAnchor`, `Scale`, `CumulativeKind` and `Aggregation`. Every change is **additive** — no member removed or renamed — and each is driven by measured evidence: EVDS declares nine frequencies with two weekly anchors, BDDK publishes in million TRY while FinTürk publishes in thousand, and one BDDK bulletin contains three distinct accumulation behaviours that a boolean cannot express. Negative tests cover the new invariants. This is a shared contract change; [M0-11](#m0)'s editor/reviewer nomination remains open and unaddressed by this task.
- Tests: PASS (2026-09-09; Python 3.12.5, DuckDB 1.5.5). `pytest -q tests/unit/test_lakehouse.py` — 36 passed in 0.70s. Recorded fast checks: Ruff 0.16.6 format and lint clean over 24 files, `pytest -q tests/unit` — 290 passed in 8.59s, Bandit 1.9.4 clean, secret scan clean. `mypy src` reports 14 errors, **unchanged** from the pre-existing baseline; the new modules are strict-clean and M0-08 still owns the XLSX ones.
- Coverage note: tests use the real published shapes rather than invented ones — a monthly stock in million TRY with the actual 2026/4–2026/6 housing-credit values, and a weekly Friday-anchored rate. The negative cases are the failures that would corrupt later work: a Thursday observation admitted into a Friday-anchored series, a Friday date accepted by a Wednesday anchor, a quarter ending in month 5, a month ending on the 29th, a re-registration that quietly changes million to thousand, a missing value that must stay NULL rather than become zero, and a partially valid batch that must write nothing.
- One rule was wrong and a test caught it: the first draft refused any series whose `cumulative` was not `NONE` unless it was a flow, which also refused `UNKNOWN`. `UNKNOWN` is not a claim that a series accumulates; only `SINCE_INCEPTION` and `YEARLY_RESET` are. Fixed, and `require_resolved()` still refuses the unknown at promotion time.
- Layout note: adds a `lakehouse` package, which is not in DEC-125's enumeration. [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) is amended to say that list names the packages the architecture sketch implied rather than a ceiling, and that a package mapping to a numbered ARCHITECTURE component may be added with its task.
- Blocker: remaining acceptance above; ownership handoff required before another teammate resumes.
- Previous handoff (historical; current queue controls selection): the container exists and refuses meaningless data; nothing normalizes yet. Next is M12-04 (canonical time spine) followed by M12-05/06/07, where the measured BDDK behaviour becomes hand-calculated fixtures: table 4 is a stock that must not be differenced into "disbursement", and table 2 resets every January so its within-year first difference is the monthly flow while January's published value is already the month. After that, M12-08 alignment for the weekly-Friday rate against the monthly stock, which the reference scenario needs.

## Acceptance criteria

A known synthetic bulletin with a January reset converts to the hand-calculated flow series exactly. A daily and a monthly series align on the canonical spine with correct sample counts. A series with unknown unit or unknown reset behaviour is rejected or surfaced as unknown, never silently normalized. Every value in `gold` traces to a `bronze` object through recorded transformations.

## Evidence / implementation record

PRs #23–#26 and #30 deliver the implemented subsets recorded above, with passing targeted/fast validation. Calendar coverage, daily alignment, unit/percentage conversions, revision-safe vintages, rebasing and mandatory per-transform proof remain incomplete. No adapter retrieves live sources. M12-DB remains untouched by this documentation task; its verified PR #30 merge is recorded in Current Project Status.

## Handoff notes

Do not infer unit or stock/flow meaning from a numeric dtype. A parsed table is not a normalized series. When cumulative behaviour is ambiguous, surface both interpretations or ask; a silently chosen one is indistinguishable from a correct one until the demo.

<a id="m13"></a>
# M13 — Semantic catalog and retrieval

Status: NOT STARTED. Initial hybrid baseline is confirmed by DEC-116 and [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline); DEC-115 and DEC-127 are SUPERSEDED. Only the explicitly triaged queue entries are READY. Embedding availability/use is confirmed; remaining Q-K-05 dimension/prefix/limit answers are dense implementation prerequisites, not a lexical-failure or prior-gain gate. Dedicated reranker capabilities remain unresolved and optional.

## Objective

Let a Turkish financial question find the right series without hard-coded codes, and prove the retrieval works with a measurement rather than an assumption.

## Dependencies

M12 series metadata and M13-01 catalog record for content, M13-03 shared normalization, reviewed aliases/concept families, metadata filters, lexical/BM25 and required Qwen3-Embedding-8B dense retrieval with the retained LanceDB index choice. Real catalog fetching needs M3/M7 and permitted access. The dense path needs bounded M4 transport/account access and remaining Q-K-05 configuration/limit answers; its model/endpoint and baseline use are confirmed by DEC-129/130. Lexical failure or prior measured gain is not a prerequisite for dense use; RRF/reranking are not prerequisites for baseline delivery.

## Tasks

- [ ] M13-01 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Acceptance/dependencies: [ordered queue](#ordered-next-safe-tasks). Define the catalog record: series ID, Turkish title, unit, frequency, source, coverage range and sample values.
- [ ] M13-02 — Status: BLOCKED for live retrieval on M7-01..06 and Q-DATA-01/Q-NET-01/02. Pull approved EVDS catalog metadata, preserving original IDs, source/vintage, archived and semantic flags; never hard-code runtime series selection.
- [ ] M13-03 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Acceptance/dependencies: [ordered queue](#ordered-next-safe-tasks). Implement one Turkish normalization function — dotted and dotless i, case folding, diacritic removal — and use it for both indexing and querying; add a test that fails if the two paths ever diverge.
- [ ] M13-04 — Build lexical/BM25 retrieval over normalized, metadata-filtered catalog records after M13-01/03/08. DuckDB FTS is the existing candidate; verify its extension/index requirements without relaxing the hardened lakehouse connection. Any separate index connection design needs task review.
- [ ] M13-05 — Status: BLOCKED on M13-01/03/08 catalog/normalization/alias prerequisites, bounded M4 embedding transport/account access and remaining Q-K-05 dimension/prefix/limit answers. Implement required initial dense retrieval with `kkbhackathon2026/Qwen3-Embedding-8B` at `https://mia.csp.kloudeks.com/v1/embeddings` and the retained lightweight LanceDB index choice. DEC-130 confirms baseline use without lexical failure or prior benchmark-gain evidence; measure it alongside the lexical path.
- [ ] M13-06 — Status: BLOCKED on executable M13-04/05 paths and held-out complementary-result evidence. BENCHMARK FIRST: activate RRF only when lexical/dense results are demonstrably complementary and fusion improves held-out quality over the measured combined baseline; report its gain/cost.
- [ ] M13-07 — Status: BLOCKED on baseline/final-selection benchmark and model capability. BENCHMARK FIRST: listwise/model reranking must provide meaningful final-selection gain justifying another model call, latency, token usage, failure surface and weak-model instability; top-20-to-5 is a historical proposal, not a fixed requirement.
- [ ] M13-08 — After M13-01/03, review roughly fifty aliases/concepts and their catalog mappings. Preserve ambiguity; an exact hit must still satisfy metadata/semantic filters. Reviewed concept families bound catalog neighborhoods for relationship investigation, not causes.
- [ ] M13-09 — After M13-01 and executable lexical/dense paths, evaluate separately reviewed development/held-out question-to-series pairs. Report lexical-only, dense-only and combined candidate quality, Recall@5/10, final selection, wrong-near-match/archived choices, latency and failure behavior under EVALUATION; no tuning on holdout. Authoring the case set can begin after catalog/alias contracts without waiting for executable retrieval.
- [ ] M13-10 — Status: BLOCKED; optional document-chunk collection requires permitted web_url ingestion plus its own measured retrieval need. Deferred from the first core slice; no mandatory second LanceDB collection.
- [ ] M13-11 — Test near-identical/archived/stale series and ambiguous aliases; require explicit resolution rather than trusting ranking. Separately test relationship discovery using hybrid retrieval within reviewed concept families: family coverage, deduplication, target leakage, semantic rejection and no-candidate outcomes after core dependencies. Embedding the target phrase and returning near-duplicate target variants does not satisfy this path.
- [ ] M13-12 — Record versioned lexical-only, dense-only and combined baseline quality/latency/failure behavior and each optional stage's incremental gain and cost. Implement catalog-bounded relationship discovery only after reviewed family policy, permitted real catalog, semantic guard and deterministic analytics; never auto-promote it to READY.

## Acceptance criteria

The mandatory Turkish normalizer + reviewed alias/concept-family mapping + metadata filtering + lexical/BM25 + Qwen3-Embedding-8B dense hybrid baseline has held-out lexical-only, dense-only and combined candidate-quality, Recall@5/10, final-selection, latency and failure-behavior measurements. Near matches, archived records and ambiguous aliases resolve explicitly. Every candidate carries its semantics/unknowns. RRF, listwise/model reranking and extra stages/infrastructure must prove incremental gain; direct-series recall alone does not validate diversified relationship-discovery candidate coverage.

## Evidence / implementation record

- Owner: Unassigned; suggested lane A or C.
- Branch: —
- PR: —
- Commit: —
- Tests: NOT RUN; no implementation.
- Benchmark: The fifty pairs from M13-09 become a retrieval case set in EVALUATION.
- Known limitations: Embedding model/endpoint availability is confirmed by DEC-129; vector dimension, batch limits, query/passage prefix and dedicated-reranker availability remain unresolved (Q-K-05). A wrong prefix convention can invalidate baseline vectors; no quality/gain/loss is measured yet.
- Previous handoff (historical; current queue controls selection): M13-03, M13-04, M13-08 and M13-09 need no model access; do them first, then measure what the dense half actually adds.

## Handoff notes

Measure both initial retrieval paths and combined candidates on Turkish financial vocabulary. Tune normalizer/aliases and candidate budgets on development cases, preserving the confirmed dense baseline; RRF/reranking still require held-out evidence. Label a failed/unavailable path and any degraded single-path result explicitly rather than calling it a complete hybrid result. A retrieval score is never evidence of correct semantics — the unit and frequency on the record are.
