# DCR-0065: Add strict lifecycle enforcement

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-11 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-11 |
| Confidence | medium |

## Summary

Add Phase 6 strict lifecycle enforcement from the lifecycle hardening design.
AgentSpec should keep warn mode as the default while adding an opt-in
`lifecycle.enforcement: strict` policy that promotes selected lifecycle drift
from warnings to blocking findings.

This phase continues the operating-contract discipline established in Phase 5:
phase design, executable plan, AgentSpec task pack, and a dedicated worktree
branch before implementation.

## Motivation

Warn-mode lifecycle projection is useful for visibility, but it does not give
teams a repo-level contract for when completion should stop. AgentSpec needs a
configurable strict mode so human and agent delivery can agree that missing
review evidence, missing verification, stale roadmap state, and broken workflow
coverage are not just advisory.

Strict enforcement must remain opt-in. Legacy repos and lightweight workflows
should continue to receive warning diagnostics without blocking completion.

## Proposed Change

- Add lifecycle enforcement defaults to runtime config.
- Make `lifecycle.enforcement: strict` the preferred strict-mode surface while
  preserving existing `finish.enforcement` compatibility.
- In strict mode, lifecycle projection reports blocking findings for workflow,
  review, verification, and roadmap drift.
- In strict mode, finish preflight blocks on strict-blocking lifecycle findings
  with repair guidance.
- Keep stale handoff as warning-only in this phase because finish/write-back can
  refresh handoff as part of normal completion.

## Impact Assessment

New requirement:

- `R-200`: AgentSpec supports opt-in strict lifecycle enforcement.

Likely affected artifacts:

- `agentspec/config.py`
- `agentspec/writeback.py`
- `agentspec/status.py`
- `tests/test_lifecycle_enforcement.py`
- `tests/test_finish_cli.py`
- `tests/test_config_profiles.py`
- `docs/designs/2026-05-11-phase-6-strict-lifecycle-enforcement-design.md`
- `docs/plans/2026-05-11-phase-6-strict-lifecycle-enforcement-workflow.md`
- `docs/change-requests/DCR-0065-add-strict-lifecycle-enforcement.md`
- `docs/traceability/requirements.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an additive, config-gated enforcement mode that
preserves warn-mode behavior and reuses existing lifecycle, review,
verification, finish, and roadmap evidence.

## Acceptance Criteria

- Warn mode remains the default for legacy and newly initialized repos.
- `lifecycle.enforcement: strict` causes lifecycle projection to report
  blocking findings for strict-eligible drift.
- Strict-eligible findings include repair guidance.
- `aspec finish` strict mode reads `lifecycle.enforcement: strict` and blocks
  strict findings before state mutation.
- Existing `finish.enforcement: strict` behavior remains compatible.
- Tests cover warn-mode compatibility, lifecycle strict blockers, finish strict
  blockers, and config defaults.
