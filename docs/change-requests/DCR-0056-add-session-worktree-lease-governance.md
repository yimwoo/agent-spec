# DCR-0056: Add session worktree lease governance

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

Add AgentSpec-native session leases for multi-agent and multi-session work.
The feature records who owns a task execution session, which context pack it is
bound to, what branch/worktree it uses, which paths it is allowed to touch, and
how the session was finished or released.

This adopts the useful worktree/session pattern from HOTL, Superpowers, and
agent skill packs while keeping AgentSpec's role as a repo-level control plane:
the plugin or code agent edits code, but AgentSpec owns the auditable session
state.

## Motivation

Large projects often have multiple code-agent sessions, humans, and subagents
working at once. Branches, worktrees, handoff files, and chat state can drift
or collide. A project needs a portable way to see active owners, claimed task
packs, worktree paths, locked scopes, and finish disposition even when not
every developer uses the same plugin.

AgentSpec already tracks requirements, task packs, runs, review evidence, and
outcomes. The missing control-plane layer is "who is currently working on
what, in which checkout, under which allowed paths."

## Proposed Change

- Add `aspec session` CLI commands:
  - `start`
  - `list`
  - `inspect`
  - `finish`
  - `release`
- Persist active session leases under `agent/sessions/active/`.
- Persist terminal session records under `agent/sessions/archived/`.
- Add session summaries to `aspec status --json` and human status output.
- Seed fresh projects with active and archived session directory markers.
- Do not add a gitignore rule for session leases in this first slice; they are
  durable AgentSpec control-plane artifacts unless a later policy says
  otherwise.
- Add focused tests for session start/list/inspect/finish/release and status
  integration.
- Keep the first slice local-first and non-destructive. Creating a lease may
  record a worktree path/branch, but it does not create or delete git
  worktrees yet.

## Impact Assessment

New requirement:

- `R-191`: AgentSpec records multi-session worktree leases.

Likely affected artifacts:

- `agentspec/session.py`
- `agentspec/cli.py`
- `agentspec/status.py`
- `agentspec/init.py`
- `agentspec/paths.py`
- `agent/sessions/active/.gitkeep`
- `agent/sessions/archived/.gitkeep`
- `tests/test_session_cli.py`
- `tests/test_cli_workflow.py`
- `docs/change-requests/DCR-0056-add-session-worktree-lease-governance.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required for the first local-state slice. A later ADR may be needed
when AgentSpec starts mutating git worktrees directly or coordinating remote
session locks across repositories.

## Acceptance Criteria

- `aspec session start --task <T-id> --json` creates an active session lease
  with schema `agentspec.session_lease.v0`.
- `aspec session list --json` reports active and archived session summaries.
- `aspec session inspect <session-id> --json` reads the active or archived
  lease.
- `aspec session finish <session-id> --disposition keep --json` moves the lease
  from active to archived and records terminal disposition.
- `aspec session release <session-id> --json` archives a released lease without
  requiring review completion.
- `aspec status --json` includes session summary counts and active session
  records.
- Fresh projects include `agent/sessions/active/` and
  `agent/sessions/archived/` markers.
- Tests cover session CLI behavior and status integration.
