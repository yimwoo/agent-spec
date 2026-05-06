---
name: project-status
description: Inspect AgentSpec status in an existing repository through the core CLI. Use when the user asks for AgentSpec status, readiness, ready tasks, active runs, handoff state, or next action.
---

# Project Status

Call this skill as `/aspec:project-status`.

Run read-only status commands from the target repository root:

```bash
aspec status --json
aspec task next
```

Use the status recommendation to decide whether to continue a run, inspect a
halted run, or start the next ready context pack. Do not mutate DCR,
requirement, task, source, or run state from this skill.
