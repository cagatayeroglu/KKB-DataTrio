# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. The intended product accepts supported data sources and questions, produces a typed analytical plan, computes results with deterministic Python tools, and presents answers/tables/charts with source, transformation, and verification evidence. Follow-up questions use an explicit analysis workspace.

**Current state:** foundation only, not a runnable end-to-end analyst. `dev` contains the minimal core contracts, the file admission policy, XLSX sheet discovery and a bounded XLSX loader, with synthetic CSV and XLSX fixtures; `make pr` passes with 245 tests. There is no lakehouse, catalog, CSV loader, profiler, provider, planner, tool, verifier or UI yet. The architecture and technology stack were frozen on 2026-09-09 and are recorded as decisions; none of it is built. Day 0 provider and evaluation drafts remain in a local stash that a fresh clone does not contain. See [current status and next safe tasks](docs/ROADMAP.md#current-project-status) for the authoritative handoff.

## Constraints and architecture

Python is the primary backend/analytics language. Delivered runtime LLM access uses Kloudeks only; no third-party runtime LLM API or Snowflake. BDDK/EVDS are intended adapters, not assumptions embedded in the core. Material calculations are deterministic, unknown semantics stay explicit, and external/model content is untrusted.

```text
Question + explicit workspace
  -> Kloudeks planner -> typed plan / validated registered tools
  -> guarded source ingestion -> contract / explicit normalization
  -> deterministic analytics -> verifier
  -> answer + table/chart + source/transformation/validation evidence
```

This is the target flow; most runtime components remain to be built.

The stack is decided (DEC-112 through DEC-126) and no longer open to preference:

| Layer | Choice |
| --- | --- |
| Storage and analytics | DuckDB over Parquet, bronze/silver/gold; Pandas for transformation |
| Spreadsheets | calamine for sources we retrieved; the bounded openpyxl loader for anything a user, model or URL names |
| Orchestration | Our own planner -> router -> executor -> verifier state machine; no framework |
| Retrieval | LanceDB and DuckDB FTS fused with RRF, listwise reranking, a hand-written alias dictionary |
| State | Artifact DAG persisted in DuckDB; adding a column adds a node |
| Provenance | Typed lineage graph in DuckDB, traversed with networkx; a cell without lineage is a defect |
| Statistics | statsmodels, ruptures, scipy — association with stated limits, never a causal claim |
| API and UI | FastAPI with SSE; Next.js, Tailwind, shadcn/ui, TanStack Table, react-plotly.js, React Flow |
| Deployment | One VM, Docker Compose, Caddy |

Excluded regardless of merit: Spark, Airflow, dbt, Kubernetes, Elasticsearch, Neo4j, LangChain, Celery, Redis, Prophet, PyOD, and anything requiring a Java runtime. Adding a dependency needs its own decision entry.

Still externally blocked: the Kloudeks endpoint, authentication, model identifiers and structured-output support; the embedding and vision models; network egress at demo time; live source access; and the runtime environment, which can override the deployment choice. See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md) and [open questions](docs/OPEN_QUESTIONS.md).

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
| [src/kkb_agent/](src/kkb_agent/) | Package. Delivered: `core/models.py`, `ingestion_policy.py`, `xlsx_sheets.py`, `xlsx_loader.py`, `_xlsx_package.py`. Planned packages under DEC-125: `app`, `agent`, `tools`, `ingest`, `transform`, `catalog`, `lineage`, `llm`, `eval` |
| `web/` (not yet created) | Next.js client under DEC-123; lives outside the Python package |
| [tests/unit/](tests/unit/) | 245 passing unit tests across contracts, admission, fixtures and the XLSX loader |
| [tests/fixtures/ingestion/](tests/fixtures/ingestion/) | Synthetic CSV and XLSX fixtures with their documented expected parsing |
| `benchmarks/cases/` (local stash only) | Three synthetic questions, not delivered; no numerical scoring runner yet |
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

`main` is the stable/demo-ready checkpoint branch; `dev` is shared integration. Never implement on or push directly to either branch.

Every meaningful task starts from latest `dev` on its own short-lived branch. Preferred names: `feature/<milestone>-<task>`, `fix/<short-description>`, and `docs/<short-description>`; for example `feature/m1-csv-ingestion`, `feature/m2-frequency-alignment`, or `fix/url-fetch-timeout`. After targeted validation, commit clearly, push the task branch, and open a PR into `dev`. Delete the branch after review and verified merge, once it has no unmerged work. The next task starts from freshly updated `dev`, never from the previous feature branch.

Codex may perform normal fetch/switch/update/branch/commit/push/PR operations for an assigned task. Preserve existing work and use the [Git workflow](AGENTS.md#git-workflow) safety rules. Do not merge your own PR without explicit instruction, force-push shared branches, or branch from unfinished feature work without an explicit documented exception. The PR #1 branch exception was specific to that merged task; the bootstrap documentation uses fresh `docs/team-handoff-protocol` from updated `dev`.

Approximately every 3–4 days, or at an important stable milestone, create a `dev -> main` PR only if the integrated state is demo-ready. Run full/release checks there; do not update `main` after every task or promote an unstable candidate to meet a calendar date.

Progress belongs in ROADMAP, reasons in DECISIONS, and missing answers in OPEN_QUESTIONS. Keep technical docs current when contracts change; leave enough short evidence that another teammate can resume without chat history.
