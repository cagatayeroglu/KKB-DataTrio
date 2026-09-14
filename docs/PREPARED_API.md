# M10-17 — Run the API over a prepared local pool

This connects [LOCAL_API](LOCAL_API.md) to the existing inspected tools,
`Session.answer`, workspace publication and canonical result projector.
No new financial formula or source fetch is hidden in the HTTP path.

## Check first, without calling a model

From the repository with its virtual environment activated and dependencies
installed (`python -m pip install -e ".[dev]"`):

```powershell
python -m kkb_agent.api --check --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v3.json --env-file .env
```

This reads configuration and the closed prepared pool, validates exact catalog
identity/required semantics, counts stored/non-null observations and reports
each series' first/last stored period. It does not construct a provider, send a
model request, fetch official data, create working copies or open a listener.
Readiness is not live connectivity or coverage completeness. Gaps/revisions and
source truth remain separate correctness concerns.

The optional explicit `--env-file` accepts bounded literal `KLOUDEKS_...=...`
settings with matching quotes or unquoted values and trailing ` # comment`.
It rejects duplicate/malformed settings and files over 64 KiB. It does not run
shell code, interpolate variables or change process environment. File values
take precedence over corresponding environment values. Without this flag,
existing process variables are used; `.env` is not loaded implicitly.
The existing approved Kloudeks host check is mandatory; local service request
timeout must be finite and 1–120 seconds, with 1–3 provider attempts configured.

## Start only when model requests are authorized

```powershell
python -m kkb_agent.api --serve --enable-model-requests --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v3.json --env-file .env --state-root data/processed/api-runs
```

`--enable-model-requests` is an explicit operator enablement, not an organizer
permission or proof of a successful live call. Startup/health still sends no
request; submitting a question uses the real Kloudeks provider. There is no
production fake provider or third-party-host fallback. The CLI always binds
`127.0.0.1`, defaults to port 8000, uses one Uvicorn worker, disables access and
forwarded-header handling, and caps concurrent HTTP connections at 32. Keep
this service local until hosting/authentication is separately implemented.

In addition to `/v1/health`, `/v1/dataset` exposes a bounded copy of the startup
inventory: catalog and prepared counts, observations, file bytes, snapshot and
catalog identities, series labels and recorded periods. It exposes no local
paths, source locators or credentials. Missing configured data returns a fixed
unavailable response. The first [local frontend](LOCAL_CLIENT.md) consumes this inventory and the turn contract.

## Snapshot and session ownership

The operator must close ingestion/other writers before startup. The runtime
validates the pool read-only, hashes its files, then copies it exclusively into
a new process-owned directory under `--state-root`. Before/after hashes detect
ordinary concurrent changes; this is not a transactional snapshot of an active
writer or protection from a malicious OS administrator.

Local absolute roots are required internally. Linked paths/junctions, UNC/network
paths, overlapping source/state roots, WAL/unexpected root files, over-deep
directory layouts and pools carrying another workspace's records are refused.
The pool is limited to 1 GiB / 10,000 files; directory visits are bounded too.
Every prepared series must have a consistent reviewed catalog identity. The
bound follows the catalog rather than a hardcoded list of seven series.
Catalog entries without prepared observations remain discovery candidates;
they never trigger silent source fetching. Larger coverage still requires
reviewed preparation/catalog expansion, not a new question argument.

Each server-issued session gets its own copy of the immutable process seed.
New periods appearing in the original after startup do not silently change
that process's analyses. Updating data requires a new validated startup;
automated refresh/version management remains separate. The original and seed
are never written by the analytical tools. There is no automatic deletion or
retention claim. At the initial worst-case cap, seed plus eight session copies
may need approximately nine times the prepared storage, plus derived results;
the expanded 29-series pool is about 8.13 MiB; the earlier seven-series pool was about 7.26 MiB.

The service's single worker opens/closes a session's connection for each turn.
The runner also refuses accidental concurrent entry. It registers inspected
`lakehouse`, `change_detection`, `anomaly`, `causality`, `table_transform`, plus
`catalog_search` and bounded catalog continuation. This prepared mode exposes
no generic web/search/upload tools or provider/gate settings to the caller.
Free catalog metadata remains continuation data, not SYSTEM instructions;
existing code-reviewed display constants are the only names added to tool
descriptions. Dense live retrieval is not silently enabled by this launcher.

Accepted publications receive server-owned names `analiz_1`, `analiz_2`, etc.
Subsequent plans see their own workspace metadata and may reference these names
for deflation/add-series operations. Earlier immutable results survive. Failed
turns may leave a numbering gap, not a fabricated publication. The runner
passes only an exact owned published result to the public projector.

