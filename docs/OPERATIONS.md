# Operations: local preparation, API and client

Use this runbook for environment setup, reviewed-pool rebuild, read-only readiness,
backend/frontend startup, API use and recovery. [ARCHITECTURE](ARCHITECTURE.md)
owns implementation contracts; [SECURITY](SECURITY.md) trust limits;
[EVALUATION](EVALUATION.md) scripted/live evidence; ROADMAP completion.
The local prepared client is not a deployed multi-user service. Wider demo-flow
requirements below are explicitly targets, not additional executable routes.

## Operator sequence

1. Install Python >=3.12 development dependencies and Node.js 22 for the client.
   Keep credentials in operator-local configuration and prepared data out of Git.
2. With approved source access, prepare a reviewed pool and matching catalog.
3. Close ingestion/writers; run the readiness command below, which calls no model.
4. When model requests are authorized, start the loopback Python API and Next.js
   in two terminals. Use one consistent browser origin.
5. Follow the recovery contract: a lost response reuses the original request and
   selection; a new request ID means new analysis. Restarting invalidates sessions.

### macOS local toolchain

The repository pins Python dependencies in `pyproject.toml`, client dependencies
in `web/package-lock.json`, and the supported local Node line in `.node-version`.
For a Homebrew installation, `node@22` is keg-only; keep an unrelated system Node
unchanged and select Node 22 in the project shell:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
brew install node@22
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
cd web
npm ci --ignore-scripts --no-audit --no-fund
```

Verify `node --version` is within the `>=22.17.0 <23` range before client checks.
The 2026-09-15 Eray environment uses Python 3.12.5 and Node 22.23.2. A newer
system Node is not proof that the client is being checked with the supported
runtime.

## Prepare or rebuild the official pool

A clone does not contain the accepted pool or Bronze payloads. Rebuild from the
reviewed adapters only with the existing source/egress authorization. Exact
selector/date-window commands, expectations and source limitations are in
[BDDK Monthly preparation](BDDK_MONTHLY_METADATA.md) and
[four-series EVDS preparation](EVDS_SERIES_METADATA.md); the
[EVDS expansion](EVDS_COVERAGE.md) records additional rate/CPI series and its
preparation command. Use the catalog revision matching that pool. This is not
every BDDK/EVDS series, nor proof of identical source bytes on a later rebuild.

Preparation writes Bronze evidence, validated Silver and provenance under the
operator-owned root. Keep the root unchanged and close every connection before
readiness/private copying. When changing pools/catalogs, restart into a fresh state
root; existing sessions retain their previous snapshot. A copy failure makes no
model call. Do not overwrite older evidence to hide a conflicting source revision.


## Local API contracts


<a id="local_api-executable-contract"></a>

### Executable contract

| Method / route | Input | Response |
| --- | --- | --- |
| GET `/v1/health` | None | Local readiness, `scripted`/`kloudeks` mode and limits; `model_checked=false` |
| GET `/openapi.json` | None | Versioned schemas; Swagger/ReDoc disabled, no CDN dependency |
| POST `/v1/sessions` | JSON `{}` | Session ID and one-time capability token; HTTP 201 |
| POST `/v1/sessions/{session_id}/turns` | JSON `request_id`, `question`, optional `selected_result_id`; token header | Owned turn reference/state; HTTP 202 |
| GET `/v1/sessions/{session_id}/turns/{turn_id}` | Token header | State, gated answer and published cells when available |
| GET `/v1/sessions/{session_id}/turns/{turn_id}/events` | Token header; optional `Last-Event-ID` 0–3 | Actual turn lifecycle SSE |
| POST `/v1/sessions/{session_id}/turns/{turn_id}/cancel` | Token header | Accepted (202); the turn stops at its next checkpoint |
| POST `/v1/sessions/{session_id}/documents` | Raw CSV/XLSX/PDF/HTML body with its content type; token header | Admitted document reference; HTTP 201 |
| POST `/v1/sessions/{session_id}/documents` with `image/png` or `image/jpeg` | Same token header and 10 MiB limit as any upload | The picture is wrapped as a one-page PDF and read by OCR like a scanned page ([DEC-179](DECISIONS.md#dec-179--a-picture-is-read-as-a-one-page-scanned-document)); HTTP 201 with `document_format: "pdf"` |
| POST `/v1/sessions/{session_id}/documents/from-url` | JSON `url` (https); token header; needs `--enable-web-url` | Fetches a tabular document through safe_fetch and admits it like an upload; HTTP 201 |
| POST `/v1/owner` | JSON `{}` | The browser's owner key, which lists and reopens its own conversations |
| GET / PATCH `/v1/settings` | Owner key header; PATCH body `disabled`, `history_turns` | The owner's restrict-only runtime choices ([DEC-162](DECISIONS.md#dec-162--a-browser-narrows-its-own-runtime-only-the-operator-widens-it)) |
| GET `/v1/prompts` | Owner key header | The prompt parts model calls are assembled from, each with its content digest; read-only by design |
| GET `/v1/conversations` (+ `q`, `archived` filters) | Owner key header | This browser's conversations, newest first |
| GET / PATCH `/v1/conversations/{id}` | Owner key or conversation token | Messages and documents; PATCH renames or archives |
| GET `/v1/conversations/{id}/runs`, `/runs/{run_id}`, `/runs/{run_id}/steps/{seq}` | Owner key or conversation token | Recorded runs, their trace steps, and one step's full detail |
| GET `/v1/conversations/{id}/results/{turn_id}` | Owner key or conversation token | The table a stored turn published, rebuilt from its receipt with the same reference, version and proof - after any restart; 409 while a turn runs |
| GET / POST `/v1/conversations/{id}/feedback` | Owner key or conversation token | Ratings for this conversation's answers |
| GET `/v1/dataset` | None | The prepared pool's series and coverage |
| GET `/v1/knowledge` | Owner key header | Every series the agent can reach, with where each one's meaning comes from |
| GET `/v1/knowledge/search?q=` | Owner key header | A question tried against this catalogue with the deployment's own retrieval, run here and stored nowhere |
| GET / POST `/v1/knowledge/index` | Owner key header | The vector generation in use; POST builds one for the catalogue in use now ([DEC-163](DECISIONS.md#dec-163--a-vector-generation-covers-one-catalogue-and-the-knowledge-base-can-have-its-own)) |
| POST `/v1/knowledge/datasets`; GET `/{slug}`; POST `/{slug}/archive`, `/{slug}/restore` | Owner key header | Versioned user datasets (DEC-157); archive keeps history |
| GET `/v1/knowledge/series/{id}/values`, `/notes` (+ POST), `/uses` | Owner key header | Stored values, versioned notes/aliases, and the answers whose proof read the series |

`X-KKB-Session-Token` carries a random 256-bit capability. Never place it in a
URL, question, browser log or model prompt. The server retains only its SHA-256
digest and checks possession plus session/turn membership. A session ID alone
grants nothing. No arbitrary workspace/result/lineage digest lookup exists.
Generate a fresh 32-character lowercase hex `request_id` for each intended
question. Repeating the same ID, exact question and selection in that session returns the
existing turn without rerunning; changed text or selection gives `request_conflict`. After a
disconnect, retrieve the existing turn or repeat the same ID. A new ID means a
new analysis, not transport recovery.


## Prepared runtime


<a id="prepared_api-m10-17--run-the-api-over-a-prepared-local-pool"></a>

### M10-17 — Run the API over a prepared local pool

This connects [LOCAL_API](ARCHITECTURE.md#local_api-m10-16--version-one-local-api-and-owned-results) to the existing inspected tools,
`Session.answer`, workspace publication and canonical result projector.
No new financial formula or source fetch is hidden in the HTTP path.

<a id="prepared_api-check-first-without-calling-a-model"></a>

### Check first, without calling a model

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
timeout must be finite and 1–1800 seconds, with 1–3 provider attempts configured.
Recommended for the served API: `KLOUDEKS_REQUEST_TIMEOUT=1800` and
`KLOUDEKS_MAX_ATTEMPTS=3`. Measured on 2026-09-19 over 70 live calls: median 88 s,
slowest finished call 880 s, decode 7–11.5 tokens a second, so a 7–8k-token plan
did not finish inside the former 900 s ceiling (4 calls lost). An attempt is only
a re-ask of a malformed answer with the fault fed back (`complete_with_repair`);
a timed-out or failed request is never retried, so three attempts never multiply
the timeout, and one attempt lets a single malformed plan fail the whole turn.
The page polls a running turn for an hour and can re-read its state afterwards.

<a id="prepared_api-start-only-when-model-requests-are-authorized"></a>

### The sources' own directory (DEC-176)

`--serve` applies the sources' own pinned listings as a second catalogue tier unless `--no-source-directory` is given: the BDDK monthly bulletin's supported rows (DEC-176) and every EVDS datagroup (DEC-177; a found datagroup is opened into its series by one public request, kept under `<state-root>/directory/evds/`). The reviewed `--catalog-index` generation covers only the reviewed catalogue, so after the first start open "Veri ve bilgi tabanı" and press "Yeniden vektörle" once (1,356 entries, about seven minutes of embedding calls, measured 2026-09-19); the generation is kept under `<state-root>/generations/` and reopened at every restart. Until then discovery is by words only and the page says so. "Kaynak dizinini yenile" on the same page (`POST /v1/knowledge/directory`) reads EVDS's live directory and the opened datagroups' series lists again: new datagroups become entries (then press "Yeniden vektörle"), new series of an opened datagroup are found by the next search; no model call. To refresh the BDDK listing itself run `python tests/manual/harvest_bddk_directory.py` (58 public requests, one a second) and review the diff of `src/kkb_agent/ingest/bddk_monthly_directory.py` in a PR.

### Start only when model requests are authorized

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

Add `--enable-web-url` only when reading a web address written in a question is
authorized. It is off by default (organizer URL policy Q-NET-02 is still open);
the readiness JSON of `--check` and `--serve` reports `"web_url": true/false`.
Enabled, a question containing an https CSV/XLSX/PDF/static-HTML address can
answer one named cell, or add one explicit-month column to a selected table
(`table_transform` `add_document_column`), through `safe_fetch`, the upload
admission rules and the unchanged answer gate; the proof shows the document's format, host, content hash
and cell position, never its path, query or cell text. Each run that actually
fetches a public address is a live network action and needs its own approval;
offline evidence is `tests/unit/test_prepared_web_url.py` and
`tests/unit/test_document_column.py`.

OCR follows its configuration (DEC-153): PDF pages without a text layer are read
through OCR whenever `KLOUDEKS_OCR_MODEL` names the DEC-129 OCR model, and
`--no-ocr` refuses it. Readiness JSON reports `"ocr"`, and OCR figures count only
from table columns that add up to the table's total row (DEC-149). Every OCR
request is a live model call inside an approved plan.

**Local search instance (DEC-180), the supported way to have `web_search` answer.** With Docker running:

```bash
mkdir -p data/processed/searxng
# settings.yml: use_default_settings: true; search.formats: [html, json]; server.secret_key: <random>; server.limiter: false
docker run -d --name datatrio_searxng --restart unless-stopped -p 127.0.0.1:8888:8080 \
  -v "$PWD/data/processed/searxng/settings.yml:/etc/searxng/settings.yml:ro" searxng/searxng:latest
