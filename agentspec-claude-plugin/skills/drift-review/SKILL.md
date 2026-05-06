---
name: drift-review
description: Run AgentSpec drift review from the repository root and inspect the generated report. Use when the user asks whether code, generated context, or requirements have drifted from accepted source.
---

# Drift Review

Call this skill as `/aspec:drift-review`.

Use this skill for read-only design/code drift checks.

## Commands

```bash
aspec drift
aspec status
```

Inspect `reports/drift/latest.md` or the report path printed by the CLI before
summarizing. Drift review does not accept requirements, complete tasks, promote
candidate sources, or edit accepted snapshots.
