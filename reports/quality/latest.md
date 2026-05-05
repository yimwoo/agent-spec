# Quality GC Report

- Grade: B
- Generated: 2026-05-05T23:05:05Z
- Summary: 0 error(s), 5 warning(s), 2 info finding(s).

## Cadence

- Completed tasks: 77
- Task interval: 3
- Was due: False
- Next recommended completed-task count: 80

## Findings

- [warning] Generated agent context is stale or missing: `AGENTS.md` AGENTS.md is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `CLAUDE.md` CLAUDE.md is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/brownfield-mapper.toml` .codex/agents/brownfield-mapper.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/security-reviewer.toml` .codex/agents/security-reviewer.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/spec-reviewer.toml` .codex/agents/spec-reviewer.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [info] Project golden principles are not configured: `agent/policies/invariants.yml` No agent/policies/invariants.yml file is configured for mechanical project rules. Recovery: `Create agent/policies/invariants.yml with project-specific required_path or forbidden_path rules.`
- [info] Open questions remain: `docs/discovery/open-questions.yml` 13 open question(s) remain in discovery state.

## Handoff

- Present: True
- Last completed task: T-079
- Next action: idle
- Next command: `aspec status --json`
