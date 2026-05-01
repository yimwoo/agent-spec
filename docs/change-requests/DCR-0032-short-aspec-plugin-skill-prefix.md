# DCR-0032: Short aspec plugin skill prefix

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Rename the AgentSpec Codex plugin identity from the implementation-oriented
`agentspec-codex-plugin` prefix to the user-facing `aspec` prefix.

The plugin package can remain in the repository under
`agentspec-codex-plugin/`, but the skill call surface should read like the CLI:
`aspec:init-project`, `aspec:continue-work`, `aspec:create-task`, and related
skills.

## Motivation

After removing overlapping repo-local skills in DCR-0031, Codex now exposes the
installed plugin as the only AgentSpec workflow skill surface. The current
visible prefix is still too long:

- `agentspec-codex-plugin:init-project`
- `agentspec-codex-plugin:continue-work`

This is hard to scan and does not match the CLI mental model. A shorter `aspec`
prefix is consistent with the command users already run in the terminal.

## Proposed Change

- Change the plugin manifest identity to `aspec`.
- Change the plugin display name to `aspec`.
- Update README and skill references from `agentspec-codex-plugin:*` to
  `aspec:*`.
- Update plugin package tests and Codex prompt-discovery checks.
- Refresh the local installed plugin under the new identity.
- Remove or disable the old installed `agentspec-codex-plugin` identity so
  Codex does not show both prefixes.

## Impact Assessment

Affected existing requirements:

- `R-164`: manual source intake remains CLI-backed, but its plugin call name
  changes to `aspec:manual-source-intake`.
- `R-165`: init and continue workflows remain documented, but the examples
  change to `aspec:init-project` and `aspec:continue-work`.
- `R-166`: dogfooding continues to use installed plugin skills, now under the
  shorter `aspec` identity.

Likely new requirement:

- `R-167`: AgentSpec Codex plugin uses the short `aspec:*` skill prefix and no
  longer exposes the old `agentspec-codex-plugin:*` prefix after local install
  refresh.

Likely affected artifacts:

- `agentspec-codex-plugin/.codex-plugin/plugin.json`
- `agentspec-codex-plugin/README.md`
- `agentspec-codex-plugin/skills/**/SKILL.md`
- `tests/test_plugin_source_intake.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a plugin packaging and UX naming cleanup that does
not change core AgentSpec CLI semantics.

## Acceptance Criteria

- Plugin manifest name is `aspec`.
- Plugin README and skill guidance use `aspec:*` examples.
- Tests assert the short prefix and reject the old long prefix in public docs.
- Local installed plugin/cache/marketplace are refreshed under the `aspec`
  identity.
- Codex prompt discovery exposes `aspec:*` skills and does not expose
  `agentspec-codex-plugin:*`.
