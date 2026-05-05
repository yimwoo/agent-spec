# DCR-0039: Agent knowledge freshness lint

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Add an AgentSpec doctor check that detects stale generated agent instruction
artifacts after requirements, readiness, or status artifacts change.

AgentSpec already emits `AGENTS.md`, `CLAUDE.md`, and Codex/Claude role files,
but a repository can drift after those files are generated. A lightweight
freshness lint should tell humans and code agents when the durable agent-facing
context needs to be regenerated before starting or continuing implementation.

## Motivation

The Harness Engineering review highlighted a useful operating pattern for code
agents: keep repo-local knowledge short, current, and mechanically checked.
AgentSpec already has the source-grounded artifact model, but the current
doctor surface does not warn when generated agent instructions are older than
the traceability and discovery artifacts they summarize.

This creates a preventable failure mode: a code agent can follow an apparently
valid `AGENTS.md` whose requirement count, readiness state, or workflow guidance
is no longer current.

## Proposed Change

- Extend `aspec doctor` with a generated-agent-context freshness check.
- Compare `AGENTS.md`, `CLAUDE.md`, and generated `.codex/agents/*.toml`
  modification times against source-of-truth AgentSpec artifacts such as
  `docs/traceability/requirements.yml`, `docs/discovery/readiness.yml`, and
  `agent/task-ledger.yml` when those files exist.
- Report a warning when any generated agent-context file is missing or older
  than a source artifact it summarizes.
- Include an actionable recovery command, preferably
  `aspec emit --target claude,codex`.
- Keep the check non-blocking for now: stale agent instructions should warn
  through doctor rather than prevent task creation.

## Impact Assessment

Affected existing requirements:

- `R-006`: generated `AGENTS.md`, `CLAUDE.md`, Claude subagents, Codex agents,
  and reusable role definitions remain usable after project state changes.
- `R-007`: the CLI exposes a local and CI-friendly validation surface.
- `R-023`: repositories contain durable context a code agent can trust without
  relying on hidden chat history.
- `R-035`: dogfooding should improve AgentSpec's own repository and agent
  workflow.

Likely new requirement:

- `R-174`: `aspec doctor` reports stale or missing generated agent instruction
  artifacts with a recovery command.

Likely affected artifacts:

- `agentspec/doctor.py`
- `tests/test_cli_workflow.py` or a focused doctor test module
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-069-agent-knowledge-freshness-lint.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a CLI validation enhancement over the existing
generated agent-context surface; it does not change the AgentSpec artifact
model or autonomous execution policy.

## Acceptance Criteria

- `aspec doctor` reports a warning when `AGENTS.md` is missing but AgentSpec
  source-of-truth artifacts exist.
- `aspec doctor` reports a warning when `AGENTS.md`, `CLAUDE.md`, or generated
  `.codex/agents/*.toml` files are older than `requirements.yml`,
  `readiness.yml`, or `agent/task-ledger.yml`.
- The warning includes `aspec emit --target claude,codex` as the recovery
  command.
- Fresh generated agent-context files do not produce the warning.
- Tests cover missing, stale, and fresh cases.
