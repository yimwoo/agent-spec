# DCR-0059: Lifecycle projection and write-back verification

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

Implement the first slice from the accepted lifecycle hardening design: expose a
normalized lifecycle projection and write-back readiness checks over existing
AgentSpec state.

This slice must preserve current architecture. It should read from task context
packs, workflows, runs, sessions, review records, the task ledger, handoff, and
roadmap state instead of introducing a second lifecycle state machine.

## Motivation

The revised lifecycle design has been accepted into AgentSpec source state as
`SRC-0003`, but the compiler did not synthesize a new implementation
requirement from it. A DCR-originated requirement is needed so the next work
starts from a task context pack and remains durable across compile runs.

The immediate product gap is that AgentSpec can surface orphan workflows, but it
does not yet expose a cohesive lifecycle projection that also explains
verification, review linkage, handoff, and roadmap write-back readiness.

## Proposed Change

- Add a lifecycle projection helper that normalizes existing AgentSpec artifacts
  into task lifecycle/gate state.
- Surface lifecycle projection and write-back readiness in `aspec status --json`
  without replacing existing status fields.
- Add lifecycle drift/readiness findings for missing review linkage, missing or
  failed verification, stale roadmap, stale handoff, and broken workflow links
  where the existing artifacts provide enough evidence.
- Keep behavior warning-oriented for this slice; strict blocking and
  `aspec finish` remain deferred.

## Impact Assessment

New requirement:

- `R-194`: AgentSpec exposes lifecycle projection and write-back readiness.

Likely affected artifacts:

- `agentspec/status.py`
- `agentspec/workflow.py`
- `agentspec/drift.py`
- `agentspec/roadmap.py`
- `agentspec/task.py`
- `agentspec/handoff.py`
- `agentspec/writeback.py`
- `tests/test_status_cli.py`
- `tests/test_task_queue.py`
- `tests/test_workflow_contract.py`
- `tests/test_cli_workflow.py`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for this slice. The change is a projection and diagnostics
layer over existing repo-local state. Later DCRs can add `aspec finish`, native
workflow creation, strict mode, migration tooling, and skill gates.

## Acceptance Criteria

- `aspec status --json` exposes a lifecycle projection section with task or
  workflow drift, verification readiness, review linkage, handoff readiness, and
  roadmap readiness when evidence is available.
- Human `aspec status` summarizes lifecycle warnings without hiding the existing
  status fields.
- `aspec continue` or `aspec next-action` does not report clean idle when
  lifecycle drift requires repair.
- Broken workflow/task links are reported distinctly from orphan workflows.
- Completed tasks missing required review linkage or verification status are
  reported as lifecycle warnings.
- Stale roadmap or handoff state is reported as lifecycle warning evidence.
- Existing workflow-pack warning behavior and roadmap generation remain
  backward compatible.
- Tests cover lifecycle projection JSON, human status output, continuation
  guidance, and compatibility with existing workflow-pack warnings.
