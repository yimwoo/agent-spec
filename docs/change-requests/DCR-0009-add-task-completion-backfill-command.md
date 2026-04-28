# DCR-0009: Add task completion backfill command

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

Add a task completion command that writes a completed supervised-run state for
an existing context pack. This lets teams backfill historical packs that were
implemented before `aspec run loop` existed, so the queue can move forward
instead of repeatedly selecting old work.

The command is explicit and local: it records completion evidence in
`agent/runs/` but does not mutate requirements, canonical source snapshots, or
context pack content.

## Motivation

`aspec task next` uses local run state to decide which packs are ready. That
works for new loop-driven work, but this repository already has completed
packs from earlier dogfood iterations without run state. A backfill command is
needed to keep queue selection useful during adoption.

## Proposed Change

- Add `aspec task complete <task-id-or-context-pack>`.
- Resolve either a task id like `T-013` or an explicit context pack path.
- Write a completed run state under `agent/runs/`.
- Record reason and verification status in the event log.
- Refuse to overwrite an existing run id.
- Keep requirement acceptance separate from task completion.

## Impact Assessment

- Supports `R-003` by making generated context packs manageable as a queue.
- Supports `R-007` by extending the local CLI control surface.
- Supports `R-127` by making supervised-run state the task status source of
  truth, including for historical backfill.
- Code surface: `agentspec/run.py`, `agentspec/cli.py`.
- Test surface: task completion CLI and queue status overlay.

## Disposition

Classification: `implement-now`.

No ADR is required because this is a local operational command over existing
state files, not a new protocol boundary.

## Acceptance Criteria

- `aspec task complete T-013` creates a completed run state for the matching
  context pack.
- `aspec task complete agent/context-packs/<file>.md` also works.
- The command refuses ambiguous or unknown task selectors.
- `aspec task list` reports the completed status after backfill.
- Existing tests pass.
