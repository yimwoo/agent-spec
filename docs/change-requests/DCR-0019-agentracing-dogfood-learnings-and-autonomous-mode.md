# DCR-0019: agentracing dogfood learnings and autonomous mode

| Field | Value |
|---|---|
| Status | accepted |
| Classification | needs-adr |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Record dogfood findings from applying AgentSpec to the real `agentracing`
repository, and define the design work needed for a no-human-gate autonomous
execution mode.

The experiment was successful enough to initialize a real TypeScript project,
derive requirements, create T-001, implement a first MVP, verify it, and mark
the task complete. It also exposed several AgentSpec product gaps that should
be fed back into this repository rather than staying in chat context.

## Motivation

AgentSpec is intended to make agent work transparent, repeatable, and safe
across repositories. The `agentracing` dogfood run proved the core workflow can
bootstrap another repo, but also showed that some generated artifacts still
assume AgentSpec's own Python codebase.

The user also requested a recurring fully autonomous contribution loop. That
raises a deliberate design question: AgentSpec needs an explicit autonomous
mode contract rather than relying on ad hoc prompt wording for "YOLO" runs.

## Proposed Change

Add follow-up design and implementation coverage for:

1. Repository-aware target inference.
   - `compile` and `task create` currently infer code targets such as
     `agentspec/cli.py` from words like "CLI".
   - In the TypeScript `agentracing` repo this produced an invalid context-pack
     allowed path, which had to be manually corrected to `src/**`, `tests/**`,
     `fixtures/**`, and package config files.
   - AgentSpec should use repo scan/archetype/language signals to infer target
     paths for non-AgentSpec repositories.

2. Context-pack target validation.
   - Before execution, AgentSpec should warn when allowed paths do not exist
     and do not match plausible repo conventions.
   - For generated packs, the tool should distinguish "source-derived guess"
     from "confirmed write scope".

3. First-class dogfood learning capture.
   - AgentSpec should provide a durable place or command for experiment notes,
     such as `reports/dogfood/` or `aspec dogfood record`.
   - Automation prompts should be able to record self-improvement findings as
     DCRs or dogfood notes in the control-plane repository.

4. CLI availability / alias bootstrap.
   - In this environment `aspec` was not on PATH, so the experiment used
     `python -m agentspec.cli`.
   - AgentSpec should surface a clearer local bootstrap command or generated
     instruction when the CLI entry point is not installed.

5. Local run-state ignore hygiene.
   - `agent/runs/*` is intended to remain local execution detail. A newly
     initialized target repo should receive ignore guidance or a generated
     `.gitignore` fragment for `agent/runs/*` while preserving `.gitkeep`.

6. Task title and filename polish.
   - The generated T-001 title was truncated mid-word (`fixtur`), which is
     harmless but visibly rough.
   - Context-pack generation should truncate titles on word boundaries and keep
     the full source-backed goal in metadata.

7. Autonomous / YOLO mode.
   - Add an explicit mode for no-human-gate execution.
   - The mode should convert human-gate pauses into logged open questions,
     DCRs, or blocked statuses.
   - It should require bounded write scope, verification evidence, no
     destructive git commands, no remote pushes unless explicitly configured,
     and a durable audit trail.
   - Suggested naming: `autonomous` for the product mode; `yolo` can be an
     alias/profile only if the safety contract is still explicit.

## Impact Assessment

Likely affected areas:

- `agentspec/compile.py`: language/archetype-aware code and test target
  inference.
- `agentspec/task.py`: context-pack generation, allowed-path validation, title
  truncation, and task metadata.
- `agentspec/init.py`: generated ignore guidance for local run state.
- `agentspec/run.py` and `agentspec/runner.py`: autonomous execution profile,
  gate handling, and audit evidence.
- `agentspec/cli.py`: new command flags or subcommands for autonomous mode and
  dogfood learning capture.
- `docs/spec/security-and-governance.md`: policy boundaries for no-human-gate
  execution.
- `docs/spec/runtime-architecture.md`: autonomous run lifecycle.
- `agent/context-packs/`: follow-up implementation packs should cite this DCR
  and any new requirements derived from it.

## Disposition

Recommendation: keep this DCR classified as `needs-adr` until the autonomous
execution policy is designed. The target inference and dogfood-log items can be
split into implementation-ready requirements after the ADR defines the
autonomous-mode safety envelope.

Required follow-ups:

- Draft an ADR for AgentSpec autonomous execution profiles.
- Derive accepted requirements for repository-aware target inference and
  context-pack target validation.
- Decide whether dogfood notes should live under `reports/dogfood/`, DCRs, or
  both.
- Create implementation packs after the requirements are accepted.

## Acceptance Criteria

- A future context pack for a TypeScript CLI project does not default to
  `agentspec/*.py` write targets.
- Generated context packs expose whether allowed paths are inferred or
  confirmed.
- New AgentSpec initialization includes guidance to keep `agent/runs/*` local.
- A documented autonomous mode exists with explicit guardrails for no-human-gate
  execution.
- Dogfood findings can be recorded as durable project artifacts without relying
  on chat history.
