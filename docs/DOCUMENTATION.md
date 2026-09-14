# Documentation guide and consolidation ledger

Start with [README](../README.md) for setup and [AGENTS](../AGENTS.md) for the
Git/task workflow. Do not read every reference to select one task.

## Authority model

| Owner | Question it answers |
| --- | --- |
| [AGENTS](../AGENTS.md) | How do we contribute, claim, validate, review and clean up? |
| [README](../README.md) | What is the product and how do I start? |
| [ROADMAP](ROADMAP.md#current-project-status) | What is DONE/PARTIAL/READY/BLOCKED, owned and next? |
| [ARCHITECTURE](ARCHITECTURE.md) | How does the current runtime work; what is a target? |
| [DECISIONS](DECISIONS.md) | What was decided, why, and what alternatives were rejected? |
| [EVALUATION](EVALUATION.md) | What was tested/measured, on which revision, with which limits? |
| [SECURITY](SECURITY.md) | What trust controls apply and how are they verified? |
| [OPEN_QUESTIONS](OPEN_QUESTIONS.md) | Which organizer/team/external answers remain unresolved? |

Other references own detailed contracts, source evidence, runbooks or history.
Link to these owners instead of copying a completion summary. A task record may
retain concise test/merge evidence required by AGENTS; detailed run records belong
in EVALUATION. Historical wording is never silently upgraded to current truth.
The [maturity chain](ARCHITECTURE.md#organizer-maturity-chain) has one owner.

## Reference inventory and disposition

Inventory baseline: 28 tracked Markdown files at dev `9ceab06`. Five source
references are byte-pinned by catalog evidence/tests and LF policy; retain them
unchanged. Their dated review scope is not a current delivery claim.

| File or cluster | Role / unique content | Disposition |
| --- | --- | --- |
| Eight authority files above | Workflow, overview, delivery, structure, rationale, evidence, controls, unknowns | KEEP; remove conflicting summaries and link owners |
| CATALOG_SEARCH, CATALOG_INDEX, CATALOG_CONTINUATION, CATALOG_MAPPING | BM25/ambiguity; local vector identity/storage; bounded replan; exact aliases/IDs and review provenance | MERGE technical content into CATALOG; dated validation into EVALUATION; map below |
| [BDDK_SOURCE](BDDK_SOURCE.md) | Dated transport/payload/units/cumulative evidence | KEEP byte-identical source evidence |
| [BDDK_MONTHLY_METADATA](BDDK_MONTHLY_METADATA.md) | Selector identity, metadata, idempotency/conflict and live preparation evidence | KEEP byte-identical source evidence |
| [EVDS_SOURCE](EVDS_SOURCE.md) | Dated endpoints, real series versus groups, frequencies/archive/base variants | KEEP byte-identical source evidence |
| [EVDS_SERIES_METADATA](EVDS_SERIES_METADATA.md) | Reviewed four-series metadata and parser quirks | KEEP byte-identical source evidence |
| [EVDS_COVERAGE](EVDS_COVERAGE.md) | Reviewed expansion identities, source hash/coverage and preparation | KEEP byte-identical source evidence |
| [DATABASE](DATABASE.md) | Every schema table/column/invariant and disk layout; checked against code | KEEP schema contract |
| [FILE_ADMISSION](FILE_ADMISSION.md) | MIME/extension/content limits and private staging | KEEP security-facing input contract |
| [INGESTION_PROFILE](INGESTION_PROFILE.md) | Loading/profile result fields, unknowns and proposed profiling contract | KEEP; admission and inspection are different stages |
| [SERIES_INSPECTION](SERIES_INSPECTION.md) | Trusted ID/semantic consistency, mandatory producer/SQL checks and receipts | KEEP mechanics; dated validation moves to EVALUATION |
| [LOCAL_API](LOCAL_API.md) | HTTP/session/request/selection/publication and recovery contracts | KEEP; not a startup guide |
| [PREPARED_API](PREPARED_API.md) | Readiness, isolated pool copies, backend startup and authorized live commands | KEEP runbook; measured acceptance moves to EVALUATION |
| [LOCAL_CLIENT](LOCAL_CLIENT.md) | Two-terminal/Windows startup and repeatable synthetic browser rehearsal | KEEP runbook and client recovery contract |
| [OPERATOR_FLOW](OPERATOR_FLOW.md) | Wider UX/proof/SSE target and safe public adapter requirements | KEEP specification; link current behavior/evidence |
| [CSV_EDGE_CASES](../tests/fixtures/ingestion/CSV_EDGE_CASES.md), [XLSX_CASES](../tests/fixtures/ingestion/XLSX_CASES.md) | Synthetic fixture expectations | KEEP byte-identical |
| [Source fixture README](../tests/fixtures/sources/README.md) | Synthetic source fixture provenance/constraints | KEEP byte-identical |
| [HISTORY](HISTORY.md) (new) | Old handbacks and fully answered question evidence | MOVE historical records intact; not active claims |
| [CATALOG](CATALOG.md) (new) | Single detailed catalog/retrieval reference | Replaces four files |
| This guide (new) | Navigation, authority and auditable migration map | KEEP; no second current-status list |

## Per-section migration map

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
| `docs/ROADMAP.md` | Historical handbacks through 2026-09-14 | Preserved | [docs/HISTORY.md#handbacks-2026-09-14](HISTORY.md#handbacks-2026-09-14) |
| `docs/ROADMAP.md` | PR #162 pre-merge claim | Preserved | [docs/HISTORY.md#pr-162-claim](HISTORY.md#pr-162-claim) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-06 — Vector cache/index implementation | Preserved | [docs/HISTORY.md#q-team-06--vector-cacheindex-implementation](HISTORY.md#q-team-06--vector-cacheindex-implementation) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-05 — Workspace persistence and reference storage | Preserved | [docs/HISTORY.md#q-team-05--workspace-persistence-and-reference-storage](HISTORY.md#q-team-05--workspace-persistence-and-reference-storage) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-04 — Causality implementation and prerequisites | Preserved | [docs/HISTORY.md#q-team-04--causality-implementation-and-prerequisites](HISTORY.md#q-team-04--causality-implementation-and-prerequisites) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-03 — Frontend framework | Preserved | [docs/HISTORY.md#q-team-03--frontend-framework](HISTORY.md#q-team-03--frontend-framework) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-02 — Analytical/parsing engine | Preserved | [docs/HISTORY.md#q-team-02--analyticalparsing-engine](HISTORY.md#q-team-02--analyticalparsing-engine) |
| `docs/OPEN_QUESTIONS.md` | Q-TEAM-01 — Orchestration mechanism | Preserved | [docs/HISTORY.md#q-team-01--orchestration-mechanism](HISTORY.md#q-team-01--orchestration-mechanism) |
| `docs/OPEN_QUESTIONS.md` | Q-DEV-01 — Coding assistants during development | Preserved | [docs/HISTORY.md#q-dev-01--coding-assistants-during-development](HISTORY.md#q-dev-01--coding-assistants-during-development) |
| `docs/SERIES_INSPECTION.md` | Validation and limits | Preserved | [docs/EVALUATION.md#prepared-inspection-delivery-evidence](EVALUATION.md#prepared-inspection-delivery-evidence) |
| `docs/PREPARED_API.md` | Measured acceptance and remaining limits | Preserved | [docs/EVALUATION.md#prepared-api-delivery-and-pool-evidence](EVALUATION.md#prepared-api-delivery-and-pool-evidence) |
| `README.md` | Commands | Preserved | [docs/PREPARED_API.md#development-and-live-check-commands](PREPARED_API.md#development-and-live-check-commands) |
| `README.md` | Repository guide | Preserved | [docs/DOCUMENTATION.md#repository-paths](DOCUMENTATION.md#repository-paths) |
| `README.md` | Constraints and architecture | Duplicate architecture/status/evidence summaries; use owners | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| `README.md` | Fast development workflow / Branches and collaboration | Duplicate workflow; use AGENTS | [AGENTS.md](../AGENTS.md) |


<a id="repository-paths"></a>

## Repository paths

| Path | Purpose / current scope |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Coding-agent scope, targeted reading, validation, Git authorization, handoff rules |
| [docs/ROADMAP.md](ROADMAP.md) | Main execution truth: relative days, M0–M13, checkboxes, READY queue, evidence/handoffs |
| [docs/ARCHITECTURE.md](ARCHITECTURE.md) | Component boundaries, contracts, state, data flow, failure behavior |
| [docs/EVALUATION.md](EVALUATION.md) | Metrics, benchmark tiers, adversarial cases, scorecard plan |
| [docs/SECURITY.md](SECURITY.md) | Required controls for enabled boundaries and their validation |
| [docs/DECISIONS.md](DECISIONS.md) | Confirmed constraints/decisions, proposals, deferred choices |
| [docs/OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Actionable organizer/team unknowns, owners, evidence, blockers |
| [docs/FILE_ADMISSION.md](FILE_ADMISSION.md) | Extension/MIME/content checks, limits and staging for uploaded files |
| [docs/INGESTION_PROFILE.md](INGESTION_PROFILE.md) | The ingestion and profile result contract |
| [docs/BDDK_SOURCE.md](BDDK_SOURCE.md) | What the BDDK bulletins publish: transports, parameters, units, measured cumulative behaviour |
| [docs/EVDS_SOURCE.md](EVDS_SOURCE.md) | How EVDS is accessed and what its catalog declares: frequencies, aggregation flags, archived and base-year variants |
| [docs/DATABASE.md](DATABASE.md) | The database definition deliverable: every table, column, invariant and the layout on disk |
| [src/kkb_agent/](../src/kkb_agent/) | Core/input and safe-fetch boundaries, lakehouse/database, llm, agent, analytics and seven tool factories; ARCHITECTURE describes their limits |
| `web/` | Next.js local client under DEC-123; [run instructions](LOCAL_CLIENT.md), separate from Python analytics |
| [tests/unit/](../tests/unit/) | Targeted contract, input, lakehouse, orchestration, workspace and verifier tests; observed results live in ROADMAP |
| [tests/fixtures/ingestion/](../tests/fixtures/ingestion/) | Synthetic CSV and XLSX fixtures with their documented expected parsing |
| M9 / [EVALUATION](EVALUATION.md) | Benchmark plan; Day 0 drafts are local-stash-only, no delivered scoring runner |
| [scripts/check_secrets.py](../scripts/check_secrets.py) | Lightweight local file pattern scan; not a history scanner |
| [scripts/generate_xlsx_fixtures.py](../scripts/generate_xlsx_fixtures.py) | Deterministic regeneration of the synthetic XLSX fixtures |
| [.github/workflows/fast-pr.yml](../.github/workflows/fast-pr.yml) | Fast PR gate on pull requests targeting `dev` |
| [Makefile](../Makefile), [pyproject.toml](../pyproject.toml) | Setup and check targets, Python >=3.12 dependencies |
| [.env.example](../.env.example), [.gitignore](../.gitignore) | Blank local configuration template and ignore rules for credentials, private data and generated output |

Copy `.env.example` to an ignored `.env` for local configuration; never put a real credential in a tracked file. Private and downloaded data belongs under the ignored `data/` and `uploads/` paths, with source access, caching/retention and redistribution permissions still governed by Q-DATA-01/03; DEC-136 is the preparation architecture, not a permission grant.
