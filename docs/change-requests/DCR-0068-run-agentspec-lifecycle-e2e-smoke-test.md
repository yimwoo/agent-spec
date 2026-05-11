# DCR-0068: Run AgentSpec lifecycle E2E smoke test

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

Run an AgentSpec-only end-to-end lifecycle smoke test that exercises task pack
creation, native workflow creation, isolated branch work, commit creation,
verification, review evidence, task completion write-back, roadmap generation,
and handoff refresh.

## Motivation

The lifecycle hardening phases added native AgentSpec controls that should be
usable without HOTL, Superpowers, or external lifecycle plugins. A dogfood E2E
run should prove the current AgentSpec CLI can carry a small task through the
full delivery loop and identify any remaining lifecycle gaps.

## Proposed Change

- Create an accepted requirement for the lifecycle E2E smoke test.
- Create a task context pack with AgentSpec.
- Create a native AgentSpec workflow with `aspec plan`.
- Work on an isolated git branch and commit the implementation evidence.
- Run deterministic verification commands.
- Record code review evidence with `aspec review code`.
- Complete the task with linked review evidence.
- Regenerate roadmap and handoff state with AgentSpec write-back.

## Impact Assessment

New requirement:

- `R-203`: AgentSpec supports its own end-to-end lifecycle dogfood workflow.

Likely affected artifacts:

- `docs/change-requests/DCR-0068-run-agentspec-lifecycle-e2e-smoke-test.md`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-099-run-agentspec-lifecycle-e2e-smoke-test.md`
- `agent/workflows/W-099-run-agentspec-lifecycle-e2e-smoke-test.md`
- `reports/dogfood/2026-05-11-agentspec-lifecycle-e2e.md`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a dogfood validation run over existing AgentSpec
surfaces and should not add a new lifecycle mechanism.

## Acceptance Criteria

- A task context pack is created from `R-203`.
- A native `agent/workflows/W-*.md` workflow is created and linked to the task
  context pack.
- Work happens on branch `codex/e2e-agentspec-lifecycle`.
- At least one implementation evidence commit is created before write-back.
- Verification commands pass.
- `aspec review code` records ready review evidence for the E2E task.
- `aspec task complete` records passed verification with the review id.
- `aspec roadmap --check --json` reports the roadmap current after write-back.
