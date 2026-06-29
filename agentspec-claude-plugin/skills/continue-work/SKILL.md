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

2. If a task is ready, plan it and claim the governed session boundary:

```bash
aspec plan <T-id>
aspec session start --task <T-id> --owner <owner> --branch <branch> --worktree <path>
```

Prefer provider-native execution after preflight: use Claude `/loop` or a
dynamic Claude workflow to execute and iterate on the task directly. Keep the
task pack, allowed paths, verification, review, and finish write-back as the
AgentSpec boundary. Do not bypass those gates because Claude owns the
execution loop.

If provider-native execution is unavailable, use the generic fallback:

```bash
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
```

`aspec run loop` and `aspec run exec` remain compatibility paths during the
transition, not the preferred Claude workflow.

For implementation work, the expected order is task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
Claim or verify an active owner/patcher session lease before implementation execution.
Do not start `aspec run loop`, `aspec run package`, or `aspec run exec` until session preflight is satisfied.
Explicit host-worktree execution is an auditable escape hatch when the workflow or context pack declares it intentionally.

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
