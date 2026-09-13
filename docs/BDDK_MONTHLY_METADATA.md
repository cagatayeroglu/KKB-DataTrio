# M3-05 — Offline monthly housing selector metadata

This bounded implementation defines candidate identity and metadata only under
[DEC-136](DECISIONS.md#dec-136--scoped-official-data-preparation-and-lakehouse-first-demo-runtime).
It performs no network, file, database, observation ingestion or planner/tool
registration. Full BDDK ingestion and broader M3-05 mappings remain unfinished.
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

## Remaining work and validation

M3-06 still needs common bounded POST support, the verified BDDK CA/TLS path,
response retrieval, source snapshots/bronze storage, observation parsing, silver
ingestion, repeatability/idempotency and prepared demo dataset acceptance.
Broader M3-05 bank/currency/table/Weekly/FinTürk metadata mappings are not delivered.
No EVDS, gold, transform, planner/runtime or live acceptance is included.

[Offline tests](../tests/unit/test_bddk_monthly.py) cover identity/dimension
separation, strict review, source evidence, serialization/catalog round-trip,
period/clock independence, metadata failures, synthetic/injection inputs and
unchanged NL ambiguity. The existing cumulative conversion rejects the produced
stock declaration. Exact command results and PR evidence belong to
[ROADMAP](ROADMAP.md#m3).
