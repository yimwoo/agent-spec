# DCR-0024: Atomic completion + research-mode ledger guard

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-29 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-29 |
| Confidence | medium |

## Summary

Promote DCR-0022 item 2 to its own implement-now slice and bundle it
with a related research-mode defect surfaced by run
`research-20260429T164324Z`. Both defects share the call site at
`agentspec/run.py:375-386` — the unconditional ledger write on
`review.decision == "complete"` — so a single fix can address both:

1. **Completion atomicity** — the ledger write follows the state-file
   write, so a failed ledger write leaves the run `complete` on disk
   while the ledger still shows the pack as open. Retries are then
   blocked by duplicate-state detection.
2. **Research-mode write** — the ledger write fires regardless of run
   mode, so research-mode `complete` produces a `<research-mode>`
   entry in `agent/task-ledger.yml`, violating ADR-0005 / R-142's
   research-mode write surface
   (`reports/dogfood/**`, `docs/discovery/open-questions.yml`,
   `docs/change-requests/**`).

## Motivation

DCR-0022 originally captured four operability findings as a single
deferred backlog DCR. The classification was correct at filing time,
but two events since then sharpen the case for promoting item 2 alone:

- The empty-queue research run on 2026-04-29 produced a live,
  observable contract violation against ADR-0005 / R-142. The
  polluting ledger entry was removed by hand; capturing the fix in
  code closes the loop.
- The dogfood DCR→R→T→PR cycle just demonstrated by issue #1 / T-043
  shows the project can absorb small, well-scoped reliability fixes
  quickly. Item 2 fits that shape.

Items 1, 3, and 4 of DCR-0022 remain `defer` — this DCR does not
override that decision.

## Proposed Change

In `agentspec/run.py` around the existing completion path
(`agentspec/run.py:373-386` and the equivalent block in
`complete_context_pack_run`):

- Skip `record_task_ledger_status` entirely when the run is research
  mode. Detect via `state.get("mode") == "research"` AND/OR
  `state.get("context_pack") == RESEARCH_CONTEXT_PACK_SENTINEL`.
  Whichever check is used must be robust to either field being
  truthful — research runs always set both, so either alone is
  sufficient.
- For non-research runs, reorder the writes so the ledger update
  happens before the run state file is finalized. Ledger writes are
  idempotent inserts; if they fail, the state file is never written
  and a retry naturally converges. No new schema needed.

The fix touches one module. No public CLI surface changes. No new
flags or schema fields.

## Impact Assessment

- New requirement: `R-146`.
- Affected requirements: `R-142` (research-mode allowed write
  surface, strengthens), `R-128` (run-state breadcrumbs, strengthens),
  `R-007` (CLI / harness reliability).
- Code surface: `agentspec/run.py`.
- Test surface: new tests for research-mode no-write and for
  completion-write ordering. Existing tests
  (`tests/test_research_mode.py`, `tests/test_supervised_run_loop.py`,
  `tests/test_supervised_run.py`) must continue to pass.

## Disposition

Classification: `implement-now`.

Both defects are real. Both share a call site. Tests are tractable
without new infrastructure. No new design surface area — the fix is
guard-and-reorder on an existing code path. No ADR is required
because the intended behavior matches the established research-mode
contract (ADR-0005 / R-142) and the documented atomicity expectation
in DCR-0022 item 2.

## Acceptance Criteria

- Research-mode `complete` does not modify `agent/task-ledger.yml`.
  Specifically: a research run that reaches `complete` leaves the
  ledger byte-identical to its pre-run state.
- Implementation-mode `complete` still records the pack as
  `complete` in `agent/task-ledger.yml` exactly as before.
- The completion code path writes the ledger before finalizing the
  run state file (or uses an equivalent compensating-delete strategy)
  so a failed ledger write cannot leave a `complete` state file
  behind without a corresponding ledger entry.
- The full test suite continues to pass, including
  `tests/test_research_mode.py` and the supervised-run tests.
- DCR-0022 item 2 references this DCR as the resolution.
