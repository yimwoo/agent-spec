---
design_type: phase
created_at: 2026-05-11
parent_design: docs/source/src-0003-lifecycle-engine-hardening-design.md
originating_dcr: DCR-0066
requirement: R-201
branch: codex/phase7-migration-tools
worktree: /Users/yimwu/Documents/workspace/Apps/agent-spec-engine-phase7-migration-tools
---

# Phase 7: Migration Tools

## Intent Contract

intent: Add explicit legacy execution migration tooling so existing workflow-style planning artifacts can be represented by AgentSpec task context packs without overwriting user-authored content.

constraints:
- Migration is dry-run by default and requires `--write` for mutations.
- Migration preserves original workflow and execution-state files exactly.
- Migration reuses the existing AgentSpec workflow scanner and task context pack backfill behavior.
- Migration does not copy legacy workflows into native workflow files in this phase.
- Migration output uses AgentSpec-native wording except where describing legacy inputs.
- Existing `aspec task create --from-workflow` behavior remains compatible.

success_criteria:
- `aspec migrate legacy-execution` reports what would be migrated without writing.
- `aspec migrate legacy-execution --write` backfills task context packs for orphan scanner-recognized legacy execution artifacts.
- Re-running write mode is idempotent and skips already referenced artifacts.
- `--from <path>` scopes the migration and fails without writes for unknown paths.
- Migration output includes rollback guidance for created artifacts.
- Tests prove idempotency and source workflow preservation.

risk_level: medium

## Verification Contract

verify_steps:
- run focused migration tests: `python -m unittest tests/test_migration_cli.py -v`
- run related workflow/task tests: `python -m unittest tests/test_migration_cli.py tests/test_workflow_contract.py tests/test_task_queue.py -v`
- run CLI status coverage: `python -m unittest tests/test_status_cli.py tests/test_cli_workflow.py -v`
- run full suite: `python -m unittest discover -s tests -v`
- check formatting: `git diff --check`
- confirm AgentSpec status: `aspec status --json`
- confirm roadmap current: `aspec roadmap --check --json`

## Governance Contract

approval_gates:
- Phase design and executable plan exist before implementation.
- AgentSpec task pack defines allowed paths before implementation.
- Failing tests are written before implementation.
- Code review evidence is recorded with `aspec review code` before task completion.
- `aspec task complete` links the ready review evidence.

rollback:
- Revert the Phase 7 commit from branch `codex/phase7-migration-tools`.
- For a mistakenly applied migration, remove only the created `agent/context-packs/T-*.md` files reported by the migration command, then rerun `aspec status --json`.
- Because source workflow files are not edited, no workflow-content rollback should be required.

ownership: AgentSpec maintainer and current code agent.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| CLI | Add `aspec migrate legacy-execution` with dry-run, `--write`, `--from`, and `--json` | Rename existing task or workflow commands |
| Planning | Build a migration plan from scanner-recognized workflow artifacts | Scan arbitrary paths outside the current AgentSpec scanner |
| Write mode | Create missing task context packs for orphan legacy artifacts | Auto-complete migration tasks |
| Idempotency | Skip workflows already referenced by context packs | Merge or rewrite existing context packs |
| Safety | Preserve source workflow content and report rollback guidance | Copy workflows into native `agent/workflows/` files |
| Documentation | Add phase DCR, requirement, design, and workflow plan | Rewrite the parent lifecycle hardening design |

## Decisions

| # | Decision | Choice | Rejected alternatives |
|---|---|---|---|
| 1 | Mutation model | Dry-run by default, `--write` required | Create context packs by default |
| 2 | Idempotency key | Existing task-pack references to the workflow path | Filename-only matching or task title matching |
| 3 | Backfill target | Reuse `create_task_context_pack_from_workflow` | Add a parallel migration-specific pack writer |
| 4 | Native workflow copy | Preserve original workflow paths in this phase | Copy every legacy plan into `agent/workflows/` |
| 5 | Scoped input | `--from` must match a scanner-recognized artifact | Accept arbitrary untracked Markdown files |
| 6 | Rollback | Report created paths and removal instructions | Add destructive rollback subcommands |

## Surface

`agentspec/migration.py` should own the migration planning and write application logic. It should return structured payloads suitable for both text and JSON output.

`agentspec/cli.py` should expose `migrate legacy-execution` without adding HOTL-named public commands. Text output should distinguish dry-run from write mode, summarize created/skipped artifacts, and include rollback guidance.

`agentspec/task.py` remains the context-pack writer through `create_task_context_pack_from_workflow`. Any helper needed for idempotency should remain narrowly scoped and compatible with the existing task-create command.

`agentspec/workflow.py` remains the scanner authority. Migration should consume scanner results rather than introducing a second discovery algorithm.

`tests/test_migration_cli.py` should cover dry-run behavior, write behavior, idempotent reruns, `--from` failure, JSON output, rollback guidance, and preservation of source workflow content.

## Risks & Open Questions

Risks:
- A migration command can be mistaken for a content rewrite tool. Mitigation: make dry-run default and explicitly state that source workflows are preserved.
- Idempotency can fail if matching uses titles or filenames instead of task-pack references. Mitigation: rely on existing workflow reference detection.
- Broad arbitrary path support could bypass scanner governance. Mitigation: keep `--from` tied to scanner-recognized artifacts in this phase.

Open questions:
- Should a future explicit flag copy legacy workflows into native `agent/workflows/` files?
- Should migration tasks be auto-marked complete after backfill, or remain visible for human review?
- Should migration produce persistent reports under `reports/migration/` once the report format is stable?
