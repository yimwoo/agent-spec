# DCR-0070: Add native lifecycle operating contract surface

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

Add an AgentSpec-native lifecycle operating contract surface that makes
AgentSpec responsible for the whole human-plus-agent software delivery loop,
not only narrow task control-plane state. The first slice should expose a
durable lifecycle catalog and packaged skills for brainstorming, design,
planning, branch/session start, workflow execution, delegation planning,
verification, review, branch finish, and handoff/recovery.

This slice should keep AgentSpec as the repo-local authority for contracts,
state transitions, allowed paths, review evidence, verification evidence,
branch/session leases, write-back, and handoff. Host-specific model spawning
remains adapter-provided, but AgentSpec owns the operating contract that those
adapters must follow.

## Motivation

The recent lifecycle hardening phases proved AgentSpec can own task packs,
native workflow artifacts, supervised runs, review evidence, finish
write-back, roadmap generation, and portable handoff. The next product step is
to make the full lifecycle explicit and discoverable so code agents can follow
AgentSpec-native behavior without relying on HOTL, Superpowers, or hidden chat
conventions.

Reviewing `addyosmani/agent-skills` shows useful lifecycle coverage areas:
idea refinement, spec-driven development, planning/task breakdown, incremental
implementation, TDD, source-driven development, code review/quality, debugging,
git workflow/versioning, documentation/ADRs, CI/CD, migration, security,
performance, browser testing, and shipping/launch. AgentSpec should not import
those skills verbatim, but it should provide native stages and skills that map
those practices onto AgentSpec artifacts.

## Proposed Change

- Add a core AgentSpec lifecycle contract module and CLI surface:
  - `aspec lifecycle --json`
  - human output for lifecycle stages, native commands, skill names, and
    implementation status.
- Classify lifecycle stages as:
  - `available`: backed by current AgentSpec commands.
  - `partial`: supported through existing primitives but not yet a dedicated
    command.
  - `planned`: intentionally future native capability.
- Add AgentSpec-native packaged skills for the broader operating contract:
  - brainstorm
  - design-work
  - start-branch
  - execute-workflow
  - delegate-work
  - finish-branch
  - handoff-recovery
- Keep the skills CLI-backed and honest about missing dedicated commands.
- Add tests for the lifecycle CLI shape and both plugin skill packages.

## Impact Assessment

New requirement:

- `R-205`: AgentSpec exposes a native lifecycle operating contract.

Likely affected artifacts:

- `agentspec/lifecycle.py`
- `agentspec/cli.py`
- `agentspec-codex-plugin/skills/**/SKILL.md`
- `agentspec-claude-plugin/skills/**/SKILL.md`
- `tests/test_lifecycle_cli.py`
- `tests/test_plugin_source_intake.py`
- `tests/test_claude_code_plugin.py`
- `docs/change-requests/DCR-0070-add-native-lifecycle-operating-contract-surface.md`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-101-add-native-lifecycle-operating-contract-surface.md`
- `agent/workflows/W-101-add-native-lifecycle-operating-contract-surface.md`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `docs/ROADMAP.md`

## Disposition

Classification: `implement-now`.

No ADR is required for the catalog/skill surface. Dedicated subagent execution
and branch finalization commands can follow as separate implementation slices
once this contract is visible and test-covered.

## Acceptance Criteria

- `aspec lifecycle --json` returns a schema-versioned lifecycle operating
  contract with stages, status, native commands, skill names, adapter boundary,
  and source inspirations.
- Human `aspec lifecycle` output lists the lifecycle stages in order and shows
  which stages are available, partial, or planned.
- Codex and Claude plugin packages include discoverable lifecycle skills for
  brainstorming, design, branch start, workflow execution, delegation planning,
  branch finish, and handoff/recovery.
- Existing lifecycle skills remain CLI-backed and no plugin skill owns durable
  state outside AgentSpec artifacts.
- Tests cover the lifecycle CLI JSON/human output and plugin skill package
  expansion.
