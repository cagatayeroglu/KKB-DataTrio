# Architecture

## Goal
A small-model-friendly analytical harness that remains reliable with unseen questions and new-but-supported data sources.

## Reference flow

```text
User
  |
  v
Intent / Planner
  |
  v
Typed Analytical Plan
  |
  +--> Source Discovery
  |      +--> BDDK
  |      +--> EVDS
  |      +--> CSV/XLSX
  |      +--> PDF/HTML/URL
  |      +--> future adapters
  |
  v
Analysis Workspace
  |
  +--> Normalize / align
  +--> Derive / deflate
  +--> Change / anomaly
  +--> Correlation / lag
  +--> Causality tool
  |
  v
Verifier
  |
  v
Answer + Evidence Ledger + Visualization
```

## Core interfaces

### LLMProvider
Keep model-specific Kloudeks details behind one interface.

Responsibilities:
- structured generation
- planner generation
- concise synthesis

The rest of the codebase must not depend on a specific Kloudeks model name.

### SourceAdapter
Common conceptual operations:
- `discover(query)`
- `inspect(source)`
- `load(selection)`
- `profile(data)`
- `provenance()`

Adapters may implement only the capabilities they support.

### DataContract
For every analytical series/table where applicable:

- source id
- human title
- unit
- frequency
- date/time column semantics
- stock vs flow
- cumulative flag / reset behavior
- aggregation semantics
- source period
- retrieval timestamp
- transformation history
- confidence / unresolved semantic warnings

Unknown fields should remain unknown, not be hallucinated.

### AnalyticalPlan
Planner output must be structured and validated.

Plan steps should reference registered tools, never arbitrary code.

Suggested fields:
- goal
- required inputs
- tool
- validated arguments
- dependencies
- expected output type
- verification requirement

### AnalysisWorkspace
Holds state across turns:
- selected sources
- normalized frames/series
- derived columns
- transformations
- evidence records
- open assumptions
- results

### EvidenceLedger
A material claim should be able to point to:
- input source(s)
- exact transformation/tool run
- relevant period/columns
- validation result
- limitations

## Tool philosophy
Prefer small deterministic tools over a giant "analysis" tool.

Initial tool families:
- source search/discovery
- table/series profiling
- frequency alignment
- unit conversion
- cumulative-to-flow conversion
- inflation adjustment
- change-point / anomaly
- correlation / lag analysis
- causality test
- chart/table generation
- verifier

## Routing
Do not fine-tune a router before a baseline exists.

Use:
1. deterministic routing when obvious (e.g. file type);
2. schema/metadata rules;
3. LLM semantic routing where necessary;
4. fallback/repair when validation fails.

## Failure handling
Each tool returns structured:
- status
- data/result reference
- evidence
- warnings
- recoverability
- error category

The planner may repair only within bounded retry limits.

## Out of scope initially
- distributed agents
- arbitrary Python execution
- heavyweight warehouse infrastructure
- per-tool custom models
- complex vector infrastructure before a benchmark proves need
