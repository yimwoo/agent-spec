# T-009: Draft ADR-0003 Supervised Run Protocol

Type: `spec`
Originating DCR: `DCR-0001-supervised-runs`
Related ADR: `ADR-0003-supervised-run-protocol`

## Goal

Convert the T-004 supervised-run spike findings into a proposed architecture
decision record for the file-backed agent reply loop.

## Requirements

- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes one
  context pack with iteration cap and allowed-paths enforcement.
- `R-128` (P2, proposed-pending-acceptance) Supervised run records
  per-iteration evidence in `agent/runs/` JSONL.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model produces structured
  feedback consumable by next iteration.
- `R-130` (P2, proposed-pending-acceptance) Supervised run halts and requires
  human approval for risky changes.

These requirements remain proposed until the ADR is accepted and an
implementation context pack ships the runtime behavior.

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

- `agent/context-packs/T-009-draft-adr-0003-supervised-run-protocol.md`
- `docs/adr/0003-supervised-run-protocol.md`

## Forbidden Paths

- Anything outside the allowed paths.
- Production runtime modules such as `agentspec/run.py`, `agentspec/review.py`,
  `agentspec/policy.py`, and `agentspec/cli.py`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Canonical source snapshots in `docs/source/`.

## Tests To Add Or Update

- None. This is a spec/ADR task.

## Acceptance Criteria

- ADR cites `DCR-0001`, T-004 spike evidence, and `R-127` through `R-130`.
- ADR defines executor, controller/reviewer, collector, policy gate, and run
  state responsibilities.
- ADR records decisions for `Q-012`, `Q-013`, and `Q-014` at least as proposed
  answers.
- ADR remains `proposed` until the project owner accepts it.
