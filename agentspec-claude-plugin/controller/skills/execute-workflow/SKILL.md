---
name: execute-workflow
description: Execute an AgentSpec task workflow through native run state, task packs, path scope, and runner packages.
---

# Execute Workflow

Controller procedure id: `execute-workflow`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill when a task context pack and workflow exist and the user wants
implementation to proceed under AgentSpec governance.

## Workflow

1. Inspect the contract, active run, and task pack:

```bash
aspec lifecycle --json
aspec status --json
aspec run prompt <run-id>
```

2. Prefer provider-native execution. Use Claude `/loop` or a dynamic Claude
   workflow to keep iterating until the workflow's verification and completion
   criteria are satisfied. Do not bypass AgentSpec task scope, session
   preflight, allowed paths, review, or finish write-back.

3. If the host-native capability is unavailable, use the provider-neutral
   generic fallback contract:

```bash
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
```

`aspec run loop` and `aspec run exec --runner claude` remain compatibility
paths. They are not the preferred Claude execution strategy.

Claim or verify an active owner/patcher session lease before implementation execution.
Do not start `aspec run loop`, `aspec run package`, or `aspec run exec` until session preflight is satisfied.
Explicit host-worktree execution is an auditable escape hatch when the workflow or context pack declares it intentionally.

4. Keep edits inside the task context pack allowed paths and report touched
   paths in the executor result.

Boundary: this skill does not create a separate execution state machine.
AgentSpec owns run state, task ledger updates, verification requirements, and
review linkage.
