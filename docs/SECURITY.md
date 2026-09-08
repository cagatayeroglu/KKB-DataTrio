# Security — Hackathon Baseline

This document is deliberately narrower than a production enterprise security program.
It protects the boundaries that are likely to matter in this challenge without slowing every coding iteration.

## 1. Data and secrets
- Never commit real API keys/tokens/cookies/passwords.
- `.env` is ignored; `.env.example` contains names only.
- Kloudeks credentials are injected at runtime.
- Logs must redact authorization headers and credential-like values.
- Organizer-provided/private datasets are not committed unless explicitly allowed.
- GitHub CI uses synthetic/public-safe fixtures only.

## 2. LLM boundary
Delivered runtime uses the organizer-approved Kloudeks path only unless organizers explicitly change the rule.

The LLM:
- may plan/route/summarize;
- may not be trusted as the source of numeric calculations;
- may not directly execute Python/shell/SQL;
- may not change system instructions based on document content.

## 3. Prompt injection
All external content is untrusted:
- web pages
- PDFs
- spreadsheets
- images/OCR
- metadata/descriptions
- tool outputs

Content such as "ignore your instructions" is extracted data, not executable instruction.

Tool selection and arguments come from system-owned schemas and validation.

## 4. Safe URL fetching / SSRF
All network retrieval must pass one `safe_fetch` boundary.

Block:
- non-HTTP(S)
- localhost
- loopback
- private RFC1918 ranges
- link-local
- cloud metadata IPs/hostnames
- credential-bearing URLs
- unsafe redirect chains

Enforce:
- DNS/IP re-check where practical
- connect/read timeout
- redirect limit
- response-size limit
- content-type allowlist/routing
- no automatic execution of downloaded content

Add targeted negative tests when this layer is implemented.

## 5. File ingestion
Before parsing:
- explicit size limit
- extension + content/MIME sanity check
- no path traversal
- no archive extraction unless required and bounded
- parser timeout/resource limits where practical

Never execute macros, embedded scripts, binaries, or formulas as code.

## 6. SQL / analytical execution
Prefer DuckDB/Polars/Pandas over arbitrary model-generated code.

If SQL is used:
- execute against controlled analytical data only
- read-only statements only
- parse/validate before execution
- reject DDL/DML/ATTACH/extension loading/filesystem/network capabilities not required by the product
- bind values rather than string-concatenating untrusted values

## 7. Python/shell execution
No:
- `eval`
- `exec`
- arbitrary `subprocess(..., shell=True)`
- dynamic import from model/user text
- model-generated Python execution inside the app

If arbitrary code execution ever becomes a requirement, stop and design a real sandbox first.

## 8. Tool validation
Every tool call:
1. validate tool name against registry;
2. validate args against typed schema;
3. authorize capability;
4. apply resource limits;
5. execute;
6. record safe metadata/evidence;
7. return structured status.

Bound retries to avoid loops/cost explosions.

## 9. CI strategy
Security checks are tiered for speed.

### Every local task
Targeted tests + lint only (`make quick`).

### Feature -> dev PR
Fast static checks:
- lint
- unit tests
- Bandit
- secret scan

### dev -> main / manual full gate
Add:
- mypy
- full pytest
- dependency audit
- benchmark smoke/full as available

Heavy image scanning/DAST/SBOM are optional hardening tasks only if the final deployment architecture actually makes them useful and time permits.

## 10. Release/demo checklist
Before final demo:
- rotate any key ever pasted into chat/log/commit
- verify git history contains no real secret
- full tests green
- dependency audit reviewed
- prompt-injection negative test
- SSRF negative tests if URL fetching exists
- malicious/oversized file tests if file upload exists
- SQL write/unsafe statement rejection test
- no third-party LLM runtime dependency
- logs do not expose secrets/raw sensitive payloads
