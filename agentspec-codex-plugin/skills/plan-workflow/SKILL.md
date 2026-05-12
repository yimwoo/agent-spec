---
name: plan-workflow
description: Plan AgentSpec implementation work from approved requirements and product outcome gates before code changes begin.
---

# Plan Workflow

Call this skill as `aspec:plan-workflow`.

Use this skill before substantial feature, refactor, production-readiness, or
E2E workflow work.

## Workflow

1. Inspect project and outcome state:

```bash
aspec status --json
aspec outcome --json
```

2. Select an accepted requirement or DCR-backed task:

```bash
aspec task next
aspec task create --requirement <R-id> --type implementation --title "<title>"
```

3. Open the task context pack and verify allowed paths, source sections,
   acceptance criteria, outcome gates, risk, and required evidence before
   editing.

For implementation work, the expected order is task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
After planning, claim or verify an active owner/patcher session lease before implementation execution.

Boundary: this skill plans from AgentSpec artifacts. It does not promote source
snapshots, bypass readiness gates, or expand write scope outside the context
pack.
