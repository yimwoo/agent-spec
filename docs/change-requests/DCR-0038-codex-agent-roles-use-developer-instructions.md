# DCR-0038: Codex agent roles use developer_instructions

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-03 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-03 |
| Confidence | medium |

## Summary

Update AgentSpec's Codex role emitter to write the current Codex custom-agent
instruction field. New projects initialized with AgentSpec currently receive
`.codex/agents/*.toml` files that use `instructions`; Codex v0.128 rejects
those files because role definitions must define `developer_instructions`.

## Motivation

A dogfood initialization of a new repository produced repeated Codex startup
warnings for `spec-reviewer`, `security-reviewer`, and `brownfield-mapper`.
The warnings prevent AgentSpec-generated Codex agents from loading, which
breaks the intended post-init workflow.

## Proposed Change

- Change `aspec emit --target codex` to emit `developer_instructions` for each
  generated `.codex/agents/*.toml` role.
- Remove the obsolete `instructions` key from generated Codex role files.
- Add test coverage that validates the generated TOML contains
  `developer_instructions` and does not contain the old field.

## Impact Assessment

Likely new requirement:

- `R-173`: Codex agent role emission uses the current custom-agent instruction
  field.

Likely affected artifacts:

- `agentspec/emit.py`
- `tests/test_plugin_source_intake.py`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a compatibility fix for the Codex integration
surface and does not change AgentSpec's artifact model.

## Acceptance Criteria

- `aspec emit --target codex` writes `.codex/agents/*.toml` files with
  `developer_instructions`.
- Generated Codex role files no longer include the obsolete `instructions`
  field.
- Tests cover the generated Codex role schema.
