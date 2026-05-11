---
workflow_id: W-104
display_name: Execution Plan
task_pack: agent/context-packs/T-104-document-prompt-first-code-agent-agentspec-workflow.md
status: active
current_stage: implementation
stream: unassigned
milestone: unassigned
slice: unassigned
branch: unassigned
created_at: 2026-05-11T06:25:01Z
updated_at: 2026-05-11T06:25:01Z
allowed_paths:
  - README.md
  - agentspec-claude-plugin/README.md
  - agentspec-codex-plugin/README.md
  - docs/GETTING_STARTED.md
  - agent/context-packs/T-104-document-prompt-first-code-agent-agentspec-workflow.md
  - agent/handoff.yml
  - agent/reviews/*.yml
  - agent/task-ledger.yml
  - agent/workflows/W-104-document-prompt-first-code-agent-agentspec-workflow.md
  - docs/ROADMAP.md
  - docs/change-requests/DCR-0073-document-prompt-first-code-agent-agentspec-workflow.md
  - docs/traceability/requirements.yml
  - reports/quality/latest.md
  - reports/quality/latest.yml
verification_commands:
  - python -m json.tool docs/traceability/requirements.yml >/dev/null
  - python -m json.tool agent/handoff.yml >/dev/null
  - git diff --check
  - PYTHONPATH=$PWD aspec status
  - PYTHONPATH=$PWD aspec roadmap
  - PYTHONPATH=$PWD aspec roadmap --check --json
required_gates:
  - context
  - path
  - verification
  - review
  - writeback
---

# Workflow W-104: Document prompt-first code-agent AgentSpec workflow

## Linked Task Pack

`agent/context-packs/T-104-document-prompt-first-code-agent-agentspec-workflow.md`

## Objective

Document prompt-first code-agent AgentSpec workflow

## Plan

1. Confirm the task context, requirements, and allowed paths.
2. Update `README.md` to lead with prompt-first code-agent usage.
3. Update `docs/GETTING_STARTED.md` with copyable prompts and evidence expectations.
4. Update Codex and Claude plugin READMEs with installed-plugin prompt usage.
5. Run verification and record the result.
6. Complete review and write-back evidence.

## Implementation Loop

### Iteration 1

- Goal: Implement the first scoped change.
- Status: in_progress
- Notes: Documentation is being updated for prompt-first code-agent workflows (`R-208`).

## Verification Plan

- `python -m json.tool docs/traceability/requirements.yml >/dev/null`
- `python -m json.tool agent/handoff.yml >/dev/null`
- `git diff --check`
- `PYTHONPATH=$PWD aspec status`
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
