# M3-05 — Offline monthly housing selector metadata

This bounded implementation defines candidate identity and metadata only under
[DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime).
It performs no network, file, database, observation ingestion or planner/tool
registration. Full BDDK ingestion and broader M3-05 mappings remain unfinished. The bounded
M3-06 offline ingestion implementation is described below; it reuses this boundary.
The [source inventory](BDDK_SOURCE.md) remains unchanged historical evidence,
including its content hash pinned by M13-08.

## Identity and review boundary

[BddkSelector](../src/kkb_agent/ingest/bddk_monthly.py) requires explicit
bulletin_family, table, row, bank_group, presentation_currency and
value_dimension; provider is fixed to BDDK and geography is null where
inapplicable. No TP/YP/TOTAL default exists. Numeric selectors are strict bounded
integers; family/currency/dimension are closed choices and geography is a bounded
token. Free text cannot change the selector or introduce executable instructions.

Canonical UTF-8 JSON uses sorted keys, compact separators and the schema label
`bddk-selector-v1`. The internal ID is `BDDK:selector:v1:<sha256(canonical JSON)>`.
Period, retrieval time, captions and labels are not identity fields. A changed
family, table, row, group, currency, component or geography has a distinct
fingerprint. Unknown fields and invalid types fail closed; fingerprinting a
syntactically valid unreviewed selector does not make it a supported candidate.
These selector syntax bounds do not assert source support for all such numbers.

`monthly_housing_catalog` admits only monthly table 4, row 2, Sektör 10001,
TL presentation and null geography, with an explicitly supplied TP, YP or TOTAL
component. Other groups/currencies, Weekly and FinTürk, unknown rows and the
synthetic fixture row 9001 cannot acquire reviewed monthly metadata. No FinTürk
thousand-TL declaration is silently treated as monthly million-TL data.

The existing CatalogRecord holds the internal ID in `series_id` and a visibly
labelled `selector-v1:<canonical JSON>` composite in `source_series_id`.
Neither is represented as an official BDDK series code. The composite retains
the source-supported selectors; the internal ID is an opaque catalog key.
SourceRef pins the reviewed BDDK inventory revision and SHA-256, not a retrieved
observation artifact. Construction opens no path or URL.

## Semantics and ambiguity

All three reviewed components declare monthly period-end outstanding STOCK,
NONE cumulative behavior, TRY/MILLION. TL presentation is independent of TP/YP/
TOTAL: even the YP component here is displayed in TRY. No values are rescaled,
differenced or relabelled as disbursement. Active/archive status, per-component
coverage and aggregation permissions remain UNKNOWN; no observations or sample
values are fabricated. Metadata declarations do not authorize calculations.

The record round-trips through CatalogRecord and can be wrapped by the existing
ReviewedSeries contract. This change does not modify M13-08's reviewed JSON,
replace its aliases, or register anything in catalog_search. Its unresolved BDDK
balance/disbursement entries remain unresolved. A later separately reviewed
snapshot may add explicit selector candidates without silently equating natural
language “konut kredisi” with TOTAL or stock with new disbursement.

## Metadata projection contract for the later response parser

MonthlyHousingMetadata carries only bounded success, caption, seven ordered
column headers, numeric row selector, row label, bank-group label and optional
aware retrieval time. MonthlyPeriod carries request year/month separately.
`validate_monthly_housing_metadata` requires:

- Boolean success is true, not coerced from a number or string.
- Exact reviewed caption `Tüketici Kredileri (milyon TL), Dönem:YYYY/M` agrees
  with the requested period; missing/changed unit or period fails closed.
- Headers are exactly `['', '', '', 'BasitFont', 'TP', 'YP', 'Toplam']` in order.
- Row number 2, label `Tüketici Kredileri - Konut` and bank group `Sektör` agree.
- The selector itself is within the reviewed subset.

This is a metadata projection validator, **not a full wire-response parser**.
The later adapter must establish that these fields come from the same response,
handle failure envelopes, validate unique row/cardinality and full cell/header
shape, preserve raw source provenance, and parse numeric observations. No
`colModels` fields, error envelope, request body or undocumented wire schema is
invented here. Strict caption matching may reject a legitimate changed source
format; review the new format rather than silently inferring units.

## Reusable ingestion target

