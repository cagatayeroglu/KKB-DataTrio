# Prepared series metadata inspection

The M13-13 prepared-reader slice compares a selected series with an
operator-supplied reviewed catalog **before numerical use**. It is a mandatory
code path within catalog-configured prepared runs, not a planner-callable tool.

`PreparedSeriesInspector(snapshot)` owns a separately validated copy of the
reviewed snapshot. `inspect(connection, series_id)` uses exact identity lookup
and a parameterized, read-only metadata query over `silver_series` and its
`bronze_artifacts` reference. It reads no observations, follows no source URL,
loads no files and has no inference or network fallback. A successful result is
not cached; each new use checks current stored declarations.

## Contract and refusal states

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

## Non-skippable wiring in the prepared mode

The existing [prepared rehearsal](CATALOG.md) constructs and injects
the inspector whenever `--catalog`/`catalog_bytes` is supplied. This applies even
if the model directly selects a series without first using catalog_search.

- `change_detection` (compare/co_movement), `anomaly`, `causality` and
  `table_transform` call the shared `read_series(..., inspector=...)`. It requires
  a consistent receipt before reading observations for that selected series.
  Neither direct invocation nor a model argument can skip this check in a
  configured factory. Unknown/mismatched inputs return a safe failure.
- The restricted `lakehouse` query can return raw inspection rows, but its
  existing direct-silver provenance check must succeed before any financial
  projection. Every selected series then requires a consistent receipt before
  rows become typed values. Failure produces no values, execution proof or
  numerical answer. Unsupported SQL/gold projections already abstain; this
  change grants them no new measurement authority.
- Existing published-table relationship analysis consumes previously verified
  results and does not select a new source series. Full cross-turn catalog
  revision/staleness revalidation remains separate work.

Successful receipts are bound into the producer's local execution-input snapshot
alongside the actual data used. SQL projection records one receipt per selected
identity. Receipts contain hashes/categories, not source descriptions, locators
or observation samples. The ordinary verifier resolves their immutable input
and output bindings. This is traceability, not independent source attestation
or protection from a privileged database/application writer.

No database schema, new tool name or source adapter changes. Factories without
a reviewed inspector retain existing generic input semantics/provenance guards.
This deliberate compatibility path is **not** completion of global M13-13
wiring. A later API must carry the selected preparation/catalog policy into all
its factories; omitting that operator configuration cannot be advertised as this
inspection mode. The lakehouse remains single-owner/not thread-safe.

## Validation and limits

See the [dated evidence](EVALUATION.md#prepared-inspection-delivery-evidence) for exact tests, pool identities, timings and limitations. [ROADMAP](ROADMAP.md#current-project-status) owns delivery status.
