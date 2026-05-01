# DCR-0025 Run-Dir Dogfood

Recorded: 2026-05-01

## Context

DCR-0025 added `--run-dir <path>` so cross-repo autonomous/research runs can
store control-plane state outside the target repository. The original failure
mode came from running AgentSpec against `agentracing`, where the loop tried to
write `agent/runs/<run-id>/` in the target checkout before research mode could
start.

## Command

```bash
aspec --root /Users/yimwu/Documents/workspace/Apps/agentracing \
  run loop \
  --mode autonomous \
  --run-id dcr0025-run-dir-dogfood \
  --run-dir /tmp/agentspec-dcr0025-dogfood \
  --json
```

## Observation

The command started an empty-queue research run successfully. The JSON payload
reported:

- `run_id`: `dcr0025-run-dir-dogfood`
- `mode`: `research`
- `run_state_dir`: `/private/tmp/agentspec-dcr0025-dogfood`
- `target_write_requirements`: `reports/dogfood/**`,
  `docs/discovery/open-questions.yml`, `docs/change-requests/**`

Follow-up checks confirmed:

- `/tmp/agentspec-dcr0025-dogfood/dcr0025-run-dir-dogfood/state.yml` exists.
- `/tmp/agentspec-dcr0025-dogfood/dcr0025-run-dir-dogfood/events.jsonl`
  exists.
- `/Users/yimwu/Documents/workspace/Apps/agentracing/agent/runs/dcr0025-run-dir-dogfood`
  was not created.
- `aspec --root /Users/yimwu/Documents/workspace/Apps/agentracing run inspect
  dcr0025-run-dir-dogfood --run-dir /tmp/agentspec-dcr0025-dogfood` reads the
  redirected state.
- The `agentracing` git worktree stayed clean.

## Implication

The DCR-0025 implementation fixes the startup/read path for redirected
cross-repo research state. The CLI also correctly avoids implying that research
mode is fully read-only: durable findings still require the target write paths
listed in the payload if the executor proceeds beyond run startup.

## Suggested Next Step

Proceed to DCR-0022 Item 1. The `agentracing` status output still shows an
attention-needed halted run where the status payload names `last_decision` but
does not expose the review reason, policy flags, test status, or a per-run
recovery command. That makes triage harder for harnesses and operators.
