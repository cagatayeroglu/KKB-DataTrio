# Decisions

Only record confirmed decisions and intentional architecture choices here.
Do not convert guesses into facts.

## Confirmed / team-provided constraints
- Primary implementation language: Python.
- Different data sources may be provided during the challenge/demo.
- Do not use Snowflake.
- Delivered system must not rely on third-party LLM APIs.
- Model/reranker access is expected through KKB/Kloudeks using open-weight models exposed by that platform.
- High-parameter models should not be assumed.
- Fine-tuning is not a required expectation.
- Code development/progression may be reviewed, so commit/PR history should remain understandable.

## Architecture decisions
- Keep Kloudeks behind an `LLMProvider` abstraction.
- Prefer typed analytical plans and tool schemas.
- Critical calculations are deterministic.
- Maintain explicit multi-turn analysis state.
- Use a common source-adapter/data-contract layer so the core is not BDDK/EVDS-specific.
- Build a benchmark harness early.
- Default to simple orchestration; add framework complexity only when measured need appears.

## Not yet decided
- exact Kloudeks endpoint/auth format
- available model names/sizes
- tool-calling / JSON-schema capabilities
- context windows / rate limits
- reranker/embedding availability
- whether coding assistants such as Codex/Claude Code are permitted purely as development tools
- exact external network restrictions during demo
- machine/GPU resources provided by organizers
