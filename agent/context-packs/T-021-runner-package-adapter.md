# T-021: Runner Package Adapter

Type: `implementation`
Originating DCR: `DCR-0015-add-runner-package-adapter`

## Goal

Add a non-executing runner package adapter that turns `aspec run step` output
into a stable envelope external code-agent runners can consume.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds a runner adapter boundary. It does not promote `R-127` or
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

- `agent/context-packs/T-021-runner-package-adapter.md`
- `docs/change-requests/DCR-0015-add-runner-package-adapter.md`
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

- `aspec run package --runner generic --json` starts/selects a ready task and
  returns a schema-tagged runner package.
- A `continue_executor` package includes `should_execute=true`, stdin prompt,
  env hints, and a report-back command template.
- A completed step returns `should_execute=false` and no stdin prompt.
- Unknown runner names are rejected.
- `python -m unittest discover -s tests -v` passes.
