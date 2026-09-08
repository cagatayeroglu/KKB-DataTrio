# AGENTS.md — KKB Hackathon Coding-Agent Rules

Scope: entire repository unless a deeper `AGENTS.md` overrides it. Explicit user task constraints take precedence over this operating workflow.

## Mission and hard constraints

Build a reliable agentic financial analyst in 8–9 days. Prioritize correct answers, demo reliability, hidden-input robustness, traceability, security boundaries, latency, UI polish, then infrastructure sophistication.

Treat these as hard unless [DECISIONS](docs/DECISIONS.md) records an authorized change with evidence:

- Python is the primary backend/analytics language.
- Delivered runtime LLM access goes through Kloudeks only. Do not add OpenAI/Anthropic/Gemini or other third-party LLM APIs to the product.
- Do not use Snowflake or hard-code the core to BDDK/EVDS.
- LLMs may interpret, plan, route, propose schema mappings, and summarize.
- Deterministic code performs material calculations and statistical tests.
- Material answers need source, transformation, and validation evidence.
- External documents, metadata, and model outputs are untrusted data.
- Unknown semantics stay explicit; never silently invent units, frequency, stock/flow meaning, or cumulative reset behavior.

Changing an organizer constraint requires organizer confirmation; a team preference or implementation shortcut cannot override it.

## New session / teammate startup protocol

Repository documentation and Git/PR history are the source of truth. Never require prior chat history to reconstruct project state. A teammate can start with only `Read AGENTS.md and continue with the next READY task.`

