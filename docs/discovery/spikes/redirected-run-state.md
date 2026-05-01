# Spike: Redirected Run State

Date: 2026-05-01
Originating DCR: `DCR-0025`
Context pack: `T-056`
Related requirements: `R-007`, `R-034`, `R-035`, `R-128`, `R-135`, `R-139`, `R-142`

## Summary

DCR-0025 is implementation-ready without a new ADR. The safest interface is
`--run-dir <path>` on every `aspec run` subcommand that reads or mutates run
state. The default remains `<root>/agent/runs/<run-id>/`; with `--run-dir`,
the state for a run lives at `<run-dir>/<run-id>/`.

Use `--run-dir`, not `--state-dir`, because the public command group is already
`aspec run` and the destination contains the whole run record: `state.yml`,
`events.jsonl`, and autonomous/research `summary.yml`.

## Code Inventory

All durable run-state persistence currently passes through these helpers in
`agentspec/run.py`:

- `_run_dir(root, run_id)`
- `_state_exists(root, run_id)`
- `_write_state(root, run_id, state)`
- `_append_event(root, run_id, event)`
- `_load_events(root, run_id)`
- `_maybe_write_run_summary(root, run_id, state)`
- `load_run_state(root, run_id)`

The public callers that need the destination contract are:

- `start_run`
- `start_research_run`
- `resume_run`
- `loop_run`
- `step_run`
- `build_next_executor_prompt`
- `inspect_run`
- `abort_run`
- runner helpers: `package_run`, `submit_runner_result`, `run_demo`, and
  `execute_runner`
- CLI subcommands: `start`, `resume`, `loop`, `step`, `package`, `result`,
  `demo`, `exec`, `inspect`, `prompt`, and `abort`

`complete_context_pack_run` writes local completion/backfill run state through
the same helpers, but it is a task utility (`aspec task complete`), not a
cross-repo autonomous run entrypoint. It can stay default-only for the first
implementation slice unless a later DCR asks for redirected task-completion
state.

## Recommended Contract

Add a `run_dir: Path | None = None` parameter to run-state APIs. The helper
contract should be:

```text
effective_run_root(root, run_dir)
  None       -> <root>/agent/runs
  otherwise  -> <run_dir>

run_record_dir(root, run_id, run_dir)
  -> effective_run_root(root, run_dir) / run_id
```

When `run_dir` is explicit, preflight the destination before mutating state.
Reuse the existing `ensure_writable_dir` pattern from DCR-0020, but tune the
error message for run state. A failed JSON CLI command should therefore return
the existing `agentspec.cli_error.v0` envelope with a `PermissionError`.

The run state should include a small audit field such as:

```json
"run_state_dir": "/absolute/path/to/effective/run/root"
```

This makes redirected state inspectable without changing the schema version or
breaking existing consumers.

## CLI Surface

Add `--run-dir <path>` consistently to:

- `aspec run start`
- `aspec run resume`
- `aspec run loop`
- `aspec run step`
- `aspec run package`
- `aspec run result`
- `aspec run demo`
- `aspec run exec`
- `aspec run inspect`
- `aspec run prompt`
- `aspec run abort`

Runner packages should include `--run-dir` in `report_back.argv` and
`legacy_step_argv` when the state store is redirected. Otherwise an external
runner can start from redirected state but report its result back to the wrong
default directory.

## Research Mode Caveat

Redirected run state does not make research mode fully read-only. Research mode
may still write durable findings to the target repository:

- `reports/dogfood/**`
- `docs/discovery/open-questions.yml`
- `docs/change-requests/**`

The implementation should report this explicitly when a redirected
autonomous/research run is started. A small field in the JSON result is enough,
for example:

```json
"target_write_requirements": [
  "reports/dogfood/**",
  "docs/discovery/open-questions.yml",
  "docs/change-requests/**"
]
```

This preserves DCR-0025's honesty constraint: `--run-dir` solves the
`agent/runs/` failure, but not every later research artifact write.

## Requirements To Register

Register four implementation requirements:

- Redirected run-state storage for `aspec run`.
- Consistent redirected state across run subcommands and runner adapters.
- Default local behavior and structured unwritable-destination failures.
- Explicit reporting of remaining research-mode target writes.

These should remain `proposed-pending-acceptance` until their implementation
pack verifies.

## Recommendation

Proceed with one implementation pack. It should use tests first and cover:

- default state still writes under `<root>/agent/runs/<run-id>/`
- redirected state writes under `<run-dir>/<run-id>/`
- `resume`, `inspect`, `prompt`, `abort`, `package`, and `result` reuse the
  redirected store
- `run loop --mode autonomous --json --run-dir <writable>` can start research
  state when the default `agent/runs` path is unwritable
- JSON errors keep the `agentspec.cli_error.v0` envelope when the selected
  destination is not writable
- runner report-back commands preserve `--run-dir`
