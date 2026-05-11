# DCR-0066: Add legacy execution migration tools

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

Add Phase 7 migration tooling from the lifecycle hardening design. AgentSpec
should expose an explicit `aspec migrate legacy-execution` command that can
inspect legacy execution plans, report what would be backfilled, and safely
create missing task context packs only when the user opts into writes.

This phase continues the operating-contract discipline used for the lifecycle
hardening phases: phase design, executable plan, AgentSpec task pack, and a
dedicated worktree branch before implementation.

## Motivation

AgentSpec already scans legacy execution plans and can backfill a context pack
from one workflow at a time. Users still need a single migration entrypoint that
is safe to run repeatedly, clear about what it will mutate, and explicit about
rollback.

Migration must not make legacy workflows a second source of truth. It should
preserve original workflow paths, avoid copying or rewriting user-authored
plans, and create AgentSpec governance artifacts only when that action is
unambiguous.

## Proposed Change

- Add `aspec migrate legacy-execution`.
- Make the command dry-run by default and require `--write` for mutations.
- Support `--from <path>` to limit migration to one scanner-recognized legacy
  execution artifact.
- In write mode, create a missing task context pack using the existing workflow
  backfill machinery.
- Skip already referenced workflows so repeated writes are idempotent.
- Report rollback guidance for every created artifact.
- Preserve legacy workflow files exactly as they are.

## Impact Assessment

New requirement:

- `R-201`: AgentSpec provides idempotent legacy execution migration tooling.

Likely affected artifacts:

- `agentspec/cli.py`
- `agentspec/migration.py`
- `agentspec/task.py`
- `agentspec/workflow.py`
- `tests/test_migration_cli.py`
- `tests/test_workflow_contract.py`
- `tests/test_task_queue.py`
- `docs/designs/2026-05-11-phase-7-migration-tools-design.md`
- `docs/plans/2026-05-11-phase-7-migration-tools-workflow.md`
- `docs/change-requests/DCR-0066-add-legacy-execution-migration-tools.md`
- `docs/traceability/requirements.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. The command is additive, reuses existing scanner and
context-pack backfill behavior, and does not change default status or task
queue semantics.

## Acceptance Criteria

- `aspec migrate legacy-execution` reports scanner-recognized orphan execution
  artifacts without mutating files.
- `aspec migrate legacy-execution --write` creates task context packs for
  orphan legacy execution artifacts.
- Re-running write mode does not create duplicate context packs.
- `--from <path>` limits migration to one artifact and fails without writing
  when the path is not scanner-recognized.
- Migration output includes rollback guidance for created artifacts.
- Migration never overwrites or edits source workflow content.
