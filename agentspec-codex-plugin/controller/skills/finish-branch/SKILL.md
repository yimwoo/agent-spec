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
aspec session finish <session-id> --disposition merged --review <REVIEW-id> --test-status passed
```

4. Use git merge, push, or PR commands only when the user or project branch
   policy asks for that disposition.

Boundary: current AgentSpec has `aspec finish` and session finish. A future
dedicated branch-finish command can add clean-checkout verification and record
merge, PR, keep, or discard disposition in one native flow.

## Human-Facing Output

For Codex or Claude Code final replies, summarize the branch disposition,
completed task, review id, verification result, outcome readiness, and roadmap
freshness by purpose and result. Keep raw `aspec ...` commands internal unless
the user asks for terminal logs or reproduction commands.
