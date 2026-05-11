# DCR-0071: Align emitted repo-local skills with lifecycle contract

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

Align generated repo-local AgentSpec skill and agent artifacts with the native
lifecycle operating contract introduced by `R-205`. The packaged Codex and
Claude plugins now expose lifecycle skills, but `aspec emit --target
claude,codex` still emits only generic project-local Claude helper skills and
Codex agent instructions that do not point agents at `aspec lifecycle`.

This change should keep plugin packages as the richer distribution mechanism
while making generated repo-local artifacts useful and honest for projects that
only run `aspec emit`.

## Motivation

The current generated Claude skills use placeholder descriptions and bodies,
which violates skill-authoring best practice: frontmatter should describe when
to trigger the skill, and the body should give concise, specific, CLI-backed
workflow guidance. The current generated Codex artifacts intentionally do not
create project-local Codex skills, but their agent instructions should still
advertise the AgentSpec lifecycle contract and packaged `aspec:*` skills.

Without this alignment, the packaged plugin surface and generated project-local
surface drift apart. That makes the lifecycle contract less portable across
host environments and weakens AgentSpec's role as the operating contract for
human-plus-agent delivery.

## Proposed Change

- Replace generic generated Claude helper skills with lifecycle-aligned
  `SKILL.md` content for core AgentSpec tasks.
- Add generated Claude skills that cover the native lifecycle stages:
  project status, source/compile, task/workflow planning, execution,
  verification, review, finish, handoff/recovery, and lifecycle inspection.
- Keep generated skills concise, CLI-backed, and free of plugin-owned durable
  state.
- Update generated Codex agent instructions to reference `aspec lifecycle
  --json`, the packaged `aspec:*` skills, and task-pack governance without
  adding project-local Codex skill state.
- Add tests that verify generated skill frontmatter, trigger text, command
  specificity, and Codex/Claude emitted artifact behavior.

## Impact Assessment

New requirement:

- `R-206`: AgentSpec emits lifecycle-aligned repo-local skill guidance.

Likely affected artifacts:

- `agentspec/emit.py`
- `tests/test_cli_workflow.py`
- `tests/test_plugin_source_intake.py`
- `docs/change-requests/DCR-0071-align-emitted-repo-local-skills-with-lifecycle-contract.md`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-102-align-emitted-repo-local-skills-with-lifecycle-contract.md`
- `agent/workflows/W-102-align-emitted-repo-local-skills-with-lifecycle-contract.md`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an emitter-quality and consistency change over the
existing lifecycle contract rather than a new runtime state model.

## Acceptance Criteria

- `aspec emit --target claude` writes lifecycle-aligned repo-local Claude skills
  with specific frontmatter descriptions and CLI-backed workflows.
- Generated Claude skills include `aspec lifecycle --json` guidance and cover
  status, source/compile, task/workflow planning, execution, verification,
  review, finish, and handoff/recovery.
- `aspec emit --target codex` continues to avoid project-local Codex skill
  state but generated Codex agent instructions point to `aspec lifecycle
  --json` and packaged `aspec:*` lifecycle skills.
- Tests cover generated skill names, frontmatter/body specificity, lifecycle
  command coverage, and the Codex no-local-skill boundary.
