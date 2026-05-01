# Autonomous run loop should degrade cleanly when target repository is read-only

Recorded: 2026-05-01

## Context

Automation `agentracing-agentspec-autonomous-cycle` ran from Codex with
`sandbox_mode=workspace-write` where the writable roots included
`agent-spec-engine` but not the target repository
`/Users/yimwu/Documents/workspace/Apps/agentracing`.

The cycle followed the required AgentSpec control-plane sequence against the
target repository:

```bash
aspec --root /Users/yimwu/Documents/workspace/Apps/agentracing task next
aspec --root /Users/yimwu/Documents/workspace/Apps/agentracing run loop --mode autonomous --json
```

## Observation

`aspec task next` correctly reported that no ready task context pack exists.
`aspec run loop --mode autonomous --json` then attempted to enter research mode
and create a new run directory under `agent/runs/`, but the filesystem rejected
the write:

```json
{
  "schema": "agentspec.cli_error.v0",
  "error": {
    "type": "PermissionError",
    "message": "[Errno 1] Operation not permitted: '/Users/yimwu/Documents/workspace/Apps/agentracing/agent/runs/research-20260501T164709Z'",
    "retryable": false,
    "command": "aspec run"
  }
}
```

One started research run directory, `research-20260501T164659Z`, was present
after the failed startup sequence. Attempting to record a bounded result against
that run also failed on the run event log:

```json
{
  "schema": "agentspec.cli_error.v0",
  "error": {
    "type": "PermissionError",
    "message": "[Errno 1] Operation not permitted: '/Users/yimwu/Documents/workspace/Apps/agentracing/agent/runs/research-20260501T164659Z/events.jsonl'",
    "retryable": false,
    "command": "aspec run"
  }
}
```

The JSON error is structured and accurate, but the autonomous flow has no
read-only fallback for inspection/research planning. This matters for recurring
automation runs where the control plane may be asked to target a repository
outside the current writable sandbox.

## Implication

AgentSpec autonomous mode currently assumes the target repository is writable
before it can even record a research-mode run. In constrained automation
contexts, that turns "no ready task" into a hard stop instead of allowing a
read-only diagnosis that could produce a useful proposed next action.

## Suggested Next Step

Attach this reproduction to existing
`docs/change-requests/DCR-0025-support-redirected-run-state-for-cross-repo-autonomous-mode.md`.
The DCR already proposes a redirected run-state interface; today's run adds a
fresh reproduction with run id `research-20260501T164709Z`.

The implementation context pack for DCR-0025 should include:

- Detect target repository writability before selecting research mode.
- Return a specific `requires_writable_root` or `readonly_target` state in JSON.
- Optionally support a read-only planning mode that can inspect requirements,
  DCRs, questions, and source snapshots without creating `agent/runs/*`.
- Keep implementation-mode execution blocked unless the selected context pack's
  allowed paths are writable.
