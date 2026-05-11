# Quality GC Report

- Grade: B
- Generated: 2026-05-11T05:26:53Z
- Summary: 0 error(s), 8 warning(s), 1 info finding(s).

## Cadence

- Completed tasks: 97
- Task interval: 3
- Was due: True
- Next recommended completed-task count: 100

## Findings

- [warning] Generated agent context is stale or missing: `AGENTS.md` AGENTS.md is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `CLAUDE.md` CLAUDE.md is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/app-evaluator.toml` .codex/agents/app-evaluator.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/app-planner.toml` .codex/agents/app-planner.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/brownfield-mapper.toml` .codex/agents/brownfield-mapper.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/quality-gc-reviewer.toml` .codex/agents/quality-gc-reviewer.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/security-reviewer.toml` .codex/agents/security-reviewer.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [warning] Generated agent context is stale or missing: `.codex/agents/spec-reviewer.toml` .codex/agents/spec-reviewer.toml is older than agent/task-ledger.yml. Recovery: `aspec emit --target claude,codex`
- [info] Open questions remain: `docs/discovery/open-questions.yml` 15 open question(s) remain in discovery state.

## Handoff

- Present: True
- Last completed task: T-099
- Next action: idle
- Next command: `aspec status --json`
