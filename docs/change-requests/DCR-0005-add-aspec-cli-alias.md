# DCR-0005: Add aspec CLI alias

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

Add `aspec` as the official short CLI alias for `agentspec`.

The long `agentspec` command remains supported for backwards compatibility,
but user-facing examples and generated key-command snippets should prefer the
shorter `aspec` form.

## Motivation

The project is now used interactively during dogfooding. Repeated commands like
`agentspec task create`, `agentspec dcr list`, and future supervised-run
commands are verbose enough to slow the inner loop. The project owner selected
`aspec` after rejecting `ase` due to likely command-name collision risk.

## Proposed Change

- Add a `pyproject.toml` console script alias:
  `aspec = "agentspec.cli:main"`.
- Keep `agentspec = "agentspec.cli:main"`.
- Make CLI help/error output use the invoked command name when invoked as
  `aspec`.
- Prefer `aspec` in README and generated AGENTS key commands.

## Impact Assessment

- Affects `R-007` (local/CI CLI) by adding a shorter public entry point.
- Affects `R-006` generated agent instruction artifacts because emitted key
  commands should use the shorter alias.
- Code surface: `pyproject.toml`, `agentspec/cli.py`, `agentspec/emit.py`.
- Test surface: CLI alias packaging/help behavior.

## Disposition

Classification: `implement-now`.

No ADR is required. This is a CLI ergonomics change that preserves the existing
long command.

## Acceptance Criteria

- `pyproject.toml` exposes both `agentspec` and `aspec` console scripts.
- `build_parser(prog="aspec")` renders usage with `aspec`.
- Generated AGENTS key commands prefer `aspec`.
- Existing CLI tests continue to pass.
