# DCR-0018: Add local subprocess runner

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

Add a local subprocess runner command that executes one runner package, feeds
the package prompt to an external command, collects the command output and
touched paths, and submits the structured runner result back through the
existing result-ingestion path.

## Motivation

The package/result protocol and deterministic demo prove the control-plane
contract. The next useful slice is a small executable adapter that can invoke a
local Codex, Claude, or custom command without baking a model choice into the
repository. This keeps the main executor as the current host/default model
while preserving separate configurable reviewer profiles.

## Proposed Change

- Add `execute_runner` in the runner module for one subprocess-backed
  package/result cycle.
- Add `aspec run exec` with JSON output.
- Allow an explicit command override, while keeping `codex` and `claude`
  runner command hints.
- Feed the package stdin prompt to the subprocess and pass AgentSpec run
  metadata through environment variables.
- Discover touched paths from git status when explicit touched paths are not
  supplied.
- Reuse `submit_runner_result` so policy gates, reviewer decisions, and ledger
  writes remain on the existing path.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by exercising a bounded local execution cycle with
  allowed-path checks.
- Supports `R-129` by sending subprocess output through the reviewer/result
  handoff.
- Code surface: `agentspec/runner.py`, `agentspec/cli.py`.
- Test surface: subprocess runner e2e tests.

## Disposition

Classification: `implement-now`.

This does not require AgentSpec to know the active executor model. Codex and
Claude CLI invocations use their host defaults unless the caller supplies an
explicit command.

## Acceptance Criteria

- `aspec run exec ... --json` returns a schema-tagged transcript.
- The transcript includes an initial runner package, subprocess execution
  metadata, a runner result payload, and a final runner package.
- The subprocess receives the package stdin prompt and AgentSpec environment
  variables.
- The happy path completes the task and writes the committed task ledger.
- A subprocess that touches a forbidden path produces a halted final package.
- `python -m unittest discover -s tests -v` passes.
