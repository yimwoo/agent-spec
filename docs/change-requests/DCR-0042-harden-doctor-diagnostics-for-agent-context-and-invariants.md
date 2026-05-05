# DCR-0042: Harden doctor diagnostics for agent context and invariants

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

Harden the new `aspec doctor` diagnostics added for generated agent context and
project invariants.

The review pass found two gaps in the first implementation: missing Codex agent
TOML output is only detected when `.codex/agents/*.toml` already has at least
one file, and malformed `agent/policies/invariants.yml` content can abort
doctor instead of being reported as diagnostic evidence.

## Motivation

The Harness Engineering follow-up work is meant to make project constraints
and validation evidence durable for code agents. Diagnostics that silently miss
an entire emitted target, or fail closed with a stack trace for an optional
policy file, reduce that value. `aspec doctor` should keep producing actionable
agent-readiness output even when a project has incomplete generated context or
invalid invariant configuration.

## Proposed Change

- Warn when AgentSpec source artifacts exist but no generated Codex agent TOML
  files are present under `.codex/agents/`.
- Keep the existing stale-file checks for generated Codex agent TOML files when
  they do exist.
- Convert malformed project invariant configuration into structured
  `invalid_config` diagnostics instead of raising out of `aspec doctor`.
- Convert malformed individual invariant entries into per-entry `invalid`
  diagnostics so one bad rule does not hide other results.
- Keep valid missing/passing/failing invariant behavior unchanged.

## Impact Assessment

Affected existing requirements:

- `R-174`: generated agent instruction freshness should include all emitted
  agent-context targets.
- `R-176`: doctor invariant evaluation should be diagnostic and non-blocking.
- `R-007`: the CLI remains usable locally and in CI.
- `R-035`: dogfooding improves AgentSpec's own repository and agent workflow.

Likely new requirement:

- `R-177`: doctor diagnostics are complete and non-fatal for generated agent
  context and project invariants.

Likely affected artifacts:

- `agentspec/doctor.py`
- `agentspec/policy.py`
- `tests/test_cli_workflow.py`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-072-harden-doctor-diagnostics-for-agent-context-and-invariants.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a narrow hardening change for recently-added
doctor diagnostics.

## Acceptance Criteria

- When AgentSpec source artifacts exist and `.codex/agents/*.toml` has no
  files, `aspec doctor` reports a missing generated Codex agent warning with
  `aspec emit --target claude,codex` as recovery.
- Existing stale checks still report stale generated Codex agent TOML files.
- Invalid `agent/policies/invariants.yml` top-level content is reported as
  `invalid_config` in `repo-scan.yml` and `agent-readiness.md`; doctor exits
  successfully.
- Invalid individual invariant entries are reported as invalid results without
  preventing valid invariant entries from being evaluated.
- Tests cover missing Codex agent TOML output and invalid invariant diagnostics.
