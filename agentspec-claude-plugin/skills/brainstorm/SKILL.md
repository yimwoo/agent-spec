---
name: brainstorm
description: Frame ambiguous AgentSpec work as source-backed DCRs, discovery notes, or design inputs before implementation starts.
---

# Brainstorm

Call this skill as `/aspec:brainstorm`.

Use this skill when a user has an idea, concern, failure pattern, or broad
product direction that is not yet ready for implementation.

## Workflow

1. Inspect the lifecycle contract and current project state:

```bash
aspec lifecycle --json
aspec status --json
```

2. Convert the intent into the lightest durable AgentSpec artifact that fits:

```bash
aspec dcr create --title "<idea>" --classification spike
aspec dcr create --title "<change>" --classification implement-now
aspec dogfood record --title "<observation>" --slug "<short-slug>"
```

3. Summarize the problem, candidate scope, likely affected requirements, and
   what still needs design or source intake.

Boundary: this skill does not create implementation scope by itself. AgentSpec
owns the DCR, source, task, review, verification, roadmap, and handoff state.
The Claude Code adapter only helps capture and explain the next CLI-backed
action.
