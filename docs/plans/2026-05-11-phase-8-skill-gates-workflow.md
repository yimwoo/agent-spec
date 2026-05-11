---
intent: Add opt-in lifecycle skill gate projections without adding a separate skill runtime state store.
success_criteria:
  - Runtime config includes disabled-by-default lifecycle skill gate defaults.
  - Status JSON includes lifecycle.skill_gates for disabled and enabled configs.
  - Enabled required gates emit repairable lifecycle findings when required evidence is missing.
  - Strict lifecycle mode promotes required skill gate findings to blocking.
  - Skill gates do not create .agentspec/hooks, agent/evidence, or another lifecycle state directory.
  - Phase 8 has DCR, requirement, task pack, design doc, plan doc, review evidence, and worktree branch artifacts.
risk_level: medium
auto_approve: true
branch: codex/phase8-skill-gates
worktree: host
allowed_paths:
  - docs/change-requests/DCR-0067-add-lifecycle-skill-gates.md
  - docs/traceability/requirements.yml
  - docs/designs/2026-05-11-phase-8-skill-gates-design.md
  - docs/plans/2026-05-11-phase-8-skill-gates-workflow.md
  - agent/context-packs/T-098-add-lifecycle-skill-gate-projection.md
  - agent/runs/*/state.yml
  - agentspec/config.py
  - agentspec/writeback.py
  - agentspec/status.py
  - tests/test_lifecycle_skill_gates.py
  - tests/test_lifecycle_enforcement.py
  - tests/test_config_profiles.py
  - tests/test_status_cli.py
  - docs/ROADMAP.md
  - reports/quality/latest.md
  - reports/quality/latest.yml
verification_commands:
  - python -m json.tool docs/traceability/requirements.yml
  - python -m unittest tests/test_lifecycle_skill_gates.py -v
  - python -m unittest tests/test_lifecycle_skill_gates.py tests/test_lifecycle_enforcement.py tests/test_config_profiles.py tests/test_status_cli.py -v
  - python -m unittest discover -s tests -v
  - git diff --check
  - aspec roadmap --check --json
  - aspec status --json
---

## Steps

- [x] **Step 1: Finalize governance artifacts**
action: Finalize `docs/change-requests/DCR-0067-add-lifecycle-skill-gates.md`, `docs/traceability/requirements.yml`, `docs/designs/2026-05-11-phase-8-skill-gates-design.md`, and this workflow file. Create the AgentSpec task context pack for R-202 from this workflow.
loop: false
verify:
  - type: shell
    command: python -m json.tool docs/traceability/requirements.yml
  - type: artifact
    path: docs/change-requests/DCR-0067-add-lifecycle-skill-gates.md
    assert:
      kind: exists
  - type: artifact
    path: docs/designs/2026-05-11-phase-8-skill-gates-design.md
    assert:
      kind: exists
  - type: artifact
    path: docs/plans/2026-05-11-phase-8-skill-gates-workflow.md
    assert:
      kind: exists

- [x] **Step 2: Add lifecycle skill gate tests**
action: Add `tests/test_lifecycle_skill_gates.py` covering disabled defaults, enabled required gate findings, strict promotion, and evidence projection from existing files. Update `tests/test_config_profiles.py` and `tests/test_status_cli.py` for the new config and status JSON shape.
loop: false
verify: python -m unittest tests/test_lifecycle_skill_gates.py tests/test_config_profiles.py tests/test_status_cli.py -v

- [x] **Step 3: Add config defaults**
action: Update `agentspec/config.py` so default runtime config exposes disabled-by-default `lifecycle.skill_gates` settings and merges nested defaults for existing configs.
loop: until focused config tests pass
max_iterations: 3
verify: python -m unittest tests/test_config_profiles.py -v

- [x] **Step 4: Implement lifecycle skill gate projection**
action: Update `agentspec/writeback.py` so `build_lifecycle_projection` includes a read-only `skill_gates` projection derived from existing design, workflow, verification, review, handoff, and roadmap artifacts. Enabled required gate failures should append lifecycle findings with repair guidance and should become blocking only through existing strict lifecycle enforcement.
loop: until skill gate tests pass
max_iterations: 3
verify: python -m unittest tests/test_lifecycle_skill_gates.py tests/test_lifecycle_enforcement.py -v

- [x] **Step 5: Run related lifecycle verification**
action: Run related lifecycle, config, and status tests to confirm skill gate projection does not regress existing lifecycle warnings, strict enforcement, or human status output.
loop: until related tests pass
max_iterations: 3
verify:
  - type: shell
    command: python -m unittest tests/test_lifecycle_skill_gates.py tests/test_lifecycle_enforcement.py tests/test_config_profiles.py tests/test_status_cli.py -v
  - type: shell
    command: python -m unittest discover -s tests -v

- [x] **Step 6: Complete AgentSpec review and task write-back**
action: Run full verification, record `aspec review code --task T-098`, complete T-098 with the review id, refresh handoff and roadmap, then commit the worktree branch.
loop: false
verify:
  - type: shell
    command: python -m unittest discover -s tests -v
  - type: shell
    command: git diff --check
  - type: shell
    command: aspec roadmap --check --json
  - type: shell
    command: aspec status --json
