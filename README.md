# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. A custom Python
harness interprets questions, validates plans and runs deterministic financial
tools; results retain source, transformation and verification evidence. The local
session API and Next.js client expose canonical tables and immutable history,
including follow-ups bound to a selected result.

## Start or resume

Read [AGENTS](AGENTS.md), then [ROADMAP current status](docs/ROADMAP.md#current-project-status).
Inspect Git and open claims before choosing work. [Documentation guide](docs/DOCUMENTATION.md)
explains which document owns each question and links the technical references.
A fresh checkout contains no prepared official data or credentials.

For development, use Python >=3.12:

```bash
make install-dev
make quick
```

For the local application, follow [LOCAL_CLIENT](docs/LOCAL_CLIENT.md): start Python
and Next.js in two terminals, then open http://127.0.0.1:3000/.
[PREPARED_API](docs/PREPARED_API.md) owns read-only readiness, pool/catalog setup and
backend limits; [its command reference](docs/PREPARED_API.md#development-and-live-check-commands)
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
scripted and live evidence. Vector infrastructure does not establish live semantic
retrieval acceptance.

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

## Repository guide

See [the documentation inventory and repository paths](docs/DOCUMENTATION.md).
Historical handbacks live in [HISTORY](docs/HISTORY.md) or the immutable Git links
it retains; they are not current startup instructions.
