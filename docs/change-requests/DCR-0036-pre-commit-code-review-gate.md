# DCR-0036: Pre-commit code review gate

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-02 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-02 |
| Confidence | medium |

## Summary

Add an explicit code-review evidence step between code-agent implementation and
final commit or task completion.

The first slice should not attempt to run a full autonomous reviewer inside the
CLI. It should record a host-provided review verdict as a durable AgentSpec
artifact, link that artifact to task completion, and reject completion when the
linked review is not ready.

## Motivation

AgentSpec already requires task context packs, allowed-path scoping, test
evidence, and traceability. The remaining gap is that a code agent can finish an
implementation and commit its own diff without a separate review artifact.

The practical workflow should be:

```text
context pack
 -> code agent implementation
 -> tests/lint
 -> code review
 -> fix findings if needed
 -> commit
 -> mark task complete / push
```

This keeps the implementation agent from being the only judge of its own diff
and gives future automation a stable surface for review evidence.

## Proposed Change

- Add `agent/reviews/REVIEW-####.yml` as the committed review evidence
  projection for task-level code reviews.
- Add `aspec review code` to record a review verdict for a task.
- Support verdicts:
  - `ready`
  - `ready-with-warnings`
  - `not-ready`
- Let `aspec task complete --review REVIEW-####` link review evidence into the
  task completion state and committed task ledger.
- Reject linked task completion when the review artifact is `not-ready` or when
  the review belongs to a different context pack.
- Update agent-facing instructions so code agents run review before the final
  commit/task completion step.

## Impact Assessment

Affected existing requirements:

- `R-007`: CLI ergonomics and local workflow support.
- `R-128`: supervised-run recovery and continuation should be auditable.
- `R-146`: task completion keeps its durable ledger ordering.

Likely new requirement:

- `R-170`: AgentSpec records pre-commit code-review evidence and links passing
  review verdicts to task completion.

Likely affected artifacts:

- `AGENTS.md`
- `agentspec/cli.py`
- `agentspec/review.py`
- `agentspec/run.py`
- `agentspec/task.py`
- `tests/test_code_review_cli.py`
- `tests/test_task_completion.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This introduces a small auditable artifact and CLI workflow
without changing the supervised-run reviewer protocol.

## Acceptance Criteria

- `aspec review code` records a review artifact under `agent/reviews/` with
  schema, review id, context pack, verdict, summary, reviewer, range, and
  timestamp.
- `aspec task complete --review REVIEW-####` links a ready or
  ready-with-warnings review into the completion state and task ledger.
- `aspec task complete --review REVIEW-####` rejects `not-ready` reviews and
  context-pack mismatches before writing run state.
- Agent-facing instructions document the code-review step before final commit.
- Existing task completion and run completion behavior remains backward
  compatible when no review is supplied.
