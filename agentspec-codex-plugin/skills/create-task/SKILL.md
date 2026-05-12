---
name: create-task
description: Create an AgentSpec task context pack for an existing repo from a ready requirement through the core CLI.
---

# Create Task

Call this skill as `aspec:create-task`.

Use this skill when a requirement is ready for implementation and needs a task
context pack.

## Commands

```bash
aspec task create --requirement <R-id> --type implementation --title "<title>"
aspec task create --from-workflow <docs/.../plans/...workflow.md>
aspec task next
```

Use `--from-workflow` when HOTL work already exists without a task pack. Open
the generated context pack and work only inside its allowed paths.
Do not move from task creation directly to execution; implementation work must
pass through workflow planning and branch/worktree/session setup first.
For implementation work, the expected order is task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
