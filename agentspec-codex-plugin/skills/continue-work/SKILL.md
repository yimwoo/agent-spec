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

2. If a task is ready, plan it and claim the governed session boundary:

```bash
aspec plan <T-id>
aspec session start --task <T-id> --owner <owner> --branch <branch> --worktree <path>
```

Prefer provider-native execution after preflight: use Codex Goal mode or the
active Codex workflow to execute and iterate on the task directly. Keep the
task pack, allowed paths, verification, review, and finish write-back as the
AgentSpec boundary. Do not bypass those gates because Codex owns the execution
loop.

If provider-native execution is unavailable, use the generic fallback:

```bash
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
```

`aspec run loop` and `aspec run exec` remain compatibility paths during the
transition, not the preferred Codex workflow.

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

5. Verify the changed area and complete the task only after tests pass:

```bash
aspec task complete <T-id> --test-status passed
aspec status
```

If no ready task exists, inspect DCRs, open questions, and requirements before
creating new work. Do not create implementation scope without a requirement or
DCR-backed task.
