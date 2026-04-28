# AgentSpec

AgentSpec is a local-first CLI that turns design documents into agent-ready repository context:

- canonical source snapshots and source sections
- spec shards
- requirements with source references
- assumptions and open questions
- task context packs
- Claude/Codex-oriented agent instruction artifacts
- brownfield doctor and drift-review skeleton reports

## Quick Start

```bash
aspec init
aspec ingest docs/source/design.md
aspec compile
aspec task create --requirement R-001
aspec task list
aspec task next
aspec run loop
aspec run prompt <run-id>
aspec run step --json
aspec emit --target claude,codex
aspec doctor
aspec drift
```

Structured `.yml` files are currently written as YAML-compatible JSON so the MVP can run with only the Python standard library.

## Agent Control Plane

```bash
aspec task list --json
aspec task next
aspec run loop
aspec run prompt <run-id> --json
aspec run step --run-id <run-id> --executor-output "..." --json
aspec task complete T-013 --test-status passed
```

`agent/task-ledger.yml` is the committed queue-status projection. Local
`agent/runs/*` keeps detailed execution state and remains ignored by git.
`aspec run prompt` renders the next executor handoff from durable run state and
reviewer events, including any continuation reviewer instruction.
`aspec run step` combines task selection/start/resume, reviewer verdicts, and
the next handoff prompt into one harness-oriented JSON response.

## Verification

```bash
python -m unittest discover -s tests -v
aspec --help
```
