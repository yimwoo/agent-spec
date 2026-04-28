# T-014: Supervised Run Loop MVP

Type: `implementation`
Originating DCR: `DCR-0008-add-supervised-run-loop-mvp`

## Goal

Add a local supervised-run loop command that selects the next ready context
pack, starts or resumes run state, and lets the continuation reviewer answer
low-risk pauses without expanding scope.

## Requirements

- `R-003` (P0, accepted) Generate a draft project canvas, spec shards,
  requirements, assumptions, open questions, and task context pack templates.
- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer agent can approve,
  continue, pause, or halt low-risk executor pauses.

This task extends the local CLI MVP only. It does not promote `R-127` or
`R-129`.

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

- `agent/context-packs/T-014-supervised-run-loop-mvp.md`
- `docs/change-requests/DCR-0008-add-supervised-run-loop-mvp.md`
- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_loop.py`
- `AGENTS.md`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_supervised_run_loop.py`

## Acceptance Criteria

- `aspec run loop` selects the newest ready context pack when none is supplied.
- `aspec run loop <context-pack>` starts a local run for that pack.
- `aspec run loop --run-id <id> --executor-output <text>` resumes an existing
  run and records a reviewer verdict.
- Dogfood continuation prompts can return `auto_continue` through the loop.
- JSON output includes selected task, state, and reviewer verdict when present.
- `python -m unittest discover -s tests -v` passes.
