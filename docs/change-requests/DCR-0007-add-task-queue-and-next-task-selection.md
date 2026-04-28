# DCR-0007: Add task queue and next task selection

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Add task queue inspection commands so agents can ask AgentSpec which context
packs exist and which pack should be picked next.

This is a lightweight queue over `agent/context-packs/`, not a scheduler. It
parses context pack metadata, overlays run state from `agent/runs/`, and
returns a ready pack for the next supervised run.

## Motivation

The supervised-run MVP can execute a single context pack, but the project goal
is for agents to move through spec-derived work one pack at a time. Without a
queue command, the human or agent must inspect filenames manually.

## Proposed Change

- Add `aspec task list` to print discovered context packs with id, status,
  type, and path.
- Add `aspec task next` to return the next ready context pack.
- Support `--json`, `--type`, `--status`, and `--order oldest|newest` where
  useful.
- Compute task status from local run state when available; otherwise mark the
  pack `ready`.
- Use newest-ready ordering by default for dogfood ergonomics, because this
  repository has historical packs without completed run records.

## Impact Assessment

- Supports `R-003` by making generated task context packs easier to consume.
- Supports `R-007` by expanding local CLI usability.
- Supports `R-127` by feeding supervised runs a context pack selected from a
  bounded queue.
- Code surface: `agentspec/task.py`, `agentspec/cli.py`.
- Test surface: task queue parsing and CLI output.

## Disposition

Classification: `implement-now`.

No ADR is required. This is a tactical CLI ergonomics feature over existing
artifact types.

## Acceptance Criteria

- `aspec task list` prints context packs and statuses.
- `aspec task list --json` returns structured records.
- `aspec task next` returns a ready context pack.
- Completed run state excludes a context pack from `task next`.
- Existing tests pass.
