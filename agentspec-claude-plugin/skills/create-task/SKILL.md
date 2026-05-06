---
name: create-task
description: Create an AgentSpec task context pack for an existing repository from a ready requirement through the core CLI. Use when a requirement needs bounded implementation scope.
---

# Create Task

Call this skill as `/aspec:create-task`.

Use this skill when a requirement is ready for implementation and needs a task
context pack.

## Commands

```bash
aspec task create --requirement <R-id> --type implementation --title "<title>"
aspec task next
```

Open the generated context pack and work only inside its allowed paths. If the
allowed paths are wrong, revise the context pack before implementation rather
than silently expanding scope.
