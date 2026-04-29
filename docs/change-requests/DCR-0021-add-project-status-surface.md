# DCR-0021: Add project status surface

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-29 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-29 |
| Confidence | medium |

## Summary

Add a compact project status command that shows human operators and code
agents what AgentSpec knows about a repository's current progress: readiness,
requirements, DCRs, task queue, active or blocked runs, recent runs, and the
next suggested action.

## Motivation

AgentSpec can now bootstrap repositories, run bounded agents, emit package
handoffs, record results, and write audit projections. The user experience
still requires stitching together several commands (`task list`, `task next`,
`run inspect`, `readiness`, and manual file reads) just to answer "what is
happening right now?" A status surface is the shared foundation for a future
`watch` command or local Web UI while keeping the CLI as the primary control
plane.

## Proposed Change

- Add `aspec status` for a readable progress summary.
- Add `aspec status --json` with a stable schema for future dashboard/MCP use.
- Summarize readiness, requirements, DCRs, task statuses, run statuses, active
  and attention-needed runs, recent runs, and next ready task.
- Keep the command read-only.

## Impact Assessment

- Supports `R-003` by making task context pack progress visible.
- Supports `R-007` by improving the local CLI.
- Supports `R-128` by surfacing run-state and summary projections.
- Supports `R-135` by making autonomous/research run progress easier to audit.
- Code surface: `agentspec/status.py`, `agentspec/cli.py`.
- Test surface: status CLI tests.

## Disposition

Classification: `implement-now`.

This does not add a Web UI yet. It creates the JSON projection a later Web UI
or `watch` mode can consume.

## Acceptance Criteria

- `aspec status` prints a concise human-readable status summary.
- `aspec status --json` returns schema-tagged JSON.
- The status includes readiness, requirement counts, DCR counts, task counts,
  run counts, attention-needed runs, recent runs, and next ready task.
- The command is read-only and works when run state or DCR folders are absent.
- `python -m unittest discover -s tests -v` passes.
