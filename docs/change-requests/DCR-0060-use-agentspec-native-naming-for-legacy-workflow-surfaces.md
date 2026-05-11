# DCR-0060: Use AgentSpec-native naming for legacy workflow surfaces

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

AgentSpec should remove HOTL-specific wording from user-facing workflow and
drift surfaces while preserving the existing ability to detect and backfill
legacy workflow and state artifacts.

This is the first implementation slice from the accepted HOTL-integration
design. It keeps the durable `workflow` contract and the
`aspec task create --from-workflow` repair command, but describes legacy inputs
as AgentSpec workflow or execution-plan artifacts instead of exposing HOTL as a
public product concept.

## Motivation

`SRC-0005` has been accepted as the current design source for integrating HOTL
capabilities without HOTL naming. Existing workflow-pack functionality from
`R-193` is intentionally useful, but several human-facing strings still say
"HOTL workflow" or "HOTL workflow artifacts."

The immediate gap is terminology drift: AgentSpec can already scan legacy
workflow inputs, but status, drift, CLI help, and task guidance should align
with the design's AgentSpec-native vocabulary before additional lifecycle
commands are introduced.

## Proposed Change

- Update human status summaries and task-next workflow warnings to use
  AgentSpec-native wording such as "workflow artifacts" or "legacy execution
  plan" instead of "HOTL workflow artifacts."
- Update `aspec drift` report wording for loaded workflow/state artifacts.
- Update CLI help for `--from-workflow` so it describes backfilling from a
  workflow or state file without naming HOTL.
- Keep the existing command name `--from-workflow`, workflow contract schema,
  and legacy `.hotl/state/**/*.json` read support unchanged for compatibility.
- Update focused tests that assert the affected user-facing wording.

## Impact Assessment

New requirement:

- `R-195`: AgentSpec uses native naming for legacy workflow surfaces.

Scope interaction with existing work:

- `R-193` / `T-088` introduced workflow-pack detection and backfill. This DCR
  narrows the public wording on that surface; it does not change the scanner,
  backfill command, or workflow-pack contract.
- `R-194` / `T-089` exposes lifecycle projection and write-back readiness. This
  DCR only revises terminology used by existing workflow/status/drift surfaces.
- `T-090` backfilled the historical AgentSpec MVP workflow. This DCR preserves
  that context-pack linkage and does not create another migration task.

Likely affected artifacts:

- `agentspec/workflow.py`
- `agentspec/drift.py`
- `agentspec/cli.py`
- `tests/test_workflow_contract.py`
- `tests/test_status_cli.py`
- `tests/test_task_queue.py`
- `docs/change-requests/DCR-0060-use-agentspec-native-naming-for-legacy-workflow-surfaces.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for this slice. The change is a terminology hardening pass
over accepted workflow-pack behavior and keeps compatibility with existing
legacy input scanning.

## Acceptance Criteria

- Human `aspec status` and workflow summary output avoid HOTL-specific public
  wording for workflow artifacts.
- `aspec drift` describes loaded workflow/state artifacts without HOTL-specific
  public wording.
- `aspec task create --help` describes `--from-workflow` without HOTL-specific
  public wording.
- `aspec task create --from-workflow <file>` remains the supported repair
  command.
- Existing legacy `.hotl/state/**/*.json` detection remains supported.
- Tests cover the revised user-facing wording and compatibility behavior.
