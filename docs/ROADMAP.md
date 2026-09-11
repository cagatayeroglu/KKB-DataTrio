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

- Last verified `origin/dev`: **`b335e16f438c0a43bec2f74e69f3f4bd3369c066`** (PR #67, M6-24); it is also the latest implementation merge.
- Verification: **2026-09-11 03:09 +0300**. Fetched `origin/dev`; PR #67 is merged, its merged tree equals the validated head `991000a`, and both its claim and final-head Fast PR runs passed. The task branch is deleted locally and remotely; no open PR or published claim at verification. No application checks were rerun for this completion bookkeeping, and no full/release checks were run.
- Schedule: **Day 5 of the confirmed 7–20 September 2026 development window** (relative Day 4 in the execution plan below; [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope)); 10 days remain to the reviewed-repository deadline, counting today. Final Day is 17 October 2026. The earlier "8–9 day" figure was an internal estimate, never an organizer date.
- Phase: **Offline end-to-end analysis with multi-turn results** — question -> real planner/registry/tool -> typed result -> workspace -> gated answer is exercised with synthetic lakehouse data and a scripted model (PRs #45–47). Four brief tools are implemented: `lakehouse`, `change_detection` (period comparison), `anomaly`, and `causality` (association/lag only). Live source adapters, live Kloudeks, `web_search`/`web_url`, Granger, breakpoint detection, full proof/replay, UI and deployment remain incomplete.
- Open PRs / active implementation claims: **none at verification**. PRs #39, #41–67 are merged; #40 was closed without merge and its documentation was delivered by #41. M6-07/08/09/10 are DONE, not active work. Eray remains the recorded owner of incomplete M4/M5/M8/M12 deliveries; an old merged branch is not an active claim or permission to take over remaining scope. Unpublished local work cannot be determined from GitHub. M1-06 is DONE after #53, M3-04 after #55, M13-01 after #57, M13-03 after #59, M6-23 after #62, M8-18 after #64 and M6-24 after #67; #61 added the post-merge branch-cleanup rule and #66 synchronized this status with the owning docs. This completion update claims no new task.
- Product/retrieval documentation synchronization: **DONE**, PR [#34](https://github.com/cagatayeroglu/KKB-DataTrio/pull/34) merged into `dev` at `41e302c`; final content `e2029ea`, document checks and Fast PR gate PASS (55s). DEC-129/130 and the reconciled current status are present in the merged tree.
- Organizer primary-source synchronization: **DONE**, PR [#41](https://github.com/cagatayeroglu/KKB-DataTrio/pull/41) merged into `dev` at `90dd9e9`; final content `9c707f6`. Owner Eray; branch deleted after merge. Records [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) (kick-off calendar, delivery form, demo-day input scope, technology expectations) and amends DEC-129 with the primary MIA guide's literal OCR/embedding contracts and error semantics; narrows Q-K-01/04/05, Q-DATA-01, Q-DEMO-01, Q-INFRA-01, Q-NET-02, Q-DEV-02 and sharpens Q-DEV-01. Documentation and the `.env.example` template only; no runtime behaviour, dependency or test-policy change. `.env.example` values stay blank so `test_environment_template_has_only_blank_values` needed no exception. Tests: `make quick` 892 passed / 16.36s; `make pr` 892 passed / 16.07s with Ruff format/lint, Bandit and secret scan clean; internal Markdown link/anchor check 0 broken.
- Latest recorded fast gate: PR #67 / `991000a` — **73 targeted / 1547 unit tests PASS**; `make quick` **30.47s**, `make pr` **30.55s**, including Ruff format/lint, Bandit and secret scan; Python 3.12.5. GitHub final-head Fast PR PASS (1m39s). Earlier counts in task records are historical delivery evidence, not the current suite size.
- Known failing gate: **M0-08** — `mypy src` remeasured during M6-24 on `b54403a`: **23 strict errors in 7 files**, all pre-existing. The earlier 17 in 5 files are unchanged; `csv_loader.py` (5, from #53) and `agent/claim_qualifiers.py` (1, from #64) were added since. Full/release validation remains unestablished. A green fast PR gate does not imply a green release.
- Critical implementation gaps: date/numeric profiling and source adapters (bounded CSV loading is delivered in #53); source POST/trust configuration and redirect following; transformation-prerequisite validation (M8-07), dependent-claim invalidation (M8-12), deflation (M2-15 before M6-13), independent recomputation and external cross-check; catalog retrieval; `web_search`/`web_url` including required HTML/PDF/XLSX/image extraction; Granger (M6-11), breakpoint detection and benchmarked analytics thresholds; benchmark runner; API/UI/deployment.
- Open correctness blockers, as named by the M6-23 and M8-18 handoffs: **D** false boundary coverage, **E** premature workspace publication and **F** the Kloudeks destination/SDK-policy mismatch (related to the M4-07 correction). **C** calendar-invalid lag pairing is closed by [M6-24](#m6-24-calendar-valid-lag-record) (#67). D, E and F have no task record or reproduction in the repository yet, so each needs triage before it can be claimed. M0-08 is deferred behind them; M6-11's lag primitive is now calendar-valid.
- External blockers (organizer primary-source review 2026-09-10): [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) now also records the **literal OCR request contract, the embedding call shape and the documented `401`/`403`/`429` semantics** from the primary MIA guide. The MIA API key is **provisioned** and held only in the operator-local ignored `.env`; Q-K-01 is narrowed to an unexercised live smoke. Q-K-02/03/04 still cover context/output capacity, native tool/JSON guarantees and the numbers behind `429`; a `vllm_xargs` parameter reveals a vLLM server but guarantees no structured-output feature. Q-K-05 needs the **vector dimension measured** from the first authorized live call, not asked. Q-DEMO-01, Q-INFRA-01, Q-NET-02, Q-DATA-01 and Q-DEV-02 gained real answers from [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) and are narrowed. **Q-DEV-01 is ANSWERED (2026-09-10)**: coding assistants are permitted as development tools; the Kloudeks-only runtime restriction is untouched by that permission. Q-DATA-03, Q-NET-01, Q-INFRA-02 and Q-DEMO-02/03 remain open. Q-TEAM-01..05 were answered in PR #19.
- Confirmed scope changes from [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope): reading **prompt-supplied URLs (PDF/Excel/image/text) is a required demo-day capability**, not an optional M7 extra; a **live deployed** solution is expected on Final Day; delivery is by granting KKB access to the private repository; both sources are bounded to **2021-01 – 2026-06**.
- Current direction: [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline) supersedes DEC-127 with initial lexical + dense hybrid retrieval; DEC-115 remains historical/SUPERSEDED. [DEC-128](DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence) records product direction. Neither claims implementation. Core ingestion/results/workspace/verifier/live provider/required tools precede broad differentiation.

- Key blocked delivery: M3-06/08 and M13-02 live retrieval still need Q-DATA-01 and Q-NET-01/02; BDDK also needs bounded POST and an explicit verified CA bundle. M4 live acceptance needs bounded transport plus authorized authentication/capability checks; key provisioning is already recorded. M13-05 needs alias implementation and usable catalog content (M13-01 record and M13-03 normalizer are merged), embedding transport and measured/confirmed Q-K-05 configuration. M9-01 still needs separately authorized review/delivery of preserved Day 0 drafts. Q-DATA-03, Q-INFRA-01/02 and Q-DEMO-02/03 remain open for redistribution, environment, retention/reset and demo fallback constraints.
- Next-task recommendations (not assignments): **Çağatay — triage M13-08** after the merged M13-01/03 prerequisites; it is not yet a triaged READY entry and is not started or claimed here. **Eray — triage the next correctness blocker (D, E or F) into a task record with a reproduction, or take M6-11**, which is READY and unowned now that M6-24 made its lag primitive calendar-valid; which comes first is a team call, since the blockers' definitions are not yet in the repository. M0-08 remains READY and deferred behind the correctness blockers. M6-13 is valuable but **not READY**: its M2 deflation prerequisite is absent (M2-14/15); a prior handoff suggestion is not readiness. Recheck claims before starting either task.

## Ordered next safe tasks

The remaining READY entries below were rechecked against `b335e16` and open PRs after M6-24 merged. The open correctness blockers D, E and F above are not queue entries until triaged; M0-08 stays deferred behind them. Owner is **unassigned**, Branch/PR/Commit **—**, Tests **NOT RUN for that task**. The queue covers triaged work, not every unchecked backlog item; recheck published claims immediately before starting.

| Order | Task / status | Satisfied prerequisites | Acceptance / handoff |
| --- | --- | --- | --- |
| 1 | **M6-11 — READY** | M6-01/07/08/09/10/21 and tool shape merged; lag pairs calendar-valid since M6-24 (#67); DEC-120 fixes the method and DEC-124 allows `statsmodels` | Reuse association/lag and add bounded Granger tests to `causality`; report method, sample/lag policy, failures and mandatory limitations, with deterministic fixtures and fast gates. See [readiness record](#m6-11-readiness-record). |
| 2 | **M0-08 — READY** | Reproduced release-gate failure; existing full target | Narrow typing fix or reviewed exceptions before the next checkpoint. Latest recorded failure is 23 errors in 7 files (remeasured during M6-24); remeasure when taking the task. Independent release prerequisite. |

Completed M1-06, M3-04, M13-01/03, M5-01/10/11/12, M6-01/02/03/04/05/06/07/08/09/10/21/22/23/24 and M8-06/10/17/18 are excluded. M8-07 stays PARTIAL for transformation prerequisites. M13 alias/holdout authoring follows catalog/normalizer contracts. PRs #57/59 deliver the M13-01 catalog record and M13-03 shared normalizer only; M12's remaining calendar/vintage/conversion/lineage acceptance and M13's unimplemented retrieval remain unchanged. Remaining owned PARTIAL scopes are not automatically released for takeover; obtain the recorded owner's handoff.

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
| [#39](https://github.com/cagatayeroglu/KKB-DataTrio/pull/39) `0dbeef1` | Post-merge M7 bookkeeping | M7-05 DONE; M7-06 DONE for direct-GET coverage; 340 targeted / 892 unit delivery evidence retained |
| [#41](https://github.com/cagatayeroglu/KKB-DataTrio/pull/41) `90dd9e9` | Organizer/MIA documentation | Document checks and Fast PR PASS; DEC-129/131 recorded, no live provider delivered |
| [#42](https://github.com/cagatayeroglu/KKB-DataTrio/pull/42) `d4d584b`; [#43](https://github.com/cagatayeroglu/KKB-DataTrio/pull/43) `2060f31` | Typed result contract and lakehouse projection | M6-01/21 DONE; 57 then 31 targeted / 949 then 980 unit |
| [#44](https://github.com/cagatayeroglu/KKB-DataTrio/pull/44) `32ab2f3`; [#45](https://github.com/cagatayeroglu/KKB-DataTrio/pull/45) `bf8bba4` | Result verification and answer gate | M8-06/10 and M5-01 DONE; M8-07 PARTIAL; 38 then 22 targeted / 1017 then 1040 unit |
| [#46](https://github.com/cagatayeroglu/KKB-DataTrio/pull/46) `ccb35db`; [#47](https://github.com/cagatayeroglu/KKB-DataTrio/pull/47) `b5b09a5` | Workspace values and multi-result answers | M5-10/11/12 and M8-17 DONE; 21 then 17 targeted / 1063 then 1080 unit |
| [#48](https://github.com/cagatayeroglu/KKB-DataTrio/pull/48) `63b363e`; [#49](https://github.com/cagatayeroglu/KKB-DataTrio/pull/49) `eafafa5` | Change/comparison functions and registered tool | M6-02/03/04/22 DONE; 37 then 21 targeted / 1117 then 1138 unit |
| [#50](https://github.com/cagatayeroglu/KKB-DataTrio/pull/50) `cb1797c`; [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51) `1e8c417` | Anomaly and association/lag tools | M6-05/06/07/08/09/10 DONE; 25 then 38 targeted / 1165 then 1203 unit; Granger/breakpoints remain absent |

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
| Day 1–3 | 8–10 September | Delivered through PR #51; snapshot 10 September |
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
- [ ] M0-08 — Status: READY. Owner: unassigned. The [Makefile](../Makefile) `full` target already exists and is correctly kept out of the per-edit loop, but it does not pass: `mypy src` reports **23** strict errors in 7 files, re-measured on `dev` `b54403a` during M6-24 (17 in 5 files at `90dd9e9` during M6-01). Eleven are in `xlsx_loader.py`; the rest are in `_xlsx_package.py`, `xlsx_sheets.py`, the M7 `ingest` modules, `csv_loader.py` (5, #53) and `agent/claim_qualifiers.py` (1, #64). Make the release gate green, or record reviewed exceptions, before the next `dev -> main` promotion. Evidence: [M0-08 active record](#m0-08-active-record).
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

Status: PARTIAL — M1-01 specification, M1-02 admission guards, M1-04/M1-05 CSV fixtures, M1-06 bounded CSV loading, M1-09 XLSX fixtures/sheet selection and M1-10 bounded XLSX loading are merged into `dev`. Profiling and the adapter registry remain unimplemented. The Day 0 SourceAdapter protocol remains stash-only, not delivered in `dev`.

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
- [x] M1-06 — Status: DONE (merged and validated). Owner: Çağatay; Branch: `feature/m1-06-bounded-csv-parsing`; PR: [#53](https://github.com/cagatayeroglu/KKB-DataTrio/pull/53), merged into `dev` at `8d33a37`; implementation commit: `7c9939c6ba1f9a0ce4823d422e3951a1ec47adb9`. Implement bounded CSV parsing; record which delimiter/encoding was used and reject ambiguous parsing safely.
  - Delivery: [csv_loader.py](../src/kkb_agent/csv_loader.py) reuses admission and `SourceRef`/`DataContract`; explicit comma/semicolon/tab/pipe delimiter (missing declaration -> `needs_input`), strict UTF-8/BOM, quotes/embedded newlines, stable ordinal columns and literal strings. Empty data fields become `None`; whitespace/NA/numeric separators/formula-like text remain uninterpreted. No guessed dates, units, frequency or financial semantics.
  - Limits: existing 10 MiB input, 100,000 data rows, 256 columns, 1,000,000 cells, 65,536-character fields and 256-character labels; structural guards run before row allocation. A terminated/reaped spawn worker bounds parse/serialization to 5 seconds, table JSON to 50 MiB, and Linux address space to 512 MiB by default. Input stream I/O timeout remains caller-owned. Malformed/empty/oversized input returns safe codes without a partial table; no persistence, profiling, adapters, engine or dependency change.
  - Tests (Python 3.12.2): `pytest -q tests/unit/test_csv_loader.py tests/unit/test_ingestion_fixture.py tests/unit/test_csv_edge_fixtures.py tests/unit/test_ingestion_policy.py` — **148 PASS / 9.12s**, including 73 new parser tests; `make quick` **1276 PASS / 33.22s**; `make pr` **1276 PASS / 33.37s**, Ruff format/lint, Bandit and secret scan clean; `git diff --check` PASS. GitHub final-head Fast PR **PASS (1m)** on `a83c2f5`; merged tree verified identical; no full/release checks run.
  - Blocker: none for M1-06. Handoff: claim was published before implementation on `54b3f15`; #53 merge and final-head CI verified, with DONE recorded in this fresh completion branch. M1-07/08 date/numeric profiling remain separate untriaged tasks. The next currently READY source-path task for Çağatay is M3-04; M6-11 remains unclaimed for Eray. No further task started.
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

Merged specification, admission, dependencies, CSV/XLSX fixtures and bounded CSV/XLSX loading are documented in the task records. M1-06 is DONE after PR #53; date/numeric profiling and adapter registration remain unimplemented. Existing M1-10 results are historical delivery evidence, not fresh tests in this completion update.


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

Status: PARTIAL — both source inventories and M3-04 synthetic fixture projections are merged. [BDDK_SOURCE](BDDK_SOURCE.md) and [EVDS_SOURCE](EVDS_SOURCE.md) record transports, units, frequencies and measured semantics; the fixture fidelity notes preserve uncaptured schema gaps. No adapter is delivered. Live adapters remain BLOCKED on Q-DATA-01 and Q-NET-01/02.

## Objective

Support likely financial sources through the generic adapter contract without making them prerequisites for all analyses.

## Dependencies

M1 adapter/ingestion contract, M2 relevant semantics, M7 safe fetch before live retrieval, confirmed access/permissions. Do not invent endpoints, credentials, or series IDs.

## Tasks

- [ ] M3-01 — Obtain source access, approved endpoints/formats, credential requirements, and redistribution rules; record Q-DATA-01 evidence.
- [x] M3-02 — Status: DONE — merged/validated (PR #21 / 35eda16, inventory/document validation). Owner: Eray; Branch: `feature/m3-02-bddk-source-inventory`. Identify representative BDDK datasets and source-published frequency/unit/stock-flow semantics with exact references. Evidence: [M3-02 active record](#m3-02-active-record).
- [x] M3-03 — Status: DONE — merged/validated (PR #22 / 074a874, inventory/document validation). Owner: Eray; Branch: `feature/m3-03-evds-source-inventory`. Identify representative EVDS series and date/unit/revision metadata with exact references. Evidence: [M3-03 active record](#m3-03-active-record).
- [x] M3-04 — Status: DONE (merged and validated). Owner: Çağatay; Branch: `feature/m3-04-source-shaped-fixtures`; PR: [#55](https://github.com/cagatayeroglu/KKB-DataTrio/pull/55), merged into `dev` at `75cb3df`; implementation commit: `874c2ef944e92e67939129e352fbe3ec5a7c4455`. Create synthetic source-shaped discovery/inspection/load fixtures without private source payloads.
  - Delivery: [fixture inventory and fidelity notes](../tests/fixtures/sources/README.md), eight small UTF-8 JSON fixtures (under 6 KiB total), and [19 fixture tests](../tests/unit/test_source_fixtures.py). BDDK monthly response projections preserve caption unit/period, ordered numeric cells, a stock decline and a December/January example; project-owned display cases retain weekly option/Friday captions and FinTürk quarterly/mixed-unit metadata. EVDS documented record projections retain aggregation flags, missing links, archive/base-year labels, ambiguous names and Friday/Wednesday cadence; observation envelope preserves comma decimals, date labels/UNIXTIME and an opaque server-formula column.
  - Limitations: synthetic authored data, never captured responses or adapter acceptance. Weekly DOM/table schema, FinTürk wire fields, BDDK `colModels`, EVDS catalog/category envelopes and POST bodies remain uncaptured; no invented provider fields or archived/active flag. UTC+03:00 is an explicit fixture convention, not a new provider guarantee. No runtime, source adapter, semantic inference, live request, credential, dependency or CI change.
  - Tests (Python 3.12.2): `pytest -q tests/unit/test_source_fixtures.py` **19 PASS / 0.05s**; `make quick` **1295 PASS / 37.23s**; `make pr` **1295 PASS / 32.57s**, Ruff format/lint, Bandit and secret scan clean; `git diff --check` PASS. GitHub final-head Fast PR **PASS (1m)** on `5a226ea`; merged tree verified identical; no full/release checks run.
  - Blocker: none for M3-04 synthetic scope. Handoff: draft claim was published before implementation from `d4722a5`; #55 merge and final-head CI verified, with DONE recorded on this fresh completion branch. Next currently READY task for Çağatay is M13-01; M6-11 remains unclaimed for Eray. No further task started. Live adapters still require source/egress approvals, contract integration and missing transport/schema work; the fixture delivery does not mark M3-05/06/07/08 READY or implemented.
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
- Blocker: no missing endpoint/auth/model decision for ordinary compatible text transport. M4-07 still needs implementation/policy correction; M4-12 needs authorized live validation with the already-provisioned operator-local key; provisioning is no longer the blocker. Native tool/JSON guarantees and capacity/limit questions remain open. Recorded Eray ownership is not transferred; no M4 task is claimed by this docs follow-up.
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

- [x] M5-01 — Status: DONE — the request -> plan -> validation -> execution -> verification lifecycle is exercised by `TestTheWholeSliceEndToEnd` in [test_answer_gate.py](../tests/unit/test_answer_gate.py), merged PR #45 / `bf8bba4`, implementation `6b5ea54`, 22 targeted / 1040 unit tests and fast gates PASS. Owner: Eray; Branch: `feature/m8-10-answer-gate` (merged). Live model/source delivery is not implied. Evidence: [M8-10 record](#m8-10-answer-gate-record).
- [x] M5-02 — Status: DONE. Resolved by [DEC-113](DECISIONS.md#dec-113--custom-bounded-orchestration-loop) on 2026-09-09: a custom planner -> router -> executor -> verifier state machine, with LangChain, LangGraph and Celery rejected. No framework is added.
- [x] M5-03 — Status: DONE — merged/validated (PR #28 / 1fa48b8, registry tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Implement a tool registry with unique system-owned names and argument schemas. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-04 — Status: DONE — merged/validated (PR #28 / 1fa48b8, argument/unknown-name negatives). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Reject unknown tool names and validate per-tool arguments, rather than trusting the plan's generic argument dictionary. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-05 — Status: PARTIAL — merged scope; remaining acceptance: Dependency validation exists; workspace/input/output ownership and declared output-type checks are missing. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Validate dependency order, input/output reference existence, workspace ownership, and declared output type. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-06 — Status: PARTIAL — merged scope; remaining acceptance: Registry descriptions are exposed; relevance narrowing and selected source metadata are not implemented. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Expose only relevant tool descriptions and source metadata to the planner. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-07 — Implement deterministic format routing and metadata-based narrowing before semantic model routing.
- [x] M5-08 — Status: DONE — merged/validated (PR #28 / 1fa48b8, scripted planning tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Generate a constrained AnalyticalPlan using the provider boundary; separate source content from system instructions. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-09 — Status: DONE — merged/validated (PR #28 / 1fa48b8, deterministic dispatch tests). Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Execute the smallest valid plan using registered deterministic tools and structured ToolResult outcomes. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-10 — Status: DONE — merged/validated (PR [#46](https://github.com/cagatayeroglu/KKB-DataTrio/pull/46) / `ccb35db`, 21 targeted / 1063 unit tests). Owner: Eray; Branch: `feature/m5-10-12-workspace-results`; Commit: `8e61988`. Preserve explicit selected sources, contracts, derived references, assumptions, transformations, evidence, and tool results between turns. Evidence: [M5-10/11/12 workspace results record](#m5-101112-workspace-results-record).
- [x] M5-11 — Status: DONE — the workspace follow-up merged in PR [#46](https://github.com/cagatayeroglu/KKB-DataTrio/pull/46) and the multi-column answer completing it merged in PR [#47](https://github.com/cagatayeroglu/KKB-DataTrio/pull/47) / `b5b09a5`. Owner: Eray. Add a series/change-date-range follow-up using existing workspace references. Evidence: [M5-10/11/12 workspace results record](#m5-101112-workspace-results-record).
- [x] M5-12 — Status: DONE — merged/validated (PR [#46](https://github.com/cagatayeroglu/KKB-DataTrio/pull/46) / `ccb35db`, 21 targeted / 1063 unit tests). Owner: Eray; Branch: `feature/m5-10-12-workspace-results`; Commit: `8e61988`. Invalidate/recompute dependent results when a selection or assumption changes; preserve historical lineage. Evidence: [M5-10/11/12 workspace results record](#m5-101112-workspace-results-record).
- [ ] M5-13 — Status: PARTIAL — merged scope; remaining acceptance: Step/repair/retry counts and repeated-plan rejection pass; total deadline/cancellation are absent. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Bound plan repairs, tool retries, steps, and total request deadline; abort repeated identical invalid plans. Evidence: [M5 loop record](#m5-loop-record).
- [ ] M5-14 — Distinguish clarification, unsupported request, recoverable outage, partial result, and terminal failure in the orchestration layer.
- [ ] M5-15 — Test invalid names/arguments/dependencies, stale references, partial tool failure, and failed-turn state preservation.
- [ ] M5-16 — Status: PARTIAL — merged scope; remaining acceptance: Unknown tools/extra arguments are refused; permitted-reference, URL/path and extraction-path authorization tests remain. Owner: Eray; Branch: `feature/m5-plan-registry-executor`. Test injected source text cannot authorize a tool, URL, file path, or code execution. Evidence: [M5 loop record](#m5-loop-record).
- [x] M5-17 — Status: DONE for the delivered scope. Run targeted planner/executor contract and negative tests, lint, and the fast PR gate; reserve full checks for checkpoints or explicit requests. Evidence: PR #28, 30 targeted / 445 unit tests and fast checks; future integration changes require their own checks.
- [x] M5-18 — Status: DONE for the delivered-scope handoff. Record supported lifecycle/turn operations, limits, validation, and next tool integration. Evidence: PRs #28/29 records below; incomplete runtime acceptance remains explicitly PARTIAL above.

<a id="m5-101112-workspace-results-record"></a>
### M5-10/11/12 workspace results record

- Status: M5-10/11/12 DONE — PR #46 / `ccb35db` delivers result storage, stale-read rejection and caller-supplied recomputation (21 targeted / 1063 unit); PR #47 / `b5b09a5` completes multi-column answers (17 targeted / 1080 unit). Both are merged with passing fast gates. The narrative below describes #46; [M8-17](#m8-17-multi-result-answer-record) supersedes its single-result limitation and next-step handoff.
- Owner: Eray (completed delivery; no active claim).
- Branch: `feature/m5-10-12-workspace-results`, from `dev` `bf8bba4bb077ec696f59b4c37dd51fef38480d53`
- PR: [#46](https://github.com/cagatayeroglu/KKB-DataTrio/pull/46), `feature/m5-10-12-workspace-results` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `8e61988` (implementation); claim `476c7ea`.
- Objective: Give the definition DAG actual values. Persist typed `AnalyticalResult`s as content-addressed workspace values, refuse a stale read instead of returning one, and recompute a dependent through a supplied recomputer rather than rebinding an old value. Prove the organizer's three-turn follow-up end to end.
- Implementation: [agent/workspace.py](../src/kkb_agent/agent/workspace.py) gains the `workspace_results` table, `store_result`, `read_result`, `record`, `value_of`, `values` and a `Recomputer` type; `resolve` and `value_of` refuse a stale read; `refresh` takes a recomputer. [agent/loop.py](../src/kkb_agent/agent/loop.py) `Session.answer` accepts a workspace and a name, so a turn's result survives into the next. [database.py](../src/kkb_agent/database.py) and [DATABASE](DATABASE.md) record the new table.
- Values are content-addressed. `workspace_results` is keyed by `AnalyticalResult.digest()`, so storing identical content twice is one row and differing content can never overwrite what an earlier turn recorded — which is what keeps a superseded answer answerable. `read_result` recomputes the digest and refuses a row that no longer hashes true; that check is the only thing between an edited row and an answer citing it as evidence.
- **A stale read is now refused, not served.** `resolve` and `value_of` raise instead of returning a superseded artifact, because returning one and hoping the caller inspects `is_stale` is exactly how an old number reaches an answer. `allow_stale=True` remains for inspection — showing what went stale, ordering a refresh — and internal traversals use it explicitly.
- **`refresh` recomputes rather than rebinding.** A name holding a value now requires a `Recomputer`; refusing otherwise is the point, because rebinding alone would clear the stale flag while leaving the old figure in place — a number that looks current and describes a selection nobody made any more. Definition-only artifacts still refresh by rebinding, and the existing "refresh your inputs first" rule is unchanged. The workspace never invents the recomputation: what a column *means* lives in the tool that produced it.
- One defect found by a failing test, fixed rather than worked around. `artifact_id` hashed the definition only, so recording a **different** result under an unchanged definition produced the same id, was treated as a no-op, left the previous number bound and marked no dependent stale — a value changing with nothing downstream noticing. `artifact_id` now takes an optional `value_ref` and includes it when present; a definition with no value hashes exactly as before, so no stored artifact is renumbered. Both properties are pinned by tests.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_workspace_results.py` — **21 passed**, including the organizer's three-turn scenario run against the real lakehouse tool: build the table, widen the range and watch the read be refused, recompute in dependency order, then add a column and assert the untouched artifact keeps its id. `pytest -q tests/unit/test_workspace.py` — 24 passed. `make quick` / `make pr` — **1063 passed / 18.63s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on both changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- One existing test changed, accessor-only: `test_refresh_rebinds_to_the_current_inputs` reads a stale artifact deliberately and now says `allow_stale=True`. No assertion was weakened.
- Limitations: the workspace holds values but **the answer path still uses one result per turn** — `Session.answer` records into the workspace and reads nothing back from it, so an answer spanning `konut_stok` and `konut_faiz` together is still not possible. That is the next step, not this one. The recomputer is supplied by the caller, so nothing here re-plans or re-runs a tool on its own; wiring `refresh` to the planner is separate. Cross-process durability and reset semantics remain Q-INFRA-02 and Q-DEMO-02 — nothing here promises restart durability.
- Blocker: none known in scope.
- Handoff: The workspace now preserves real results across turns, refuses stale reads and recomputes on demand, and the organizer's three-turn shape is proven against the real tool. The next step that raises product value is **a multi-result answer**: let `gate_answer` and `Session.answer` work over `Workspace.values()` so one answer can cite several columns, which is what the reference scenario's table actually is. After that, M8-12 stale-evidence invalidation can reuse `digest()` directly, and M6-02/03 add the change and comparison producers.

### M5 workspace record

- Status: DONE for M5-10/11/12 across PRs #29/#46/#47. The original #29 narrative/tests below are historical; current result storage, stale-read rejection, caller-supplied recomputation and multi-result answer evidence are in the [workspace results record](#m5-101112-workspace-results-record). Cross-workspace access, automatic replanning and restart semantics are not claimed complete.
- Owner: Eray (completed delivery; no active claim).
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
- Blocker: none for completed M5-10/11/12; separate reference/ownership checks remain M5-05.
- Previous handoff (historical; current queue controls selection): the multi-turn mechanism holds definitions, not values; `value_ref` points at data rather than carrying it. This alone does not make values replayable. What it cannot yet do is compute anything, because no tool is implemented. The next step is the first real tool: `lakehouse` over the M12 gold tables, which turns a validated plan step into an artifact with a value and a lineage node.

### M5 loop record

- Status: PARTIAL — merged/validated; remaining M5-05/06/13/16 reference, narrowing, deadline and boundary criteria are listed above. M5-01 is completed by PR #45. The original #28 narrative/tests below are historical.
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

Status: PARTIAL — four of the six brief tools exist: [`lakehouse`](../src/kkb_agent/tools/lakehouse.py) with its five security gates, [`change_detection`](../src/kkb_agent/tools/change_detection.py) for period comparison, [`anomaly`](../src/kkb_agent/tools/anomaly.py) over period-over-period changes, and [`causality`](../src/kkb_agent/tools/causality.py) for association and lag. `web_search` and `web_url` have no implementation; `causality` lacks Granger (M6-11) and `change_detection` lacks breakpoint detection (part of M6-05/06's original wording), and both say so in their descriptions.

## Objective

Produce reproducible financial/statistical results with stated prerequisites, sample counts, and limitations.

## Dependencies

M1 data references, M2 operation-specific semantic policies, M5 tool registration, M8 evidence-record interface. The causality method is fixed by [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits); basic descriptive tools do not.

## Tasks

- [x] M6-01 — Status: DONE — merged/validated (PR [#42](https://github.com/cagatayeroglu/KKB-DataTrio/pull/42) / `d4d584b`, 57 targeted / 949 unit tests). Owner: Eray; Branch: `feature/m6-01-result-contract`; Commit: `194df0c`. Define result schemas for values, units, periods, sample counts, warnings, and evidence references. Evidence: [M6-01 result contract record](#m6-01-result-contract-record).
- [x] M6-02 — Status: DONE — merged/validated (PR [#48](https://github.com/cagatayeroglu/KKB-DataTrio/pull/48) / `63b363e`, 37 targeted / 1117 unit tests). Owner: Eray; Branch: `feature/m6-02-04-change-comparison`; Commit: `fc1b78e`. Evidence: [M6-02/03/04 change and comparison record](#m6-020304-change-and-comparison-record). Implement absolute change and relative change with explicit denominator/zero handling.
- [x] M6-03 — Status: DONE — merged/validated (PR [#48](https://github.com/cagatayeroglu/KKB-DataTrio/pull/48) / `63b363e`, 37 targeted / 1117 unit tests). Owner: Eray; Branch: `feature/m6-02-04-change-comparison`; Commit: `fc1b78e`. Evidence: [M6-02/03/04 change and comparison record](#m6-020304-change-and-comparison-record). Implement period comparison with exact date selection and transparent missing observations.
- [x] M6-04 — Status: DONE — merged/validated (PR [#48](https://github.com/cagatayeroglu/KKB-DataTrio/pull/48) / `63b363e`, 37 targeted / 1117 unit tests). Owner: Eray; Branch: `feature/m6-02-04-change-comparison`; Commit: `fc1b78e`. Evidence: [M6-02/03/04 change and comparison record](#m6-020304-change-and-comparison-record). Add hand-calculated change fixtures including negative values, zeros, and empty ranges.
- [x] M6-05 — Status: DONE — merged/validated (PR [#50](https://github.com/cagatayeroglu/KKB-DataTrio/pull/50) / `cb1797c`, 25 targeted / 1165 unit tests). Owner: Eray; Branch: `feature/m6-05-06-anomaly`; Commit: `a308202`. Evidence: [M6-05/06 anomaly record](#m6-0506-anomaly-record). Choose/document a simple change/anomaly baseline and its minimum-sample/parameter policy.
- [x] M6-06 — Status: DONE — merged/validated (PR [#50](https://github.com/cagatayeroglu/KKB-DataTrio/pull/50) / `cb1797c`, 25 targeted / 1165 unit tests). Owner: Eray; Branch: `feature/m6-05-06-anomaly`; Commit: `a308202`. Evidence: [M6-05/06 anomaly record](#m6-0506-anomaly-record). Implement the chosen anomaly/change method with deterministic output and recorded parameters.
- [x] M6-07 — Status: DONE — merged/validated, 38 targeted / 1203 unit and Fast PR PASS. Owner: Eray; Branch: `feature/m6-07-10-association` from `dev` `cb1797c`; PR: [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51) merged at `1e8c417`; Commit: `b575883`. Evidence: [M6-07..10 association and lag record](#m6-0710-association-and-lag-record). Implement association on aligned observations; report method, sample count, and missing-value policy.
- [x] M6-08 — Status: DONE — merged/validated, 38 targeted / 1203 unit and Fast PR PASS. Owner: Eray; Branch: `feature/m6-07-10-association` from `dev` `cb1797c`; PR: [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51) merged at `1e8c417`; Commit: `b575883`. Evidence: [M6-07..10 association and lag record](#m6-0710-association-and-lag-record). Reject or explicitly flag too few observations and constant series; avoid invalid/undefined statistics.
- [x] M6-09 — Status: DONE — merged/validated, 38 targeted / 1203 unit and Fast PR PASS. Owner: Eray; Branch: `feature/m6-07-10-association` from `dev` `cb1797c`; PR: [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51) merged at `1e8c417`; Commit: `b575883`. Evidence: [M6-07..10 association and lag record](#m6-0710-association-and-lag-record). Implement lag analysis with a clear lag sign, bounded search window, and per-lag sample counts.
- [x] M6-10 — Status: DONE — merged/validated, 38 targeted / 1203 unit and Fast PR PASS. Owner: Eray; Branch: `feature/m6-07-10-association` from `dev` `cb1797c`; PR: [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51) merged at `1e8c417`; Commit: `b575883`. Evidence: [M6-07..10 association and lag record](#m6-0710-association-and-lag-record). Test non-stationary/spurious-correlation examples and prevent an association result becoming causal prose.
- [x] M6-20 — Status: DONE — merged/validated (PR #31 / 6b1ee47, 39 targeted SQL tests). Owner: Eray; Branch: `feature/m6-lakehouse-tool`. Implement the `lakehouse` tool as restricted text-to-SQL over gold under [DEC-121](DECISIONS.md#dec-121--six-brief-named-tools-with-typed-schemas-and-restricted-sql): parse the statement, allow only whitelisted tables, dry-run through `EXPLAIN`, then execute read-only with the engine's file, network and extension capabilities switched off. Evidence: [lakehouse tool record](#lakehouse-tool-record).
- [x] M6-21 — Status: DONE — merged/validated (PR [#43](https://github.com/cagatayeroglu/KKB-DataTrio/pull/43) / `2060f31`, 31 targeted / 980 unit tests). Owner: Eray; Branch: `feature/m6-21-lakehouse-typed-result`; Commit: `0e4521b`. Project a validated `lakehouse` query into the M6-01 `AnalyticalResult` using only the semantics the lakehouse already stores, so a claim can be bound to a period, unit and run. Added under the M6-20 precedent, where a numbered task was created when the need appeared. Evidence: [M6-21 typed lakehouse result record](#m6-21-typed-lakehouse-result-record).
- [x] M6-22 — Status: DONE — merged/validated (PR [#49](https://github.com/cagatayeroglu/KKB-DataTrio/pull/49) / `eafafa5`, 21 targeted / 1138 unit tests). Owner: Eray; Branch: `feature/m6-22-change-detection-tool`; Commit: `19351a3`. Expose the M6-02/03/04 analytics as the brief-named `change_detection` tool: an explicit operation argument, declared semantics and observations read from the lakehouse, a typed comparison with lineage. Added under the M6-20/M6-21 precedent. Evidence: [M6-22 change detection tool record](#m6-22-change-detection-tool-record).
- [x] M6-23 — Status: DONE (merged and validated). Owner: Çağatay; Branch: `feature/m6-23-projection-provenance` (merged and deleted); PR: [#62](https://github.com/cagatayeroglu/KKB-DataTrio/pull/62), merged at `b3ab7f2`. Reject fabricated lakehouse measurements and semantics. Critical correctness regression in M6-21: referencing an allowed table does not establish provenance for projected values or metadata. Evidence: [M6-23 record](#m6-23-projection-provenance-record).
- [x] M6-24 — Status: DONE — merged/validated (PR [#67](https://github.com/cagatayeroglu/KKB-DataTrio/pull/67) / `b335e16`, 73 targeted / 1547 unit tests). Owner: Eray; Branch: `feature/m6-24-calendar-valid-lag` (deleted after merge); Commit: `991000a`. Enforce calendar-valid lag pairs: a lag of k pairs periods k declared calendar steps apart, never k surviving rows. Correctness blocker C in M6-09's lag search; added under the M6-20/M6-21 precedent. Evidence: [M6-24 record](#m6-24-calendar-valid-lag-record).
- [ ] M6-11 — Status: READY. Owner: unassigned; Branch/PR/Commit: —. Implement the DEC-120 causality tool: lagged cross-correlation and Granger tests via `statsmodels`, with mandatory printed limitations and no "X causes Y" phrasing. Association/lag is already delivered by #51; remaining Granger readiness/acceptance: [record](#m6-11-readiness-record).
- [ ] M6-12 — Implement supported causality method only if justified/time permits; otherwise record explicit scope cut and abstention behavior.
- [ ] M6-13 — Status: BLOCKED on M2-14/15 index/reference compatibility and deflation implementation; no deflation function is delivered. Owner: unassigned; Branch/PR/Commit: —. Reuse M2 deflation with reference-period evidence; never compare nominal and real measures silently.
- [ ] M6-14 — Generate deterministic table/chart data from tool outputs; formatting must not recompute material values through the model.
- [ ] M6-15 — Test numeric oracles, tolerances, warning semantics, and source/transformation links.
- [ ] M6-16 — Run targeted analytics tests/lint and relevant smoke cases; record per-tool support and next task.

<a id="m6-24-calendar-valid-lag-record"></a>
### M6-24 calendar-valid lag record

- Status: DONE — PR #67 merged into `dev` at `b335e16f438c0a43bec2f74e69f3f4bd3369c066`; merged tree equals validated head `991000ae32f41f0d42280ddb0bb9ad2af4d83f2a`. Claim and implementation commits are reachable from `origin/dev`.
- Owner: Eray
- Branch: `feature/m6-24-calendar-valid-lag`, from `dev` `b54403a84f7ba97b6a065a894a68be2509c3764b`; deleted locally and remotely after the verified merge.
- PR: [#67](https://github.com/cagatayeroglu/KKB-DataTrio/pull/67), `feature/m6-24-calendar-valid-lag` -> `dev`; merged. Draft claim published before implementation; no other open PR or claim on the post-publication recheck.
- Commit: `991000ae32f41f0d42280ddb0bb9ad2af4d83f2a` (implementation); claim `f0bd336`.
- Prerequisites: merged M6-09 lag search (#51) and the existing period utilities (`lakehouse/periods.py` `spine`, `SeriesSemantics`, `Frequency`/`WeeklyAnchor`). No live data, provider, organizer answer or Day 0 recovery is needed.
- Reproduction (on `2fc56c9`, synthetic in-memory): the left series publishes every month of 2024–2025 and the right skips March 2024 only. `_aligned` drops March and `_shift` slices the compressed lists by position, so lag +1 pairs `x@2024-02-29` with `y@2024-04-30`, two calendar months apart, and the result is COMPUTED with per-lag counts `{-2: 21, -1: 22, 0: 23, 1: 22, 2: 21}`. A row offset is not a time lag, and the negative branch has the same defect. No existing test combined a gap with a non-zero lag.
- Acceptance: (1) lag k means k declared calendar periods, not k surviving rows; (2) missing periods cannot be compressed into adjacent lag pairs; (3) sample counts reflect only calendar-valid pairs; (4) incompatible or missing frequency/anchor information fails closed; (5) contiguous-calendar behaviour remains correct; (6) relationship/lag warnings and limitations remain accurate.
- Approach, confirmed by Eray before implementation: pairs are drawn only from periods both series published — x at aligned period p with y at the aligned period exactly k declared steps later — keyed by position on the canonical period spine rather than in the list. A partner period that is not aligned makes no pair. A frequency with no canonical step, mismatched weekly anchors and dates off the declared calendar abstain instead of guessing.
- Scope: `analytics/association.py`, its tests and this record. No Granger (M6-11), no D/E/F blocker work, no M0-08 typing and no tool schema change.
- Implementation: [analytics/association.py](../src/kkb_agent/analytics/association.py). `_calendar_positions` places every aligned period on the canonical `spine` for its declared frequency and anchor, and `_shift` now pairs by that position — x at position t with y at t+k, both aligned — instead of slicing lists. One keyed rule serves both signs, so the negative branch cannot drift from the positive one again. Contiguous data gives exactly the old pairs.
- Fail closed, all ABSTAINED with the reason and no number: a frequency with no canonical step (daily, business-day, twice-monthly, irregular — the `spine` policy, which has no holiday calendar to count by); an aligned date off the declared calendar, at either end or inside; a period published twice; and weekly series anchored to different weekdays. The anchor check lives in the shared `_prepare`, so `associate` now abstains on it too instead of reporting "0 aligned periods" as INSUFFICIENT — more data would never fix it. Unknown frequency was already refused as unresolved, and a weekly series without an anchor cannot be constructed; both are pinned. Association over daily periods is unaffected, since lag 0 needs no step.
- Warnings (acceptance 6): the lag result compared the strongest offset's Pearson figure with lag 0's Spearman figure, so the WAVES/ECHO fixture — an exact two-month copy — was told its linear and rank correlations differed by 1.36 and that the relationship was not linear. The shape and trend diagnostics now read the strongest offset's own pairs; a genuinely curved lead is still flagged and a shared trend still named. `parameters.lag_unit` states the unit ("declared monthly periods ... a gap is never bridged"). Sign, search-inflation and dropped-period warnings and every limitation are unchanged.
- Tests: PASS (2026-09-11, Python 3.12.5). `pytest -q tests/unit/test_association.py` — **73 passed / 1.21s**, 35 new: the reproduction (now `{-2: 20, -1: 21, 0: 23, 1: 21, 2: 20}`), contiguous lag +1 and -1, one missing month in each direction, several gaps on both sides checked at every offset -3..+3 against an independent index-based oracle and `statistics.correlation`, alternating months (no one-month pair exists), an offset pushed below the floor by a gap, too few calendar-valid pairs, lag 0 equal to `associate`, weekly and quarterly steps, each refusal above, the three warning cases and a lakehouse-stored gap through the `causality` tool. **26 of the 35 fail against the pre-fix module**; the other 9 pin behaviour that must not change. Related suites (`test_alignment`, `test_cumulative`, `test_lakehouse`, `test_result_contract`, `test_anomaly`, `test_change_comparison`, `test_change_detection_tool`) with association: 306 passed. `make quick` **1547 passed / 30.47s**; `make pr` **1547 passed / 30.55s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the changed module PASS; `mypy src` 23 errors in 7 files, identical with and without this change (see M0-08).
- Documentation: ARCHITECTURE's analytics paragraph (pairs only on periods both published, per-offset counts, sign convention, search inflation) stays true and is unchanged; the historical M6-07..10 record stays historical. The `causality` tool description and schema are unchanged because nothing they state became false. The M0-08 figure in this file was corrected from a fresh measurement, as M6-01 did before.
- Limitations: pairs need both periods published by both series, which is conservative — x at t and y at t+k are not paired when y at t or x at t+k is missing, although both values being paired exist. `_trend` still scores against list position, so a gap slightly compresses the time axis of the shared-trend flag in both `associate` and `lag`; it is a reader's flag with an unmeasured threshold, not a count, and is left for a separate change. No lag over daily data until a holiday calendar exists.
- Blocker: none known in scope.
- GitHub: claim run and final-head [Fast PR PASS](https://github.com/cagatayeroglu/KKB-DataTrio/actions/runs/34544817213) (1m39s) at `991000a`; conflict-free, three-file scope verified before the merge.
- Handoff: blocker C is closed and M6-24 is complete; this record finalizes already merged work. M6-11 (Granger) can now build on a calendar-valid lag primitive. D, E and F remain open and untriaged. No next task is started by this update.

<a id="m6-0710-association-and-lag-record"></a>
### M6-07..10 association and lag record

- Status: DONE — M6-07/08/09/10 merged in PR #51 at `1e8c41701aa0a68c40be4128b33eaecc6bb78763`; merged tree equals validated `b575883d5f60fff74b96013e7344c5212a311993`. Final GitHub check PASS, verified 2026-09-10.
- Owner: Eray
- Branch: `feature/m6-07-10-association`, from `dev` `cb1797ca0010ab39f880a3b7755e9e7e1b5654bb`
- PR: [#51](https://github.com/cagatayeroglu/KKB-DataTrio/pull/51), `feature/m6-07-10-association` -> `dev`; merged; no active claim remains. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `b575883d5f60fff74b96013e7344c5212a311993` (implementation); claim `53f50f3`.
- Objective: Association on aligned observations with method, sample count and missing-value policy; bounded lag with an explicit sign convention and per-lag counts; refusal of constant and too-short series; a shared-trend diagnostic for the spurious case. Exposed as the brief's `causality` tool under DEC-120.
- Scope note: **Granger (M6-11) is not in this task.** It needs `statsmodels` from the DEC-124 allowlist and joins the two delivered operations (`association`, `lag`) as a third operation, so the argument schema offers only what exists and the tool description says Granger is unavailable.
- Implementation: [analytics/association.py](../src/kkb_agent/analytics/association.py) and [tools/causality.py](../src/kkb_agent/tools/causality.py). Pure Python — `numpy` is a transitive `pandas` dependency, not a declared one, so relying on it here would have been a hidden dependency for arithmetic this simple.
- **Alignment (M6-07).** Two series are paired only on periods both actually published, matched by period end. A monthly series and a quarterly one are **refused**, not resampled: choosing how to resample is a semantic decision with a right answer per series, and making it silently here is how a number stops meaning what its label says. Dropped periods are counted and reported; nothing is filled to make a pair.
- **Shape.** Pearson measures linear association; Spearman measures monotone association and is unmoved by one extreme pair. Both are reported, and when they differ by more than 0.2 the result says the relationship is not linear and that the rank figure is the more robust. The cut discriminates as intended and is pinned in both directions: an exponential-against-linear pair gaps 0.23 and is flagged, a squared one gaps 0.03 and is not. Flagging the mild case would train a reader to ignore the warning. Exponential shapes are not contrived here — nominal Turkish series in the brief's window grow close to exponentially.
- **Refusals (M6-08).** Fewer than 24 aligned pairs is INSUFFICIENT, because a correlation over a handful of points is noise with a decimal point. A series with no variance makes correlation UNDEFINED rather than zero, and the result carries no number at all.
- **Lag (M6-09).** Correlation at each offset in a bounded window, capped at 12 because every extra lag is another chance for noise to produce the largest number. The **sign convention** appears in the value label, the parameters and a warning in plain words — reading it backwards inverts the entire finding — and a test asserts that swapping the two series negates the reported offset. Each offset reports its own sample count, since a lag of k discards k overlapping observations and the far offsets would otherwise look as well-evidenced as the near ones. The result states that the strongest of N offsets was selected and is inflated by the search itself.
- **Spurious correlation (M6-10).** Each series is scored against time; when both trend strongly the result says two trending series correlate whatever they measure and names period-over-period differencing as the check. It does **not** silently difference them — that would answer a question nobody asked and the reported number would no longer be the one the label describes. A test builds two independent rising series, confirms they correlate above 0.99, and asserts the warning fires.
- **No causal prose (M6-10, DEC-120).** Every result carries "association, not causation", "a third factor moving both would produce the same number" and "no identification strategy was applied"; the lag result adds that a leading correlation is not evidence of direction. This is enforced by the M6-01 contract, which refuses to construct a relational result without limitations, so it cannot be lost by a rewrite. The tool passes limitations to the model **as warnings**, because a model that never sees the caveat writes around it, and its description leads with "reports ASSOCIATION ONLY".
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_association.py` — **38 passed**, including a built-in two-period lag the search must recover, the swap-inverts-the-sign property, per-lag counts, the spurious pair, both sides of the non-linearity cut, frequency mismatch, constant and short-series refusals, and the tool's schema refusing `granger` and an over-cap lag. `make quick` / `make pr` — **1203 passed / 19.95s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Limitations: **no Granger, so DEC-120's tool is half-delivered** and the description says so. No stationarity test, no cointegration, no differencing option, and no partial correlation controlling for a third series — the shared-trend warning names the problem without solving it. Two series at a time. The 24-pair floor, the 0.9 trend limit and the 0.2 non-linearity gap are unmeasured defaults recorded in the result; M9 owes them a benchmark.
- Blocker: none known in scope.
- Handoff: Four of the six brief tools now exist. The natural next step is **M6-11**, Granger through `statsmodels` as this tool's third operation, which completes DEC-120 — note it adds `statsmodels` and its `scipy` dependency to the runtime manifest and to CI install time. M6-13 deflation remains a high-value later candidate for the reference scenario, but M2-14/15 must be implemented before its reuse objective is READY.

<a id="m6-11-readiness-record"></a>
### M6-11 readiness record

- Status: READY — rechecked at `b335e16` after PR #67 (M6-24); no open PR or published claim.
- Owner: unassigned; Branch/PR/Commit: —; Tests: NOT RUN (no Granger implementation).
- Prerequisites: typed result/refusal/evidence contracts (#42/#43), aligned association/lag and registered `causality` tool (#51) with calendar-valid lag pairs (#67), confirmed DEC-120 method and DEC-124 dependency allowance. `statsmodels` is not installed yet; adding the already-approved dependency belongs to this task.
- Remaining acceptance: add bounded Granger tests using the existing typed tool/result shape; retain explicit alignment, lag/sample policy, deterministic failure/refusal fixtures and mandatory non-causal limitations; targeted tests and `make pr`. Do not claim stationarity, identification or structural-break handling that is not implemented.
- Blocker: none known for this offline task; no live source, organizer answer or Day 0 recovery required.
- Handoff: independent parallel candidate for Eray, not an assignment. Publish a fresh claim from latest `dev` before implementation; do not reuse #51's merged branch.

<a id="m6-0506-anomaly-record"></a>
### M6-05/06 anomaly record

- Status: DONE — PR #50 merged into `dev` at `cb1797ca0010ab39f880a3b7755e9e7e1b5654bb`; merged tree equals validated `a308202`.
- Owner: Eray
- Branch: `feature/m6-05-06-anomaly`, from `dev` `eafafa5cf5a1761bfbc62875558cf67bf9592ac6`; deleted after merge.
- PR: [#50](https://github.com/cagatayeroglu/KKB-DataTrio/pull/50), `feature/m6-05-06-anomaly` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: recorded on the PR; claim `83c56d0`.
- Objective: Choose and document a robust anomaly baseline with explicit minimum-sample and threshold policy, implement it deterministically with the parameters recorded in the result, and expose it as the brief-named `anomaly` tool. Thresholds are PROPOSED until a benchmark measures them.
- Implementation: [analytics/anomaly.py](../src/kkb_agent/analytics/anomaly.py) and [tools/anomaly.py](../src/kkb_agent/tools/anomaly.py), following the M6-22 shape — read declared semantics, compute, return a typed result, record lineage only for a computed one.
- **M6-05, the baseline, is two choices.** *What is examined*: period-over-period **changes**, never levels. Housing credit runs 276,785 to 801,438 over five years, so every recent level is unusually high against its own history and a level detector would flag the present and nothing else; the interesting event is a month that moved unlike other months. *How the spread is estimated*: median and **median absolute deviation**, with the Iglewicz–Hoaglin modified z-score at 3.5. Mean and standard deviation are computed from data containing the outlier, so one large jump inflates the spread until its own score falls below the cut — the more extreme the event, the better it hides. A test measures that: a jump 49x the usual step scores under 5 on a plain z-score, barely above the cut.
- A defect the tests found, fixed properly. **MAD is exactly zero whenever more than half the changes are identical** — which is the archetypal case, a regular series with one jump — so the first implementation refused the clearest signal there is. The fix is the same paper's published fallback: the mean absolute deviation about the median, scaled by 1.253314, used only when MAD collapses. It is zero only when *every* change is identical, which is then genuinely UNDEFINED and is also M6-08's constant-series rule. The result records which estimator was used.
- The threshold and the minimum sample are **not planner arguments**, and a test asserts the schema exposes only `series_id`, `start` and `end`. A model that can move a threshold will move it until something looks interesting, and the output would not show that it had. Both defaults are recorded in every result's `parameters`, including a `threshold_status` of "PROPOSED; no benchmark has measured it" so an unmeasured default cannot read as a validated one.
- The count is always reported, including zero. "No anomalies" is an answer, and the M8 gate withholds any sentence whose number it cannot bind — so a bare "0 anomali bulundu" needed a bindable zero. It is `DIMENSIONLESS`, not unknown.
- A gap breaks the chain rather than being bridged: differencing across it would report two periods of movement as one, which is larger than anything that happened. The skipped period is counted and reported.
- One shared-contract correction, made where the rule belongs. `SampleCounts` refused any below-floor count, which also blocked an **INSUFFICIENT** result from stating how far short it fell — the exact thing that makes such a result self-explaining. The counts alone cannot see the status they belong to, so the rule moved to `AnalyticalResult._check_computed`: only a COMPUTED result may not fall below its own floor. `SampleCounts.below_floor` describes the shortfall instead. The earlier `used == 0` carve-out was the smell that this was in the wrong place. M6-01's tests are updated to pin the corrected rule on both sides.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_anomaly.py` — **25 passed**, covering the level-versus-change property, the collapsed-MAD fallback, the outlier-hiding comparison, the always-reported count, too-few-changes, constant-series, unresolved and cumulative refusals, gap handling, the recorded parameters, and the tool's lineage, unknown-series failure and argument surface. `make quick` / `make pr` — **1165 passed / 19.94s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Limitations: one series at a time, and no explanation of *why* a period is unusual — the tool reports which periods stand out, not what happened in them. The threshold and minimum sample are unmeasured defaults; M9 owes them a benchmark before any claim that they are tuned. Seasonality is not modelled, so a series with a strong annual pattern will flag its own season; the reference series are not obviously seasonal, but that is an assumption, not a finding. Breakpoint detection still belongs to `change_detection` and remains unimplemented.
- Blocker: none known in scope.
- Handoff: Three of the six brief tools now exist — `lakehouse`, `change_detection` and `anomaly`. The remaining analytical one is **`causality`** (M6-07/08/09/10/11): association on aligned observations, lag with a stated sign convention, and the DEC-120 rule that it reports association with mandatory limits and never causal prose. `web_search` and `web_url` remain gated on Q-NET-01/02, though the `web_url` parser work is worth starting because DEC-131 makes it a confirmed demo-day requirement.

<a id="m6-22-change-detection-tool-record"></a>
### M6-22 change detection tool record

- Status: DONE — PR #49 merged into `dev` at `eafafa5cf5a1761bfbc62875558cf67bf9592ac6`; merged tree equals validated `0d0a617`.
- Owner: Eray
- Branch: `feature/m6-22-change-detection-tool`, from `dev` `63b363e819d3747bfd44ae1663b67134400f5f5b`; deleted after merge.
- PR: [#49](https://github.com/cagatayeroglu/KKB-DataTrio/pull/49), `feature/m6-22-change-detection-tool` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `19351a3` (implementation); claim `02b0c7c`.
- Objective: Register `change_detection` so the planner can ask for a comparison. Read the series' declared semantics and its observations from the lakehouse, return the M6-02/03 typed result, and record lineage. Breakpoint detection is deliberately absent from the argument schema until M6-05/06 implements it.
- Implementation: [tools/change_detection.py](../src/kkb_agent/tools/change_detection.py), exported from [tools](../src/kkb_agent/tools/__init__.py). The analytics package is unchanged — this task adds the route to it, not the arithmetic.
- **No seventh tool.** `ToolRegistry` refuses any name outside the six the brief fixes, and a tested case proves it still does. A period comparison is a level change, which is squarely inside what `change_detection` names ("trend, seviye veya davranış değişimleri"). Reading the brief's tool list as a maximum rather than adding to it also keeps [DEC-121](DECISIONS.md#dec-121--six-brief-named-tools-with-typed-schemas-and-restricted-sql)'s "tool additions need their own decision" clause unused, which is the right outcome when an existing name fits.
- The `operation` argument has one member on purpose. Breakpoint and trend-break detection are two different jobs with two different methods, so the tool says which one it is doing rather than blurring them — and `breaks` is **absent from the schema entirely** until M6-05/06 gives it a method. A planner cannot ask for something that does not work if the schema never offers it; a test asserts the schema refuses `breaks` today, and the description says so in words.
- Semantics are read, never inferred. `read_series` pulls unit, scale, frequency, anchor, observation kind, cumulative behaviour and aggregation from `silver_series` and reconstructs the validated `SeriesSemantics`; a declaration that cannot be reconstructed is an error rather than a set of defaults, because guessing a scale is how a million-TRY figure gets compared against a thousand-TRY one. Everything that follows — the stock warning, the cumulative refusal, points rather than percent for a rate — comes from the analytics package and is not re-decided in the tool.
- A refusal is a **successful** call. An unpublished date returns SUCCESS carrying an INSUFFICIENT result and surfaces the reason as a warning; only an unknown series is a FAILURE. Reporting a refusal as a failure would hide which of the two happened. A refused comparison records **no** lineage node, because provenance for a non-result is a link to nothing.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_change_detection_tool.py` — **21 passed**, covering the computed comparison and its declared semantics, a rate's point change through the tool, lineage written and resolvable, the unknown-series failure, the unpublished-date and backwards-range refusals, schema rejection of `breaks` and of an extra field, the registry still refusing a seventh name, and a planner-routed question reaching a gated answer with an invented figure stripped. `make quick` / `make pr` — **1138 passed / 19.75s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on both changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Limitations: `compare` only — no breakpoint detection, no change *series* over every period, and no multi-series comparison in one call. The tool compares two endpoint dates the planner must state exactly; it does not resolve "last quarter" or pick a range itself. Cumulative series are still refused rather than converted. Four brief tools remain unimplemented: `web_search`, `web_url`, `anomaly` and `causality`.
- Blocker: none known in scope.
- Handoff: The agent can now be *asked* for a comparison and answer it under the gate, which is the first tool beyond `lakehouse` to do real analytical work. Next by brief coverage is **M6-05/06** (the anomaly baseline and its `anomaly` tool) and **M6-07/09/11** (association, lag and the DEC-120 `causality` tool) — both extend this same shape. The scenario's second turn needs **M6-13** deflation, which also unblocks M8-07's transformation prerequisites.

<a id="m6-020304-change-and-comparison-record"></a>
### M6-02/03/04 change and comparison record

- Status: DONE — PR #48 merged into `dev` at `63b363e819d3747bfd44ae1663b67134400f5f5b`; merged tree equals validated `3d39581`.
- Owner: Eray
- Branch: `feature/m6-02-04-change-comparison`, from `dev` `b5b09a5cd90293ea464eb26057c4afaaef467e9c`; deleted after merge.
- PR: [#48](https://github.com/cagatayeroglu/KKB-DataTrio/pull/48), `feature/m6-02-04-change-comparison` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `fc1b78e` (implementation); claim `b7ce3fe`.
- Objective: Compute absolute and relative change and a period comparison as typed results, with stock/flow, cumulative and rate/index semantics deciding what a change means, an explicit denominator/zero policy, exact endpoint selection and transparent missing observations. Hand-calculated fixtures over negatives, zeros and empty ranges.
- Implementation: new [analytics](../src/kkb_agent/analytics/change.py) package — ARCHITECTURE component 9, added with its task under [DEC-125](DECISIONS.md#dec-125--source-layout-with-named-module-packages) — providing `absolute_change`, `relative_change` and `compare_periods`, each returning an M6-01 `AnalyticalResult`. No existing module changed.
- Subtracting is not the hard part; deciding whether the subtraction *means* anything is, and that decision comes from declared semantics rather than from the numbers. A **stock** differenced is the change in an outstanding balance, and the result says so in a warning: the BDDK inventory found `Tüketici Kredileri - Konut` falls in 8 of 65 steps, so reading its difference as new lending is wrong by the whole repayment stream. A **cumulative** series abstains until it is converted to flow, because differencing it measures accumulation instead of activity — and one BDDK bulletin contains both accumulation behaviours. **Unresolved semantics abstain** rather than compute.
- A **rate** or **index** changes in points, not in its own unit. 40 -> 46.75 is +6.75 **percentage points** and +16.875 **percent**; the two differ by a factor of two and a half, and the unit is carried in the value so the verifier's scale check can see it. Both figures are available and separately labelled.
- The denominator policy is a refusal, not a formula. A **zero base** returns UNDEFINED — zero has no proportion — and points at the absolute change instead. A **negative base** returns UNDEFINED because the sign inverts: -100 -> -50 is an improvement that the formula reports as -50%. A negative *endpoint* over a positive base is fine and computes -150%, because nothing about that is ambiguous.
- Selection is exact and gaps stay gaps. A requested date that was never published is INSUFFICIENT naming what the series does publish, because resolving to a neighbouring month is indistinguishable in the output from having compared the right one. A null endpoint is INSUFFICIENT saying "a gap is not zero and is not carried forward"; an interior gap between the endpoints is not this function's problem and does not block the change.
- One oracle was wrong and the test caught it — the recorded expectation for the relative change was `4.447253%` when exact decimal division gives `4.4472015%`. The **test** was corrected, not the code, and the comment now records that the figure was checked by independent decimal arithmetic rather than by calling the function under test. That is what hand-calculated fixtures are for.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_change_comparison.py` — **37 passed**, covering the arithmetic, negatives, zeros, empty and backwards ranges, non-published dates, single-endpoint and both-endpoint gaps, rate/index point units, cumulative and unresolved refusals, and the comparison's combined output. `make quick` / `make pr` — **1117 passed / 19.25s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the new package PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08. No `assert` is used for narrowing — a `_Endpoints` record carries the checked values instead, because an assert vanishes under `-O`.
- Limitations: **not yet a registered tool.** These are functions the caller invokes; wiring them behind a brief-named tool, and letting the planner choose a date range, is separate work. Nothing reads observations from the lakehouse here — the caller supplies them, so the `silver_observations` default input reference is a convention rather than an enforced fact. Only two endpoints are compared; a change *series* over every period, which a chart needs, is not implemented. Cumulative conversion is refused rather than performed, even though `to_flow` exists, because choosing to convert is a semantic decision the caller should make explicitly.
- Blocker: none known in scope.
- Handoff: The analytical half of the reference scenario's first turn now exists: housing credit's level, its move and the rate's move in the correct units, all as gated-answerable results. The next step that turns this into demo behaviour is **exposing it as a registered tool** so the planner can ask for a comparison, followed by M6-05/06 (the anomaly baseline) and M6-07/09 (association and lag), which the brief names. M6-13 deflation is the other half of the scenario's second turn and unblocks M8-07's transformation prerequisites.

### M6-01 result contract record

- Status: DONE — PR #42 merged into `dev` at `d4d584bfe08efa3d8fe9f0d852a825d7a1e60906`; merged tree equals validated `3c4d68e`.
- Owner: Eray
- Branch: `feature/m6-01-result-contract`, from `dev` `90dd9e9858725457533bb4c64aaf1061f6f9e0dc`; deleted after merge.
- PR: [#42](https://github.com/cagatayeroglu/KKB-DataTrio/pull/42), `feature/m6-01-result-contract` -> `dev`; merged. Claim published before implementation; no collision on post-publication remote recheck.
- Commit: `194df0c` (implementation); claim `42fc1e6`.
- Objective: Define the narrow typed contract an analytical tool returns — values, units and scale, periods, sample counts, warnings and evidence references — and specify how result identity connects to M5 execution and M8 verification. Not a proof engine.
- Readiness at start: queue position 1, unowned, no competing branch or PR on `origin`. Core records, the M5 registry and the M6-20 lakehouse result exist; DEC-112/119/120/128 fix the deterministic/evidence direction. No unresolved team or organizer decision blocks a contract definition.
- Implementation: [core/results.py](../src/kkb_agent/core/results.py) defines `Period`, `SampleCounts`, `ResultValue`, `ResultEvidence` and `AnalyticalResult`, plus `ResultKind`, `ResultStatus` and the `DIMENSIONLESS` unit sentinel, exported through [core/__init__.py](../src/kkb_agent/core/__init__.py). No tool, executor, workspace or verifier code changed; nothing is wired yet, by design.
- Why the invariants are what they are. Each refusal traces to a measured failure rather than a preference. **A value must state its unit**: `unit=None` means unknown and forces the result to populate `unresolved_semantics`, while a genuinely unitless quantity declares `DIMENSIONLESS`. BDDK publishes monthly/weekly bulletins in million TRY and FinTürk in thousand, so an unrecorded scale is a silent 1000x error rather than a cosmetic gap ([BDDK_SOURCE](BDDK_SOURCE.md)). **A non-computed result carries no values at all**, and INSUFFICIENT / UNDEFINED / ABSTAINED are kept distinct: more data fixes the first, never fixes the second, and the third means the numbers exist but their meaning does not. **Association, lag and causality results must state limitations** before they validate, which puts [DEC-120](DECISIONS.md#dec-120--causality-reports-association-with-stated-limits) in the type system instead of in a code review. **A weekly period must name its anchor and end on that weekday**, because EVDS anchors most weekly series to Friday and at least one to Wednesday.
- Values are strict. `value` rejects strings and booleans rather than coercing them: `"1.234"` is 1234 in a Turkish answer and 1.234 to Python, and that is the same thousandfold ambiguity the verifier's number parser exists to avoid. Non-finite values are already refused by `ContractModel`.
- Identity, and the part M5/M8 still owe. `result_id` is the caller's handle; `digest()` is a SHA-256 over the canonical serialization **excluding** `result_id`, so the same computation stored under another name hashes alike while any change to a value, period, sample count, parameter, run or evidence reference changes the hash. That is the missing primitive behind two recorded gaps — the workspace cannot currently reject a stale result and the verifier binds numbers by value proximity because no result carries period/unit/run identity. This task supplies the identity only: the run manager, the stale-read rejection and the answer gate remain M5-10/11/12 and M8-03..M8-12. A digest is not a proof.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_result_contract.py` — **57 passed / 0.11s**. `make quick` — **949 passed / 16.84s**. `make pr` — **949 passed / 16.25s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on both new/changed source files PASS. [Tests](../tests/unit/test_result_contract.py) cover period ordering and weekly-anchor agreement, negative/coerced/non-finite counts and values, the unit and limitation refusals, all three non-computed states, JSON round-trip, digest stability under rename and digest change under each material field, and post-construction reassignment.
- Measured correction to a stale figure: `mypy src` reports **17 errors in 5 files** on `dev` `90dd9e9`, not the 14 recorded under M0-08. The three additional errors are in the M7 `ingest` modules merged after PR #32. This branch adds none; the M0-08 record is corrected below rather than left to mislead whoever picks it up.
- Limitations: contract only. No tool emits an `AnalyticalResult` yet, the lakehouse tool still returns `QueryResult`, and `ToolResult.output` remains `object`. `ResultEvidence.input_refs` are unresolved strings — this module does not check that a lineage node or evidence record exists, which is M8-04. `describes_same_computation` compares content, not replay: two results can hash alike and still both be wrong.
- Blocker: none known in scope.
- Handoff: The contract exists and is exported from `kkb_agent.core`. The next step that turns it into product value is making the `lakehouse` tool return an `AnalyticalResult` instead of a bare `QueryResult`, which then lets M8 bind a claim to a period/unit/run rather than to any nearby number. M6-02/03 (change and comparison) are the natural first producers and can now be written against a settled output shape. Do not extend this module with proof, storage or recomputation logic; those belong to M8 and M5.

### M6-23 projection provenance record

- Status: DONE — implementation merged into `dev`; targeted/local fast checks and final-head Fast PR passed
- Owner: Çağatay
- Branch: `feature/m6-23-projection-provenance`, from `dev` `706007b343f14c7ed37317e02a049133951f2492`; deleted locally/remotely after verified merge and dependency/worktree checks
- PR: [#62](https://github.com/cagatayeroglu/KKB-DataTrio/pull/62), merged into `dev` at `b3ab7f2ff3976705177c867c3507445199987ae2` under the explicit task-specific authorization; no other PR merge authorized
- Commit: implementation `4c88be2fc0472568fd4659d08d949af5c72f297e`; final reviewed head `56f081a5ddca2072df4aa48f5012ca6cc3a07e0b`; both reachable from fetched `origin/dev`, with the validated code/tests unchanged by merge
- Severity: CRITICAL — blocks the first trusted live vertical slice.
- Prerequisites: M6-01 (#42), M6-20 (#31), M6-21 (#43), M8-06 (#44) and M8-10 (#45) are merged. No live data, provider, organizer answer or Day 0 recovery is needed.
- Reproduction: synthetic in-memory queries with an allowed `FROM` and fabricated measurements, series identity, periods or unit/scale columns receive COMPUTED evidence and pass the answer gate. Missing identity also bypasses the store recheck. Reproduced on `706007b` before implementation.
- Acceptance: A COMPUTED measurement must trace its value and required semantic identity to permitted stored inputs or an explicitly supported deterministic transformation. Source-table presence alone is insufficient. Literal/fabricated values, identities, periods, units and scales cannot acquire trusted evidence. Unsupported or ambiguous projections abstain with no material values; canonical source-backed queries remain supported. Blocking synthetic regressions cover these cases through the answer gate.
- Scope: Conservative SQL-to-result provenance gate, relevant tests and this record only. Existing SQL security controls remain independent. No general SQL provenance engine, claim/prose binding changes, M6-24, M0-08 or M6-11 work.
- Delivered: A conservative AST gate permits direct observation/metadata columns joined on series_id, then fixed parameterized SQL checks each returned row against its stored identity/value/semantics. Only COMPUTED results receive query lineage. No verifier/runtime-contract changes.
- Supported: Canonical silver joins (ON/USING, either order), explicit unchanged column aliases, filters/order/limits, null counts and truncation. Existing registered deterministic comparison remains supported.
- Fail closed: Literal/expressed measurements or metadata, missing identity/period/unit/scale, renamed/duplicate fields, mismatched joins, CTE/derived-table/set-operation projections, unidentified aggregates and gold projections with no complete semantic identity. Raw SQL inspection rows remain available; they are not result evidence.
- Tests: PASS (Python 3.12.2). `pytest -q tests/unit/test_projection_provenance.py tests/unit/test_lakehouse_projection.py tests/unit/test_lakehouse_tool.py tests/unit/test_verifier.py tests/unit/test_result_verification.py tests/unit/test_answer_gate.py tests/unit/test_multi_result_answer.py --disable-warnings --maxfail=1` — 219 passed / 5.68s, including 35 new in-memory cases; original regression failed before the fix. `make quick` — 1462 passed / 32.24s; `make pr` — 1462 passed / 32.40s, format/lint/Bandit/secret scan clean. Narrow `mypy --follow-imports=silent` on the three changed runtime modules passed. Final-head [Fast PR PASS](https://github.com/cagatayeroglu/KKB-DataTrio/actions/runs/34515407695/job/102999449796) at `56f081a`. Completion bookkeeping received diff/link/status review only; application checks were not rerun for documentation. No full/release/live checks or M0-08 changes.
- Blocker: none for M6-23; the remaining correctness defects below still block their affected acceptance paths.
- Handoff: M6-23 is merged and its task branch is cleaned. Review the separate completion PR from `docs/m6-23-completion` (based on updated `dev` `b3ab7f2`); its merge is not authorized by the #62 exception. B claim binding, C lag, D coverage, E workspace publication and F provider policy remain unresolved. M6-11 stays available for Eray; M0-08 remains READY/unowned but waits behind correctness blockers. No next task was started; main and the Day 0 stash were untouched.

### M6-21 typed lakehouse result record

- Status: DONE — PR #43 merged into `dev` at `2060f31bd9422c448c67a7191b59a5be7614d568`; merged tree equals validated `aa0ba65`.
- Owner: Eray
- Branch: `feature/m6-21-lakehouse-typed-result`, from `dev` `d4d584bfe08efa3d8fe9f0d852a825d7a1e60906`; deleted after merge.
- PR: [#43](https://github.com/cagatayeroglu/KKB-DataTrio/pull/43), `feature/m6-21-lakehouse-typed-result` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `0e4521b` (implementation); claim `d464d5b`; Q-DEV-01 closure `f6a44b1`.
- Objective: Make the `lakehouse` tool emit an M6-01 `AnalyticalResult` beside the rows it already returns, reading unit, scale, frequency, anchor and observation kind from the columns the lakehouse itself stores. Invent no semantics; keep the security gates untouched.
- Implementation: [tools/_projection.py](../src/kkb_agent/tools/_projection.py) maps a validated query onto the contract; [tools/lakehouse.py](../src/kkb_agent/tools/lakehouse.py) gains `LakehouseOutput`, which pairs the typed `result` with the `table` of rows. The five SQL gates are untouched — the projection runs only after `run_query` returns.
- The design rule is one sentence: **a column the query did not select is a semantic we do not know.** `silver_series` stores unit, scale, frequency, anchor and observation kind as the exact enum values the store wrote, so recognising those columns is a lookup rather than a guess. Only schema column names are interpreted; a column called `tutar` is data. Anything absent lands in `unresolved_semantics` with the reason, so a bare `SELECT value FROM silver_observations` returns a real number that openly admits it has no unit, no scale and no period. That is deliberate pressure toward joining `silver_series`.
- Two refusals live here because the security gates were never meant to catch them. A query that reads **no lakehouse table** abstains: `SELECT 42 AS konut_kredisi` is valid SQL, passes all five gates, and would otherwise let a model mint a figure with the authority of a computed one. A query with **no `value` column** abstains as a listing rather than pretending its rows are a measurement. Both keep the rows available; only the claim is withheld.
- Degrading loudly rather than guessing. A row declaring `weekly` without an anchor cannot form a valid `Period`, so the frequency drops to UNKNOWN and the note says which column was missing. A stored anchor that disagrees with the row's own `period_end` is reported as a contradiction instead of being silently accepted. Nulls count as `missing`, non-numeric cells as `excluded`, and booleans are refused because `bool` is an `int` in Python and would otherwise become `1.0`. Coverage is stated only when **every** row carried a period, since a span computed from some rows understates what is absent.
- Status mapping: COMPUTED with at least one numeric value; INSUFFICIENT for no rows or an all-null column; ABSTAINED for no source table, no value column, or a non-numeric value column. A non-computed status is still a **successful** tool call — the query ran — and its reason is surfaced as a warning, because conflating it with a failure would hide which of the two happened.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_lakehouse_projection.py` — **31 passed**. `pytest -q tests/unit/test_lakehouse_tool.py tests/unit/test_verifier.py` — 76 passed. `make quick` — **980 passed / 15.76s**. `make pr` — **980 passed / 16.71s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the three changed tool modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Two existing tests changed, both accessor-only: `test_lakehouse_tool.py` and `test_verifier.py` read `result.output.rows[0][0]`, now `result.output.table.rows[0][0]`. No assertion was weakened and no security test was touched.
- Limitations: contract-shaped, not verified. The verifier still matches numbers by value proximity and does **not** consume the typed result — wiring it is M8-06/07. `input_refs` are table names, not row-level references, so provenance stays table-level exactly as PR #31 recorded. A query aliasing an unrelated expression to `value` produces a typed number the projection cannot distinguish from a real one; the unit and period will be unresolved, which is the signal, not a guarantee. Nothing recomputes anything.
- Blocker: none known in scope.
- Handoff: The first real tool now returns a typed, digestible result with declared semantics. The next step that converts this into product value is M8-06/07 — have the verifier bind a claim to a result's period, unit and run instead of to any nearby stored value, and reject a number whose result declares its semantics unresolved. M6-02/03 can now be written against a settled output shape and should reuse `_projection` rather than re-deriving semantics. Do not extend `_projection` to interpret non-schema column names; that is the invented-semantics failure it exists to prevent.

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

PR #31 delivers restricted lakehouse SQL; #42/#43 add typed results/projection; #48/#49 add deterministic change/comparison and `change_detection`; #50 adds `anomaly`; #51 adds association/lag through `causality`. Their records preserve validation. Granger, breakpoint detection, deflation and benchmark-calibrated thresholds remain incomplete.


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

Status: PARTIAL — result-bound verification (#44), mandatory `Session.answer` gating (#45), multi-result workspace answers (#47) and claim semantic binding (#64) are merged and validated. Value/scale/period/reference checks and fixed-query store rereads exist. Transformation-prerequisite validation, dependent-claim invalidation after changed assumptions, conflicting vintages, full unit-text validation and independent recomputation from raw inputs remain incomplete. Workspace stale-read rejection is implemented; it does not complete all M8-12 claim invalidation.

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
- [x] M8-06 — Status: DONE — merged/validated (PR [#44](https://github.com/cagatayeroglu/KKB-DataTrio/pull/44) / `32ab2f3`, 38 targeted / 1017 unit tests). Owner: Eray; Branch: `feature/m8-06-07-result-verification`; Commit: `ba922f3`. Implement deterministic verification for basic change/numeric results against preserved input references. Evidence: [M8-06/07 result verification record](#m8-0607-result-verification-record).
- [ ] M8-07 — Status: PARTIAL — value, scale, period and sample checks merged in PR [#44](https://github.com/cagatayeroglu/KKB-DataTrio/pull/44) / `32ab2f3`, Commit: `ba922f3`; transformation-prerequisite validation remains unimplemented and waits on M2-15/M6-13. Owner: Eray (remaining scope retained, no active PR); historical Branch: `feature/m8-06-07-result-verification`. Verify units, periods, sample counts, and transformation prerequisites alongside values. Evidence: [record](#m8-0607-result-verification-record).
- [ ] M8-08 — Distinguish passed, failed, and not-run validation; partial results must identify exactly which claims are supported.
- [ ] M8-09 — Detect conflicting sources/vintages and surface the disagreement instead of choosing silently.
- [x] M8-10 — Status: DONE — merged/validated (PR [#45](https://github.com/cagatayeroglu/KKB-DataTrio/pull/45) / `bf8bba4`, 22 targeted / 1040 unit tests). Owner: Eray; Branch: `feature/m8-10-answer-gate`; Commit: `6b5ea54`. Gate answer assembly so unsupported claims are omitted, qualified, or answered with abstention. Evidence: [M8-10 answer gate record](#m8-10-answer-gate-record).
- [ ] M8-11 — Keep source citations separate from computation verification; a URL alone cannot prove a calculation.
- [ ] M8-12 — Test stale evidence after changed dates/assumptions and invalidate dependent claims.
- [ ] M8-13 — Render concise evidence summaries with safe locators and limitations for M10.
- [ ] M8-14 — Test missing source/run/transformation links, altered numeric output, and unsupported causal statements.
- [x] M8-15 — Status: DONE for the delivered numeric-binding scope. Run targeted evidence/verifier/contract tests, lint, and the fast PR gate when changing shared models. Evidence: PR #32, 37 targeted / 552 unit tests and fast checks; this is not full proof validation.
- [x] M8-17 — Status: DONE — merged/validated (PR [#47](https://github.com/cagatayeroglu/KKB-DataTrio/pull/47) / `b5b09a5`, 17 targeted / 1080 unit tests). Owner: Eray; Branch: `feature/m8-17-multi-result-answer`; Commit: `09d1741`. Let one gated answer cite several named results instead of one, faulting only the numbers that rest on a disqualified result, and gate `Session.answer` over the workspace's current values. Added under the M6-20/M6-21 precedent, where a numbered task is created when the need appears. Evidence: [M8-17 multi-result answer record](#m8-17-multi-result-answer-record).
- [x] M8-16 — Status: DONE for the delivered-scope handoff. Record verified claim types, evidence gaps, and the next tool needing verification. Evidence: PR #32's limitations and the reconciled record below; fixed-query store rereads exist via #44, independent second-path recomputation remains unimplemented.

- [x] M8-18 — Status: DONE — Bind accepted claims to result identity and semantics. PR #64 merged and validated at `e7630a8`. Owner: Çağatay; Branch: `feature/m8-18-claim-semantic-binding`. Narrow regression correction; historical M8 ownership is retained. Evidence: [M8-18 record](#m8-18-claim-semantic-binding-record).

<a id="m8-18-claim-semantic-binding-record"></a>
### M8-18 claim semantic binding record

- Status: DONE — PR #64 merged into `dev` at `e7630a8bd96a2c47b237b03513ada90e6d4a322e`; merged tree equals validated final head `a14d4301044b726ae9f2c61bb0f8e1bf2e224de2`. Implementation and task-branch tip are reachable from `origin/dev`.
- Owner: Çağatay
- Branch: `feature/m8-18-claim-semantic-binding`, from verified `dev` `0e27976cbfb02c1f86feb627dcf2a3f70d631a90` (M6-23 implementation #62 and completion #63 merged); task branch deleted locally and remotely after verified merge and dependency checks.
- PR: [#64](https://github.com/cagatayeroglu/KKB-DataTrio/pull/64), `feature/m8-18-claim-semantic-binding` -> `dev`; merged. Draft claim published before implementation; no other open PR on the post-publication recheck.
- Commit: `f10f03a6df996edb63e98f1d3cf253c6e50dafd6` (implementation); claim `92d5bfa`.
- Scope: Deterministic binding to supported result/value identity and explicit period, unit/currency and scale; conflicting or ambiguous qualifiers fail closed. Reject unsupported causal wording and prevent amount-qualified year-like numbers escaping validation. No broad semantic guard, deflation, or changes to other audit blockers.
- Implementation: [claim_qualifiers.py](../src/kkb_agent/agent/claim_qualifiers.py) checks explicit workspace/result/value IDs, Turkish/English months, calendar years/ISO dates and attached unit/currency/scale vocabulary. [verifier.py](../src/kkb_agent/agent/verifier.py) selects one semantically consistent result/value candidate; multiple supported candidates fail closed instead of taking the first magnitude match. The gate withholds unsupported causal sentences, including those without numbers. Amount-qualified year-like tokens lose the YEAR exemption in both verification entry points.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_claim_semantic_binding.py tests/unit/test_verifier.py tests/unit/test_result_verification.py tests/unit/test_answer_gate.py tests/unit/test_multi_result_answer.py tests/unit/test_change_detection_tool.py --tb=short` — **185 passed / 4.41s**, including **50 new synthetic regressions**. `make quick` — **1512 passed / 33.99s**, Ruff clean. `make pr` — **1512 passed / 33.13s**, Ruff format/lint, Bandit and secret scan clean. GitHub final-head Fast PR **PASS / 81s**, [run](https://github.com/cagatayeroglu/KKB-DataTrio/actions/runs/34518963546/job/103011384888), head `a14d430`; conflict-free and exact five-file scope verified before the authorized merge. No full/release/mypy gate run.
- Regression evidence: latest-dev reproduction accepted wrong month/currency/explicit series identity, unsupported causal prose and `2024 milyon TL`; the initial new test run had 32 failures. Wrong scale already rejected. Two old period tests were tightened because unknown periods and a single matching year do not prove explicit dates or a wider range; legitimate supported existing gate answers remain accepted.
- Limitations: bounded deterministic vocabulary, not general prose understanding or a full Claim/Proof implementation. Exact identifiers do not infer natural-language series aliases. Generic unsupported wording outside the listed causal vocabulary is not proved. Caller-justified `allowed` context retains its existing trust contract, but cannot override a contradicted matching result. Historical M8-01/07/12/14 remaining scope is not marked complete. No raw-input recomputation, C/D/E/F audit fix, deflation or broad semantic guard is delivered.
- Blocker: none known in this narrow scope.
- Handoff: M8-18 is complete; no new implementation task was started. Task-branch cleanup is complete, local `dev` equals `origin/dev`, and the working tree was clean at verification. This record finalizes already merged work only. M6-11 remains reserved for Eray and inactive; M0-08 remains READY/unowned but deferred behind correctness blockers. Historical Eray ownership on M8-01/M8-07 remains unchanged. Remaining audit blockers are C calendar-invalid lag, D false boundary coverage, E premature workspace publication and F Kloudeks destination/SDK mismatch. Stop after this task; no next implementation is claimed.

<a id="m8-17-multi-result-answer-record"></a>
### M8-17 multi-result answer record

- Status: DONE — PR #47 merged into `dev` at `b5b09a5cd90293ea464eb26057c4afaaef467e9c`; merged tree equals validated `f762363`. M5-11's remaining acceptance is met by this delivery.
- Owner: Eray
- Branch: `feature/m8-17-multi-result-answer`, from `dev` `ccb35db99c964175acf8d0ee3f971bb10cb218d8`; deleted after merge.
- PR: [#47](https://github.com/cagatayeroglu/KKB-DataTrio/pull/47), `feature/m8-17-multi-result-answer` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `09d1741` (implementation); claim `3b19ddf`.
- Objective: Bind a claim to any of several named results, fault only the numbers resting on a disqualified one, and let `Session.answer` gate over the workspace's current values. The reference scenario's answer is about a table with several columns, not a single figure.
- Implementation: [agent/verifier.py](../src/kkb_agent/agent/verifier.py) gains `verify_claims`, `result_faults` and `_as_named`; `verify_result` becomes `verify_claims` with a single entry, and `gate_answer` accepts one result, a sequence, or a name-to-result mapping. [agent/loop.py](../src/kkb_agent/agent/loop.py) gains `render_results` and gates `Session.answer` over `Workspace.values()` merged with this turn's result.
- Why one result was never enough. The reference scenario's answer is about a **table** — housing credit beside its rate, then a price index added without disturbing either. Gating that against a single result cannot work: the moment a sentence cites two columns, one number is unbound and the sentence is withheld. A test states the removed limitation directly — the same sentence that now passes against the table abstains against either column alone.
- **Disqualification is per result, not per answer.** A broken `konut_faiz` faults exactly the numbers resting on it and leaves a sound `konut_stok` claim standing; the omission reason is prefixed with the column name, because "which column is broken" is the first thing an operator needs and the last thing a flat list of reasons tells them. Only when **every** result is disqualified does the whole draft fall, prose included — which is also what happens when there is one result and it is the broken one, so M8-10's behaviour is preserved exactly rather than special-cased.
- A sentence mixing a sound and a broken column is withheld whole. The gate does not try to salvage half a sentence: the broken half poisons what it shares.
- The workspace supplies the rest of the table. `Session.answer` merges `Workspace.values()` with this turn's result, so a follow-up can speak about columns earlier turns computed. `values()` already excludes stale names, so **a superseded column cannot re-enter an answer through the back door** — tested by staling a rate and asserting the sentence quoting it is refused. Each result reaches the writer under its workspace name, because a writer given two anonymous number lists cannot say which is which.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_multi_result_answer.py` — **17 passed**. `make quick` / `make pr` — **1080 passed / 19.45s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on both changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Three existing tests changed, wording-only: the verdict now says "these results" rather than "this result". No assertion was weakened and no behaviour changed for a single-result caller.
- Limitations: a number matching values in **two** results binds to the first in iteration order and the verdict names which — that is reported, not resolved, and an answer whose columns share a value is inherently ambiguous. The gate still works over whatever the caller hands it; nothing decides *which* columns an answer should be about. `verify` remains reachable for callers holding no typed result. Nothing here recomputes a claim from raw inputs, and no external cross-check exists.
- Blocker: none known in scope.
- Handoff: The reference scenario's shape is now answerable end to end: several columns, one gated answer, stale columns excluded, a broken column reported by name without silencing the rest. The remaining M5-11 acceptance is met. Next in evidence work is **M8-12** — invalidate dependent claims after changed dates or assumptions, which can reuse `AnalyticalResult.digest()` and the workspace's staleness directly. Next in analytics is **M6-02/03**, the change and comparison producers, which give the table something to compare rather than only report.

<a id="m8-10-answer-gate-record"></a>
### M8-10 answer gate record

- Status: DONE — PR #45 merged into `dev` at `bf8bba4bb077ec696f59b4c37dd51fef38480d53`; merged tree equals validated `81ab6e5`.
- Owner: Eray
- Branch: `feature/m8-10-answer-gate`, from `dev` `32ab2f309b47a3b74b782216274fbce009b0a147`; deleted after merge.
- PR: [#45](https://github.com/cagatayeroglu/KKB-DataTrio/pull/45), `feature/m8-10-answer-gate` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `6b5ea54` (implementation); claim `712c8a7`.
- Objective: Put `verify_result` on the path an answer actually takes. Omit sentences carrying unsupported numbers, qualify what survives with the verdict's limitations, and abstain when nothing is presentable. Add the minimum answer assembly the gate needs to be reachable; not a full presentation layer.
- Implementation: [agent/verifier.py](../src/kkb_agent/agent/verifier.py) gains `gate_answer`, `GatedAnswer`, `OmittedSentence` and `AnswerStatus`. [agent/loop.py](../src/kkb_agent/agent/loop.py) gains `Session.answer`, `Session.draft`, `collect_results`, `render_result` and the `Answered` record. **This is the first end-to-end slice**: a question now reaches a gated answer through the real planner, registry, lakehouse tool, typed result and verifier, with only the model scripted.
- Why a gate and not a report. Verification nothing routes through is a report. The decision here is mechanical rather than advisory: a sentence carrying a number the verifier could not support is **withheld**, what survives is **qualified** by the verdict's own limitations, and a draft with nothing left becomes an **abstention** rather than a shorter claim. A shortened claim is the dangerous outcome — it reads as a complete answer.
- The three outcomes are ordered, and the order matters. A result that failed **as a whole** — it established nothing, its evidence does not resolve, its values disagree with the store, its sample floor was missed — takes the entire draft with it, including the unnumbered prose, because that prose describes the same broken result. Only when the result itself is sound does the gate fall back to withholding individual sentences.
- Withholding is recorded, never silent. Each `OmittedSentence` carries its text and the reasons it failed, because an answer that quietly loses a sentence is indistinguishable from one that never made the claim, and the operator has to see the difference.
- What the writer is given. `render_result` hands the model the computed values with their units, scales, periods, sample counts, unresolved semantics and limitations — and **not the rows**. A writer given rows will aggregate them, and a figure it computed itself is exactly what the gate must reject. There is also nothing in that prompt for an injected instruction to travel in. A tested case asserts the synthesis prompt contains the value and no `SELECT`.
- No draft is requested for an analysis that established nothing: a non-COMPUTED result abstains before the provider is called. One scripted response in that test proves the second call never happens.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_answer_gate.py` — **22 passed**. `make quick` / `make pr` — **1040 passed / 17.75s**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on both changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08.
- Limitations: **one result per answer.** `Session.answer` takes the last typed result; choosing among several, or writing an answer spanning them, needs the workspace this loop does not yet hold — that is M5-10/11/12, and taking the last is a stated limitation rather than a selection policy. Sentence splitting is punctuation-based, so an unusual layout could group two claims into one withheld sentence; it withholds too much rather than too little. `verify` remains reachable for callers that have no typed result. Nothing here recomputes a claim from raw inputs, and no external cross-check exists.
- Blocker: none known in scope.
- Handoff: The vertical slice is closed for one tool and one result: question -> plan -> execute -> typed result -> drafted answer -> gate. The next work that raises its value is **M5-10/11/12**, the workspace integration that lets a follow-up reuse prior results and lets an answer span more than one of them; after that, M8-12 stale-result invalidation using `AnalyticalResult.digest()`. M6-02/03 add the second and third producers. Do not extend `gate_answer` into presentation — rendering the omissions and limitations is M10-06/08.

<a id="m8-0607-result-verification-record"></a>
### M8-06/07 result verification record

- Status: M8-06 DONE, M8-07 PARTIAL — PR #44 merged into `dev` at `32ab2f309b47a3b74b782216274fbce009b0a147`; merged tree equals validated `400ad90`. M8-07 stays unchecked because transformation-prerequisite validation is not implemented.
- Owner: Eray (recorded owner of the original M8-07 scope; same owner resumes, so no transfer is needed)
- Branch: `feature/m8-06-07-result-verification`, from `dev` `2060f31bd9422c448c67a7191b59a5be7614d568`
- PR: [#44](https://github.com/cagatayeroglu/KKB-DataTrio/pull/44), `feature/m8-06-07-result-verification` -> `dev`; merged. Draft claim published before implementation; no collision on post-publication remote recheck.
- Commit: `ba922f3` (implementation); claim `efb6b01`.
- Objective: Make the verifier check a claim against a specific `AnalyticalResult` — its own values, periods, units and preserved input references — instead of against any stored value of similar magnitude. Add a store recheck independent of the model's SQL. Not a full proof engine.
- Implementation: [agent/verifier.py](../src/kkb_agent/agent/verifier.py) gains `verify_result` beside the existing `verify`, plus `recheck_against_store` and a `Binding.RESULT`. `NumberVerdict` gains `result_id`, `value_label` and `faults`; `supported` now requires a binding **and** no faults, because finding a match is not the same as the match being presentable.
- The old gate's weakness, stated plainly: `verify` asks "does a number like this exist anywhere in the store?". A figure taken from the wrong series, the wrong period or the wrong scale passes that question. `verify_result` asks whether the number is one **this** result produced. There is deliberately no fallback to a store-wide search — that fallback is the behaviour being replaced — so a number must bind to a result value, to a caller-justified context figure, or be a year.
- Scale contradiction (M8-07). A written scale word next to a figure is compared with the value's recorded `Scale`. `801.438 milyon` against a thousand-scaled value is rejected even though the number is real: this is the BDDK/FinTürk 1000x error surviving into the sentence, where no value-only check can see it. Asserting a scale on a value whose scale the result never established is rejected for the same reason. Whole words only — a suffixed form like `milyonu` is skipped rather than guessed, because failing to check is recoverable and wrongly rejecting a correct answer gets the verifier switched off.
- Period contradiction (M8-07). Years are read from the **sentence** containing the figure, not a character window, so a year in a neighbouring sentence cannot cause a false rejection. A contradiction requires that *every* year in that sentence falls outside the value's period, since a sentence may legitimately name a range beside its own figure.
- Preserved input references (M8-06). `evidence.lineage_node` and every `input_refs` entry are resolved against the database — a known table, or a stored lineage node. An unresolvable reference is rejected, because a dangling reference is worse than an absent one: it renders as provenance while pointing at nothing. This covers M8-04 for this path only; general orphan-evidence rejection remains M8-04.
- Second-path recheck (M8-06). `recheck_against_store` re-reads each value keyed on **series and period** using fixed, code-written SQL, independent of whatever statement the model composed. It catches a wrong join, a wrong period pairing and an altered figure. Its limits are stated in the verdict rather than implied: it is a second *read* of the same store, not an independent derivation, so it cannot catch a value that was stored wrongly. Values with no identity to look up — an aggregate labelled `value` — are skipped rather than guessed at.
- Result-level refusals: a non-COMPUTED result rejects the whole answer and surfaces its own reason, so nothing can be quoted from an analysis that established nothing; an optional `minimum_samples` floor is enforced when a caller states one; declared `unresolved_semantics` reach the verdict's limitations, and a value carrying them faults any number resting on it.
- Tests: PASS (2026-09-10, Python 3.12.2). `pytest -q tests/unit/test_result_verification.py` — **38 passed**. `make quick` / `make pr` — **1017 passed**, Ruff format/lint, Bandit and secret scan clean. Narrow `mypy --follow-imports=silent` on the changed modules PASS; `mypy src` remains **17 errors**, unchanged, all pre-existing under M0-08. The suite includes the discriminating case: a figure that the old `verify` accepts and `verify_result` refuses because it is not in this result.
- Limitations: `verify` is unchanged and still used by the existing end-to-end chain, so the weak gate remains reachable until M8-10 routes answer assembly through the strong one. Unit **text** is not compared — only scale words are, because unit strings are free text and a false rejection is worse than a missing check. Transformation prerequisites are not yet validated: `TransformationRecord`s travel with the evidence but nothing checks that a declared deflation actually ran, so M8-07's transformation half is **not** complete. No external cross-check and no recomputation from raw inputs.
- Blocker: none known in scope.
- Handoff: The strong gate exists but nothing routes through it yet — **M8-10** is the next step: make answer assembly call `verify_result` and omit, qualify or abstain on an unsupported claim. M8-12 (stale evidence after changed dates/assumptions) can now use `AnalyticalResult.digest()`. The transformation half of M8-07 needs M6-13 deflation to exist before there is a prerequisite worth checking; leave M8-07 unchecked until then.

### Verifier record

- Status: PARTIAL — merged numeric matching (#32) extended by result verification (#44), answer gating (#45) and multi-result answers (#47). M8-01/02/07 and complete claim/run/snapshot/recompute acceptance remain; the original #32 narrative/tests below are historical.
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

PRs #32/#44/#45/#47 deliver numeric/result verification and integrated multi-result answer gating. Preserved input-reference resolution and fixed-query store rereads are implemented; independent recomputation, complete source/run/transformation proof, vintage conflicts and dependent-claim invalidation remain. Core EvidenceRecord still defaults to NOT_RUN and permits an absent run. Source ancestry or a matching result digest alone is not complete verification.


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

Status: PARTIAL. M13-01 catalog contract and M13-03 shared normalizer are merged in PRs #57/59; retrieval stages remain unimplemented. Initial hybrid baseline is confirmed by DEC-116 and [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline); DEC-115 and DEC-127 are SUPERSEDED. Only the explicitly triaged queue entries are READY. Embedding availability/use is confirmed; remaining Q-K-05 dimension/prefix/limit answers are dense implementation prerequisites, not a lexical-failure or prior-gain gate. Dedicated reranker capabilities remain unresolved and optional.

## Objective

Let a Turkish financial question find the right series without hard-coded codes, and prove the retrieval works with a measurement rather than an assumption.

## Dependencies

M12 series metadata and M13-01 catalog record for content, M13-03 shared normalization, reviewed aliases/concept families, metadata filters, lexical/BM25 and required Qwen3-Embedding-8B dense retrieval with the retained LanceDB index choice. Real catalog fetching needs M3/M7 and permitted access. The dense path needs bounded M4 transport/account access and remaining Q-K-05 configuration/limit answers; its model/endpoint and baseline use are confirmed by DEC-129/130. Lexical failure or prior measured gain is not a prerequisite for dense use; RRF/reranking are not prerequisites for baseline delivery.

## Tasks

- [x] M13-01 — Status: DONE (merged and validated). Owner: Çağatay; Branch: `feature/m13-01-catalog-record`, from `5d336bd`; PR: [#57](https://github.com/cagatayeroglu/KKB-DataTrio/pull/57), merged into `dev` at `021e9e5`; implementation Commit: `7b072b7300750a4e4e508f8e99714c41ff215bbd`. Define the catalog record: series ID, Turkish title, unit, frequency, source, coverage range and sample values.
  - Evidence: `src/kkb_agent/catalog/records.py` provides `CatalogRecord`, `CatalogStatus`, `CoverageRange`, `SourceGroup` and `AggregationPolicy`, reusing core source/semantic types. Preserves original provider/series IDs, titles/captions, source groups, unknown/archived state, unit/scale, native frequency/weekly anchor, stock-flow/cumulative kind, per-operation permissions, base year, coverage and up to 20 raw scalar samples. JSON round-trip retains null/unknown and numeric strings without normalization or inference.
  - Tests: `pytest -q tests/unit/test_catalog_records.py` **69 PASS / 0.18s**; `make quick` **1364 PASS / 33.92s**; `make pr` **1364 PASS / 32.49s**, Ruff format/lint, Bandit and secret scan clean; JSON schema identity/closed-field check PASS. GitHub final-head `4e6e200` Fast PR **PASS / 1m**; merged tree verified identical.
  - Blocker: none remaining for M13-01. Limitations: declarations are not verified financial semantics or calculation permission; catalog-wide uniqueness and any BDDK composite selector mapping remain adapter/index responsibilities. No normalizer, aliases, BM25, embeddings, vector index, live access or new dependency.
  - Handoff: M13-01 is delivered; M13-03 remains independently READY and unclaimed; catalog/normalizer/alias and transport prerequisites still gate hybrid retrieval. M6-11 remains unclaimed for Eray.
- [ ] M13-02 — Status: BLOCKED for live retrieval on Q-DATA-01/Q-NET-01/02 and the EVDS adapter/parser path; M7-01/02/03/05/06 are delivered for direct GET, while redirect following (M7-04) is absent and all 3xx are rejected. Pull approved EVDS catalog metadata, preserving original IDs, source/vintage, archived and semantic flags; never hard-code runtime series selection.
- [x] M13-03 — Status: DONE (merged and validated). Owner: Çağatay; Branch: `feature/m13-03-turkish-normalizer`, from `7147771`; PR: [#59](https://github.com/cagatayeroglu/KKB-DataTrio/pull/59), merged into `dev` at `dd42cbd`; implementation Commit: `6f78175bc55dec5406de8dcc87c4fdf31bdde844`. Implement one Turkish normalization function — dotted and dotless i, case folding, diacritic removal — and use it for both indexing and querying; add a test that fails if the two paths ever diverge.
  - Evidence: `src/kkb_agent/catalog/normalization.py` provides `normalize_search_text`; `normalize_index_text` and `normalize_query_text` are the same callable. Separate search representation uses NFC, Turkish I folding/casefold, Latin diacritic removal and whitespace/punctuation boundaries. Retains non-Latin text/marks, dashes, percent/slash and numeric dots/commas; never mutates CatalogRecord or source IDs.
  - Tests: `pytest -q tests/unit/test_catalog_normalization.py` **63 PASS / 0.13s**; `make quick` **1427 PASS / 33.44s**; `make pr` **1427 PASS / 32.43s**, Ruff format/lint, Bandit and secret scan clean; diff check PASS. GitHub final-head Fast PR PASS (1m); merged tree equals validated `1145fa3`.
  - Blocker: none remaining for M13-03. Limitations: intentionally lossy search text can collide; matches do not resolve source identity, archived status or financial semantics. No synonyms/aliases, stemming, translation, numeric interpretation, BM25, embeddings, vector index, live calls or new dependency.
  - Handoff: M13-03 is delivered; its task branch has no active implementation claim. M13-08 alias/concept review can now be triaged using the merged M13-01 contract and normalizer; no new task is started or claimed here; M13-04/05 retain alias/content/transport prerequisites. M6-11 remains unclaimed for Eray.
- [ ] M13-04 — Build lexical/BM25 retrieval over normalized, metadata-filtered catalog records after M13-01/03/08. DuckDB FTS is the existing candidate; verify its extension/index requirements without relaxing the hardened lakehouse connection. Any separate index connection design needs task review.
- [ ] M13-05 — Status: BLOCKED on M13-03/08 normalization/alias prerequisites and usable catalog content (M13-01 contract merged in #57), bounded M4 embedding transport/account access and remaining Q-K-05 dimension/prefix/limit answers. Implement required initial dense retrieval with `kkbhackathon2026/Qwen3-Embedding-8B` at `https://mia.csp.kloudeks.com/v1/embeddings` and the retained lightweight LanceDB index choice. DEC-130 confirms baseline use without lexical failure or prior benchmark-gain evidence; measure it alongside the lexical path.
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

- M13-01: Owner Çağatay; branch `feature/m13-01-catalog-record`; PR #57 merged at `021e9e5`; implementation `7b072b7`, final head `4e6e200`; 69 targeted / 1364 unit and Fast PR PASS, as recorded above. Remaining M13 tasks are unclaimed unless their task record or a published PR says otherwise.
- Retrieval benchmark: NOT RUN; executable retrieval stages are not implemented.
- Benchmark: The fifty pairs from M13-09 become a retrieval case set in EVALUATION.
- Known limitations: Embedding model/endpoint availability is confirmed by DEC-129; vector dimension, batch limits, query/passage prefix and dedicated-reranker availability remain unresolved (Q-K-05). A wrong prefix convention can invalidate baseline vectors; no quality/gain/loss is measured yet.
- Previous handoff (historical; current queue controls selection): M13-03, M13-04, M13-08 and M13-09 need no model access; do them first, then measure what the dense half actually adds.

## Handoff notes

Measure both initial retrieval paths and combined candidates on Turkish financial vocabulary. Tune normalizer/aliases and candidate budgets on development cases, preserving the confirmed dense baseline; RRF/reranking still require held-out evidence. Label a failed/unavailable path and any degraded single-path result explicitly rather than calling it a complete hybrid result. A retrieval score is never evidence of correct semantics — the unit and frequency on the record are.
