# DCR-0031: Use plugin skills as the Codex skill surface

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Remove the overlapping repo-local Codex skills from this repository and make
`aspec emit --target codex` rely on the packaged AgentSpec Codex plugin for
skills. Codex should expose one AgentSpec skill surface during dogfooding: the
same installed plugin skills an end user sees.

Repo-local Codex agents may still be emitted. The cleanup is specifically about
`.agents/skills/**`, which currently duplicates plugin workflows such as task
creation, compile, drift review, and source intake.

## Motivation

DCR-0029 and DCR-0030 introduced the AgentSpec Codex plugin and installed it for
local testing. Codex now shows two AgentSpec skill groups:

- project-local generated skills from `.agents/skills/**`;
- installed personal plugin skills from `agentspec-codex-plugin`.

That makes the dogfood environment different from the end-user plugin
experience and makes debugging ambiguous. The project should test the same
plugin skills it expects users to run.

## Proposed Change

- Stop emitting repo-local `.agents/skills/**` for the Codex target.
- Delete this repository's generated `.agents/skills/agentspec-*` files.
- Keep `.codex/agents/**` emission intact; those are project-local agents, not
  workflow skills.
- Keep the packaged plugin skills as the user-facing AgentSpec skill surface.
- Update tests to assert Codex emit does not create overlapping repo-local
  AgentSpec skills and that this repository does not carry them.

## Impact Assessment

Affected existing requirements:

- `R-044`: `aspec emit --target codex` remains valid, but emits Codex agents
  without project-local AgentSpec skills.
- `R-164`: manual source intake remains available through the packaged plugin
  skill, not through generated `.agents/skills`.
- `R-165`: plugin init and continuation skills remain the documented user path.

Likely new requirement:

- `R-166`: Codex dogfooding uses the installed AgentSpec plugin skill surface
  without overlapping repo-local generated AgentSpec skills.

Likely affected artifacts:

- `agentspec/emit.py`
- `agentspec/paths.py`
- `.agents/skills/**`
- `tests/test_plugin_source_intake.py`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a cleanup of plugin distribution boundaries and test
coverage after the Codex plugin alpha.

## Acceptance Criteria

- `aspec emit --target codex` continues to emit `.codex/agents/**`.
- `aspec emit --target codex` does not emit `.agents/skills/agentspec-*`.
- This repository no longer has tracked `.agents/skills/agentspec-*` skill
  files.
- Codex prompt discovery exposes the installed `agentspec-codex-plugin:*`
  skills and does not expose the old repo-local `agentspec-*` skill names.
- Full test suite passes.
