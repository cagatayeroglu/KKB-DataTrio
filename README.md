# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. The intended product accepts supported data sources and questions, produces a typed analytical plan, computes results with deterministic Python tools, and presents answers/tables/charts with source, transformation, and verification evidence. Follow-up questions use an explicit analysis workspace.

**Current state:** Day 0 foundation, not a runnable end-to-end analyst. [PR #1](https://github.com/cagatayeroglu/KKB-DataTrio/pull/1) merged the execution/workflow documentation into `dev` at `fe5d44a`. The 11 Day 0 core/provider/evaluation/fixture/test files remain only in a verified local stash, excluded from documentation delivery; a fresh clone does not contain them. No passing application validation was established. See [current status and next safe tasks](docs/ROADMAP.md#current-project-status), including local recovery details, for the authoritative handoff.

## Constraints and architecture

Python is the primary backend/analytics language. Delivered runtime LLM access uses Kloudeks only; no third-party runtime LLM API or Snowflake. BDDK/EVDS are intended adapters, not assumptions embedded in the core. Material calculations are deterministic, unknown semantics stay explicit, and external/model content is untrusted.

```text
Question + explicit workspace
  -> Kloudeks planner -> typed plan / validated registered tools
  -> guarded source ingestion -> contract / explicit normalization
  -> deterministic analytics -> verifier
  -> answer + table/chart + source/transformation/validation evidence
```

This is the target flow; most runtime components remain to be built. Framework, analytical engine, frontend, persistence, exact model, and causality method remain unresolved. See [architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md).

## Repository guide

| Path | Purpose / current scope |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Coding-agent scope, targeted reading, validation, Git authorization, handoff rules |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Main execution truth: relative days, M0–M11, checkboxes, READY queue, evidence/handoffs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component boundaries, contracts, state, data flow, failure behavior |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Metrics, benchmark tiers, adversarial cases, scorecard plan |
| [docs/SECURITY.md](docs/SECURITY.md) | Required controls for enabled boundaries and their validation |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Confirmed constraints/decisions, proposals, deferred choices |
| [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) | Actionable organizer/team unknowns, owners, evidence, blockers |
| [src/kkb_agent/](src/kkb_agent/) | Package; in-progress core/provider/evaluation scaffolding |
| [tests/unit/](tests/unit/) | Package smoke plus in-progress Day 0 unit tests |
| `benchmarks/cases/` (local stash only) | Three synthetic questions, excluded from documentation delivery; no numerical scoring runner yet |
| [scripts/check_secrets.py](scripts/check_secrets.py) | Lightweight local file pattern scan; not a history scanner |
| [Makefile](Makefile), [pyproject.toml](pyproject.toml) | Existing setup/check targets and Python >=3.12 dependencies |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | Legacy setup examples; the current branch/workflow rules in AGENTS and DEC-109 take precedence |

This checkout currently lacks `.gitignore`, `.env.example`, and `.github/` workflows. Their implementation/validation is tracked in M0. Do not store real credentials or private data in repository files while assuming ignore rules exist.

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
