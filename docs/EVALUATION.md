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

After run 3 the writer prompt now forbids cause wording entirely; that change is offline-tested only. Remaining acceptance gaps: an ACCEPTED live Turn 1 with workspace publication, latency (~100 s, mostly long generation), the writer echoing `dimensionless` from display phrases, and Turn 3's "sebep olabilir mi" question, which the gate's cause rule will withhold by design.

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

Cases F/H/I are not blockers for the organizer core three-turn demo; basic conflict refusal and preservation of trusted history still apply now. Expand prepared known/unseen concepts after the first four-series real E2E slice, as safely practical. Required dense/vector retrieval remains unimplemented. LanceDB is the selected catalog index (DEC-138); measure its retrieval quality, latency and failure behaviour against lexical-only and dense-only baselines. Vector records contain catalog representations only, never BDDK/EVDS values; no PostgreSQL service is selected.

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

These commands are present in [Makefile](../Makefile); results have not been established in this documentation task:

| Command | Actual current behavior |
| --- | --- |
| `make install-dev` | Installs editable package and declared dev extras; setup command, not validation |
| `make quick` | Ruff check on src/tests/scripts and unit pytest |
| `make pr` | Ruff format/check, unit pytest, Bandit, local secret-pattern script |
| `make full` | Ruff format/check, mypy, full pytest, Bandit, local secret-pattern script, pip-audit |

M7-19's operator command is `python -m kkb_agent.live_check --document --question '…URL…'` ([approved-run setup](../README.md)). It is never invoked by a gate. Offline tests inject a fake fetch and scripted provider through the normal `Session.answer` path. **ONE LIVE PUBLIC CSV DOCUMENT ACCEPTANCE PASSED** ([bounded evidence](#m7-19-live-csv-acceptance)). A future live run requires separate operator approval and an accepted Q-NET-01/02 boundary; no network question is closed by these tests.

Document smoke success requires executed `web_url`, admitted/loaded content, a selected cell's `AnalyticalResult`, its transform-to-source edge resolving in the same lakehouse, and at least one retained accepted numeric claim bound to that exact result. ACCEPTED/QUALIFIED alone, another tool's answer, a year-only/non-numeric answer, or a supported number inside a withheld sentence cannot pass. Wrong figure/unit/scale/period, ambiguous cell numbers, missing lineage and fetch/parser/provider failure are tested offline. This proves binding to the published cell, not independent recomputation, external corroboration or arbitrary prose correctness. Reports expose only bounded stage metadata/counts, numeric coordinates and SHA-256 digests of source/content/result identities; no raw URLs, prompts, answers, cells or sheet names.

M7-20 preserves the existing `WebUrlOutput.code` as operator-only `fetch_code` when the failure category is `fetch_failed` and the value is in `FetchCode`. Unknown/non-fetch codes return null. DNS, redirect loop/cap, time, size and media categories remain distinguishable; TLS shares `TRANSPORT_FAILURE` with other transport failures. This does not recover the code from the prior live run; a separately authorized future run would report it. User-facing abstention and all fetch/parser guards remain unchanged. The M7-19 admission-report follow-up likewise exposes allowlisted admission/loader codes as `document_code` for `not_admitted`/`needs_input`. Normal synthetic UTF-8 CSV passes the unchanged fetched/upload path; the prior live rejection cannot be diagnosed from its generic category alone, and no exact captured bytes are retained.

`make eval-smoke`, `make eval-full`, and benchmark CLI commands **do not exist yet**. When M9 implements a runner, replace the planned entries below with actual commands and safe output locations. Do not document a placeholder as runnable.

| Planned tier | Runner command | Result location | Status |
| --- | --- | --- | --- |
| EVAL-SMOKE | TBD after runner implementation | TBD; local sanitized report | NOT IMPLEMENTED |
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

## Adversarial case catalog

