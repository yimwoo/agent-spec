# T-015: Task Completion Backfill Command

Type: `implementation`
Originating DCR: `DCR-0009-add-task-completion-backfill-command`

## Goal

Add an explicit CLI command for marking an existing context pack complete by
writing supervised-run state, so historical work does not stay at the front of
the task queue.

## Requirements

- `R-003` (P0, accepted) Generate a draft project canvas, spec shards,
  requirements, assumptions, open questions, and task context pack templates.
- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.

This task adds queue/status operations only. It does not promote `R-127`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-07` Architectural Principles
- `D-12.12` Context Pack Builder
- `D-13.3` Supervised Run Orchestrator
- `D-19.6` `agentspec task create`

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-015-task-completion-backfill-command.md`
- `docs/change-requests/DCR-0009-add-task-completion-backfill-command.md`
- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_task_completion.py`
- `AGENTS.md`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_task_completion.py`

## Acceptance Criteria

- `aspec task complete T-013` creates a completed run state for the matching
  context pack.
- `aspec task complete agent/context-packs/<file>.md` also works.
- The command refuses ambiguous or unknown task selectors.
- `aspec task list` reports the completed status after backfill.
- `python -m unittest discover -s tests -v` passes.
