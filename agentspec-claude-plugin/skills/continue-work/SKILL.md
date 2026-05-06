---
name: continue-work
description: Continue AgentSpec work in an existing repository by inspecting status, selecting the next task, and running or resuming the CLI-backed AgentSpec loop. Use when the user asks to continue, resume, or pick up AgentSpec work.
---

# Continue Work

Call this skill as `/aspec:continue-work`.

Use this workflow when the user wants the next safe action in a repository that
already has AgentSpec artifacts.

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

5. Verify the changed area and complete the task only after tests pass and the
   required review evidence is recorded.

If no ready task exists, inspect DCRs, open questions, and requirements before
creating new work. Do not create implementation scope without a requirement or
DCR-backed task.
