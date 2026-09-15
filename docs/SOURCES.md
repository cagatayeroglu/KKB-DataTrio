# Sources, acquisition and financial semantics

This is the entry point for supported financial sources, file/URL acquisition,
reviewed identity and source/profile semantics. [ARCHITECTURE](ARCHITECTURE.md)
owns runtime/contracts, [DATABASE](DATABASE.md) storage, [SECURITY](SECURITY.md)
trust controls, [OPERATIONS](OPERATIONS.md) preparation/startup, and
[EVALUATION](EVALUATION.md) measured acceptance. Delivery status remains in ROADMAP.

## BDDK and EVDS evidence register

The five records below are retained as **revision-bound evidence**, not competing
current-status documents. Catalog tests read their current paths, sections and
exact SHA-256 bytes. Moving/deleting/editing them would require changing catalog
artifacts and tests, outside this docs-only task. Their historical discovery
statements remain historical even where adapters now exist.

| Evidence record | Exact detail to consult | Why it remains separate |
| --- | --- | --- |
| [BDDK_SOURCE](BDDK_SOURCE.md) | Monthly/Weekly/FinTürk endpoints, selectors/request shapes, units and cumulative observations | Original BDDK identity/provenance hash; read directly by catalog and adapter tests |
| [BDDK_MONTHLY_METADATA](BDDK_MONTHLY_METADATA.md) | Canonical composite selector IDs, TP/YP/TOTAL, normalization, idempotency/conflict and preparation limits | Prepared v2/v3 review evidence hashes this complete record |
| [EVDS_SOURCE](EVDS_SOURCE.md) | API behavior, datagroups versus series, native frequency, aggregation flags, archives and base variants | Original real-series and provenance inventory hash |
| [EVDS_SERIES_METADATA](EVDS_SERIES_METADATA.md) | Four reviewed series, request/parser quirks, stock/rate/index meaning, base/reference years | Prepared v2/v3 hashes its reviewed metadata and section text |
| [EVDS_COVERAGE](EVDS_COVERAGE.md) | Expanded rate/CPI identities, native frequencies, coverage and preparation evidence | Prepared v3 hashes its expanded-source review |

Enforcement: [original catalog pins](../tests/unit/test_catalog_mappings.py),
[prepared catalog pins](../tests/unit/test_prepared_catalog.py),
[expanded catalog pins](../tests/unit/test_expanded_catalog.py) and
[BDDK source hash](../tests/unit/test_bddk_monthly.py). These are existing tests,
not new checks or permission to change the evidence.

## Source identity and preparation rules

