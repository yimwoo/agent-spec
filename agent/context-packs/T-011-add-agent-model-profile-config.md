# T-011: Add Agent Model Profile Config

Type: `implementation`
Originating DCR: `DCR-0006-add-agent-model-profile-config`
Related ADR: `ADR-0003-supervised-run-protocol`

## Goal

Add a configuration shape for model profiles used by secondary supervised-run
agents, while keeping the main executor bound to the current interactive host
agent and its default model.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes one
  context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model produces structured
  feedback consumable by next iteration.

This task adds configuration scaffolding only; it does not accept or implement
`R-127` or `R-129`.

## Source Sections

- `D-07` Architectural Principles
- `D-12.12` Context Pack Builder
- `D-12.17` Policy Engine
- `D-22.3` Codex Role Rules
- `D-23.4` Automation Permissions

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON to
  avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-011-add-agent-model-profile-config.md`
- `docs/change-requests/DCR-0006-add-agent-model-profile-config.md`
- `.agentspec/config.yml`
- `agentspec/config.py`
- `agentspec/init.py`
- `tests/test_config_profiles.py`
- `tests/test_init_layout.py`

## Forbidden Paths

- Anything outside the allowed paths.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Raw credential files such as `~/.codex/auth.json`.

## Tests To Add Or Update

- `tests/test_config_profiles.py`
- `tests/test_init_layout.py`

## Acceptance Criteria

- Fresh `aspec init` writes portable profile defaults.
- Main executor defaults to current host/default model.
- Reviewer profiles reference credential/config sources but contain no secrets.
- Current dogfood config can specify concrete reviewer models.
- `python -m unittest discover -s tests -v` passes.
