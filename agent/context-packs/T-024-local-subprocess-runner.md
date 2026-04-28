# T-024: Local Subprocess Runner

Type: `implementation`
Originating DCR: `DCR-0018-add-local-subprocess-runner`

## Goal

Add a local subprocess runner that executes one package/result control-plane
cycle using a real local command.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds a subprocess adapter over the existing runner contract. It does
not promote `R-127` or `R-129`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-13.3` Supervised Run Orchestrator
- `D-21` Claude Code Integration
- `D-22` Codex Integration
- `D-23.4` Policy Gates
- `D-24` Evaluation and Observability

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.
- The main executor uses the active host/default model; AgentSpec configures
  secondary reviewer profiles, not the currently interactive code agent.

## Allowed Paths

- `agent/context-packs/T-024-local-subprocess-runner.md`
- `docs/change-requests/DCR-0018-add-local-subprocess-runner.md`
- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_exec.py`
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

- `tests/test_runner_exec.py`

## Acceptance Criteria

- `aspec run exec ... --json` returns a schema-tagged transcript.
- The transcript includes an initial runner package, subprocess execution
  metadata, a runner result payload, and a final runner package.
- The subprocess receives the package stdin prompt and AgentSpec environment
  variables.
- The happy path completes the task and writes the committed task ledger.
- A subprocess that touches a forbidden path produces a halted final package.
- `python -m unittest discover -s tests -v` passes.
