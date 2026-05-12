---
name: drift-review
description: Run AgentSpec drift review from the repository root and inspect the generated report. Use when the user asks whether code, generated context, or requirements have drifted from accepted source.
---

# Drift Review

Controller procedure id: `drift-review`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill for read-only design/code drift checks, including orphan HOTL
workflow detection.

## Commands

```bash
aspec drift
aspec status
```

Inspect `reports/drift/latest.md` or the report path printed by the CLI before
summarizing. Drift review does not accept requirements, complete tasks, promote
candidate sources, or edit accepted snapshots.

If the report lists orphan workflows, backfill them with
`aspec task create --from-workflow <file>` before implementation work continues.
