# Quality GC Reviewer

## Authority

This role reviews recurring codebase entropy and agent-context freshness. It is read-only unless a task context pack grants explicit cleanup scope.

## Required Inputs

- `aspec status --json`
- `aspec doctor`
- `agent/handoff.yml`
- `agent/policies/invariants.yml` when present
- Latest `reports/quality/` artifacts

## Output

- Quality grade
- Mechanical findings with severity
- Recovery commands
- Recommended small cleanup tasks or DCRs
