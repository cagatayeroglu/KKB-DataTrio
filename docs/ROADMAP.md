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

Snapshot: **2026-09-08**, local repository inspection during a documentation-only task. Days below are relative workdays, not confirmed event dates.

| Item | Last verified observation |
| --- | --- |
| Current phase | Day 0 foundation; core implementation in progress |
| Active branch | `feature/day0-core`; remain here for this documentation task |
| Current milestone | M0; partial scaffolding also supports M4, M5, M8, M9 |
| Local branch inventory | `main`, `dev`, `feature/day0-core` exist; remote protection/privacy/CI not verified |
| Baseline before documentation edits | `429ea40` — `Add files via upload`; not validation evidence for untracked Day 0 work |
| Initial drafting worktree | Tracked diff and staging area were empty before the documentation rewrite; this is historical baseline evidence |
| In-progress files | Untracked `src/kkb_agent/core/`, `providers/`, `evaluation/`, `benchmarks/`, and three Day 0 unit-test files |
| Validation baseline | Source/test files inspected, **application tests and lint NOT RUN in this documentation task**; no passing result established for this snapshot |
| Missing foundation artifacts | `.gitignore`, `.env.example`, and `.github/` workflows absent in this checkout |
| Runtime completeness | No implemented ingestion adapter, registry/executor, analytics, safe fetch, verifier, or UI found in the inspected source tree |
| Documentation | Execution system and related documents rewritten; document-only verification recorded under M0-DOC |

**Known blockers:** live Kloudeks integration needs Q-K-01/02/03; live BDDK/EVDS paths need Q-DATA-01 and network rules Q-NET-01/02; demo environment and cache/persistence rules need Q-INFRA-01/02 and Q-DATA-03. Missing answers block their live paths, not synthetic/offline foundation work.

**Major team choices still open:** orchestration framework, analytical engine, frontend framework, exact causality method, provider model, and persistence backend. Router fine-tuning, vector DB, and multi-agent topology remain deferred. See DECISIONS before adopting any of these.

**Completion boundary:** no runtime milestone is marked COMPLETE in this snapshot. Present code is PARTIAL until its targeted validation and acceptance are recorded. Documentation completion does not imply implementation completion.

**Shared-delivery boundary:** the 11 Day 0 files under `src/kkb_agent/core/`, `src/kkb_agent/providers/`, `src/kkb_agent/evaluation/`, `benchmarks/cases/`, and the three new unit tests are local/untracked and excluded from this documentation commit. Their plain-text paths describe this checkout, not files delivered to teammates. A fresh clone does not contain them; obtain them through separately authorized code delivery before resuming tasks that require them.

## Ordered next safe tasks

For a general “continue,” use the first eligible unchecked READY task. This queue points to canonical task checkboxes below; do not maintain a second set of completion boxes here. Recheck actual state and claim the task before starting. A user-specified task overrides this queue.

| Order | Task | Status / start condition | Expected handoff |
| --- | --- | --- | --- |
| 1 | M0-01 | READY — inspect/validate existing Day 0 contracts without redesign | Exact targeted command/result and remaining contract gaps |
| 2 | M4-01 | READY — validate existing non-networking provider stub | Stub behavior and configuration-test evidence; live transport stays blocked |
| 3 | M9-01 | READY — validate existing benchmark schema/fixture file | Schema results; explicitly state runner/scorecard still absent |
| 4 | M0-04 | READY — separate authorized coding task for missing local ignore/config hygiene | Non-secret config documentation and targeted ignore validation |
| 5 | M1-01 | READY — specify ingestion/profile contract and limits, preserving core interfaces | Proposal and testable examples; unresolved engine choice remains open |

READY is checkout-dependent. M0-01, M4-01, and M9-01 require their local Day 0 files and a configured Python >=3.12 development environment. If those files are absent in a teammate's clone, mark that task BLOCKED for missing code delivery and continue with the first independent eligible entry, currently M0-04. Do not mark a validation task complete merely to unblock the queue.

| READY task | Task-specific acceptance |
| --- | --- |
| M0-01 | Existing core unit tests and core/test-file lint pass; record exact commands/results and unresolved gaps; no contract redesign |
| M4-01 | Existing provider unit tests and provider/test-file lint pass; record environment parsing, masked representation, and pending-error coverage; live transport remains blocked |
| M9-01 | Existing evaluation-schema test and evaluation/test-file lint pass; record schema-only validation; do not claim analytical execution or numeric scoring |
| M0-04 | Ignore rules and placeholder-only config exist; safe synthetic checks prove secrets/private/generated paths are ignored and the example remains trackable |
| M1-01 | A reviewed specification covers the listed result fields, unknown semantics, and testable examples; no engine selection or runtime contract change is implied |

No application validation is requested as part of the present documentation-only task. These are handoffs for subsequent work. If a READY task reveals a missing runtime/tooling prerequisite, record it rather than claiming success or installing dependencies without considering the task scope.

# Team Handoff Protocol

