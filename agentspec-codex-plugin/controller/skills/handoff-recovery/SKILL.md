---
name: handoff-recovery
description: Recover AgentSpec work from durable status, handoff, roadmap, active runs, and next-action guidance.
---

# Handoff Recovery

Controller procedure id: `handoff-recovery`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill when resuming interrupted work, answering "what is next?", or
checking whether the repository is idle, running, blocked, or stale.

## Workflow

1. Read the durable AgentSpec state:

```bash
aspec lifecycle --json
aspec status --json
aspec next-action
aspec task next
```

2. If a run is active, inspect its prompt or continue it:

```bash
aspec run prompt <run-id>
aspec run loop --run-id <run-id>
```

3. If write-back is stale, repair with the command reported by status:

```bash
aspec roadmap
aspec roadmap --check --json
```

Boundary: this skill reads and repairs AgentSpec-owned state. It does not infer
hidden plugin state, and it should not continue outside the active task pack's
allowed paths.
