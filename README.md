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
python -m agentspec.cli init
python -m agentspec.cli ingest docs/source/design.md
python -m agentspec.cli compile
python -m agentspec.cli task create --requirement R-001
python -m agentspec.cli emit --target claude,codex
python -m agentspec.cli doctor
python -m agentspec.cli drift
```

Structured `.yml` files are currently written as YAML-compatible JSON so the MVP can run with only the Python standard library.

## Verification

```bash
python -m unittest discover -s tests -v
python -m agentspec.cli --help
```
