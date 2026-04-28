# DCR-0014: Add harness step command

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Add a single harness-facing control-plane step that selects or resumes a
supervised run, evaluates reviewer output when present, and returns the next
action plus an executor handoff prompt in one JSON payload.

This gives external code-agent runners a stable loop primitive instead of
requiring them to orchestrate `task next`, `run loop`, and `run prompt`
separately.

## Motivation

The local control plane can now select tasks, run bounded iterations, call a
continuation reviewer, and render a next executor prompt. The missing product
surface is a compact command that a harness can call repeatedly to decide
whether to continue the main executor, wait for a human/reviewer, or stop.

## Proposed Change

- Add `aspec run step` as a harness-oriented wrapper around `run loop` and
  `run prompt`.
- Return a schema-tagged JSON payload with `next_action`, run state, selected
  task, reviewer verdict, and optional handoff prompt.
- Use `next_action=continue_executor` for started/running runs,
  `await_human` for paused runs, `complete` for completed runs, and `stop` for
  halted/aborted runs.
- Keep deterministic policy gates and verification completion semantics
  unchanged.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by preserving bounded run execution and allowed-path
  enforcement.
- Supports `R-129` by making reviewer feedback directly consumable by a
  next-iteration harness step.
- Code surface: `agentspec/run.py`, `agentspec/cli.py`.
- Test surface: supervised-run step tests.

## Disposition

Classification: `implement-now`.

This is a minimal harness protocol layer. It does not execute an external code
agent; it only returns the control-plane decision and prompt that such a runner
can consume.

## Acceptance Criteria

- `aspec run step --json` can select the next ready context pack, start a run,
  and return `next_action=continue_executor` with a handoff prompt.
- `aspec run step --run-id <id> --executor-output ... --json` can resume a run
  and include reviewer verdict plus a next prompt when the decision is
  `auto_continue`.
- Completed runs return `next_action=complete` and no handoff prompt.
- Paused runs return `next_action=await_human` and no handoff prompt.
- `python -m unittest discover -s tests -v` passes.