All checkboxes below track **validated executable coverage**, not the existence of a written scenario. The benchmark cases remain unchecked because no benchmark runner executes them; overlapping unit-test coverage exists and is recorded in ROADMAP, not counted as a benchmark run. Individual progress belongs in M9; update a catalog checkbox only when its runnable case and passing assertion are recorded, not after every unrelated task.

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
| No measured run yet | — | — | — | — | — | M9-01 then runner/oracles |

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

[OPERATOR_FLOW](OPERATOR_FLOW.md) defines the operator happy path, abstention, tool/source failure, follow-up and reset limitations. Acceptance here is document/code-contract review, not a UI rehearsal or API test. Its final section enumerates offline API/session/table/proof/SSE security tests for the later runtime implementation. Existing session, verifier and lineage regressions support backend facts only; no app/health/HTTP/SSE surface is claimed.

<a id="catalog-tool-acceptance-dec-133"></a>

## Catalog tool acceptance (DEC-133 delivery; DEC-135 current boundary)

M13-04 implements offline `catalog_search`; [its contract](CATALOG_SEARCH.md) and `tests/unit/test_catalog_search.py` cover the development checks below. Reuse M13 cases and reviewed catalog/alias versions rather than inventing live source IDs. Before delivery cover exact aliases and shared Turkish/punctuation/case normalization; multiple plausible candidates; source/frequency/archive filtering (archive excluded by policy); stable IDs and explicit unknowns; preserved stock/flow and rate/amount distinctions; deterministic ordering/caps; empty query, no-match and no fabricated records. Catalog injection-looking text remains inert. Reject unknown arguments and planned/unknown tools, expose only registered implementations, and regress the existing base tools. Offline synthetic test records must be labelled synthetic and never promoted to a trusted runtime catalog.

Measure lexical-only, dense-only and combined retrieval under DEC-130 separately; an offline lexical stage is not hybrid acceptance. Validate dimension/config if dense is used. No live access is required or authorized by these tests. Future table_transform acceptance must preserve mandatory semantics, security, lineage and verification. DEC-135 harness acceptance must separately prove that selected financial series cannot bypass metadata inspection, retrieved observations cannot become analysis-ready before quality checks, and comparable multi-source measures trigger bounded reconciliation outside LLM discretion. Preserve unknowns, reject invented equivalence, and test all reconciliation states. These automatic integrations and their acceptance tests remain future M13-13/M1-12/M8-09 work, not delivered by M13-04. These tests claim offline lexical tool validation, not a benchmark score, full hybrid delivery or future-tool implementation.

### M7-22 offline search acceptance

`tests/unit/test_web_search_tool.py` uses a test-only FakeSearchBackend and scripted planner. It covers closed bounded arguments, ranked/capped/empty results, supplied versus missing metadata, duplicate/redacted locators, unsafe URLs, malformed typed replies, response byte cap, safe timeout/backend failures, worker termination and secret/stdout isolation. Injection-looking snippets stay inert; search-only Session.answer abstains without a writer or analytical claim. Search locators do not authorize web_url. The M7-22 delivery tests register six core factories; M13-04 subsequently tests catalog_search as the seventh. DEC-135 table_transform and new automatic harness integrations remain unimplemented. Neighboring web_url/planner tests and make quick/pr preserve existing behavior. Exact results and merge evidence belong to M7-22 in ROADMAP. No real provider, credentials or live call is used. Production acceptance still requires the separately authorized real-adapter and unseen-query smoke in the [acceptance record](ROADMAP.md#web-search-production-acceptance).

### M13-08 reviewed mapping development checks

The [demo mapping artifact](CATALOG_MAPPING.md) is development/reference material, not M13-09 holdout. Its tests pin repository-supported real IDs, content/evidence hashes, exact alias unions, ambiguity, unresolved source groups/selectors, archived/unknown distinctions, native frequency/rate basis, family exclusions and deterministic loading. No synthetic record becomes a reviewed real candidate; no recall/benchmark score or live-source acceptance is claimed. Teammate-authored held-out queries and independent adjudication remain separate M13-09 work.
