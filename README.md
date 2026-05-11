# AgentSpec

AgentSpec turns design intent into durable, repo-local operating context for
human + agent software delivery.

It is a local-first CLI that snapshots sources, derives requirements, creates
bounded task packs, runs governed execution loops, records verification/review
evidence, and writes back roadmap + handoff state. The goal is simple: a code
agent should be able to continue work from the repository itself, not from chat
history.

## Why It Exists

Code agents work best when the operating contract is explicit:

- what source material is canonical
- which requirements are accepted
- what paths a task may touch
- what verification and review evidence is required
- what should be handed to the next human or agent

AgentSpec keeps that contract in committed artifacts: `docs/source/`,
`docs/traceability/requirements.yml`, `agent/context-packs/`,
`agent/task-ledger.yml`, `agent/handoff.yml`, and `docs/ROADMAP.md`.

This README is the front door. The deeper human guide is
[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Install

```bash
pip install -e .
```

This exposes `aspec` and `agentspec` on `PATH`. They are the same CLI. If you
do not want to install the package, use:

```bash
python -m agentspec.cli --help
```

## Five-Minute Quickstart

Run this inside a repository that has, or will have, a Markdown design source:

```bash
aspec init --mode greenfield --targets claude,codex
aspec ingest docs/source/design.md
aspec compile
aspec status
aspec task create --requirement R-001
aspec plan --current
aspec run loop
```

After implementation work, record review and finish write-back:

```bash
aspec review code --task T-001 --verdict ready --summary "No blocking findings."
aspec finish T-001 --test-status passed --review REVIEW-0001
aspec roadmap --check
```

For this repository, use `PYTHONPATH=$PWD aspec ...` if the editable install is
not active in your shell.

## Lifecycle

AgentSpec's native lifecycle is the project contract. Plugins and local skills
are adapters over these repo-local artifacts, not separate sources of truth.

```mermaid
flowchart LR
  A["Brainstorm / DCR"] --> B["Design Intake"]
  B --> C["Compile Spec"]
  C --> D["Create Task Pack"]
  D --> E["Plan Workflow"]
  E --> F["Execute"]
  F --> G["Verify"]
  G --> H["Review"]
  H --> I["Finish"]
  I --> J["Roadmap + Handoff"]
```

Core commands:

| Stage | Command |
|---|---|
| Status | `aspec status --json` |
| Lifecycle map | `aspec lifecycle` |
| Source intake | `aspec ingest`, `aspec intake import`, `aspec compile` |
| Task planning | `aspec task create`, `aspec plan` |
| Execution | `aspec run loop`, `aspec run step`, `aspec run package`, `aspec run result` |
| Verification | `aspec outcome`, `aspec maturity status`, `aspec roadmap --check` |
| Review | `aspec review code` |
| Finish | `aspec finish`, `aspec task complete` |
| Recovery | `aspec next-action`, `aspec continue` |

The lifecycle surface is covered by `R-205`. The end-to-end dogfood workflow is
covered by `R-203`. This README and the human guide are covered by `R-207`.

## Project Model

AgentSpec separates incoming design material from accepted repo-local truth:

- **Source snapshot**: immutable source material under `docs/source/`.
- **Requirement**: accepted implementation obligation in
  `docs/traceability/requirements.yml`.
- **DCR**: design change request for anything that changes after the accepted
  source snapshot.
- **Task context pack**: bounded implementation unit under
  `agent/context-packs/`.
- **Workflow**: native execution plan under `agent/workflows/`.
- **Review + finish evidence**: records under `agent/reviews/`,
  `agent/task-ledger.yml`, `agent/handoff.yml`, and `docs/ROADMAP.md`.

Agents should start from `AGENTS.md`, `aspec status --json`, and the active task
pack. Humans should start from this README and
[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Repository Layout

```text
agentspec/                  CLI implementation
tests/                      regression tests
docs/source/                accepted source snapshots
docs/spec/                  generated spec shards
docs/traceability/          requirements and traceability maps
docs/change-requests/       DCRs for design changes
docs/designs/               hand-authored design docs and index
docs/discovery/             assumptions, risks, questions, spikes
agent/context-packs/        bounded task packs for implementation
agent/workflows/            native AgentSpec workflow plans
agent/reviews/              review evidence
agent/handoff.yml           latest project handoff state
agentspec-codex-plugin/     Codex adapter package
agentspec-claude-plugin/    Claude adapter package
```

## Human Guide

Read [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for:

- bootstrapping a new project
- importing changing external sources
- creating and executing task packs
- recording verification and review evidence
- finishing work and refreshing handoff/roadmap state
- deciding what to commit

Read [docs/designs/README.md](docs/designs/README.md) for the documentation
registry and source-of-truth map.

## Verification

```bash
python -m unittest discover -s tests -v
aspec status --json
aspec roadmap --check --json
```

For documentation-only changes, also run:

```bash
python -m json.tool docs/traceability/requirements.yml >/dev/null
git diff --check
```
