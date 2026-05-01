---
name: continue-work
description: Continue work in an existing AgentSpec repository by reading status, selecting the next task, running or resuming the loop, and respecting task-pack governance.
---

# Continue Work

Call this skill as `aspec:continue-work`.

Use this skill when the user wants to continue work in a repository that already
has AgentSpec artifacts.

## Workflow

1. Inspect status and the next task:

```bash
aspec status --json
aspec task next
```

2. If a task is ready, start or resume the AgentSpec loop:

```bash
aspec run loop
```

3. If a run needs attention, use the recovery command reported by status, such
   as:

```bash
aspec run inspect <run-id>
aspec run prompt <run-id>
```

4. Before editing, open the selected context pack and follow its allowed paths.
   Do not bypass the task context pack.

5. Verify the changed area and complete the task only after tests pass:

```bash
aspec task complete <T-id> --test-status passed
aspec status
```

If no ready task exists, inspect DCRs, open questions, and requirements before
creating new work. Do not create implementation scope without a requirement or
DCR-backed task.
