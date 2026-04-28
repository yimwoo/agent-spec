# DCR-0017: Add local runner demo e2e

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

Add a deterministic local runner demo that exercises the full package/result
control-plane handshake end to end.

The demo starts or selects a supervised run, emits a runner package, simulates
a local executor result, submits that result through the runner result
ingestion path, and returns a transcript that tests and humans can inspect.

## Motivation

The runner package/result APIs are useful as primitives, but the project needs
a compact e2e proof that the pieces work together. A local deterministic demo
keeps the flow CI-friendly while documenting the runner contract future
Codex/Claude subprocess adapters should follow.

## Proposed Change

- Add `run_demo` in the runner module to execute one package/result cycle.
- Add `aspec run demo` with JSON output.
- Include a transcript with the initial package, submitted runner result, and
  final package.
- Use normal policy gates, reviewer decisions, and task ledger writes through
  existing `package_run` and `submit_runner_result` code paths.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by exercising bounded supervised run state and allowed-path
  policy end to end.
- Supports `R-129` by exercising the reviewer/runner handoff contract that is
  consumable by a next iteration.
- Code surface: `agentspec/runner.py`, `agentspec/cli.py`.
- Test surface: local runner demo e2e tests.

## Disposition

Classification: `implement-now`.

This is a deterministic fixture, not a real code-agent subprocess launcher.
It prepares the ground for future concrete Codex/Claude runner adapters.

## Acceptance Criteria

- `aspec run demo ... --json` returns a schema-tagged transcript.
- The transcript includes an initial runner package, a runner result payload,
  and a final runner package.
- The happy path completes the task and writes the committed task ledger.
- The e2e test verifies the package/result flow without network access or
  external agent binaries.
- `python -m unittest discover -s tests -v` passes.
