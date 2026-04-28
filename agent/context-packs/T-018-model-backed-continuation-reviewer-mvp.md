# T-018: Model-Backed Continuation Reviewer MVP

Type: `implementation`
Originating DCR: `DCR-0012-add-model-backed-continuation-reviewer-mvp`

## Goal

Add an optional model-backed reviewer path so a configured continuation
reviewer can answer low-risk executor pauses with structured
`continue | pause | halt | complete` decisions.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task adds the model-backed verdict boundary only. It does not promote
`R-127` or `R-129`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-07` Architectural Principles
- `D-13.3` Supervised Run Orchestrator
- `D-23.4` Policy Gates
- `D-24` Evaluation and Observability

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-018-model-backed-continuation-reviewer-mvp.md`
- `docs/change-requests/DCR-0012-add-model-backed-continuation-reviewer-mvp.md`
- `agentspec/model_review.py`
- `agentspec/review.py`
- `agentspec/run.py`
- `agentspec/cli.py`
- `agentspec/config.py`
- `tests/test_model_review.py`
- `AGENTS.md`
- `agent/task-ledger.yml`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_model_review.py`

## Acceptance Criteria

- `aspec run resume --reviewer model` can use a configured reviewer profile to
  return `auto_continue`.
- Policy halt cannot be overridden by a model verdict.
- Invalid or unavailable model output falls back to deterministic pause.
- Model-backed completion cannot bypass failed or missing verification.
- `python -m unittest discover -s tests -v` passes.
