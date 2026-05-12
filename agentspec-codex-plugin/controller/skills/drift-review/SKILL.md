---
name: drift-review
description: Run AgentSpec drift review from the repository root and inspect the generated report.
---

# Drift Review

Controller procedure id: `drift-review`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill to compare current code changes with AgentSpec requirements,
ADRs, task context packs, and HOTL workflow coverage.

## Command

```bash
aspec drift
```

Report findings with requirement IDs and source section IDs where available.
If the report lists orphan workflows, backfill them with
`aspec task create --from-workflow <file>` before implementation work continues.
