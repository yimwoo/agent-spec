# T-020: Harness Step Command

Type: `implementation`
Originating DCR: `DCR-0014-add-harness-step-command`

## Goal

Add a single JSON-oriented harness command that selects or resumes one
supervised run step and returns the next action plus an executor handoff prompt
when continuation is allowed.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds a harness protocol surface. It does not promote `R-127` or
`R-129`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-13.3` Supervised Run Orchestrator
- `D-23.4` Policy Gates
- `D-24` Evaluation and Observability

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-020-harness-step-command.md`
- `docs/change-requests/DCR-0014-add-harness-step-command.md`
- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_step.py`
- `README.md`
- `AGENTS.md`
- `agent/task-ledger.yml`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_supervised_run_step.py`

## Acceptance Criteria

- `aspec run step --json` can select the next ready context pack, start a run,
  and return `next_action=continue_executor` with a handoff prompt.
- `aspec run step --run-id <id> --executor-output ... --json` can resume a run
  and include reviewer verdict plus a next prompt when the decision is
  `auto_continue`.
- Completed runs return `next_action=complete` and no handoff prompt.
- Paused runs return `next_action=await_human` and no handoff prompt.
- `python -m unittest discover -s tests -v` passes.
