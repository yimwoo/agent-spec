# DCR-0061: Add AgentSpec-native workflow creation and linkage

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

AgentSpec should add the first native workflow authoring path for the accepted
HOTL-integration design: create or link `agent/workflows/W-*.md` artifacts from
task context packs, with bidirectional task/workflow references and
AgentSpec-native terminology.

This DCR intentionally keeps the durable term `workflow` while allowing
"execution plan" as user-facing wording. It does not introduce a separate HOTL
runtime, `.hotl/` output, or a parallel planning state machine.

## Motivation

`R-193` and `R-195` established workflow-pack detection, legacy backfill, and
AgentSpec-native public wording. AgentSpec can now detect native workflow files
and broken task/workflow links, but users still lack a first-class way to create
or link a native `agent/workflows/` artifact from a task pack.

The accepted design recommends `agent/workflows/` for new planning artifacts and
reserves future `aspec plan` behavior for DCR-backed work. This DCR turns that
recommendation into the next focused implementation slice.

## Proposed Change

- Add a native workflow creation/linking command surface, preferably
  `aspec plan <task>` with an implementation helper in `agentspec.workflow`.
- Create `agent/workflows/W-*.md` files with front matter that records
  `workflow_id`, `task_pack`, status, timestamps, relevant task metadata,
  allowed paths, and verification commands.
- Update the linked task context pack `Workflow:` field so the task points back
  to the generated workflow.
- Preserve existing scanner, drift, and `aspec task create --from-workflow`
  behavior for legacy inputs.
- Refuse or clearly report broken links when an existing task/workflow
  relationship conflicts with the requested plan operation.
- Use AgentSpec-native wording in generated files, CLI help, status output, and
  tests; no new generated artifact should contain HOTL naming.

## Impact Assessment

New requirement:

- `R-196`: AgentSpec creates and links native workflow artifacts.

Scope interaction with existing work:

- `R-193` / `T-088` already scans workflows, reports coverage, and backfills
  context packs from existing workflow files. This DCR adds the missing native
  authoring/linking path.
- `R-194` / `T-089` reads workflow/task link state for lifecycle projection.
  This DCR should make that projection cleaner by producing valid
  bidirectional links.
- `R-195` / `T-091` removes HOTL wording from public workflow surfaces. This DCR
  must preserve that naming direction in newly generated artifacts and help
  text.
- `T-090` backfilled the historical workflow and should remain unchanged; this
  DCR targets new native workflow artifacts.

Likely affected artifacts:

- `agentspec/workflow.py`
- `agentspec/task.py`
- `agentspec/cli.py`
- `agentspec/init.py`
- `tests/test_workflow_contract.py`
- `tests/test_task_queue.py`
- `tests/test_cli_workflow.py`
- `docs/change-requests/DCR-0061-add-agentspec-native-workflow-creation-and-linkage.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for this slice. The accepted design already recommends
native workflow artifacts under `agent/workflows/`; this DCR only adds a
governed authoring path over the existing workflow contract.

## Acceptance Criteria

- `aspec plan <task>` or an equivalent AgentSpec-native command creates a
  workflow/execution-plan artifact under `agent/workflows/`.
- The generated workflow front matter links back to the selected task context
  pack.
- The selected task context pack `Workflow:` field links to the generated
  workflow.
- Generated workflow content includes task metadata, allowed paths, and
  verification commands when available.
- `aspec status --json` and workflow coverage report the generated task/workflow
  pair without orphan or broken-link warnings.
- Existing `aspec task create --from-workflow <file>` behavior remains
  backward compatible for legacy and native workflow files.
- No new generated file, CLI help, or human-facing status text uses HOTL naming.
- Tests cover workflow creation, bidirectional link validation, conflict
  handling, status integration, and backfill compatibility.
