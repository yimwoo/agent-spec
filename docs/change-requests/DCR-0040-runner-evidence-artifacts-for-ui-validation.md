# DCR-0040: Runner evidence artifacts for UI validation

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Add an optional structured evidence field to runner results so code agents can
report browser/UI validation artifacts in a durable, reviewable shape.

The first slice should not implement a browser runtime inside AgentSpec. It
should define the control-plane contract that lets Codex, Claude, Playwright,
Chrome DevTools Protocol adapters, or host-provided browser skills report DOM
snapshots, screenshots, navigation traces, console logs, network captures,
videos, traces, and related verification artifacts.

## Motivation

The Harness Engineering review calls out browser observability as a practical
unlock for UI work: code agents can reproduce bugs and validate fixes more
reliably when they can inspect DOM snapshots, screenshots, and navigation
behavior directly.

AgentSpec already records touched paths, test status, executor output, and
research-mode acceptance evidence. Implementation-mode runner results still
lack a general evidence channel for UI artifacts. That leaves browser testing
evidence trapped in free-form prose, making it hard for reviewers and later
agents to know which screenshots, traces, or DOM captures support a completion
claim.

## Proposed Change

- Extend `agentspec.runner_result.v0` with an optional `evidence` object.
- Define `agentspec.runner_evidence.v0` as a generic runner evidence envelope
  with:
  - `artifacts`: paths plus artifact kind and description.
  - `verification_commands`: commands and status values.
  - optional `notes`.
- Include a populated evidence template in runner packages so external runners
  know how to report browser/UI evidence.
- Validate evidence shape before mutating run state.
- Thread valid evidence into the executor event so it is preserved in
  `agent/runs/<run-id>/events.jsonl`.
- Keep evidence non-gating for this slice: `test_status` and the reviewer
  decision still determine completion.

## Impact Assessment

Affected existing requirements:

- `R-007`: the CLI remains the local/CI control plane for runner workflows.
- `R-128`: supervised runs collect per-iteration evidence.
- `R-129`: reviewer feedback consumes structured run evidence.
- `R-170`: task completion is linked to review evidence.

Likely new requirement:

- `R-175`: Runner results support structured evidence artifacts for UI/browser
  validation.

Likely affected artifacts:

- `agentspec/runner.py`
- `agentspec/run.py`
- `tests/test_runner_package.py`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-070-runner-evidence-artifacts-for-ui-validation.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a backward-compatible schema extension for the
existing runner protocol. Future DCRs can add web-archetype detection, generated
browser skills, Playwright/CDP adapters, or stronger reviewer gates that require
specific UI evidence for UI-facing tasks.

## Acceptance Criteria

- Runner packages include an `evidence` result template with UI-relevant
  artifact kinds such as screenshot, DOM snapshot, navigation trace, console
  log, network log, video, and trace.
- `aspec run result` accepts valid `evidence` and records it in the executor
  event.
- Invalid evidence is rejected before run state changes.
- Existing runner results without `evidence` remain valid.
- Tests cover package template shape, valid evidence threading, and invalid
  evidence rejection.
