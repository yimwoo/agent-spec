---
name: design-work
description: Turn accepted design material into AgentSpec source snapshots, requirements, and traceability without bypassing source governance.
---

# Design Work

Call this skill as `aspec:design-work`.

Use this skill when implementation depends on a design document, external
source, API contract, ADR, or user-provided design note.

## Workflow

1. Inspect the lifecycle contract and source readiness:

```bash
aspec lifecycle --json
aspec status --json
```

2. Import or ingest the source through AgentSpec:

```bash
aspec ingest <markdown-path>
aspec intake import <path> --kind markdown --source-key <source-key> --classification internal --storage-mode committed --as-candidate
aspec intake diff <snapshot-id>
aspec intake promote <snapshot-id> --decision accepted --compile
aspec compile
```

3. Check the resulting requirements and identify whether the next step is a DCR,
   task pack, workflow, or more source clarification.

Boundary: this skill does not own source parsing, diffing, promotion, or
accepted snapshots. Those are AgentSpec artifacts and CLI responsibilities.
