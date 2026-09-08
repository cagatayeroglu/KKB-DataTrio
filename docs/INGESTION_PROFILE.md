# M1-01 — Ingestion/profile result specification

This is the reviewable specification for [M1-01](ROADMAP.md#m1), with synthetic examples. It defines planned observable results, not implemented CSV/XLSX support or new shared runtime types. [DEC-103/104](DECISIONS.md#dec-103--common-data-contracts-and-explicit-workspace) require generic references and explicit semantics; the analytical engine remains undecided.

## Integration boundary

[ARCHITECTURE, components 5–7](ARCHITECTURE.md#5-source-discovery-and-adapters--confirmed-abstraction) describes `load` returning an opaque data reference and `profile` returning a dictionary. The fields below specify that dictionary's intended meaning without changing those signatures. The Day 0 protocol/models are stash-only in the verified checkout; integrate with the validated M0 contracts and their editor before adding runtime types. This task neither inspects nor recovers the stash.

An adapter profiles one explicitly selected table, regardless of source name or parser engine. A data reference resolves only through the application's authorized data boundary; it is not a user-supplied path, URL, SQL expression, or executable text. The source reference identifies the original source independently of the loaded/derived data reference. Sheet/table selection accompanies the source reference so two sheets cannot accidentally share a profile identity. Ingestion time must not substitute for observation date or source vintage.

## Result fields

Names and types here are a proposed interchange shape for review, not a claim that matching Python classes exist. A JSON example below makes the contract testable without choosing Pandas, Polars, DuckDB, or another dependency.

| Field | Required meaning |
| --- | --- |
| `status` | `ok`, `needs_input`, or `rejected`. `ok` means a bounded table was loaded/profiled; it does not mean financial semantics are resolved or an analytical operation is safe. |
| `data_ref` | Opaque nonempty reference for `ok`; `null` otherwise. Never publish a usable reference to a failed or partly parsed table. |
| `source_ref` | Nonempty source identity assigned at intake, including on rejection; resolves to controlled provenance metadata. Raw bytes, credential-bearing URLs, and absolute local paths do not belong in this field. |
| `selection` | Explicit sheet/table identifier, or `null` when the source unambiguously contains one table. Ambiguous multi-table input returns `needs_input` before choosing one. |
| `row_count` | Exact number of data rows, excluding the header, for `ok`; positive integer. `null` when a table has not been accepted, including empty/header-only input. Never substitute sample size for total row count. |
| `columns` | Ordered column records below, one per accepted column. Empty on `needs_input`/`rejected`; order/identity must survive duplicate or empty labels. |
| `unresolved_semantics` | Structured records of affected column IDs, unresolved fields, and a short reason. An empty list means no unresolved fields in the declared semantic scope, not blanket analytical approval. |
| `diagnostics` | Short codes with safe column/selection references and counts where useful; no copied cell payload or stack trace. Empty when there is nothing to report. |
| `diagnostics_truncated` | Boolean; true if additional diagnostics were omitted because of the reporting cap. Never silently discard the fact that further issues exist. |

For non-`ok` results, counts/column profiles are unavailable (`row_count: null`, `columns: []`), rather than misleading zeros. Include a reason in `diagnostics` and, for `needs_input`, the precise missing selection or parsing declaration. Do not expose unsafe filenames in the diagnostic text.

## Column fields and invariants

| Field | Meaning and invariants |
| --- | --- |
| `id`, `name` | `id` is unique and stable within this data reference (for example `c0` by ordinal); `name` preserves the original label as untrusted metadata. Labels are not unique keys or instructions. Renaming a label does not introduce source-specific code. |
| `type` | Engine-neutral observed representation: `integer`, `number`, `boolean`, `string`, `mixed`, or `unknown`. All-missing columns are `unknown`. A date-looking string can remain `string`; its date interpretation is a separate candidate. Record any accepted parsing declaration in provenance. |
| `missing_count` | Integer from 0 through `row_count`. Missingness follows the declared parser/null policy; absent fields and empty fields are not silently equated with zero. Whitespace and tokens such as `NA` need an explicit policy. |
| `missing_fraction` | `missing_count / row_count`. Store finite numbers only; display rounding must not change the counts. Zero-row input is rejected without column profiles, so no division by zero is attempted. |
| `date_candidates` | List of `{format, matched_count}` interpretations, tested over nonmissing cells. No automatic time-column selection. Invalid or ambiguous values stay visible; a format match does not prove business time semantics. |
| `numeric_candidates` | List of `{decimal_separator, thousands_separator, matched_count}` interpretations. `thousands_separator` may be `null`. Counts describe parseability, not a conversion already performed. |
| `candidate_state` | Separate `date` and `numeric` values: `unique`, `ambiguous`, `none`, or `not_evaluated`. `unique` requires one complete, unambiguous interpretation of all nonmissing cells. Partial matches remain `ambiguous`; an all-missing column is `not_evaluated`, not vacuously `unique`. |
| `semantics` | Explicit values for `unit`, `frequency`, `time_role`, `stock_flow`, `cumulative`, and `reset_rule`; each is `unknown` until declared/confirmed with provenance. Known cumulative values are booleans; `false` is not interchangeable with `unknown`. `not_applicable` needs an explicit justified declaration. |

Every candidate's `matched_count` is between 0 and `row_count - missing_count`; nonmatching nonmissing count is the difference. Candidate lists are empty for `none`/`not_evaluated`. `unique` has exactly one full-coverage candidate. `ambiguous` can mean multiple full-coverage interpretations, incomplete coverage, or an explicitly bounded search that did not establish uniqueness; a diagnostic distinguishes these reasons. A candidate never overwrites original values, drops failed rows, picks a locale, or fills missing values.

Each `unknown` semantic field is covered by `unresolved_semantics`, including after a successful parse. A known semantic declaration must retain an evidence reference in the source's controlled metadata; a dtype, regular-looking sample, confidence score, or header guess alone is insufficient. Date/numeric candidates can be reported while unit, frequency, stock/flow, and cumulative reset remain unknown. Any later transformation must check its own prerequisites under ARCHITECTURE rather than interpreting `status: ok` as permission.

## Bounded profiling and deferred limits

M1-01 specifies result behavior at limits; [M1-02](ROADMAP.md#m1) owns the extension/MIME/content policy, numerical byte/row/column/time caps, and storage paths before loaders are enabled. [SEC-FILE-01/02](SECURITY.md#sec-file-01--file-admission-and-safe-storage) also require expansion/sheet limits and no formula/macro execution or external-link resolution. No loader may advertise support while these guards are undefined or unenforced.

- Profile only the accepted bounded table; counts and candidate coverage refer to every accepted row. If parsing/profiling cannot finish within its configured bounds, return `rejected` with `LIMIT_EXCEEDED`, not an `ok` sample mislabeled as the full table.
- Do not include raw-cell samples in the default profile. Preserve data behind its reference. Profile metadata has one column record per guarded column; label lengths and total metadata size must fit the admission/output limits specified in M1-02.
- Proposed small reporting caps for this profile: at most **2 candidate interpretations per kind per column** and **20 diagnostics**. If more candidate interpretations exist, retain `ambiguous` with `CANDIDATES_TRUNCATED`; if further diagnostics cannot be listed, set `diagnostics_truncated: true`. These are result reporting caps, not parser CPU/input limits or proof of exhaustive interpretation.
- Keep checks deterministic and local. A header/cell containing instructions is source data and cannot trigger a tool, network request, expression evaluation, or filesystem action.

## Synthetic example: accepted table, unresolved semantics

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

## Testable edge cases for later implementation

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

## Review acceptance and handoff

M1-01 review should verify every ROADMAP result field is specified, the example counts/ratios agree with the synthetic input, unknown semantics remain explicit, candidate ambiguity never silently transforms data, and accepted versus rejected/selection-required shapes are distinguishable. Review the reporting caps as proposed metadata limits; numerical file/parser limits remain M1-02 work.

Merge of this specification does not enable loaders or validate stash-only interfaces. M1-02 is the next specification candidate: define practical file admission/resource limits and storage policy before parsing. It is not yet marked READY in ROADMAP; triage its prerequisites and ownership before starting. M1-03 still needs Q-TEAM-02; runtime ingestion additionally needs validated M0 contracts. No framework, database, planner/routing architecture, live source adapter, or private-data retention decision is made here.
