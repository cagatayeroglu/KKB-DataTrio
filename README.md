# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. The intended product accepts supported data sources and questions, produces a typed analytical plan, computes results with deterministic Python tools, and presents answers/tables/charts with source, transformation, and verification evidence. Follow-up questions use an explicit analysis workspace.

**Current state:** Day 0 foundation, not a runnable end-to-end analyst. On the 2026-09-08 inspected `feature/day0-core` checkout, core schemas/protocols, a non-networking Kloudeks stub, and three benchmark fixture cases are local/untracked work, excluded from the documentation commit. A fresh clone does not contain these files or the three new Day 0 unit tests. No passing application validation was established during the documentation update. See [current status and next safe tasks](docs/ROADMAP.md#current-project-status) for the authoritative handoff.

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
| `benchmarks/cases/` (local only) | Three untracked synthetic questions, excluded from documentation delivery; no numerical scoring runner yet |
| [scripts/check_secrets.py](scripts/check_secrets.py) | Lightweight local file pattern scan; not a history scanner |
| [Makefile](Makefile), [pyproject.toml](pyproject.toml) | Existing setup/check targets and Python >=3.12 dependencies |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | Legacy manual setup examples; not proof of remote settings/CI or standing Git authorization |

This checkout currently lacks `.gitignore`, `.env.example`, and `.github/` workflows. Their implementation/validation is tracked in M0. Do not store real credentials or private data in repository files while assuming ignore rules exist.

## Fast development workflow

1. Inspect status/current branch and relevant existing changes.
2. Read DECISIONS, ROADMAP's relevant status/milestone, and one task-relevant technical document. Do not read all docs every prompt.
3. Follow the requested task; for “continue,” take the first eligible unchecked READY task with satisfied dependencies.
4. Make a small coherent change, run targeted tests/touched-code lint, and record concise evidence plus the next task in that milestone only.

A task can be checked only after implementation **and** relevant validation pass. Document-only tasks need diff/link/status verification. Partial work stays unchecked with a specific next action. [Team Handoff Protocol](docs/ROADMAP.md#team-handoff-protocol) supports three rotating lanes without a long report after every edit.

## Commands

Requires Python >=3.12. Run setup when needed, then ordinary quick checks:

```bash
make install-dev
make quick
```

`make pr` is the requested feature-to-dev gate. `make full` is for [defined boundary/release gates](AGENTS.md#validation-tiers-and-speed-limits) or explicit requests, not ordinary edits. Documentation-only work does not require application/security checks. The command definitions exist; this README does not claim they have passed on the current branch.

There is no `eval-smoke`/`eval-full` Make target, benchmark runner, UI launch command, or live Kloudeks transport yet. [EVALUATION](docs/EVALUATION.md#implemented-command-registry) separates existing commands from planned tiers. `make full` does not run a benchmark.

## Branches and collaboration

`dev` is integration; `main` is demo-stable. Authorized feature branches use `feature/...` or `codex/...` and PRs to `dev`; release checkpoints go `dev -> main`. Follow explicit task instructions to stay on the current branch. Agents do not commit, push, merge, delete branches, or alter repository settings without explicit authorization.

Progress belongs in ROADMAP, reasons in DECISIONS, and missing answers in OPEN_QUESTIONS. Keep technical docs current when contracts change; leave enough short evidence that another teammate can resume without chat history.
