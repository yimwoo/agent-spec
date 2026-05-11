---
intent: Add opt-in strict lifecycle enforcement while keeping warn mode as the default.
success_criteria:
  - Warn mode remains the default behavior.
  - lifecycle.enforcement strict mode reports blocking lifecycle findings for strict-eligible drift.
  - Strict blockers include repair guidance.
  - aspec finish blocks strict findings before state mutation.
  - Existing finish.enforcement strict behavior remains compatible.
  - Phase 6 has DCR, requirement, task pack, design doc, plan doc, review evidence, and worktree branch artifacts.
risk_level: medium
auto_approve: true
branch: codex/phase6-strict-lifecycle-enforcement
worktree: host
---

## Steps

- [x] **Step 1: Finalize governance artifacts**
action: Finalize `docs/change-requests/DCR-0065-add-strict-lifecycle-enforcement.md`, `docs/traceability/requirements.yml`, `docs/designs/2026-05-11-phase-6-strict-lifecycle-enforcement-design.md`, and this workflow file. Accept DCR-0065 and create the AgentSpec task context pack for R-200.
loop: false
verify:
  - type: shell
    command: python -m json.tool docs/traceability/requirements.yml >/dev/null
  - type: artifact
    path: docs/change-requests/DCR-0065-add-strict-lifecycle-enforcement.md
    assert:
      kind: exists
  - type: artifact
    path: docs/designs/2026-05-11-phase-6-strict-lifecycle-enforcement-design.md
    assert:
      kind: exists
  - type: artifact
    path: docs/plans/2026-05-11-phase-6-strict-lifecycle-enforcement-workflow.md
    assert:
      kind: exists

- [x] **Step 2: Add strict lifecycle tests**
action: Add `tests/test_lifecycle_enforcement.py` covering warn-mode compatibility, strict lifecycle blockers for review, verification, roadmap, orphan workflow, broken workflow links, and repair guidance.
loop: false
verify: python -m unittest tests/test_lifecycle_enforcement.py -v

- [x] **Step 3: Add lifecycle config defaults**
action: Update `agentspec/config.py` and `tests/test_config_profiles.py` so merged runtime config includes `lifecycle.enforcement` with warn mode as the default.
loop: false
verify: python -m unittest tests/test_config_profiles.py tests/test_lifecycle_enforcement.py -v

- [x] **Step 4: Implement strict lifecycle projection**
action: Update `agentspec/writeback.py` so `build_lifecycle_projection` resolves lifecycle enforcement, reports blocking counts in strict mode, and adds repair guidance to strict-eligible findings.
loop: until strict lifecycle tests pass
max_iterations: 3
verify: python -m unittest tests/test_lifecycle_enforcement.py tests/test_status_cli.py -v

- [x] **Step 5: Implement strict finish integration**
action: Update finish enforcement resolution and finish projection so `lifecycle.enforcement: strict` blocks strict-eligible findings before state mutation while preserving `finish.enforcement: strict` compatibility.
loop: until finish strict tests pass
max_iterations: 3
verify: python -m unittest tests/test_finish_cli.py tests/test_lifecycle_enforcement.py tests/test_writeback.py -v

- [x] **Step 6: Complete AgentSpec review and task write-back**
action: Run full verification, record `aspec review code --task T-096`, complete T-096 with the review id, refresh handoff and roadmap, then commit the worktree branch.
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
