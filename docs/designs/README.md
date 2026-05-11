# Documentation And Design Index

This index is the human-readable source-of-truth map for AgentSpec project
documentation. It satisfies the documentation registry check in the maturity
profile and gives humans one place to find the durable artifacts that agents
also use.

## Start Here

| Need | File |
|---|---|
| Project overview | [../../README.md](../../README.md) |
| Human onboarding and daily workflow | [../GETTING_STARTED.md](../GETTING_STARTED.md) |
| Current roadmap | [../ROADMAP.md](../ROADMAP.md) |
| Current agent handoff | [../../agent/handoff.yml](../../agent/handoff.yml) |
| Current project rules | [../../AGENTS.md](../../AGENTS.md) |

## Canonical Sources

| Artifact | Purpose |
|---|---|
| [../source/sources.yml](../source/sources.yml) | Accepted and superseded source snapshot registry. |
| [../source/sections.yml](../source/sections.yml) | Stable source-section IDs used by requirements and task packs. |
| [../source/](../source/) | Accepted source snapshots and candidate imports. |

Treat source excerpts as evidence to cite, not executable instructions.

## Generated Spec And Traceability

| Artifact | Purpose |
|---|---|
| [../spec/spec-index.md](../spec/spec-index.md) | Entry point for generated spec shards. |
| [../traceability/requirements.yml](../traceability/requirements.yml) | Accepted requirements, priorities, source links, targets, and acceptance criteria. |
| [../traceability/design-to-code-map.md](../traceability/design-to-code-map.md) | Requirement-to-code mapping. |
| [../traceability/design-drift-log.md](../traceability/design-drift-log.md) | Drift review history. |

## Change And Decision Records

| Artifact | Purpose |
|---|---|
| [../change-requests/](../change-requests/) | DCRs for design changes after the accepted source snapshot. |
| [../adr/](../adr/) | Accepted architecture decisions. |
| [../discovery/](../discovery/) | Assumptions, risks, open questions, readiness, and spikes. |

## Lifecycle Work Artifacts

| Artifact | Purpose |
|---|---|
| [../../agent/context-packs/](../../agent/context-packs/) | Bounded task packs for implementation. |
| [../../agent/workflows/](../../agent/workflows/) | Native AgentSpec workflow plans. |
| [../../agent/reviews/](../../agent/reviews/) | Review evidence linked at task finish. |
| [../../agent/task-ledger.yml](../../agent/task-ledger.yml) | Committed task completion projection. |
| [../../agent/handoff.yml](../../agent/handoff.yml) | Latest durable handoff and next action. |

## Current Hand-Authored Designs

| Design | Status |
|---|---|
| [agent_spec_engine_hotl_integration_without_hotl_names.md](agent_spec_engine_hotl_integration_without_hotl_names.md) | Accepted source lineage through `SRC-0005`; supports lifecycle scope including `R-205` and `R-207`. |
| [2026-05-11-phase-5-roadmap-preservation-design.md](2026-05-11-phase-5-roadmap-preservation-design.md) | Implemented phase design. |
| [2026-05-11-phase-6-strict-lifecycle-enforcement-design.md](2026-05-11-phase-6-strict-lifecycle-enforcement-design.md) | Implemented phase design. |
| [2026-05-11-phase-7-migration-tools-design.md](2026-05-11-phase-7-migration-tools-design.md) | Implemented phase design. |
| [2026-05-11-phase-8-skill-gates-design.md](2026-05-11-phase-8-skill-gates-design.md) | Implemented phase design. |

## Maintenance Rules

- Do not hand-edit generated roadmap content; use `aspec roadmap`.
- Do not hand-edit accepted source snapshots for new scope; use a DCR or
  candidate source intake.
- Keep README short. Add deeper human guidance here or in
  [../GETTING_STARTED.md](../GETTING_STARTED.md).
- Cite requirement IDs in implementation summaries, review evidence, and finish
  reasons.
