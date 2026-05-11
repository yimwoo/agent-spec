---
intent: Add explicit idempotent migration tooling for legacy execution artifacts.
success_criteria:
  - Dry-run migration reports scanner-recognized orphan execution artifacts without writes.
  - Write mode creates context packs for orphan legacy execution artifacts.
  - Write mode is idempotent and skips already referenced artifacts.
  - Scoped migration with --from fails without writing for unknown paths.
  - Migration output includes rollback guidance and preserves source workflow content.
  - Phase 7 has DCR, requirement, task pack, design doc, plan doc, review evidence, and worktree branch artifacts.
risk_level: medium
auto_approve: true
branch: codex/phase7-migration-tools
worktree: host
allowed_paths:
  - docs/change-requests/DCR-0066-add-legacy-execution-migration-tools.md
  - docs/traceability/requirements.yml
  - docs/designs/2026-05-11-phase-7-migration-tools-design.md
  - docs/plans/2026-05-11-phase-7-migration-tools-workflow.md
  - agent/context-packs/T-097-add-legacy-execution-migration-tools.md
  - agent/runs/*/state.yml
  - agentspec/cli.py
  - agentspec/migration.py
  - agentspec/task.py
  - agentspec/workflow.py
  - tests/test_migration_cli.py
  - tests/test_workflow_contract.py
  - tests/test_task_queue.py
  - tests/test_status_cli.py
  - tests/test_cli_workflow.py
  - docs/ROADMAP.md
  - reports/quality/latest.md
  - reports/quality/latest.yml
verification_commands:
  - python -m unittest tests/test_migration_cli.py -v
  - python -m unittest tests/test_migration_cli.py tests/test_workflow_contract.py tests/test_task_queue.py -v
  - python -m unittest tests/test_status_cli.py tests/test_cli_workflow.py -v
  - python -m unittest discover -s tests -v
  - git diff --check
  - aspec roadmap --check --json
  - aspec status --json
---

## Steps

- [x] **Step 1: Finalize governance artifacts**
action: Finalize `docs/change-requests/DCR-0066-add-legacy-execution-migration-tools.md`, `docs/traceability/requirements.yml`, `docs/designs/2026-05-11-phase-7-migration-tools-design.md`, and this workflow file. Create the AgentSpec task context pack for R-201 from this workflow.
loop: false
verify:
  - type: shell
    command: python -m json.tool docs/traceability/requirements.yml
  - type: artifact
    path: docs/change-requests/DCR-0066-add-legacy-execution-migration-tools.md
    assert:
      kind: exists
  - type: artifact
    path: docs/designs/2026-05-11-phase-7-migration-tools-design.md
    assert:
      kind: exists
  - type: artifact
    path: docs/plans/2026-05-11-phase-7-migration-tools-workflow.md
    assert:
      kind: exists

- [x] **Step 2: Add migration CLI tests**
action: Add `tests/test_migration_cli.py` covering dry-run no-write behavior, write-mode context-pack creation, idempotent reruns, scoped `--from` failure without writes, JSON output, rollback guidance, and source workflow preservation.
loop: false
verify: python -m unittest tests/test_migration_cli.py -v

- [x] **Step 3: Implement migration planner**
action: Add `agentspec/migration.py` with scanner-backed planning for `legacy-execution`, including dry-run records, scoped path validation, already-referenced skips, and rollback guidance fields.
loop: until migration planner tests pass
max_iterations: 3
verify: python -m unittest tests/test_migration_cli.py tests/test_workflow_contract.py -v

- [x] **Step 4: Wire CLI command**
action: Update `agentspec/cli.py` so `aspec migrate legacy-execution` supports `--from`, `--write`, and `--json`, prints native migration summaries, and returns nonzero for invalid scoped paths before any write.
loop: until migration CLI tests pass
max_iterations: 3
verify: python -m unittest tests/test_migration_cli.py tests/test_task_queue.py -v

- [x] **Step 5: Run related lifecycle verification**
action: Run related workflow, task, status, and CLI tests to confirm migration tooling does not regress existing workflow scanner, backfill, or status behavior.
loop: until related tests pass
max_iterations: 3
verify:
  - type: shell
    command: python -m unittest tests/test_migration_cli.py tests/test_workflow_contract.py tests/test_task_queue.py -v
  - type: shell
    command: python -m unittest tests/test_status_cli.py tests/test_cli_workflow.py -v

- [x] **Step 6: Complete AgentSpec review and task write-back**
action: Run full verification, record `aspec review code --task T-097`, complete T-097 with the review id, refresh handoff and roadmap, then commit the worktree branch.
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
