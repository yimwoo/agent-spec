# DCR-0047: First-class verification scope and session handoff

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

Make verification and continuation artifacts first-class in AgentSpec task
scope. Generated task context packs should include the standard support files
needed to finish work (`agent/reviews/*.yml`, `agent/task-ledger.yml`, and
`agent/handoff.yml`) so agents do not have to revise allowed paths just to
record review, completion, and handoff evidence.

Also add a compact committed handoff artifact at `agent/handoff.yml` whenever a
task completes. New sessions should be able to inspect that file or
`aspec status` to know the last completed task, whether a next task is ready,
and the exact command to continue.

## Motivation

Q-011 asked whether task context packs should include verification-generated
artifacts in allowed scope or model them separately. Recent dogfood tasks
repeatedly needed manual scope additions for `agent/reviews/REVIEW-####.yml`
and `agent/task-ledger.yml` before completion. That friction is unnecessary:
verification artifacts are not product-code scope expansion; they are required
control-plane evidence.

The user also wants multi-session continuity. A future code agent should not
need to reread all docs and code to determine where to resume. It should be
able to start from a small committed handoff state, then drill into the active
context pack only when there is ready work.

## Proposed Change

- Generated task context packs include a standard "verification support"
  scope:
  - `agent/reviews/*.yml`
  - `agent/task-ledger.yml`
  - `agent/handoff.yml`
- `aspec task complete` writes `agent/handoff.yml` after recording the task
  ledger and run state.
- Normal supervised run completion also writes the same handoff artifact.
- `aspec status --json` includes the latest handoff summary when present.
- Human `aspec status` output points at the handoff artifact.
- Mark `Q-011` answered by this DCR.

## Impact Assessment

Affected existing artifacts:

- `agentspec/task.py`
- `agentspec/run.py`
- `agentspec/status.py`
- `tests/test_task_queue.py`
- `tests/test_task_completion.py`
- `tests/test_status_cli.py`
- `docs/discovery/open-questions.yml`

Likely new requirement:

- `R-182`: Task packs include verification support scope and task completion
  writes a committed handoff state.

Likely task context pack:

- `T-077`: first-class verification scope and session handoff.

## Disposition

Classification: `implement-now`.

No ADR is required. The change extends the existing task-ledger, status, and
handoff mechanics; it does not alter the core task/run architecture.

## Acceptance Criteria

- Newly generated task context packs include `agent/reviews/*.yml`,
  `agent/task-ledger.yml`, and `agent/handoff.yml` in Allowed Paths.
- Completing a task writes `agent/handoff.yml` with schema, last completed
  task, status counts, next action, and continuation commands.
- `aspec status --json` includes the handoff payload when present.
- Human `aspec status` output mentions the handoff path and next action.
- `Q-011` is marked answered by `DCR-0047/R-182`.
- Full unittest discovery passes.