## Checkbox and status rules

- `[ ]` means unfinished, whether not started, PARTIAL, or BLOCKED.
- `[x]` means implementation exists **and** relevant targeted validation has passed. For documentation-only work, verify the document change itself.
- Use plain text `Status: READY`, `Status: PARTIAL`, `Status: BLOCKED`, `Status: NOT STARTED`, or `Status: COMPLETE`; never use invented checkbox syntax.
- READY describes a next action with satisfied prerequisites. PARTIAL describes existing work without full acceptance. BLOCKED must name its dependency/question and an unblocking action.
- A file's existence, a test definition, a model protocol, or a desired diagram is not runtime acceptance evidence.
- Mark a milestone COMPLETE only when its in-scope tasks and acceptance criteria pass. Optional/deferred tasks stay unchecked and explicitly scoped out with a reason; do not check them merely because they were cut.

## Claim, work, hand off

1. Read current status and the relevant milestone; check branch/diff and task dependencies.
2. Put the actual owner and active task IDs in that milestone's record. Avoid two teammates editing the same contract at once.
3. Complete one task or coherent group and run the relevant checks from AGENTS.
4. Update **only that milestone's** checkboxes, short evidence, blocker, and next task. Update the top summary only if the phase, critical blocker, or queue changed.
5. If stopping mid-task, keep it unchecked, mark PARTIAL, state what exists, what failed/was not run, and the exact next action.

A good handoff is a few lines, not an essay. PR/commit/benchmark fields can remain `—` until they exist. Do not imply a commit or remote check happened. Link a safe result artifact when available; omit sensitive input content.

On pickup, set Owner, actual Branch, active task ID, and task Status in that record. On stop, set Tests to the exact command/result or NOT RUN with reason, record the blocker (or none), and put the next task ID/start condition in Handoff. Mark local-only work explicitly; a branch name alone does not mean the code was committed or pushed.

Illustrative example only; this is not current project evidence:

```markdown
Completed:
- [x] CSV parser and basic profiling
- [x] Malformed-file negative tests
Evidence:
- Branch: feature/csv-ingestion
- Tests: <exact targeted command> — 14 passed
- PR: #12
Remaining:
- [ ] XLSX multi-sheet handling
- [ ] Size-limit cases
Handoff: CSV result contract is stable. Continue with M1-09 using that contract.
```

## Three-person coordination

Suggested rotating slots, **not assigned teammates**:

| Slot | Primary lane | Review partner | Handoff artifact |
| --- | --- | --- | --- |
| A — data | M1/M2/M3 and extraction inputs to M7 | B for contract changes | Fixtures, contracts, normalization expectations |
| B — runtime | M0/M4/M5 and workspace integration | C for failure cases | Typed plans, tool runs, recoverability behavior |
| C — correctness/demo | M8/M9/M10 and rehearsal coordination | A for numerical oracles | Expected results, scorecard, operator steps |

Everyone contributes to M6/M7/M11 where needed. At each workday's start, spend a few minutes claiming one task per person and identifying dependencies; at stop, leave the short record above. Select actual owners before work. Do not add a meeting/reporting ceremony to every Codex prompt. Shared contracts get one active editor and a named reviewer; other teammates work on independent fixtures or consumers.

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

Status: PARTIAL. Existing tracked package/build/check definitions plus unvalidated, untracked Day 0 core work.

## Objective

Establish a safe, fast baseline and shared contracts that three teammates can extend without losing in-progress work.

## Dependencies

Local checkout and Python >=3.12 for later application validation. No live Kloudeks access is needed for the stub/contracts. Remote changes require explicit authorization.

## Tasks

- [ ] M0-01 — Status: READY. Validate existing core models/interfaces with `tests/unit/test_core_models.py` and touched-code lint; record exact results before marking the scaffold complete.
- [ ] M0-02 — Add targeted coverage for duplicate/self dependencies, invalid outcome combinations, and workspace serialization as needed; keep schema changes distinct from validation-only work.
- [ ] M0-03 — Validate the tracked package smoke test and existing `make quick` baseline; record unavailable tooling/failures honestly.
- [ ] M0-04 — Status: READY. Add local ignore rules for secrets/private data/generated outputs and a placeholder-only `.env.example`; test ignore behavior without real credentials.
- [ ] M0-05 — Reconcile provisional Kloudeks variable names with the stub; label them local conventions until Q-K-01 is answered.
- [ ] M0-06 — Inspect repository privacy, branch protection, and remote CI only in an authorized setup task; local branches alone do not prove remote settings.
- [ ] M0-07 — Add a fast feature-to-dev CI workflow in a later authorized task; no workflow exists in this snapshot.
- [ ] M0-08 — Add the separate manual/release full gate without making it run after every edit.
- [ ] M0-09 — Confirm synthetic/public-safe fixture policy and document where local private inputs may be stored before accepting them.
- [ ] M0-10 — Document an actual successful setup command/result on a teammate's Python >=3.12 environment.
- [ ] M0-11 — Record the validated core contract baseline and named editor/reviewer before shared contract changes.
- [ ] M0-12 — Run the relevant quick checks for ordinary foundation work; boundary/contract modifications follow AGENTS full-gate triggers.
- [ ] M0-13 — Record implementation evidence and the next ready task after validation.
- [x] M0-DOC — Status: COMPLETE (documentation only). Create and verify the living roadmap, handoff protocol, technical plans, decision/question records, and targeted agent workflow.