Use reviewed real EVDS series IDs, never a datagroup as an observation series.
For example, CPI groups `bie_tukfiy2025`/`bie_tukfiy2003` differ from reviewed
series `TP.TUKFIY2025.GENEL`/`TP.GENENDEKS.T1`. Keep their base years distinct.
BDDK Monthly selectors identify table, row, group, currency and component;
internal composite hashes are not source-native series codes. TP/YP/TOTAL and
stock versus new disbursement are not interchangeable. [DEC-139](DECISIONS.md#dec-139--kullanılan-konut-kredisi-means-the-outstanding-balance)
records the organizer housing-stock interpretation.

Preserve declared unit/scale, native frequency/weekly anchor, stock/flow/rate/index,
cumulative/reset rules, base year, archive state, source vintage and actual window
coverage. Unknown declarations remain unknown; regular observations or a title do
not establish missing semantics. Reviewed KFE observation-derived metadata is not
a provider-title declaration. See the pinned records for exact IDs and evidence.

Trusted BDDK/EVDS adapters prepare Bronze evidence and normalized Silver before
runtime questions. Identical batches are no-ops; conflicting history is refused.
The pool and credentials are operator-local, absent from Git. Broader coverage,
revisions and retention are separate from a successful fixed-pool build.
[OPERATIONS](OPERATIONS.md#prepare-or-rebuild-the-official-pool) links the exact
preparation commands. Catalog discovery never proves observation availability or
grants a fetch; [CATALOG](CATALOG.md) owns mappings and retrieval mechanics.

## File and URL acquisition

Uploaded CSV/XLSX/PDF and separately authorized URL documents are session inputs,
not automatically permanent official series. `web_url` uses bounded safe fetch
for a supplied/authorized address, then the relevant loader; search results grant
no fetch authority. Static HTML has its own bounded extraction path and is not an
accepted upload extension. JavaScript rendering and image-address extraction are
not implied by PDF/HTML support. [SECURITY](SECURITY.md#sec-url-01--central-safe-fetch--ssrf--redirects)
owns network restrictions; [ARCHITECTURE](ARCHITECTURE.md#6-safe-ingestion-extraction-and-profiling--partial-implementation-confirmed-boundary)
owns parser integration. Admission is only a precondition: it does not infer a
table, delimiter, date locale, numeric meaning or financial semantics.

The reference sections below retain exact admission rules, proposed profile
examples and prepared metadata refusal states. Proposed profile fields/caps and
historical integration statements are not claims of completed profiling.


## File admission

Original bounded admission/profile specification. References to future integration describe this contract’s delivery scope; current completion belongs to ROADMAP.

<a id="file_admission-initial-format-policy"></a>

### Initial format policy

| Extension | Declared MIME | Content checks implemented |
| --- | --- | --- |
| `.csv` | `text/csv`; optional UTF-8 charset | Bounded bytes, UTF-8/UTF-8 BOM decoding, nonempty text, no binary control characters, reject leading markup/PDF signatures. No delimiter, header, numeric/date conversion, row dropping, or locale inference. |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | ZIP local-header signature, readable central directory, required OOXML part names (`[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, at least one worksheet), bounded archive metadata. No extraction or XML/cell interpretation. |
| `.pdf` | `application/pdf` | Bounded bytes and a `%PDF-` header within the first 1,024 bytes (M7-09). Objects, streams, encryption and pages are validated by the bounded [PDF loader](../src/kkb_agent/pdf_loader.py), not here. |

Extension and MIME are case-normalized; missing/generic/mismatched MIME is rejected rather than guessed. CSV MIME parameters other than UTF-8 charset are rejected. `.xls`, `.xlsm`, HTML, and other formats remain unsupported. These are initial local policy choices, not claims about the organizer's hidden input set; add formats only with their own bounded path and tests.

Original filenames must be nonempty basenames of at most 255 UTF-8 bytes with no path separators, colon, control characters, or leading/trailing whitespace. They never select a storage destination. A valid unfamiliar basename is treated exactly like a familiar one. Filename/provenance retention belongs to the caller and must not leak through logs.

CSV has no authoritative magic signature: successful preflight proves admissible text, not syntactically valid CSV. M1-06/M1-13 must reject malformed/header-only tables under an explicit parsing declaration. XLSX envelope checks do not validate XML, CRCs, relationship targets, actual sheet content, or truthful expansion metadata; M1-10 must validate these while reading under enforced output/time bounds. No archive member is extracted, formula/macro executed, or link resolved here.


## Ingestion and profile specification

Original bounded admission/profile specification. References to future integration describe this contract’s delivery scope; current completion belongs to ROADMAP.

<a id="ingestion_profile-synthetic-example-accepted-table-unresolved-semantics"></a>

### Synthetic example: accepted table, unresolved semantics

Illustrative parsing declaration for this example only: UTF-8, comma delimiter, first row is header, empty field is missing, dot decimal separator, no thousands separator, no trimming or imputation. Values in `measure` parse as integers under that declaration; date strings are retained. This does not select a repository-wide CSV parser or default locale.

```csv
as_of,measure,label
2026-01-31,100,A
2026-02-28,,B
2026-03-31,125,C
```

Expected result (the references identify synthetic data only):

```json
{
  "status": "ok",
  "data_ref": "data:synthetic-table-1",
  "source_ref": "source:synthetic-input-1",
  "selection": null,
  "row_count": 3,
  "columns": [
    {
      "id": "c0", "name": "as_of", "type": "string",
      "missing_count": 0, "missing_fraction": 0.0,
      "date_candidates": [{"format": "YYYY-MM-DD", "matched_count": 3}],
      "numeric_candidates": [],
      "candidate_state": {"date": "unique", "numeric": "none"},
      "semantics": {"unit": "unknown", "frequency": "unknown", "time_role": "unknown", "stock_flow": "unknown", "cumulative": "unknown", "reset_rule": "unknown"}
    },
    {
      "id": "c1", "name": "measure", "type": "integer",
      "missing_count": 1, "missing_fraction": 0.3333333333333333,
      "date_candidates": [],
      "numeric_candidates": [{"decimal_separator": ".", "thousands_separator": null, "matched_count": 2}],
      "candidate_state": {"date": "none", "numeric": "unique"},
      "semantics": {"unit": "unknown", "frequency": "unknown", "time_role": "unknown", "stock_flow": "unknown", "cumulative": "unknown", "reset_rule": "unknown"}
    },
    {
      "id": "c2", "name": "label", "type": "string",
      "missing_count": 0, "missing_fraction": 0.0,
      "date_candidates": [], "numeric_candidates": [],
      "candidate_state": {"date": "none", "numeric": "none"},
      "semantics": {"unit": "unknown", "frequency": "unknown", "time_role": "unknown", "stock_flow": "unknown", "cumulative": "unknown", "reset_rule": "unknown"}
    }
  ],
  "unresolved_semantics": [
    {
      "column_ids": ["c0", "c1", "c2"],
      "fields": ["unit", "frequency", "time_role", "stock_flow", "cumulative", "reset_rule"],
      "reason": "Synthetic source supplies no semantic declarations."
    }
  ],
  "diagnostics": [],
  "diagnostics_truncated": false
}
```

The three month-end strings do not establish monthly business frequency or identify stock versus flow. `measure` missingness is 1/3, not 0/3, and the stored rows remain three. No transformation is implied by the numeric candidate.

<a id="ingestion_profile-testable-edge-cases-for-later-implementation"></a>

### Testable edge cases for later implementation

These are synthetic specification examples, not claims of implemented parser behavior. Input lists below are cell values in an already selected column, independent of CSV quoting or XLSX APIs.

| Case | Expected observable result |
| --- | --- |
| Same three-row table with unfamiliar header labels | Same row count, ordered IDs, types, missingness and candidate counts; preserve the new labels. No BDDK/EVDS conditionals. Source/data references identify that input, not a reused different dataset. |
| Duplicate labels `value,value` with row `1,2` | Two columns with different IDs and preserved labels; `DUPLICATE_COLUMN_LABEL`. Do not collapse a dictionary by label. |
| Date strings `01/02/2026`, `02/03/2026` without a date declaration | Preserve strings; `DD/MM/YYYY` and `MM/DD/YYYY` each match 2; date state `ambiguous`, diagnostic `AMBIGUOUS_DATE`. No selected time role or derived date range. |
| Numeric strings `1,234`, `2,345` without a locale declaration | Decimal-comma and comma-grouping candidates each match 2; numeric state `ambiguous`, diagnostic `AMBIGUOUS_NUMBER`. No scaling/conversion. |
| Values `10`, `bad`, empty under the example null policy | Row count 3, missing count 1, fraction 1/3; dot-decimal candidate matches 1 of 2 nonmissing values, state `ambiguous`, diagnostic `NUMERIC_PARSE_FAILURE` with count 1. Preserve the failed value in data; no silent coercion or dropped row. |
| Three empty cells in a column | Row count 3, missing count 3, fraction 1; type `unknown`, no candidates, both states `not_evaluated`; semantic fields remain unknown. |
| Header-only table under an explicit valid declaration | `rejected`, `data_ref: null`, `row_count: null`, `columns: []`; diagnostic `EMPTY_TABLE`, consistent with M1-13. Do not calculate a missingness ratio with a zero denominator. |
| Empty bytes or malformed row width | `rejected`, `data_ref: null`, `row_count: null`, `columns: []`; `EMPTY_INPUT` or `MALFORMED_TABLE`. Header-only is distinguishable from a missing/malformed table. |
| Two sheets, no explicit selection | `needs_input`, no accepted table reference/count/profile; `SELECTION_REQUIRED` with safe sheet identifiers. Selecting one later yields that sheet's source fragment and exact counts. |
| An input/parser/output limit exceeded, or content does not match admitted format | `rejected` with `LIMIT_EXCEEDED` or `FORMAT_MISMATCH`, no usable data reference or partial count. M1-02/M1-14 establish exact boundary values and rejection instrumentation. |
| More than two plausible interpretations, or more than twenty diagnostics | Candidate state remains `ambiguous` and reports truncation; diagnostic count stays <=20 and `diagnostics_truncated` is true when needed. Never call a truncated search unique. |


## Prepared metadata inspection


<a id="series_inspection-contract-and-refusal-states"></a>

### Contract and refusal states

`SeriesInspection` is a closed typed record with catalog snapshot/record hashes,
prepared metadata hash, source artifact identity, declared archive/coverage
facts, unknown fields and mismatched field names. Its states are:

| State | Meaning |
| --- | --- |
| `consistent` | Required reviewed declarations match usable prepared metadata |
| `unknown_identity` | No exact reviewed catalog ID; no database lookup is attempted |
| `not_prepared` | The known identity has no registered prepared series |
| `archived` | Explicitly archived and not enabled by operator policy |
| `unresolved_catalog` | Required meaning is missing in the reviewed catalog |
| `invalid_prepared_metadata` | Stored meaning cannot be reconstructed/resolved, or its artifact identity is invalid/missing |
| `metadata_mismatch` | A supplied reviewed declaration disagrees with the prepared one |

Required checks are unit, scale, native frequency, stock/flow/rate/index kind
and cumulative behavior. A weekly series also needs its anchor and an index
needs its base year. Known aggregation defaults and explicitly forbidden
aggregation methods are checked. Unknown defaults are preserved as optional
unknowns; they are not inferred from the local database or used to grant an
aggregation permission. Existing operation-specific resampling/aggregation
guards still apply.

Unknown archive status never becomes ACTIVE. Source-declared coverage remains
unknown when absent; reading local metadata does not prove requested-window
availability, gap-freedom, freshness or the original source's release schedule.
`allow_archived` is an operator boolean, absent from planner schemas; even when
enabled, required semantics and consistency must pass.

`calculation_authorized` stays **false**, including for a consistent receipt:
metadata consistency is one prerequisite, not analytical evidence or blanket
permission. The producing tool must still check the requested periods, values,
transformation rules and source/execution evidence. Inspection does not prove
that the model chose the right measure for the user's intent.