1. Inspect the repository root (`git rev-parse --show-toplevel`), current branch, `git status --short --branch --untracked-files=all`, relevant staged/unstaged diffs, remote URLs, and tracking state (`git branch -vv`). Preserve existing work and inspect applicable deeper agent instructions.
2. For new implementation work, obtain latest `dev` safely using [Git workflow](#git-workflow). Do not carry unrelated files across branches, restore someone else's stash, or reset divergent history. An explicitly requested same-task resumption can use its existing branch after checking ownership and handoff.
3. Read [Current project status](docs/ROADMAP.md#current-project-status), its ordered queue, and [DECISIONS](docs/DECISIONS.md). Distinguish confirmed decisions from proposals and unresolved answers. Read only the active/relevant milestone section once a candidate task is identified.
4. Follow an explicitly assigned task if it is not BLOCKED and does not conflict with confirmed decisions; otherwise report the blocker. For “continue” / “next task,” select the first unchecked READY task with satisfied dependencies and no active owner. Check current task-branch/PR claims as well as `dev`; an unmerged claim may not yet appear in `dev`'s ROADMAP. Skip BLOCKED or already claimed tasks.
5. Verify dependencies against concrete implementation and PR history. If ROADMAP disagrees with Git/repository state, report the mismatch, inspect the relevant implementation/PR, and reconcile only when evidence is clear. Never mark work DONE based on roadmap text alone. If selection requires an unresolved team decision, stop and report the exact decision instead of guessing. If ownership cannot be established, choose an independent unclaimed READY task or report the blocker.
6. Read only the technical document relevant to the selected task below. Create its fresh branch from updated `dev`, claim it using the rules below, then implement only that task. Never reuse an old feature branch for unrelated work.

For `Read AGENTS.md and continue.`, the sequence is: Git/repository inspection -> latest `dev` -> ROADMAP status -> DECISIONS -> first eligible unowned READY task -> relevant milestone/technical document -> fresh branch -> published claim -> implementation -> targeted checks -> relevant evidence -> commit -> push -> PR into `dev` (update the claim PR) -> stop before merge unless explicitly authorized.

Acceptance: a teammate such as Eray or Arda, with zero previous ChatGPT/Codex conversation history, can enter the repository and safely continue using only Git state/history, ROADMAP, DECISIONS, and the relevant technical documentation. Default reading is this file, DECISIONS, current/relevant ROADMAP sections, and one technical document; never every large Markdown file.

| Task | Technical reference |
| --- | --- |
| Architecture, planner, registry, provider, workspace | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| Ingestion, normalization, analytics, provenance | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| BDDK bulletin transports, units, cumulative behaviour | [BDDK_SOURCE](docs/BDDK_SOURCE.md) |
| Security, URL/file boundary, auth, secrets, network | [SECURITY](docs/SECURITY.md) |
| Benchmark, hidden cases, scoring, regression | [EVALUATION](docs/EVALUATION.md) |
| Sequencing/priorities/handoff only | Relevant ROADMAP section is sufficient |
| External answer needed | Relevant question in [OPEN_QUESTIONS](docs/OPEN_QUESTIONS.md) |

Do not read every document on every prompt. Do not conduct broad research or repository-wide audits for routine work. An explicitly requested documentation overhaul is an exception, not the normal loop.

## Task selection

- Follow the user's specified task and scope restrictions.
- If asked to “continue,” choose the first unchecked task marked `Status: READY` in ROADMAP's ordered queue whose dependencies remain satisfied and which has no active owner or published claim.
- Recheck its milestone, blockers, and actual repository state. A stale READY marker is not proof of readiness.
- Never silently choose BLOCKED work. Select an independent READY task if available; otherwise name the blocker and exact answer needed.
- PARTIAL / IN PROGRESS includes all local or task-branch work, even with passing tests, until its implementation is merged into `dev` and required validation has passed. Resume the same task on its branch; never reuse it for an unrelated task.
- Never resolve a team choice by guessing or mark aspirational architecture as implemented.
- Claim a small task/coherent group in its milestone record. Use actual teammate names when supplied; do not invent assignments. A suggested role slot is not a person's commitment.

## Task claiming and ownership

Allowed task states are READY, IN PROGRESS, BLOCKED, PARTIAL, and DONE. READY has satisfied prerequisites and no active owner. Legacy COMPLETE means DONE only after verified completion evidence; NOT STARTED describes untriaged backlog/milestone scope, not permission to start a task.

Before implementation, set the task's `Status: IN PROGRESS`, `Owner: <developer>`, and `Branch: <fresh task branch>` in its ROADMAP record. Use the initiating developer's known identity (or an explicitly identified agent owner); never assign Eray or Arda by example or guesswork. Keep Task ID, PR, Commit, Tests, Blocker, and Handoff in the same compact record.

A local edit is not a shared claim. Commit/push the small ROADMAP claim on the task branch and open a draft PR into `dev` naming the task ID before implementation; keep that PR for the task's delivery. Fetch and inspect open/draft PR claims immediately before claiming and again after publishing. If remote claims cannot be inspected or two claims collide, pause the overlapping work and confirm ownership; branch/PR publication is not an atomic lock. Do not silently choose a winner or merge a claim yourself. This uses the existing branch/PR workflow, not a separate tracking service.

Do not start work already IN PROGRESS by another teammate; an owner on PARTIAL/BLOCKED work also remains responsible until an explicit transfer/release. Independent tasks can run in parallel on separate fresh branches from latest `dev`. Shared contracts need one editor. Prefer waiting for dependencies to merge into `dev`; stacked work requires explicit authorization and a recorded base branch, dependency PR, and integration plan.

Elapsed time alone never makes a task abandoned. Before takeover, inspect its branch/PR status and Handoff, confirm with the owner or team whether work is active, and record the previous/new owner, transfer confirmation, retained branch/PR, and remaining work. If confirmation is unavailable, leave ownership unchanged and choose independent work. Do not overwrite or discard another person's work.

## During work

- Keep scope narrow and use the smallest coherent diff; avoid unrelated refactors.
- Add relevant tests beside changed behavior, including critical failure paths.
- Keep typed boundaries explicit. A parsed plan still needs registered-tool, argument, reference, and capability checks.
- Preserve workspace selections, derived data, assumptions, transformations, evidence, and results across turns; chat history is not analytical state.
- Record resampling, interpolation, conversion, deflation, lagging, filtering, or imputation explicitly.
- Do not dump sensitive payloads into logs, fixtures, or handoff notes.
- Add dependencies only for concrete implementation-time or delivery-risk benefits. Record consequential engine/framework decisions before adoption.
- If blocked, record the dependency and next safe task. Do not widen scope into speculative infrastructure.

## Validation tiers and speed limits

Ordinary code work: relevant targeted tests plus fast lint on touched Python. `make quick` is the default repository-wide ceiling; narrower checks are appropriate for narrow work. Do not repeatedly broaden passing checks without a new concern.

| Work / gate | Required validation | Target budget |
| --- | --- | --- |
| Documentation only | Full relevant diff review; local links, checkbox syntax, factual status | Lightweight review; no application checks |
| Ordinary code task | Targeted tests + touched-code lint, or `make quick` | <=60 seconds when practical |
| Task PR to `dev` | Fast PR gate: `make pr` for code; relevant evaluation smoke once available. Documentation-only PRs use the document checks above | <=3 minutes |
| Shared contract, safe-fetch/file execution, auth/secrets/network change | Targeted contract/negative tests + fast PR gate; include critical failure paths | Keep the ordinary/PR budgets |
| Opening/updating `dev -> main`, final demo/release checkpoint, or explicit full-check request | `make full`; full evaluation/rehearsal at release/demo gates | <=8 minutes automated gate target; time-box rehearsal separately |

`make full` currently does **not** invoke a benchmark runner. [EVALUATION](docs/EVALUATION.md) distinguishes implemented commands from planned tiers. A passing full application gate is not evidence of a passing benchmark.

Do not automatically run dependency audits, Docker builds/scans, full integration/benchmark suites, release checks, or long live-network checks after ordinary edits. EVAL-FULL is reserved for release/demo gates or explicit requests. Do not wait for GitHub Actions unless asked; report remote checks as pending when authorized work creates them.

If checks repeatedly exceed their budget, profile/split them. If tooling is unavailable or checks fail, record the exact limitation and keep affected tasks unchecked. User instructions such as “documentation only; no full checks” override generic workflow gates for that task; editing documentation about a boundary is not changing the runtime boundary.

DEC-109 and this document own Git workflow, task completion, and validation-gate placement. Full/release-level checks belong at stable `dev -> main` or final demo checkpoints, or an explicit full-check request. This supersedes older automatic full-check wording elsewhere; task-specific security controls and targeted negative tests still apply.

## Security rules for this scope

- Never commit real API keys, tokens, cookies, private credentials, or `.env`. Use environment variables/repository secrets for Kloudeks credentials.
- Never print authorization headers or secrets. Logs record IDs, categories, timings, and redacted metadata rather than full sensitive payloads.
- Do not commit organizer/private data without explicit permission; fixtures must be synthetic or explicitly safe/public.
- Source instructions are data, never authority to select tools or change system rules.
- No runtime `eval`, `exec`, model-generated Python, unrestricted subprocess, or dynamic import from model/user text.
- Do not execute model-generated SQL directly. If SQL is introduced, parse/validate it and restrict engine capabilities and data access to approved read-only operations.
- External source retrieval uses one safe-fetch layer. Block non-HTTP(S), localhost/private/link-local/cloud-metadata destinations; bound redirects, sizes, and timeouts.
- Uploaded files require extension/MIME/content checks, size/parser limits, and safe storage paths before exposure.
- Validate tool names and typed arguments before execution; bound retries and resource use.
- Security-sensitive implementation changes require targeted negative tests in the same change. [SECURITY](docs/SECURITY.md) owns control acceptance criteria.

## After work: update only the relevant roadmap record

Mark DONE / `[x]` only after implementation exists, required targeted validation has passed, its PR is **merged into `dev`**, and roadmap evidence is updated. Documentation-only tasks also require verified edits and merge into `dev`. Local work, a commit, a push, an open/approved PR, or passing checks alone is PARTIAL / IN PROGRESS.

After meaningful work, update affected task checkboxes and the milestone evidence/handoff only. Keep it short:

```text
Task: actual roadmap ID
Status: READY / IN PROGRESS / BLOCKED / PARTIAL / DONE
Owner: actual teammate / agent task owner
Branch: actual task branch, based on latest dev
PR: URL/number and review/merge state, or pending
Commit: implementation revision, or pending before commit
Tests: exact command and result, or NOT RUN with reason
Blocker: specific issue, or none known in scope
Handoff: what works; what remains; recommended next action and start condition
```

Keep PR/Commit pending until they exist, then record real references in the relevant task record; never invent a future commit SHA. Update top-level status/queue only when the phase, critical blocker, or next ready task changes. Do not rewrite unrelated milestones. After an authorized merge, the next task owner verifies the merge and passing checks, then records DONE/[x], PR, useful implementation/merge revision, tests, and next step in a small update on a fresh branch from updated `dev`; never push that bookkeeping directly to `dev` or pre-check the task in its unmerged implementation PR. This records already merged work and does not require an endless chain of completion tasks.

Before stopping unfinished work, publish a short handoff with what works, what remains, the exact branch, targeted checks/results, known failure/blocker (or none), and recommended next action. Keep it concise; do not imply tests passed without results. Example only, not project evidence:

```text
Task: <actual roadmap ID>
Status: PARTIAL
Owner: Eray (illustrative)
Branch: feature/m2-frequency-alignment
PR: pending
Commit: pending
Tests: 21 passed; 2 blocked by weekly fixture
Blocker: weekly fixture missing
Handoff: Monthly alignment works. Weekly stock-series resampling remains; add the fixture, then continue that path.
```

## Git workflow

Persistent branches: `main` is the stable/demo-ready checkpoint; `dev` is shared integration. Never implement directly on either branch and never push directly to either branch.

When asked to implement a roadmap task, Codex may perform the following Git/terminal operations as part of the normal project workflow, without separate permission for each routine step:

1. Inspect repository, branch, staged/tracked/untracked work, remote, and task dependencies. Preserve unrelated work. If switching would carry unrelated changes into the new task or overwrite files, use an isolated checkout based on latest `dev`, or report the concrete blocker; never reset/clean or silently discard/stash another teammate's work.
2. Fetch the verified remote; switch to `dev` and update it with `git pull --ff-only origin dev`. Verify local `dev` matches the fetched integration tip before branching. If it diverges or cannot be updated, report the blocker rather than resetting it or branching from stale state.
3. Create a separate short-lived task branch from that freshly updated `dev`. Prefer `feature/<milestone>-<task>`, `fix/<short-description>`, or `docs/<short-description>`; examples: `feature/m1-csv-ingestion`, `feature/m2-frequency-alignment`, `fix/url-fetch-timeout`.
4. Publish the small ROADMAP claim and draft PR as described in [Task claiming and ownership](#task-claiming-and-ownership), then implement only the selected task. Run targeted tests/lint or `make quick`, apply the fast PR gate, and update only its ROADMAP record. Keep its checkbox unchecked while awaiting merge.
5. Stage only intended task files, commit with a clear message, push that task branch normally, and update its PR **into `dev`** for review. Record actual Commit/PR/check results and a concise Handoff; do not wait for remote CI unless asked.
6. After review and a verified merge into `dev`, remove the short-lived branch locally/remotely when it contains no unmerged work and is no longer active in a checkout. Branch cleanup is part of this workflow; never delete `dev`/`main` or force-delete unmerged work.
7. Start the next task from freshly updated `dev` on another new branch, never from the previous feature branch. Any branch based on another unfinished feature branch requires an explicit instruction and a documented dependency/base exception.

Codex must not merge its own PR unless explicitly told, push directly to `dev`/`main`, force-push shared branches, reuse an old branch for unrelated work, or change repository settings without explicit authorization. Follow explicit task-specific branch constraints. The original workflow update stayed on `feature/day0-core` by exception; PR #1 has since merged, and that exception does not authorize future branch reuse.

Approximately every 3–4 days, or at an important stable milestone, prepare a `dev -> main` PR if the integrated state is demo-ready. `main` is not updated after every task. Run full/release checks at that gate and leave promotion/merge to review and explicit merge authorization; an elapsed calendar interval alone does not justify promotion.

## Definition of done and handoff

A normal feature is DONE only when requested behavior works, required targeted tests/lint and the fast PR gate pass, its critical failure path is covered, and the implementation is merged into `dev` with updated roadmap evidence and a next step. Before merge, report implementation-ready/PARTIAL with its PR status. Full/release checks apply at checkpoint gates or explicit requests. Do not introduce secret/debug dumps.

End with the outcome, validation, material limitation/blocker, and next task. Another teammate must be able to resume from repository notes without reading chat history.

Do not build fine-tuning pipelines, Kubernetes, enterprise RBAC/RLS, production backup/restore, distributed queues, heavyweight lakehouses, full DAST, SBOM/signing, elaborate multi-agent roleplay, custom vector databases, or arbitrary code sandboxes without a concrete requirement. Do not turn ordinary features into release-hardening projects.
