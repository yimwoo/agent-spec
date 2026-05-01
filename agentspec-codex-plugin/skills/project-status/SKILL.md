---
name: project-status
description: Inspect AgentSpec project status, ready tasks, and next recommended action through the core CLI.
---

# Project Status

Use this skill before starting AgentSpec implementation work in a repository.
It reads repo-local AgentSpec artifacts through the CLI and does not modify
source, spec, requirements, or task state.

## Commands

```bash
aspec status --json
aspec task next
```

Use the status recommendation to decide whether to continue a run, inspect a
halted run, or start the next ready context pack.
