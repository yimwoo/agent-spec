# DCR-0063: Add finish orchestrator

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

Add the Phase 3 finish orchestrator from the lifecycle hardening design. The
new `aspec finish` command should make task completion a single write-back
operation over existing task ledger, handoff, roadmap, review, and verification
artifacts.

This slice adds orchestration and diagnostics only. It should reuse existing
completion and write-back helpers rather than inventing a second finish state,
review format, or task ledger schema.

## Motivation

Phase 2 introduced shared write-back helpers, but users still need to know which
completion command to run and how to diagnose missing ledger, handoff, review,
verification, or roadmap evidence. A first-class finish command gives agents and
humans one lifecycle operation for "is this task finishable?" and "mark this
task complete safely."

## Proposed Change

- Add `aspec finish <task-selector>` and `aspec finish --dry-run`.
- Support `aspec finish --current` when the current project handoff identifies
  an active or last task that can be selected safely.
- In dry-run mode, return warning-mode diagnostics with repair commands without
  mutating completion state.
- In normal mode, orchestrate existing task completion/write-back APIs so ledger,
  handoff, review linkage, verification, and roadmap behavior stays compatible.
- Add config-backed strict mode so finish readiness findings can fail completion
  only when explicitly enabled.
- Keep existing `aspec task complete` behavior available and backward
  compatible.

## Impact Assessment

New requirement:

- `R-198`: AgentSpec exposes a finish orchestrator over completion write-back.

Likely affected artifacts:

- `agentspec/cli.py`
- `agentspec/run.py`
- `agentspec/writeback.py`
- `agentspec/task.py`
- `agentspec/status.py`
- `tests/test_finish_cli.py`
- `tests/test_task_completion.py`
- `tests/test_writeback.py`
- `docs/change-requests/DCR-0063-add-finish-orchestrator.md`
- `docs/traceability/requirements.yml`
- `docs/ROADMAP.md`
- `reports/doctor/repo-scan.yml`
- `reports/quality/latest.md`
- `reports/quality/latest.yml`

## Disposition

Classification: `implement-now`.

No ADR is required. The command is an orchestrator over existing AgentSpec
completion state and should remain migration-safe. Future slices can extend
finish to deeper session/workflow policy checks after the first warning and
strict-mode contract is stable.

## Acceptance Criteria

- `aspec finish <task-selector>` can complete a task through existing
  write-back and task completion formats.
- `aspec finish --dry-run <task-selector>` reports whether a task is finishable
  without mutating ledger, handoff, run, or roadmap state.
- Finish output includes repair commands when ledger, handoff, review,
  verification, or roadmap evidence is missing or stale.
- Finish reuses existing review evidence and ledger schemas.
- Strict mode is opt-in through config and fails completion when finish
  readiness findings remain.
- Existing `aspec task complete` and supervised run completion behavior remains
  backward compatible.
- Tests cover finish completion, dry-run diagnostics, strict-mode failure, and
  compatibility with shared write-back helpers.
