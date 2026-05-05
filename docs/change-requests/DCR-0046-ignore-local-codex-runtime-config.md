# DCR-0046: Ignore local Codex runtime config

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

Ignore repo-local Codex runtime configuration at `.codex/config.toml` while
continuing to track generated Codex agent role files under `.codex/agents/`.

This is a repository hygiene and privacy change. It does not change AgentSpec
runtime behavior.

## Motivation

The local `.codex/config.toml` file is host-specific runtime configuration and
should not be published to GitHub. The project already commits
`.codex/agents/*.toml` as generated agent-context artifacts, so ignoring the
entire `.codex/` directory would be too broad.

## Proposed Change

- Add `.codex/config.toml` to `.gitignore`.
- Do not ignore `.codex/agents/*.toml`.
- Leave the existing untracked `.codex/config.toml` file local.

## Impact Assessment

Affected artifacts:

- `.gitignore`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-076-ignore-local-codex-runtime-config.md`
- `agent/reviews/REVIEW-0013.yml`
- `agent/task-ledger.yml`

Likely new requirement:

- `R-181`: Local Codex runtime config is ignored while generated Codex agent
  roles remain trackable.

## Disposition

Classification: `implement-now`.

No ADR is required. This is a narrow repository hygiene rule for a local config
file.

## Acceptance Criteria

- `.gitignore` contains `.codex/config.toml`.
- `.gitignore` does not ignore all of `.codex/`.
- `git status --short` no longer lists `.codex/config.toml` as untracked.
- Existing tracked `.codex/agents/*.toml` files remain tracked.
