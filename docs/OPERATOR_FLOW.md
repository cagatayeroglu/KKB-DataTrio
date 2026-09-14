# M10-01 — Operator flow and API boundary requirements

Status: M10-01 operator specification; the dated [M10-16 local API](LOCAL_API.md) now implements the bounded session/question/turn/result contract and turn-lifecycle SSE. This document retains wider requirements and historical backend gaps below; LOCAL_API owns current executable routes, limits and remaining gaps. Prepared-runtime startup, full plan/tool progress, proof traversal and the frontend remain separate integrations. [DEC-123](DECISIONS.md#dec-123--fastapi-with-sse-behind-a-nextjs-front-end) still requires a typed API before M10-03's client.

## One demo flow

Use synthetic/local-safe data for development rehearsal; real demo acceptance targets the prepared official dataset under DEC-136 with source-use permissions. Live source/model/OCR activity requires separate authorization. An operator must be able to distinguish a scripted rehearsal from live output; the existing live_check command is not an API or a safe automatic startup check.

| Step | Operator action | Application contract / observable outcome | Recovery and ownership |
| --- | --- | --- | --- |
| 1. Start | Open a fresh analysis session | Explicit session identity; readiness means local configuration/store capability, never an automatic provider call | Unavailable service exposes a fixed safe category; retry only by an explicit new operator action |
| 2. Load/select | Select prepared lakehouse data or supply an authorized document URL in the question | Prepared official observations are the financial-data input; the first four-series slice is prepared in an operator-local root (not committed; rebuild commands in ROADMAP). Uploads use existing admission/loaders. URLs use web_url and safe_fetch; no arbitrary connector or BDDK/EVDS adapter is implied. Show the source selection and unknown semantics | Rejected/unsupported source is not added as usable data. Ask for a supported format or required sheet/delimiter; do not guess |
| 3. Ask | Submit a question in this session, optionally referencing a prior result | Server validates bounded request and session-owned references, then invokes existing Session.answer with that session's connection/workspace and trusted registry | No client-selected provider, tool registry, connection path, SQL or gate override |
| 4. Inspect progress | Read plan/tool status while waiting | DEC-123 SSE target: validated step/tool identifiers and lifecycle status only. Plan inspection is informational; it is not a new confirmation gate or hidden reasoning view | Never expose raw plan arguments, model prompts, intermediate document content or exception text |
| 5. Inspect answer | Read accepted/qualified answer or abstention | Present GatedAnswer.text only after its gate. Preserve limitations, unknown semantics and omitted-claim indication without showing rejected sentences | An abstention is a completed safe outcome, not a transport failure or a value of zero |
| 6. Inspect result/evidence | Select a result cell and “Why this number?” | Show the recorded value with period/unit/scale; request bounded evidence for that immutable result/cell. Missing proof is explicitly unavailable/partial | No source ancestor alone upgrades a value to verified. Graph presentation cannot repair absent evidence |
| 7. Follow up | Add a series or change a period in the same session | Resolve only owned current workspace values; retain prior result identity and show stale/recomputed state, never silently overwrite displayed evidence | Refuse stale/unowned references. Unsupported follow-up asks for clarification; no automatic full-table reconstruction |
| 8. Recover/reset | Start a new analysis after failure, or request reset | A new session must not inherit another session's data. Reset/cancellation UX is M10-11; no destructive reset/delete endpoint is promised here | Preserve old evidence until the explicit retention/reset policy permits removal; disconnect does not mean a running job was cancelled |

The first UI may use concise text/table evidence, not an interactive graph canvas. Chart generation and full source-upload/follow-up/cancellation UI remain M10-04..11. M10-13/14 own actual UI rehearsal, including an independent teammate; a specification review is not a passed UI rehearsal.

## Prepared dataset selection and separate web inputs

The [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes the prepared BDDK/EVDS pool the primary official-data demo path. The four organizer concepts are the first real vertical-slice target, not final coverage. Build and validate the pool before runtime through reusable adapters → raw bronze → validation/normalization → silver → required gold → DuckDB + Parquet. Users select trusted prepared candidates and see actual requested-window coverage/unknowns. Bronze alone cannot establish a financial answer.

```text
User -> planner -> catalog_search (lexical now; required dense/vector target)
 -> trusted prepared candidate -> lakehouse silver / appropriate trusted gold
 -> guarded transforms / analytics -> mandatory correctness harness -> verifier
 -> accepted answer / table / chart / workspace
Prepared-pool miss or unresolved selection -> clarification / abstention
```

The normal core three-turn flow does not fetch BDDK/EVDS when a question arrives. Financial-source independence does not promise offline planning/query embeddings. Runtime official-source cache-miss materialization is a future policy-gated scalability extension, not a demo prerequisite. No generic web fallback or guessed coverage. M3-06's bounded offline Monthly adapter is delivered; live BDDK/CA acceptance, real prepared pool, EVDS ingestion, automatic routing and API/UI remain unfinished.

Final catalog retrieval adds the required Qwen 4096-dimensional embedding path and separate catalog vector similarity layer to BM25/aliases/filters. Neither dense nor vector index is implemented. The vector layer contains catalog descriptions/identity references, never financial observations. LanceDB is the selected catalog index (DEC-138); no new user-facing configuration flow is implied.

Preserve version/source vintage, actual coverage and refresh/revision history; do not promise a completed version manager. DEC-135 inspection and quality triggers apply before dependent use; their automatic wiring remains unfinished. The intended flow must work beyond housing balance/rate, CPI and national KFE over approximately 2021-01–2026-06, without hardcoded series selection.

General research is a separate planner branch: `web_search` (SearXNG compatibility candidate only), then only separately authorized `web_url`. Search results do not grant fetch authority. Crawl4AI is optional future extraction evaluation only. Uploaded CSV/XLSX/PDF and BIST/IMF/other authorized URL documents remain session artifacts; shared storage does not turn them into permanent official series. Prepared datasets are not canned answers or permission for silent fixture substitution. No new user-facing tool or permission flow is implemented here.

## Backend facts and integration prerequisites

- [Session.answer](../src/kkb_agent/agent/loop.py) returns Answered(planned, outcome, results, answer). It is synchronous and has no progress callback. Do not pretend post-hoc fabricated events were streamed during execution.
- Its Session has mutable rejection history; a process-global instance cannot be an uncontrolled multi-user session. [Workspace](../src/kkb_agent/agent/workspace.py) scopes bindings by workspace_id but defaults to `default`; this default must never silently identify an HTTP client. A workspace ID alone is not authorization. Some underlying result/artifact/lineage storage is shared, so arbitrary digest lookup is not a safe public API.
- Workspace.store_result/read_result retain and validate content-addressed AnalyticalResult values; artifact value_ref and bindings identify versions. These are the existing result snapshots, not a reason for a second UI result/provenance database.
- M5-21 stages a computed candidate in memory and publishes trusted workspace state only after successful execution, an ACCEPTED answer and candidate-level verification. QUALIFIED/ABSTAINED/errors do not publish. Publication is atomic and rejects changed workspace previews; earlier tool lineage/evidence writes are outside this transaction. A later API must still distinguish internal candidates from supported claims and preserve these failed-turn guarantees.
- [AnalyticalResult](../src/kkb_agent/core/results.py) has result_id, digest, run/step IDs, ResultValue entries, evidence, warnings and unresolved_semantics. ResultValue has no universal cell_id. Do not invent a global cell identity from a mutable label or an unrelated lineage node.
- [Lineage](../src/kkb_agent/lakehouse/lineage.py) stores hash-addressed typed nodes and edges. trace currently walks all ancestors; it is not a bounded public graph query. An adapter must bound database reads as well as returned JSON, rather than call trace then truncate.
- The [answer gate](../src/kkb_agent/agent/verifier.py) and [literal proof](../src/kkb_agent/agent/literal.py) remain the authority. API/proof projection must not rerun a weaker numeric matcher or equate a source hash with correctness.

These facts do not block operator-flow specification. They are acceptance requirements for the first API implementation; claiming a deployed/shared session service before satisfying them would be unsafe. Hosting, auth exposure, retention and restart behavior remain constrained by Q-INFRA-01/02, Q-DATA-03 and M10-02; no organizer answer is inferred here.

## Public payload requirements for the later typed API

This is a field-level design requirement, not implemented serialization. The API implementation must publish versioned Pydantic/OpenAPI schemas with extra fields rejected, explicit nullable fields, finite numbers, length/count/body limits and safe fixed errors. It must settle and test numeric bounds before opening an HTTP listener. All payloads are JSON data; the UI receives no internal Python objects.

| Payload | Required shape / reuse | What must not be forwarded |
| --- | --- | --- |
| Session | Opaque server-issued session_id; lifecycle/expiry capability stated explicitly; request/result membership checked against that session | Caller-controlled filesystem/database paths; `default` shared workspace; implicit tenant/auth claims |
| Question | question string, session identity; optional owned prior-result reference only where backend supports it | Gate kwargs, provider/model credentials, arbitrary tool definitions or SQL |
| Turn/answer | Opaque turn/result references; AnswerStatus `accepted`, `qualified`, `abstained`; gated text, safe limitations/warnings and bounded tool statuses | Raw Answered dump, omitted sentence text, raw rejections, provider completions or exception strings |
| Result/table | result identity plus immutable version; bounded columns/rows projected from canonical ResultValue data; value separate from optional display text; Period, unit, Scale, sample counts, claim_kind retained | LLM-calculated presentation values, fabricated cells, implicit currency/scale, arbitrary raw SQL-result export |
| Cell reference | Opaque address scoped to session + immutable result snapshot + value slot; selected document coordinates/source fragment retained by existing proof | Row-index/label alone across mutable versions; a hash treated as proof or exposed in answer prose |
| Source/evidence | Bounded safe source label/type, nullable period/semantics, warnings and evidence/proof references | Full locator query/credentials, internal paths, arbitrary node attributes or raw source/provider contents |
| Chart | Optional reference to a trusted result-derived data/spec, absent until supported by M10-07 | Generated Python/JS/HTML, model-executable chart code, an empty chart claimed as implemented |

For DEC-132, preserve `literal_source_value`, unit=null and scale=unknown when that is the source state. The complete bounded source quotation may be supported only after existing exact result/cell/source-fragment proof. Unknown analytical values remain unsupported. A literal figure is not implicitly a verified financial interpretation, and the display must retain the unspecified-unit/scale qualification.

At the HTTP boundary, evaluate a minimal health/readiness response, session creation, question submission and turn retrieval before adding specialized endpoints. Proof/table data may be part of that response or fetched by owned reference; route names are not frozen by M10-01. Do not build upload, chart, reset or graph endpoints just because the eventual UI needs them.

## Session/request isolation and failure lifecycle

Use a trusted server-owned mapping from opaque session IDs to workspace/connection context, not one global Session/Workspace. A request must not resolve an otherwise valid result/node from another session. Initially serializing work per session is acceptable; thread safety and total concurrent capacity must be explicit implementation choices. Shared DuckDB connections must not be used concurrently without a verified ownership model.

A future local-safe first API must explicitly state whether sessions survive process restart and when they expire. No durable auth, retention period, arbitrary cleanup or multi-tenant architecture is selected here. Missing/expired/unowned references return safe unavailable/not-found responses without revealing another session's existence. Reset must not delete a shared lineage store as a shortcut.

Transport failure, planning failure, tool failure and verification abstention are different outcomes. Reuse ToolStatus (`success`, `failure`, `partial`, `not_run`) and existing safe tool categories; fetch/document subcodes are allowlisted as in live_check, never exception strings. Transport-level invalid request/session/timeout/internal categories belong to the later HTTP adapter. Unknown internal failures map to a fixed generic response; request IDs may aid operator correlation without exposing payloads. Never automatically retry a question after a disconnect: it may already have executed.

## “Why this number?” proof requirements

Interaction: table cell → Why this number? → bounded recorded-evidence subgraph. This is analytical provenance for results produced by KKB DataTrio, not ORYN-style enterprise metadata discovery or discovery of external dbt/Airflow/SQL lineage.

Use the actual DEC-118 kinds:

- NodeKind: `source_file`, `series`, `transform`, `column`, `metric`, `claim`.
- EdgeKind: `derives_from`, `aggregates`, `deflates_by`, `cites`.
- Storage direction: upstream_id → downstream_id. A root query walks upstream but does not reverse stored edge meaning.

A target ProofGraph contains an owned result/cell reference, graph availability (`unavailable`, `partial`, `available`), nodes, edges, separately preserved verifier outcome, and limitations. Availability describes recorded graph coverage, not correctness. Nodes carry opaque ID, actual kind and a bounded safe label; no arbitrary attributes map. Edges contain actual endpoint IDs and actual EdgeKind. Do not invent `VerificationResult`/`InputSnapshot` nodes because the target architecture names them: return only records that exist. Do not manufacture a claim_id when current gate output lacks one.

The read-only adapter must resolve the owned immutable value first, then its actual evidence root. Traverse deterministically with explicit maximum nodes, edges, depth, label lengths, output bytes and database work; order parents by (ID, edge kind). Stop at budget exhaustion and report partial/truncated, never complete. Missing/invalid roots produce unavailable. Return no unrelated global roots and no fabricated edge to make disconnected evidence look complete. Existing document selected-cell proof is stronger than source presence; preserve that distinction. A complete-looking graph alone must never set a VERIFIED flag.

The exact executable graph schema, numeric limits, query implementation and cross-session tests belong to the later API/evidence implementation. M10-08 owns claim-level evidence inspection; DEC-128 defers graph-heavy layout, not stable evidence references. No new graph database, mutable UI provenance store or networkx dependency is needed for this specification.

## SSE requirements (DEC-123)

The future API must report observed lifecycle events in order with a per-turn monotonic sequence and owned turn identity. Minimum meanings: turn started; validated plan available; tool started/completed with ToolStatus and allowlisted category; gate started; turn completed with final gated-response reference; turn failed with safe error. Abstention is a completed turn with `abstained`, not an internal exception.

Instrument actual backend boundaries in its implementation task; do not simulate live progress by replaying a completed trace under misleading timestamps. Planner reasoning/prompts, raw arguments/results, document bytes, credentials, discarded drafts and stack traces never enter SSE. Reconnection/replay, cancellation and reset are not promised until M10-11 defines them. A stream ending unexpectedly does not grant another execution or erase evidence. SSE lifecycle hooks do not exist today.

## Acceptance of this specification and later implementation

M10-01 is complete when the eight operator steps, current-vs-target boundary, error/follow-up/reset behavior and result/evidence responsibilities are documented against merged code. Review links and actual enum names; retain explicit unsupported features. Existing offline session/verifier/workspace/lineage/document suites can substantiate the described backend facts; they are not API tests.

The later API acceptance must cover app/health/schema/serialization, two isolated sessions, invalid/unowned IDs, oversized input, accepted/qualified/abstained output, unknown semantics and literal values, stable versioned cells, deterministic bounded graph traversal with missing/unrelated evidence, read-only proof access, safe SSE and error redaction. Include sentinel credentials/query tokens/paths and ensure neither response nor stream exposes them. Reuse scripted providers/synthetic documents; no live calls are part of these gates.

No full UI, app listener, endpoint, executable wire schema, proof adapter, authentication, deployment or UI rehearsal is delivered by M10-01. M10-03 is the next existing client task, but it cannot start until an executable agreed API contract exists; triage that missing API implementation scope separately rather than silently bundling it into operator specification or frontend scaffolding.
