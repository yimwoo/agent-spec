---
name: delegate-work
description: Plan AgentSpec-governed delegation for independent workflow slices using disjoint ownership and native run packages.
---

# Delegate Work

Controller procedure id: `delegate-work`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill when a workflow has independent slices that could be executed by
separate agents or host processes without overlapping write paths.

## Workflow

1. Inspect the lifecycle contract and task boundaries:

```bash
aspec lifecycle --json
aspec status --json
aspec run prompt <run-id>
```

2. Split only independent work. Each child assignment must have a task id,
   allowed paths, expected output, verification command, owner, and dedicated
   branch/worktree lease for write-mode work. Do not point two owner/patcher
   child sessions at the same branch or worktree unless `--allow-shared` is
   explicitly part of the handoff.

3. Use current AgentSpec package/result commands for handoff and fan-in:

```bash
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
aspec session list --json
aspec session start --task <T-id> --owner <owner> --branch <branch> --worktree <path>
```

4. Aggregate returned evidence before review and finish.

Boundary: native `aspec run delegate` is planned, not implemented. Until then,
the adapter may spawn host subagents, but durable delegation state must remain
in AgentSpec task packs, sessions, run packages, results, reviews, and handoff.
