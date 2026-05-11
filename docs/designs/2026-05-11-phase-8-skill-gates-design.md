---
design_type: phase
created_at: 2026-05-11
parent_design: docs/source/src-0003-lifecycle-engine-hardening-design.md
originating_dcr: DCR-0067
requirement: R-202
branch: codex/phase8-skill-gates
worktree: /Users/yimwu/Documents/workspace/Apps/agent-spec-engine-phase8-skill-gates
---

# Phase 8: Skill Gates

## Intent Contract

intent: Add opt-in lifecycle skill gate projections so host agents can see missing design, planning, verification, review, and finish evidence without making skills own AgentSpec lifecycle state.

constraints:
- Skill gates remain adapters or guidance modules; they do not execute hooks, spawn subagents, or own lifecycle state.
- Default behavior remains quiet for legacy and newly initialized repos.
- Gate findings derive from existing AgentSpec artifacts: design docs, workflows, task ledger, review evidence, handoff, and roadmap.
- Public naming remains AgentSpec-native.
- Existing lifecycle projection, strict enforcement, finish, and status behavior remain compatible.

success_criteria:
- Runtime config includes disabled-by-default lifecycle skill gate defaults.
- `aspec status --json` includes a `lifecycle.skill_gates` projection.
- Enabled required gates emit repairable lifecycle findings when required evidence is missing.
- Strict lifecycle mode promotes required gate findings to blocking findings.
- Tests prove defaults, enabled findings, strict promotion, and non-stateful behavior.

risk_level: medium

## Verification Contract

verify_steps:
- run focused skill gate tests: `python -m unittest tests/test_lifecycle_skill_gates.py -v`
- run related lifecycle/config/status tests: `python -m unittest tests/test_lifecycle_skill_gates.py tests/test_lifecycle_enforcement.py tests/test_config_profiles.py tests/test_status_cli.py -v`
- run full suite: `python -m unittest discover -s tests -v`
- check formatting: `git diff --check`
- confirm roadmap current: `aspec roadmap --check --json`
- confirm AgentSpec status: `aspec status --json`

## Governance Contract

approval_gates:
- Phase design and executable plan exist before implementation.
- AgentSpec task pack defines allowed paths before implementation.
- Failing tests are written before implementation.
- Code review evidence is recorded with `aspec review code` before task completion.
- `aspec task complete` links the ready review evidence.

rollback:
- Revert the Phase 8 commit from branch `codex/phase8-skill-gates`.
- Remove any optional project `lifecycle.skill_gates` config if a repo enabled it during testing.
- Because no new lifecycle state directory is introduced, rollback does not require state migration.

ownership: AgentSpec maintainer and current code agent.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| Config | Add `lifecycle.skill_gates` defaults | Make gates enabled by default |
| Projection | Add status JSON projection for enabled and disabled gates | Persist a separate skill gate state file |
| Findings | Emit repairable findings for missing required evidence | Execute skill adapters or shell hooks |
| Enforcement | Reuse lifecycle strict mode for blocking promotion | Add a new enforcement mode |
| Naming | Keep public text AgentSpec-native | Expose HOTL-specific terminology |
| Documentation | Add phase DCR, requirement, design, and workflow plan | Rewrite the parent lifecycle design |

## Decisions

| # | Decision | Choice | Rejected alternatives |
|---|---|---|---|
| 1 | State model | Derive gates from existing artifacts | Add `agent/evidence/` or `.agentspec/hooks/` in this phase |
| 2 | Default | Disabled and advisory by default | Enable gates for every existing repo |
| 3 | Status surface | Nest projection under `lifecycle.skill_gates` | Add a top-level skill runtime status |
| 4 | Enforcement | Reuse `lifecycle.enforcement: strict` | Add a separate gate-blocking config |
| 5 | Gate vocabulary | Use AgentSpec lifecycle stages | Preserve external skill or plugin names |
| 6 | Repair model | Include commands or guidance in findings | Emit findings that only name missing evidence |

## Surface

`agentspec/config.py` should expose portable lifecycle skill gate defaults and merge them into existing project configs without disturbing project overrides.

`agentspec/writeback.py` should build the skill gate projection inside the existing lifecycle projection. The projection should include enabled state, required gates, per-gate evidence, findings, and repair guidance. The helper must read existing files and avoid creating any state.

`agentspec/status.py` should continue using the existing lifecycle projection and should not need a parallel status model. Human output can rely on existing lifecycle warning rendering when enabled gates produce findings.

`tests/test_lifecycle_skill_gates.py` should cover disabled defaults, enabled required gate findings, strict promotion, and evidence projection. Existing lifecycle and status tests should continue to pass unchanged except for intentional JSON shape assertions.

## Risks & Open Questions

Risks:
- Skill gates could become a second runtime if they start writing state. Mitigation: keep the phase read-only and derived from existing artifacts.
- Gate names could leak external plugin terminology. Mitigation: use AgentSpec lifecycle stage names.
- Enabled gates could duplicate existing lifecycle warnings. Mitigation: make them opt-in and include gate-specific repair guidance.

Open questions:
- Should a later phase add adapter-authored evidence records under a stable `agent/evidence/` schema?
- Should lifecycle gates eventually map to repo maturity profiles?
- Should shell hooks remain separate from skill gates or become one optional adapter surface?
