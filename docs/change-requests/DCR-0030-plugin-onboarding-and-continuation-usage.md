# DCR-0030: Plugin onboarding and continuation usage

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

Clarify the AgentSpec Codex plugin user journey so end users can choose either
the core CLI or the Codex plugin for two common workflows:

- initializing AgentSpec in a new or existing repository;
- continuing work in a repository that already has AgentSpec artifacts.

The plugin should remain a thin CLI adapter. The update is documentation and
skill guidance, not new core behavior.

## Source Sections

- `D-03.2`: V2 goal for Claude Code and Codex plugins as thin adapters.
- `D-10.5`: Codex plugin surface.
- `D-22.2`: Codex plugin package layout.
- `D-26.1`..`D-26.3`: core before plugins and recommended plugin sequence.

## Motivation

DCR-0029 added a Codex plugin alpha and manual source-intake skill, but the
package still reads like an internal implementation artifact. An end user needs
clear instructions for:

- using the CLI directly when they prefer terminal workflows;
- using plugin skills when they are working inside Codex;
- choosing the right command or skill for a new repository vs an existing one;
- continuing from `aspec status`, `aspec task next`, or `aspec run loop`.

Without this, users may assume the plugin replaces the CLI or creates a separate
state model. That would conflict with the core-before-plugins principle.

## Proposed Change

Update the Codex plugin package with:

- README usage sections for CLI and plugin workflows.
- An `init-project` skill that explains how to initialize a target repo through
  `aspec init`, `aspec ingest` or `aspec intake`, `aspec compile`, `aspec emit`,
  and `aspec status`.
- A `continue-work` skill that explains how to inspect status, select the next
  task, run or resume an AgentSpec loop, and verify changes.
- Updated skill descriptions so Codex can select skills for "new repo",
  "existing repo", "continue work", "import external design", and "source
  intake" phrasing.

## Non-Goals

- No new source connector behavior.
- No plugin-owned state.
- No replacement for `aspec` CLI commands.
- No auto-promotion, auto-task-completion, or hidden writes outside the
  selected AgentSpec command.

## Impact Assessment

Affected existing requirements:

- `R-012`: plugins remain thin adapters over core CLI/MCP direction.
- `R-100`: vendor-neutral core remains primary; plugins adapt.
- `R-164`: plugin source intake remains CLI-backed and human-gated.

Likely new requirement:

- `R-165`: AgentSpec Codex plugin usage documentation and skill metadata explain
  how to initialize a new or existing repository and continue work using either
  CLI commands or plugin skills.

Likely affected artifacts:

- `agentspec-codex-plugin/README.md`
- `agentspec-codex-plugin/.codex-plugin/plugin.json`
- `agentspec-codex-plugin/skills/**/SKILL.md`
- `tests/test_plugin_source_intake.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This is plugin documentation and skill metadata over the
existing CLI-backed plugin boundary.

## Acceptance Criteria

- Plugin README shows CLI and plugin paths for initializing a repository.
- Plugin README shows CLI and plugin paths for continuing work in an existing
  AgentSpec repository.
- Plugin skills include discoverable descriptions for init/new-repo and
  continue-existing-repo workflows.
- Tests verify the plugin package includes the init, continue, status, and
  manual source-intake guidance.
- Installed local Codex plugin copy is refreshed after the repo package update.