The launcher also wires the [selected-result backend](LOCAL_API.md#m10-18--selection-admission-and-workspace-resolution-partial).
An explicit API result reference is resolved to its pinned workspace artifact
under the runner lock; mandatory plan/dispatch checks bind supported table
operations to that source, and successful publications record that dependency.
Older unchanged results can be selected. PR #166's browser client now submits
this field when follow-selection is enabled, persisting the original reference
for retries and restoring the exact view on reload. Automated client/bridge
checks and the dated synthetic browser rehearsal pass; live selected-table
acceptance remains unverified.

## Measured acceptance and remaining limits

See the [dated evidence](EVALUATION.md#prepared-api-delivery-and-pool-evidence) for exact tests, pool identities, timings and limitations. [ROADMAP](ROADMAP.md#current-project-status) owns delivery status.

Use a matching pool/catalog snapshot. Restart into a fresh state root when changing either; existing sessions keep their own snapshot and are not silently refreshed.


<a id="development-and-live-check-commands"></a>

## Development and authorized live-check commands

Requires Python >=3.12. Run setup when needed, then ordinary quick checks:

```bash
make install-dev
make quick
```

On Windows, after creating `.venv` and installing `.[dev]`, run the same fast PR checks with `.\.venv\Scripts\python.exe scripts/check_windows.py`. The script uses the same interpreter for every check, needs no PowerShell execution-policy change, enables UTF-8 for Turkish fixtures, and stops at the first failed check. It makes no live model/source calls. `.gitattributes` preserves the reviewed source documents' LF hashes and all test fixtures' exact bytes on checkout.

Without Windows symbolic-link creation privilege, the real symlink fixture reports a skip; missing-root rejection still runs. POSIX file-mode assertions apply on POSIX only; on Windows, use an operator-owned private staging directory with appropriate Windows ACLs. Source-fetch supervision observes connection progress on both platforms without changing connection or total-time budgets.

For opt-in catalog discovery followed by one bounded analysis/clarification plan, add `--catalog docs/catalog/prepared_v3.json` to the prepared rehearsal. See [the continuation contract](CATALOG.md). This enables lexical catalog search; real dense-query policy and live selection quality still need acceptance. The [reviewed EVDS expansion](EVDS_COVERAGE.md) adds nine credit-rate series and thirteen CPI divisions: the measured local pool holds 29 series / 4,124 observations, with 37 catalog identities. This is broader coverage, not every BDDK/EVDS series. v1/v2 remain historical snapshots; use the matching catalog and rebuild any vector index for the new content digest.

Before `live_check --prepared-root`, finish ingestion and close all connections to the prepared lakehouse; keep that root unchanged during the copy. `prepared_copy_failed` means the copy could not be created (for example, a locked file); no model call was made. Close the owning process and use a fresh work directory for a later explicitly authorized rehearsal.

Normal code tasks use targeted tests/lint or `make quick`; task PRs to `dev` use the fast `make pr` gate, including strict `mypy src` (DEC-140). `make full` belongs to stable `dev -> main`/final demo checkpoints or explicit requests. Boundary changes still need targeted negative tests. Documentation-only tasks/PRs use diff/link/status checks, not application/security/release checks. [AGENTS](../AGENTS.md#validation-tiers-and-speed-limits) owns the gate rules; these command definitions are not claimed passing results.

There is no `eval-smoke`/`eval-full` Make target or benchmark runner. UI launch instructions are in [LOCAL_CLIENT](LOCAL_CLIENT.md). `python -m kkb_agent.llm.smoke` (transport) and `python -m kkb_agent.live_check` (one question end to end on synthetic data) are operator-run live checks, never part of a gate. [EVALUATION](EVALUATION.md#implemented-command-registry) separates existing commands from planned tiers. `make full` does not run a benchmark.

M7-19 adds an explicit document mode to `live_check`. **One live public CSV acceptance passed** ([evidence and limits](EVALUATION.md#m7-19-live-csv-acceptance)). The following is a future operator invocation, not an offline test: it calls Kloudeks and fetches the URL in the question. Use it only after separate approval for that run and an accepted network/source boundary (Q-NET-01/02; Q-DATA where relevant). Supply the actual question, URL, column and row; no address is injected by the command.

```sh
# Only after explicit live-run approval; replace the placeholder question.
( set -a; . ./.env; set +a; python -m kkb_agent.live_check --document --question 'QUESTION CONTAINING THE APPROVED PUBLIC URL AND REQUESTED CELL' )
```

The application reads configuration from `os.environ`, never `.env` itself. The document report contains stage/status/timing, hashed identities, numeric cell coordinates and verification counts, not question/answer/document text or URLs. Exit 0 requires a retained numeric claim bound to the fetched cell with resolvable source/transform lineage; loading a file alone is not success. On `fetch_failed`, the operator-only `fetch_code` reports an existing `FetchCode` or null; TLS and other transport errors remain grouped as `TRANSPORT_FAILURE`. For `not_admitted`/`needs_input`, operator-only `document_code` exposes an allowlisted existing admission/loader code or null. `not_admitted` alone does not identify whether admission or parsing failed. No raw failure text is exported. The existing no-argument synthetic mode is unchanged. CSV/XLSX/text-layer PDF and bounded static HTML tables/text are supported. M7-11 offers explicitly injected untrusted OCR text only; the operator command does not enable it. JavaScript rendering and image-address loading are unsupported. Only the separately recorded public CSV live acceptance has passed.
