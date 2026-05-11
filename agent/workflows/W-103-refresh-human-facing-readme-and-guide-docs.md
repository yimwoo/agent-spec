---
workflow_id: W-103
display_name: Execution Plan
task_pack: agent/context-packs/T-103-refresh-human-facing-readme-and-guide-docs.md
status: active
current_stage: implementation
stream: unassigned
milestone: unassigned
slice: unassigned
branch: unassigned
created_at: 2026-05-11T06:10:42Z
updated_at: 2026-05-11T06:10:42Z
allowed_paths:
  - README.md
  - docs/GETTING_STARTED.md
  - docs/designs/README.md
  - agent/context-packs/T-103-refresh-human-facing-readme-and-guide-docs.md
  - agent/handoff.yml
  - agent/reviews/*.yml
  - agent/task-ledger.yml
  - agent/workflows/W-103-refresh-human-facing-readme-and-guide-docs.md
  - docs/ROADMAP.md
  - docs/change-requests/DCR-0072-refresh-human-facing-readme-and-guide-docs.md
  - docs/traceability/requirements.yml
  - reports/quality/latest.md
  - reports/quality/latest.yml
verification_commands:
  - python -m json.tool docs/traceability/requirements.yml >/dev/null
  - git diff --check
  - PYTHONPATH=$PWD aspec maturity status
  - PYTHONPATH=$PWD aspec status --json
  - PYTHONPATH=$PWD aspec roadmap
  - PYTHONPATH=$PWD aspec roadmap --check --json
required_gates:
  - context
  - path
  - verification
  - review
  - writeback
---

# Workflow W-103: Refresh human-facing README and guide docs

## Linked Task Pack

`agent/context-packs/T-103-refresh-human-facing-readme-and-guide-docs.md`

## Objective

Refresh human-facing README and guide docs

## Plan

1. Confirm the task context, requirements, and allowed paths.
2. Rewrite `README.md` as a concise project front door.
3. Add `docs/GETTING_STARTED.md` for the human operating workflow.
4. Add `docs/designs/README.md` as the documentation/source-of-truth index.
5. Run verification and record the result.
6. Complete review and write-back evidence.

## Implementation Loop

### Iteration 1

- Goal: Implement the first scoped change.
- Status: in_progress
- Notes: README and guide/index docs are being refreshed for `R-207`.

## Verification Plan

- `python -m json.tool docs/traceability/requirements.yml >/dev/null`
- `git diff --check`
- `PYTHONPATH=$PWD aspec maturity status`
- `PYTHONPATH=$PWD aspec status --json`
- `PYTHONPATH=$PWD aspec roadmap`
- `PYTHONPATH=$PWD aspec roadmap --check --json`

## Review Checklist

- [ ] Path scope respected
- [ ] Verification evidence recorded
- [ ] Review evidence recorded
- [ ] Handoff and roadmap write-back complete

## Completion Checklist

- [ ] `agent/handoff.yml` updated
- [ ] `agent/task-ledger.yml` updated
- [ ] `docs/ROADMAP.md` regenerated
- [ ] Final summary written
