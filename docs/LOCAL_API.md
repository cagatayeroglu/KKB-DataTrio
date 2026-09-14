# M10-16 — Version-one local API and owned results

The first HTTP implementation of [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end)
provides a FastAPI factory, process-local session capabilities, bounded turn
execution and explicit published-result projection. This is **not a deployed
service**. [M10-17 startup](PREPARED_API.md) now supplies the inspected prepared
Session runner and an explicitly enabled loopback launcher. Tests use scripted execution.
[OPERATOR_FLOW](OPERATOR_FLOW.md) retains the wider target requirements.

## Executable contract

| Method / route | Input | Response |
| --- | --- | --- |
| GET `/v1/health` | None | Local readiness, `scripted`/`kloudeks` mode and limits; `model_checked=false` |
| GET `/openapi.json` | None | Versioned schemas; Swagger/ReDoc disabled, no CDN dependency |
| POST `/v1/sessions` | JSON `{}` | Session ID and one-time capability token; HTTP 201 |
| POST `/v1/sessions/{session_id}/turns` | JSON `request_id`, `question`, optional `selected_result_id`; token header | Owned turn reference/state; HTTP 202 |
| GET `/v1/sessions/{session_id}/turns/{turn_id}` | Token header | State, gated answer and published cells when available |
| GET `/v1/sessions/{session_id}/turns/{turn_id}/events` | Token header; optional `Last-Event-ID` 0–3 | Actual turn lifecycle SSE |

`X-KKB-Session-Token` carries a random 256-bit capability. Never place it in a
URL, question, browser log or model prompt. The server retains only its SHA-256
digest and checks possession plus session/turn membership. A session ID alone
grants nothing. No arbitrary workspace/result/lineage digest lookup exists.
Generate a fresh 32-character lowercase hex `request_id` for each intended
question. Repeating the same ID, exact question and selection in that session returns the
existing turn without rerunning; changed text or selection gives `request_conflict`. After a
disconnect, retrieve the existing turn or repeat the same ID. A new ID means a
new analysis, not transport recovery.

### M10-18 first slice — selection admission only (PR #163, incomplete)

`selected_result_id` is a published API `result_ref`, not an internal workspace
name or digest. Authentication comes first. Admission resolves exactly one
completed, ACCEPTED result in the same session and pins its source turn, public
reference and version. Unknown, foreign, unpublished or ambiguous references
return `invalid_result` (422) without admitting work. Missing/null selection
retains the original runner behavior; an identical retry never runs again.

An explicitly supplied `selected_runner` receives the pinned identity on the
existing worker. Until the prepared workspace integration is implemented, the
standard prepared service has no such handler and returns `unavailable` (503)
for an otherwise valid explicit selection. It never silently discards selection.
This admission receipt is not proof that a workspace artifact is current: the
next slice must resolve/validate its stored version and staleness, bind planning
and tool execution, and record publication dependencies. Frontend selection,
recovery and end-to-end transform tests remain pending. Do not merge this first
slice as a completed selected-result fix.

## Bounded lifecycle

| Boundary | Limit |
| --- | --- |
| Sessions / turns | 8 sessions, 24 turns each including failures; no silent eviction |
| Execution | One admitted turn globally on a dedicated worker; no application backlog |
| Question | 4,096 characters and 8 KiB UTF-8; nonblank, no unsupported controls |
| HTTP body | 16 KiB before JSON parsing including chunked bodies; 5-second read deadline |
| Output | Under 1 MiB including wrapper; 2,048 cells; refuse excess, never truncate tables |
| Text | 8,192 characters; labels/units 240; at most 16 bounded notices |
| SSE | One stream per session; three recorded events; 30-second connection window |

The runner owns/opens/closes its database connection on the worker. HTTP
threads never receive a DuckDB connection or global mutable Session. `queued`
means admitted and awaiting that worker. Events preserve the real admitted,
running and completed-or-failed transitions; elapsed time starts at worker
entry, admission is zero. Full plan/tool/gate callbacks remain separate work.
Replay preserves observed times; reconnect using `Last-Event-ID` or poll after
the stream closes. No fabricated tool progress is emitted.

Restart invalidates capabilities and in-memory responses. There is no expiry
scheduler, reset/delete endpoint, automatic file cleanup or durable resume.
Shutdown refuses new work and waits for the existing runner; a Python thread
is not safely killable. Provider/analytic bounds belong to the runner. A
disconnect never cancels or retries analysis. Full wall-clock kill/isolation
remains separate work.

## Canonical values and trust

[project_answer](../src/kkb_agent/api/projection.py) takes `Answered` plus the
exact result read from the caller's **own published workspace**. Its digest
must match the last candidate and the answer must be ACCEPTED. Acceptance
alone cannot export candidates. QUALIFIED/ABSTAINED turns return safe answers
and notices without a newly published result in this slice.

Cells retain exact finite values, original slots, optional periods, units,
scales, stock/flow meaning, samples and lag. Display text uses the existing
deterministic formatter. Result version and claim kind survive; literal values
never upgrade unknown unit/scale. Cell/result references derive from the
server-issued turn and immutable result version, stable for repeat reads and
distinct across turns/versions. Clients may lay out cells but must not invent
missing cells or replacement values.

Raw outcomes, rejected sentences, prompts, errors, source locators and
transformation parameters are excluded. Gated prose/labels remain untrusted
text: render text nodes, never raw HTML. Conservative locator/credential
scrubbing and optional known-secret redaction prevent accidental display;
this is not a general secret detector. A production runner must use this
projector instead of raw internal serialization. `proof_graph="unavailable"`
is explicit; stable references are not a fabricated graph or verification
result. M10-08 owns bounded proof traversal; no unbounded Lineage.trace export.

## Local HTTP boundary

Exact localhost/127.0.0.1 Hosts with configured port and matching HTTP Origins
are accepted; default port is 8000. Foreign/null Origins, cross-site requests
and duplicate sensitive headers are refused. POST requires JSON; query strings,
form/plain-text submission, wildcard CORS, cookies and forwarded-host trust
are absent. The launcher must bind loopback. Possession is **not production
authentication** and resolves no hosting/TLS/retention question.

Errors contain only version and a fixed category, never rejected input or raw
exceptions. Unexpected route errors are contained before the ASGI logger.
Responses use no-store, nosniff and no-referrer. The launcher must disable
access logs; callers protect capabilities. No route accepts credentials,
paths, SQL, tool definitions or gate overrides.

## Dependencies and validation

FastAPI 0.141.1, Starlette 1.6.0 and Uvicorn 0.53.0 are pinned; no hosted service
is added. `pip check` passes. Existing httpx 0.28.1 stays the Kloudeks transport.
Two upstream test-client deprecations (httpx versus httpx2 and AnyIO
BlockingPortal) remain visible; no production transport migration is implied.
The app follows the primary [FastAPI lifecycle contract](https://fastapi.tiangolo.com/advanced/events/).

Tests use a real Session/gate over synthetic DuckDB data and cover canonical
publication, immutable cells, finite values, hostile HTTP, isolation, duplicate
questions, busy/capacity rules, safe failures, SSE replay and shutdown. No live
model/source request, deployment or live reasoning quality is claimed.
[EVALUATION](EVALUATION.md) records the final gate.
