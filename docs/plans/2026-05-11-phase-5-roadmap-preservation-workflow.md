---
intent: Add opt-in generated-block roadmap preservation mode while preserving the existing full-file roadmap default.
success_criteria:
  - Full-file roadmap generation remains the default behavior.
  - Generated-block mode preserves manual content before and after the managed block.
  - aspec roadmap --check works deterministically in both modes.
  - Phase 5 has DCR, requirement, task pack, design doc, plan doc, review evidence, and worktree branch artifacts.
risk_level: medium
auto_approve: true
branch: codex/phase5-roadmap-preservation
worktree: host
---

## Steps

- [x] **Step 1: Finalize governance artifacts**
action: Finalize `docs/change-requests/DCR-0064-add-roadmap-preservation-mode.md`, `docs/traceability/requirements.yml`, `docs/designs/2026-05-11-phase-5-roadmap-preservation-design.md`, and this workflow file. Accept DCR-0064 and create the AgentSpec task context pack for R-199.
loop: false
verify:
  - type: shell
    command: python -m json.tool docs/traceability/requirements.yml >/dev/null
  - type: artifact
    path: docs/change-requests/DCR-0064-add-roadmap-preservation-mode.md
    assert:
      kind: exists
  - type: artifact
    path: docs/designs/2026-05-11-phase-5-roadmap-preservation-design.md
    assert:
      kind: exists
  - type: artifact
    path: docs/plans/2026-05-11-phase-5-roadmap-preservation-workflow.md
    assert:
      kind: exists

- [x] **Step 2: Add roadmap preservation tests**
action: Add `tests/test_roadmap_preservation.py` covering full-file default compatibility, generated-block insertion, generated-block replacement, manual content preservation before and after the block, missing-block check failure, and stale-block check failure. Use temp directories and existing AgentSpec JSON/YAML helpers.
loop: false
verify: python -m unittest tests/test_roadmap_preservation.py -v

- [x] **Step 3: Add roadmap config defaults**
action: Update `agentspec/config.py` so merged runtime config includes a roadmap config object. The default mode must preserve current full-file behavior. Invalid roadmap mode handling belongs in the roadmap module, not in unrelated callers.
loop: false
verify: python -m unittest tests/test_config_profiles.py tests/test_roadmap_preservation.py -v

- [x] **Step 4: Implement generated-block roadmap write/check**
action: Update `agentspec/roadmap.py` so `write_roadmap` and `check_roadmap` resolve the active roadmap mode from `.agentspec/config.yml`. In full-file mode, preserve current behavior. In generated-block mode, insert or replace a stable AgentSpec managed block while preserving manual content outside it; `check_roadmap` must compare only the managed block and fail when the block is missing or stale.
loop: until roadmap preservation tests pass
max_iterations: 3
verify: python -m unittest tests/test_roadmap_preservation.py tests/test_workflow_contract.py -v

- [x] **Step 5: Verify CLI and lifecycle compatibility**
action: Run CLI and lifecycle tests that exercise roadmap status, write-back, finish, and project status. Adjust only if the new config-gated mode breaks existing full-file behavior.
loop: until related tests pass
max_iterations: 3
verify: python -m unittest tests/test_cli_workflow.py tests/test_status_cli.py tests/test_writeback.py tests/test_finish_cli.py -v

- [x] **Step 6: Complete AgentSpec review and task write-back**
action: Run full verification, record `aspec review code --task T-095`, complete T-095 with the review id, refresh handoff and roadmap, then commit the worktree branch.
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
