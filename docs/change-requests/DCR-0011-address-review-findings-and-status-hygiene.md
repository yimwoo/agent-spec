# DCR-0011: Address review findings and status hygiene

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

Address the four findings from the self code/doc review before continuing with
new feature work. This keeps CLI help, status docs, README onboarding, and
task completion behavior aligned with the current supervised-run control plane.

## Motivation

Agents use CLI help and `AGENTS.md` as operational source material. Stale text
or partially written completion state can cause the next agent to choose the
wrong workflow or get stuck retrying a completion command. These are small
cleanup items, but they matter before increasing autonomy.

## Proposed Change

- Update `dcr accept` help text so it no longer says requirements cascade.
- Refresh `AGENTS.md` status for ADR-0003, T-016, and the task ledger.
- Add the new control-plane workflow to the README quick start.
- Preflight task ledger validity before `task complete` writes run state.
- Add regression tests for stale CLI help and ledger preflight behavior.

## Impact Assessment

- Supports `R-007` by keeping CLI help accurate and local workflows
  discoverable.
- Supports `R-127` by making task completion state safer and less likely to
  strand local run state without committed queue state.
- Documentation surface: `AGENTS.md`, `README.md`, DCR/T-017 context pack.
- Code surface: `agentspec/cli.py`, `agentspec/run.py`, `agentspec/task.py`.
- Test surface: CLI/help and task completion regression tests.

## Disposition

Classification: `implement-now`.

No ADR is required; this is review cleanup within existing behavior.

## Acceptance Criteria

- `aspec dcr --help` describes `dcr accept` without a cascade claim.
- `AGENTS.md` accurately reports DCR-0011 and completed T-001..T-017 status.
- README quick start includes task queue, run loop, and task ledger workflow.
- Malformed task ledger prevents `task complete` before run state is written.
- `python -m unittest discover -s tests -v` passes.
