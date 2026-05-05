# DCR-0051: Refresh generated agent context and configure quality invariants

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

Resolve the next actionable Quality GC warnings by refreshing generated agent
context and adding a repo-local invariant policy file.

This change keeps the cleanup mechanical: it updates generated context so new
agent sessions start from current AgentSpec state, and it configures a small
set of required-path golden principles that `aspec doctor` and `aspec quality`
can evaluate continuously.

## Motivation

The latest Quality GC report still reports stale generated agent context and a
missing `agent/policies/invariants.yml`. These are exactly the "entropy and
garbage collection" issues the Quality GC lane was added to surface.

Blindly running `aspec emit --target claude,codex` would refresh timestamps but
would also overwrite `AGENTS.md` with a thinner generated file than this repo
currently needs. The emitter should preserve the important working rules and
include current status/handoff cues before we refresh the generated artifacts.

## Proposed Change

- Update the `AGENTS.md` emitter so generated agent instructions include:
  - task-pack and allowed-path working rules;
  - the pre-completion code-review gate;
  - current status counts from `aspec status`;
  - the latest handoff/next-action command;
  - the fuller command surface used by this repo.
- Run `aspec emit --target claude,codex` so `AGENTS.md`, `CLAUDE.md`, Claude
  role/skill files, Codex agent TOML files, and repo-local role definitions
  are current.
- Add `agent/policies/invariants.yml` with passing required-path invariants for
  core AgentSpec memory and generated-agent-context artifacts.
- Refresh the Quality GC report after completion so the committed latest report
  reflects the cleanup outcome.

## Impact Assessment

Affected artifacts:

- `agentspec/emit.py`
- `tests/test_cli_workflow.py`
- `AGENTS.md`
- `CLAUDE.md`
- `.claude/agents/*.md`
- `.claude/skills/**/SKILL.md`
- `.codex/agents/*.toml`
- `agent/roles/*.md`
- `agent/policies/invariants.yml`
- `reports/quality/latest.yml`
- `reports/quality/latest.md`
- `docs/traceability/requirements.yml`

New requirement:

- `R-186`: generated agent context stays current and project invariants are
  configured.

## Disposition

Classification: `implement-now`.

No ADR is required. This is a local quality cleanup and emitter hardening slice
over existing generated-artifact and invariant-check surfaces.

## Acceptance Criteria

- `aspec emit --target claude,codex` produces an `AGENTS.md` that includes the
  code-review gate, current status counts, and latest handoff command.
- Generated Claude and Codex role files are refreshed and include the current
  quality-gc role surface.
- `agent/policies/invariants.yml` exists and `aspec doctor` reports
  `project_invariants.status=passed`.
- `aspec quality --json` no longer reports agent-context freshness warnings or
  missing invariant configuration.
- Focused tests and full unittest discovery pass.
