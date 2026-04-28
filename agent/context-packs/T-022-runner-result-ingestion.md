# T-022: Runner Result Ingestion

Type: `implementation`
Originating DCR: `DCR-0016-add-runner-result-ingestion`

## Goal

Add a structured report-back command so external runner adapters can submit
executor results as JSON and receive the next runner package.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds result ingestion for the runner package contract. It does not
promote `R-127` or `R-129`.

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

- `agent/context-packs/T-022-runner-result-ingestion.md`
- `docs/change-requests/DCR-0016-add-runner-result-ingestion.md`
- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_package.py`
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

- `tests/test_runner_package.py`

## Acceptance Criteria

- `aspec run result <run-id> --result-json ... --json` accepts a valid runner
  result and returns the next runner package.
- Completed runner results return `should_execute=false`.
- Invalid runner results are rejected before run state changes.
- Runner package `report_back` advertises the result schema and command.
- `python -m unittest discover -s tests -v` passes.
