---
name: project-status
description: Inspect AgentSpec status for a new or existing repo, including readiness, ready tasks, active runs, and the next CLI-backed action.
---

# Project Status

Call this skill as `aspec:project-status`.

Use this skill before starting or continuing AgentSpec work in a repository. It
reads repo-local AgentSpec artifacts through the CLI and does not modify source,
spec, requirements, or task state.

## Commands

```bash
aspec status --json
aspec task next
```

Use the status recommendation to decide whether to continue a run, inspect a
halted run, start the next ready context pack, or backfill an in-flight workflow
with `aspec task create --from-workflow <file>`.

For implementation work, the expected order is task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
Claim or verify an active owner/patcher session lease before implementation execution.

## Human-Facing Output

For Codex or Claude Code responses, present the status main point and next
action in plain language. Keep raw `aspec ...` commands internal unless the
user asks for command-level evidence or wants to run the CLI directly.
