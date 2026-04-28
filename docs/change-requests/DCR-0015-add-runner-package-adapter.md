# DCR-0015: Add runner package adapter

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

Add a runner package adapter that wraps a harness step in an execution envelope
for external code-agent runners.

The package includes the step verdict, whether the runner should execute, the
prompt to send on stdin, stable environment variables, and a control-plane
command template for reporting the executor result back to AgentSpec.

## Motivation

`aspec run step` gives harnesses the next control-plane action, but external
runners still need to map that action into an execution contract. A small
runner package makes the handoff explicit without hard-coding a particular
Codex or Claude CLI invocation.

## Proposed Change

- Add a runner package builder around `step_run`.
- Add `aspec run package` with `--runner generic|codex|claude` and `--json`.
- For `continue_executor`, return `should_execute=true`, stdin prompt, env
  hints, and a report-back command array using `aspec run step`.
- For `await_human`, `complete`, or `stop`, return `should_execute=false` and
  no stdin prompt.
- Keep the adapter non-executing; it prepares the package but does not spawn an
  external code agent.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by keeping run scope and iteration state in the execution
  package.
- Supports `R-129` by carrying reviewer-generated prompt text into a runner
  consumable envelope.
- Code surface: `agentspec/runner.py`, `agentspec/cli.py`.
- Test surface: runner package tests.

## Disposition

Classification: `implement-now`.

This is a reference adapter boundary, not a full autonomous agent launcher.
Future work can add concrete Codex/Claude subprocess runners once the package
contract proves stable.

## Acceptance Criteria

- `aspec run package --runner generic --json` starts/selects a ready task and
  returns a schema-tagged runner package.
- A `continue_executor` package includes `should_execute=true`, stdin prompt,
  env hints, and a report-back command template.
- A completed step returns `should_execute=false` and no stdin prompt.
- Unknown runner names are rejected.
- `python -m unittest discover -s tests -v` passes.
