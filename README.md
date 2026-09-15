# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. A custom Python
harness interprets questions, validates plans and runs deterministic financial
tools; results retain source, transformation and verification evidence. The local
session API and Next.js client expose canonical tables and immutable history,
including follow-ups bound to a selected result.

## Start or resume

Read [AGENTS](AGENTS.md), then [ROADMAP current status](docs/ROADMAP.md#current-project-status).
Inspect Git and open claims before choosing work. [Documentation map](#documentation-map)
explains which document owns each question and links the technical references.
A fresh checkout contains no prepared official data or credentials.

For development, use Python >=3.12:

```bash
make install-dev
make quick
```

For the local application, follow [OPERATIONS](docs/OPERATIONS.md#local_client-datatrio-local-analysis-workspace): start Python
and Next.js in two terminals, then open http://127.0.0.1:3000/.
[OPERATIONS](docs/OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) owns read-only readiness, pool/catalog setup and
backend limits; [its command reference](docs/OPERATIONS.md#prepared_api-development-and-authorized-live-check-commands)
preserves Windows checks and explicitly authorized live-check/recovery instructions.
Startup/readiness is not live-model acceptance. Never commit credentials or
prepared data; source/model requests require their existing authorization.

## Constraints and architecture

Runtime LLM access is Kloudeks-only; Python tools perform material calculations.
External documents, metadata and model output remain untrusted. Unknown financial
semantics stay explicit. Our analytical lakehouse is DuckDB + Parquet with our
Bronze/Silver/Gold, ingestion and provenance; LanceDB indexes catalog descriptions
and identities, never financial observations.

The prepared path supports reviewed BDDK/EVDS data, catalog discovery, deterministic
analysis, bounded deflation/add-series transforms, table co-movement and mandatory
configured metadata inspection. [ARCHITECTURE](docs/ARCHITECTURE.md) owns runtime
mechanics and distinguishes supported slices from targets; [CATALOG](docs/CATALOG.md)
owns retrieval contracts. [ROADMAP](docs/ROADMAP.md#current-project-status) owns
completion and remaining work; [EVALUATION](docs/EVALUATION.md) separates synthetic,
scripted and live evidence. Catalog retrieval is lexical by default and hybrid
(lexical + Qwen dense, DEC-142) when the API is started with a local catalog index;
retrieval quality is measured on reviewed cases, not yet in a live served turn.

Reuse means adding **supported financial sources/schemas** through reviewed metadata
and adapter/policy work without rewriting the shared core. It does not promise
arbitrary domains. The [organizer maturity chain](docs/ARCHITECTURE.md#organizer-maturity-chain)
connects catalog, preparation, analysis, stateful follow-up and financial-source reuse.
[DECISIONS](docs/DECISIONS.md) preserves organizer provenance and rationale, including
the 20 September 2026 development deadline and 17 October 2026 Final Day.

## Fast development workflow

Use [AGENTS startup and task lifecycle](AGENTS.md#new-session--teammate-startup-protocol).
It owns fresh branches/claims, appropriate checks, PRs into dev, explicit merge
authorization and safe cleanup. No direct implementation on dev/main; preserve
existing work and stashes. [Gate rules](AGENTS.md#validation-tiers-and-speed-limits)
and the [implemented command registry](docs/EVALUATION.md#implemented-command-registry)
distinguish available commands from planned benchmarks.

The [MVP sprint rules](AGENTS.md#mvp-sprint-acceleration--scope-and-quality-retained)
accelerate the path by using targeted checks while editing and one broad PR gate
per final code-bearing revision. They do not cut broad source coverage, production
search, OCR, proof UI, general transforms, refresh/vintage lifecycle, hybrid
retrieval or benchmark/rehearsal delivery, and they do not weaken correctness or
security controls.

## Documentation map

| Principal document | Authority |
| --- | --- |
| [README](README.md) | Product overview, quickstart and this map |
| [AGENTS](AGENTS.md) | Engineering workflow and task/PR lifecycle |
| [ROADMAP](docs/ROADMAP.md#current-project-status) | Current delivery, owners, next tasks and labelled task history |
| [DECISIONS](docs/DECISIONS.md) | Decisions/provenance, [Open Questions](docs/DECISIONS.md#open-questions) and answered records |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Runtime flow, component/API/profile contracts and mandatory harness wiring |
| [DATABASE](docs/DATABASE.md) | Storage schema, invariants and disk layout |
| [SOURCES](docs/SOURCES.md) | BDDK/EVDS evidence register, acquisition, identity and financial/source semantics |
| [CATALOG](docs/CATALOG.md) | Reviewed mappings, lexical/vector retrieval and bounded continuation |
| [OPERATIONS](docs/OPERATIONS.md) | Environment, preparation, backend/frontend startup, API use and recovery |
| [SECURITY](docs/SECURITY.md) | Trust boundaries, admission/storage/HTTP controls and verification requirements |
| [EVALUATION](docs/EVALUATION.md) | Tests, measured/scripted/live acceptance and documentation migration evidence |

Five BDDK/EVDS Markdown files remain byte-pinned source evidence, listed with
their individual reasons in [SOURCES](docs/SOURCES.md#bddk-and-evds-evidence-register).
The small OPEN_QUESTIONS file is only a compatibility redirect for links embedded
in that immutable evidence. INGESTION_PROFILE likewise preserves links from the
unchanged fixture explanations; its actual contract/examples have moved.
Three fixture explanations remain beside their fixtures. These exceptions are not additional current-status owners.

## Repository paths

| Path | Purpose / current scope |
| --- | --- |
| [src/kkb_agent/](src/kkb_agent) | Core/input and safe-fetch boundaries, lakehouse/database, llm, agent, analytics and the registered tool factories; ARCHITECTURE describes their limits |
| `web/` | Next.js local client under DEC-123; [run instructions](docs/OPERATIONS.md#local_client-datatrio-local-analysis-workspace), separate from Python analytics |
| [tests/unit/](tests/unit) | Targeted contract, input, lakehouse, orchestration, workspace and verifier tests; observed results live in ROADMAP |
| [tests/fixtures/ingestion/](tests/fixtures/ingestion) | Synthetic CSV and XLSX fixtures with their documented expected parsing |
| M9 / [EVALUATION](docs/EVALUATION.md) | Benchmark plan; Day 0 drafts are local-stash-only, no delivered scoring runner |
| [scripts/check_secrets.py](scripts/check_secrets.py) | Lightweight local file pattern scan; not a history scanner |
| [scripts/generate_xlsx_fixtures.py](scripts/generate_xlsx_fixtures.py) | Deterministic regeneration of the synthetic XLSX fixtures |
| [.github/workflows/fast-pr.yml](.github/workflows/fast-pr.yml) | Fast PR gate on pull requests targeting `dev` |
| [Makefile](Makefile), [pyproject.toml](pyproject.toml) | Setup and check targets, Python >=3.12 dependencies |
| [.env.example](.env.example), [.gitignore](.gitignore) | Blank local configuration template and ignore rules for credentials, private data and generated output |

Copy `.env.example` to an ignored `.env` for local configuration; never put a real credential in a tracked file. Private and downloaded data belongs under the ignored `data/` and `uploads/` paths, with source access, caching/retention and redistribution permissions still governed by Q-DATA-01/03; DEC-136 is the preparation architecture, not a permission grant.
