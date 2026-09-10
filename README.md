# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. The intended product accepts supported data sources and questions, produces a typed analytical plan, computes results with deterministic Python tools, and presents answers/tables/charts with source, transformation, and verification evidence. Follow-up questions use an explicit analysis workspace.

The repository contains an offline end-to-end analysis path: guarded CSV/XLSX input and bounded direct-GET safe fetch, DuckDB/Parquet storage and financial semantics, typed analytical results, validated planning/tool execution, persisted workspace values and multi-result answer verification. Four brief tools exist: `lakehouse`, `change_detection` (comparison), `anomaly`, and `causality` (association/lag). The composed tests use synthetic data and a scripted model. Live source adapters/Kloudeks, CSV profiling, full proof/replay, Granger/breakpoints, `web_search`/`web_url`, catalog retrieval, UI and deployment remain incomplete. [ROADMAP Current Project Status](docs/ROADMAP.md#current-project-status) is the single delivery and next-task summary.

## Constraints and architecture

Python is the backend/analytics language; delivered runtime LLM access uses Kloudeks only. DuckDB/Parquet and Pandas are confirmed, with custom bounded orchestration and a DuckDB workspace/lineage graph. Material calculations are deterministic, unknown semantics stay explicit, and external/model content remains untrusted. BDDK/EVDS are intended adapters, not hard-coded core assumptions. No Snowflake or third-party hosted LLM services. The `openai` SDK is permitted only as a client exclusively configured for Kloudeks; [DEC-129](docs/DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the official endpoints, MIA-key authentication, confirmed text/vision, embedding and OCR models, and the literal OCR/embedding request contracts. Availability does not imply implemented live transport or native tool/JSON support; no live request has been made. [DEC-131](docs/DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) records the organizer calendar (development closes **20 September 2026**, Final Day **17 October 2026**), delivery by private-repository access, the expectation of a live deployed solution, and prompt-supplied URL documents as required demo-day scope.

Target flow:

```text
Question + explicit workspace
  -> validated typed plan / registered tools
  -> guarded ingestion + explicit financial semantics
  -> deterministic analysis + run/result/input evidence
  -> independent verification gate
  -> answer/table/chart + concise claim-level Why?
```

The answer gate binds numbers to typed results, checks scale/period contradictions, resolves preserved input references and can reread identified values from the store. It withholds unsupported sentences and can abstain. Workspace result digests and stale-read rejection preserve prior values across turns; they do not prove independent recomputation, complete run/input provenance or replay. [ARCHITECTURE](docs/ARCHITECTURE.md) separates implemented boundaries from confirmed targets and remaining gaps.

Retrieval's initial hybrid baseline is Turkish normalization, reviewed alias/concept-family mapping, metadata filtering, lexical/BM25 and the organizer's Qwen3-Embedding-8B dense retrieval, with LanceDB retained as the lightweight vector index ([DEC-130](docs/DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline); DEC-127/115 are superseded). Benchmarks compare lexical-only, dense-only and combined quality/latency/failures; dense use does not wait for lexical failure. RRF, reranking and extra infrastructure require measured benefit. Direct retrieval and catalog-bounded relationship discovery remain separate evaluation paths.

[DEC-128](docs/DECISIONS.md#dec-128--financial-question-validation-and-claim-level-evidence) records intended premise validation, finance semantic guard, bounded relationship stability and claim-level proof on the same spine. Core integration comes first; none is a claim of completed product behavior. FastAPI/SSE + Next.js and single-VM deployment remain confirmed targets, subject to organizer constraints; graph-heavy proof UI is deferred.

## Repository guide

| Path | Purpose / current scope |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Coding-agent scope, targeted reading, validation, Git authorization, handoff rules |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Main execution truth: relative days, M0–M13, checkboxes, READY queue, evidence/handoffs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component boundaries, contracts, state, data flow, failure behavior |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Metrics, benchmark tiers, adversarial cases, scorecard plan |
| [docs/SECURITY.md](docs/SECURITY.md) | Required controls for enabled boundaries and their validation |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Confirmed constraints/decisions, proposals, deferred choices |
| [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) | Actionable organizer/team unknowns, owners, evidence, blockers |
| [docs/FILE_ADMISSION.md](docs/FILE_ADMISSION.md) | Extension/MIME/content checks, limits and staging for uploaded files |
| [docs/INGESTION_PROFILE.md](docs/INGESTION_PROFILE.md) | The ingestion and profile result contract |
| [docs/BDDK_SOURCE.md](docs/BDDK_SOURCE.md) | What the BDDK bulletins publish: transports, parameters, units, measured cumulative behaviour |
| [docs/EVDS_SOURCE.md](docs/EVDS_SOURCE.md) | How EVDS is accessed and what its catalog declares: frequencies, aggregation flags, archived and base-year variants |
| [docs/DATABASE.md](docs/DATABASE.md) | The database definition deliverable: every table, column, invariant and the layout on disk |
| [src/kkb_agent/](src/kkb_agent/) | Core/input and safe-fetch boundaries, lakehouse/database, llm, agent, analytics and four tools; ARCHITECTURE describes their limits |
| `web/` (not yet created) | Next.js client under DEC-123; lives outside the Python package |
| [tests/unit/](tests/unit/) | Targeted contract, input, lakehouse, orchestration, workspace and verifier tests; observed results live in ROADMAP |
| [tests/fixtures/ingestion/](tests/fixtures/ingestion/) | Synthetic CSV and XLSX fixtures with their documented expected parsing |
| M9 / [EVALUATION](docs/EVALUATION.md) | Benchmark plan; Day 0 drafts are local-stash-only, no delivered scoring runner |
| [scripts/check_secrets.py](scripts/check_secrets.py) | Lightweight local file pattern scan; not a history scanner |
| [scripts/generate_xlsx_fixtures.py](scripts/generate_xlsx_fixtures.py) | Deterministic regeneration of the synthetic XLSX fixtures |
| [.github/workflows/fast-pr.yml](.github/workflows/fast-pr.yml) | Fast PR gate on pull requests targeting `dev` |
| [Makefile](Makefile), [pyproject.toml](pyproject.toml) | Setup and check targets, Python >=3.12 dependencies |
| [.env.example](.env.example), [.gitignore](.gitignore) | Blank local configuration template and ignore rules for credentials, private data and generated output |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | Legacy setup examples; the current branch/workflow rules in AGENTS and DEC-109 take precedence |

Copy `.env.example` to an ignored `.env` for local configuration; never put a real credential in a tracked file. Private and downloaded data belongs under the ignored `data/` and `uploads/` paths, and storing organizer data at all is a separate unresolved permission question.

## Fast development workflow

For a fresh teammate/session with no conversation history, enter: `Read AGENTS.md and continue with the next READY task.` The [startup protocol](AGENTS.md#new-session--teammate-startup-protocol) uses Git/PR history, latest `dev`, ROADMAP, DECISIONS, and only the relevant technical document. It verifies dependencies and ownership, publishes a claim on a fresh task branch, implements/tests, then updates the same PR into `dev` and stops before merge unless authorized. If a required decision or ownership is unresolved, it reports the blocker rather than guessing.

1. Inspect status/current branch and relevant existing changes.
2. Read DECISIONS, ROADMAP's relevant status/milestone, and one task-relevant technical document. Do not read all docs every prompt.
3. Follow an eligible requested task; for “continue,” take the first unchecked READY task with satisfied dependencies and no active owner/published claim.
4. Start from freshly updated `dev`, create a new task branch, publish its ROADMAP claim and draft PR, and implement only that task. Run targeted checks, update relevant evidence, commit, push, and update the same PR into `dev` for review.

A task is DONE / `[x]` only after its implementation is **merged into `dev`**, required targeted validation passes, and roadmap evidence is updated. Documentation-only tasks need diff/link/status verification plus merge too. Local/feature-branch work stays PARTIAL / IN PROGRESS even after tests or push. Each active task records Status, Owner, Branch, PR, Commit, Tests, Blocker, and Handoff; the [Team Handoff Protocol](docs/ROADMAP.md#team-handoff-protocol) explains visible claims, explicit ownership transfers, and the small post-merge status update. Elapsed time does not release another teammate's claim.

## Commands

Requires Python >=3.12. Run setup when needed, then ordinary quick checks:

```bash
make install-dev
make quick
```

Normal code tasks use targeted tests/lint or `make quick`; task PRs to `dev` use the fast `make pr` gate. `make full` belongs to stable `dev -> main`/final demo checkpoints or explicit requests. Boundary changes still need targeted negative tests. Documentation-only tasks/PRs use diff/link/status checks, not application/security/release checks. [AGENTS](AGENTS.md#validation-tiers-and-speed-limits) owns the gate rules; these command definitions are not claimed passing results.

There is no `eval-smoke`/`eval-full` Make target, benchmark runner, UI launch command, or live Kloudeks transport yet. [EVALUATION](docs/EVALUATION.md#implemented-command-registry) separates existing commands from planned tiers. `make full` does not run a benchmark.

## Branches and collaboration

This is the team's private-repository workflow; verify remote access/settings through authorized setup, never treat privacy as a secret store. `main` is the stable/demo-ready checkpoint branch; `dev` is shared integration. Never implement on or push directly to either branch.

Every meaningful task starts from latest `dev` on its own short-lived branch. Preferred names: `feature/<milestone>-<task>`, `fix/<short-description>`, and `docs/<short-description>`; for example `feature/m1-csv-ingestion`, `feature/m2-frequency-alignment`, or `fix/url-fetch-timeout`. After targeted validation, commit clearly, push the task branch, and open a PR into `dev`. Delete the branch after review and verified merge, once it has no unmerged work. The next task starts from freshly updated `dev`, never from the previous feature branch.

Codex may perform normal fetch/switch/update/branch/commit/push/PR operations for an assigned task. Preserve existing work and use the [Git workflow](AGENTS.md#git-workflow) safety rules. Do not merge your own PR without explicit instruction, force-push shared branches, or branch from unfinished feature work without an explicit documented exception. The PR #1 branch exception was specific to that historical task, not permission to reuse its branch.

Approximately every 3–4 days, or at an important stable milestone, create a `dev -> main` PR only if the integrated state is demo-ready. Run full/release checks there; do not update `main` after every task or promote an unstable candidate to meet a calendar date.

Progress belongs in ROADMAP, reasons in DECISIONS, and missing answers in OPEN_QUESTIONS. If current status conflicts with Git/merged PR evidence, stop automatic selection and reconcile it. Update the owning technical/decision document when its contract changes; leave enough short evidence that another teammate can resume without chat history.
