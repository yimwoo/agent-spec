---
design_type: phase
created_at: 2026-05-11
parent_design: docs/source/src-0003-lifecycle-engine-hardening-design.md
originating_dcr: DCR-0065
requirement: R-200
branch: codex/phase6-strict-lifecycle-enforcement
worktree: /Users/yimwu/Documents/workspace/Apps/agent-spec-engine-phase6-strict-lifecycle-enforcement
---

# Phase 6: Strict Lifecycle Enforcement

## Intent Contract

intent: Add opt-in strict lifecycle enforcement so AgentSpec can distinguish advisory lifecycle drift from blocking delivery contract failures.

constraints:
- Warn mode remains the default for existing and newly initialized repos.
- Existing `finish.enforcement` strict behavior remains compatible.
- Strict mode uses existing AgentSpec lifecycle, review, verification, workflow, and roadmap evidence.
- This phase does not add git hooks, branch policy enforcement, human-only review policy, or a new evidence store.
- Handoff drift remains warning-only because finish/write-back can regenerate it during normal completion.

success_criteria:
- Runtime config includes a lifecycle enforcement object that defaults to warn mode.
- `lifecycle.enforcement: strict` makes lifecycle projection report blocking findings for strict-eligible drift.
- Strict-eligible lifecycle findings include repair guidance.
- `aspec finish` reads `lifecycle.enforcement: strict` and blocks strict findings before completion state is written.
- Existing `finish.enforcement: strict` behavior still works.
- Tests cover warn-mode compatibility, strict lifecycle blockers, strict finish blockers, repair guidance, and config defaults.

risk_level: medium

## Verification Contract

verify_steps:
- run focused strict enforcement tests: `python -m unittest tests/test_lifecycle_enforcement.py tests/test_finish_cli.py -v`
- run config/default tests: `python -m unittest tests/test_config_profiles.py tests/test_lifecycle_enforcement.py -v`
- run related lifecycle tests: `python -m unittest tests/test_status_cli.py tests/test_writeback.py tests/test_finish_cli.py -v`
- run full suite: `python -m unittest discover -s tests -v`
- check formatting: `git diff --check`
- confirm AgentSpec status: `aspec status --json`
- confirm roadmap current: `aspec roadmap --check --json`

## Governance Contract

approval_gates:
- Phase design and executable plan exist before implementation.
- AgentSpec task pack defines allowed paths before implementation.
- Code review evidence is recorded with `aspec review code` before task completion.
- `aspec task complete` links the ready review evidence.

rollback:
- Revert the Phase 6 commit from branch `codex/phase6-strict-lifecycle-enforcement`.
- Because strict mode is opt-in, repos can also return to warn behavior by removing or changing `lifecycle.enforcement`.

ownership: AgentSpec maintainer and current code agent.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| Lifecycle config | Add `lifecycle.enforcement` default and strict value | Replace maturity enforcement or require strict by default |
| Lifecycle projection | Promote strict-eligible warnings to blocking findings in strict mode | Add new lifecycle state storage |
| Finish | Block strict findings before state mutation | Add separate `aspec verify-work` command |
| Repair guidance | Add repair commands for blocking findings | Add auto-fix or `drift --fix` |
| Workflow policy | Treat orphan and broken workflow links as strict blockers | Require every run to have a workflow |
| Handoff | Keep stale handoff warning-only | Block finish solely because handoff can be regenerated |

## Decisions

| # | Decision | Choice | Rejected alternatives |
|---|---|---|---|
| 1 | Default enforcement | Warn mode remains default | Make strict default for all repos |
| 2 | Config surface | Prefer `lifecycle.enforcement` and preserve `finish.enforcement` override compatibility | Keep strict mode only under `finish.enforcement` |
| 3 | Blocking set | Workflow, review, verification, and roadmap drift can block strict mode | Block every lifecycle warning, including stale handoff |
| 4 | Repair model | Emit explicit repair guidance on strict blockers | Add automatic fix commands in this phase |
| 5 | Finish ordering | Strict blockers fail before completion state is written | Complete first and report strict failures afterward |
| 6 | Review policy | Accept existing ready and ready-with-warnings verdicts | Require human-only review evidence now |

## Surface

`agentspec/config.py` should define default lifecycle config and merge it for existing configs. The expected default is warning enforcement so older repos retain current behavior.

`agentspec/writeback.py` remains the lifecycle projection and finish orchestration authority. It should resolve lifecycle enforcement once, mark strict-eligible lifecycle findings as blocking when strict mode is enabled, and keep repair guidance near the findings that need it.

`agentspec/status.py` should continue consuming the same lifecycle projection shape. Any display changes should be minimal and preserve existing status output for warn mode.

`tests/test_lifecycle_enforcement.py` should cover strict lifecycle status, warn-mode compatibility, and repair guidance. Existing finish and config tests should be extended only where they prove public behavior.

## Risks & Open Questions

Risks:
- Strict mode can become too noisy if every warning blocks. Mitigation: only promote workflow, review, verification, and roadmap findings in this phase.
- Existing finish strict config could be broken by moving to lifecycle config. Mitigation: preserve `finish.enforcement` as an override-compatible surface.
- Roadmap strictness can block completion before a project runs `aspec roadmap`. Mitigation: every strict roadmap blocker includes the explicit repair command.

Open questions:
- Should strict mode eventually map from maturity enforcement?
- Should projects be able to configure which finding types block?
- Should stale handoff become blocking after finish/write-back ordering is further hardened?
