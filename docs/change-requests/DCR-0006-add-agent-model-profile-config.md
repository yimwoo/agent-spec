# DCR-0006: Add agent model profile config

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Add repository-level agent model profile configuration for secondary agents.

The main executor remains the currently interactive host agent and inherits the
host's default model. Continuation and quality reviewers can use explicit model
profiles resolved through the local adapter, such as Codex's user-level
configuration and auth files.

## Motivation

The supervised-run protocol needs different model choices for different jobs:
the active code-writing agent should stay under the user's current session,
while low-risk continuation review can use a cheaper/faster model and final
quality review can use a stronger model.

Without a repository-level profile shape, `aspec run` would either hardcode
model choices or require model ids in every context pack.

## Proposed Change

- Add default `agent_profiles` to `.agentspec/config.yml` during `aspec init`.
- Add default `supervised_runs` profile bindings to `.agentspec/config.yml`.
- Represent the main executor as `adapter=current-host`,
  `model=host-default`.
- Represent secondary reviewers as named Codex adapter profiles that reference
  `codex-auth` and `codex-config` credential/config sources without storing
  secrets.
- Allow existing repositories to fill concrete model ids locally.

## Impact Assessment

- Supports `R-127` and `R-129` from DCR-0001 / ADR-0003 without implementing
  the supervised-run loop.
- Supports `R-007` by preparing CLI runtime configuration.
- Code surface: `agentspec/config.py`, `agentspec/init.py`.
- Config surface: `.agentspec/config.yml`.
- Test surface: init/config defaults.

## Disposition

Classification: `implement-now`.

No new ADR is required because ADR-0003 already records the model-profile
decision in proposed form. This DCR adds the harmless configuration shape.

## Acceptance Criteria

- Fresh `aspec init` writes `agent_profiles.main_executor` with
  `adapter=current-host` and `model=host-default`.
- Fresh `aspec init` writes continuation and quality reviewer profiles that
  reference local Codex credential/config sources but contain no API keys.
- Current dogfood config contains concrete reviewer model examples.
- Existing tests pass.
