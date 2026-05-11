# DCR-0067: Add lifecycle skill gates

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-11 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-11 |
| Confidence | medium |

## Summary

Add Phase 8 skill gates from the lifecycle hardening design. AgentSpec should
expose opt-in lifecycle skill gate projections that help coding agents check
whether design, planning, verification, review, and finish evidence exists
without making skills or external adapters own lifecycle state.

This phase continues the operating-contract discipline used for the lifecycle
hardening phases: phase design, executable plan, AgentSpec task pack, and a
dedicated worktree branch before implementation.

## Motivation

AgentSpec now has lifecycle projection, shared write-back helpers, finish
orchestration, strict enforcement, roadmap preservation, and migration tooling.
The remaining design question is how to make agent skills useful without
turning them into another runtime or source of truth.

Skill gates should be a projection over existing AgentSpec artifacts. They
should tell a host agent what evidence is missing and how to repair it, while
leaving execution adapters, subagents, and host-specific skills outside the
durable lifecycle state model.

## Proposed Change

- Add runtime config defaults for `lifecycle.skill_gates`.
- Keep skill gates disabled by default and advisory unless explicitly enabled.
- Project enabled required gates from existing AgentSpec artifacts.
- Surface gate evidence and findings under the existing lifecycle status JSON.
- Promote enabled gate findings to blocking only when lifecycle strict mode is
  already enabled.
- Avoid creating `.agentspec/hooks/`, `agent/evidence/`, or any separate skill
  runtime state in this phase.

## Impact Assessment

New requirement:

- `R-202`: AgentSpec exposes opt-in lifecycle skill gate projections.

Likely affected artifacts:

- `agentspec/config.py`
- `agentspec/writeback.py`
- `agentspec/status.py`
- `tests/test_lifecycle_skill_gates.py`
- `tests/test_lifecycle_enforcement.py`
- `tests/test_config_profiles.py`
- `tests/test_status_cli.py`
- `docs/designs/2026-05-11-phase-8-skill-gates-design.md`
- `docs/plans/2026-05-11-phase-8-skill-gates-workflow.md`
- `docs/change-requests/DCR-0067-add-lifecycle-skill-gates.md`
- `docs/traceability/requirements.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. The change is additive, config-gated, and reuses the
existing lifecycle projection instead of adding a parallel skill or hook state
machine.

## Acceptance Criteria

- Runtime config exposes disabled-by-default lifecycle skill gate settings.
- `aspec status --json` includes a lifecycle skill gate projection.
- Enabled required gates emit lifecycle findings with repair guidance when
  existing AgentSpec evidence is missing.
- Strict lifecycle mode promotes enabled skill gate findings to blocking.
- Skill gate projection does not create or require new durable lifecycle state.
- Tests cover defaults, enabled gate findings, strict promotion, and status JSON
  shape.
