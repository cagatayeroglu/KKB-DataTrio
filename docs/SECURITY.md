# Security — hackathon-scoped boundary plan

Protect the boundaries relevant to this short-window product — development closes 20 September 2026 under [DEC-131](DECISIONS.md#dec-131--organizer-kick-off-brief-schedule-delivery-form-and-demo-day-input-scope) — without making ordinary development a security-release ceremony. [ROADMAP](ROADMAP.md) owns execution status, [AGENTS](../AGENTS.md) check triggers, and [EVALUATION](EVALUATION.md) adversarial coverage. These controls are required behavior for enabled capabilities, not a claim that those capabilities exist.

Implementation evidence lives in [ROADMAP Current Project Status](ROADMAP.md#current-project-status) and the linked task records. Delivered boundaries include ignore/config hygiene, fast CI, file admission with bounded CSV/XLSX/PDF parsing, bounded GET safe fetch with validated redirects, the Kloudeks transport with its destination and redaction controls, registry/argument/count validation, restricted lakehouse SQL, `web_url`'s binding to addresses the user wrote, and partial workspace/lineage/numeric matching. End-to-end stale/reference isolation and complete proof gating remain incomplete. M7-04 adds offline redirect negatives; validation and merge state are recorded in its ROADMAP record.

## Threat model and scope

Assets: Kloudeks credentials, organizer/private datasets, local files/network, compute/request budget, workspace integrity, analytical correctness, and demonstrable provenance.

Untrusted inputs: user-provided files/URLs, external pages/PDFs/spreadsheets/images, filenames/metadata, source responses, extracted/OCR text, and model/tool outputs derived from them. A document can contain malicious instructions even when its hosting domain is familiar. Authentication does not make a source's content trustworthy.

Primary threats: credential/data leakage; SSRF to local/private/metadata targets; parser/resource exhaustion; prompt injection into tool selection; arbitrary code/SQL execution; stale/corrupted state; and plausible unsupported financial claims. Boundaries must fail safely before unsafe side effects, while normal malformed-data errors remain actionable.

This is not a production multi-tenant platform. Kubernetes security, enterprise RBAC/RLS, production backup/restore, full DAST, SBOM/signing, and complex security infrastructure are not mandatory. Revisit only for concrete organizer/deployment requirements in DECISIONS.

## Control status and maintenance

- `[ ]` means control implementation or validation is unfinished.
- `[x]` requires implementation **and** passing relevant negative/positive tests; documentation of a policy alone is insufficient.
- PARTIAL means some code exists without full control acceptance. BLOCKED must name the missing answer/dependency.
- Each control has a delivery trigger. Disabled optional capabilities may be recorded as not applicable with a reason at the final gate; leave their unfinished control boxes unchecked.
- Update only controls changed in a security-sensitive task and their relevant roadmap milestone. Do not rewrite this catalog after ordinary analytics/UI work.

## SEC-KEY-01 — Secrets and credential storage

Status: PARTIAL — M0-04 (#3) validated ignore/config hygiene; M4 (#27) tests configuration and structured-error redaction; the secret-pattern scan is in fast CI. Full logging/export and live credential handling are not established. **A real MIA API key now exists** (delivered 2026-09-10) in the operator-local, git-ignored `.env`; it has been used only in operator runs Eray explicitly authorized on 2026-09-11 (the M4-12 smoke and the M4-15 live question), and no key value appears in this repository. This raises the stakes on the untested export/logging paths below rather than closing anything.

Threat: Keys or private credentials leak through Git, fixtures, logs, screenshots, exception representations, or CI output.

Required control: Inject credentials from environment/repository secrets only; never commit real keys or `.env`; use placeholders and synthetic tests. The organizer states the same rule independently (DEC-129) and adds screenshots, slides, chat messages and browser-side code as leak surfaces — relevant once a UI exists, since a key reaching client-side code is published. SecretStr representation masking is useful but does not protect explicit secret extraction or all serialization/log paths.

When: M0 hygiene before storing local credentials; M4 before real Kloudeks requests; check again at M11.

- [x] Add/validate ignore rules for `.env`, private inputs, caches, and generated sensitive artifacts.
- [x] Add placeholder-only `.env.example`; verify it contains no working credential. Every value stays blank and is enforced by `test_environment_template_has_only_blank_values`; confirmed non-secret endpoint/model identifiers are documented as comments rather than filled in, so the control needs no exception.
- [x] Validate missing/invalid credential configuration fails with a sanitized message.
- [ ] Test secret values absent from object repr, structured logs, errors, traces, and evidence exports.
- [ ] Keep real credentials out of tests; normal unit/feature CI needs no live Kloudeks key.
- [ ] Review scanner coverage/limitations before treating a clean scan as evidence; the existing script is not a full history scanner.
- [ ] Record a response for an actually exposed key: revoke/rotate, remove current exposure, assess history/artifacts, document sanitized incident metadata.

Intended tests: Synthetic credential sentinels in config/error paths; temporary safe fixtures for ignore/scanner behavior; inspect output for sentinel leakage without printing real keys.

Acceptance: No real credential is required for unit tests; configured secret sentinels do not escape through supported output paths; ignore/config behavior passes. A clean local pattern scan alone is not proof that all history is secret-free.

## SEC-KLO-01 — Kloudeks transport configuration

Status: PARTIAL — merged offline provider/config/schema-repair/doubles (#27); [DEC-129](DECISIONS.md#dec-129--official-kloudeks-endpoints-models-and-compatible-client-policy) records official transport/auth/models and image limits. M4-07 adds the transport ([kloudeks.py](../src/kkb_agent/llm/kloudeks.py)): DEC-129's host only, fixed paths and configured models, no redirects and no ambient proxy/environment settings, responses bounded in time and size, sanitized errors, and destination tests in place of the former `openai` name ban. M4-12's authorized live smoke passed for chat and embedding on 2026-09-11, reporting only safe metadata; OCR access, native tool/JSON guarantees and limits are still open. Availability/configuration is not a passing live test.

Threat: User/model text selects an attacker endpoint, credentials go to an unintended host, requests exceed quotas, or a silent third-party LLM fallback violates constraints.

Required control: The DEC-129 endpoint/auth contract is trusted operator configuration behind LLMProvider. The `openai` SDK is permitted solely as its compatible client; explicitly bind the Kloudeks base URL and reject default `api.openai.com` routing, third-party hosted LLM fallback and user/model endpoint overrides. Enforce TLS verification and bounded transport behavior; credentials must not follow redirects to another origin. This is a destination/service rule, not an import-name ban.

When: M4 live transport/auth implementation, before any real credential is used.

- Contract evidence: DEC-129 records the organizer endpoint/auth/model contract without credentials; this answers the documentation subpart, not the unfinished runtime control acceptance below.
- [x] Restrict endpoint selection to trusted configuration; user/source/model content cannot override it. (M4-07, #76)
- [x] Validate approved destination policy and require secure transport for credentials. (M4-07, #76)
- [x] Define redirects explicitly; reject unexpected origin changes and credential forwarding. (M4-07: never followed)
- [x] Set connection/read/total timeouts, response limits, and bounded attempts. (M4-07; transport retries remain M4-10)
- [x] Validate structured response locally and sanitize provider errors. (M4-07, #76)
- [x] Test exclusive Kloudeks routing and absence of third-party hosted LLM fallback, allowing the compatible SDK import itself. The blanket `openai` string-ban test was replaced in M4-07 (#76).
- [x] Add offline negative tests plus a separately authorized live smoke with safe metadata. Offline tests by M4-07 (#76); the authorized live smoke by M4-12 (#78), passed 2026-09-11.

Intended tests: Fake provider transport for alternate endpoint injection, redirect, timeout, oversized response, malformed model output, missing credentials, and failed TLS/config paths where applicable.

Acceptance: Only the confirmed configured provider can receive credentials; malformed output cannot invoke a tool; transport fails within limits. Any private organizer endpoint exception must be explicit and isolated to trusted provider configuration, never a bypass for user-controlled source URLs.

## SEC-TRUST-01 — External content and prompt injection

Status: PARTIAL — registry/argument injection negatives and user/system-role separation exist (#28). `web_url` (M7-17) fetches only an address written in the user's question, so neither a fetched cell nor a plan's restated question can pick a destination; its tests cover both. A value it returns (M7-18) is labelled with the plan's column and row, never document text, so a header cannot write into the answer prompt. Document extraction beyond CSV/XLSX, workspace/data permitted-reference enforcement and live URL use remain incomplete.

Threat: A PDF, spreadsheet cell, HTML page, image/OCR result, metadata field, or model response instructs the agent to disclose secrets, change rules, invoke unsafe tools, or fabricate evidence.

Required control: Keep system instructions/capabilities separate from source content. Treat all extracted text as data. A source cannot grant permissions or select an unrestricted execution path. Defensive prompt wording supplements typed/capability checks; it does not replace them.

When: M5 planner context construction and M7 extraction, before untrusted content reaches a tool-capable loop.

- [ ] Label and delimit source content/metadata as untrusted context with safe source IDs.
- [ ] Bound selected content and exclude credentials/full private payloads from planner context where unnecessary.
- [ ] Validate model output against registered tool schemas and permitted references regardless of source wording.
- [ ] Prevent embedded URLs/paths/SQL/code from executing merely because they were extracted.
- [ ] Preserve evidence of extraction uncertainty without trusting claimed validation inside the document.
- [ ] Test malicious PDF text, spreadsheet cells, HTML, source titles, and model output.
- [ ] Assert absence of prohibited tool/network side effects, not only a polite refusal sentence.

Intended tests: Inert instruction strings in synthetic fixtures and fake transports. Include “ignore instructions,” secret-sentinel requests, private URL suggestions, and fake system/tool-role text.

Acceptance: Hostile source content remains data and cannot bypass registry, fetch/file boundaries, or claim verification. Do not claim a prompt filter alone solves injection.

## SEC-TOOL-01 — Tool-call validation and bounded execution

Status: PARTIAL — registry, per-tool arguments, dependency ordering and count budgets exist (#28). `Session.answer` now applies result verification and multi-result gating (#44/#45/#47). Workspace/data-reference ownership, declared output types, total deadline/cancellation and enforcement for other callers remain incomplete.

Threat: Malformed/generated tool calls access unauthorized references, execute the wrong capability, bypass verification, or loop until budget exhaustion.

Required control: Validate tool name, per-tool typed arguments, referenced data/workspace, dependencies/output type, capability, and resource budget before dispatch. Mandatory material-claim verification is system policy, even if a plan field suggests otherwise.

When: M5 registry/executor, before any tool-capable model loop; extend tests with new capabilities.

- [x] Reject unknown/duplicate registry tool names.
- [x] Reject wrong/extra arguments and invalid ranges/enums before tool invocation.
- [ ] Resolve references through controlled workspace/data storage rather than trusting raw paths.
- [ ] Validate dependency order and actual input/output reference existence.
- [ ] Enforce step, retry, result-size, and request-deadline limits.
- [ ] Stop repeated identical invalid plans; do not compound provider and tool retry budgets silently.
- [ ] Prevent plan flags or model output from skipping required evidence checks.
- [ ] Return structured categorized failure and preserve prior coherent state.
- [ ] Test invalid names/args/refs, timeouts, repeated repair, and cross-workspace access.

Intended tests: Instrumented fake tools prove validation occurs before execution; deterministic failure chains verify attempts and state transitions.

Acceptance: No invalid/unauthorized call reaches an implementation, and execution terminates at configured bounds with a traceable safe outcome.

## SEC-SQL-01 — Model-generated SQL risk

Status: PARTIAL — DuckDB and restricted SQL are confirmed by DEC-112/121. M6-20 (#31) implements single SELECT, parsed table/function restrictions, whitelisted tables, EXPLAIN, bounded returned rows and database-level external-access/extension restrictions. Query-time/resource bounds and complete function/column/workspace scope are not established by those tests.

Threat: Query text reads/writes files, loads extensions, attaches data, accesses network resources, mutates storage, or consumes excessive resources. A SELECT statement can still invoke dangerous functions.

Required control: The `lakehouse` tool uses restricted SQL under DEC-121. Always parse/validate an allowlisted AST, restrict tables/functions, bind values, use read-only controlled analytical data, and disable file/network/extension capabilities. Do not directly execute model-generated SQL.

When: M6-20 and each extension of its enabled SQL boundary. Read-only SELECT text alone is insufficient; retain engine restrictions and targeted escape-path tests.

- [x] Decide whether a concrete tool needs SQL; record engine choice separately.
- [ ] Restrict statements, tables, columns, functions, and query complexity using the selected engine's actual capabilities.
- [x] Reject DDL/DML, multi-statements, ATTACH, extension loading, and file/network/table-function escape paths.
- [ ] For system-built query fragments, bind values and allowlist identifiers; never concatenate untrusted fragments. The complete model-proposed statement still requires the parsed whitelist/engine boundary.
- [ ] Enforce read-only access plus row/time/resource limits at the engine boundary.
- [ ] Add negative tests for writes, unsafe SELECT functions, file/network reads, comments/obfuscation, and excess work.

Intended tests: Synthetic local tables and fake paths/network sinks; assert both rejection and no side effect. Engine-specific controls need engine-specific tests.

Acceptance: Only approved read-only analytical operations over permitted data execute. Report which SQL controls remain incomplete; the enabled lakehouse tool cannot be described as an absent capability.

## SEC-EXEC-01 — Arbitrary Python/shell execution prohibition

Status: PARTIAL — registered callable dispatch exists (#28), with unknown shell/tool and extra-argument rejection. No arbitrary Python/shell capability is implemented; new parser/tool paths still need their own negative tests.

Threat: Input/model text becomes Python, shell, dynamic imports, or unrestricted subprocess execution on the host.

Required control: Registered deterministic Python implementations only. No runtime `eval`, `exec`, generated Python execution, unrestricted subprocess, or imports selected by input. Ordinary developer commands are distinct from product capabilities.

When: M5 tool executor and every new analytical/parser extension.

- [ ] Keep execution dispatch system-owned and input arguments data-only.
- [ ] Reject tool/schema requests carrying arbitrary executable code or module names.
- [ ] Review new tool boundaries for dynamic execution and unrestricted subprocess use.
- [ ] If a fixed parser utility is needed, justify it, constrain arguments/resources, and never derive a shell command from input text.
- [ ] Test code/shell/import payloads cannot execute or create files/network requests.

Intended tests: Instrumented registry plus inert payload strings and safe filesystem sentinels. Static inspection complements, but does not replace, dispatch tests.

Acceptance: No supported product input provides arbitrary Python/shell execution. A future requirement would need an explicit decision and real isolation design first, not a quick bypass.

## SEC-FILE-01 — File admission and safe storage

Status: PARTIAL — local admission/storage checks and negatives delivered in M1-02 (#5), specified in [FILE_ADMISSION](FILE_ADMISSION.md). M7-05 (#38) now bounds direct-GET response/decompression streams. Fetched CSV/XLSX bytes pass the same admission checks and loaders as uploads (M7-08), and PDF bytes likewise (M7-09), with the loader chosen by the validated response media type and the bytes re-checked against it; other downloaded formats have no parser route.

Threat: Uploaded/downloaded filenames escape storage roots; misleading extensions/MIME route malicious content; large inputs exhaust memory; private uploads leak into Git/artifacts.

Required control: One admission boundary for uploaded and downloaded files, with supported extension/MIME/content checks, configured limits, generated storage IDs, and controlled local paths. Filenames are metadata, not paths.

When: M1 CSV/XLSX ingestion; reuse at M7. Implement before any upload/download parsing exposure.

- [x] Define supported formats and per-format byte/row/column limits.
- [x] Enforce byte limits before full buffering/parsing, including streamed downloads.
- [x] Check extension, declared MIME, and content signature/structure; reject mismatches or route only under an explicit safe policy.
- [ ] Normalize/validate storage paths and generate internal names; reject traversal, absolute paths, and unauthorized symlink escapes.
- [ ] Separate raw/derived/temp data from source code and Git-tracked fixtures.
- [ ] Return sanitized errors for empty, malformed, oversized, unsupported, and ambiguous input.
- [ ] Add path, MIME/content mismatch, empty/malformed, and boundary-size negative tests.

Intended tests: Temporary-directory synthetic inputs; `../`/absolute-path names, mismatched bytes, exact limit/limit+1 cases, and early-parser-call instrumentation.

Acceptance: Rejected files never reach parsers; accepted files remain inside controlled storage and configured limits. No private upload becomes a fixture by default.

## SEC-FILE-02 — Parser and document resource limits

Status: PARTIAL — bounded XLSX package validation, explicit selection, active-content rejection and terminated parser worker delivered in M1-09/10 (#11/#16). The bounded CSV loader followed in M1-06 (#53): structural row/column/cell/field limits run before row allocation, and a terminated spawn worker bounds parse time, output size and (on Linux) address space. The PDF loader (M7-09/M7-10) uses the same worker with a page cap, field/table/cell budgets and its own deadline, and refuses encrypted, malformed and text-less PDFs with fixed codes; its tests include a 6 KB file that expands into runaway work and is killed at the deadline. M7-11 adds explicitly enabled, bounded PDF OCR text only; M7-07 adds bounded static HTML; image-address parsing and operator bulk-path containment are not delivered.

Threat: XLSX/other containers expand massively, PDFs/images consume excessive resources, embedded formulas/macros/scripts execute, or parser uncertainty becomes fabricated analytical data.

Required control: Per-format bounded parsing and explicit extraction uncertainty. Limit expanded bytes, entries, rows/columns/sheets, pages, image dimensions/pixels, execution time, and returned text as applicable. Do not execute macros, embedded scripts, spreadsheet formulas as code, or external resource links.

When: M1 parser implementation and each additional M7 format before enablement.

- [ ] Choose maintained parsers only after dependency/engine decision and document required capabilities.
- [x] Bound XLSX container entry count/expanded size and sheet/row/column counts.
- [x] Make formula cached-value handling explicit; never silently imply recalculation or trustworthy freshness.
- [ ] Disable external-link/resource resolution where applicable.
- [ ] Bound PDF page/object/text processing and image/OCR dimensions/work; reject unsupported encrypted/scanned content explicitly.
- [x] Ensure parser work can stop within configured time/resource limits; an outer timeout alone must not leave runaway work.
- [x] Preserve page/sheet/table/cell location and low-confidence extraction warnings.
- [x] Test corrupt containers, excessive expansion, malformed documents, embedded instructions, and limit exhaustion.

Intended tests: Small synthetic pathological fixtures rather than huge harmful files; instrumented bounded parser behavior and maximum-output assertions.

Acceptance: Enabled parsers cannot exceed documented tested limits silently or execute active content. Unsupported extraction does not produce invented numbers. Record the actual configured limits before claiming support.

## SEC-URL-01 — Central safe fetch / SSRF / redirects

Status: PARTIAL — M7-01/02/03/05/06 are merged and validated (#35–38; 340 targeted / 892 unit at #38 delivery). [safe_fetch](../src/kkb_agent/ingest/safe_fetch.py) implements GET with DNS-to-socket binding, verified TLS and bounded response handling. M7-04 follows only 301/302/303/307/308, with fresh validation/binding per hop, a default cap of 3 and canonical-URL loop detection. Headers share one aggregate budget, redirect bodies are closed unread, and the same supervised worker retains one total deadline plus per-hop DNS/connect deadlines. POST, source trust configuration and adapter integration remain incomplete. Downloaded CSV/XLSX/PDF reach the upload parsers only through `web_url` (M7-08/M7-17/M7-09). Live exposure still requires Q-DATA-01/Q-NET-01/02.

Threat: User/model URLs target localhost, private services, link-local/cloud metadata, redirect to forbidden targets, rebind DNS, steal credentials, or stream excessive content.

Required control: All external **source retrieval** uses one safe-fetch boundary, including named adapters and URLs found inside documents. The trusted configured Kloudeks transport is separately controlled by SEC-KLO-01. Default to blocking unsafe destinations, not best-effort warnings.

When: M7 safe fetch, before M3/M7 live source retrieval. Network-policy answers do not replace technical controls.

- [ ] Centralize source fetching; reject direct HTTP bypasses in adapters/parsers.
- [x] Allow only HTTP/HTTPS; reject userinfo/credential-bearing URLs and non-approved port behavior.
- [x] Normalize/validate hosts and resolved addresses, including alternate IP notation and IPv6.
- [x] Block localhost/loopback, private RFC1918, IPv6 local ranges, link-local, unspecified/reserved unsafe destinations, and cloud-metadata addresses/hostnames.
- [x] Validate all resolved DNS addresses; reject mixed public/private results.
- [x] Bind validation to the actual connection target to address DNS rebinding/time-of-check mismatch; test the chosen approach.
- [x] Handle redirects explicitly and revalidate every followed hop before connecting. M7-04 requires exactly one usable Location; malformed/unsupported redirects fail closed.
- [x] Enforce redirect cap and loop detection; never forward credentials/cookies to a new origin automatically. M7-04 rebuilds only fixed GET headers and preserves hostname/TLS checks.
- [x] Configure connect/read/total deadlines and bound compressed/decompressed response bytes.
- [x] Validate content type and bytes before parser routing; limit streams even when Content-Length is absent/false.
- [x] Control proxy/environment behavior so it cannot silently bypass destination policy.
- [x] Return sanitized structured blocked/timeout/size/content errors and record safe destination metadata.
- [x] Add negative tests for schemes, public-to-private redirects, IPv4/IPv6, metadata, mixed DNS, rebinding, slow/oversized streams, and redirect loops. M7-02/03/05 and `test_safe_redirects.py` cover the enabled GET boundary offline.

Intended tests: Fake DNS/transport or controlled local test doubles that simulate destinations; do not actually contact metadata/private services. Assert forbidden destinations are never contacted, not merely that the final response is rejected.

Acceptance: Every enabled source network path enforces destination checks through the final connection and every redirect, plus byte/time/content limits. URL syntax parsing alone is not SSRF protection. If safe enforcement is not achievable, keep the affected live capability disabled.

## SEC-LOG-01 — Logging, redaction, and evidence exports

Status: PARTIAL — provider representations and validation errors have targeted redaction tests (#27). No integrated logging/export sanitization service exists. Source locators and query-purpose metadata still need consumer-side sanitization. M7-20 adds only enum-allowlisted `FetchCode` to the document operator report for fetch failures; arbitrary reason strings, URLs, DNS addresses and raw exceptions are excluded. The M7-19 admission-report follow-up applies the same allowlist-only policy to existing admission/loader codes (`document_code`); no raw document or error text is exposed. This does not establish a general logging/export service.

Threat: Logs/traces/scorecards leak credentials, signed query strings, private document contents, or cross-workspace data; raw exceptions expose sensitive configuration.

Required control: Default to IDs, stage, category, duration, counts, and redacted metadata. Keep provenance useful with safe locators/fragments; do not dump complete payloads. Apply sanitization consistently to errors and optional debug/export paths.

When: First M4/M5/M7 runtime logging and M8/M9 artifacts, before real inputs.

- [ ] Define safe structured log fields and sanitize source locators/query parameters.
- [ ] Redact credential-like fields/headers and synthetic sentinels in nested error/context structures.
- [ ] Avoid raw prompt, response, document, table, and credential dumps by default.
- [ ] Keep evidence references resolvable without exposing sensitive locator parts.
- [ ] Make any necessary diagnostic content capture explicit, local, bounded, and permission-compatible.
- [ ] Test happy/error/retry/export paths for secret and private-payload sentinel leakage.

Intended tests: Synthetic sentinels across nested exceptions, provider/source errors, and scorecard/evidence outputs; check outputs without logging the sensitive real data they stand for.

Acceptance: Normal diagnostics support tracing a run using safe metadata; no tested sensitive sentinel appears in public-facing/log/export paths.

## SEC-DATA-01 — Retention, private data, and workspace isolation

Status: BLOCKED for organizer retention permission (Q-DATA-03/Q-INFRA-02); local safe defaults can be designed now.

Threat: Organizer data is committed, retained longer than allowed, reused across sessions, or exposed through stale/cross-workspace references and shared demo artifacts.

Required control: Until permission is confirmed, use synthetic fixtures and do not commit private inputs. Treat local retention/cache as unconfirmed. Define controlled storage, cleanup, workspace-scoped reference resolution, and honest persistence behavior before handling private data.

When: M1 storage, M5 workspace service, M8 artifacts, and M11 demo preparation.

- [ ] Obtain retention/cache/redistribution answers with evidence in OPEN_QUESTIONS.
- [ ] Define local input/temp/derived/output locations, retention duration, and cleanup trigger before private ingestion.
- [ ] Prevent cross-workspace reference access and stale derived-result reuse.
- [ ] Keep raw data, derived outputs, logs, and screenshots out of committed fixtures unless explicitly permitted.
- [ ] Test workspace separation, reset/cleanup behavior, and failed-turn preservation.
- [ ] Label permitted cached data with source/version/retrieval time and distinguish it from live retrieval.

Intended tests: Two synthetic workspaces, invalid references, reset/cleanup under success/failure, and cache invalidation after input changes.

Acceptance: Recorded policy matches actual cleanup/persistence behavior; no private dataset is committed or cached based on an assumption. Enterprise tenancy/RBAC is not required to enforce local reference isolation.

## SEC-REPO-01 — GitHub/private repository and development artifacts

Status: PARTIAL — fast credential-free PR CI is delivered (#15) and runs on PRs into dev. Remote access/branch-protection acceptance remains M0-06; branch names or passing CI do not prove settings.

Threat: A supposedly private repo is public, history/artifacts expose data, workflow changes leak secrets, or broad Git operations publish unrelated work.

Required control: Verify remote visibility/access in an authorized setup task; inspect intended diffs/files before publication; keep ordinary CI synthetic and credential-free. A private repository is not a secret store.

When: M0 setup before sharing/publishing; authorized PR/release tasks; M11 final artifact review.

- [ ] Verify actual remote privacy, collaborator access, and branch protection without claiming local branch names prove settings.
- [ ] Add/validate ignore rules and safe fixture policy through M0.
- [ ] Inspect intended staged/diff contents and untracked files before authorized publication; avoid broad accidental inclusion.
- [x] Configure credential-free feature CI; restrict secret-bearing live checks to justified explicit workflows.
- [ ] Inspect permitted CI artifacts/screenshots/reports for sensitive data.
- [ ] Review relevant history for secret exposure at the final gate; do not imply the current scanner checks history.
- [ ] Preserve explicit commit/push/merge/settings authorization and understandable history.

Intended tests/review: Lightweight diff/file review on publication; synthetic CI and scanner tests; authorized remote-setting inspection; final history/artifact review scoped to real exposure risks.

Acceptance: Visibility/settings are evidenced, published changes contain only intended safe files, and unit CI does not require private inputs or real credentials.

## SEC-DEP-01 — Dependency policy

Status: PARTIAL — dependency integration/installation evidence is recorded in M1-03 and merged fast gates. Since M0-08, `make full` runs `pip-audit` with two named, reviewed exceptions (PYSEC-2026-113, Arrow C++ IPC pre-buffering that pyarrow does not expose; PYSEC-2026-1845, pytest's shared `/tmp` directory in a development-only tool); any other finding fails the gate. Reasons live in ROADMAP's M0-08 record; release reproducibility remains checkpoint work. `pdfplumber` joined the runtime manifest from the DEC-124 allowlist for M7-09 (with `pdfminer.six`, `pypdfium2`, `Pillow` and `cryptography`), and `make full` on that head found nothing new; its Ghostscript repair path is never called. DEC-124 is an allowlist, not a requirement to install all packages; DEC-130 requires the hybrid lexical+dense baseline with the retained lightweight LanceDB index, while RRF/reranking and extra retrieval infrastructure remain benchmark-gated. This does not claim those dependencies or runtime paths are delivered.

Threat: Unnecessary or unsuitable dependencies add parser/network vulnerabilities, slow setup, or make the demo irreproducible.

Required control: Add a dependency only for material implementation-time/delivery-risk benefit. Review maintenance, needed capabilities, runtime side effects, and compatibility. Do not add an engine/framework before its unresolved team choice is settled. Freeze a reproducible set for the final candidate using a team-agreed mechanism.

When: Any dependency addition; audit at defined full gates and final demo, not every ordinary edit.

- [ ] Record why a new dependency is needed and whether existing code/dependencies suffice.
- [ ] Check required parser/engine features and unsafe defaults relevant to its boundary.
- [ ] Run targeted tests for the integration and required gate for changed boundaries.
- [ ] Run/review `pip-audit` through the full gate when applicable; distinguish findings from accepted fixes/limitations.
- [ ] Establish final candidate dependency reproducibility before rehearsal.

Intended tests/review: Integration fixtures and installation on the demo environment; targeted negative tests for new parser/network capabilities; gate audit review.

Acceptance: Dependencies have a concrete purpose, tested integration, and recorded final versions/configuration. Do not install new Markdown/security tooling solely for a documentation task.

## CI security tiers

[fast-pr.yml](../.github/workflows/fast-pr.yml) runs the existing `make pr` gate on pull requests targeting `dev`, with a read-only GitHub token and superseded-run cancellation. [Makefile](../Makefile) owns command definitions; ROADMAP owns observed results.

| Tier | Actual command / intended use | Frequency |
| --- | --- | --- |
| Local ordinary | Targeted tests + touched-code lint or `make quick` | Every ordinary code task; <=60 seconds target |
| Feature -> dev | `make pr`: format/lint, unit tests, Bandit, local secret-pattern scan | Requested PR gate; <=3 minutes target |
| Full/release | `make full`: adds mypy/full pytest/dependency audit to static/security checks | `dev -> main`, final checkpoint, explicit full-check request; ordinary boundary changes use targeted negatives + fast PR gate |
| Benchmark/rehearsal | Separate runner/operator commands once implemented | EVALUATION-defined gates; not implicitly included in `make full` |
| Documentation only | Diff, links/paths, checkbox/status review | No application/security/release checks |

Network-dependent audits/live tests can fail because infrastructure is unavailable; record that result honestly and keep acceptance pending. Do not substitute “not run” for “passed.” Profile/split checks that repeatedly exceed the budget; do not normalize slow feedback.

## Final-demo security checklist

Run this at M11, not after ordinary prompts. Record command/review evidence in M11 and relevant control sections. Optional disabled capabilities need a documented not-enabled outcome rather than a false completion check.

- [ ] Confirm enabled sources/formats/tools match implemented and tested boundaries.
- [ ] Verify no real secrets/private organizer data in intended Git history, current files, demo screens, or exported artifacts; rotate any actually exposed key.
- [ ] Confirm live model traffic uses only the approved Kloudeks configuration and safe credential handling.
- [ ] Complete required full gate and review dependency/security findings.
- [ ] Pass applicable tool-validation, code-execution, prompt-injection, and bounded-retry negatives.
- [ ] Pass SSRF/DNS/redirect/stream limits for every enabled source-network path.
- [ ] Pass MIME/size/path/parser/active-content negatives for every enabled upload/document format.
- [ ] Pass lakehouse SQL restriction and resource/reference tests for the enabled capability.
- [ ] Verify logs/evidence/scorecards are sanitized and material claims cannot bypass verification.
- [ ] Confirm retention/cache/fallback permissions and test cleanup/workspace separation.
- [ ] Rehearse a hostile input, provider/source outage, and recovery within the actual demo workflow.
- [ ] Record remaining limitations and go/no-go; do not enable an untested risky capability to make the demo appear broader.

### Literal document claims (DEC-132)

External document values remain untrusted until exact source/value binding succeeds. The execution-owned literal tag is not a model argument. Its selected-reading snapshot, raw-cell digest, coordinates and source fragment must match the content-addressed lineage nodes in the current store; source presence alone, a changed value or an analytical transformation is insufficient. Only a fixed source-quotation answer can use unresolved semantics, with an explicit unspecified-unit/scale statement; it grants no currency, percent, index, comparison or transformation permission. Internal result/evidence/lineage handles are withheld. Full source bytes remain unpersisted; the proof retains only bounded selected-cell metadata. No fetch, admission, parser or OCR guard is relaxed.

### M7-11 OCR trust boundary

Only text-less pages use the opt-in OCR fallback. pypdfium2 renders inside the existing killed/reaped parser worker with page/pixel/PNG/output/deadline bounds; no browser, Ghostscript, external image URL or repair execution is introduced. Kloudeks OCR uses fixed destination/model/request fields and inherited TLS/no-proxy/no-redirect/response bounds. At most three separate page calls, no retries. No environment is read by the loader; the operator must inject capability explicitly.

OCR output is untrusted text, even when it looks like a table or says it has been verified. Layout-token removal is presentation cleanup, not validation. It stays outside native PDF cells and cannot create an AnalyticalResult, verifier-supported number or DEC-132 literal quotation. Missing schema and total/consistency checks are not waived. Raw OCR/provider content and PNGs stay out of repr, warnings and lineage; fixed OCR_FAILED/OCR_EMPTY/OCR_INCOMPLETE codes are operator-allowlisted. Native selected-cell proof is unchanged. Mocked tests only; live OCR needs separate approval and does not follow from prior CSV acceptance.

### M7-07 static HTML boundary

HTML never grants authority. Only the original question URL reaches unchanged safe_fetch DNS/peer/TLS/redirect guards. HTML charset is checked before response parameters are discarded; only UTF-8/BOM is admitted, with meta declarations checked locally. The terminated parser worker bounds input/depth/text/tables/cells/output/time; malformed or unsupported table structures fail closed. No scripts, styles, forms, event attributes, meta navigation, browser rendering or linked assets are executed/fetched. Source-local table/cell IDs and redacted content-hash provenance reuse the existing literal proof; captions/visual styling cannot invent units. OCR behavior and analytical unknown-semantic checks remain unchanged. Parser failures expose fixed categories only. CSS-computed visibility and JS-rendered content are not supported; untrusted text remains data, not safe HTML for UI insertion.

### M10 operator/API boundary requirements

[M10-01](OPERATOR_FLOW.md) specifies session-scoped references, safe answer/evidence projection and bounded read-only proof requirements. No HTTP boundary is implemented or declared secure by this specification. The current default workspace, shared artifact lookup, mutable Session, pre-gate result recording and unbounded Lineage.trace must not be exposed directly. A later adapter must enforce ownership, bounds and redaction, preserve gate states and distinguish recorded source ancestry from value proof. Retention/auth/deployment questions remain open; no live service is authorized here.

<a id="product-tool-boundary-dec-133"></a>

## Product tool boundary (DEC-135)

Approved target names are not executable capabilities. Expose only registered, implemented tools with closed typed arguments and typed results, bounded execution and trusted reference checks. M13-04 `catalog_search` reads operator-injected reviewed catalog state only: no model-supplied SQL, filesystem path or network URL; no mutation or implicit external loading. Treat labels, aliases and source metadata as untrusted data, including instruction-looking text. Return only catalog-backed metadata; unknowns remain unknown. Semantic/security guards, lineage and verifier/gate remain mandatory harness layers, never optional planner calls. Planned table_transform must meet these same controls before registration; this rule does not claim unfinished executor output/reference checks already exist.

DEC-135 requires deterministic metadata inspection before selected financial-series observations are used and bounded quality validation before observations become analysis-ready. Multiple trusted sources/results supporting the same measure require conditional reconciliation of semantics, period, frequency, unit, scale and values; unsupported comparability remains NOT_COMPARABLE/NEEDS_TRANSFORM/NEEDS_INPUT, never inferred. These controls must not depend on planner tool selection or a model-supplied bypass flag. M13-13/M1-12/M8-09 automatic wiring is still unimplemented; this policy does not certify those paths as secured or replace existing guard/verifier checks.

### M7-22 offline search boundary

`web_search` accepts only bounded query/max_results and an operator-injected trusted SearchBackend. Backend credentials/configuration are outside planner schemas; exceptions become fixed codes. Spawned execution has a deadline, terminated/reaped worker, suppressed backend stdout/stderr, typed hit/field caps and a 64 KiB JSON response cap; adapters must bound their own wire I/O and are not sandboxed. Existing URL policy is applied offline: unsafe schemes/credentials/local/private literal targets are excluded; hostname DNS is not asserted. Query/fragment-free display locators are flagged and deduplicated conservatively, never treated as equivalent fetch authority. Titles/snippets remain untrusted metadata, not AnalyticalResults or writer evidence. `URL_NOT_IN_QUESTION`, DNS pinning, TLS, lineage and verifier behavior are unchanged. Only synthetic test backends exist; no production/live search acceptance is claimed.