## Acceptance criteria

A teammate can install the declared development environment, run recorded quick checks without live credentials, locate contract/fixture ownership, and identify the next task. Ignore/config/CI behavior is verified before claiming the repository foundation complete. M0-DOC alone does not satisfy this milestone.

## Evidence / implementation record

- Owner: Unassigned for runtime; Codex completed documentation in this task.
- Branch: `feature/day0-core` (inspected 2026-09-08).
- PR: —
- Commit: The documentation-only revision is discoverable with `git log -1 --format='%h %s' -- docs/ROADMAP.md`; the implementation baseline is `429ea40`, and local Day 0 code remains uncommitted.
- Tests: Application tests/lint NOT RUN in this documentation task. M0-DOC PASS (2026-09-08): documentation diff review, `git diff --check`, local and tracked-tree link/anchor checks, checkbox/task/record checks, and 17 unchanged non-document file hashes. Lightweight checks use Python standard library only; no tooling installed.
- Benchmark: NOT RUN; runner absent.
- Notes: `src/kkb_agent/core/models.py`, `src/kkb_agent/core/interfaces.py`, and `tests/unit/test_core_models.py` exist as untracked Day 0 work. [Makefile](../Makefile) defines `quick`, `pr`, `full`.
- Known limitations: No passing implementation validation established; ignore/config files and CI workflows missing.
- Handoff: Start M0-01 in the originating checkout where its local files exist. In a fresh clone, those tasks are BLOCKED until code delivery; M0-04 is the next independent READY task. Do not redesign contracts or check off Day 0 merely because files exist.

## Handoff notes

Preserve all untracked Day 0 files; they are not part of the documentation delivery. The initial drafting tracked/staged diff was empty. A schema validation task can remain narrow; a later shared contract modification requires the contract gate. Remote Git actions remain separate and explicitly authorized.

M0-01 starting commands for a configured Python >=3.12 development environment (not executed in this documentation task):

```bash
python -m pytest -q tests/unit/test_core_models.py
ruff check src/kkb_agent/core tests/unit/test_core_models.py
```

Record failures/tooling gaps and keep the task unchecked if either command fails. Do not use this small validation-only task to redesign shared contracts.

<a id="m1"></a>
# M1 — Generic data ingestion/profiling

Status: NOT STARTED. A SourceAdapter protocol is present, but no loader/profile implementation is established.

## Objective

Turn supported unfamiliar tables into bounded, profiled data references with explicit semantics and provenance.

## Dependencies

M0 validated contracts for implementation; Q-TEAM-02 for engine dependency selection. Contract examples and synthetic fixture design can proceed before the engine decision. File exposure requires SEC-FILE-01/02.

## Tasks

- [ ] M1-01 — Status: READY. Specify the ingestion/profile result contract: data reference, source reference, columns/types, row count, date/numeric candidates, missingness, and unresolved semantics.
- [ ] M1-02 — Specify extension/MIME/content checks, byte/row/column limits, and storage paths before implementing loaders.
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
- [ ] M1-17 — Run targeted ingestion/profiling tests and touched-code lint; apply the full gate when changing the file boundary.
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
- Notes: Existing SourceAdapter is a protocol, not CSV/XLSX support.
- Known limitations: Engine and parser limits not chosen; no safe file boundary.
- Handoff: M1-01 can specify examples now; implementation follows validated M0 contracts and engine decision.

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
- [ ] M3-15 — Run targeted adapter tests/lint; use network-boundary gate for live transport changes and record separately authorized live smoke results.
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

- [ ] M4-01 — Status: READY. Run existing provider unit tests and touched-code lint; record environment parsing, SecretStr representation, and explicit pending-error behavior.
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
- [ ] M4-13 — Run provider tests/lint and full boundary gate for transport/auth changes; keep live smoke separate from credential-free unit CI.
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
- [ ] M5-17 — Run targeted planner/executor tests/lint and full checks when changing shared planner/executor contracts.
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
- [ ] M7-16 — Run targeted boundary/extraction tests/lint and the full boundary gate; record limits, supported formats, and remaining restrictions.

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
- [ ] M8-15 — Run targeted evidence/verifier tests/lint; apply contract gate when changing shared models.
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

- [ ] M9-01 — Status: READY. Run the existing evaluation-schema test and touched-code lint; record exactly what schema loading validates.
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
- [ ] M11-14 — Prepare `dev -> main` only when explicitly requested; record PR/check status and merge only with separate applicable authorization.
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
