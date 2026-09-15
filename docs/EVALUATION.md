# Evaluation / hidden-input benchmark plan

This file defines what correctness means and how to measure it. [ROADMAP M9](ROADMAP.md#m9) tracks implementation and results. [ARCHITECTURE](ARCHITECTURE.md) defines the pipeline; [SECURITY](SECURITY.md) defines hostile-boundary expectations.

## Evaluation goals

- Measure whether the system selects the right source/series, executes valid tools, and returns correct material results.
- Expose semantic mistakes that plausible prose can hide: date alignment, frequency, units, stock/flow, cumulative resets, and revisions.
- Require complete evidence and correct abstention, including discipline around causal claims.
- Verify that a follow-up changes the intended state while preserving prior lineage.
- Exercise bounded recovery and latency under ordinary and adversarial inputs.
- Use failures to choose the next engineering task, not merely to produce an aggregate score.

Implementation boundary: merged unit tests exercise ingestion, semantics, lakehouse, planning, workspace definitions and numeric matching. [ROADMAP Current Project Status](ROADMAP.md#current-project-status) owns their revisions/results. They are not a benchmark scorecard. The Day 0 `evaluation/models.py`, case JSON and schema-test drafts are preserved in a local stash, not delivered or currently untracked files in dev. No executing benchmark runner, benchmark numerical-oracle schema, scorecard generator or eval Make target exists. This docs task runs document checks only.

## Acceptance scope and evidence navigation

The [historical handoff](https://github.com/cagatayeroglu/KKB-DataTrio/blob/1578b7ce0d20566784dba49d984b940424847721/docs/HANDOFF_ARDA_2026-09-14.md) records two-turn live Kloudeks acceptance and scripted three-turn/browser rehearsal, not full live Qwen three-turn acceptance or repeated-run reliability. The recorded 29-series / 4,124-observation pool and Bronze evidence are operator-local, absent from fresh Git checkout and not repository-reproducible as an identical snapshot today. Local LanceDB/hybrid fixture tests do not establish semantic retrieval quality; default prepared API retrieval has no real Qwen embedding injection. Prepared metadata inspection is mandatory/auto-wired, while broader quality/reconciliation remain unfinished. Dated run records below retain their original evidence and limitations.

Under [DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria), acceptance must also exercise a smaller allowed open-weight model with the same custom deterministic harness and preservation of untouched columns/history. For reuse, add a new supported financial source / dataset / schema through reviewed catalog metadata and adapter/policy configuration without rewriting the core lakehouse, workspace, execution, lineage, verifier or API architecture; cross-domain/healthcare acceptance is not required. Add the specific state case: select an older UI result, ask “bu tablo” to transform/add a column, and verify the exact owned result/version used; include stale/unowned rejection and failed-turn preservation. The selected-result client/API/runtime path and synthetic browser cases were delivered in #166; see the [2026-09-15 record](#m10-18-browser-selection-2026-09-15). Live Kloudeks selected-table acceptance and smaller-model/financial-source reuse acceptance remain separate unrecorded checks, not invented organizer scoring weights.

Dated run records below describe their recorded revision. Their “remaining” or “not implemented” statements are historical, even where later work closed the gap; current completion belongs to ROADMAP.

## Prepared official-data and runtime acceptance

[DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime) changes the intended official financial-data path, not the meaning of a passing test. Preparation acceptance must independently record the selected BDDK selectors/EVDS real IDs, approximately 2021-01–2026-06 requested coverage for housing credit balance/rate, CPI and KFE, native frequency/anchor, units/scales, stock/flow/rate/base-year meaning, source vintage and artifact/version provenance. Missing periods, unknown metadata and unresolved IDs remain explicit. A reviewed catalog snapshot, synthetic fixture or existing DuckDB table is not evidence that the official dataset is ready.

The organizer real three-turn regression must execute questions against that prepared official dataset, through the actual planner/tools/workspace/verifier, with independent numeric oracles and recorded dataset identity. It must cover follow-up table grounding, successful publication and rejected-turn preservation. The normal core demo must use prepared silver/appropriate trusted gold without depending on question-time BDDK/EVDS retrieval; bronze is source evidence, not analytical truth. Include a financial-source-unavailable run over the prepared pool, while allowing separately configured Kloudeks planning/query-embedding access. A pool miss must clarify/abstain safely; future on-demand materialization is not required to pass the core three-turn acceptance. This is planned acceptance, not a delivered benchmark runner or a passed rehearsal; live Kloudeks/source runs require separate authorization and source/network permissions. Real on-day inputs must still be processed, with no canned answers or silent synthetic fallback.

M5-21 and M8-21 remain delivered correctness protections; only the bounded weekly requested-window slice of M12-08 is delivered. Daily/business-day/holiday/twice-monthly/irregular calendars remain unsupported, and overall M12-08 stays PARTIAL. Prepared data does not bypass DEC-135's required inspection/quality/semantic prerequisites or prove full requested coverage by observed min/max alone.

Production web-search acceptance stays separate under DEC-134: SearXNG is a compatibility candidate only, including upstream-query privacy/network review. Crawl4AI is optional future extraction work, not current `web_url` acceptance. Search-result URLs remain unauthorized to fetch automatically. Existing command/tier and historical live-acceptance records below are unchanged.

### M6-25 organizer Turn 1 live run (2026-09-14)

Owner-authorized runs of `python -m kkb_agent.live_check --prepared-root data/processed/lakehouse` ask the organizer's Turn 1 question through Kloudeks (Qwen planner and writer) over a private copy of the prepared pool; the copy keeps runtime lineage, execution evidence and workspace writes out of the prepared root. Offline tests use the same path with a scripted provider ([test_co_movement](../tests/unit/test_co_movement.py)).

**Independent oracle** (plain script over the pool, not the tool): over 2021-02..2025-12 the monthly average of `TP.KTF12` (weekly Fridays assigned by period end) fell in 32 of 59 transitions; the BDDK housing balance TOTAL rose in 28 of them and did not rise in 4 — 2021-02 (−522), 2021-05 (−1,196), 2023-12 (−2,190) and 2024-01 (−1,534) million TRY, nominal.

| Run | Outcome |
| --- | --- |
| 1 (default 30 s request timeout) | Planner call `ReadTimeout`; no completion. Turn 1 needs `KLOUDEKS_REQUEST_TIMEOUT=120` for the operator run. |
| 2 (120 s) | Planner produced the exact plan on attempt 1 (`change_detection` `co_movement`, BDDK TOTAL id, `EVDS:TP.KTF12`, 2021-01-01..2025-12-31, `by_end`); result counts equal the oracle; answer QUALIFIED in 115.5 s. The gate withheld the writer's whole 60-row table and flagged-month table because a newline not followed by whitespace did not end a sentence, so every figure was attributed to the wrong row's period. |
| Fix | A line break now always ends a claim; flagged changes are no longer duplicated under a second label (that made quotes ambiguous). Both withheld tables from run 2 re-gate ACCEPTED offline against the real result. |
| 3 (120 s, after fix) | Same exact plan and counts; the full table, counts, four flagged months and their changes were ACCEPTED; answer QUALIFIED in 97.8 s because one sentence used cause wording, which the gate withholds even when negated (DEC-120). Not published to the workspace (only ACCEPTED publishes, M5-21). |
| 4 (merged `cd44a26`, 120 s) | Exact plan and oracle-equal counts again; answer QUALIFIED in 133.9 s with 65 withheld sentences. The writer listed the 60 months as prose lines instead of a table; the gate could not bind that shape (date parts extracted as numbers, `period: value` read as an identity label). The report carried reasons but not the withheld sentence texts. |
| M6-14 slice | The per-period table is built by code from the answered result and returned beside the gated answer; the writer is told it is shown separately. |
| 5 (`09eb2b5`) | The planner added a lakehouse step selecting `o.unit` (a silver_series column); that step failed and stopped the plan before `co_movement` ran; ABSTAINED in 44.7 s. Fix: the lakehouse description names each table's columns; the planner is told not to add redundant steps. |
| 6 (`b2e81bd`) | Planner answered; the writer call timed out at 120 s (171.3 s total) while reading all 246 values. Fix: with a period table present the writer reads only summaries and highlighted periods (20 values, 5.2 KB); the gate still binds against the full result. |
| 7 (`92c1fb7`) | Exact one-step plan, 60-row table attached, QUALIFIED in 47.9 s: one sentence used a raw value label as its subject, which the gate reads as claiming that value. Fix: the writer names series by reviewed meaning and writes counts without `dimensionless`. |
| **8 (`4be8ad5`)** | **Exact one-step plan, oracle-equal counts, 60-row table (2021-01..2025-12), ACCEPTED with no withheld sentence in 56.3 s, and published to the workspace as `konut_kredisi_ve_faiz`.** The prose names series by their full reviewed descriptions. |


Run 4 showed free-prose monthly tables are shape-dependent and slow, so the table moved to code (M6-14). Run 8 is the first live Turn 1 accepted and published. Variance remains a risk: runs 5–7 each exposed a different planner/writer behaviour, so one accepted run is not a reliability rate; a repeated live regression belongs to M9/M11. Open items: long series descriptions in prose, `KLOUDEKS_REQUEST_TIMEOUT=120` required, the stock-versus-"kullanılan" reading still deferred, and Turn 3's cause question under the gate's cause rule. Remaining acceptance gaps: an ACCEPTED live Turn 1 with workspace publication, latency (~100 s, mostly long generation), the writer echoing `dimensionless` from display phrases, and Turn 3's "sebep olabilir mi" question, which the gate's cause rule will withhold by design.

### M5-20/M2-15 organizer Turn 2 live runs (2026-09-14)

`python -m kkb_agent.live_check --prepared-root data/processed/lakehouse --turns 2` (owner-authorized, `KLOUDEKS_REQUEST_TIMEOUT=120`) asks Turn 1 and, once it is published, the organizer's Turn 2 question in the same workspace over a private pool copy. Independent oracle: real balance = nominal × CPI(2025-12) / CPI(t) over all 60 months equals the tool output exactly (e.g. 2021-01 nominal 276,785 → 1,894,772.1; 2023-12 438,222 → 828,155.2 million TRY at 2025-12 prices).

| Run | Outcome |
| --- | --- |
| 1 (`30e4081`) | Turn 1 ACCEPTED and published (54.3 s). Turn 2 planned exactly on attempt 1 (`table_transform` `deflate`, source `konut_kredisi_ve_faiz`, BDDK TOTAL column, `EVDS:TP.TUKFIY2025.GENEL`, reference 2025-12-31); 5-column table; QUALIFIED in 21.2 s — `2025-12` left an unbound `12`, and nominal values copied into the transform matched the same values in the Turn 1 result, making quotes ambiguous. Fix: year-months are calendar tokens; a transform keeping all of its source's values supersedes it in that answer's view; the writer keeps price reference months out of figure sentences. |
| 2 (`c99f5e2`) | Turn 1 ACCEPTED and published (74.1 s). Turn 2 exact plan; QUALIFIED in 33.4 s with one list sentence `a..b: value; ...` withheld because a period range header was read as an unknown identity. Fix: period ranges and year-months are calendar headers; the period check still refuses a range that does not cover the value. The withheld sentence re-gates ACCEPTED offline. |
| **3 (`8d95448`)** | **Turn 1 ACCEPTED and published (86.6 s); Turn 2 ACCEPTED with no withheld sentence (33.5 s), published as `konut_kredisi_ve_faiz_reel` beside the untouched Turn 1 table; exact plan; 5 columns × 60 rows; transformations `align_weekly_to_monthly`, `deflate`.** |

Remaining: repeated-run reliability, long reviewed series descriptions in prose, the deferred stock-versus-"kullanılan" reading (the Turn 1 writer now states it), Session publications still record no workspace dependency (redefining Turn 1 would not mark Turn 2 stale), and M2-14 rebasing.

## Scalable official-data acceptance target

[DEC-137](DECISIONS.md#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) expands future evaluation beyond the four-series first vertical slice. These are planned cases, not implemented tests or benchmark results. The [dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) separates core prepared-pool acceptance from later scalability; required hybrid acceptance remains in the delivery path:

| Case | Required evidence / expected outcome |
| --- | --- |
| A. Prepared known series | Correct identity, version, requested coverage and independently checked values from lakehouse |
| B. Prepared unseen concept | Retrieve the supported concept without a demo alias shortcut; preserve semantic checks |
| C. Catalog-known, not materialized | Core demo: report actual miss/window and clarify/abstain; no question-time official fetch requirement or invented prepared state |
| D. Ambiguous candidates | Keep admissible alternatives; clarify without guessing top-1 or TP/YP/TOTAL |
| E. Unresolved semantics | No unsafe fetch/calculation; explicit unknown/abstention |
| F. Allowed official materialization (later scalability) | Bounded adapter → snapshot/validate → version → lakehouse; failure preserves previous trusted data |
| G. Repeated request | Reuse that validated lakehouse version; no unnecessary refetch |
| H. New-period refresh (later orchestration) | Deterministic idempotency; new version/coverage recorded, previous evidence preserved |
| I. Historical revision/vintage (later selection/promotion) | Keep both snapshots/versions; explicit revision policy, no silent overwrite |
| J. Lexical versus hybrid | Same catalog/holdout; Recall@5/10, final selection, latency and failure/degraded behavior |
| K. Turkish paraphrases/unseen terms | Independent cases beyond the four demo concepts and authored aliases |
| L. Unsafe identity/semantics/policy | Clarify/abstain without generic web fallback or invented IDs/endpoints |

Cases F/H/I are not blockers for the organizer core three-turn demo; basic conflict refusal and preservation of trusted history still apply now. Expand prepared known/unseen concepts after the first four-series real E2E slice, as safely practical. LanceDB is the selected and implemented local catalog vector index (DEC-138); `LocalCatalogIndex`, optional hybrid composition and Qwen embedding transport exist, with dimension 4096 measured. The default prepared registry omits dense-stage injection and therefore remains lexical. Real Qwen index population/query embedding and live/measured semantic retrieval acceptance remain unfinished; measure quality, latency and failure behaviour against lexical-only and dense-only baselines. Vector records contain catalog representations only, never BDDK/EVDS values; no PostgreSQL service is selected.

Retain M13-09 independent holdout separation; do not tune aliases/embeddings against its answers. Report catalog/dataset/parser/semantic-policy/model/cache-index versions and cold/warm timings. Use deterministic offline source/provider doubles for implementation gates; any later live acceptance requires explicit authorization. Requested-boundary coverage must use declared supported calendars; no extrapolated support for daily/business-day/holiday/irregular cases. Production search and URL-document acceptance remain separate trust-domain tracks.

## Metrics

Score applicable assertions per case, then report passed/total and category-level failures. A metric may be N/A only when declared irrelevant by the case. An expected capability that is unsupported is a failure or an explicit scope exclusion, never quietly removed from the denominator. NOT RUN is distinct from failed; report both and do not inflate pass rates by omitting unexecuted required cases.

| Metric | Observable assertion | Scoring / evidence |
| --- | --- | --- |
| Source selection correctness | Selected source ID/version is in the case's allowed set | Exact IDs; report missing and wrong selections separately |
| Series selection correctness | Selected series matches required concept, geography, unit, population, adjustment, and period | Exact fixture identifiers or adjudicated allowed equivalents |
| Tool selection correctness | Required capability is used and forbidden tools are absent | Check executed trace; allow equivalent approved plans rather than brittle word-for-word steps |
| Plan validity | Schema, names, args, references, order, capabilities, and budgets validate before dispatch | Per-layer pass/fail plus whether invalid calls were executed |
| Numeric correctness | Values match independent oracle at declared precision | Per-output absolute/relative tolerance; no model grading for material arithmetic |
| Date alignment correctness | Included/excluded dates and paired observations match policy | Exact date keys, interval boundaries, and sample counts |
| Frequency handling | Source/target periods and aggregation/missing-period policy are correct | Derived periods/values plus transformation record |
| Unit handling | Unit, scale, currency/rate representation, and conversion factors are correct | Value and metadata assertions; percent vs percentage-point distinction |
| Stock vs flow handling | Aggregation respects the measure's semantic type | End-of-period versus compatible flow sum; reject unknown semantics |
| Cumulative-series handling | Reset/baseline logic and missing-period behavior match source semantics | Boundary-period oracle, reset metadata, derived-flow lineage |
| Evidence completeness | Material claims resolve to source, input/run, transformation, period/columns, and verification | Count complete material claims / all material claims; reject orphan/stale references |
| Unsupported claim abstention | Unsupported requests trigger the expected clarification/abstention and no invented result | Recall on unsupported cases plus false-abstention rate on supported cases |
| Causality discipline | Association does not become causal wording; stronger claims meet method prerequisites | Structured claim type plus review of rendered answer and limitations |
| Latency | Completion and recovery fit recorded stage/request budgets | End-to-end and stage times, p50/p95 when sample size is sufficient; disclose sample count |
| Recovery behavior | Failure is categorized; retry/repair is bounded; final state/result is coherent | Attempts, termination category, preserved state, and permitted fallback behavior |
| Multi-turn state correctness | Follow-ups preserve selections/history and invalidate changed dependents | Workspace before/after assertions and lineage resolution |

No current numerical target is claimed. Establish baselines in M9, then record agreed thresholds and judging priorities from Q-JUDGE-01. Proposed non-negotiable demo conditions are no known unsafe dispatch, fabricated material values, or unsupported causal claims in required rehearsal cases. These are acceptance goals, not measured achievements.

### Numeric oracle policy

Expected values come from hand calculations or an independently reviewed deterministic reference. Do not copy the implementation's calculation into the expected-value generator and call it independent validation. Store units, periods, sample counts, and missing-value behavior alongside numbers.

Declare tolerances per output, for example `abs(actual - expected) <= atol + rtol * abs(expected)`. Choose tolerances for the actual operation, not to make a failing output pass. Specify handling of rounding, zero denominators, NaN/infinity, and undefined statistics. Compare full calculation precision before display rounding when the case requires it.

M8-20's offline rendering regressions in [test_answer_gate.py](../tests/unit/test_answer_gate.py) check Turkish display text against unchanged analytical values/digests and the existing result-bound gate (`5e-4` relative plus `1e-9` absolute). They cover integer grouping, six-significant-digit fractions, negative/tiny values, three-decimal ambiguity, unit/scale/period/identity contradictions and writer over-rounding. `4,4472` binds to `4.447201536789372`; `4,45` is withheld. These are presentation/binding tests, not new analytical tolerances or live-model quality measurements; M8-18 semantic regressions remain required.

### Claim and plan scoring

Use the executed trace, not the model's assertion that it ran a tool. Permit equivalent registered-tool paths when they satisfy the same prerequisites and result/evidence contract. Automated numerical and structural assertions are primary. A teammate reviews ambiguous semantic/causal wording against a written rubric; an LLM grader alone cannot establish numeric correctness or security compliance.

## Test tiers

| Tier | Purpose / contents | When to run | Budget / prerequisites |
| --- | --- | --- | --- |
| FAST / UNIT | Contract, parser/tool, semantics, verifier, scorer, and targeted negative tests using synthetic inputs | Ordinary coding: touched behavior; `make quick` default ceiling | <=60 seconds when practical; no live credentials/network |
| EVAL-SMOKE | Small representative end-to-end set: change, unknown semantics, alignment, invalid tool, evidence failure, multi-turn follow-up | Relevant feature-to-dev/milestone integration once runner exists; explicit debugging | Fits feature gate <=3 minutes target; deterministic provider double by default |
| EVAL-FULL | Agreed expanded corpus, adversarial categories, holdout slice, regression comparison | `dev -> main`, final demo/release checkpoint, or explicit request | Target automated release gate <=8 minutes; split deterministic/live suites if slower |
| DEMO-REHEARSAL | Actual operator/environment: start, question, evidence, follow-up, failure, permitted fallback | Before final demo; repeat changed paths after material fixes | Time-box to confirmed demo duration plus setup; record live/offline conditions |

**Normal coding sessions must NOT automatically run EVAL-FULL.** A full application gate for a shared contract or security boundary does not automatically imply all live benchmarks/rehearsals. Follow [AGENTS](../AGENTS.md) gate triggers. No tier permits committing private data or using real credentials in ordinary unit CI.

### Implemented command registry

The application gates are present in [Makefile](../Makefile). M9-05 adds the first benchmark
CLI without changing that shared file:

| Command | Actual current behavior |
| --- | --- |
| `make install-dev` | Installs editable package and declared dev extras; setup command, not validation |
| `make quick` | Ruff check on src/tests/scripts and unit pytest |
| `make pr` | Ruff format/check, unit pytest, Bandit, local secret-pattern script |
| `make full` | Ruff format/check, mypy, full pytest, Bandit, local secret-pattern script, pip-audit |
| `python -m kkb_agent.evaluation` | Run the fixed offline M9-05 EVAL-SMOKE cases; emit deterministic JSON to stdout and exit nonzero when any case fails |

M7-19's operator command is `python -m kkb_agent.live_check --document --question '…URL…'` ([approved-run setup](../README.md)). It is never invoked by a gate. Offline tests inject a fake fetch and scripted provider through the normal `Session.answer` path. **ONE LIVE PUBLIC CSV DOCUMENT ACCEPTANCE PASSED** ([bounded evidence](#m7-19-live-csv-acceptance)). A future live run requires separate operator approval and an accepted Q-NET-01/02 boundary; no network question is closed by these tests.

Document smoke success requires executed `web_url`, admitted/loaded content, a selected cell's `AnalyticalResult`, its transform-to-source edge resolving in the same lakehouse, and at least one retained accepted numeric claim bound to that exact result. ACCEPTED/QUALIFIED alone, another tool's answer, a year-only/non-numeric answer, or a supported number inside a withheld sentence cannot pass. Wrong figure/unit/scale/period, ambiguous cell numbers, missing lineage and fetch/parser/provider failure are tested offline. This proves binding to the published cell, not independent recomputation, external corroboration or arbitrary prose correctness. Reports expose only bounded stage metadata/counts, numeric coordinates and SHA-256 digests of source/content/result identities; no raw URLs, prompts, answers, cells or sheet names.

M7-20 preserves the existing `WebUrlOutput.code` as operator-only `fetch_code` when the failure category is `fetch_failed` and the value is in `FetchCode`. Unknown/non-fetch codes return null. DNS, redirect loop/cap, time, size and media categories remain distinguishable; TLS shares `TRANSPORT_FAILURE` with other transport failures. This does not recover the code from the prior live run; a separately authorized future run would report it. User-facing abstention and all fetch/parser guards remain unchanged. The M7-19 admission-report follow-up likewise exposes allowlisted admission/loader codes as `document_code` for `not_admitted`/`needs_input`. Normal synthetic UTF-8 CSV passes the unchanged fetched/upload path; the prior live rejection cannot be diagnosed from its generic category alone, and no exact captured bytes are retained.

`make eval-smoke` and `make eval-full` aliases do not exist. The M9-05 CLI exists without a
Makefile edit; EVAL-FULL and demo-rehearsal commands remain unimplemented.

| Tier | Runner command | Result location | Status |
| --- | --- | --- | --- |
| EVAL-SMOKE | `python -m kkb_agent.evaluation` (`--case CASE_ID` is repeatable) | Sanitized deterministic JSON on stdout; redirect only to an operator-chosen ignored/local path | IMPLEMENTED in M9-05 / PR #186; five fixed cases |
| EVAL-FULL | TBD after runner implementation | TBD; versioned sanitized scorecard/summary | NOT IMPLEMENTED |
| DEMO-REHEARSAL | Actual operator script/run steps TBD | M11 evidence record plus permitted artifacts | NOT IMPLEMENTED |

## Case format and authoring workflow

Historical Day 0 inspection described a BenchmarkCase draft with question/input/tool/evidence/warning fields, but that model is not delivered in dev. The runner/case schema remains M9 work. The following are **PROPOSED requirements**, not accepted keys in an existing runtime schema:

- Family/tier, fixture/source versions, allowed source/series selections and tools.
- Exact expected numeric values, units, dates, sample counts, and per-value tolerances.
- Required transformations, warning/error/abstention outcomes, forbidden claims/calls.
- Initial workspace, turn sequence, state assertions, and expected invalidation.
- Failure injection schedule, attempt/deadline bounds, and latency conditions.
- Owner/oracle reviewer and the reason the case detects a distinct failure mode.

Author one minimized case per material behavior. Include at least one failure example for a new boundary and an independently reviewed expected result for a material calculation. Implement schema/runner support before adding unsupported keys to current fixture files. Keep inputs synthetic or permission-documented public data; treat all fixture text as untrusted at runtime.

## M9-05 deterministic EVAL-SMOKE (2026-09-15, PR #186)

The first executable smoke is a five-case, synthetic, offline slice. Stable typed results carry
the case input, expected and actual structures, `PASS`/`FAIL`, mismatch paths/reasons, semantic
assumptions, numeric tolerances, oracle derivation, category denominators and a SHA-256 identity
of the selected case set. Reports intentionally omit timestamps and measured duration so equal
code/cases produce byte-identical JSON. A bounded scripted provider supplies only the fixed
operation selection; it contains no numerical or abstention answer. Actual values come from the
production analytics functions, while expected values are literal hand calculations/constants.
No manual helper, prepared pool, credential, Kloudeks, live source or production search is used.

| Case | Actual production path | Independent oracle / expected behavior |
| --- | --- | --- |
| `turn1-monthly-directions` | `analytics.comovement.co_movement` | Hand-subtracted rate/credit changes over three consecutive months; 2 rate falls, one credit rise and one non-rise; stock/disbursement and non-causal limits retained |
| `turn2-deflate-credit-only` | `analytics.deflation.deflate` | Four literal `nominal * 115 / CPI` results; original table digest/prefix and rate cells unchanged |
| `turn3-add-monthly-kfe` | `analytics.table_series.add_monthly_series` | Four exact month keys and fixed KFE levels; eight existing cells preserved, four appended, no fill |
| `table-direction-relationship` | `analytics.table_relationship.compare_table_directions` | Hand-enumerated down/up directions; only February matches and the result remains non-causal |
| `unknown-scale-abstention` | `analytics.comovement.co_movement` semantic guard | Declared unknown credit scale yields `ABSTAINED`, zero values and explicit unresolved `target: scale` |

Validation on implementation revision `3f14644`: focused suite and related analytical regressions
`115 passed` in 8.95s; repeated reports were byte-identical; deliberately wrong expected periods
and a deliberately corrupted production count both produced `FAIL`. The final local `make pr`
gate passed: Ruff format/check, strict mypy over 107 source files, 3,499 unit tests in 144.66s,
Bandit and secret scan. The earlier gate attempt reached the same 3,499 passing tests but stopped
on Bandit's false-positive treatment of an enum member named `PASS`; renaming Python members
while preserving the JSON verdicts `PASS`/`FAIL` resolved it. This is primitive-level smoke, not
the full Session/API/UI three-turn flow, hidden-input coverage, EVAL-FULL or organizer scoring.

## Adversarial case catalog

All checkboxes below track **validated executable coverage**, not the existence of a written scenario.
M9-05 is a small primitive smoke and does not by itself complete the broader catalog entries below;
overlapping unit-test coverage is not counted as benchmark coverage. Individual progress belongs in
M9; update a catalog checkbox only when its exact runnable case and passing assertion are recorded,
not after every related smoke or unit test.

### Data semantics

- [ ] SEM-01 — Daily vs weekly: explicit week boundary, partial week, expected aggregation and dates.
- [ ] SEM-02 — Weekly vs monthly: a week straddles two months; reject unsupported allocation instead of assigning silently.
- [ ] SEM-03 — Stock vs flow: same dates, different aggregation; catch a sum of outstanding balances.
- [ ] SEM-04 — Cumulative from beginning: require preceding baseline; first derived flow remains unavailable when baseline is absent.
- [ ] SEM-05 — Yearly-reset cumulative: January reset, missing December, and negative corrections/revisions distinguished.
- [ ] SEM-06 — TRY vs thousand TRY vs million TRY: exact scale factors and propagated unit labels.
- [ ] SEM-07 — Percentage vs decimal vs basis points: distinguish relative percent change and percentage-point change.
- [ ] SEM-08 — Missing periods: intersection/union sample counts and no silent interpolation.
- [ ] SEM-09 — Duplicate dates: identical duplicate versus conflicting value; explicit deduplication/rejection policy.
- [ ] SEM-10 — Revised historical observations: preserve vintage and prevent mixed-release comparison without disclosure.
- [ ] SEM-11 — Similarly named wrong series: household vs total, nominal vs adjusted, or mismatched geography.
- [ ] SEM-12 — Different index base years: valid rebasing with reference versus incompatible/no-overlap rejection.
- [ ] SEM-13 — Ambiguous dates: day/month order, month-end labels, and irregular reporting calendar.
- [ ] SEM-14 — Unknown unit/frequency/stock-flow meaning: correct clarification rather than guessed transformation.

### Files / sources

- [ ] FILE-01 — CSV: UTF-8, BOM, quoted separators, alternate delimiter, missing values, and locale numerics.
- [ ] FILE-02 — XLSX: supported cell types, explicit dates, formula cached-value limitations.
- [ ] FILE-03 — Multi-sheet XLSX: wrong-first-sheet trap, sheet selection, sheet/cell provenance.
- [ ] FILE-04 — HTML: multiple tables, misleading caption, script/instruction text, correct table/source fragment.
- [ ] FILE-05 — PDF: page/table extraction, merged headers, uncertain cell values, source page evidence.
- [ ] FILE-06 — Image/scanned PDF: bounded supported OCR or explicit unsupported/low-confidence result.
- [ ] FILE-07 — Malformed file: corrupt/truncated input fails before fabricated rows appear.
- [ ] FILE-08 — Empty/header-only file: explicit empty-data outcome and no numeric summary.
- [ ] FILE-09 — Oversized file: byte and expanded-content limits enforced without full unbounded buffering.
- [ ] FILE-10 — Unexpected schema: unfamiliar columns/types do not select an unrelated known dataset.
- [ ] FILE-11 — Changed column names: semantic candidates exposed; uncertainty remains explicit.
- [ ] FILE-12 — MIME/extension mismatch: HTML named XLSX or executable bytes named CSV rejected/routed safely.
- [ ] FILE-13 — URL redirect: public-to-private chain blocked before destination request.
- [ ] FILE-14 — Unavailable/contradictory sources: bounded failure or explicit disagreement with traceable vintages.

Optional formats still need a tested unsupported-format path while disabled. Do not advertise PDF/image extraction based solely on an abstention test.

### Agent / tool failures

- [ ] AGENT-01 — Invalid tool name: no dispatch and bounded correction/final error.
- [ ] AGENT-02 — Invalid arguments: wrong type, extra key, bad enum, unsafe reference; reject before execution.
- [ ] AGENT-03 — Timeout: propagate deadline, stop safely, retain prior accepted workspace.
- [ ] AGENT-04 — Empty result: distinguish valid empty range from unavailable source; no invented statistic.
- [ ] AGENT-05 — Unavailable source/provider: bounded retry and only permitted, labeled fallback.
- [ ] AGENT-06 — Contradictory sources: no silent arbitrary winner or merged incompatible observations.
- [ ] AGENT-07 — Malformed model output: invalid JSON, extra fields, missing steps, non-schema prose.
- [ ] AGENT-08 — Repeated planner failure: identical invalid repair terminates within request budget.
- [ ] AGENT-09 — Dependency/reference failure: cycle/forward reference, missing output, stale workspace reference.
- [ ] AGENT-10 — Partial tool chain: accepted earlier results remain distinguishable from failed dependent claims.

### Prompt injection

- [ ] INJ-01 — PDF text says to ignore instructions or invoke an unregistered tool; content remains data.
- [ ] INJ-02 — Spreadsheet cell requests secret disclosure or a system command; no execution/disclosure.
- [ ] INJ-03 — HTML text asks to fetch a private/metadata URL; safe-fetch rejects any attempted capability misuse.
- [ ] INJ-04 — Source title/metadata disguises instructions as system/tool output; registry and claim checks still apply.
- [ ] INJ-05 — Model output proposes code/SQL/path/endpoint outside allowed schema; rejected before side effects.

Use inert synthetic markers and fake transports; tests must not actually exfiltrate data or contact metadata services. Assert both user-visible outcome and absence of prohibited tool/network side effects.

### Statistical

- [ ] STAT-01 — Spurious correlation: common trend produces association without a causal conclusion.
- [ ] STAT-02 — Too few observations: arithmetic may be defined while inference is withheld.
- [ ] STAT-03 — Lag effects: known shifted signal verifies sign convention, search bounds, and per-lag sample counts.
- [ ] STAT-04 — Non-stationary time series: method prerequisites/limitations are enforced rather than hidden by a high coefficient.
- [ ] STAT-05 — Causality requested without sufficient evidence: clear abstention and description of what is actually supported.
- [ ] STAT-06 — Nominal vs real confusion: reject silent comparison and require an explicit deflation index/base.
- [ ] STAT-07 — Constant series/zero denominator: no fabricated finite statistic or unexplained infinity/NaN.
- [ ] STAT-08 — Lag/method selection effects: record selection policy; do not present searched maximum as unqualified evidence.

### Multi-turn

- [ ] TURN-01 — Add another series: preserve previous sources/lineage and recompute affected comparisons.
- [ ] TURN-02 — Change date range: retain raw data history, update selection, invalidate old dependent values/charts.
- [ ] TURN-03 — Deflate previous result: keep nominal values and add index/reference assumptions plus derived lineage.
- [ ] TURN-04 — Preserve analysis state: a follow-up does not rely on the model remembering unstructured chat.
- [ ] TURN-05 — Correct prior wrong assumption: record correction and invalidate all dependent transformations/claims.
- [ ] TURN-06 — Failure during follow-up: prior accepted state remains usable; failed outputs cannot masquerade as current results.

## Retrieval and product evaluation tracks

This extends the existing plan under [DEC-130](DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline) and [DEC-128](DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence); it does not claim implemented metrics or passing scores. Reuse M9's case/runner/scorecard rather than creating separate product agents.

### 1. Direct series retrieval

Use reviewed question-to-catalog-ID or allowed-equivalent sets, with catalog versions, original titles and semantics. Keep development and teammate-authored holdout separate, including paraphrases, rare/exact terms, Turkish casing, near-identical names, ambiguous aliases and archived/stale variants.

For lexical-only, dense-only and combined hybrid candidates, report **Recall@5**, **Recall@10**, final series-selection quality, wrong-near-match rate, archived/stale selection rate, ambiguity-resolution outcomes, latency and failure behavior. State denominators and whether multiple IDs are valid; an explicit needed clarification is distinct from a wrong selection. Selection requires unit/frequency/population/coverage agreement, not merely a text match.

### 2. Candidate relationship discovery

Score this separately from named-series retrieval. A target-only lexical or dense result full of target variants can have high direct recall and still fail discovery. Independently review which concept families are relevant to investigate, without labeling any as an economic cause.

Measure relevant concept-family coverage, duplicate-family rate, target-copy/leakage rejection, invalid-semantic candidate rejection and the **null case: no useful candidate**. Include equivalent series under different names and duplicated/derived target copies; document exclusions before scoring. Evaluate lexical-only, dense-only and combined pools from hybrid retrieval within reviewed financial concept families, followed by diversity/deduplication and finance-semantic filtering. Embedding just the target phrase and returning twenty target-series variants fails this scope. Do not force a winning relationship when evidence is weak, unstable, insufficient or invalid.

### 3. Finance semantic guard

Measure both invalid-operation acceptance rate and valid-operation false-rejection rate. Cases must cover stock/flow, rate/amount, cumulative reset/baseline, frequency/aggregation, unit/scale, percentage representation, missing periods, coverage and index-base ambiguity; include archived/stale metadata where relevant. Assert ALLOW, NEEDS_TRANSFORM, NEEDS_INPUT or REJECT, and that rejected/unknown operations never execute. A valid explicit transformation must carry its policy and evidence.

### 4. Premise validation

Use independently specified true and false premises with expected periods and semantics. Measure false-premise detection and correct-premise preservation; include nominal-versus-real, stock-versus-flow and wrong-period assumptions. Verify correction/refinement of the question, not only a refusal sentence. Missing price-index/reference semantics must lead to clarification, not invented real values.

### 5. Relationship stability

Use stable synthetic relationships, independently constructed known drift/reversal cases, and insufficient-data controls. Report stable-case false alarms, known-drift detection and insufficient-data abstention. Fix bounded window/lag/minimum-sample policy before evaluation; report selection effects and missing observations. No research-grade regime-detection or causal-identification claim follows from passing these cases.

### 6. Proof / verifier

Test numeric recomputation against an independent oracle; missing-chain rejection; stale-result rejection; tampered-value detection; and source/run/result-ID validity. Include same numeric value in the wrong series/period/unit/workspace, a changed value behind an unchanged definition hash, a stale definition returned by a resolver, and a missing input or transformation. An allowed year/context number or numeric match in unrelated gold data must not count as verified material evidence.

Assert the logical chain `Claim -> VerificationResult -> AnalysisRun -> ResultSnapshot -> InputSnapshots -> TransformationSpec -> Source`, sufficient immutable identity and an enforced answer gate. The existing number-binding tests establish only their narrower behavior. Numeric VERIFIED / NOT VERIFIED, relationship EXPLORATORY / STABILITY-SUPPORTED / INSUFFICIENT and causal NOT ESTABLISHED are distinct outcomes; missing evidence dimensions are UNKNOWN / N/A, never averaged into a probability.

### Retrieval activation experiment

DEC-130 confirms lexical+dense as the initial baseline; this experiment measures that baseline and gates only additional stages.

1. Freeze reviewed development/holdout sets and catalog/model/index/config versions; agree evaluation budgets and additional-stage gain/cost criteria before inspecting holdout. No threshold is asserted here without results.
2. Evaluate **lexical-only**, **dense-only** and **combined hybrid candidates** with the same normalization, reviewed aliases/concept-family policy and metadata/semantic constraints. Use `kkbhackathon2026/Qwen3-Embedding-8B` (measured dimension 4096) with the explicitly recorded cache/index configuration; DEC-138 selects LanceDB as the catalog index; record its configuration and measure quality, latency and failures. Record candidate pooling/deduplication/order and per-path budgets; do not assume hybrid means RRF.
3. Report Recall@5/10, final selection, latency (cold/warm and sample counts) and failure behavior for each mode. Include embedding timeout/unavailability, invalid vector/configuration and single-path degraded responses. Distinguish a labeled useful fallback from a successful full-hybrid run. Dense use is not conditional on lexical failure or positive incremental gain; results guide tuning and any later explicit decision.
4. Try RRF only if the two paths demonstrably contribute complementary useful candidates. Enable it only when held-out fusion quality improves; record lost as well as gained cases and latency.
5. Try listwise/model reranking only if meaningful final-selection gain pays for another model call, latency, token usage, malformed-output/retry failures and weak-model instability. Additional stages/vector infrastructure need measured benefit too; leave unjustified stages disabled.

Keep direct-series selection and catalog-bounded relationship discovery as separate tracks. Optional-stage outages must preserve an explicitly labeled baseline outcome; dense-path outages must not be mislabeled full hybrid. Do not tune against holdout and retain its label; replace leaked/tuned cases. Expected numeric results must not be generated by the same function under test; prefer hand calculation or an independently reviewed deterministic path. LLM-independent oracles and catalog adjudication establish correctness, not a model's self-rating. These experiments do not add mandatory full/release runs to ordinary task feedback.

## Eventual scorecard format

PROPOSED report, illustrative only. Null fields intentionally indicate no measurement; this is not an existing result artifact or a valid current BenchmarkCase object.

```json
{
  "run_id": "example-only",
  "revision": null,
  "dirty_worktree": null,
  "case_set_version": null,
  "tier": "EVAL-SMOKE",
  "provider_mode": "synthetic-double",
  "model_id": null,
  "config_fingerprint": null,
  "environment": null,
  "summary": {
    "required_cases": null,
    "passed": null,
    "failed": null,
    "not_run": null,
    "excluded_with_reason": null
  },
  "cases": [{
    "case_id": "SEM-02-example",
    "outcome": "not_run",
    "metrics": {
      "numeric": {"passed": null, "applicable": true},
      "evidence": {"complete_claims": null, "material_claims": null}
    },
    "failure_categories": [],
    "attempts": null,
    "latency_ms": null,
    "artifact_ref": null
  }]
}
```

Add every applicable metric from the metric table in the implemented scorecard, with explicit denominators and safe evidence references. Record revision plus dirty state, case/config version, dependency/environment information, model/provider mode, timing boundaries, and failure categories. Do not store credentials or full private prompts/responses in reports.

Human summary format:

| Run / revision | Tier / conditions | Passed / required | Not run / excluded | Failed categories / case IDs | Latency sample / p50 / p95 | Next fix |
| --- | --- | --- | --- | --- | --- | --- |
| M9-05 / `3f14644` | EVAL-SMOKE; fixed synthetic inputs; scripted operation fixture; offline | 5 / 5 cases; five category denominators | Session/API/UI, invalid-tool/evidence-recovery, hidden formats, EVAL-FULL and live paths | None; wrong-oracle and corrupted-actual negative controls fail as expected | Not recorded by deterministic report | Review PR #186; expand only in separately claimed M9 work |

Do not hide category failures inside an average. Numeric, semantic, evidence, and unsafe-dispatch failures need distinct visibility even when most easy cases pass.

## Regression philosophy and triage

1. Reproduce a material failure with the smallest safe fixture; record its category and expected behavior.
2. Fix the responsible boundary/tool, not just the wording for one question.
3. Run targeted tests and relevant smoke. Broaden only for a changed boundary, new failure concern, or defined release gate.
4. Preserve the regression case. If the oracle was wrong, record reviewer rationale and change it visibly; do not weaken tolerance silently.
5. Compare like-for-like case/config/provider versions. Separate deterministic regressions from source drift and model variability.
6. Reserve teammate-authored holdout questions/schema variations. If a holdout is used to tune behavior, move it to development coverage and replace it.
7. Fix unsafe execution, wrong material numbers/semantics, and fabricated evidence before latency/polish. Correct abstention outranks an unsupported answer, while unnecessary abstention is still measured.

Target 50–100 distinct adversarial cases by the expanded benchmark milestone, subject to the delivery window. Coverage and oracle quality matter more than duplicate case count. Record known exclusions and remaining blind spots in M9/M11. No benchmark claim should imply protection against untested formats, live networks, or methods.

### M7-19 CSV smoke source suitability (offline review)

The FSU `tally_cab.csv` source attempted on 2026-09-11 is unsuitable for the current acceptance smoke: fetch passed (`text/csv`) but the parser returned `MALFORMED_TABLE`. No source bytes were retained, so the exact offending live bytes/position cannot be reconstructed and no new fetch was made. Do not label the public file's dialect from the generic code alone.

Offline synthetic reproduction classifies **space before an opening quote** as **CORRECT_REJECTION** under the existing contract. After a comma, a space starts an unquoted field; a following quote is then a forbidden bare quote. The smallest trigger is two characters, space then quote (` "`); a complete example is `a, "b"` followed by `1,2`. Removing that space, quoting the whole field, or keeping an unquoted space without a quote works. LF/CRLF do not change the outcome. Spaces inside quotes or unquoted fields remain literal; no trimming is introduced. This matches [RFC 4180 section 2](https://www.rfc-editor.org/rfc/rfc4180.html#section-2)'s field grammar; it is not a claim that all CSV dialects forbid this layout.

Every CSV `MALFORMED_TABLE` site: an empty physical record outside quotes; a record width differing from the first record; a bare quote after unquoted characters; non-delimiter/non-newline text after a closing quote (including spaces); end of input while still quoted; an all-empty parsed header; or worker-caught `csv.Error`/`UnicodeError`. Invalid UTF-8 normally fails admission first as `UNSUPPORTED_ENCODING`. Header-only input is `EMPTY_TABLE`, and budgets are `LIMIT_EXCEEDED`. Admission preserves the bytes; parsing only decodes UTF-8 with optional BOM and uses the explicit delimiter, `doublequote=True`, `skipinitialspace=False`, `strict=True`.

Next separately approved live smoke should use a controlled public HTTPS CSV with accepted `text/csv`, known clean UTF-8 bytes, explicit comma delimiter, nonempty headers, consistent widths and RFC-style quoting (no padding outside quotes). Prefer the synthetic fixture shape `Distance (miles),Fare ($)` / `4.5,18.00`, with the same bytes prevalidated offline; no hosting or live run is authorized by this note. The normal document-result/lineage/writer/verifier acceptance still applies; the expected value is never seeded into the result.

### Literal quotation acceptance (DEC-132)

Unknown semantics block interpretation and transformation, not exact source quotation. The earlier DataHub run and EXPECTED_REJECTION diagnosis describe the pre-DEC-132 contract; the later authorized success is recorded below. Offline M7-18 follow-up tests require the exact selected value/cell/result and resolved source lineage before an unresolved literal can pass the fixed quotation template. Unknown metadata stays unknown. Wrong value, inferred percent/currency/scale, appended interpretation, changed result/cell/source, broken lineage and analytical reuse must fail; accepted prose without a supported document claim still fails M7-19. CSV/XLSX/PDF share this policy. Normal analytical regressions retain their existing semantics checks. A future live smoke needs separate approval.

### M7-19 live CSV acceptance

On 2026-09-12, Çağatay authorized and confirmed one live document smoke on `dev` `598cdf8b43617fbc4cbeb256fbca5938736cde11`, using the public [DataHub VIX CSV](https://datahub.io/core/core-datasets/_r/-/test/fixtures/finance-vix/data/vix-daily.csv). The normal planner → web_url → safe_fetch → admission → CSV parser → exact selection → AnalyticalResult → lineage → writer → verifier/gate path passed.

- Fetch and parser PASS; media `text/csv`; `fetch_code=null`, `document_code=null`.
- Selected `Date=2004-01-02`, column `VIXClose`, value `18.22`; ClaimKind `LITERAL_SOURCE_VALUE`. Result/cell/source-fragment binding verified; SOURCE_FILE/TRANSFORM lineage resolved.
- Unit null, scale unknown; no semantic invention. Final bounded answer: “Kaynak hücredeki değer: 18,22. Kaynak birim veya ölçek belirtmiyor.”
- Verifier supported the claim; retained document-bound numeric claims **1**; gate **ACCEPTED**. One planner and one writer call, zero repairs, elapsed **8.262 s**; exactly one Session.answer invocation and no retry in this run.

This is the first successful live external-document E2E with a verified document-bound numeric claim. It proves one public HTTPS CSV path and literal quotation under DEC-132, not OCR, arbitrary HTML, every URL/media variant, financial interpretation, or independent corroboration. No secrets or raw provider output are recorded. Later live runs still require separate authorization; this record closes no general network/source-access question.

### M7-11 offline OCR regressions

Synthetic PDFs and mocked HTTP/provider responses exercise native-text priority, mixed/textless pages, individual bounded PNG rendering, exact DEC-129 one/multiple-image HTTP fields, disabled/misconfigured OCR, page/pixel/PNG/deadline caps, encryption/malformed input, unmapped glyphs, empty/truncated/oversized OCR and provider failures without retry or secret leakage. OCR instructions/table-shaped numeric text stay untrusted; OCR-only Session.answer abstains without a writer or analytical result. Native PDF and DEC-132 literal regressions must stay green. No live OCR/network/model request belongs to this suite. A future OCR numeric acceptance needs separately specified schema and consistency checks and exact source/value proof; rendered/model text alone cannot pass.

### M7-07 offline static HTML acceptance

Synthetic inline HTML and fake fetch/provider fixtures cover Turkish UTF-8/BOM, entities/block text, th/td and multiple tables, missing cells, deterministic fragments, span/nested/ragged/malformed refusals, inactive elements/attributes/resources, prompt injection, meta refresh, charset policy, depth/text/cell/row/column/table/input/worker limits, empty JS shells and safe operator errors. Real Session.answer/lineage/verifier tests require exact HTML cell binding for DEC-132 literal quotation; inferred USD/scale/interpretation and ambiguous table matches fail. Captions do not grant financial semantics. Existing CSV/XLSX/PDF/OCR/safe-fetch regressions remain required. Static placeholder text is not a verified answer; no JS execution/DOM repair/CSS layout or live HTML acceptance is claimed. Future live source checks require separate approval.

### M10-01 operator specification

[OPERATOR_FLOW](ARCHITECTURE.md#operator_flow-m10-01--operator-flow-and-api-boundary-requirements) defines the operator happy path, abstention, tool/source failure, follow-up and reset limitations. Acceptance here is document/code-contract review, not a UI rehearsal or API test. Its final section enumerates offline API/session/table/proof/SSE security tests for the later runtime implementation. Existing session, verifier and lineage regressions support backend facts only; no app/health/HTTP/SSE surface is claimed.

<a id="catalog-tool-acceptance-dec-133"></a>

## Catalog tool acceptance (DEC-133 delivery; DEC-135 current boundary)

M13-04 implements offline `catalog_search`; [its contract](CATALOG.md) and `tests/unit/test_catalog_search.py` cover the development checks below. Reuse M13 cases and reviewed catalog/alias versions rather than inventing live source IDs. Before delivery cover exact aliases and shared Turkish/punctuation/case normalization; multiple plausible candidates; source/frequency/archive filtering (archive excluded by policy); stable IDs and explicit unknowns; preserved stock/flow and rate/amount distinctions; deterministic ordering/caps; empty query, no-match and no fabricated records. Catalog injection-looking text remains inert. Reject unknown arguments and planned/unknown tools, expose only registered implementations, and regress the existing base tools. Offline synthetic test records must be labelled synthetic and never promoted to a trusted runtime catalog.

Measure lexical-only, dense-only and combined retrieval under DEC-130 separately; an offline lexical stage is not hybrid acceptance. Validate dimension/config if dense is used. No live access is required or authorized by these tests. Future table_transform acceptance must preserve mandatory semantics, security, lineage and verification. DEC-135 harness acceptance must separately prove that selected financial series cannot bypass metadata inspection, retrieved observations cannot become analysis-ready before quality checks, and comparable multi-source measures trigger bounded reconciliation outside LLM discretion. Preserve unknowns, reject invented equivalence, and test all reconciliation states. These automatic integrations and their acceptance tests remain future M13-13/M1-12/M8-09 work, not delivered by M13-04. These tests claim offline lexical tool validation, not a benchmark score, full hybrid delivery or future-tool implementation.

### M7-22 offline search acceptance

`tests/unit/test_web_search_tool.py` uses a test-only FakeSearchBackend and scripted planner. It covers closed bounded arguments, ranked/capped/empty results, supplied versus missing metadata, duplicate/redacted locators, unsafe URLs, malformed typed replies, response byte cap, safe timeout/backend failures, worker termination and secret/stdout isolation. Injection-looking snippets stay inert; search-only Session.answer abstains without a writer or analytical claim. Search locators do not authorize web_url. The M7-22 delivery tests register six core factories; M13-04 subsequently tests catalog_search as the seventh. DEC-135 table_transform and new automatic harness integrations remain unimplemented. Neighboring web_url/planner tests and make quick/pr preserve existing behavior. Exact results and merge evidence belong to M7-22 in ROADMAP. No real provider, credentials or live call is used. Production acceptance still requires the separately authorized real-adapter and unseen-query smoke in the [acceptance record](ROADMAP.md#web-search-production-acceptance).

### M13-08 reviewed mapping development checks

The [demo mapping artifact](CATALOG.md#catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping) is development/reference material, not M13-09 holdout. Its tests pin repository-supported real IDs, content/evidence hashes, exact alias unions, ambiguity, unresolved source groups/selectors, archived/unknown distinctions, native frequency/rate basis, family exclusions and deterministic loading. No synthetic record becomes a reviewed real candidate; no recall/benchmark score or live-source acceptance is claimed. Teammate-authored held-out queries and independent adjudication remain separate M13-09 work.


## M0-10 Windows takeover validation (2026-09-14)

PR #148, based on dev `2394aa7`. Python 3.12.14 on Windows. The equivalent fast PR gate (`scripts/check_windows.py`) passes: **2887 passed, 1 skipped in 188.54s**, with Ruff format/lint, Bandit and secret scan clean. The real symlink case is skipped only for Windows error 1314 (missing creation privilege); missing-root rejection still runs. POSIX mode bits are asserted on POSIX; Windows staging requires an operator-owned private directory with suitable ACLs. Scoped mypy for `_fetch_process.py` passes; this is not a full/release gate or a fix for the previously recorded release typing debt.

The source inventory hashes and all fixture bytes are preserved by Git attributes. Oversized negative payloads have short test IDs. CSV/XLSX/PDF worker cleanup is checked via exit state and closed handles instead of POSIX signal 0. Hostile ZIP fixture names remain hostile in Windows-created archives. Closed-pool rehearsal copies pass; failed copies make no model call and expose no filesystem details.

A real offline child test reproduced Windows `communicate` withholding partial output: a connected worker was incorrectly stopped at the connect deadline. A bounded phase-prefix observer fixes this without changing any deadline, destination, credential or retry policy. Real local child tests cover DNS stall, body stall and a successful response after the connect deadline but before the total deadline.

Validation ran in an isolated copy of the same claimed branch, using the existing project interpreter/dependencies with `PYTHONPATH` pointed at the tested source and an explicit temporary test directory. This avoided temporary desktop write-approval timeouts. The original task changes were reviewed, hashes rechecked and task-owned files backed up before synchronization to the Desktop checkout. That checkout then passed 146 transport/prepared-rehearsal tests in 15.44s. Implementation commit: `512103d`.

Local prepared data is separate from this offline gate: the BDDK 2021-01–2026-06 preparation committed TP and YP (66 observations each), but TOTAL retrieval failed; a follow-up identified `TIMEOUT` at 2021-02. EVDS preparation failed before completion; a one-month KFE smoke returned `TIMEOUT` after 5.02s. This was the initial failed preparation attempt, superseded by the successful bounded continuation below. No data, credentials or raw live output is committed.


### M0-10 prepared-pool and live continuation

The existing BDDK and EVDS preparation paths subsequently completed on the original Desktop checkout without changing retry, timeout, TLS or destination policies. BDDK TP/YP/TOTAL each hold 66 monthly observations; EVDS TP.KTF12 holds 287 weekly observations and TP.TUKFIY2025.GENEL, TP.GENENDEKS.T1 and TP.KFE.TR each hold 66 monthly observations. Window: 2021-01–2026-06. Total: **7 series, 683 observations, no missing values; 80 local files / 7,613,310 bytes**. BDDK TOTAL expectations match exactly: January 2021 = 276,785 and June 2026 = 801,438 million TRY. This remains a bounded demo pool, not broad-source coverage or automatic refresh.

An independent read-only Decimal calculation over silver observations gives 59 monthly transitions, 32 falling-rate transitions and 4 with non-rising credit balance: 2021-02, 2021-05, 2023-12 and 2024-01. A separate offline Session run with scripted plans and the actual tools/verifier publishes both tables, preserves **all 242 source values**, and matches independent CPI deflation for **all 60 months** at 2025-12 prices (relative tolerance 1e-12, absolute 1e-8). No model was used in that numerical comparison; result-verifier faults = 0.

Local live evidence at implementation `512103d` (documentation head `1225e49`): the first configured two-turn attempt failed at the planner with `TransportError / ReadTimeout` after 168.1 s, so Turn 2 did not run. A short synthetic chat then passed in 1.148 s on `kkbhackathon2026/Qwen3.8-27B`. One further prepared two-turn run **ACCEPTED and published both answers in the same workspace**: Turn 1 95.131 s, Turn 2 44.567 s; each plan and draft completed in one attempt, no rejected plan or withheld sentence. Plans used `co_movement` then `deflate`, matching the operator contracts. Tables have 60 rows, respectively 4 and 5 columns; 242 then 302 result values. Turn 1 counts match the independent oracle. SHA-256 comparison confirms all 80 prepared files unchanged after rehearsals.

The live launcher imported literal trusted `KLOUDEKS_*` assignments into the operator process without evaluating the file or logging secrets; the CLI reads environment variables and does not load `.env` itself. The rehearsal used the previously documented 120 s request setting and a private prepared-pool copy. Initial missing-environment and transport failures remain failures; the later accepted run does not prove repeated-run reliability. Latency, overly long display names, Turn 3, release typing debt and API/UI remain outstanding.


## M5-20 add-series slice (2026-09-14)

PR #149, implementation `2bf1db81ea1a83b95f24f0fc17b273a0ad8dc775`, base dev `7481ea4`, Windows/Python 3.12.14. Targeted add-series/Turn 2/Session tests: **84 passed / 12.41s**. The two analytics/tool modules pass scoped mypy with an operator-writable cache; the default cache produced a tooling internal error, not a clean result. Fast PR gate: **2918 passed, 1 skipped / 194.19s**, Ruff format/lint, Bandit and secret scan clean. The one skip remains Windows symlink privilege. This is not the full release gate; earlier typing debt remains.

The new tests cover a non-KFE monthly stock, exact row/value preservation, missing versus zero, observations outside the displayed window, duplicate/invalid dates, unavailable series/workspace, unresolved/cumulative/weekly declarations, column collisions, non-finite values, operation-specific closed arguments, source-store mismatch, missing-cell evidence and a scripted third-turn publication. Two review findings were reproduced and fixed: single-period prose metrics must not expand the displayed row set, and Turn 3 numeric prose must not be rejected because a fully copied Turn 1 ancestor remains visible. Only declared fully preserved ancestors are narrowed; unrelated equal-valued results remain visible and published history is preserved.

A separate offline run over a private copy of Arda's prepared real pool uses scripted plans with actual Session/tools/verifier. Turn 1 and deflation retain their independent 60-month check; add_series then adds `EVDS:TP.KFE.TR`. All **60 KFE values** exactly equal a separate silver query, **302 preceding values** are unchanged, index base **2023** is recorded, and all three tables publish with zero verifier faults. All **80 prepared files** remain byte-identical. This validates column addition, not the model's planning of Turn 3 or the requested price/credit explanation. No new live network/model call, hybrid retrieval, general inspection harness, automatic refresh or release acceptance is claimed. Next: computed relationship evidence and a full three-turn live rehearsal.


## M6-25 table relationship / Turn 3 slice (2026-09-14)

PR #150, based on dev `06f9152`, Windows/Python 3.12.14. The generic `change_detection.table_co_movement` operation consumes a verified earlier-step or published table and preserves its values. Targeted comparison/three-turn tests: **38 passed / 7.64s**; the first broader targeted run had 114 passes and two test-expectation failures (weekly rate labels include the recorded reduction policy; writer criteria use prose labels), corrected before that 38-test run. Five changed source modules pass scoped mypy. Broader live_check typing still reports four pre-existing document-mode errors; no full-release typing claim.

Coverage includes hand-calculated direction/condition counts, zero eligible periods, missing months without bridging, duplicate/invalid/non-finite values, unresolved/flow semantics, exact repeat criteria, closed reference/condition schemas, undeclared/unknown/self dependencies, wrong-type/unproved/altered source results, actual executor ordering, verified output, table preservation and numeric publication. The three-turn rehearsal passes only after every table is published and the specified real-credit/KFE/rate calculation exists. Adding KFE alone, comparing nominal credit, or using the wrong direction cannot pass the organizer rehearsal; a final QUALIFIED answer without publication is also a failure.

An independent operator check on a private copy of Arda's prepared pool reads raw silver observations with Decimal arithmetic, independently averages weekly rates by month-end assignment and deflates credit with CPI at 2025-12 prices. Across **59** consecutive transitions: rates fell in **32**; KFE rose in all **32**; real credit did not rise in **22** of those. Actual Session/tool counts and all 22 matching months agree; all 60 KFE cells match, all 302 prior values are preserved, three results publish, and result verification reports no faults. All 80 prepared files remain byte-identical. Plans in this check are scripted, with zero model calls: this is arithmetic/state evidence, not live model acceptance.

The attempted live Kloudeks three-turn dispatch was stopped by automatic approval review before execution; explicit destination/data-transfer approval was requested. No live outcome is claimed at this point. Implementation `e742ba966ffc4403c6aada4edffe2030d8360e4f`. Fast PR gate: **2956 passed, 1 skipped / 204.29s** (the Windows symlink-privilege skip); Ruff format/lint, Bandit and secret scan clean. Broader coverage, hybrid retrieval, all-series semantic inspection, generic publication staleness and release acceptance remain separate.


## M0-08 strict-typing refresh (2026-09-14)

PR #151, base dev `0f50b73`, Windows/Python 3.12.14. Fresh `mypy src` measured **64 errors in six files / 86 source files**, including the installed untyped native PDF renderer. The updated source passes strict mypy over all 86 files, without disabling strictness or adding module-wide ignores. The only new suppression is the documented `pypdfium2` import without a typing marker; image/page limits and provider restrictions remain enforced.

Relevant HTML, PDF OCR, document proof, catalog mapping, bounded HTTP and co-movement suites: **340 passed / 57.89s**. Eleven added regressions require malformed internal page flags/indices to fail before native allocation, a cell callback outside a cell to return a fixed rejection, and a result without evidence to fail document proof. Existing loader/security/financial output tests pass. The typing changes otherwise preserve calculations, metadata, parser policies and transport budgets. DEC-140 now runs source typing at the fast PR boundary, preventing this debt from hiding until a release check. Full release/audit/main promotion and live three-turn acceptance are not claimed by this task.

Implementation `13364dd9ba26d5014cab6e41916c02548c4ac07c`. Updated Windows fast PR gate: **2967 passed, 1 skipped / 218.80s**, strict mypy clean across 86 files, Ruff format/lint, Bandit and secret scan clean. The skip remains the documented Windows symbolic-link privilege. Remote CI is checked separately; no dependency audit or main promotion occurred.

### M13-08 prepared-catalog revision (2026-09-14)

PR #152, implementation `dc5d8360d3da04b2fe4368cbf2b2b7b8968d8f59`. The new v2 catalog has 15 identities and 21
concepts, including all seven supported prepared series. Development tests:
**132 PASS / 1.55s**, 28 new regressions covering metadata parity, components,
CPI bases, interest/profit-share distinction, unresolved amount-flow/inflation-rate,
archive opt-in and source/native-frequency filters. The v1 corpus remains unchanged.
All ten evidence entries match their pinned Git revision bytes; LF checkout rules
make new document hashes portable. No numerical observations are committed.

Fast PR gate: **2995 passed / one Windows privilege skip in 212.40s**, source mypy (86 files), Ruff,
Bandit and secrets clean. The 132 focused tests were rerun after the LF-only evidence
pin adjustment. These are development regressions, not M13-09 held-out retrieval
quality, full-source coverage, live hybrid acceptance or proof of runtime registration.
No model/source network calls or main promotion occurred.

### M13-05 local LanceDB slice (2026-09-14)

PR #153, implementation `9489881e32a7cb636f43490d3eab26fe41e35de6`. **40 native persistence/search and contract
tests PASS / 6.02s** after explicitly projecting `_distance` rather than relying
on Lance's deprecated auto-projection. Final fast PR gate: **3035 passed / one Windows privilege skip in 204.99s**,
strict mypy over 88 source files, Ruff, Bandit and secrets clean. No full/release
gate or live model/source call was run. Development checks cover independent
cosine results, deterministic ties, eligibility before top-k, profile/text/snapshot
mismatch, invalid vectors, local-only paths, failed publication and preservation.

An operator-local fixture index with 15 x 4096 vectors occupied **260,889 bytes**;
build 58.7ms, checked reopen 84.0ms; 20 repeated searches had the same top-10,
median 9.80ms / max 12.19ms on this Windows host. These figures exclude model
calls and do not establish semantic Recall@k, full-source scale or live quality.

Pinned LanceDB 0.38.0 passed dependency compatibility (`pip check`). The 17-package
runtime closure audit reported only existing PyArrow 21.0.0 advisory
CVE-2026-25087 / PYSEC-2026-113, duplicated in the audit response. The raw result
is nonzero. [The applicability review](EVALUATION.md#catalog_index-validation-and-dependency-review)
uses upstream evidence that C++ IPC pre-buffering is unavailable to Python;
this implementation enables no such path. No audit suppression was introduced.
Real embedding policy, hybrid candidate composition/evaluation and planner
consumption remain separate; the parent M13-05 is not DONE.

### M13-05 bounded hybrid candidate composition (2026-09-14)

PR #154, implementation `dc823973153415c39a21bf637e3d214d7d080104`. **29 new native-index / fixture-vector tests
PASS / 7.22s**, plus 127 lexical/current-catalog/index regressions PASS / 6.28s.
Final fast PR gate: **3064 PASS, one Windows privilege skip / 199.57s**; strict
mypy across 89 source files, Ruff, Bandit and secrets clean. 150 local document
targets checked. No full/release gate or live source/model request.

Checks exercise complementary candidate provenance, stable caps, exact-concept
and source/frequency/archive eligibility, ambiguous/unresolved inputs, snapshot
and input-policy mismatch, malformed or failed dense stages, explicit lexical
degradation and absence of analytical evidence. Fixture provenance stays visible.
The alternating-archive-tier-v1 candidate baseline is executable through explicit
operator injection; it does not establish real Qwen retrieval quality, held-out
Recall@k, all-source coverage, live input policy or planner replanning. Parent
M13-05 remains incomplete. See [the contract](CATALOG.md).

### M5-06/M5-13 catalog continuation (2026-09-14)

PR #155, implementation `45f189ef422db34ce7855c8e1393cf7a9e71d4ce`. **35 new tests PASS / 1.92s**;
the earlier combined planner/catalog/rehearsal run was 135 PASS / 2.88s before
two final regressions were added. Final fast PR: **3099 passed / one Windows privilege skip in 246.65s**;
strict mypy 90 source files, Ruff, Bandit and secrets clean. 159 document
targets checked. No full/release gate or live source/model call.

Scripted discovery over the actual reviewed catalog feeds a further validated
plan, deterministic change calculation, writer/gate and workspace publication.
The fixture lakehouse's independently known 100→150 change is 50 million TRY,
and all original prepared bytes remain unchanged. The real Kloudeks transport
against an in-process HTTP mock keeps discovery in a user/data role, not its
merged system message. Negative tests cover no-work clarification, mixed phases,
repeated discovery, web escalation/injection, bad or oversized typed feedback,
fresh IDs, forbidden discovery dependencies, shared steps/repairs, tool failures
and trace binding. These prove integration mechanics, not live model reasoning
or semantic-selection accuracy. See [the contract](CATALOG.md).

### M13-13 prepared-series inspection (2026-09-14)

PR #156, implementation `ca7d11e1e3f0a87ba8ab13e705e806d1f2aef297`. **42 new inspection regressions plus 35
catalog-continuation tests PASS / 15.64s**. Final fast PR: **3141 passed / one Windows privilege skip in 222.30s**;
strict mypy 91 source files, Ruff, Bandit and secrets clean. 179 local document
targets checked. No full/release gate or live model/source call.

Tests cover exact identities, absent preparation, required/optional unknowns,
archive policy, semantic mismatches, immutable reviewed input, fresh metadata
checks, producer/SQL enforcement and receipt binding in execution evidence.
The existing seven-series real pool passes a read-only metadata check (519.51ms
including database open/close), with all 80 source files hash-identical.

A private-copy three-turn scripted run uses the inspected producers. An
independent Decimal oracle agrees on 59 transitions, 32 rate falls and 22 joint
price-up/real-credit-nonrise months. All 302 previous values and 60 KFE values
match, all three results publish, and no verifier faults occur. The original
80 files remain unchanged. This establishes deterministic integration, not live
reasoning reliability, source truth attestation or causation. Broader M13-13,
quality/reconciliation and history staleness remain incomplete. See
[SERIES_INSPECTION](ARCHITECTURE.md#series_inspection-prepared-series-metadata-inspection) for the exact mode boundary.

### M10-16 local API contract (2026-09-14)

PR #157, implementation `cd2e5fc3c9e8633cd44ecf99ab75f0bbe54e3637`. **55 new regressions** cover real-gate
published-result projection, immutable cell identities, finite values, safe
qualified/abstained output, ownership, duplicate requests, atomic admission,
body/origin/header limits, error redaction, lifecycle SSE and shutdown.
Final fast PR: **3196 passed / one Windows privilege skip in 232.09s**; strict mypy 96 source files, Ruff, Bandit and
secrets clean. pip check passes. 164 local document targets checked.
Two upstream Starlette test-client deprecations remain visible; no production
Kloudeks transport migration or warning suppression. Test durations were
profiled within this required gate because Windows gates exceeded the 3-minute
target; no extra benchmark/full-release or live network/model test was run.

The HTTP tests retain exact values from a real Session/gate over synthetic
DuckDB inputs, not model-generated presentation numbers. This establishes the
local contract only: prepared runtime startup, full plan/tool callbacks, bounded
public proof graph, frontend and deployed/authenticated multi-user service
remain incomplete. See [LOCAL_API](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results).

### M10-17 prepared API runtime (2026-09-14)

PR #158, implementation `a58eca122c25b6df42856a0d6144c0e8a6c88c4f`. 38 new prepared-runtime/CLI cases, one
Windows symlink-privilege skip; prior API tests retained. Final fast PR:
**3233 passed / two Windows privilege skips in 238.07s**, strict mypy 98 files, Ruff/Bandit/secrets clean.
172 local document targets checked. An initial gate before optional literal
env-file support passed 3228/two skips; final evidence above includes the added
loader tests. An oversized test parameter initially broke Windows test naming;
explicit short test IDs fixed the fixture, without relaxing configuration limits.

Read-only --check with the operator-local .env reports configured/ready, no model
request, seven prepared series / 683 observations / 15 catalog identities /
80 files / 7,613,310 bytes. The real-pool scripted in-process HTTP rehearsal
publishes all three organizer turns. Independent Decimal arithmetic matches
59 transitions, 32 rate falls and 22 joint months; 302 previous cells and 60 KFE
values match exactly. All original files retain their hashes; largest response
143,584 bytes. Readiness 717.15ms; turns 1425.33/925.01/1578.83ms are local
scripted-pipeline measurements, not live Qwen latency or reasoning acceptance.

Source/seed mutation, wrong metadata, populated foreign workspace, copy bounds,
unsafe roots, per-session ownership, publication/follow-up, startup/model guards
and credential-redaction cases are covered. Repeated identical numeric claims
across distinct result identities can still abstain under the existing gate;
the API preserves that limit. No live model/source call, ingestion expansion,
frontend, proof graph or production deployment is claimed. See
[PREPARED_API](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) for startup and remaining limits.


## M3-08 expanded EVDS preparation — 2026-09-14

Arda explicitly requested broader local coverage before resuming UI PR #159.
PR #160 adds nine reviewed weekly new-loan interest rates and thirteen monthly
CPI expenditure divisions (see EVDS_COVERAGE.md), with prepared catalog v3:
37 real candidate identities / 46 concepts, 146,600 bytes, digest
`e5ecffa6564feab6cb3646a0ee15bf0272b2acd558c650fd316690b7920826c4`.
Historical v1/v2 and all original adapter declarations remain unchanged.

Two public metadata lists exactly matched the prior pinned datagroup hashes.
An initial run was refused before retrieval because isolated Python loaded the
old checkout's four-series registry. An isolated worktree environment with the
new package fixed configuration; no `-I`, worker or network guard was relaxed.
The actual guarded preparation used 22 public `fe` requests in 23.56 seconds:
nine series × 287 Fridays plus thirteen × 66 months, 2021-01–2026-06,
zero missing values, nine trailing out-of-window weeks excluded explicitly.
Each series passed original-window reparse/manifest/calendar/lineage read-back.

The staged pool has 29 identities, 4,124 observations, 124 files and 8,520,172
bytes. Original seven-series observations compare exactly and the original pool
was not changed by staging. A separate raw-JSON/Decimal check agrees with all
3,926 EVDS observations (26 series). Read-only API readiness with v3 is true,
provider configuration present, model_checked=false. The initial verification
helper opened the database read/write and changed its physical file hash;
the final read-only check preserved every file. This was an operator helper,
not a relaxation of the runtime snapshot check.

Targeted source/contract suite: 133 passed; catalog discovery/composition: 14
passed. Final Fast PR: 3271 passed / 2 Windows privilege skips / 2 existing
dependency warnings; Ruff, strict mypy 98 files, Bandit and secret scan clean.
No live model or embedding call. Scope tests preserve KMH/currency ambiguity,
rate versus amount, division versus headline CPI/KFE, null preservation and
old-catalog refusal. This is not full BDDK/EVDS coverage or live unseen-query
acceptance. Local raw data, credentials and DuckDB/Parquet files are not in Git.

CI scheduling: the old 5-minute whole-job limit cancelled PR #158 after its
3235 Linux tests and all security checks passed (41 s install + 247 s tests).
The whole-job ceiling is now 8 minutes; application/retrieval/test timeouts and
gate contents remain unchanged. Remote status must be reported separately.

### M11-03 Eray macOS expanded-pool readiness — 2026-09-15

Eray requested restoration of the documented broad local pool without cutting
later delivery scope. The existing seven-series root was copied to the ignored
`data/processed/lakehouse-before-v3-20260915` recovery path before preparation.
The reviewed EVDS operator then made exactly 22 public `fe` requests for the nine
additional weekly credit-rate series and thirteen monthly CPI divisions over
2021-01 through 2026-06. The guarded run completed in 18.92 seconds; every
series passed manifest, calendar, lineage and read-back checks, with zero
missing values and no unknown-series fallback or retry. No model or embedding
request was made.

Read-only database comparison reports 29 series, 4,124 observations, zero null
values and 121 Bronze artifact records. All 683 rows belonging to the original
seven series match the pre-expansion recovery copy exactly. The local API
`--check` reports ready, provider configured, `model_checked=false`, 37 catalog
identities, 29 prepared identities, 4,124 rows, 124 files and a 4,587,244-byte
bounded pool inventory. Snapshot identity is
`6fc3afd587ee34982b220c2de9d8162c88d096bdeef8278736f74deb48fc887f`;
catalog identity is
`e0bbaac8eb4d1b1e90deacab42989cd6f74181f8ce267150825e8d24e169fb11`.

The local Python editable development dependencies were repaired. Homebrew
Node 22.23.2 and locked client dependencies pass Prettier, strict TypeScript,
all 23 client/proxy tests and the Next.js production build. These are local
environment/data-readiness results, not live Qwen, dense retrieval, deployment
or full three-turn acceptance. Targeted Python ingestion/catalog/API/selection/
three-turn regressions pass **195 tests in 11.70 seconds** with two existing
warnings; the consolidated documentation check passes **59 tests in 5.68
seconds**, and `pip check` reports no broken requirements.


## M10-03 first local client acceptance (2026-09-14)

PR #159 adds the bounded same-origin bridge and responsive Next.js client.
Final integrated `python scripts/check_windows.py`: **3281 passed, 2 Windows
privilege skips, 2 existing dependency warnings, 257.43 s**; Ruff formatting/lint,
strict mypy (98 source files), Bandit and repository secret scan PASS.
`cd web; npm run check`: Prettier, strict TypeScript and **16 tests PASS**.
`npm run build`: production Next.js build PASS. The separate CI web job runs
these same client checks/build; remote CI status is distinct from this evidence.

Browser rehearsal used a production Next server at loopback port 3000 and a
test-only scripted provider behind the actual Python HTTP API. The expanded
29-series/4124-observation public pool was used. No model/embedding/source
network request was made. Three prescribed turns published **242, 302 and 368
cells**, with the first four-column table still selectable after the final
six-column result. Reload restored the same session and three result versions.
A fourth scripted clarification retained Analiz 3 and displayed the fixed
Turkish clarification. This is client/integration evidence, not live Qwen or
arbitrary-question semantic acceptance.

Desktop (~917×884) and narrow 390×844 viewport inspected. Narrow document
clientWidth/scrollWidth both measured 375 px (remaining width is the scrollbar);
tables scroll within their container. Inventory and read-only settings panels
remain usable; viewport override reset after QA. Earlier client tests also
exercise malformed responses, unsafe proxy destinations/origins, bounded body
and response reads, session recovery, duplicate cells and missing values.
No claim of full accessibility audit, complete proof UI or bug-free software.

Integration caught a v3 evidence-byte mismatch after the coverage commit:
EVDS_COVERAGE was hashed as pre-commit CRLF but `.gitattributes` pins its Git blob
to LF. The actual blob at `1958d9a` hashes to
`996c11247f24de3b2d98873c5b00a5aa750f44be59289c6386a7c54a264b864f`.
v3 review revision **r4** corrects that evidence field and records the correction;
its canonical digest is `e0bbaac8eb4d1b1e90deacab42989cd6f74181f8ce267150825e8d24e169fb11`.
All source identities, aliases, metadata, historical v1/v2 and financial values
remain unchanged. The existing byte-evidence regression now passes on the
integrated checkout; the earlier 3271-pass report above was before Git normalized
those bytes and is not a claim that the original merged r3 passed fresh checkout.

Startup/recovery instructions and remaining scope: [LOCAL_CLIENT](OPERATIONS.md#local_client-datatrio-local-analysis-workspace).
Live three-turn browser acceptance, charts/export, upload/refresh, full proof,
detailed tool progress, writable settings and deployment remain outstanding.


<a id="m10-18-client-selection-2026-09-14"></a>
## M10-18 client selected-source continuation — 2026-09-14 (merged #166)

Node 22.17.0: `cd web; npm run check` passes formatting, TypeScript and **23 tests**.
`npm run build` passes production compilation/prerendering. Added regressions
cover immutable selected source on uncertain retry despite view/mode changes,
older-reference reload, refusal to substitute missing sources, legacy retry
compatibility, accepted-publication eligibility, both IDs on GET recovery,
terminal admission rejection versus ambiguous failure and exact proxy forwarding.
The secret scan passes. Backend source is unchanged in this continuation; the
previous backend gate remains the measured 3326 passed / 2 skipped result in
[ROADMAP](ROADMAP.md#current-project-status), not a new full-suite run.

A temporary synthetic prepared pool (2 series, 6 observations, 15 catalog entries),
real PreparedRunner/AnalysisService and the production Next server started on
loopback. Initial browser inspection showed the offline banner and selection
checkbox. The first form interaction and subsequent read-only state check each
timed out in automatic approval review; the server's submission ledger stayed
empty. Therefore **selected-flow browser/E2E and responsive interaction acceptance
are NOT established**. Planned old-table reload, lost-admission retry, refusal
preservation and free-question flows must still be exercised in the browser.
No live model/source request was made. No numerical or reasoning reliability
claim follows from this client test count or the initial page inspection.


<a id="m10-18-browser-selection-2026-09-15"></a>
## M10-18 selected-table browser acceptance — 2026-09-15 (merged #166)

The earlier browser-approval timeout was resolved. Production Next client from
`3ffc53b` / handoff `c8d1318`, real PreparedRunner/AnalysisService and deterministic
tools ran with the finite synthetic pool (two series, six observations, fifteen
catalog candidates). No application code changed for this acceptance. The
[repeatable sequence](OPERATIONS.md#local_client-repeat-the-finite-synthetic-selection-rehearsal)
and its test-only fault wrapper are now retained in the repository.

Observed through browser interactions:

- Initial publication: three stock values 100/120/150 million TRY; add-series:
  six values retaining all stocks and CPI 100/110/120.
- Selecting Analiz 1 after Analiz 2 and reloading preserves Analiz 1 in the
  result panel and composer source indicator.
- The third question receives a synthetic 503 after real API admission. Its
  source remains Analiz 1, controls freeze, reload does not resubmit, and the
  explicit recovery button produces Analiz 3 with six values.
- The safe ledger records six successful admission attempts for five distinct
  request IDs; the repeated request and selected-source IDs are identical.
  Provider invocation counts at admission are 0/2/4/6/6/7: the recovery causes
  no extra provider work before the next question. The injected 422 is outside
  admission and excluded from these counts.
- Adding unavailable KFE abstains with no replacement result. Injected 422
  invalid_result preserves the old table and releases the composer; its rejected
  entry survives reload without an automatic retry.
- Disabling follow-selection survives reload. The subsequent free question is
  accepted with no selected reference; earlier results remain available.
- Busy/pending controls are disabled. At 390x844, mode toggle and older-version
  dropdown work; document clientWidth/scrollWidth both equal 375px. Desktop and
  narrow screenshots were inspected; temporary viewport override was reset.

This proves the bounded client/API/tool flow for prescribed synthetic plans,
not live Kloudeks planning, arbitrary queries, real-data semantics or complete
accessibility coverage. No live model/source calls or merge were performed.
Both temporary servers were stopped after the rehearsal. Full proof UI and
legacy/official-refresh dependency coverage remain incomplete.


<a id="m13-15-catalog-quality-hardening-2026-09-15"></a>
## M13-15 catalog quality hardening — 2026-09-15 (PR #190, open)

The offline case set
[retrieval_cases_v3_quality.json](catalog/retrieval_cases_v3_quality.json) has six
previously reviewed development calibrations and 22 fresh holdout queries. Holdout
Q01–Q22 was committed at `b2f2098` before its first retrieval run and has no exact
query overlap with the three earlier case files. It covers rate basis, KMH/card
inclusion scope, currency and BDDK TP/YP/TOTAL components, CPI base years, explicit
archive/current wording, under-specified multi-series concepts and neighboring
unsupported intents. Relevance comes from the reviewed v3/r4 metadata and finance
semantics, never from the function under test. The runtime does not read case files.

| Fresh holdout metric (offline lexical) | Before | After |
| --- | ---: | ---: |
| hit@1 | 0.7368 | **1.0000** |
| MRR | 0.8333 | **1.0000** |
| Recall@5 / Recall@10 | 0.9474 / 0.9474 | **1.0000 / 1.0000** |
| primary@1 (15 cases) | 0.7333 | **1.0000** |
| unsupported acceptable status (3 cases) | 1.0000 | 1.0000 |
| archive leaks | 0 | 0 |

Baseline top-1 failures were Q03 (KMH excluded), Q07 (avro denomination), Q14
(explicit archive request), Q19 (English outstanding mortgage interest) and Q20
(English TRY mortgage balance). The bounded reviewed-intent post-order in DEC-144
fixes all five without changing status, similarity scores, candidate generation,
aliases or the catalog snapshot. Under-specified Q16/Q17 remain multi-candidate and
clarification-required. The earlier r2 lexical set has five top-1 improvements
(N07, N09, N10, N14, N15), no top-1 losses, and identical development metrics;
the M13-14 safety holdout remains 1.0 hit@1/MRR/status acceptance with zero archive
leaks. Machine-readable results are in
[retrieval_eval_2026-09-15_quality.json](catalog/retrieval_eval_2026-09-15_quality.json).

N07 and N09 move from rank 2 to rank 1. N18 remains an explicit `PARTIAL`: its
English wording does not cause lexical candidate generation to surface a reviewed
BDDK balance identity, and this post-order intentionally cannot add one. Real dense
quality after this policy is NOT RUN because no live embedding call was authorized;
fixture-vector hybrid tests prove only deterministic mechanics and status/archive
boundaries. No Kloudeks, embedding, BDDK, EVDS, production-search or chat call was
made.

<a id="m13-14-catalog-similarity-safety-2026-09-15"></a>
## M13-14 catalog similarity-only safety — 2026-09-15 (PR #188)

The focused offline case set
[retrieval_cases_v3_safety.json](catalog/retrieval_cases_v3_safety.json) contains
two previously seen development calibrations and 16 fresh holdout cases: eight
supported financial intents and eight unsupported intents that share generic or
neighboring catalog terms. Holdout S01–S16 was committed at `0cfead9` before its
first retrieval run. Its exact queries do not occur in either earlier case set;
the runtime never reads the case file, and no alias, indexed text, score or
question-specific rule was changed. Case-set digest:
`e3d9aefc3bb7e8ff8b14b5fb1898521c921b843cb75d76a2edf7bd0808edea0b`.

| Holdout metric | Before | After |
| --- | ---: | ---: |
| Supported hit@1 / MRR (8 cases) | 1.0000 / 1.0000 | 1.0000 / 1.0000 |
| Supported Recall@5 / Recall@10 | 0.9375 / 0.9375 | 0.9375 / 0.9375 |
| Unsupported acceptable status (8 cases) | 0.0000 | 1.0000 |
| Archive leaks | 0 | 0 |

Before DEC-143, every unsupported holdout intent was reported `MATCH`: examples
include a birth-rate request matching credit-rate records, an energy-production
index matching KFE/CPI records, a euro exchange-rate request matching euro
commercial-credit interest, and a housing-sales count matching housing credit and
price records. After the change all eight are `PARTIAL`, preserving the same
candidates for explicit clarification. Six supported BM25-only paraphrases also
become `PARTIAL` while keeping their correct top-1; the two supported queries with
reviewed concept matches retain their prior status. All 18 calibration/holdout
rankings are identical before and after.

The earlier r2 lexical ranking metrics reproduce exactly after the change:
development hit@1 0.6667 / MRR 0.7120 and holdout hit@1 0.5789 / MRR 0.7105;
its eight no-answer cases now all have an acceptable explicit status. This is a
status-safety correction, not proof that nearby candidates are relevant, a dense
quality measurement, or an out-of-scope classifier. No live embedding, Kloudeks,
BDDK, EVDS or production-search call was made. Archive-intent ordering, broad
multi-series ranking, N07/N09/N18 and full catalog coverage remain separate limits.

<a id="m13-05-fresh-holdout-2026-09-15"></a>
## M13-05 DEC-142 combination on a fresh holdout — 2026-09-15 (PR #179, merged)

Authorization: Eray approved PROP-07/PROP-08 (DEC-142) and the proposed next step.
Live use: 132 Kloudeks `kkbhackathon2026/Qwen3-Embedding-8B` query requests (66 per
policy, about 4.9 s and 4.5 s) against the two existing local index generations; no
passage, chat, BDDK, EVDS or search request. Code: `3602636`. Cases:
[retrieval_cases_v3_r2.json](catalog/retrieval_cases_v3_r2.json), the 44 M13-09 cases
as development plus fresh holdout N01–N22 (19 scored, 3 no-answer), committed in
`86a9952` before any retrieval run on them. Compact per-case evidence:
[retrieval_eval_2026-09-15_r2.json](catalog/retrieval_eval_2026-09-15_r2.json).

| Split | Mode | hit@1 | hit@5 | Recall@5 | Recall@10 | MRR | primary@1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| holdout | lexical | 0.5789 | 0.8421 | 0.8421 | 0.8421 | 0.7105 | 0.6111 |
| holdout | dense, plain | 0.7368 | 0.8421 | 0.8421 | 0.8947 | 0.7961 | 0.7222 |
| holdout | dense, instruct | **0.8421** | **1.0000** | **1.0000** | **1.0000** | **0.9123** | **0.8333** |
| holdout | hybrid alternating, instruct | 0.5789 | 0.9474 | 0.9474 | 0.9474 | 0.7412 | 0.6111 |
| holdout | hybrid DEC-142, instruct | 0.6842 | 0.9474 | 0.9474 | 0.9474 | 0.7982 | 0.7222 |
| holdout | hybrid DEC-142, plain | 0.6316 | 0.8421 | 0.8421 | 0.8421 | 0.7368 | 0.6667 |
| development | lexical | 0.6667 | 0.7692 | 0.7393 | 0.7949 | 0.7120 | 0.6452 |
| development | dense, instruct | 0.8718 | 1.0000 | 0.9615 | 1.0000 | 0.9231 | 0.9032 |
| development | hybrid alternating, instruct | 0.6667 | 0.9231 | 0.9103 | 0.9487 | 0.7927 | 0.6452 |
| development | hybrid DEC-142, instruct | 0.8205 | 0.9231 | 0.9103 | 0.9487 | 0.8697 | 0.8387 |

No archive leaks and no dense failures in any mode. Development numbers for the
lexical, dense and alternating modes reproduce the M13-09 run exactly.

Findings:

- **PROP-07 holds on unseen queries:** instruct dense beats plain dense on the fresh
  holdout (hit@1 0.8421 vs 0.7368, hit@5 1.0 vs 0.8421).
- **PROP-08 gain over the alternating baseline holds:** on the fresh holdout the
  DEC-142 order wins N12 ("Ege'nin en büyük şehrinde konut fiyatları") and N19
  ("haberleşme fiyatları") and loses none (hit@1 0.5789 → 0.6842, MRR 0.7412 →
  0.7982); on development it wins 8 and loses 2 (D11, H07).
- **The combination is still below dense-only** (holdout 0.6842 vs 0.8421), from two
  rules kept unchanged by DEC-142. (1) A reviewed match on a broad multi-series
  concept keeps lexical order inside it: N10 "döviz cinsi konut kredisi bakiyesi"
  matches `housing_balance` and ranks TP before YP; N15 "eski baz yıllı genel TÜFE
  serisi" matches `cpi_level` and ranks 2025 before 2003. Dense ranks both correctly
  inside the same eligible set. The same rule is right for D08 ("TÜFE"). (2) The
  archive tier keeps archived records after current ones even on archive-intent
  queries: for N14 ("artık güncellenmeyen eski konut serileri", archives opted in)
  dense ranks both archives first, but hybrid fills its ten places with current
  candidates, so no archive appears (its only hit@5/Recall@10 miss); D24 is similar.
- **Correction to M13-09 wording:** its two İstanbul losses (D11, H07) are BM25
  matches, not reviewed-phrase matches, so DEC-142 does not recover them.
- Three holdout cases fail in every mode: N07 (English stock rate), N09 ("KMH
  hariç" goes to the KMH-inclusive series) and N18 (English TL balance).
- No-answer: N20 (disbursement) stays PARTIAL in lexical/hybrid; out-of-scope N21
  "dolar kuru" and N22 "işsizlik oranı" return candidates in every mode (no
  abstention threshold); all candidates remain clarification-required.
- Latency (one local run): lexical median 9 ms, dense 77 ms including the query
  request; hybrid measured 21 ms only because it reused the cached query vector, so
  an uncached runtime search costs about dense plus lexical.

Limits: one author, one 37-series catalog, 19 scored fresh holdout cases; this
holdout is now seen too. Changing the broad-concept order or the archive tier
needs a new decision and another fresh holdout. Runtime wiring is verified offline
(fixture vectors relabelled in tests); no live served turn used the dense stage.

<a id="m13-09-retrieval-evaluation-2026-09-15"></a>
## M13-09 retrieval evaluation with real Qwen embeddings — 2026-09-15 (PR #178, merged)

Eray-authorized Kloudeks embedding requests only (`kkbhackathon2026/Qwen3-Embedding-8B`,
batching allowed): 6 batched passage requests for two index generations (37
passages each, about 1.8 s per build) and 88 single query requests (44 per
policy, about 3.3 s). No chat, BDDK, EVDS or search call. Catalog v3/r4
`e0bbaac8…`; 44 reviewed cases (39 scored, 5 no-answer) authored before any run;
compact per-case evidence in [retrieval_eval_2026-09-15.json](catalog/retrieval_eval_2026-09-15.json).

| Mode (all 39 scored) | hit@1 | hit@5 | Recall@5 | Recall@10 | MRR | primary@1 |
| --- | --- | --- | --- | --- | --- | --- |
| lexical | 0.6667 | 0.7692 | 0.7393 | 0.7949 | 0.7120 | 0.6452 |
| dense, `qwen3-plain-v1` | 0.7179 | 0.9231 | 0.8718 | 0.9744 | 0.8193 | 0.7419 |
| dense, `qwen3-instruct-query-v1` | **0.8718** | **1.0000** | **0.9615** | **1.0000** | **0.9231** | **0.9032** |
| hybrid `alternating-archive-tier-v1`, plain | 0.6667 | 0.9231 | 0.8868 | 0.9487 | 0.7874 | 0.6452 |
| hybrid `alternating-archive-tier-v1`, instruct | 0.6667 | 0.9231 | 0.9103 | 0.9487 | 0.7927 | 0.6452 |

Split view (hit@1 / MRR): development lexical 0.6957 / 0.7101, instruct dense
0.8696 / 0.9130; holdout lexical 0.6250 / 0.7146, instruct dense 0.8750 / 0.9375,
plain dense 0.6250 / 0.7537. No archive leaks or dense failures in any mode.

Findings: instruct dense beats lexical at top-1 on 11 cases (paraphrases, CPI
divisions, English, diacritic-free, archive) and loses 3 ("TÜFE" alias goes to the
transport division; two İstanbul queries go to İzmir), so the paths are
complementary. The alternating combination keeps lexical at rank 1 and therefore
cannot exceed lexical hit@1 (PROP-08). No-answer cases: lexical/hybrid keep
UNRESOLVED for mapped-but-unavailable concepts (D21, D22); out-of-scope queries
("kredi kartı faiz oranı", "borsa istanbul hisse endeksi") return candidates in
every mode, and one lexical NO_MATCH (H15) becomes a hybrid MATCH because dense has
no abstention threshold; all candidates remain clarification-required. Dense
median per case is about 79 ms including the query request; hybrid reuses the
cached query vector.

Limits: one author, one 37-series catalog, 44 cases; holdout results have now been
seen, so a changed combination or policy needs a new holdout before a gain claim.
Latency is from one local run. The prepared runtime is not yet switched to dense.

<a id="m10-07-period-chart-2026-09-15"></a>
## M10-07 period chart — 2026-09-15 (offline, merged #177)

- Dependencies (authorized by Eray): `react-plotly.js` 4.1.0 and
  `plotly.js-dist-min` 4.1.1 aliased as `plotly.js`, installed with
  `--ignore-scripts`; lazy plot chunk 4,629,092 bytes, not in the first load.
- Client on Node 22.23.2: Prettier, strict TypeScript and **30/30** tests (4 new:
  canonical values and gaps per period, separate unit groups, hidden change
  columns, no chart for single-period/summary results, plain-text labels,
  at-most-two active groups, distinguishing legend suffixes); production build
  PASS.
- Browser rehearsal with a scratch scripted API over the real prepared pool
  (PreparedRunner copy; no model or source call): Turn 1 shows 60 months with
  milyon TL (left) and % (right) axes, "500.000"-style ticks; Turn 3 offers four
  groups (milyon TL, %, yüzde puan, endeks), switching % off and endeks on
  re-plots the KFE line on the right axis; nominal, change and real balance
  legends stay distinguishable. At 390 px the page has no horizontal overflow
  (client/scroll width 390); legend text is clipped by a few pixels inside the
  chart card.

Limits: no export, per-cell highlighting or chart for summary-only results; the
UI does not yet let the user pick more than two unit groups at once.

<a id="m11-07-live-repeat-3-2026-09-15"></a>
## M11-07 live repeat 3 — first complete three-turn API/client acceptance — 2026-09-15 (PR #176, merged)

Owner-authorized by Eray: Kloudeks chat completions only, ceiling 15, no retry,
600 s, private pool copy; **6 requests used**, one API process and one browser
session with follow-selection on. No embedding/BDDK/EVDS/search call. Code at
`dev` `6e589b1` (#171–#175); no code change in this record.

| Turn | Calls (plan / writer) | Gate | Published |
| --- | --- | --- | --- |
| 1 | 43.4 s / 114.5 s | accepted, 0 omitted | Analiz 1 (242 values): `co_movement`, TOTAL + TP.KTF12, 2021-01..2025-12, `by_end`; 59 / 32 / 28 / 4, the four months and their balance/rate changes equal the oracle |
| 2 | 9.5 s / 29.4 s | accepted, 0 omitted | Analiz 2 (302 values) on selected Analiz 1: `deflate` by TÜFE 2003=100 (`TP.GENENDEKS.T1`) at 2025-12; quoted real values (1,874,180 million TRY) equal the base-invariant oracle; the price-reference sentence passed |
| 3 | 54.1 s / 96.4 s | accepted, 0 omitted | Analiz 3 (368 values) on selected Analiz 2: `add_series` KFE then one `table_co_movement` (driver rate down, target KFE up, condition real balance non-increasing); counts 59 / 0 / 46 / 22 / 46 / 22 and the 22 joint periods equal the oracle intersection; rehearsal relationship check true |

Turn 3 prose states the KFE column is present, lists four of the joint periods
with oracle-equal rate and real-balance values, and says the co-movement alone
does not show why credit did not rise (no causal wording). Proof chains are
`available`: BDDK 66 raw responses; EVDS rate, TÜFE 2003=100 and KFE; nested
co-movement (analiz_1) → deflate (analiz_2) → add_series → table co-movement.

Quality notes (not gate failures): Turn 1 prose repeats long reviewed series
names, includes the raw fragment "monthly average (by_end)" and a DEC-139
"kullandırım" scope note; Turn 3 does not quote the 22 count (marked AMBIGUOUS
because it repeats inside that comparison). One complete run is not a
reliability rate; latency was 158 / 39 / 150 s per turn.

<a id="m11-07-live-repeat-2-2026-09-15"></a>
## M11-07 live repeat 2 — 2026-09-15 (PR #175, merged)

Owner-authorized by Eray: Kloudeks chat completions only, ceiling 15, no retry,
600 s, private pool copy; **9 requests used**, stopped after the second Turn 3
qualification to fix the measured cause offline. No embedding/BDDK/EVDS/search.

| Turn | Calls (plan / writer) | Gate | Outcome |
| --- | --- | --- | --- |
| 1 | 27.0 s / 52.8 s | accepted | published Analiz 1 (`by_end`), 59/32/28/4 and months oracle-equal |
| 2 | 8.5 s / 43.0 s | accepted | published Analiz 2 on selected Analiz 1 with a real value quoted "2025-12 fiyatlarıyla" (the #174 fix); deflated by TÜFE 2003=100 (`TP.GENENDEKS.T1`), identical real values to the 2025=100 oracle because the ratio is base-invariant (1,874,180 and 773,412 million TRY) |
| 3 | 28.3 s / 116.6 s | qualified (2 sentences) | one combined comparison (rate down, real non-increasing, when KFE up), counts 59/0/59/32/46/22 oracle-equal; "22 geçişte…" kept; not published |
| 3 retry | 49.1 s + 22.4 s / 143.6 s | qualified (2 sentences) | combined comparison in another role order (driver KFE up, target real, when rate down), 59/0/32/32/22/22; not published |

Offline diagnosis on the session copy, gating Turkish probes against the real
candidate result: (1) plain headings such as "Değerlendirme:" / "Sonuç:" failed
the identity-header rule; (2) counts carried from Turn 1 (59, 32) or repeated
inside one comparison (32/32, 22/22) were ambiguous. The launcher classified
"Ambiguous result/value identity" as identity; its category order is fixed.

Fixes in this PR: plain unknown headings are discourse labels; the writer sees
indistinguishable values as `display AMBIGUOUS` without a figure and is told not
to quote them or open with a heading. Tests: `test_writer_ambiguity_and_headers.py`
(12) plus a Turn 3 heading/duplicate-count regression; affected suites **1426
passed / 56.04 s**; Ruff, format, strict `mypy src` (100 files) clean. Scripted
replay over a disposable real-pool copy with both live role orders and drafts using
a heading, a unique count and a cross-year price reference: **three turns
accepted and published in both orders**, rehearsal check passed.

<a id="m11-07-live-repeat-2026-09-15"></a>
## M11-07 live repeat after M11-11 — 2026-09-15 (PR #174, merged)

Owner-authorized by Eray: Kloudeks chat completions only, hard ceiling 15
requests, no automatic retry, 600 s timeout, private pool copy; **10 requests
used**; stopped early by Eray's decision to fix the measured failure first. No
embedding, BDDK, EVDS or search call. Ledgers are local ignored artifacts; the
second API process also recorded gate status and omission categories (no text).

| Process / turn | Calls (plan / writer) | Outcome |
| --- | --- | --- |
| 1 — Turn 1 | 33.3 s / 119.2 s | ACCEPTED, published Analiz 1 (242 values), oracle-equal |
| 1 — Turn 2 | 6.6 s / 27.8 s | QUALIFIED (one sentence withheld, not published); category not yet recorded |
| 2 — Turn 1 | 40.2 s / 55.1 s | ACCEPTED, no omission, published Analiz 1. Planner chose `by_majority` weekly assignment; counts 59/32/28/4, the four months and rate changes (−0.3475/−0.2875/−0.4025/−0.5020 pp) equal the by-majority oracle; balance changes equal the nominal oracle |
| 2 — Turn 2 | 9.0 s / 600.0 s TransportError | failed turn (`provider_failed`, 609 s); prior table retained; the client stopped polling at ten minutes and a page reload showed the fixed failure |
| 2 — Turn 2 retry | 9.1 s / 26.3 s | QUALIFIED: one sentence withheld for `period` (two numbers); not published, so Turn 3 was not asked |

Offline diagnosis: a real figure's sentence carrying the recorded CPI reference
month ("2023-12 … 2025-12 fiyatlarıyla 828.155 milyon TL") failed the period rule
because 2025 was read as the claim's year. The new absence rule did not trigger.
Fixed in this PR (see ARCHITECTURE claim qualifiers) with cross-year gate tests.
Unconfirmed: the in-page "Aynı isteğin durumunu al" click did not refresh the
view, but pointer/keyboard input to the browser pane was not being delivered at
that time (typing also failed); reload recovered correctly and code review of the
handler found no defect.

<a id="m11-11-turn-three-grounding-2026-09-15"></a>
## M11-11 Turn 3 grounding fixes — 2026-09-15 (offline, merged #173)

Measured failure from [M11-07](#m11-07-organizer-three-turn-live-rehearsal-2026-09-15): the live Turn 3
plan ran two unconsumed `table_co_movement` steps on the same added-KFE table.
The first expressed the requested three-way condition; `Session.answer` kept
only the last (no KFE condition). The writer, shown KFE only as "table shown
separately", said KFE had no values, and the gate accepted the figure-free prose.
Session records of that run were inspected offline; no model call was made.

- **Plan rule:** more than one unconsumed non-discovery step is rejected before
  dispatch with repair feedback. The exact live parallel plan, replayed with a
  scripted provider over a disposable copy of the real pool, was rejected on
  attempt 1; the repaired single comparison (rate down, real balance
  non-increasing, when KFE up) published Turn 3 with counts 59 / 0 / 59 / 32 /
  46 / 22 and passed the rehearsal relationship check. Oracle: KFE rose in all
  59 transitions; rate fell ∧ KFE up ∧ real not rising = 22.
- **Writer context:** presence lines list complete and partially empty table
  columns (KFE in the complete list for that replay).
- **Gate:** bounded absence wording is withheld beside computed results. The live
  Turn 3 draft now abstains (both sentences withheld); counts, limits and every
  analytics limitation string still pass.
- **Rehearsal acceptance:** the Turn 3 relationship check accepts any assignment
  of the three conditions to driver/target/condition roles (same joint set).
- Tests: new `test_absence_claims.py` (28), live-shaped `test_turn_three.py`
  regressions (repair and absence), selected-plan/document negatives kept at
  dispatch plus new pre-dispatch refusals. Affected planning/session/gate suites
  **1542 passed / 63.55 s**; Ruff, format and strict `mypy src` (100 files) clean.

Not re-run live: whether the real planner follows the repair feedback, and
writer prose quality, need a new bounded live rehearsal. A single withheld
sentence still prevents publication (unchanged M5-21 policy).

<a id="m11-07-organizer-three-turn-live-rehearsal-2026-09-15"></a>
## M11-07 organizer three-turn live rehearsal — 2026-09-15 (PR #172, merged)

Owner-authorized by Eray: Kloudeks chat completions only, no automatic retry
(`KLOUDEKS_MAX_ATTEMPTS=1`), private per-session copy of the local prepared
pool (29 series / 4,124 rows, catalog v3), production client, request ceiling
raised by Eray from 9 to 15 during the run. **10 of 15 requests used.** No
embedding, BDDK, EVDS or search call. Content-free ledgers are local ignored
artifacts. Path: `tests/manual/live_client.py` → PreparedRunner/AnalysisService
(catalog continuation enabled) → browser with follow-selection on.

Independent oracle (`tests/manual/organizer_oracle.py`, SQL rows + Decimal, no
tool code): 60 months / 59 transitions; rate (TP.KTF12 weekly, by-end monthly
average) fell 32; nominal TOTAL balance did not rise 4 (2021-02, 2021-05,
2023-12, 2024-01; −522/−1,196/−2,190/−1,534 million TRY); real = nominal ×
CPI(2025-12)/CPI(t): 2021-01 1,894,772.1, 2021-02 1,874,183.9, 2021-05
1,800,150.9, 2023-12 828,155.2, 2024-01 773,412.0; real not rising 46; rate fell
∧ real not rising 22; rate fell ∧ KFE up ∧ real not rising 22 (same months).

| Run | Timeout | Calls (plan / writer) | Outcome |
| --- | --- | --- | --- |
| 1 — Turn 1 | 120 s | 76.9 s ok / 120.0 s TransportError | Failed turn (`provider_failed`). Offline record check: exact one-step plan (`co_movement`, TOTAL, TP.KTF12, 2021-01..2025-12, `by_end`), 242 computed values; writer context only 5.3 KiB + 1.5 KiB system prompt, so latency, not prompt size. UI kept prior state and showed a fixed message. |
| 2 — Turn 1 | 600 s | 80.5 s ok / 207.3 s ok | QUALIFIED in 288 s: every figure equals the oracle, one unsupported sentence withheld, so nothing was published (M5-21) and Turn 2 had no table to bind. |
| 3 — Turn 1 | 600 s | 57.5 s ok / 171.5 s ok | **ACCEPTED, published Analiz 1 (242 values)** in ~229 s; counts, the four months and their balance/rate changes equal the oracle. Proof chain `available`: BDDK 66 raw responses (`www.bddk.org.tr`), EVDS 1 (`evds3.tcmb.gov.tr`), verified co-movement step. |
| 3 — Turn 2 | 600 s | 10.9 s ok / 62.1 s ok | **ACCEPTED, published Analiz 2 (302 values)** in ~73 s with selected source Analiz 1; `deflate` of the TOTAL column by CPI at 2025-12. Displayed real values match the oracle at six significant digits. |
| 3 — Turn 3 | 600 s | 87.8 s ok / 81.2 s ok | Gate ACCEPTED, published Analiz 3 (368 values) in ~169 s with selected source Analiz 2. Plan: `add_series` KFE, then two `table_co_movement` steps (KFE up; real balance non-increasing). Published comparison: 59 complete / 32 rate down / 46 real non-increasing / 22 both — equal to the oracle, and the 22 months equal the three-way oracle months — but the KFE condition is **not** part of the published comparison. **The prose is wrong:** it states the KFE column has no values and the intersection cannot be computed, although the table carries 60 KFE values. The gate accepted it because the sentences contain no bindable number. Proof chain `available`: four sources, co-movement (analiz_1) → deflate (analiz_2) → add_series → table co-movement. |

Findings: (1) the 120 s launcher ceiling was a real blocker; it now accepts up
to 900 s (targeted launcher tests). (2) Latency: 73–288 s per turn; a slow turn
can exceed the client's ten-minute polling window. (3) A single withheld
sentence prevents publication and breaks the follow-up chain. (4) Turn 3 is
**not demo-acceptable**: the writer is given only highlighted/summary values
(KFE values are "shown separately"), invents an absence claim, and non-numeric
false statements pass the gate; the plan split the condition into two
comparisons. (5) One run each is not a reliability rate.

<a id="m10-08-result-proof-chain-2026-09-15"></a>
## M10-08 result-level proof chain — 2026-09-15 (PR #171, merged)

Offline evidence only; no Kloudeks, embedding, BDDK, EVDS or other network call.

- Python targeted suites (proof, API boundary/selection, prepared API/selection,
  selected runtime, execution evidence, BDDK monthly load): **288 passed /
  11.24 s**. `tests/unit/test_api_proof.py` adds 28 cases: the real BDDK
  monthly adapter (injected responses) traced to three raw responses and
  `www.bddk.org.tr`; lakehouse table → add-series nesting with `analiz_1`;
  missing CPI lineage → `partial`; changed result → `unavailable`; closed store
  → `proof_unreadable`; unverified nested input reported and not followed;
  raw-response and step budgets → `partial`; hostile titles scrubbed/redacted;
  eleven locator shapes (http, credentials, bad port, IPv4/IPv6, localhost,
  file, internal) reduced to https DNS hosts or dropped; eight inconsistent or
  fabricated contract payloads refused; projection refuses another version's
  proof; a foreign session receives 404 for the owning turn. Ruff, format,
  strict mypy (`src/kkb_agent/api`, 8 files) and Bandit clean.
- Client on Node 22.23.2: Prettier, strict TypeScript and **26/26** tests
  (3 new proof tests: ordering/labels, eight refused schema payloads,
  version-bound result) PASS; production `next build` PASS.
- Real local pool, measured on a disposable copy (deleted afterwards; original
  untouched): BDDK compare → `available`, 66 raw responses from
  `www.bddk.org.tr`, 19.9 ms, 1,522 bytes; EVDS compare → `available`, one raw
  batch response from `evds3.tcmb.gov.tr`, 4.0 ms; three-series lakehouse table
  (198 values) → `available`, 14.5 ms, 3,135 bytes. No locator, endpoint path or
  pool path in the serialized proofs.
- Browser rehearsal with `tests/manual/proof_client.py` and the production
  client: Turn 1 table (100/120/150 million TL) showed "zincir eksiksiz" with
  three BDDK raw responses, the prepared read and the accepted gate; the
  selected add-series Turn 2 showed "zincir kısmi" with both series, the nested
  `analiz_1` step, the add-series step and the named lineage gap. Reload
  restored Analiz 2; at 390 px the document client/scroll widths were both 390.
  Temporary servers were stopped and the viewport override reset.

Limits: result-level, not per-cell or per-claim mapping; `available` is recorded
coverage, not source correctness or independent recomputation. Live Kloudeks
turns, the full organizer three-turn flow and graph layout were not exercised.

<a id="catalog-validation-records"></a>

# Catalog validation records

Historical delivery records migrated from technical references. Test counts,
package versions, findings and pending integration statements are as recorded at
the original delivery, not a new run or current task selection.


<a id="catalog_search-m13-04--offline-reviewed-catalog-search"></a>

## Historical delivery scope — M13-04 — Offline reviewed catalog search

`catalog_search` discovers bounded candidates, not observation values or verified
analytical claims. It uses the [M13-08 reviewed snapshot](CATALOG.md#catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping) and
shared Turkish normalizer. Delivered under DEC-133 and retained by DEC-135, this is
the authoritative lexical/reviewed baseline for the bounded offline demo scope;
full hybrid acceptance still needs M13-05 dense retrieval and evaluation.

The separate [local LanceDB index](CATALOG.md) implements validated vector
persistence and exact search over eligible IDs. The existing factory now accepts
an optional operator-injected `CatalogDenseStage` for combined candidate retrieval.
Without it, lexical-only behavior remains. Configured stages run both methods
when reviewed eligibility is nonempty, even after lexical success. This is tested
with fixture vectors; live policy and semantic quality remain separate work.
The opt-in [bounded catalog continuation](CATALOG.md) now lets a
planner consume these candidate results as data before one analysis/clarification
plan. Default one-plan sessions retain their previous behavior.


<a id="catalog_search-fts-review-and-scope"></a>

## Historical M13-04 — FTS review and scope

At implementation, local DuckDB 1.5.5 had no installed FTS extension. Even its
extension inventory requires filesystem access refused by the hardened lakehouse
connection. No INSTALL/LOAD/autoload or download was attempted. M13-04 uses a
bounded in-memory Python BM25 calculation over this small reviewed corpus instead
of requiring an extension or a separate index connection. This is a task-local
lexical implementation, not a change to the DEC-112 analytical engine. No new
dependency is needed. Lakehouse external-access/extension restrictions remain
unchanged. A larger corpus/index change needs its own measured task review.


<a id="catalog_search-validation-and-handoff"></a>

## Historical M13-04 — Validation and handoff

**Historical M13-04 delivery evidence:** the following record describes the original lexical-tool handoff, before the later transform and prepared-inspection deliveries. Its absence/prerequisite statements are historical, not current prepared-path status.

`tests/unit/test_catalog_search.py` covers aliases/normalization, specificity,
ambiguity/caps, source/frequency/archive filtering, preserved metadata/families,
unknown/unresolved cases, ranking/order/serialization, content identity and
holdout rejection, inert labels, output-mutation isolation, closed arguments,
planner discovery and seven coexisting factories. Scripted Session tests verify
catalog metadata cannot produce an analytical claim or enter the writer as
verified evidence. Existing six-tool/agent regressions remain required.

These development cases are not M13-09 holdout or Recall@5/10 evidence. No live
source/model/search request, embedding, RRF/reranking, table_transform or new
automatic inspection/quality/reconciliation harness integration is implemented. Actual delivery/merge evidence belongs to
[ROADMAP](ROADMAP.md#m13). M13-13 mandatory inspection still needs its trusted-ID lookup/usable-metadata
contract review before being claimed; M13-05 retains its transport/configuration
prerequisites.

**Current prepared-path status:** deterministic monthly `deflate`, `add_series` and table co-movement are implemented. Configured prepared metadata inspection is mandatory and auto-wired; broader inspection, quality and reconciliation remain incomplete. This is a bounded transform slice, not a fully general `table_transform` framework. [ROADMAP](ROADMAP.md#m13) records current delivery evidence.


<a id="catalog_index-m13-05--local-catalog-vector-index"></a>

## Historical delivery scope — M13-05 — Local catalog vector index

This is the bounded offline storage/search slice selected by DEC-138. It uses
LanceDB **0.38.0**, an exact pinned runtime dependency, and the current reviewed
catalog contract (at most 40 records, 4096-dimensional vectors). It is not a
full-source catalog, live Qwen quality result or completed hybrid pipeline.


<a id="catalog_index-validation-and-dependency-review"></a>

## Historical M13-05 — Validation and dependency review

`tests/unit/test_catalog_index.py` runs real LanceDB with labelled fixture
vectors: persistence/reopen, independent cosine oracle, stable ties,
prefilter-before-top-k, empty/unknown IDs, policy/origin mismatch, invalid vectors,
existing-root preservation and failed publication. This is separate from M13-09
held-out semantic quality. No model or official-source request was made.

The installed 17-package runtime dependency closure passed `pip check`.
Targeted `pip-audit` on 2026-09-14 reported one unique existing PyArrow 21.0.0
advisory twice: **CVE-2026-25087 / PYSEC-2026-113**. The raw audit exits nonzero;
it is not a clean scan. No advisory was reported for LanceDB 0.38.0 or its newly
added packages. The [Apache release announcement](https://arrow.apache.org/blog/2026/02/16/23.0.1-release/)
limits the issue to C++ IPC-file pre-buffering explicitly enabled through
`RecordBatchFileReader::PreBufferMetadata`; the [advisory reproduced by GitHub](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg)
states that this is not exposed in Python bindings. This implementation uses
Python Arrow table construction and Lance's local vector table, accepts no IPC
upload and enables no such C++ API. On that evidence the report is not applicable
to this Python path. The existing PyArrow range is unchanged; no audit suppression
or gate weakening was added. A future C++/IPC integration needs reassessment;
release-wide dependency upgrade/audit policy is a separate checkpoint.

API behavior was checked against the installed pinned package and official
[LanceDB vector search documentation](https://docs.lancedb.com/search/vector-search).
Real embedding-policy confirmation, live index construction, hybrid-quality
evaluation and bounded planner consumption remain next integration steps.


<a id="catalog_continuation-bounded-catalog-to-analysis-continuation"></a>

## Historical delivery scope — Bounded catalog-to-analysis continuation

M5-06/M5-13 adds an explicitly enabled Session path:

```text
question -> validated catalog-only plan -> catalog_search
         -> bounded candidate metadata as data
         -> one validated analysis plan or typed clarification
         -> existing tools -> writer/verifier -> accepted workspace publication
```

This connects discovery to planning. It does not make a rank or similarity
score authoritative, add source fetching, or complete all selected-series
inspection. The [prepared reader slice](ARCHITECTURE.md#series_inspection-prepared-series-metadata-inspection) now checks catalog/store
metadata consistency whenever this rehearsal receives catalog bytes. Prepared-series and analytical tools retain their existing semantic,
availability, provenance and numerical checks. Unavailable prepared data still
cannot be silently fetched from the web.


<a id="prepared-inspection-delivery-evidence"></a>

## Prepared inspection delivery evidence

The 42 focused inspection regressions plus 35 catalog-continuation tests passed
(77 total / 15.64s locally). They cover required and optional unknowns, exact IDs,
archive policy, all semantic mismatch classes, snapshot/output mutation, current
metadata rereads, non-skippable producer/SQL behavior, receipt evidence and
prepared-rehearsal injection without a prior discovery step.

A read-only check of the existing **seven prepared series** found all declarations
consistent with reviewed v2. It took 519.51ms including opening/closing DuckDB;
all **80 prepared files** retained their hashes and no external call occurred.

A separate three-turn run over a private copy of the real prepared pool, using
scripted planning and these inspected producers, matched an independent Decimal
oracle: 59 monthly transitions, 32 rate-decline months and 22 matching
price-up/real-credit-nonrise months. It preserved 302 earlier values, checked all
60 KFE values and published all three results without verifier faults; the
original 80 files stayed unchanged. This is deterministic integration evidence,
not live model reliability or causal proof.

Wider source coverage, observation quality/reconciliation, natural-language
ambiguity resolution, history staleness and live model/embedding evaluation are
not completed by this slice. [ROADMAP](ROADMAP.md#current-project-status) and
[EVALUATION](EVALUATION.md) retain those distinctions.


<a id="prepared-api-delivery-and-pool-evidence"></a>

## Prepared API delivery and pool evidence

The original M10-17 local pool passed read-only readiness: **7 prepared identities,
683 observations, 15 reviewed catalog identities, 80 files, 7,613,310 bytes**.
Configuration is present and the approved endpoint is valid; no live request
was used to establish this. A separate in-process HTTP rehearsal with scripted
plans and the real public pool passes all three organizer turns. An independent
Decimal oracle agrees on 59 transitions, 32 rate falls and 22 joint periods.
All 302 previous values and 60 KFE values survive, and the original 80 files
remain hash-identical. The largest response is 143,584 bytes. Readiness took
717.15ms; scripted turns took 1,425.33 / 925.01 / 1,578.83ms. These are local
pipeline timings, **not Qwen inference latency or live reasoning reliability**.

The subsequent [EVDS expansion](EVDS_COVERAGE.md) prepares **29 identities and
4,124 observations** with **37 catalog identities** in v3. Original seven-series
values are retained; 3,926 EVDS observations additionally match raw decimal
values in an independent read-back. The prepared pool is 8,520,172 bytes across
124 files. These are local preparation/readiness checks, not a live-model test
over the expanded universe. Use v3 for this pool; v2 remains a historical
snapshot and correctly refuses the additional identities. Restart the API into
a fresh state root when switching pools/catalogs; existing sessions keep their
own snapshot and are not silently refreshed.

One existing gate limitation remains visible: repeating a numerical calculation
under a second identity and writing an unqualified identical number can abstain
because multiple results match. The API preserves that refusal; it does not
weaken numeric matching. A real add-series follow-up over synthetic inputs
passes, retaining the previous publication and all original values.

Live model acceptance still requires its explicit authorized rehearsal. Dense
policy/quality, broader official coverage, public proof traversal, full stage
progress, source input UI, remaining frontend features and deployment remain separate tasks.
See [EVALUATION](EVALUATION.md) and [ROADMAP](ROADMAP.md) for final test/merge state.


## Historical acceptance summary — 2026-09-14

Historical context — not current implementation status. The following original summary predates #166; its display-only selection statement is retained as dated evidence.

The [historical handoff](https://github.com/cagatayeroglu/KKB-DataTrio/blob/1578b7ce0d20566784dba49d984b940424847721/docs/HANDOFF_ARDA_2026-09-14.md) records two-turn live Kloudeks acceptance and scripted three-turn/browser rehearsal, not full live Qwen three-turn acceptance or repeated-run reliability. The recorded 29-series / 4,124-observation pool and Bronze evidence are operator-local, absent from fresh Git checkout and not repository-reproducible as an identical snapshot today. Local LanceDB/hybrid fixture tests do not establish semantic retrieval quality; default prepared API retrieval has no real Qwen embedding injection. Prepared metadata inspection is mandatory/auto-wired, while broader quality/reconciliation remain unfinished. Dated run records below retain their original evidence and limitations.

Under [DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria), acceptance must also exercise a smaller allowed open-weight model with the same custom deterministic harness and preservation of untouched columns/history. For reuse, add a new supported financial source / dataset / schema through reviewed catalog metadata and adapter/policy configuration without rewriting the core lakehouse, workspace, execution, lineage, verifier or API architecture; cross-domain/healthcare acceptance is not required. Add the specific state case: select an older UI result, ask “bu tablo” to transform/add a column, and verify the exact owned result/version used; include stale/unowned rejection and failed-turn preservation. Current UI selection is display-only and does not transmit that reference. These are required future checks, not passing tests or invented organizer scoring weights.


## Local API contracts

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="local_api-dependencies-and-validation"></a>

### Dependencies and validation

FastAPI 0.141.1, Starlette 1.6.0 and Uvicorn 0.53.0 are pinned; no hosted service
is added. `pip check` passes. Existing httpx 0.28.1 stays the Kloudeks transport.
Two upstream test-client deprecations (httpx versus httpx2 and AnyIO
BlockingPortal) remain visible; no production transport migration is implied.
The app follows the primary [FastAPI lifecycle contract](https://fastapi.tiangolo.com/advanced/events/).

Tests use a real Session/gate over synthetic DuckDB data and cover canonical
publication, immutable cells, finite values, hostile HTTP, isolation, duplicate
questions, busy/capacity rules, safe failures, SSE replay and shutdown. No live
model/source request, deployment or live reasoning quality is claimed.
[EVALUATION](EVALUATION.md) records the final gate.


## Local client

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="local_client-prova-versus-live-acceptance"></a>

### Prova versus live acceptance

The 2026-09-14 browser inspection used the real public prepared snapshot and a
finite **scripted test provider** through the same Python API. The page states
“Çevrimdışı prova — Canlı Qwen kullanılmıyor.” Three prescribed plans exercised
comparison, deflation and adding KFE, producing 242, 302 and 368 published
cells. This demonstrates client/API/tool integration and state preservation,
not arbitrary-query model reasoning or live Kloudeks acceptance.

The temporary developer rehearsal is not the production launcher or a fallback.
It is unsuitable for arbitrary questions; the official CLI above uses Kloudeks
only and requires explicit enablement. Live three-turn browser acceptance is
still pending. No live model/embedding request was made for this UI validation.

<a id="local_client-validation-and-remaining-work"></a>

### Validation and remaining work

From `web/`, `npm run check` runs formatting, strict TypeScript and the bounded
bridge/session/canonical-table regression tests. `npm run build` verifies the
production client. CI has a separate Node job; Python's Fast PR gate and secret
scanner continue to cover the repository. Generated `node_modules` and `.next`
trees are pruned, while authored JS/TS/configuration, lockfiles and `.env` paths
remain in secret-scanner scope.

This is an inspectable first client, not completion of all M10. Uploads, source
refresh jobs, charts/export, full proof traversal, detailed tool-stage events,
writable agent settings, server cancellation and hosted authentication remain
separate tasks. Monthly/weekly/daily analytical support is owned by backend
semantics and source frequency; the UI does not manufacture daily observations.
See [ROADMAP](ROADMAP.md#m10-03-first-local-client-2026-09-14) for delivery evidence.

<a id="local_client-m10-18-selection-continuation-2026-09-14-pr-166"></a>

### M10-18 selection continuation (2026-09-14, PR #166)

Merged PR #166 adds the client behavior above. Automated client/bridge tests and
production build pass; see [the dated evaluation](EVALUATION.md#m10-18-client-selection-2026-09-14).
On 2026-09-15 the selected-table browser scenarios passed using the production
frontend and real Python prepared runtime over synthetic data: old selection
through reload, uncertain-admission retry after reload, source preservation on
abstention/rejection and free-question mode. See the [dated browser evidence](EVALUATION.md#m10-18-browser-selection-2026-09-15).
Live Kloudeks acceptance, proof graph UI and broader refresh invalidation remain
separate. PR #166 merged into dev at `de11f3e` after both CI gates passed
for HEAD `09eb827`; its task branch was deleted.


## Wider operator-flow target

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="operator_flow-acceptance-of-this-specification-and-later-implementation"></a>

### Acceptance of this specification and later implementation

M10-01 is complete when the eight operator steps, current-vs-target boundary, error/follow-up/reset behavior and result/evidence responsibilities are documented against merged code. Review links and actual enum names; retain explicit unsupported features. Existing offline session/verifier/workspace/lineage/document suites can substantiate the described backend facts; they are not API tests.

The later API acceptance must cover app/health/schema/serialization, two isolated sessions, invalid/unowned IDs, oversized input, accepted/qualified/abstained output, unknown semantics and literal values, stable versioned cells, deterministic bounded graph traversal with missing/unrelated evidence, read-only proof access, safe SSE and error redaction. Include sentinel credentials/query tokens/paths and ensure neither response nor stream exposes them. Reuse scripted providers/synthetic documents; no live calls are part of these gates.

No full UI, app listener, endpoint, executable wire schema, proof adapter, authentication, deployment or UI rehearsal is delivered by M10-01. M10-03 is the next existing client task, but it cannot start until an executable agreed API contract exists; triage that missing API implementation scope separately rather than silently bundling it into operator specification or frontend scaffolding.


## File admission

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="file_admission-targeted-verification-and-next-integration"></a>

### Targeted verification and next integration

Run `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_policy.py` and touched-file Ruff checks. Tests use small synthetic text/ZIP buffers, exact-limit/one-over cases, rejected-input instrumentation, ambiguous values preserved byte-for-byte, and temporary storage cleanup/permissions. They do not prove future loader/profile behavior.

Since M1-02, DEC-112 selected the engine, and these guards are called by the CSV (M1-06), XLSX (M1-10) and PDF (M7-09) loaders; downloaded files reach the same path through `load_fetched` (M7-08). No loader produces the full M1-01 profile yet. [ROADMAP](ROADMAP.md#current-project-status) holds the current status.


## Ingestion and profile specification

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="ingestion_profile-review-acceptance-and-handoff"></a>

### Review acceptance and handoff

M1-01 review should verify every ROADMAP result field is specified, the example counts/ratios agree with the synthetic input, unknown semantics remain explicit, candidate ambiguity never silently transforms data, and accepted versus rejected/selection-required shapes are distinguishable. Review the reporting caps as proposed metadata limits; numerical file/parser limits remain M1-02 work.

Merge of this specification did not enable loaders or validate stash-only interfaces, and made no framework, database, planner/routing architecture, live source adapter, or private-data retention decision. Since then, M1-02 admission, the CSV (M1-06), XLSX (M1-10) and PDF (M7-09) loaders and the engine choice (DEC-112) have been delivered or decided; no loader produces the full profile specified here yet. [ROADMAP](ROADMAP.md#current-project-status) holds the current status.


## Prepared metadata inspection

Dated delivery/specification evidence migrated intact; historical “remaining” statements describe that slice, not current project status.

<a id="series_inspection-validation-and-limits"></a>

### Validation and limits

See the [dated evidence](EVALUATION.md#prepared-inspection-delivery-evidence) for exact tests, pool identities, timings and limitations. [ROADMAP](ROADMAP.md#current-project-status) owns delivery status.


## PR #169 first-pass migration evidence

Historical consolidation record at `c6e16f5`. Its file dispositions describe the first pass; second-pass routing below supersedes them. Link destinations follow the surviving content.

<a id="documentation-per-section-migration-map"></a>

### Per-section migration map

Every heading in each removed catalog file was mapped before deletion. Section
bodies were first transferred intact and compared, allowing only local link remapping. Two repeated architecture/status sections then had their duplicates replaced with links to their existing owners, as mapped below.
Old document titles become section headings. Historical mapping/review scope is
explicitly labelled; no source identifiers, alias tables, hashes, controls or
dated evidence were summarized away. Additional moved sections are listed too. The migrated README command reference corrects two stale current descriptions (UI startup exists; LF policy covers the reviewed source documents); commands, parser/recovery details and authorization constraints are unchanged.

| Original file | Original heading | Action | Exact destination |
| --- | --- | --- | --- |
| `docs/CATALOG_SEARCH.md` | M13-04 — Offline reviewed catalog search | Preserved | [docs/EVALUATION.md#catalog_search-m13-04--offline-reviewed-catalog-search](EVALUATION.md#catalog_search-m13-04--offline-reviewed-catalog-search) |
| `docs/CATALOG_SEARCH.md` | Bounded combined candidate contract | Preserved | [docs/CATALOG.md#catalog_search-bounded-combined-candidate-contract](CATALOG.md#catalog_search-bounded-combined-candidate-contract) |
| `docs/CATALOG_SEARCH.md` | Catalog and observation boundary | Keep metadata/observation contract; duplicate runtime status → ARCHITECTURE, pool counts → EVALUATION | [docs/CATALOG.md#catalog_search-catalog-and-observation-boundary](CATALOG.md#catalog_search-catalog-and-observation-boundary) |
| `docs/CATALOG_SEARCH.md` | Required final hybrid and vector-search target | Duplicate: Qwen/model/dimension, vector fields, flow, separation, fallback and benchmark policy already owned here | [ARCHITECTURE runtime composition](ARCHITECTURE.md#catalog-runtime-composition) |
| `docs/CATALOG_SEARCH.md` | Trusted configuration and contracts | Preserved | [docs/CATALOG.md#catalog_search-trusted-configuration-and-contracts](CATALOG.md#catalog_search-trusted-configuration-and-contracts) |
| `docs/CATALOG_SEARCH.md` | Deterministic retrieval | Preserved | [docs/CATALOG.md#catalog_search-deterministic-retrieval](CATALOG.md#catalog_search-deterministic-retrieval) |
| `docs/CATALOG_SEARCH.md` | FTS review and scope | Preserved | [docs/EVALUATION.md#catalog_search-fts-review-and-scope](EVALUATION.md#catalog_search-fts-review-and-scope) |
| `docs/CATALOG_SEARCH.md` | Validation and handoff | Preserved | [docs/EVALUATION.md#catalog_search-validation-and-handoff](EVALUATION.md#catalog_search-validation-and-handoff) |
| `docs/CATALOG_INDEX.md` | M13-05 — Local catalog vector index | Preserved | [docs/EVALUATION.md#catalog_index-m13-05--local-catalog-vector-index](EVALUATION.md#catalog_index-m13-05--local-catalog-vector-index) |
| `docs/CATALOG_INDEX.md` | Inputs and storage | Preserved | [docs/CATALOG.md#catalog_index-inputs-and-storage](CATALOG.md#catalog_index-inputs-and-storage) |
| `docs/CATALOG_INDEX.md` | Opening and searching | Preserved | [docs/CATALOG.md#catalog_index-opening-and-searching](CATALOG.md#catalog_index-opening-and-searching) |
| `docs/CATALOG_INDEX.md` | Validation and dependency review | Preserved | [docs/EVALUATION.md#catalog_index-validation-and-dependency-review](EVALUATION.md#catalog_index-validation-and-dependency-review) |
| `docs/CATALOG_CONTINUATION.md` | Bounded catalog-to-analysis continuation | Preserved | [docs/EVALUATION.md#catalog_continuation-bounded-catalog-to-analysis-continuation](EVALUATION.md#catalog_continuation-bounded-catalog-to-analysis-continuation) |
| `docs/CATALOG_CONTINUATION.md` | Activation and compatibility | Preserved | [docs/CATALOG.md#catalog_continuation-activation-and-compatibility](CATALOG.md#catalog_continuation-activation-and-compatibility) |
| `docs/CATALOG_CONTINUATION.md` | What the harness enforces | Preserved | [docs/CATALOG.md#catalog_continuation-what-the-harness-enforces](CATALOG.md#catalog_continuation-what-the-harness-enforces) |
| `docs/CATALOG_CONTINUATION.md` | Clarification and remaining limits | Preserved | [docs/CATALOG.md#catalog_continuation-clarification-and-remaining-limits](CATALOG.md#catalog_continuation-clarification-and-remaining-limits) |
| `docs/CATALOG_MAPPING.md` | M13-08 — Reviewed offline demo catalog mapping | Preserved | [docs/CATALOG.md#catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping](CATALOG.md#catalog_mapping-m13-08--reviewed-offline-demo-catalog-mapping) |
| `docs/CATALOG_MAPPING.md` | Current prepared-scope revision (2026-09-14) | Preserved | [docs/CATALOG.md#catalog_mapping-current-prepared-scope-revision-2026-09-14](CATALOG.md#catalog_mapping-current-prepared-scope-revision-2026-09-14) |
| `docs/CATALOG_MAPPING.md` | Historical v1 review | Preserved | [docs/CATALOG.md#catalog_mapping-historical-v1-review](CATALOG.md#catalog_mapping-historical-v1-review) |
| `docs/CATALOG_MAPPING.md` | Version and trust boundary | Preserved | [docs/CATALOG.md#catalog_mapping-version-and-trust-boundary](CATALOG.md#catalog_mapping-version-and-trust-boundary) |
| `docs/CATALOG_MAPPING.md` | Real identity inventory | Preserved | [docs/CATALOG.md#catalog_mapping-real-identity-inventory](CATALOG.md#catalog_mapping-real-identity-inventory) |
| `docs/CATALOG_MAPPING.md` | Complete concept mapping | Preserved | [docs/CATALOG.md#catalog_mapping-complete-concept-mapping](CATALOG.md#catalog_mapping-complete-concept-mapping) |
| `docs/CATALOG_MAPPING.md` | Unresolved source context | Preserved | [docs/CATALOG.md#catalog_mapping-unresolved-source-context](CATALOG.md#catalog_mapping-unresolved-source-context) |
| `docs/CATALOG_MAPPING.md` | Families and ambiguity | Preserved | [docs/CATALOG.md#catalog_mapping-families-and-ambiguity](CATALOG.md#catalog_mapping-families-and-ambiguity) |
| `docs/CATALOG_MAPPING.md` | Loading and validation | Preserved | [docs/CATALOG.md#catalog_mapping-loading-and-validation](CATALOG.md#catalog_mapping-loading-and-validation) |
| `docs/CATALOG_MAPPING.md` | Current catalog boundary | Preserved | [docs/CATALOG.md#catalog_mapping-current-catalog-boundary](CATALOG.md#catalog_mapping-current-catalog-boundary) |
| `docs/CATALOG_MAPPING.md` | Handoff to M13-04 | Preserved | [docs/CATALOG.md#catalog_mapping-handoff-to-m13-04](CATALOG.md#catalog_mapping-handoff-to-m13-04) |
| `docs/ROADMAP.md` | Historical handbacks through 2026-09-14 | Preserved | [docs/HISTORY.md#handbacks-2026-09-14](ROADMAP.md#history-handbacks-through-2026-09-14) |
| `docs/ROADMAP.md` | PR #162 pre-merge claim | Preserved | [docs/HISTORY.md#pr-162-claim](ROADMAP.md#history-pr-162-pre-merge-claim) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-06 — Vector cache/index implementation | Preserved | [docs/HISTORY.md#q-team-06--vector-cacheindex-implementation](DECISIONS.md#history-q-team-06--vector-cacheindex-implementation) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-05 — Workspace persistence and reference storage | Preserved | [docs/HISTORY.md#q-team-05--workspace-persistence-and-reference-storage](DECISIONS.md#history-q-team-05--workspace-persistence-and-reference-storage) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-04 — Causality implementation and prerequisites | Preserved | [docs/HISTORY.md#q-team-04--causality-implementation-and-prerequisites](DECISIONS.md#history-q-team-04--causality-implementation-and-prerequisites) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-03 — Frontend framework | Preserved | [docs/HISTORY.md#q-team-03--frontend-framework](DECISIONS.md#history-q-team-03--frontend-framework) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-02 — Analytical/parsing engine | Preserved | [docs/HISTORY.md#q-team-02--analyticalparsing-engine](DECISIONS.md#history-q-team-02--analyticalparsing-engine) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-01 — Orchestration mechanism | Preserved | [docs/HISTORY.md#q-team-01--orchestration-mechanism](DECISIONS.md#history-q-team-01--orchestration-mechanism) |
| `docs/OPEN_QUESTIONS.md` | Q-DEV-01 — Coding assistants during development | Preserved | [docs/HISTORY.md#q-dev-01--coding-assistants-during-development](DECISIONS.md#history-q-dev-01--coding-assistants-during-development) |
| `docs/SERIES_INSPECTION.md` | Validation and limits | Preserved | [docs/EVALUATION.md#prepared-inspection-delivery-evidence](EVALUATION.md#prepared-inspection-delivery-evidence) |
| `docs/PREPARED_API.md` | Measured acceptance and remaining limits | Preserved | [docs/EVALUATION.md#prepared-api-delivery-and-pool-evidence](EVALUATION.md#prepared-api-delivery-and-pool-evidence) |
| `README.md` | Commands | Preserved | [docs/PREPARED_API.md#development-and-live-check-commands](OPERATIONS.md#prepared_api-development-and-authorized-live-check-commands) |
| `README.md` | Repository guide | Preserved | [docs/DOCUMENTATION.md#repository-paths](../README.md#repository-paths) |
| `README.md` | Constraints and architecture | Duplicate architecture/status/evidence summaries; use owners | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| `README.md` | Fast development workflow / Branches and collaboration | Duplicate workflow; use AGENTS | [AGENTS.md](../AGENTS.md) |


## PR #169 second-pass migration evidence

Second pass starts at `c6e16f57c6fc99635645006c3ebe95b02e5258ba`.
The map below was prepared before deletion. Unique section bodies were moved
intact, permitting local-link rebasing; duplicate navigation is replaced by the
README principal map. Original question IDs, source details, commands and dated
evidence remain. The 11 principal documents plus five hash-pinned source records,
two compatibility stubs and three fixture explanations give 21 Markdown files
(28 before the PR; 27 after the first pass).

The test docstring in `tests/unit/test_ingestion_fixture.py` still names its
original INGESTION_PROFILE source. It is historical provenance, not a file read
or a Markdown link; tests are unchanged. Its complete synthetic example is now
in SOURCES. The source-file hash tests prevent removing the five evidence files;
the BDDK evidence's Q-DATA links require the OPEN_QUESTIONS compatibility stub.
Two unchanged fixture explanations link to INGESTION_PROFILE; a second small stub
retains those links without editing anything under tests/.

| Old file | Heading | Action | Exact destination |
| --- | --- | --- | --- |
| `LOCAL_API.md` | M10-16 — Version-one local API and owned results | Preserve | [section](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results) |
| `LOCAL_API.md` | Executable contract | Preserve | [section](OPERATIONS.md#local_api-executable-contract) |
| `LOCAL_API.md` | M10-18 — selected-result grounding (merged) | Preserve | [section](ARCHITECTURE.md#local_api-m10-18--selected-result-grounding-merged) |
| `LOCAL_API.md` | Bounded lifecycle | Preserve | [section](ARCHITECTURE.md#local_api-bounded-lifecycle) |
| `LOCAL_API.md` | Canonical values and trust | Preserve | [section](ARCHITECTURE.md#local_api-canonical-values-and-trust) |
| `LOCAL_API.md` | Local HTTP boundary | Preserve | [section](SECURITY.md#local_api-local-http-boundary) |
| `LOCAL_API.md` | Dependencies and validation | Preserve | [section](EVALUATION.md#local_api-dependencies-and-validation) |
| `PREPARED_API.md` | M10-17 — Run the API over a prepared local pool | Preserve | [section](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) |
| `PREPARED_API.md` | Check first, without calling a model | Preserve | [section](OPERATIONS.md#prepared_api-check-first-without-calling-a-model) |
| `PREPARED_API.md` | Start only when model requests are authorized | Preserve | [section](OPERATIONS.md#prepared_api-start-only-when-model-requests-are-authorized) |
| `PREPARED_API.md` | Snapshot and session ownership | Preserve | [section](ARCHITECTURE.md#prepared_api-snapshot-and-session-ownership) |
| `PREPARED_API.md` | Measured acceptance and remaining limits | Preserve | [section](OPERATIONS.md#prepared_api-measured-acceptance-and-remaining-limits) |
| `PREPARED_API.md` | Development and authorized live-check commands | Preserve | [section](OPERATIONS.md#prepared_api-development-and-authorized-live-check-commands) |
| `LOCAL_CLIENT.md` | DataTrio local analysis workspace | Preserve | [section](OPERATIONS.md#local_client-datatrio-local-analysis-workspace) |
| `LOCAL_CLIENT.md` | Run on Windows | Preserve | [section](OPERATIONS.md#local_client-run-on-windows) |
| `LOCAL_CLIENT.md` | What the first screen does | Preserve | [section](OPERATIONS.md#local_client-what-the-first-screen-does) |
| `LOCAL_CLIENT.md` | Recovery and limits | Preserve | [section](OPERATIONS.md#local_client-recovery-and-limits) |
| `LOCAL_CLIENT.md` | Prova versus live acceptance | Preserve | [section](EVALUATION.md#local_client-prova-versus-live-acceptance) |
| `LOCAL_CLIENT.md` | Validation and remaining work | Preserve | [section](EVALUATION.md#local_client-validation-and-remaining-work) |
| `LOCAL_CLIENT.md` | M10-18 selection continuation (2026-09-14, PR #166) | Preserve | [section](EVALUATION.md#local_client-m10-18-selection-continuation-2026-09-14-pr-166) |
| `LOCAL_CLIENT.md` | Repeat the finite synthetic selection rehearsal | Preserve | [section](OPERATIONS.md#local_client-repeat-the-finite-synthetic-selection-rehearsal) |
| `OPERATOR_FLOW.md` | M10-01 — Operator flow and API boundary requirements | Preserve | [section](ARCHITECTURE.md#operator_flow-m10-01--operator-flow-and-api-boundary-requirements) |
| `OPERATOR_FLOW.md` | One demo flow | Preserve | [section](OPERATIONS.md#operator_flow-one-demo-flow) |
| `OPERATOR_FLOW.md` | Prepared dataset selection and separate web inputs | Preserve | [section](OPERATIONS.md#operator_flow-prepared-dataset-selection-and-separate-web-inputs) |
| `OPERATOR_FLOW.md` | Backend facts and integration prerequisites | Preserve | [section](ARCHITECTURE.md#operator_flow-backend-facts-and-integration-prerequisites) |
| `OPERATOR_FLOW.md` | Public payload requirements and implemented local API | Preserve | [section](ARCHITECTURE.md#operator_flow-public-payload-requirements-and-implemented-local-api) |
| `OPERATOR_FLOW.md` | Session/request isolation and failure lifecycle | Preserve | [section](ARCHITECTURE.md#operator_flow-sessionrequest-isolation-and-failure-lifecycle) |
| `OPERATOR_FLOW.md` | “Why this number?” proof requirements | Preserve | [section](ARCHITECTURE.md#operator_flow-why-this-number-proof-requirements) |
| `OPERATOR_FLOW.md` | SSE requirements (DEC-123) | Preserve | [section](ARCHITECTURE.md#operator_flow-sse-requirements-dec-123) |
| `OPERATOR_FLOW.md` | Acceptance of this specification and later implementation | Preserve | [section](EVALUATION.md#operator_flow-acceptance-of-this-specification-and-later-implementation) |
| `FILE_ADMISSION.md` | M1-02 — File admission policy | Preserve | [section](SECURITY.md#file_admission-m1-02--file-admission-policy) |
| `FILE_ADMISSION.md` | Initial format policy | Preserve | [section](SOURCES.md#file_admission-initial-format-policy) |
| `FILE_ADMISSION.md` | Practical local limits | Preserve | [section](SECURITY.md#file_admission-practical-local-limits) |
| `FILE_ADMISSION.md` | Transient storage and errors | Preserve | [section](SECURITY.md#file_admission-transient-storage-and-errors) |
| `FILE_ADMISSION.md` | Targeted verification and next integration | Preserve | [section](EVALUATION.md#file_admission-targeted-verification-and-next-integration) |
| `INGESTION_PROFILE.md` | M1-01 — Ingestion/profile result specification | Preserve | [section](ARCHITECTURE.md#ingestion_profile-m1-01--ingestionprofile-result-specification) |
| `INGESTION_PROFILE.md` | Integration boundary | Preserve | [section](ARCHITECTURE.md#ingestion_profile-integration-boundary) |
| `INGESTION_PROFILE.md` | Result fields | Preserve | [section](ARCHITECTURE.md#ingestion_profile-result-fields) |
| `INGESTION_PROFILE.md` | Column fields and invariants | Preserve | [section](ARCHITECTURE.md#ingestion_profile-column-fields-and-invariants) |
| `INGESTION_PROFILE.md` | Bounded profiling and deferred limits | Preserve | [section](SECURITY.md#ingestion_profile-bounded-profiling-and-deferred-limits) |
| `INGESTION_PROFILE.md` | Synthetic example: accepted table, unresolved semantics | Preserve | [section](SOURCES.md#ingestion_profile-synthetic-example-accepted-table-unresolved-semantics) |
| `INGESTION_PROFILE.md` | Testable edge cases for later implementation | Preserve | [section](SOURCES.md#ingestion_profile-testable-edge-cases-for-later-implementation) |
| `INGESTION_PROFILE.md` | Review acceptance and handoff | Preserve | [section](EVALUATION.md#ingestion_profile-review-acceptance-and-handoff) |
| `SERIES_INSPECTION.md` | Prepared series metadata inspection | Preserve | [section](ARCHITECTURE.md#series_inspection-prepared-series-metadata-inspection) |
| `SERIES_INSPECTION.md` | Contract and refusal states | Preserve | [section](SOURCES.md#series_inspection-contract-and-refusal-states) |
| `SERIES_INSPECTION.md` | Non-skippable wiring in the prepared mode | Preserve | [section](ARCHITECTURE.md#series_inspection-non-skippable-wiring-in-the-prepared-mode) |
| `SERIES_INSPECTION.md` | Validation and limits | Preserve | [section](EVALUATION.md#series_inspection-validation-and-limits) |
| `OPEN_QUESTIONS.md` | Actionable open questions | Preserve | [section](DECISIONS.md#open_questions-actionable-open-questions) |
| `OPEN_QUESTIONS.md` | DEC-137 unresolved materialization and storage policy | Preserve | [section](DECISIONS.md#open_questions-dec-137-unresolved-materialization-and-storage-policy) |
| `OPEN_QUESTIONS.md` | How to use this list | Preserve | [section](DECISIONS.md#open_questions-how-to-use-this-list) |
| `OPEN_QUESTIONS.md` | Priority queue | Preserve | [section](DECISIONS.md#open_questions-priority-queue) |
| `OPEN_QUESTIONS.md` | Kloudeks | Preserve | [section](DECISIONS.md#open_questions-kloudeks) |
| `OPEN_QUESTIONS.md` | Q-K-01 — Endpoint, authentication, and credential delivery | Preserve | [section](DECISIONS.md#open_questions-q-k-01--endpoint-authentication-and-credential-delivery) |
| `OPEN_QUESTIONS.md` | Q-K-02 — Available models and context capacity | Preserve | [section](DECISIONS.md#open_questions-q-k-02--available-models-and-context-capacity) |
| `OPEN_QUESTIONS.md` | Q-K-03 — Structured output and tool calling | Preserve | [section](DECISIONS.md#open_questions-q-k-03--structured-output-and-tool-calling) |
| `OPEN_QUESTIONS.md` | Q-K-04 — Quotas, timeouts, and retry behavior | Preserve | [section](DECISIONS.md#open_questions-q-k-04--quotas-timeouts-and-retry-behavior) |
| `OPEN_QUESTIONS.md` | Q-K-05 — Embeddings and rerankers | Preserve | [section](DECISIONS.md#open_questions-q-k-05--embeddings-and-rerankers) |
| `OPEN_QUESTIONS.md` | Organizer infrastructure | Preserve | [section](DECISIONS.md#open_questions-organizer-infrastructure) |
| `OPEN_QUESTIONS.md` | Q-INFRA-01 — Runtime/deployment environment | Preserve | [section](DECISIONS.md#open_questions-q-infra-01--runtimedeployment-environment) |
| `OPEN_QUESTIONS.md` | Q-INFRA-02 — Storage lifetime and isolation | Preserve | [section](DECISIONS.md#open_questions-q-infra-02--storage-lifetime-and-isolation) |
| `OPEN_QUESTIONS.md` | Datasets | Preserve | [section](DECISIONS.md#open_questions-datasets) |
| `OPEN_QUESTIONS.md` | Q-DATA-01 — BDDK/EVDS and provided source access | Preserve | [section](DECISIONS.md#open_questions-q-data-01--bddkevds-and-provided-source-access) |
| `OPEN_QUESTIONS.md` | Q-DATA-02 — Hidden formats, schema variation, and size | Preserve | [section](DECISIONS.md#open_questions-q-data-02--hidden-formats-schema-variation-and-size) |
| `OPEN_QUESTIONS.md` | Q-DATA-03 — Caching, retention, and redistribution | Preserve | [section](DECISIONS.md#open_questions-q-data-03--caching-retention-and-redistribution) |
| `OPEN_QUESTIONS.md` | Q-DATA-04 — Authoritative semantics and revisions | Preserve | [section](DECISIONS.md#open_questions-q-data-04--authoritative-semantics-and-revisions) |
| `OPEN_QUESTIONS.md` | External internet / network | Preserve | [section](DECISIONS.md#open_questions-external-internet--network) |
| `OPEN_QUESTIONS.md` | Q-NET-01 — Demo/development internet access | Preserve | [section](DECISIONS.md#open_questions-q-net-01--demodevelopment-internet-access) |
| `OPEN_QUESTIONS.md` | Q-NET-02 — Allowed external source URLs | Preserve | [section](DECISIONS.md#open_questions-q-net-02--allowed-external-source-urls) |
| `OPEN_QUESTIONS.md` | Demo format | Preserve | [section](DECISIONS.md#open_questions-demo-format) |
| `OPEN_QUESTIONS.md` | Q-DEMO-01 — Timing, format, and user interaction | Preserve | [section](DECISIONS.md#open_questions-q-demo-01--timing-format-and-user-interaction) |
| `OPEN_QUESTIONS.md` | Q-DEMO-02 — Multi-turn state and reset semantics | Preserve | [section](DECISIONS.md#open_questions-q-demo-02--multi-turn-state-and-reset-semantics) |
| `OPEN_QUESTIONS.md` | Q-DEMO-03 — Permitted fallback and demonstration assets | Preserve | [section](DECISIONS.md#open_questions-q-demo-03--permitted-fallback-and-demonstration-assets) |
| `OPEN_QUESTIONS.md` | Allowed development tooling | Preserve | [section](DECISIONS.md#open_questions-allowed-development-tooling) |
| `OPEN_QUESTIONS.md` | Q-DEV-02 — External tools, libraries, and code disclosure | Preserve | [section](DECISIONS.md#open_questions-q-dev-02--external-tools-libraries-and-code-disclosure) |
| `OPEN_QUESTIONS.md` | Scoring / judging | Preserve | [section](DECISIONS.md#open_questions-scoring--judging) |
| `OPEN_QUESTIONS.md` | Q-JUDGE-01 — Rubric and unsupported-answer handling | Preserve | [section](DECISIONS.md#open_questions-q-judge-01--rubric-and-unsupported-answer-handling) |
| `OPEN_QUESTIONS.md` | Q-JUDGE-02 — Submission and development-history evidence | Preserve | [section](DECISIONS.md#open_questions-q-judge-02--submission-and-development-history-evidence) |
| `OPEN_QUESTIONS.md` | Compute / resources | Preserve | [section](DECISIONS.md#open_questions-compute--resources) |
| `OPEN_QUESTIONS.md` | Q-COMP-01 — Provided machine and resource limits | Preserve | [section](DECISIONS.md#open_questions-q-comp-01--provided-machine-and-resource-limits) |
| `OPEN_QUESTIONS.md` | Q-COMP-02 — Optional training/inference experiment budget | Preserve | [section](DECISIONS.md#open_questions-q-comp-02--optional-traininginference-experiment-budget) |
| `OPEN_QUESTIONS.md` | Internal team choices — resolve with evidence, not organizer guesses | Preserve | [section](DECISIONS.md#open_questions-internal-team-choices--resolve-with-evidence-not-organizer-guesses) |
| `OPEN_QUESTIONS.md` | Q-TEAM-07 — Broad prepared coverage target | Preserve | [section](DECISIONS.md#open_questions-q-team-07--broad-prepared-coverage-target) |
| `OPEN_QUESTIONS.md` | Q-TEAM-08 — Refresh and vintage selection policy | Preserve | [section](DECISIONS.md#open_questions-q-team-08--refresh-and-vintage-selection-policy) |
| `HISTORY.md` | Historical handbacks and answered questions | Preserve | [section](ROADMAP.md#history-historical-handbacks-and-answered-questions) |
| `HISTORY.md` | Handbacks through 2026-09-14 | Preserve | [section](ROADMAP.md#history-handbacks-through-2026-09-14) |
| `HISTORY.md` | PR #162 pre-merge claim | Preserve | [section](ROADMAP.md#history-pr-162-pre-merge-claim) |
| `HISTORY.md` | Q-TEAM-06 — Vector cache/index implementation | Preserve | [section](DECISIONS.md#history-q-team-06--vector-cacheindex-implementation) |
| `HISTORY.md` | Q-TEAM-05 — Workspace persistence and reference storage | Preserve | [section](DECISIONS.md#history-q-team-05--workspace-persistence-and-reference-storage) |
| `HISTORY.md` | Q-TEAM-04 — Causality implementation and prerequisites | Preserve | [section](DECISIONS.md#history-q-team-04--causality-implementation-and-prerequisites) |
| `HISTORY.md` | Q-TEAM-03 — Frontend framework | Preserve | [section](DECISIONS.md#history-q-team-03--frontend-framework) |
| `HISTORY.md` | Q-TEAM-02 — Analytical/parsing engine | Preserve | [section](DECISIONS.md#history-q-team-02--analyticalparsing-engine) |
| `HISTORY.md` | Q-TEAM-01 — Orchestration mechanism | Preserve | [section](DECISIONS.md#history-q-team-01--orchestration-mechanism) |
| `HISTORY.md` | Q-DEV-01 — Coding assistants during development | Preserve | [section](DECISIONS.md#history-q-dev-01--coding-assistants-during-development) |
| `DOCUMENTATION.md` | Documentation guide and consolidation ledger | Duplicate navigation/roles replaced by README principal map and source-evidence exceptions | [section](../README.md#documentation-map) |
| `DOCUMENTATION.md` | Authority model | Duplicate navigation/roles replaced by README principal map and source-evidence exceptions | [section](../README.md#documentation-map) |
| `DOCUMENTATION.md` | Reference inventory and disposition | Duplicate navigation/roles replaced by README principal map and source-evidence exceptions | [section](../README.md#documentation-map) |
| `DOCUMENTATION.md` | Per-section migration map | Preserve | [section](EVALUATION.md#documentation-per-section-migration-map) |
| `DOCUMENTATION.md` | Repository paths | Preserve non-document paths; replace duplicate document rows with principal map | [section](../README.md#repository-paths) |
