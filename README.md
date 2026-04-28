# AgentSpec

AgentSpec is a local-first CLI that turns design documents into agent-ready repository context:

- canonical source snapshots and source sections
- spec shards
- requirements with source references
- assumptions and open questions
- task context packs
- Claude/Codex-oriented agent instruction artifacts
- brownfield doctor and drift-review skeleton reports

## Install

```bash
pip install -e .
```

This exposes both `aspec` (short) and `agentspec` (long) on PATH. They are
the same entry point; `aspec --help` and `agentspec --help` produce
identical output modulo the program name. If you prefer not to install,
you can invoke the CLI directly via `python -m agentspec.cli`.

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
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
aspec run demo --json
aspec run exec --command-json '["python","-c","print(\"Done.\")"]' --test-status passed --json
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
aspec run package --runner codex --run-id <run-id> --json
aspec run result <run-id> --result-json '{"executor_output":"Done.","test_status":"passed"}' --json
aspec run demo --run-id demo-001 --json
aspec run exec --runner codex --run-id run-001 --test-status passed --json
aspec task complete T-013 --test-status passed
```

`agent/task-ledger.yml` is the committed queue-status projection. Local
`agent/runs/*` keeps detailed execution state and remains ignored by git.
`aspec run prompt` renders the next executor handoff from durable run state and
reviewer events, including any continuation reviewer instruction.
`aspec run step` combines task selection/start/resume, reviewer verdicts, and
the next handoff prompt into one harness-oriented JSON response.
`aspec run package` wraps a harness step in a runner execution envelope with
stdin prompt, environment hints, and a report-back command template.
`aspec run result` accepts a structured runner result JSON and returns the next
runner package, completing the package/result handshake.
`aspec run demo` runs a deterministic local package/result transcript for e2e
testing without invoking an external agent binary.
`aspec run exec` executes one runner package with a local subprocess, feeds the
prompt on stdin, discovers touched paths from git status, and submits the result
through the same package/result handshake.

## Verification

```bash
python -m unittest discover -s tests -v
aspec --help
```
