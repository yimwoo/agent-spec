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
halted run, start the next ready context pack, or backfill an in-flight workflow
with `aspec task create --from-workflow <file>`. Do not mutate DCR,
requirement, task, source, or run state from this skill.

## Human-Facing Output

For Codex or Claude Code responses, present the status main point and next
action in plain language. Keep raw `aspec ...` commands internal unless the
user asks for command-level evidence or wants to run the CLI directly.
