# DataTrio local analysis workspace

M10-03 first working client, PR #159. A single responsive screen combines the
question, accepted result versions, canonical tables, prepared-data inventory
and read-only operating settings. There is no login screen in this local slice.
The Next.js server connects to the existing [prepared Python API](PREPARED_API.md).
Financial calculations and publication decisions stay in Python.

## Run on Windows

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
shell interpolation. Model timeout must be 1–120 seconds and attempts 1–3;
model latency must be measured before choosing a demo setting. Startup/health
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

## What the first screen does

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
  The API's detailed source-to-result proof graph is not exposed yet.

The exact raw display strings can retain source-specific notation; the client
only translates known labels. There is no model-generated HTML rendering.

## Recovery and limits

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

The local API admits at most eight sessions and 24 turns per session, with one
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

## Prova versus live acceptance

The 2026-09-14 browser inspection used the real public prepared snapshot and a
finite **scripted test provider** through the same Python API. The page states
“Çevrimdışı prova — Canlı Qwen kullanılmıyor.” Three prescribed plans exercised
comparison, deflation and adding KFE, producing 242, 302 and 368 published
cells. This demonstrates client/API/tool integration and state preservation,
not arbitrary-query model reasoning or live Kloudeks acceptance.

The temporary developer rehearsal is not the production launcher or a fallback.
It is unsuitable for arbitrary questions; the official CLI above uses Kloudeks
only and requires explicit enablement. Live three-turn browser acceptance is
still pending. No live model/embedding request was made for this UI validation.

## Validation and remaining work

From `web/`, `npm run check` runs formatting, strict TypeScript and the bounded
bridge/session/canonical-table regression tests. `npm run build` verifies the
production client. CI has a separate Node job; Python's Fast PR gate and secret
scanner continue to cover the repository. Generated `node_modules` and `.next`
trees are pruned, while authored JS/TS/configuration, lockfiles and `.env` paths
remain in secret-scanner scope.

This is an inspectable first client, not completion of all M10. Uploads, source
refresh jobs, charts/export, full proof traversal, detailed tool-stage events,
writable agent settings, server cancellation and hosted authentication remain
separate tasks. Monthly/weekly/daily analytical support is owned by backend
semantics and source frequency; the UI does not manufacture daily observations.
See [ROADMAP](ROADMAP.md#m10-03-first-local-client-2026-09-14) for delivery evidence.

## M10-18 selection continuation (2026-09-14, PR #166)

This branch adds the client behavior above. Automated client/bridge tests and
production build pass; see [the dated evaluation](EVALUATION.md#m10-18-client-selection-2026-09-14).
On 2026-09-15 the selected-table browser scenarios passed using the production
frontend and real Python prepared runtime over synthetic data: old selection
through reload, uncertain-admission retry after reload, source preservation on
abstention/rejection and free-question mode. See the [dated browser evidence](EVALUATION.md#m10-18-browser-selection-2026-09-15).
Live Kloudeks acceptance, proof graph UI and broader refresh invalidation remain
separate. This PR remains unmerged.

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

Use this exact question order in a fresh browser workspace:

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
