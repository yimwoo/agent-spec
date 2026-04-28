# DCR-0016: Add runner result ingestion

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

Add structured runner result ingestion so external runner adapters can report
executor output back to AgentSpec with JSON instead of expanding many CLI
flags.

The result command validates the runner payload, records the supervised-run
step, and returns the next runner package for the same run.

## Motivation

`aspec run package` gives external runners a stable execution envelope, but
the report-back path still points at low-level `run step` flags. A JSON result
command completes the package/result handshake and makes simple local loops
less brittle.

## Proposed Change

- Add a runner result schema for `executor_output`, `touched_paths`,
  `test_status`, and optional `reviewer_mode`.
- Add `aspec run result <run-id> --result-json ... --runner ... --json`.
- Validate malformed results before mutating run state.
- Return the next runner package, so callers can continue or stop based on the
  same package contract.
- Update runner package `report_back` metadata to advertise the result schema.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by preserving run boundaries and allowed-path policy during
  result ingestion.
- Supports `R-129` by carrying executor/reviewer loop state through a
  structured package/result handshake.
- Code surface: `agentspec/runner.py`, `agentspec/cli.py`.
- Test surface: runner package/result tests.

## Disposition

Classification: `implement-now`.

This remains non-executing infrastructure. It prepares the loop contract for a
future concrete Codex/Claude subprocess runner.

## Acceptance Criteria

- `aspec run result <run-id> --result-json ... --json` accepts a valid runner
  result and returns the next runner package.
- Completed runner results return `should_execute=false`.
- Invalid runner results are rejected before run state changes.
- Runner package `report_back` advertises the result schema and command.
- `python -m unittest discover -s tests -v` passes.
