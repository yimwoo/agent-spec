# T-017: Review Findings And Status Hygiene

Type: `implementation`
Originating DCR: `DCR-0011-address-review-findings-and-status-hygiene`

## Goal

Address self-review findings before continuing with new supervised-run feature
work.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.

This task improves accuracy and safety around existing behavior. It does not
promote `R-127`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-07` Architectural Principles
- `D-13.3` Supervised Run Orchestrator
- `D-19.6` `agentspec task create`

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-017-review-findings-and-status-hygiene.md`
- `docs/change-requests/DCR-0011-address-review-findings-and-status-hygiene.md`
- `AGENTS.md`
- `README.md`
- `agentspec/cli.py`
- `agentspec/run.py`
- `agentspec/task.py`
- `tests/test_dcr_cli.py`
- `tests/test_task_completion.py`
- `agent/task-ledger.yml`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_dcr_cli.py`
- `tests/test_task_completion.py`

## Acceptance Criteria

- `aspec dcr --help` describes `dcr accept` without a cascade claim.
- `AGENTS.md` accurately reports DCR-0011 and completed T-001..T-017 status.
- README quick start includes task queue, run loop, and task ledger workflow.
- Malformed task ledger prevents `task complete` before run state is written.
- `python -m unittest discover -s tests -v` passes.
