# DCR-0069: Make handoff status portable across clean checkouts

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

Make committed AgentSpec handoff state portable across clean checkouts by
removing local-only run counts from the durable handoff freshness contract.
`agent/runs/*/state.yml` files are ignored local execution state, so a handoff
written in one worktree must not become stale solely because a different
checkout lacks those ignored files.

## Motivation

The AgentSpec lifecycle E2E smoke test completed successfully in its active
worktree, but a detached clean checkout of the same commit reported
`stale_handoff`: `aspec status --json` saw one tracked run summary while
`agent/handoff.yml` had embedded three local run records from ignored state
files. That makes committed handoff readiness depend on local untracked files,
which is unsafe for branch handoff, review, and CI.

## Proposed Change

- Keep `agent/handoff.yml` focused on portable project counts.
- Do not include local-only run counts in newly written handoff
  `current_state`.
- Do not compare handoff run counts when detecting stale handoff lifecycle
  warnings.
- Add regression coverage for a clean checkout that has fewer run state files
  than the worktree that wrote handoff.

## Impact Assessment

New requirement:

- `R-204`: AgentSpec handoff freshness is portable across clean checkouts.

Likely affected artifacts:

- `agentspec/handoff.py`
- `agentspec/writeback.py`
- `tests/test_status_cli.py`
- `tests/test_writeback.py`
- `tests/test_lifecycle_enforcement.py`
- `docs/change-requests/DCR-0069-make-handoff-status-portable-across-clean-checkouts.md`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-100-make-handoff-status-portable-across-clean-checkouts.md`
- `agent/workflows/W-100-make-handoff-status-portable-across-clean-checkouts.md`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a compatibility fix to the existing handoff and
lifecycle projection behavior, not a new lifecycle state store.

## Acceptance Criteria

- New handoff writes do not include local-only run counts in `current_state`.
- Lifecycle stale handoff detection ignores legacy handoff run-count
  mismatches.
- Requirements, DCR, task count, and other portable handoff mismatches continue
  to report `stale_handoff`.
- A regression test covers a clean checkout with fewer tracked run artifacts
  than the handoff writer worktree.
- The AgentSpec lifecycle E2E clean-checkout probe no longer reports
  `stale_handoff` solely because of ignored local run state.
