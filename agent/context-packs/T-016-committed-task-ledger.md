# T-016: Committed Task Ledger

Type: `implementation`
Originating DCR: `DCR-0010-add-committed-task-ledger`

## Goal

Add a committed task ledger so shared queue status survives outside a single
developer's ignored `agent/runs/` directory.

## Requirements

- `R-003` (P0, accepted) Generate a draft project canvas, spec shards,
  requirements, assumptions, open questions, and task context pack templates.
- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.

This task adds a committed status projection only. It does not promote `R-127`.

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

- `agent/context-packs/T-016-committed-task-ledger.md`
- `docs/change-requests/DCR-0010-add-committed-task-ledger.md`
- `agent/task-ledger.yml`
- `agentspec/task.py`
- `agentspec/cli.py`
- `agentspec/run.py`
- `tests/test_task_ledger.py`
- `tests/test_task_completion.py`
- `AGENTS.md`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_task_ledger.py`
- `tests/test_task_completion.py`

## Acceptance Criteria

- `aspec task list` uses `agent/task-ledger.yml` to report completed tasks
  without local run state.
- Newer local run state overrides older ledger entries.
- `aspec task complete T-013` updates the ledger.
- The ledger can be populated for the current repository's completed packs.
- `python -m unittest discover -s tests -v` passes.
