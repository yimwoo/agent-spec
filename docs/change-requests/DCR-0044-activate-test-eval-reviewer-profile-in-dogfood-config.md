# DCR-0044: Activate test eval reviewer profile in dogfood config

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

Activate the new `test_eval_reviewer` profile in AgentSpec's own dogfood
runtime config.

`R-178` added the profile and made it the default for fresh or merged runtime
configs, but this repository has an explicit `.agentspec/config.yml` override
that still routes terminal quality review to `quality_reviewer`.

## Motivation

A test-eval review found that this checkout will not actually dogfood the new
evaluator model path until the committed project config adds
`test_eval_reviewer` and points `supervised_runs.quality_reviewer_profile` at
it. The implementation works when configured, but the repository should use the
same profile it now recommends.

## Proposed Change

- Add a `test_eval_reviewer` agent profile to `.agentspec/config.yml`.
- Set the profile's Codex-backed model to `oca/gpt5.3-codex`.
- Change `supervised_runs.quality_reviewer_profile` from `quality_reviewer` to
  `test_eval_reviewer`.
- Leave the existing `quality_reviewer` profile in place for compatibility.

## Impact Assessment

Affected existing requirements:

- `R-178`: AgentSpec exposes a configurable test-eval reviewer profile.
- `R-124`: agent model/profile configuration is portable and project-local.

Likely new requirement:

- `R-179`: AgentSpec dogfood config uses the test-eval reviewer profile.

Likely affected artifacts:

- `.agentspec/config.yml`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-074-activate-test-eval-reviewer-profile-in-dogfood-config.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a repository-local configuration activation for an
already-accepted runtime profile.

## Acceptance Criteria

- `.agentspec/config.yml` contains a `test_eval_reviewer` profile.
- The dogfood `test_eval_reviewer` profile uses model `oca/gpt5.3-codex`.
- `supervised_runs.quality_reviewer_profile` points at `test_eval_reviewer`.
- Existing `quality_reviewer` profile remains available.
- Targeted config tests and full unittest discovery pass.
