# DCR-0043: Add app-build planner evaluator harness and test-eval reviewer profile

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Add an explicit app-build harness archetype that maps Anthropic-style planner,
generator, and evaluator responsibilities onto AgentSpec's existing control
plane.

AgentSpec already has the durable task, runner, and review primitives. This
change makes the mapping concrete for web/app projects, emits planner and
evaluator role guidance, and adds a first-class `test_eval_reviewer` model
profile so the evaluator can run on a different model than the implementation
agent.

## Motivation

The Harness Engineering follow-up work established durable task packs, runner
evidence, generated context freshness, and project invariant checks. Anthropic's
long-running app harness guidance reinforces the same pattern: keep planning,
generation, and evaluation separate, and require browser/user-flow evidence for
UI-heavy work.

AgentSpec has equivalent concepts, but the role names and model binding are not
obvious to project users. In particular, the existing `test-eval-reviewer` role
is a documentation artifact, while runtime model profiles expose
`quality_reviewer`. A project should be able to configure a dedicated evaluator
model, such as a Codex/LiteLLM model string, without changing the implementer's
model.

## Proposed Change

- Add app planner and app evaluator role artifacts to the generated role set.
- Add an `agent/workflows/app-build.md` workflow that documents the
  planner/generator/evaluator contract for app and web tasks.
- Add a default `test_eval_reviewer` agent profile and bind terminal quality
  review to it by default.
- Preserve existing `quality_reviewer` profile compatibility for projects that
  already point `supervised_runs.quality_reviewer_profile` at it.
- Allow model-backed autonomous/research quality signoff to use the configured
  test-eval/quality reviewer profile.
- Document that the generator remains the external code runner or host code
  agent; AgentSpec owns the planning and evaluation harness, not code writing.

## Impact Assessment

Affected existing requirements:

- `R-006`: AgentSpec emits role and reviewer definitions.
- `R-036`: policy and review behavior should be represented as data, not
  hardcoded prompt assumptions.
- `R-124`: agent model/profile configuration is portable and project-local.
- `R-144`: terminal completion uses quality-reviewer signoff in autonomous
  mode.
- `R-175`: runner evidence supports UI/browser validation artifacts.

Likely new requirement:

- `R-178`: AgentSpec exposes an app-build planner/generator/evaluator harness
  and configurable test-eval reviewer profile.

Likely affected artifacts:

- `agentspec/config.py`
- `agentspec/emit.py`
- `agentspec/init.py`
- `agentspec/model_review.py`
- `agentspec/paths.py`
- `agentspec/run.py`
- `agentspec/review.py`
- `docs/traceability/requirements.yml`
- `tests/test_config_profiles.py`
- `tests/test_dual_reviewer_signoff.py`
- `tests/test_init_layout.py`
- `tests/test_model_review.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This uses the existing supervised/autonomous reviewer
architecture and role-emission surface. A future DCR can add a dedicated
browser automation runner; this slice only makes the harness contract and
evaluator model binding explicit.

## Acceptance Criteria

- Fresh `aspec init` output includes app planner and app evaluator role
  artifacts and an app-build workflow.
- Fresh runtime config includes a `test_eval_reviewer` profile that can carry a
  project-specific model string independently of `main_executor`.
- Terminal quality review binds to `test_eval_reviewer` by default while
  preserving explicit `quality_reviewer_profile` overrides.
- Model-backed autonomous/research quality signoff uses the configured
  evaluator profile when `--reviewer model` or `--reviewer auto` is enabled.
- The app-build workflow states that the generator is the external code runner
  and that evaluators should require UI/browser evidence for app tasks.
- Tests cover profile defaults/overrides, emitted app-build roles/workflow, and
  model-backed quality signoff.
