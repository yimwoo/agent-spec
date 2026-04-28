# T-023: Local Runner Demo E2E

Type: `implementation`
Originating DCR: `DCR-0017-add-local-runner-demo-e2e`

## Goal

Add a deterministic local runner demo/e2e fixture that proves the package/result
control-plane protocol can run one full task loop.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds an e2e demo fixture. It does not promote `R-127` or `R-129`.

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

- `agent/context-packs/T-023-local-runner-demo-e2e.md`
- `docs/change-requests/DCR-0017-add-local-runner-demo-e2e.md`
- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_demo.py`
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

- `tests/test_runner_demo.py`

## Acceptance Criteria

- `aspec run demo ... --json` returns a schema-tagged transcript.
- The transcript includes an initial runner package, a runner result payload,
  and a final runner package.
- The happy path completes the task and writes the committed task ledger.
- The e2e test verifies the package/result flow without network access or
  external agent binaries.
- `python -m unittest discover -s tests -v` passes.
