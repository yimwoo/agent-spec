# T-040: Project Status Surface

Type: `implementation`
Originating DCR: `DCR-0021-add-project-status-surface`

## Goal

Add a read-only project status surface for humans and code agents to see
AgentSpec progress without stitching together multiple commands.

## Requirements

- `R-003` (P0, accepted) Generate a draft project canvas, spec shards,
  requirements, assumptions, open questions, and task context pack templates.
- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-128` (P2, accepted) Supervised run records per-iteration evidence in
  `agent/runs/` JSONL.
- `R-135` (P0, accepted) Autonomous execution profile transforms
  `pause_for_human` into blocked findings.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-07` Architectural Principles
- `D-19` CLI Specification
- `D-23.6` Audit
- `D-24` Evaluation and Observability

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.
- CLI status JSON should be the shared foundation for a future `watch` command
  or local Web UI.

## Allowed Paths

- `agent/context-packs/T-040-project-status-surface.md`
- `docs/change-requests/DCR-0021-add-project-status-surface.md`
- `agentspec/status.py`
- `agentspec/cli.py`
- `tests/test_status_cli.py`
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

- `tests/test_status_cli.py`

## Acceptance Criteria

- `aspec status` prints a concise human-readable status summary.
- `aspec status --json` returns schema-tagged JSON.
- The status includes readiness, requirement counts, DCR counts, task counts,
  run counts, attention-needed runs, recent runs, and next ready task.
- The command is read-only and works when run state or DCR folders are absent.
- `python -m unittest discover -s tests -v` passes.
