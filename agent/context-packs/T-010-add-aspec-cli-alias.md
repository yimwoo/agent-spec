# T-010: Add `aspec` CLI Alias

Type: `implementation`
Originating DCR: `DCR-0005-add-aspec-cli-alias`

## Goal

Add `aspec` as the short public command for AgentSpec while retaining the
existing `agentspec` command.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-006` (P1, accepted) Generate AGENTS.md, CLAUDE.md, Claude Code subagents,
  Codex agents, and reusable role definitions.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-19` CLI Specification
- `D-22.3` Codex Role Rules

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON to
  avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-010-add-aspec-cli-alias.md`
- `docs/change-requests/DCR-0005-add-aspec-cli-alias.md`
- `pyproject.toml`
- `agentspec/cli.py`
- `agentspec/emit.py`
- `README.md`
- `AGENTS.md`
- `tests/test_cli_alias.py`
- `tests/test_cli_workflow.py`

## Forbidden Paths

- Anything outside the allowed paths.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.

## Tests To Add Or Update

- `tests/test_cli_alias.py`
- Existing CLI workflow tests if emitted AGENTS command expectations change.

## Acceptance Criteria

- `pyproject.toml` exposes both `agentspec` and `aspec`.
- Parser help can render `usage: aspec ...`.
- README and generated AGENTS key commands prefer `aspec`.
- `python -m unittest discover -s tests -v` passes.
