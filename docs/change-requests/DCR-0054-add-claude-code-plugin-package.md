# DCR-0054: Add Claude Code plugin package

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-06 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-06 |
| Confidence | medium |

## Summary

Add a distributable AgentSpec Claude Code plugin package alongside the existing
Codex plugin package. The Claude Code plugin should provide the same
CLI-backed AgentSpec workflow skills for project initialization, continuation,
status inspection, task creation, spec compilation, drift review, and manual
source intake.

This does not change the core engine or make the plugin own parsing, state, or
governance. It packages Claude Code-facing skills and metadata as a thin
adapter over the existing `aspec` CLI.

## Motivation

AgentSpec already emits project-local `CLAUDE.md`, `.claude/agents/**`, and
`.claude/skills/**` artifacts, and it already ships an AgentSpec Codex plugin
for reusable skill distribution. Users who operate in Claude Code need the
same reusable plugin experience rather than relying only on repo-local emitted
skills.

The canonical design already calls for Claude Code and Codex plugins as thin
adapters over the core CLI/MCP direction. Current Claude Code plugin guidance
also supports packaging skills in a plugin directory with a
`.claude-plugin/plugin.json` manifest, making a dedicated AgentSpec Claude Code
plugin a natural next adapter slice.

## Proposed Change

- Add an `agentspec-claude-plugin/` package with:
  - `.claude-plugin/plugin.json`
  - `README.md`
  - root-level `skills/**/SKILL.md` workflow skills
- Mirror the Codex plugin's CLI-backed workflows while using Claude Code
  naming and installation guidance.
- Keep skills concise and procedural, with `name` and `description`
  frontmatter and no duplicated core implementation logic.
- Add tests that validate the Claude Code plugin manifest, skill files,
  README usage guidance, and thin-adapter boundaries.
- Validate the plugin with the Claude Code CLI when available.

## Impact Assessment

Source sections:

- `D-03.2`: V2 goal for Claude Code and Codex plugins as thin adapters.
- `D-10.4`: Claude Code plugin surface.
- `D-21.2`: Claude Code plugin package direction.
- `D-26.1`..`D-26.3`: core-before-plugins and plugin sequence.

Affected existing requirements:

- `R-006`: project-local Claude artifacts remain supported.
- `R-012`: plugins remain thin adapters over core CLI/MCP direction.
- `R-100`: vendor-neutral core remains primary; plugins adapt.
- `R-164`: plugin source intake remains CLI-backed and human-gated.

New requirement:

- `R-189`: AgentSpec ships a Claude Code plugin package with CLI-backed
  workflow skills.

Likely affected artifacts:

- `agentspec-claude-plugin/**`
- `docs/change-requests/DCR-0054-add-claude-code-plugin-package.md`
- `docs/traceability/requirements.yml`
- `tests/test_claude_code_plugin.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an adapter/package slice that follows the existing
plugin strategy and mirrors the shipped Codex plugin boundary.

## Acceptance Criteria

- Claude Code plugin package includes `.claude-plugin/plugin.json`.
- Claude Code plugin package includes discoverable skills for init,
  continuation, status, task creation, compile, drift review, and manual source
  intake workflows.
- README documents local Claude Code plugin loading/validation and the matching
  CLI paths.
- Skill guidance remains CLI-backed and states that the plugin does not own
  parsing, promotion, credentials, or accepted snapshots.
- Tests validate the package layout, manifest metadata, skill frontmatter, and
  public guidance.
- `claude plugin validate agentspec-claude-plugin` passes when Claude Code
  is installed.
