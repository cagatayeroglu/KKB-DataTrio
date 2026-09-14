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
Older unchanged results can be selected. The current browser client does not
yet submit this field; no browser or live selected-table acceptance is claimed.

## Measured acceptance and remaining limits

The original M10-17 local pool passed read-only readiness: **7 prepared identities,
683 observations, 15 reviewed catalog identities, 80 files, 7,613,310 bytes**.
Configuration is present and the approved endpoint is valid; no live request
was used to establish this. A separate in-process HTTP rehearsal with scripted
plans and the real public pool passes all three organizer turns. An independent
Decimal oracle agrees on 59 transitions, 32 rate falls and 22 joint periods.
All 302 previous values and 60 KFE values survive, and the original 80 files
remain hash-identical. The largest response is 143,584 bytes. Readiness took
717.15ms; scripted turns took 1,425.33 / 925.01 / 1,578.83ms. These are local
pipeline timings, **not Qwen inference latency or live reasoning reliability**.

The subsequent [EVDS expansion](EVDS_COVERAGE.md) prepares **29 identities and
4,124 observations** with **37 catalog identities** in v3. Original seven-series
values are retained; 3,926 EVDS observations additionally match raw decimal
values in an independent read-back. The prepared pool is 8,520,172 bytes across
124 files. These are local preparation/readiness checks, not a live-model test
over the expanded universe. Use v3 for this pool; v2 remains a historical
snapshot and correctly refuses the additional identities. Restart the API into
a fresh state root when switching pools/catalogs; existing sessions keep their
own snapshot and are not silently refreshed.

One existing gate limitation remains visible: repeating a numerical calculation
under a second identity and writing an unqualified identical number can abstain
because multiple results match. The API preserves that refusal; it does not
weaken numeric matching. A real add-series follow-up over synthetic inputs
passes, retaining the previous publication and all original values.

Live model acceptance still requires its explicit authorized rehearsal. Dense
policy/quality, broader official coverage, public proof traversal, full stage
progress, source input UI, remaining frontend features and deployment remain separate tasks.
See [EVALUATION](EVALUATION.md) and [ROADMAP](ROADMAP.md) for final test/merge state.
