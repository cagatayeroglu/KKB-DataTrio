# Bounded catalog-to-analysis continuation

M5-06/M5-13 adds an explicitly enabled Session path:

```text
question -> validated catalog-only plan -> catalog_search
         -> bounded candidate metadata as data
         -> one validated analysis plan or typed clarification
         -> existing tools -> writer/verifier -> accepted workspace publication
```

This connects discovery to planning. It does not make a rank or similarity
score authoritative, add source fetching, or complete mandatory selected-series
inspection. Prepared-series and analytical tools retain their existing semantic,
availability, provenance and numerical checks. Unavailable prepared data still
cannot be silently fetched from the web.

## Activation and compatibility

`Session(..., catalog_continuation=True)` enables the phase contract. The registry
must explicitly contain an operator-configured `catalog_search` to use discovery.
If a plan directly uses known reviewed identities or published tables, it executes
without an extra discovery/model call. The default `False` preserves the prior
one-plan path. `Session.plan()` only plans; `Session.run()` owns execution and the
single continuation. No general autonomous research loop is introduced.

The existing prepared-pool rehearsal can opt in with a reviewed snapshot:

```powershell
python -m kkb_agent.live_check --prepared-root data/processed/lakehouse --catalog docs/catalog/prepared_v2.json --turns 3
```

This command makes live Kloudeks calls and remains subject to the existing run
authorization. It is documentation, not evidence that a live run passed. It reads
and validates the bounded operator-owned catalog file, registers lexical search
and enables continuation. It does not silently enable query embeddings. An
application can separately inject the [configured combined stage](CATALOG_SEARCH.md)
into its registered tool once its real embedding policy is accepted. Invalid
catalog bytes fail before pool copying or a model call; paths/errors are redacted.

The prepared lakehouse must be closed during its existing private-copy step.
Analysis writes stay in that copy; source preparation is unchanged.

## What the harness enforces

- A discovery plan contains only `catalog_search`, at most four independent
  queries. Mixing calculations or dependent queries into it is rejected before
  any step executes and consumes the ordinary plan-repair budget.
- Only successful typed catalog outputs reach the second plan. Metadata is
  revalidated and projected without source locators, observation samples or
  source-evidence file references. Financial declarations, original descriptions,
  review notes, ambiguity, unresolved conditions and stage provenance remain.
- The feedback is a JSON **user/data message**, never a system message. The
  Kloudeks transport's leading-system merge preserves this distinction. JSON
  is a representation, not a proof against injection; executable authority is
  still enforced by the registry, phase validation and analytical tools.
- Feedback is capped at 32 KiB in UTF-8. Oversized metadata is refused rather
  than silently dropping conditions that could determine the series choice.
- The one continuation may use only registered `lakehouse`, `anomaly`,
  `causality`, `change_detection` and `table_transform`, or clarify. It receives
  only those tool descriptions. No second discovery or catalog-derived
  `web_search`/`web_url` action is accepted, even if a web tool exists in the
  broader registry. A separately requested direct web workflow remains separate.
- Continuation IDs must be fresh, and discovery steps cannot be referenced as
  calculation dependencies. The analysis gets a fresh execution context; catalog
  metadata is not an input table or numerical evidence.
- `max_steps` and `max_plan_repairs` are shared across both phases. With defaults,
  at most eight distinct steps and two plan repairs across at most two planning
  phases are accepted. Each provider call retains its own bounded transport/schema
  retries; the plan counts are not a claim of total HTTP-call or wall-time limits.
- The executor binds every returned tool/step identity to the validated step,
  including exhausted retries, preserving the outcome's real trace and evidence.

`Planned.plan` is the final analysis/clarification plan; `Planned.discovery_plan`
keeps the earlier validated plan separately. `attempts` and `rejections` are
aggregate; `discovery_rounds` is zero or one. `ExecutionOutcome.results` preserves
both phases in order. The live-check report includes a separate discovery record.
It does not merge historical discovery steps into an executable clarification plan.

## Clarification and remaining limits

`AnalyticalPlan` has either nonempty steps or `steps=[]` plus one fixed reason:
`ambiguous_series`, `missing_series`, `unresolved_semantics`, `unsupported_request`.
Neither an empty reasonless plan nor a reason plus executable steps is accepted.
A clarification produces a fixed Turkish prompt, no writer/model prose, no
analytical claim and no workspace publication. Candidate details remain available
in the discovery outcome for a future UI; no invented explanation is displayed.

This is an **offline-tested integration**, not live model-selection quality.
The planner still decides whether the question distinguishes candidates; mandatory
selected-series inspection (M13-13) remains unfinished. Total deadline/cancellation,
cross-turn automatic replanning/staleness, wider source availability, real embedding
input policy and held-out retrieval quality are separate work. The mode is not a
proof that every candidate ambiguity is resolved correctly.

The four example searches for total housing credit, housing interest, CPI and KFE
produce 15 returned candidate entries and **25,385 UTF-8 bytes** of projected
feedback with the reviewed v2 snapshot. This is below the local cap; it is not a
measurement of model context/token capacity or live latency.

See [ARCHITECTURE](ARCHITECTURE.md), [SECURITY](SECURITY.md),
[EVALUATION](EVALUATION.md), and the [current ROADMAP](ROADMAP.md#current-project-status).
