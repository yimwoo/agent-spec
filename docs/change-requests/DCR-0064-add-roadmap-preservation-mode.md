# DCR-0064: Add roadmap preservation mode

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-10 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-10 |
| Confidence | medium |

## Summary

Add Phase 5 roadmap preservation mode from the lifecycle hardening design. The
roadmap generator should keep the current full-file generated mode as the
default while adding an opt-in generated-block mode that preserves manual
content outside AgentSpec-managed markers.

This slice also corrects the execution discipline for lifecycle work: it creates
a phase design document, an executable plan document, and runs in a dedicated
git worktree before implementation changes.

## Motivation

The existing `aspec roadmap` command rewrites the whole roadmap file. That is
safe for generated-only projects, but it prevents humans from maintaining
project notes, operating context, or release-roadmap commentary in
`docs/ROADMAP.md` without losing those edits on the next write.

AgentSpec is becoming an operating contract for human + agent delivery, so
generated projections need explicit preservation boundaries. Humans should know
what the tool owns and where their hand-authored content is stable.

## Proposed Change

- Add an opt-in roadmap preservation mode behind repo config, keeping full-file
  generation as the default.
- In generated-block mode, `aspec roadmap` updates only the AgentSpec generated
  block and preserves manual content before and after the block.
- `aspec roadmap --check` must validate both full-file mode and generated-block
  mode deterministically.
- Add tests that cover manual content before and after the generated block,
  missing generated blocks, stale generated blocks, and default full-file
  compatibility.
- Add a phase design doc and executable workflow plan for this slice before code
  implementation.

## Impact Assessment

New requirement:

- `R-199`: AgentSpec preserves manual roadmap content in generated-block mode.

Likely affected artifacts:

- `agentspec/roadmap.py`
- `agentspec/cli.py`
- `agentspec/config.py`
- `tests/test_roadmap_preservation.py`
- `tests/test_workflow_contract.py`
- `tests/test_cli_workflow.py`
- `docs/designs/2026-05-11-phase-5-roadmap-preservation-design.md`
- `docs/plans/2026-05-11-phase-5-roadmap-preservation-workflow.md`
- `docs/change-requests/DCR-0064-add-roadmap-preservation-mode.md`
- `docs/traceability/requirements.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an additive, config-gated behavior that preserves
the current default and uses the existing roadmap file path and check command.

## Acceptance Criteria

- Full-file roadmap generation remains the default behavior.
- A repo config flag enables generated-block roadmap mode.
- Generated-block mode preserves manual content before and after the managed
  block.
- `aspec roadmap --check` succeeds when the generated block is current and fails
  when the block is missing or stale.
- Tests cover full-file compatibility, generated-block write behavior, and
  generated-block check behavior.
- The phase has a design doc, an executable plan doc, and a dedicated git
  worktree/branch before implementation completion.
