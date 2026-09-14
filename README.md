# KKB Agentic Analytics

An evidence-backed financial-data analyst for the KKB Hackathon. The intended product accepts supported data sources and questions, produces a typed analytical plan, computes results with deterministic Python tools, and presents answers/tables/charts with source, transformation, and verification evidence. Follow-up questions use an explicit analysis workspace.

The repository contains an offline end-to-end analysis path: guarded CSV/XLSX input and bounded direct-GET safe fetch, DuckDB/Parquet storage and financial semantics, typed analytical results, validated planning/tool execution, persisted workspace values and multi-result answer verification. Eight callable factories exist: `catalog_search`, `table_transform` (deflate/add_series) and the six brief tools (search is offline-only): `lakehouse`, `change_detection` (comparison), `anomaly`, `causality` (association, lag and Granger precedence), `web_search` with an explicitly injected backend, and `web_url` for a CSV/XLSX table, a PDF's text and ruled tables, or bounded static HTML text/tables at an address the user wrote, with one named cell answerable through the gate. The composed tests use synthetic data and a scripted model. Scoped BDDK/EVDS ingestion adapters and the prepared official dataset, CSV profiling, full proof/replay, breakpoint detection, production `web_search`, `web_url`'s JavaScript-rendered/image-address extraction, full hybrid/catalog coverage, UI and deployment remain incomplete. [ROADMAP Current Project Status](docs/ROADMAP.md#current-project-status) is the single delivery and next-task summary.

The [DEC-135](docs/DECISIONS.md#dec-135--planner-actions-and-mandatory-correctness-harness) target is eight planner-callable tools: the six brief tools, `catalog_search` and `table_transform`; all eight factories are implemented (`table_transform` exposes `deflate` and `add_series`). Series inspection, observation quality and applicable source reconciliation are mandatory harness capabilities whose automatic wiring remains future work. `web_search` requires an operator-injected `SearchBackend`; production provider selection and live acceptance remain blocked. See the [status table](docs/ARCHITECTURE.md#approved-tool-surface) and [task mapping](docs/ROADMAP.md#product-tool-delivery-order).

## Constraints and architecture

Python is the backend/analytics language; delivered runtime LLM access uses Kloudeks only. DuckDB/Parquet and Pandas are confirmed, with custom bounded orchestration and a DuckDB workspace/lineage graph. Material calculations are deterministic, unknown semantics stay explicit, and external/model content remains untrusted. BDDK/EVDS are intended thin preparation/ingestion adapters; the analytical core remains source-independent. No Snowflake or third-party hosted LLM services. The `openai` SDK is permitted only as a client exclusively configured for Kloudeks; [DEC-129](docs/DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) owns the official endpoints, MIA-key authentication, confirmed text/vision, embedding and OCR models, and the literal OCR/embedding request contracts. A bounded transport ([llm/kloudeks.py](src/kkb_agent/llm/kloudeks.py)) sends the key only to that endpoint; it is tested offline, passed one authorized live smoke for chat and embedding (M4-12), and carried one live question end to end on synthetic data (M4-15). Native tool/JSON support is not assumed. [DEC-131](docs/DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) records the organizer calendar (development closes **20 September 2026**, Final Day **17 October 2026**), delivery by private-repository access, the expectation of a live deployed solution, and prompt-supplied URL documents as required demo-day scope.

Primary hackathon path under the [DEC-137 dated refinement](docs/DECISIONS.md#dec-137-prepared-pool-refinement):

```text
PREPARATION (approved official-source access)
  BDDK / EVDS -> trusted reusable ingestion adapters -> raw bronze snapshots
  -> validation / normalization -> silver observations -> required gold datasets
  -> prepared DuckDB + Parquet lakehouse

DEMO RUNTIME TARGET
  user -> planner -> catalog_search -> trusted prepared series -> lakehouse
  -> guarded transforms / analytics -> mandatory correctness harness -> verifier
  -> accepted workspace publication + answer / table / chart / evidence
  prepared-pool miss or unresolved meaning -> clarification / abstention
```

This is intended demo routing, not completed automatic integration or dataset acceptance. Required semantic/quality checks run before dependent use. The primary structured BDDK/EVDS path reads prepared **silver** canonical observations or appropriate trusted **gold** materializations; **bronze** is immutable source evidence, not direct analytical truth. All three are lakehouse layers. Normal demo financial analysis does not require question-time official-source fetching; Kloudeks planning and future query embeddings have separate model connectivity requirements.

The first real **2021-01–2026-06** housing-credit balance, housing/mortgage rate, CPI/TÜFE and national KFE vertical slice is still unprepared and is not the final pool scope. After it works end to end, expand relevant BDDK/EVDS structured financial coverage as safely practical. Unknown semantics, ambiguous identities and unsupported calendars remain explicit; do not promise every source byte. Source-use, retention and deployment questions remain open.

M3-05's bounded monthly selector/metadata slice and M3-06's reusable offline Monthly ingestion slice are delivered; both overall tasks remain PARTIAL. M3-06 binds all raw months in a manifest, publishes silver/lineage atomically, repeats identical batches as no-ops and refuses changed bytes/ranges/contracts without silently overwriting history. Live BDDK/CA acceptance and real prepared data remain unfinished; EVDS ingestion is not delivered. Adapters primarily **build the prepared pool**, with controlled refresh an intended reuse, not a one-off housing script.

DEC-137's catalog-known cache-miss → policy-approved official adapter → validate/materialize/version → reuse lakehouse branch remains a **future scalability extension**, not an organizer core three-turn prerequisite. Sophisticated refresh/vintage orchestration and object-storage optimization are later work. Prepared-pool misses may clarify/abstain; they confer no generic web fallback authority.

DuckDB + Parquet owns the financial lakehouse and analytical data; raw bronze bytes are content-addressed artifacts with lakehouse metadata. A distinct intended **vector DB/index layer** stores/indexes/searches catalog embeddings only. It never stores BDDK/EVDS financial observations. Local persistent storage is the near-term data path; S3-compatible optimization remains future work, not a selected provider. Uploads and authorized URL documents remain session artifacts.

`web_search` stays separate general web discovery: SearXNG is the preferred compatibility candidate, with no production integration/live acceptance; self-hosting may still send queries upstream and requires organizer/network/privacy confirmation. `web_url` keeps its current specific supplied/authorized URL path. Crawl4AI is only an optional future dynamic/JS extraction candidate, subject to all existing safety/evidence controls. A search result never automatically authorizes fetching.

The answer gate binds numbers to typed results, checks scale/period contradictions, resolves preserved input references and can reread identified values from the store. It withholds unsupported sentences and can abstain. Workspace result digests and stale-read rejection preserve prior values across turns; they do not prove independent recomputation, complete run/input provenance or replay. [ARCHITECTURE](docs/ARCHITECTURE.md) separates implemented boundaries from confirmed targets and remaining gaps.

Retrieval's initial hybrid baseline is Turkish normalization, reviewed alias/concept-family mapping, metadata filtering, lexical/BM25 and the organizer's Qwen3-Embedding-8B dense retrieval, with a separate intended catalog vector-search layer under DEC-137. LanceDB is the selected catalog vector index ([DEC-138](docs/DECISIONS.md#dec-138--handback-priorities-lancedb-catalog-index-and-no-prepared-data-in-git)) with a [bounded local storage/search slice](docs/CATALOG_INDEX.md) now implemented; live embedding policy and semantic-quality acceptance remain pending ([DEC-130](docs/DECISIONS.md#dec-130--initial-hybrid-retrieval-baseline); DEC-127/115 are superseded). The confirmed model is `kkbhackathon2026/Qwen3-Embedding-8B`, measured at 4096 dimensions. Dense retrieval is required for the final hybrid target; catalog_search accepts an operator-configured combined stage and otherwise uses reviewed aliases, filters and bounded BM25. Live embedding policy and hybrid-quality evaluation remain pending. Vectors describe catalog concepts, not financial observation values. The final conceptual path combines BM25 candidates and Qwen query-embedding/vector-similarity candidates with metadata filters into a bounded candidate set; it does not require a PostgreSQL/pgvector service. Benchmarks compare lexical-only, dense-only and combined quality/latency/failures; dense use does not wait for lexical failure. RRF, reranking and extra infrastructure require measured benefit. Direct retrieval and catalog-bounded relationship discovery remain separate evaluation paths.

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
| [src/kkb_agent/](src/kkb_agent/) | Core/input and safe-fetch boundaries, lakehouse/database, llm, agent, analytics and seven tool factories; ARCHITECTURE describes their limits |
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

Copy `.env.example` to an ignored `.env` for local configuration; never put a real credential in a tracked file. Private and downloaded data belongs under the ignored `data/` and `uploads/` paths, with source access, caching/retention and redistribution permissions still governed by Q-DATA-01/03; DEC-136 is the preparation architecture, not a permission grant.

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

On Windows, after creating `.venv` and installing `.[dev]`, run the same fast PR checks with `.\.venv\Scripts\python.exe scripts/check_windows.py`. The script uses the same interpreter for every check, needs no PowerShell execution-policy change, enables UTF-8 for Turkish fixtures, and stops at the first failed check. It makes no live model/source calls. `.gitattributes` preserves the two reviewed source inventories' LF hashes and all test fixtures' exact bytes on checkout.

Without Windows symbolic-link creation privilege, the real symlink fixture reports a skip; missing-root rejection still runs. POSIX file-mode assertions apply on POSIX only; on Windows, use an operator-owned private staging directory with appropriate Windows ACLs. Source-fetch supervision observes connection progress on both platforms without changing connection or total-time budgets.

For opt-in catalog discovery followed by one bounded analysis/clarification plan, add `--catalog docs/catalog/prepared_v2.json` to the prepared rehearsal. See [the continuation contract](docs/CATALOG_CONTINUATION.md). This enables lexical catalog search; real dense-query policy and live selection quality still need acceptance.

Before `live_check --prepared-root`, finish ingestion and close all connections to the prepared lakehouse; keep that root unchanged during the copy. `prepared_copy_failed` means the copy could not be created (for example, a locked file); no model call was made. Close the owning process and use a fresh work directory for a later explicitly authorized rehearsal.

Normal code tasks use targeted tests/lint or `make quick`; task PRs to `dev` use the fast `make pr` gate, including strict `mypy src` (DEC-140). `make full` belongs to stable `dev -> main`/final demo checkpoints or explicit requests. Boundary changes still need targeted negative tests. Documentation-only tasks/PRs use diff/link/status checks, not application/security/release checks. [AGENTS](AGENTS.md#validation-tiers-and-speed-limits) owns the gate rules; these command definitions are not claimed passing results.

There is no `eval-smoke`/`eval-full` Make target, benchmark runner or UI launch command yet. `python -m kkb_agent.llm.smoke` (transport) and `python -m kkb_agent.live_check` (one question end to end on synthetic data) are operator-run live checks, never part of a gate. [EVALUATION](docs/EVALUATION.md#implemented-command-registry) separates existing commands from planned tiers. `make full` does not run a benchmark.

M7-19 adds an explicit document mode to `live_check`. **One live public CSV acceptance passed** ([evidence and limits](docs/EVALUATION.md#m7-19-live-csv-acceptance)). The following is a future operator invocation, not an offline test: it calls Kloudeks and fetches the URL in the question. Use it only after separate approval for that run and an accepted network/source boundary (Q-NET-01/02; Q-DATA where relevant). Supply the actual question, URL, column and row; no address is injected by the command.

```sh
# Only after explicit live-run approval; replace the placeholder question.
( set -a; . ./.env; set +a; python -m kkb_agent.live_check --document --question 'QUESTION CONTAINING THE APPROVED PUBLIC URL AND REQUESTED CELL' )
```

The application reads configuration from `os.environ`, never `.env` itself. The document report contains stage/status/timing, hashed identities, numeric cell coordinates and verification counts, not question/answer/document text or URLs. Exit 0 requires a retained numeric claim bound to the fetched cell with resolvable source/transform lineage; loading a file alone is not success. On `fetch_failed`, the operator-only `fetch_code` reports an existing `FetchCode` or null; TLS and other transport errors remain grouped as `TRANSPORT_FAILURE`. For `not_admitted`/`needs_input`, operator-only `document_code` exposes an allowlisted existing admission/loader code or null. `not_admitted` alone does not identify whether admission or parsing failed. No raw failure text is exported. The existing no-argument synthetic mode is unchanged. CSV/XLSX/text-layer PDF and bounded static HTML tables/text are supported. M7-11 offers explicitly injected untrusted OCR text only; the operator command does not enable it. JavaScript rendering and image-address loading are unsupported. Only the separately recorded public CSV live acceptance has passed.

## Branches and collaboration

This is the team's private-repository workflow; verify remote access/settings through authorized setup, never treat privacy as a secret store. `main` is the stable/demo-ready checkpoint branch; `dev` is shared integration. Never implement on or push directly to either branch.

Every meaningful task starts from latest `dev` on its own short-lived branch. Preferred names: `feature/<milestone>-<task>`, `fix/<short-description>`, and `docs/<short-description>`; for example `feature/m1-csv-ingestion`, `feature/m2-frequency-alignment`, or `fix/url-fetch-timeout`. After targeted validation, commit clearly, push the task branch, and open a PR into `dev`. Delete the branch after review and verified merge, once it has no unmerged work. The next task starts from freshly updated `dev`, never from the previous feature branch.

Codex may perform normal fetch/switch/update/branch/commit/push/PR operations for an assigned task. Preserve existing work and use the [Git workflow](AGENTS.md#git-workflow) safety rules. Do not merge your own PR without explicit instruction, force-push shared branches, or branch from unfinished feature work without an explicit documented exception. The PR #1 branch exception was specific to that historical task, not permission to reuse its branch.

Approximately every 3–4 days, or at an important stable milestone, create a `dev -> main` PR only if the integrated state is demo-ready. Run full/release checks there; do not update `main` after every task or promote an unstable candidate to meet a calendar date.

Progress belongs in ROADMAP, reasons in DECISIONS, and missing answers in OPEN_QUESTIONS. If current status conflicts with Git/merged PR evidence, stop automatic selection and reconcile it. Update the owning technical/decision document when its contract changes; leave enough short evidence that another teammate can resume without chat history.

M10 starts with the [operator-flow specification](docs/OPERATOR_FLOW.md): source selection, question, progress, gated answer, evidence, follow-up and recovery. FastAPI/SSE, executable API schemas and the Next.js UI are still unimplemented; this is not an API startup command.
