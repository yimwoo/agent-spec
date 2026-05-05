# DCR-0049: Quality GC Task Completion Cadence

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

Add optional task-completion cadence integration for the Quality GC lane.

`aspec quality` now provides a useful recurring report, but operators still
have to remember when to run it. AgentSpec should be able to run the scan
automatically after task completion when project config opts in and the
completed-task cadence is due.

## Motivation

The user asked whether Quality GC is called automatically during task work or
must be run manually. The first slice intentionally kept it manual and
scheduler-ready. The next small step is to make the recurring lane available
inside the existing task-completion lifecycle without making it a blocking
implementation gate.

Quality GC should remain a diagnostic cleanup lane: if it runs, it writes the
latest report; if it is disabled or not due, task completion proceeds normally.

## Proposed Change

- Add `quality_gc` runtime config defaults:
  - `run_on_task_complete`
  - `task_interval`
  - `report_dir`
- Keep global defaults disabled so existing projects do not get unexpected
  report writes.
- Enable the cadence in this dogfood repository config.
- After `aspec task complete` writes ledger state and handoff, evaluate the
  Quality GC cadence and run `aspec quality` when due.
- Record the Quality GC result or skip reason in the completion state.
- Keep Quality GC failures non-blocking for task completion.

## Impact Assessment

Affected artifacts:

- `agentspec/config.py`
- `agentspec/run.py`
- `agentspec/quality.py`
- `.agentspec/config.yml`
- `tests/test_config_profiles.py`
- `tests/test_task_completion.py`
- `tests/test_quality_gc.py`
- `docs/traceability/requirements.yml`

Likely new requirement:

- `R-184`: task completion can run Quality GC when configured cadence is due.

Likely task context pack:

- `T-079`: Quality GC task completion cadence.

## Disposition

Classification: `implement-now`.

No ADR is required. This is an opt-in hook over an existing diagnostic report
surface. A later DCR can add cron automation templates or automatic cleanup
task creation.

## Acceptance Criteria

- Runtime config exposes `quality_gc.run_on_task_complete`,
  `quality_gc.task_interval`, and `quality_gc.report_dir` with safe defaults.
- This repository's `.agentspec/config.yml` enables task-completion Quality GC
  cadence with a task interval of 3.
- `aspec task complete` runs Quality GC after completion when configured and
  due.
- `aspec task complete` records `quality_gc.status=skipped` when disabled or
  not due.
- Quality GC errors are recorded as `quality_gc.status=error` without blocking
  task completion.
- Focused tests and full unittest discovery pass.
