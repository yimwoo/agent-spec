---
name: finish-branch
description: Finish AgentSpec-governed branch work by checking verification, review, write-back, roadmap, and session disposition.
---

# Finish Branch

Controller procedure id: `finish-branch`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill after implementation, verification, and review are complete and
the user wants to close a development branch or task.

## Workflow

1. Check finish readiness and lifecycle state:

```bash
aspec lifecycle --json
aspec finish <T-id> --dry-run --review <REVIEW-id> --test-status passed --json
aspec status --json
```

2. Finish AgentSpec write-back:

```bash
aspec finish <T-id> --review <REVIEW-id> --test-status passed --reason "<summary>"
aspec roadmap
aspec roadmap --check --json
```

3. Archive a session lease when one exists:

```bash
aspec session finish <session-id> --disposition merge --review <REVIEW-id> --test-status passed
```

   Use `pr` when work is delivered through a pull request, `merge` when it is
   merged directly, `keep` when the branch/worktree must remain available, and
   `discard` when the work is intentionally abandoned. Use `aspec session
   release` for handoff or abandoned ownership; release is not delivery
   closure.

4. Use git merge, push, or PR commands only when the user or project branch
   policy asks for that disposition.

5. Treat local cleanup as advisory. `aspec status --json` reports cleanup
   eligibility only after task/write-back closure, delivery closure, clean
   branch/worktree resources, and no active owner/patcher lease for the same
   resources. Do not remove a git worktree or delete a local branch without
   explicit user confirmation or a later opt-in project policy.

Boundary: current AgentSpec has `aspec finish` and session finish. A future
dedicated branch-finish command can add clean-checkout verification and record
merge, PR, keep, discard, release, and advisory cleanup checks in one native
flow. Ticket fixes, features, designs, milestones, and cross-repo AgentSpec
work share the same finish lifecycle.

## Human-Facing Output

For Codex or Claude Code final replies, summarize the branch disposition,
completed task, review id, verification result, outcome readiness, and roadmap
freshness by purpose and result. Keep raw `aspec ...` commands internal unless
the user asks for terminal logs or reproduction commands.
