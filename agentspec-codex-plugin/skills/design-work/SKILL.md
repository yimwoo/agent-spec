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

## Human-Facing Output

For Codex or Claude Code final replies after design/source revisions, keep raw
`aspec ...` commands internal unless the user asks for command-level logs or
terminal reproduction steps. Report source intake, promotion, compile, roadmap,
and status checks by purpose and result, for example:

- "Source candidate diff reviewed."
- "Accepted source projections refreshed."
- "Generated requirements and roadmap are current."

Do not include a final "Tests / checks run" section that lists internal
AgentSpec CLI commands such as `aspec intake diff`, `aspec intake promote`,
`aspec compile`, `aspec status --json`, or `aspec roadmap --check`.

End with a short "Next" block in plain language. Say whether the next valid
move is to review the generated requirements, accept or revise a DCR, create a
task context pack, start implementation, or clarify the source. When status
output includes `agent_display`, prefer that command-free next-action text.
