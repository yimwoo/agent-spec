---
name: outcome-audit
description: Audit AgentSpec product outcome readiness through the core CLI, including workflow gates, blockers, evidence, and next actions.
---

# Outcome Audit

Call this skill as `aspec:outcome-audit`.

Use this skill when a user asks whether a project is actually ready for a
production workflow, E2E journey, release, or enterprise milestone.

## Commands

```bash
aspec outcome --json
aspec status --json
aspec quality --json
```

Report outcome readiness separately from task counts. A completed task ledger
does not prove production E2E readiness unless the relevant outcome gates are
ready and backed by evidence.

Boundary: this plugin does not invent product readiness. If `agent/outcomes.yml`
is missing, empty, or blocked, report that and recommend defining or clearing
the outcome gates.
