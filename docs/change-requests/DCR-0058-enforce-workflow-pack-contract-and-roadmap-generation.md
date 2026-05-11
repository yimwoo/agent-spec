# DCR-0058: Enforce workflow-pack contract and roadmap generation

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-10 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-10 |
| Confidence | medium |

## Summary

AgentSpec should enforce the rule that implementation work is represented by a
task context pack even when work starts in an external HOTL workflow. Drift,
status, and task creation should all recognize repo-local HOTL workflow files
and state files that have no referencing context pack.

AgentSpec should also generate a canonical roadmap projection from existing
handoff, task ledger, and traceability artifacts so status is not maintained by
hand.

## Motivation

The current control plane can report "no ready task context pack" while useful
work exists in external workflow files. That bypasses `R-095` and makes the
project look idle even though there is untracked implementation work.

The immediate dogfood gap is orphan workflows such as `docs/**/plans/**workflow.md`
or `.hotl/state/**.json` that are not cited by any task pack.

## Proposed Change

- Add a dependency-free workflow scanner/parser for HOTL workflow Markdown and
  JSON state files.
- Make `aspec drift` report orphan workflow/state artifacts with enough context
  to backfill a task pack.
- Add `aspec task create --from-workflow <file>` to scaffold a task context pack
  from an existing workflow, including title, workflow path, allowed paths, and
  verification commands.
- Include workflow warnings in `aspec status --json`, human status output,
  `aspec task next`, and next-action guidance when no ready pack exists.
- Add `aspec roadmap` and `aspec roadmap --check` for `docs/ROADMAP.md`.
- Update context-pack templates and plugin skills so the contract is visible
  outside this repository.

## Impact Assessment

New requirement:

- `R-193`: AgentSpec enforces workflow-pack coverage and generated roadmap status.

Likely affected artifacts:

- `agentspec/workflow.py`
- `agentspec/roadmap.py`
- `agentspec/drift.py`
- `agentspec/task.py`
- `agentspec/status.py`
- `agentspec/cli.py`
- `agentspec/init.py`
- `agentspec-codex-plugin/skills/**/SKILL.md`
- `agentspec-claude-plugin/skills/**/SKILL.md`
- `tests/test_workflow_contract.py`
- `tests/test_task_queue.py`
- `tests/test_status_cli.py`
- `tests/test_cli_workflow.py`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for this slice. It tightens the existing local-first task
context pack contract and keeps plugin skills as thin adapters over core CLI
behavior.

## Acceptance Criteria

- `aspec drift` reports orphan HOTL workflow Markdown and HOTL state files that
  are not referenced by a task context pack.
- `aspec task create --from-workflow <file>` creates a context pack with
  workflow metadata, allowed paths, verification commands, and standard
  verification support scope.
- `aspec status --json` and human `aspec status` surface in-flight workflow
  warnings when no task pack references the workflow/state artifact.
- `aspec task next` prints a workflow-pack warning when no ready task pack is
  available.
- Fresh projects include an `agent/context-packs/_TEMPLATE.md` hand-authoring
  template with Stream, Milestone, Slice, Branch, and Workflow fields.
- `aspec roadmap` writes `docs/ROADMAP.md` from handoff, task ledger, and
  traceability artifacts, and `aspec roadmap --check` detects stale output.
- Codex and Claude plugin skills mention the workflow backfill, status warning,
  roadmap, and write-back checks.
