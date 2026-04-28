# T-013: Add Task Queue And Next Task Selection

Type: `implementation`
Originating DCR: `DCR-0007-add-task-queue-and-next-task-selection`

## Goal

Add CLI support for listing task context packs and selecting the next ready
pack for supervised execution.

## Requirements

- `R-003` (P0, accepted) Generate a draft project canvas, spec shards,
  requirements, assumptions, open questions, and task context pack templates.
- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.

This task only selects context packs. It does not promote `R-127`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-07` Architectural Principles
- `D-12.12` Context Pack Builder
- `D-19.6` `agentspec task create`

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON to
  avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-013-add-task-queue-and-next-task-selection.md`
- `docs/change-requests/DCR-0007-add-task-queue-and-next-task-selection.md`
- `agentspec/task.py`
- `agentspec/cli.py`
- `tests/test_task_queue.py`

## Forbidden Paths

- Anything outside the allowed paths.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Raw run logs unrelated to tests.

## Tests To Add Or Update

- `tests/test_task_queue.py`

## Acceptance Criteria

- `aspec task list` prints context packs and statuses.
- `aspec task list --json` returns structured records.
- `aspec task next` returns the newest ready pack by default.
- `aspec task next --order oldest` returns the oldest ready pack.
- Completed run state excludes a pack from `task next`.
- `python -m unittest discover -s tests -v` passes.