```

then start the API with `--searxng-url http://127.0.0.1:8888 --searxng-loopback`. The flag reads that one loopback address only; `safe_fetch` still refuses loopback for every address a question or a page names.

`--searxng-url https://search.example.org` (DEC-158) registers `web_search` over
that SearXNG instance's JSON API (enable `json` in its `search.formats`). The
request goes through `safe_fetch`, which refuses loopback and private addresses,
so the instance must be publicly reachable; a local `127.0.0.1` instance is
refused and reported as a backend error. Results are
shown as an unverified candidate list and never authorize `web_url`; a live search
smoke is still required before production search is claimed (DEC-134).

Official acquisition is on by default (DEC-155, DEC-159); `--no-official-acquisition`
refuses it. A question that needs a reviewed EVDS series or a reviewed BDDK
monthly housing selector the prepared pool lacks fetches it through the reviewed
adapter (EVDS: ten years to the last whole month, a listed daily or weekly series to
the clock's day; BDDK: from 2021-01 to three months back, one request per month), at
most twelve a turn (as many as one typed read may name), each shown in the
turn's trace as `acquisition.<code>`. Successful raw responses are kept under
`<state-root>/acquired/` by request fingerprint and replayed through the same
parser, so later conversations do not refetch within the same month; the
knowledge base shows when each series was fetched. Readiness JSON reports
`"official_acquisition"`. A live fetch needs network access to the public source.

Uploads are admitted by default and `--no-uploads` refuses them: the local client attaches an uploaded CSV, Excel
(`.xlsx`), PDF or static HTML document (up to 10 MiB, four per session) to the
next question; readiness JSON reports `"uploads"` and `/v1/health` lists the
`document_upload` capability, which shows the client's attach button. Uploads
are stored only under the process's `--state-root` session directory, without
filenames, and are not deleted automatically; treat that root as holding the
uploaded data. An attached document supports the same one-cell answer and
selected-table column addition as a prompt address; offline evidence is
`tests/unit/test_document_upload.py`.

Either document source can also start a new analysis: ask for a monthly table
from named columns ("Ekli belgeden Ay, Kapanış ve Faiz sütunlarıyla aylık tablo
oluştur") as a free question, with "Seçili tabloyla devam et" unticked. Columns
without a unit in their header, with ambiguous numbers or not found are left out
and named in the proof warnings; period problems refuse the table. The published
table can then be selected for adding prepared series or comparisons. Offline
evidence is `tests/unit/test_document_table.py`.

<a id="prepared_api-optional-dense-catalog-retrieval"></a>

### Optional dense catalog retrieval (DEC-142)

Catalog discovery is lexical unless an index generation is supplied. Build one
generation per catalog snapshot once (37 passages in 3 batched embedding requests,
about 2 s on 2026-09-15), into a new ignored directory:

```bash
python -m kkb_agent.catalog.embedding --catalog docs/catalog/prepared_v3.json --root "$PWD/data/processed/catalog-index/qwen3-instruct-query-v1-e0bbaac8" --policy qwen3-instruct-query-v1 --env-file .env --enable-embedding-requests
```

Then add `--catalog-index "$PWD/data/processed/catalog-index/qwen3-instruct-query-v1-e0bbaac8"`
to `--check` and `--serve`. `KLOUDEKS_EMBEDDING_MODEL` must be
`kkbhackathon2026/Qwen3-Embedding-8B`; a mismatched model, snapshot, policy or a
missing generation refuses startup. `--check` prints `"catalog_retrieval": "hybrid"`
without an embedding request. While serving, each distinct discovery query adds one
embedding request (about 75 ms measured) using the same provider timeout and
attempts; a failed request falls back to lexical candidates for that search.
Rebuild the generation after any catalog snapshot change. Contract details are in
[CATALOG](CATALOG.md#catalog_search-prepared-runtime-dense-stage).

In addition to `/v1/health`, `/v1/dataset` exposes a bounded copy of the startup
inventory: catalog and prepared counts, observations, file bytes, snapshot and
catalog identities, series labels and recorded periods. It exposes no local
paths, source locators or credentials. Missing configured data returns a fixed
unavailable response. The first [local frontend](OPERATIONS.md#local_client-datatrio-local-analysis-workspace) consumes this inventory and the turn contract.

<a id="prepared_api-measured-acceptance-and-remaining-limits"></a>

### Measured acceptance and remaining limits

See the [dated evidence](EVALUATION.md#prepared-api-delivery-and-pool-evidence) for exact tests, pool identities, timings and limitations. [ROADMAP](ROADMAP.md#current-project-status) owns delivery status.

Use a matching pool/catalog snapshot. Restart into a fresh state root when changing either; existing sessions keep their own snapshot and are not silently refreshed.

The 2026-09-15 Eray macOS rebuild uses `prepared_v3.json` and reports ready with
29 prepared identities, 4,124 observation rows, 37 catalog identities, 124
files and zero null observations. The previous seven-series pool is retained at
the ignored operator path `data/processed/lakehouse-before-v3-20260915`; its 683
stored rows compare exactly with the corresponding rows in the expanded pool.
This is a local recovery copy, not a tracked fixture or a substitute for the
rebuild procedure. The readiness call used `--check`, reported
`model_checked=false`, and made no model request.

<a id="development-and-live-check-commands"></a>
<a id="prepared_api-development-and-authorized-live-check-commands"></a>

### Development and authorized live-check commands

The document-mode command here obtains configuration from process variables;
its environment statement does not override the API launcher’s explicit literal
`--env-file` option documented above.

Requires Python >=3.12. Run setup when needed, then ordinary quick checks:

```bash
make install-dev
make quick
```

On Windows, after creating `.venv` and installing `.[dev]`, run the same fast PR checks with `.\.venv\Scripts\python.exe scripts/check_windows.py`. The script uses the same interpreter for every check, needs no PowerShell execution-policy change, enables UTF-8 for Turkish fixtures, and stops at the first failed check. It makes no live model/source calls. `.gitattributes` preserves the reviewed source documents' LF hashes and all test fixtures' exact bytes on checkout.

Without Windows symbolic-link creation privilege, the real symlink fixture reports a skip; missing-root rejection still runs. POSIX file-mode assertions apply on POSIX only; on Windows, use an operator-owned private staging directory with appropriate Windows ACLs. Source-fetch supervision observes connection progress on both platforms without changing connection or total-time budgets.

For opt-in catalog discovery followed by one bounded analysis/clarification plan, add `--catalog docs/catalog/prepared_v3.json` to the prepared rehearsal. See [the continuation contract](CATALOG.md). This enables lexical catalog search; `live_check` does not configure the DEC-142 dense stage, which is available through the prepared API's [`--catalog-index`](OPERATIONS.md#prepared_api-optional-dense-catalog-retrieval). Live selection quality with dense retrieval still needs acceptance. The [reviewed EVDS expansion](EVDS_COVERAGE.md) adds nine credit-rate series and thirteen CPI divisions: the measured local pool holds 29 series / 4,124 observations, with 37 catalog identities. This is broader coverage, not every BDDK/EVDS series. v1/v2 remain historical snapshots; use the matching catalog and rebuild any vector index for the new content digest.

Before `live_check --prepared-root`, finish ingestion and close all connections to the prepared lakehouse; keep that root unchanged during the copy. `prepared_copy_failed` means the copy could not be created (for example, a locked file); no model call was made. Close the owning process and use a fresh work directory for a later explicitly authorized rehearsal.

Normal code tasks use targeted tests/lint or `make quick`; task PRs to `dev` use the fast `make pr` gate, including strict `mypy src` (DEC-140). `make full` belongs to stable `dev -> main`/final demo checkpoints or explicit requests. Boundary changes still need targeted negative tests. Documentation-only tasks/PRs use diff/link/status checks, not application/security/release checks. [AGENTS](../AGENTS.md#validation-tiers-and-speed-limits) owns the gate rules; these command definitions are not claimed passing results.

There is no `eval-smoke`/`eval-full` Make target or benchmark runner. UI launch instructions are in [LOCAL_CLIENT](OPERATIONS.md#local_client-datatrio-local-analysis-workspace). `python -m kkb_agent.llm.smoke` (transport) and `python -m kkb_agent.live_check` (one question end to end on synthetic data) are operator-run live checks, never part of a gate. [EVALUATION](EVALUATION.md#implemented-command-registry) separates existing commands from planned tiers. `make full` does not run a benchmark.

M7-19 adds an explicit document mode to `live_check`. **One live public CSV acceptance passed** ([evidence and limits](EVALUATION.md#m7-19-live-csv-acceptance)). The following is a future operator invocation, not an offline test: it calls Kloudeks and fetches the URL in the question. Use it only after separate approval for that run and an accepted network/source boundary (Q-NET-01/02; Q-DATA where relevant). Supply the actual question, URL, column and row; no address is injected by the command.

```sh
# Only after explicit live-run approval; replace the placeholder question.
( set -a; . ./.env; set +a; python -m kkb_agent.live_check --document --question 'QUESTION CONTAINING THE APPROVED PUBLIC URL AND REQUESTED CELL' )
```

The application reads configuration from `os.environ`, never `.env` itself. The document report contains stage/status/timing, hashed identities, numeric cell coordinates and verification counts, not question/answer/document text or URLs. Exit 0 requires a retained numeric claim bound to the fetched cell with resolvable source/transform lineage; loading a file alone is not success. On `fetch_failed`, the operator-only `fetch_code` reports an existing `FetchCode` or null; TLS and other transport errors remain grouped as `TRANSPORT_FAILURE`. For `not_admitted`/`needs_input`, operator-only `document_code` exposes an allowlisted existing admission/loader code or null. `not_admitted` alone does not identify whether admission or parsing failed. No raw failure text is exported. The existing no-argument synthetic mode is unchanged. CSV/XLSX/text-layer PDF and bounded static HTML tables/text are supported. M7-11 offers explicitly injected untrusted OCR text only; the operator command does not enable it. JavaScript rendering and image-address loading are unsupported. Only the separately recorded public CSV live acceptance has passed.


## Local client


<a id="local_client-datatrio-local-analysis-workspace"></a>

### DataTrio local analysis workspace

M10-03 first working client, PR #159. A single responsive screen combines the
question, accepted result versions, canonical tables, prepared-data inventory
and read-only operating settings. There is no login screen in this local slice.
The Next.js server connects to the existing [prepared Python API](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool).
Financial calculations and publication decisions stay in Python.

<a id="local_client-run-on-windows"></a>

### Run on Windows

Use two PowerShell terminals. The examples assume the existing Desktop checkout,
installed Python development environment, reviewed prepared pool and configured
local `.env`. No credentials or prepared observations belong in Git.

First verify the backend configuration and data without a model request:

```powershell
cd C:\Users\Cabaroglu\Desktop\KKB-DataTrio
.\.venv\Scripts\python.exe -m kkb_agent.api --check --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v3.json --env-file .env
```

This checks the local snapshot and configuration; it does not prove live Qwen
connectivity. The expanded local snapshot measured on 2026-09-14 contains
29 prepared series, 4,124 observations and 37 catalog candidates. Another
teammate must prepare their own data using the source guides; cloning Git does
not download this pool. See [EVDS coverage](EVDS_COVERAGE.md) and
[BDDK preparation](BDDK_SOURCE.md).

When live model requests are authorized, start the Python API in terminal 1:

```powershell
.\.venv\Scripts\python.exe -m kkb_agent.api --serve --enable-model-requests --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v3.json --env-file .env --state-root data/processed/api-runs
```

This binds `127.0.0.1:8000`. Submitting a question sends the required context to
the explicitly configured Kloudeks provider. No OpenAI/Anthropic/Google-hosted
fallback exists. The optional `--env-file` is parsed as bounded literal values;
its values override corresponding process environment settings. It never runs
shell interpolation. Model timeout must be 1–900 seconds and attempts 1–3;
measured turns took 73–288 s (see the [live rehearsal](EVALUATION.md#m11-07-organizer-three-turn-live-rehearsal-2026-09-15)),
so use 600 s. The client stops polling after ten minutes and offers to resume
the same turn; it never resubmits. Startup/health
does not call the model. See PREPARED_API for the exact snapshot/worker bounds.

In terminal 2, use Node.js 22 (tested with 22.17.0):

```powershell
cd C:\Users\Cabaroglu\Desktop\KKB-DataTrio\web
npm ci --ignore-scripts --no-audit --no-fund
$env:KKB_LOCAL_API_URL = 'http://127.0.0.1:8000'
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run dev
```

Open **http://127.0.0.1:3000/**. `localhost:3000` also works, but use the same
origin consistently so the browser retains its session. The frontend port is
deliberately fixed to 3000 in this local bridge. A different backend port can
be selected through the API's `--port` and the matching server-only URL above.

For a production-build preview, stop the frontend with Ctrl+C and run:

```powershell
npm run build
npm run start
```

Keep the Python terminal running. Stop each server with Ctrl+C when finished.
No process is automatically installed as a service. Changing prepared data or
catalogs requires restarting the API with a validated snapshot; old sessions
are not silently refreshed. A backend restart invalidates browser capabilities.

<a id="local_client-what-the-first-screen-does"></a>

### What the first screen does

- Shows actual prepared/candidate counts, stored periods and pool size. The
  inventory refresh button only rereads API metadata; it does not ingest data.
- Example questions fill the composer; they do not submit themselves.
- A question creates a session and submits a uniquely identified turn. Status
  is polled from the API; the UI does not invent percentages or tool stages.
- Accepted published output displays the API's cells; qualified/abstained
  responses retain prose/notices without a new table. Table layout,
  pagination, searching and Turkish labels do not recalculate finance values.
- Missing cells remain absent. Different units/scales and duplicate cells are
  kept separate. Whole-window counts are separated from monthly observations.
- Each publication remains selectable. Cell detail shows recorded unit, period,
  cell identity and result version; unavailable semantics stay explicit.
- Clarification, abstention and transport failure preserve the previous table.
- A period chart above the table plots the same published values. Each unit
  and scale has its own axis group; choose at most two (for example milyon TL
  and %). Empty periods stay gaps and month-over-month change columns start
  hidden in the legend. Hover shows the full series name and display value.
- Cell detail shows the result-level proof chain: raw source responses (count,
  https host, retrieval date), the prepared series read, each verified
  calculation step including an earlier published table, and the accepted gate.
  "Kısmi" names each recorded gap; the chain is not per-cell or a correctness
  guarantee.

The exact raw display strings can retain source-specific notation; the client
only translates known labels. There is no model-generated HTML rendering.

<a id="local_client-recovery-and-limits"></a>

### Recovery and limits

The session capability is held in this tab's `sessionStorage`, never a URL or
Kloudeks credential. The question, request identity and optional selected public
result reference are saved together before POST. The displayed result reference
and follow-selection preference are stored separately from each request.
“Seçili tabloyla devam et” binds the next question to the displayed accepted
publication. Switching it off sends a question without an explicit table pin;
it does not erase backend analysis state. The composer and historical questions
show which source was used. A successful publication becomes the new selection;
a refusal/failure leaves the prior table visible.

Reload restores the exact selected reference, including an older table; a missing
stored reference never silently becomes the newest table. Legacy storage remains
readable, and legacy retries do not acquire a new selected source retroactively.
Reloading restores known turns through GET; it never silently resubmits a
question. If admission was uncertain, the visible recovery action reuses the
same request identity, exact question and original selected reference. Selection
controls stay disabled while admission/execution/recovery is pending. Multiple
unread turn states recover in order. Explicit admission rejections are retained
as terminal entries; transport/5xx failures keep the recovery record. Storage
failures prevent new submission rather than
losing the recovery record.

The local API admits at most 200 sessions and 100 turns per session, with one
analysis worker. Creating a new workspace does not delete old analytical files
or reclaim server sessions. Polling stops after ten minutes; this is not a
server-side cancellation. Opening a new workspace with an unresolved request asks
before discarding its local recovery record; it does not cancel the server job.
The operator can restart the API when required.
The composer is disabled during admission/execution to avoid accidental overlap.

If the API is absent or returns an invalid response, the screen reports a fixed
Turkish failure. It does not substitute sample values or silently use another
provider. Server-only `KKB_LOCAL_API_URL` permits a fixed loopback destination;
no `NEXT_PUBLIC_` secret or model credential is required by `web/`.

<a id="local_client-repeat-the-finite-synthetic-selection-rehearsal"></a>

### Repeat the finite synthetic selection rehearsal

From the repository root with Python dev/test dependencies installed:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python tests/manual/selected_client.py
```

In another terminal, start the production client using the build instructions
above and `KKB_LOCAL_API_URL=http://127.0.0.1:8127`. This [manual test launcher](../tests/manual/selected_client.py)
uses a temporary two-series pool and prescribed test-provider responses; it is
not the product launcher and cannot answer arbitrary questions. It never calls
Kloudeks or official sources. Stop both servers with Ctrl+C after the rehearsal.
It overwrites only its generated `artifacts/selected-browser-ledger.jsonl` ledger
(request/source IDs, status and provider-call counts; no capability tokens).

For the proof chain, `python tests/manual/proof_client.py` (same environment
and port) serves an adapter-shaped BDDK pool built from injected responses plus
a CPI series without raw-source lineage. Ask `Konut kredisi tablosunu getir.`
then, with follow-selection on, `Önceki tabloyu koruyup TÜFE ekle.`; open a cell
in each result. The first chain is complete (three raw responses); the second is
partial because CPI has no raw-source lineage. No Kloudeks or official source
is contacted.

For an owner-authorized live rehearsal with a hard request ceiling, run
`tests/manual/live_client.py` (same prepared runner/service as `--serve`,
`--max-model-requests N` between 1 and 15, `KLOUDEKS_MAX_ATTEMPTS=1` required) and
compare answers with `python tests/manual/organizer_oracle.py data/processed/lakehouse`.
That rehearsal client keeps its own stricter rule (one attempt, timeout 1–900 s) so its
request ceiling counts every provider call; give it its own settings file when the served
API's file uses three attempts. Each run needs separate bounded model-request
authorization; these flags do not themselves grant permission.

Embedding is disabled by default. To rehearse hybrid discovery, supply all three:
`--catalog-index <matching-generation>`, `--max-embedding-requests N` (1–15), and
`--enable-embedding-requests`. Startup verifies the configured embedding model and
index snapshot/profile/origin before constructing a provider. Use catalog v3 and
the matching `qwen3-instruct-query-v1-e0bbaac8` generation until a reviewed replacement
is handed over. Building an absent index needs separate embedding authorization.

Chat and query-embedding budgets are independent, shared by all sessions in that
launcher process and reserved before dispatch. Failures consume a slot; retries
are disabled. Only one nonempty query per embedding call is permitted; passage
embedding and vision remain refused. Cached queries make no new provider request.
Once the embedding budget is exhausted, uncached dense searches explicitly degrade
to lexical retrieval under the existing catalog policy; chat can continue within
its own ceiling. This degraded result does not establish live hybrid acceptance.

For document inputs, `--enable-uploads` accepts attached uploads, and
`--enable-web-url --max-fetches N` (1–10) lets questions read an address they
contain through the real `safe_fetch`; each request is reserved before dispatch
and ledgered as host, outcome code, media type, bytes and time only, never path
or query. Every fetch of a public address is a live network action inside the
same separately approved plan. `--enable-ocr --max-ocr-requests N` (1–10) OCRs
PDF pages without a text layer (set `KLOUDEKS_OCR_MODEL` to the DEC-129 OCR model
in the environment); each OCR request is reserved before dispatch and ledgered
as outcome, character count and time only. OCR figures count only from table
columns that add up to the table's total row (DEC-149).

`python tests/manual/live_turns.py --port 8128 --plan plan.json --out <dir>` drives
such a launcher over the HTTP turn contract: plan steps upload a document or ask
a question (optionally selecting the previous publication and attaching the last
upload). It keeps the session token in memory, resends a `provider_failed` turn
once in the same session, stops at the first non-accepted turn and writes each
turn's JSON to `<dir>`, which is operator-local data.

Choose a fresh `--ledger artifacts/<run-name>.jsonl` for each run. The default is
`artifacts/live-rehearsal-ledger.jsonl`; an existing file refuses startup rather than
being overwritten. The content-free ledger records configured limits, catalog
digest, dispatch starts and outcomes, timings, final counters and each gate's
omission categories, never messages, vectors, sentences or credentials.

Each gate entry also carries an `omissions` list so a withheld sentence can be
located afterwards without another live run. Per withheld sentence it records its
`sentence` index among the draft's non-empty sentences (`-1` when the whole draft
was disqualified at once), its reason `codes`, and for each rejected quantity the
parsed `value`, its `binding`, the `result_id` and `value_label` it bound to when
it bound to one, and that number's own `codes`. Reason text quotes the draft, so
the codes come from the verifier's own classifier and the quoted spans are dropped
before classification; neither the sentence nor the figure as the model wrote it is
recorded. A parsed value and our own result/value identities are operator data, not
answer text, and this list never makes the ledger a copy of the answer. Count
`started` entries per kind, not all lines: each dispatch has a separate outcome.
A stopped process may leave a start without an outcome; never interpret that as a
free retry. A logging failure before dispatch prevents that provider call.

Use this exact question order in a fresh browser workspace for the selection rehearsal:

1. `Konut kredisi tablosunu getir.` — three stock values, 100/120/150 million TRY.
2. `Seçili tabloya TÜFE ekle.` — six values, adding CPI 100/110/120.
3. Select **Analiz 1**, reload, then send `Eski tabloya TÜFE ekle; bağlantı provası`.
   The test wrapper returns one 503 **after** admission. Reload; the table/source
   must remain Analiz 1. Use **Bekleyen isteğe devam et**: Analiz 3 must contain
   six values; the ledger must repeat the exact request/source without new work.
4. Select **Analiz 1** and send `Seçili tabloya havuzda olmayan KFE serisini ekle.`.
   Expect abstention and the unchanged three-value source table.
5. Send `Reddedilen kaynak provası`. The wrapper injects 422 invalid_result;
   no retry loop or new publication; the composer must become usable.
6. Disable **Seçili tabloyla devam et**, reload, then send
   `Serbest soruyla yeni bir tablo getir.`. Expect a three-value publication
   with no selected-result field on admission. Historical results remain.

Also inspect selection controls while busy/pending and at 390x844; the document
must not scroll horizontally. Restore any temporary viewport override afterward.


## Wider operator-flow target

M10-01 target specification. Absence/prerequisite statements here describe its original scope; current routes and selected-result behavior are defined in the executable API contracts.

<a id="operator_flow-one-demo-flow"></a>

### One demo flow

Use synthetic/local-safe data for development rehearsal; real demo acceptance targets the prepared official dataset under DEC-136 with source-use permissions. Live source/model/OCR activity requires separate authorization. An operator must be able to distinguish a scripted rehearsal from live output; the existing live_check command is not an API or a safe automatic startup check.

| Step | Operator action | Application contract / observable outcome | Recovery and ownership |
| --- | --- | --- | --- |
| 1. Start | Open a fresh analysis session | Explicit session identity; readiness means local configuration/store capability, never an automatic provider call | Unavailable service exposes a fixed safe category; retry only by an explicit new operator action |
| 2. Load/select | Select prepared lakehouse data or supply an authorized document URL in the question | Prepared official observations are the financial-data input; the first four-series slice is prepared in an operator-local root (not committed; rebuild commands in LOCAL_CLIENT). Uploads use existing admission/loaders. URLs use web_url and safe_fetch; no arbitrary connector or BDDK/EVDS adapter is implied. Show the source selection and unknown semantics | Rejected/unsupported source is not added as usable data. Ask for a supported format or required sheet/delimiter; do not guess |
| 3. Ask | Submit a question in this session, optionally referencing a prior result | Server validates bounded request and session-owned references, then invokes existing Session.answer with that session's connection/workspace and trusted registry | No client-selected provider, tool registry, connection path, SQL or gate override |
| 4. Inspect progress | Read plan/tool status while waiting | DEC-123 SSE target: validated step/tool identifiers and lifecycle status only. Plan inspection is informational; it is not a new confirmation gate or hidden reasoning view | Never expose raw plan arguments, model prompts, intermediate document content or exception text |
| 5. Inspect answer | Read accepted/qualified answer or abstention | Present GatedAnswer.text only after its gate. Preserve limitations, unknown semantics and omitted-claim indication without showing rejected sentences | An abstention is a completed safe outcome, not a transport failure or a value of zero |
| 6. Inspect result/evidence | Select a result cell and “Why this number?” | Show the recorded value with period/unit/scale; request bounded evidence for that immutable result/cell. Missing proof is explicitly unavailable/partial | No source ancestor alone upgrades a value to verified. Graph presentation cannot repair absent evidence |
| 7. Follow up | Add a series or change a period in the same session | Resolve only owned current workspace values; retain prior result identity and show stale/recomputed state, never silently overwrite displayed evidence | Refuse stale/unowned references. Unsupported follow-up asks for clarification; no automatic full-table reconstruction |
| 8. Recover/reset | Start a new analysis after failure, or request reset | A new session must not inherit another session's data. Reset/cancellation UX is M10-11; no destructive reset/delete endpoint is promised here | Preserve old evidence until the explicit retention/reset policy permits removal; disconnect does not mean a running job was cancelled |

The selected-table continuation, immutable pre-POST request identity and reload/recovery contract is defined in [LOCAL_CLIENT](OPERATIONS.md#local_client-datatrio-local-analysis-workspace) and [LOCAL_API](ARCHITECTURE.md#local_api-m10-18--selected-result-grounding-merged). [DEC-141](DECISIONS.md#dec-141-organizer-verbal-criteria) requires preservation of untouched columns/history. [ROADMAP](ROADMAP.md#current-project-status) owns remaining UI scope; [EVALUATION](EVALUATION.md#m10-18-browser-selection-2026-09-15) distinguishes synthetic browser rehearsal from live acceptance. A specification review is not a passed rehearsal.

<a id="operator_flow-prepared-dataset-selection-and-separate-web-inputs"></a>

### Prepared dataset selection and separate web inputs

The [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes the prepared BDDK/EVDS pool the primary official-data demo path. The four organizer concepts are the first real vertical-slice target, not final coverage. Build and validate the pool before runtime through reusable adapters → raw bronze → validation/normalization → silver → required gold → DuckDB + Parquet. Users select trusted prepared candidates and see actual requested-window coverage/unknowns. Bronze alone cannot establish a financial answer.

```text
User -> planner -> catalog_search (operator-configured retrieval)
 -> trusted prepared candidate -> lakehouse silver / appropriate trusted gold
 -> guarded transforms / analytics -> mandatory correctness harness -> verifier
 -> accepted answer / table / chart / workspace
Prepared-pool miss or unresolved selection -> clarification / abstention
```

The normal core three-turn flow does not fetch BDDK/EVDS when a question arrives. Financial-source independence does not promise offline planning/query embeddings. Runtime official-source cache-miss materialization is a future policy-gated scalability extension, not a demo prerequisite. No generic web fallback or guessed coverage. [PREPARED_API](OPERATIONS.md#prepared_api-m10-17--run-the-api-over-a-prepared-local-pool) owns startup and snapshot handling; [EVALUATION](EVALUATION.md#prepared-api-delivery-and-pool-evidence) owns measured pool coverage and reproducibility; [ROADMAP](ROADMAP.md#current-project-status) owns completion.

Catalog retrieval mechanics belong to [CATALOG](CATALOG.md), composition to [ARCHITECTURE](ARCHITECTURE.md#catalog-runtime-composition), and acceptance to [EVALUATION](EVALUATION.md#catalog-validation-records). The operator flow introduces no vector configuration UI; a retrieved candidate still requires trusted identity, usable data and semantic checks.

Preserve version/source vintage, actual coverage and refresh/revision history; do not promise a completed version manager. DEC-135 metadata inspection is mandatory and auto-wired in configured prepared readers/projection; broader inspection, quality and reconciliation remain unfinished. The intended flow must work beyond housing balance/rate, CPI and national KFE over approximately 2021-01–2026-06, without hardcoded series selection.

General research is a separate planner branch: `web_search` (SearXNG compatibility candidate only), then only separately authorized `web_url`. Search results do not grant fetch authority. Crawl4AI is optional future extraction evaluation only. Uploaded CSV/XLSX/PDF and BIST/IMF/other authorized URL documents remain session artifacts; shared storage does not turn them into permanent official series. Prepared datasets are not canned answers or permission for silent fixture substitution. No new user-facing tool or permission flow is implemented here.
