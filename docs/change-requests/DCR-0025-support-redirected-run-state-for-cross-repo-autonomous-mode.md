# DCR-0025: Support redirected run state for cross-repo autonomous mode

| Field | Value |
|---|---|
| Status | classified |
| Classification | spike |
| Submitted | 2026-04-30 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-30 |
| Confidence | medium |

## Summary

Add a narrow cross-repo autonomous-mode spike for redirecting supervised run
state away from the analyzed target repository when the target checkout is
read-only or outside the active write sandbox.

This extends the same dogfood operating model addressed by DCR-0020 for
`doctor` and `drift`: AgentSpec can already redirect report artifacts with
`--report-dir`, but `aspec run loop --mode autonomous --json` still attempts
to create `agent/runs/<run-id>/` inside the target repository before research
mode can record any durable findings.

## Motivation

The 2026-05-01 `agentracing` autonomous dogfood cycle had no ready task pack,
so the requested control-plane path was to enter autonomous research mode.
Instead, startup failed before run state existed:

```text
PermissionError: [Errno 1] Operation not permitted:
'/Users/yimwu/Documents/workspace/Apps/agentracing/agent/runs/research-20260501T041956Z'
```

In the same checkout, `aspec task next` succeeded and reported no ready context
pack. This means target discovery and task selection were read-only compatible,
but autonomous run-state persistence was not.

The 2026-05-01 08:56 PDT follow-up cycle reproduced the same class of issue in
two places. `aspec run loop --mode autonomous --json` returned a JSON
`PermissionError` while trying to create
`agent/runs/research-20260501T125612Z`, and the later attempt to submit a
research result for `research-20260501T125602Z` failed while appending
`agent/runs/research-20260501T125602Z/events.jsonl`. This shows the redirected
state contract needs to cover both run startup and subsequent result/reviewer
event writes, not only initial directory creation.

DCR-0020 and T-037 solved this class of issue for report output by adding
`--report-dir` to `doctor` and `drift`. The run loop needs an equivalent
contract or preflight behavior for `agent/runs/` so cross-repo dogfood cycles
can either write state in a caller-selected location or fail with an actionable
JSON envelope before losing the selected control-plane context.

## Proposed Change

Spike a redirected run-state interface for `aspec run` commands. Candidate
interfaces:

- `--run-dir <path>` or `--state-dir <path>` on `aspec run loop`, `start`,
  `resume`, `result`, `exec`, `inspect`, and related commands that need the
  same state store.
- A config key for automation/controller use, so repeated cross-repo cycles do
  not need to pass the flag on every command.
- A preflight helper parallel to the report-output writability checks from
  T-037, returning a structured CLI error when neither the default
  `<target>/agent/runs/` path nor the redirected path is writable.

The spike should preserve the current default behavior for normal local
repositories: run state remains under the target repository's `agent/runs/`
unless the caller opts into a redirected state store.

The spike should also decide whether redirected run state is sufficient for
research-mode durable output. If research mode still writes
`docs/change-requests/**`, `docs/discovery/open-questions.yml`, or
`reports/dogfood/**` in the target repo, the CLI should surface that remaining
write requirement explicitly rather than implying fully read-only operation.

## Impact Assessment

Affected requirements:

- `R-007`: local and CI CLI reliability for harnesses and automations.
- `R-034`: brownfield assessment should be read-only by default where possible.
- `R-035`: dogfood AgentSpec on real repositories.
- `R-128`: supervised run state records per-iteration evidence.
- `R-135`: autonomous-mode progress remains auditable and recoverable.
- `R-139`: dogfood findings have a stable durable location.
- `R-142`: empty-queue autonomous research mode writes only bounded artifacts.

Likely affected modules:

- `agentspec/run.py`: run-state path construction, loading, and persistence.
- `agentspec/cli.py`: shared run-state destination options and help text.
- `agentspec/io.py` or a sibling helper: writable-directory preflight.
- `agentspec/status.py`: optional visibility into redirected state stores.
- `tests/`: regression coverage for read-only target checkouts with redirected
  run state.

Related prior work:

- DCR-0020 / T-037 added redirected report output for `doctor` and `drift`.
- DCR-0024 / T-044 tightened research-mode ledger writes and completion
  atomicity, but did not address run-state destination selection.

## Disposition

Classification: `spike`.

Recommendation: keep this scoped to run-state destination semantics first.
Do not broaden it into a full multi-repository controller architecture unless
the spike proves the CLI cannot safely share one state store across `run`
subcommands.

If accepted, generate one small implementation context pack that starts with a
test fixture or temporary checkout whose target `agent/runs/` is unwritable
while a caller-selected state directory is writable.

## Acceptance Criteria

- The future context pack cites `DCR-0025`, `R-007`, `R-034`, `R-035`,
  `R-128`, `R-135`, `R-139`, and `R-142`.
- `aspec run loop --mode autonomous --json` can start or resume run state
  using a caller-selected writable directory when the target repository's
  `agent/runs/` path is not writable.
- Related `aspec run` subcommands that read or mutate the same run state use
  the same destination contract consistently.
- The default local behavior remains unchanged for writable repositories.
- If durable research artifacts still require target-repository writes, the CLI
  documents and reports that remaining requirement clearly.
- Tests cover default state storage, redirected state storage, unwritable
  default path failure, and JSON error-envelope behavior.
