# Evaluation / Hidden-Test Harness

The benchmark is part of the product, not a final-weekend afterthought.

## What to score
At minimum:
- source selection
- tool selection
- plan validity
- date/frequency correctness
- unit correctness
- stock/flow/cumulative correctness
- numeric answer correctness
- citation/evidence completeness
- unsupported-causality abstention
- recovery from tool failure
- latency

## Case families

### Easy
- retrieve one series
- summarize one period
- basic comparison

### Multi-step
- fetch two or more sources
- align frequencies
- derive real/nominal values
- add a new series in a follow-up turn

### Adversarial data semantics
- daily vs monthly mismatch
- stock vs flow
- yearly-reset cumulative data
- million TRY vs TRY
- percent vs basis points
- missing periods
- duplicate dates
- wrong but similarly named series

### External source
- HTML table
- PDF table/text
- XLSX/CSV
- malformed/empty file
- URL redirect
- source with prompt-injection text

### Statistical traps
- spurious correlation
- insufficient observations
- non-stationary series
- lag selection
- causality requested where only association is defensible

### Agent failures
- unknown tool name
- invalid arguments
- tool timeout
- empty result
- contradictory sources
- partial source outage

## Regression tiers

### `eval-smoke`
Small set; use before milestone merges.

### `eval-full`
Larger adversarial set; use before `dev -> main` and final demo.

Do not run the full eval suite after every tiny change.

## Scorecard
Store machine-readable results, e.g.:

```json
{
  "case_id": "freq_014",
  "pass": true,
  "source": 1.0,
  "tool": 1.0,
  "numeric": 1.0,
  "evidence": 1.0,
  "latency_ms": 820
}
```

Track failure categories over time so engineering decisions are evidence-driven.
