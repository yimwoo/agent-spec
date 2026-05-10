# DCR-0055: Add outcome gates and unified lifecycle skills

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-10 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-10 |
| Confidence | medium |

## Summary

Add an AgentSpec-native product outcome layer and unified lifecycle skill
surface so code agents can distinguish "AgentSpec tasks are complete" from
"the product's critical E2E workflows are production-ready." The outcome layer
tracks named workflows, gates, evidence, blockers, and a readiness verdict in
repo-local artifacts and exposes them through the CLI, status, and quality
diagnostics.

Also expand generated/packaged AgentSpec skill guidance so teams can rely on
project-approved lifecycle workflows without every developer installing the
same personal HOTL, Superpowers, or ad hoc skill pack.

## Motivation

The Oracle DB system-testing platform dogfood project exposed a gap in
AgentSpec's current readiness model: the project can have many completed
requirements/tasks and still be unable to run its intended production E2E
workflows. AgentSpec currently governs context packs and review evidence well,
but it does not have a first-class product-outcome control plane above tasks.

The desired operating model is for AgentSpec to own the repo-local lifecycle
policy and generate thin adapters for Codex, Claude Code, and other agent
hosts. HOTL, addyosmani/agent-skills, and obra/superpowers should be useful
references, but not required local dependencies for every developer.

## Proposed Change

- Add an `agent/outcomes.yml` artifact contract for product workflows, outcome
  gates, required proof, blockers, and readiness scoring.
- Add `aspec outcome` CLI reporting with JSON and human-readable output.
- Include outcome readiness in `aspec status --json` and generated `AGENTS.md`
  so agents see product readiness alongside task readiness.
- Promote failing or missing outcome gates into Quality GC findings.
- Add unified AgentSpec lifecycle skills to Codex and Claude plugin packages:
  `outcome-audit`, `plan-workflow`, `verify-work`, `review-code`, and
  `finish-work`.
- Keep plugins and generated skills as thin adapters over core CLI/artifact
  behavior.

## Impact Assessment

New requirement:

- `R-190`: AgentSpec exposes product outcome gates and unified lifecycle
  skills.

Likely affected artifacts:

- `agentspec/outcome.py`
- `agentspec/cli.py`
- `agentspec/status.py`
- `agentspec/quality.py`
- `agentspec/init.py`
- `agentspec/paths.py`
- `agentspec/emit.py`
- `agentspec-codex-plugin/skills/**/SKILL.md`
- `agentspec-claude-plugin/skills/**/SKILL.md`
- `tests/test_outcome_cli.py`
- `tests/test_cli_workflow.py`
- `tests/test_quality_gc.py`
- `tests/test_claude_code_plugin.py`
- `docs/change-requests/DCR-0055-add-outcome-gates-and-unified-lifecycle-skills.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for the first slice. The core model remains local-first,
CLI-first, and adapter-neutral. A later ADR may be appropriate for remote MCP
or organization-wide lifecycle policy distribution.

## Acceptance Criteria

- `aspec outcome --json` emits schema `agentspec.outcome_status.v0`.
- `aspec outcome` summarizes outcome readiness, blockers, and next actions.
- Fresh projects include an `agent/outcomes.yml` seed artifact.
- `aspec status --json` includes an `outcomes` section.
- Generated `AGENTS.md` includes product outcome readiness and the outcome CLI
  command.
- Quality GC reports a warning when product outcomes are not ready or outcome
  gates are blocked.
- Codex and Claude plugin packages include CLI-backed lifecycle skills for
  outcome audit, workflow planning, verification, code review, and finishing.
- Tests cover outcome status/reporting, quality integration, generated context,
  and plugin skill package layout.