[DEC-137](DECISIONS.md#dec-137--catalog-complete-lakehouse-first-official-source-materialization-architecture) preserves this delivered metadata slice while general M3-05 stays PARTIAL. The housing selector is the first verified use case for a reusable BDDK path: trusted selector → bounded official request → response validation/snapshot → source parser → Observation → validated/versioned lakehouse. The [DEC-137 dated refinement](DECISIONS.md#dec-137-prepared-pool-refinement) makes BUILD / REFRESH of the prepared official pool the primary near-term adapter role. Runtime cache-miss materialization is future scalability, not a core-demo prerequisite. M3-06 below implements the bounded offline Monthly path; current range/content changes require a new version rather than performing incremental refresh. Broader mappings and refresh/vintage promotion remain future work, and nothing resolves TP/YP/TOTAL on behalf of a natural-language request. The hash-pinned source inventory remains historical evidence; new mappings need their own review.

## Remaining work and validation

M3-06 has a bounded offline implementation below. Live source/egress approval,
BDDK CA-chain acceptance, real dataset preparation and broader mappings remain
unfinished. No Weekly, FinTürk, EVDS, gold, planner/runtime routing or live
acceptance is included.

[Offline tests](../tests/unit/test_bddk_monthly.py) cover identity/dimension
separation, strict review, source evidence, serialization/catalog round-trip,
period/clock independence, metadata failures, synthetic/injection inputs and
unchanged NL ambiguity. The existing cumulative conversion rejects the produced
stock declaration. Exact command results and PR evidence belong to
[ROADMAP](ROADMAP.md#m3).

## M3-06 bounded Monthly ingestion (offline validated)

[MonthlyRequest / MonthlyRange](../src/kkb_agent/ingest/bddk_monthly_request.py)
and [ingest_monthly](../src/kkb_agent/ingest/bddk_monthly_load.py) consume the
validated selector and inclusive month range. The review dispatcher currently
supports the M3-05 table 4 / row 2 / sector / TL contract, separately for TP, YP
and TOTAL. Unsupported identities fail before retrieval. Broader source
contracts must extend the reviewed metadata boundary; request iteration,
transport, manifest and storage do not embed housing row numbers or labels.
No free-form metadata, URL, body or planner-callable adapter tool is accepted.

The official HTTPS BasitRaporGetir form contains only `tabloNo`, `yil`, `ay`,
`paraBirimi`, `taraf`. Row/component selection happens in the response. Selector
and month produce a deterministic request fingerprint. The common fixed fetch
worker independently revalidates the Monthly descriptor and matching fixed
endpoint/limits, then uses the existing DNS/peer binding, system-verified TLS
and bounded HTTP parser. No redirect, cookie, authentication, proxy or retry is
introduced. Source access permission remains the trusted caller's responsibility.

Operator ceilings: 120 months/requests, 256 form bytes, 16 KiB response headers,
1 MiB encoded body, 2 MiB decoded body per response, 5-second connect/read and
30-second whole-request deadlines. Requests are sequential; at most 3600 seconds
of network work for the maximum range, without a database transaction. These
bounds are not BDDK quotas. No live CA path was tested; if system trust cannot
verify the chain, retrieval fails. A reviewed issuer bundle and deployment
verification remain separately authorized live preparation work where needed.

The parser checks successful JSON, complete single-page shape, unique row
identities, exact selected seven-cell/header shape, bank group, reviewed label,
report/unit and requested month. Unknown `colModels` and unselected labels/font
hints remain inert; their undocumented semantics are not guessed. Only JSON
numbers or null are accepted for the selected value. Non-finite numbers and
integers that cannot be represented exactly in silver DOUBLE are refused.
Monthly calendar bounds include leap years. Null stays missing, with no fill,
rescale, differencing or stock-to-disbursement relabeling.

Every used raw response is immutable content-addressed bronze. The internal
`bddk-monthly-batch-v1` JSON manifest binds canonical selector, exact start/end,
ordered periods/request fingerprints/raw hashes, parser and semantic versions,
transformation policy and normalized-observation hash. Its own SHA-256 is the
artifact ID referenced by `silver_series`; it is explicitly **our internal
manifest**, not an official response. Retrieval timestamps stay in bronze
metadata and do not change content identity. Source lineage reaches every raw
response through the manifest and normalized series; analytical outputs still
require M8-21 execution evidence.

Fetch/snapshot/parse/validate the entire batch before a short DuckDB transaction
registers the series, appends observations and records lineage. A failure rolls
back trusted publication; immutable raw/manifest artifacts from an unsuccessful
attempt may remain. Identical selector/range/bytes/contracts are an idempotent
no-op. Any changed bytes, range or contract on an existing selector returns
`VERSION_CONFLICT`, preserving previous values. This conservative first-batch
policy also refuses incremental extension; version promotion/refresh belongs to
later M3-09/M12-12 work, not an implicit upsert.

`materialized_monthly` checks this exact selector/window offline, rehashes and
reparses raw artifacts and checks current silver values/semantics and lineage.
Its missing-value count distinguishes materialization from observation
completeness. It does not mark all history/catalog selectors prepared or resolve
natural-language ambiguity. Runtime availability routing is still future work.

[Ingestion regressions](../tests/unit/test_bddk_monthly_load.py) include the
66-month synthetic range, idempotency/revisions, transaction fault injection and
real lakehouse query/answer gating. [POST regressions](../tests/unit/test_bddk_monthly_transport.py)
use the actual HTTP parser with fake DNS/socket/TLS and the fixed worker protocol.
Full M3-06 remains PARTIAL pending live source/CA/data acceptance.
