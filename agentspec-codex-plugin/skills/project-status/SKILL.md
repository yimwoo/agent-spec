---
name: project-status
description: Inspect AgentSpec status for a new or existing repo, including readiness, ready tasks, active runs, and the next CLI-backed action.
---

# Project Status

Use this skill before starting or continuing AgentSpec work in a repository. It
reads repo-local AgentSpec artifacts through the CLI and does not modify source,
spec, requirements, or task state.

## Commands

```bash
aspec status --json
aspec task next
```

Use the status recommendation to decide whether to continue a run, inspect a
halted run, or start the next ready context pack.
