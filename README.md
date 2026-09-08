# KKB Agentic Analytics

Hackathon repository for an evidence-backed agentic financial-data analyst.

## Product loop

```text
Question
  -> Planner
  -> Source discovery
  -> Data contract / normalization
  -> Deterministic analytics tools
  -> Verification
  -> Answer + table/chart + evidence
```

The system is intentionally model-light: the LLM decides *what to do*; typed deterministic tools perform critical calculations.

## Branches

- `dev`: active integration
- `main`: demo-stable
- short-lived `feature/...` / `codex/...` branches for work

## Fast development commands

```bash
make install-dev
make quick
```

Before a `dev -> main` demo checkpoint:

```bash
make full
```

See:
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/SECURITY.md`
- `docs/EVALUATION.md`
- `docs/DECISIONS.md`
