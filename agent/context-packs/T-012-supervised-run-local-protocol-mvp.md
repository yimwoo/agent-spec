# T-012: Supervised Run Local Protocol MVP

Type: `implementation`
Originating DCR: `DCR-0001-supervised-runs`
Related ADR: `ADR-0003-supervised-run-protocol`

## Goal

Implement the smallest local supervised-run protocol boundary:

- create and inspect file-backed run state
- record per-iteration JSONL events
- resolve configured executor/reviewer profiles
- produce deterministic reviewer/controller verdicts for low-risk continuation,
  pause, halt, and completion cases

This task does not call external model APIs. It prepares the adapter boundary
for a later model-backed reviewer.

## Requirements

- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes one
  context pack with iteration cap and allowed-paths enforcement.
- `R-128` (P2, proposed-pending-acceptance) Supervised run records
  per-iteration evidence in `agent/runs/` JSONL.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model produces structured
  feedback consumable by next iteration.
- `R-130` (P2, proposed-pending-acceptance) Supervised run halts and requires
  human approval for risky changes.

This MVP exercises the protocol but should not promote these requirements
until the implementation is verified.

## Source Sections

- `D-07` Architectural Principles
- `D-12.12` Context Pack Builder
- `D-12.17` Policy Engine
- `D-22.3` Codex Role Rules
- `D-23.4` Automation Permissions
- `D-23.6` Audit
- `D-24` Observability and Evaluation

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON to
  avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-012-supervised-run-local-protocol-mvp.md`
- `docs/adr/0003-supervised-run-protocol.md`
- `docs/discovery/open-questions.yml`
- `agentspec/cli.py`
- `agentspec/policy.py`
- `agentspec/review.py`
- `agentspec/run.py`
- `tests/test_supervised_run.py`

## Forbidden Paths

- Anything outside the allowed paths.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Raw credential files such as `~/.codex/auth.json`.

## Tests To Add Or Update

- `tests/test_supervised_run.py`

## Acceptance Criteria

- `aspec run start <context-pack>` creates `agent/runs/<run-id>/state.yml` and
  `events.jsonl`.
- `aspec run resume <run-id>` appends executor, reviewer, and controller events.
- Dogfood continuation output for the active context pack yields
  `auto_continue`.
- Touched paths outside the active context pack's allowed paths yield `halt`.
- Ambiguous task choice yields `pause_for_human`.
- `aspec run inspect <run-id>` reports current state.
- `aspec run abort <run-id>` records an abort event.
- `python -m unittest discover -s tests -v` passes.
