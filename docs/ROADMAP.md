# 8–9 Day Roadmap

This roadmap is intentionally aggressive. The goal is a strong hidden-test demo, not an enterprise platform.

## Day 0 / bootstrap
- private GitHub repo
- `dev` + `main`
- CI fast gate
- `.env.example`
- Kloudeks adapter interface/stub
- typed core schemas
- synthetic fixtures
- baseline benchmark skeleton

Exit: repository is safe to build in and a smoke test passes.

## Day 1 — data core
- source adapter protocol
- DataContract
- CSV/XLSX ingestion
- basic BDDK/EVDS path after endpoints/data access are confirmed
- profiling: columns, dates, missingness, unit/frequency metadata

Exit: known public datasets can be loaded into a common workspace.

## Day 2 — planner + tool registry
- typed AnalyticalPlan
- tool registry
- constrained plan generation
- schema validation
- bounded repair
- explicit multi-turn workspace

Exit: natural-language query can produce a valid plan and execute a simple query.

## Day 3 — normalization
- time/frequency alignment
- stock/flow aggregation policy
- cumulative-series handling
- units/scales
- derived columns
- provenance for every transformation

Exit: adversarial frequency/unit fixtures pass.

## Day 4 — analytics
- change detection
- anomaly detection
- correlation
- lag analysis
- causality baseline with explicit caveats
- deterministic chart/table outputs

Exit: sample housing-credit analysis can be completed end-to-end without model-generated numbers.

## Day 5 — external source / URL
- safe URL fetch
- HTML
- PDF
- Excel/CSV
- image path only if required/available
- prompt-injection-resistant extraction
- source citations/evidence

Exit: system can add a second external data source to an existing analysis.

## Day 6 — verifier + benchmark
- EvidenceLedger
- critical numeric re-checks
- invalid-plan/tool retry tests
- 50–100 adversarial benchmark cases
- scorecard by failure category

Exit: regressions are measurable, not anecdotal.

## Day 7 — UI + demo reliability
- minimal polished UI
- analysis plan/progress
- tables/charts
- evidence/source panel
- failure messages
- caching and latency cleanup

Exit: demo can be run by someone who did not write the backend.

## Day 8 — hardening / rehearsal
- run full benchmark
- security full check
- eliminate flaky paths
- freeze dependencies
- rehearse hidden-source scenarios
- create `dev -> main` release checkpoint
- demo fallback dataset/cache where allowed

## Optional Day 9
Only fix measured weaknesses.
No architectural rewrites unless a blocker appears.

## Priority cuts if behind schedule
Cut in this order:
1. fancy UI
2. exotic file formats
3. fine-tuned router
4. advanced causality methods
5. deep observability
6. extra agents

Do NOT cut:
- typed plans
- data contracts
- frequency/unit correctness
- evidence/provenance
- safe external input handling
- benchmark/regression tests
