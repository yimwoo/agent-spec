# DCR-0062: Add shared write-back module

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-10 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-10 |
| Confidence | medium |

## Summary

Add the Phase 2 shared write-back module from the lifecycle hardening design.
The module should consolidate task ledger, handoff, roadmap, review-link, and
verification write-back helpers while preserving the existing durable schemas.

This slice prepares AgentSpec for a later `aspec finish` orchestrator without
adding that public command yet.

## Motivation

Phase 1 exposed lifecycle projection and write-back readiness, and the native
workflow slice added first-class workflow creation. Completion behavior is still
spread across `agentspec.run`, `agentspec.task`, `agentspec.handoff`, and
`agentspec.roadmap`, making it harder to verify write-back completeness or reuse
safe completion behavior from future orchestration commands.

## Proposed Change

- Add shared write-back helpers in `agentspec.writeback` that wrap existing
  ledger, handoff, roadmap, review-link, and verification formats.
- Keep ledger-first completion safety: do not produce terminal completion state
  if required ledger or handoff writes fail.
- Expose a reusable completion projection that can explain task, review,
  verification, handoff, and roadmap readiness for a selected task.
- Refactor completion code to call the shared helpers instead of duplicating
  write-back serialization.
- Preserve current `aspec task complete` and supervised run completion behavior.
- Keep `aspec finish` deferred to a later DCR-backed slice.

## Impact Assessment

New requirement:

- `R-197`: AgentSpec centralizes completion write-back helpers.

Likely affected artifacts:

- `agentspec/writeback.py`
- `agentspec/run.py`
- `agentspec/task.py`
- `agentspec/handoff.py`
- `agentspec/roadmap.py`
- `agentspec/status.py`
- `tests/test_writeback.py`
- `tests/test_task_completion.py`
- `tests/test_status_cli.py`
- `docs/ROADMAP.md`
- `reports/doctor/repo-scan.yml`
- `reports/quality/latest.md`
- `reports/quality/latest.yml`
- `docs/change-requests/DCR-0062-add-shared-write-back-module.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an internal consolidation over existing repo-local
schemas and should not introduce a second lifecycle state machine. The public
`aspec finish` command remains a future Phase 3 task.

## Acceptance Criteria

- `agentspec.writeback` exposes reusable helpers for completion projection,
  task ledger update, handoff update, roadmap update, and write-back
  verification.
- Existing task completion and supervised run completion behavior remain
  backward compatible.
- Code review linkage and verification status are threaded through the shared
  helper path.
- Write-back verification can report missing ledger, handoff, review, or stale
  roadmap evidence for a selected task.
- Failure ordering does not mark work complete before required ledger and
  handoff writes succeed.
- Tests cover helper behavior, completion compatibility, review/verification
  linkage, and write-back readiness diagnostics.
