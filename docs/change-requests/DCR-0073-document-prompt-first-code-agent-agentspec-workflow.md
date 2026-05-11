# DCR-0073: Document prompt-first code-agent AgentSpec workflow

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-11 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-10 |
| Confidence | medium |

## Summary

Clarify that AgentSpec's primary adoption path is prompt-first code-agent use,
not humans manually driving every CLI command. Humans install the plugin or CLI,
then ask a code agent to initialize a new project, continue an existing
AgentSpec repository, intake new design material, and operate the lifecycle.

The docs should still show the CLI commands because code agents run and report
them, but those commands should be framed as agent-operated implementation
details rather than the required human user experience.

## Motivation

The current README is clean but still looks like a human CLI quickstart. That
undersells the intended product experience: any capable code agent can use
AgentSpec to create a code-agent-friendly repository structure, resume work from
repo-local context, handle new design input through snapshots/DCRs, and complete
the lifecycle with verification, review, roadmap, and handoff write-back.

After installing the plugin, the human should be able to use natural prompts
and let the agent call `aspec` correctly.

## Proposed Change

- Update `README.md` with prompt-first quickstarts for new projects, existing
  projects, and new design changes.
- Update `docs/GETTING_STARTED.md` so humans know what to ask the code agent
  and what evidence to expect back.
- Update Codex and Claude plugin READMEs with prompt examples and the expected
  agent behavior after plugin installation.
- Keep direct CLI examples available as implementation details for agents,
  automation, and advanced users.

## Impact Assessment

- Source sections: `D-05`, `D-10`, `D-18`,
  `agentspec-hotl-integration-without-hotl-names:D-19`.
- New requirement: `R-208`.
- Affected docs: `README.md`, `docs/GETTING_STARTED.md`,
  `agentspec-codex-plugin/README.md`, `agentspec-claude-plugin/README.md`.
- AgentSpec bookkeeping: new task context pack, native workflow, review
  evidence, task ledger, handoff, and generated roadmap refresh.
- Code modules: none.

## Disposition

Accepted for immediate implementation as a documentation-only change.

## Acceptance Criteria

- README leads with prompt-first code-agent usage and explains that humans can
  ask an agent to run AgentSpec on a new or existing project.
- Human guide includes copyable prompts for new project initialization,
  existing project continuation, new design/change intake, and lifecycle finish.
- Plugin READMEs explain how to ask Codex or Claude Code to use the packaged
  `aspec:*` skills after installation.
- Docs still preserve CLI command examples for agents and advanced users, but
  do not imply humans must manually operate every lifecycle step.
- Documentation verification passes with JSON validity checks, markdown diff
  checks, AgentSpec status, and roadmap freshness checks.
