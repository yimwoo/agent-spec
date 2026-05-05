# DCR-0041: Project invariant checks in doctor

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Add a small repo-local invariant check surface to `aspec doctor`.

Projects should be able to define simple mechanical rules, such as required
paths and forbidden path patterns, that doctor can evaluate and report. This
turns agent-facing architecture and workflow expectations into durable checks
instead of relying only on prose instructions.

## Motivation

The Harness Engineering review emphasized that agents work better when
important repository expectations are encoded as tools and linters, not only as
documentation. AgentSpec already has a hard-coded policy engine for run safety,
but project-specific invariants remain mostly free-form guidance in generated
agent instructions, context packs, or human memory.

This leaves recurring correctness and maintainability rules hard for agents to
discover and easy for them to violate. A lightweight invariant file gives
projects a practical path to encode local rules without introducing a hosted
policy service or broad organization policy packs.

## Proposed Change

- Add optional `agent/policies/invariants.yml` support using the existing
  JSON-compatible artifact format.
- Support two MVP invariant kinds:
  - `required_path`: fail when a configured path does not exist.
  - `forbidden_path`: fail when any repository file matches a configured
    pattern.
- Include invariant results in `aspec doctor`'s structured `repo-scan.yml` and
  markdown `agent-readiness.md`.
- Treat missing invariant config as `not_configured`, not an error.
- Keep invariant failures non-blocking in this slice; CI can choose to enforce
  the doctor report later.

## Impact Assessment

Affected existing requirements:

- `R-034`: the verifier must use explicit criteria.
- `R-036`: organization-specific rules should be represented as versioned
  policy packs, not hardcoded prompts.
- `R-007`: the CLI remains usable locally and in CI.
- `R-035`: dogfooding improves AgentSpec's own repository and agent workflow.

Likely new requirement:

- `R-176`: `aspec doctor` evaluates repo-local project invariants.

Likely affected artifacts:

- `agentspec/policy.py`
- `agentspec/doctor.py`
- `tests/test_cli_workflow.py`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-071-project-invariant-checks-in-doctor.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a small local validation surface. Future DCRs can
add richer invariant kinds, severity thresholds, CI exit-code enforcement, and
organization-level policy pack distribution.

## Acceptance Criteria

- With no `agent/policies/invariants.yml`, `aspec doctor` reports invariant
  status as `not_configured`.
- `required_path` invariants pass when the path exists and fail when it is
  missing.
- `forbidden_path` invariants pass when no files match and fail when files
  match the configured pattern.
- `repo-scan.yml` records invariant results with id, kind, status, message,
  and severity.
- `agent-readiness.md` includes a Project Invariants section.
- Tests cover missing config, passing invariants, and failing invariants.
