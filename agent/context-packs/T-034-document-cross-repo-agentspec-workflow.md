# T-034: Document Cross-Repo AgentSpec Workflow

Type: `implementation`

## Goal

Update the root README so a code agent can use this `agent-spec-engine` checkout as the control plane for developing another repository.

## Requirements

- `R-003` Generate a draft project canvas, spec shards, requirements, assumptions, open questions, and task context pack templates.
- `R-006` Generate AGENTS.md, CLAUDE.md, Claude Code subagents, Codex agents, and reusable role definitions.
- `R-023` After that, the repository should contain enough durable context for a code agent to start work without relying on hidden chat history.

## Source Sections

- `D-01` Product Charter
- `D-19` CLI Specification

## Allowed Paths

- `README.md`
- `agent/context-packs/T-034-document-cross-repo-agentspec-workflow.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.

## Tests To Add Or Update

- No code tests required for README-only changes.

## Acceptance Criteria

- README explains how to run AgentSpec against another repository via `--root`.
- README gives a concrete bootstrap flow from design source to context pack to agent execution.
- README explains how agents should handle task context packs, allowed paths, requirement IDs, and traceability.
- README mentions autonomous/research mode at the level currently supported by the CLI.
