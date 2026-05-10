# DCR-0057: Add progressive maturity profiles

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

Add an AgentSpec maturity profile model so repositories can adopt the control
plane progressively instead of choosing between loose Markdown-only workflows
and strict enterprise gates. The model defines three levels:

- `lightweight`
- `governed-implementation`
- `production-readiness`

Each level reports required artifacts, missing checks, score, and blocking
state. Early adoption should warn and guide; stricter projects can opt into
blocking behavior once teams are ready.

## Motivation

Large teams need code agents to work safely for long sessions, but too much
ceremony at the start discourages adoption. Smaller or plugin-averse teams may
want only `AGENTS.md`, status, basic requirements, and a doc registry. Enterprise
teams need task packs, allowed paths, session leases, review/test evidence, and
drift checks. Production claims need outcome gates, release evidence, rollback,
security review, audit, and CI/E2E evidence.

AgentSpec should make these levels explicit, measurable, and visible without
forcing every repository to start at maximum strictness.

## Proposed Change

- Add `agent/maturity.yml` as the repo-local maturity profile artifact.
- Add `agentspec/maturity.py` to load defaults and compute maturity status.
- Add `aspec maturity status --json`.
- Add `aspec maturity check --json`.
- Add `aspec maturity set <level> --enforcement warn|block --json`.
- Add `--maturity` and `--maturity-enforcement` to `aspec init`.
- Add maturity status to `aspec status --json` and human status output.
- Seed fresh projects with a lightweight maturity artifact.
- Keep the first slice local-first and dependency-free.

This DCR does not require every profile check to become a hard gate immediately.
Completion and production gate enforcement can be tightened in later DCRs once
teams have adopted the profile artifact.

## Impact Assessment

New requirement:

- `R-192`: AgentSpec supports progressive maturity profiles.

Likely affected artifacts:

- `agentspec/maturity.py`
- `agentspec/cli.py`
- `agentspec/status.py`
- `agentspec/init.py`
- `agent/maturity.yml`
- `tests/test_maturity_cli.py`
- `tests/test_cli_workflow.py`
- `docs/change-requests/DCR-0057-add-progressive-maturity-profiles.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for the first local-state slice. A later ADR may be needed
if maturity profiles become organization-wide policy packs or begin blocking
remote CI/release operations.

## Acceptance Criteria

- Missing `agent/maturity.yml` defaults to a lightweight profile in
  `aspec maturity status --json`.
- Fresh projects include `agent/maturity.yml`.
- `aspec init --maturity governed-implementation` writes the selected profile.
- `aspec maturity set production-readiness --enforcement block --json` updates
  the profile artifact.
- `aspec maturity check --json` reports level, enforcement, score, missing
  checks, warnings, and blocking checks.
- `aspec status --json` includes maturity status.
- Human `aspec status` includes a maturity summary line.
- Tests cover maturity CLI behavior and status/init integration.
