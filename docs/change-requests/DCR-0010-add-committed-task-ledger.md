# DCR-0010: Add committed task ledger

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

Add a committed task ledger at `agent/task-ledger.yml` so shared queue status
does not depend on ignored local supervised-run state. The ledger records the
latest known status for each context pack and is used by `aspec task list` /
`aspec task next` when no newer local run state is available.

Local `agent/runs/*` remains the detailed execution log. The ledger is the
small, reviewable manifest that can travel with the repository.

## Motivation

`aspec task complete` can backfill historical tasks, but its run artifacts are
ignored by git. That is appropriate for bulky runtime logs, but it means another
machine still sees old context packs as ready. A committed ledger gives code
agents a shared notion of progress while keeping run logs local by default.

## Proposed Change

- Introduce `agent/task-ledger.yml` as JSON-compatible YAML.
- Add ledger read/write helpers in the task queue module.
- Update task status overlay so local run state wins when newer; otherwise the
  committed ledger supplies status.
- Update `aspec task complete` to write both local completion run state and the
  committed ledger.
- Keep requirement acceptance separate from ledger completion.

## Impact Assessment

- Supports `R-003` by making context-pack progress portable.
- Supports `R-007` by improving the local CLI workflow.
- Supports `R-127` by retaining supervised-run state as execution evidence
  while adding a compact shared status projection.
- Code surface: `agentspec/task.py`, `agentspec/cli.py`, `agentspec/run.py`.
- Data surface: `agent/task-ledger.yml`.
- Test surface: task ledger parsing, precedence, and CLI completion updates.

## Disposition

Classification: `implement-now`.

No ADR is required because this is a local manifest over existing task/run
state rather than a new orchestration protocol.

## Acceptance Criteria

- `aspec task list` uses `agent/task-ledger.yml` to report completed tasks
  without local run state.
- Newer local run state overrides older ledger entries.
- `aspec task complete T-013` updates the ledger.
- The ledger can be populated for the current repository's completed packs.
- `python -m unittest discover -s tests -v` passes.
