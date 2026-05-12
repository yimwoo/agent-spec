---
name: start-branch
description: Start AgentSpec-governed branch or session work by claiming a task, branch, worktree, and allowed-path lease.
---

# Start Branch

Call this skill as `/aspec:start-branch`.

Use this skill when beginning implementation work that should be tied to a task
context pack, branch, worktree, or explicit owner lease.

## Workflow

1. Inspect lifecycle, status, and the active or next task:

```bash
aspec lifecycle --json
aspec status --json
aspec task next
```

2. Inspect existing leases, then create a dedicated git branch and, for
   concurrent write work, a dedicated git worktree. Do not reuse an active
   owner/patcher branch or worktree for new write-mode work; resume the existing
   session, use `--mode observer` for read-only inspection, or pass
   `--allow-shared` only when sharing is intentional. Then record the AgentSpec
   session lease:

```bash
aspec session list --json
git worktree add ../<worktree-name> -b <branch>
aspec session start --task <T-id> --owner <owner> --branch <branch> --worktree <path>
aspec session list --json
```

3. Open the selected context pack and confirm allowed paths before editing.

Boundary: current AgentSpec records and enforces session leases, but branch and
worktree creation is still performed by the host git tool. A future native
branch-start command can combine both steps without adding plugin-owned state.
