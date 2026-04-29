# T-042: CLI JSON Error Envelope

Type: `implementation`

Originating DCR: `DCR-0021-add-project-status-surface`

## Goal

Close the only P1 finding from the T-040 code review: the top-level
CLI exception handler always prints plain stderr text, even when the
caller passed `--json`. Harnesses consuming `aspec run step --json`,
`aspec run package --json`, `aspec status --json`, etc. cannot
distinguish error type, retryability, or recovery context — they get
an opaque non-zero exit code.

This pack adds a stable `agentspec.cli_error.v0` envelope and emits it
to stdout when the failing command was invoked with `--json`. Plain
stderr text remains the default for non-JSON callers.

The change is treated as an operability fix on T-040 (which introduced
the project-status JSON contract). Schema name versioning matches the
existing `agentspec.project_status.v0` / `agentspec.task_ledger.v0`
family. Per the dogfood discipline, T-042 cites DCR-0021 as its
origin since the gap surfaced during T-040's code review.

## Requirements

- `R-007` Local CLI must be reliable for harnesses, not just humans.
  A consumer of `aspec ... --json` cannot reliably loop without
  structured error information.
- `R-128` Run-state and summary projections become harness-consumable
  only when failures are also harness-consumable.

## Source Sections

- `D-19` CLI Specification
- `D-23.6` Run state retention (informs the envelope's relationship
  to existing run-state schemas)

## Allowed Paths

- `agentspec/cli.py`
- `tests/test_cli_json_errors.py`
- `agent/context-packs/T-042-cli-json-error-envelope.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- Anything outside the allowed paths.
- `docs/change-requests/*.md` — no DCR is being filed or modified by
  this pack. The operability bundle DCR (separate file, separate
  commit) is its own slice.
- `docs/source/`, `docs/spec/`, `docs/traceability/` — no
  schema/source change.

## Tests To Add Or Update

New file `tests/test_cli_json_errors.py` covering:

- A failing command invoked with `--json` writes a JSON envelope to
  stdout; stderr stays empty for the envelope content.
- The envelope `schema` field is exactly `agentspec.cli_error.v0`.
- The envelope's `error.type` matches the exception class name
  (`FileNotFoundError`, `ValueError`).
- The envelope's `error.retryable` is `False` for known input errors
  (`ValueError`, `FileNotFoundError`); `True` for transient classes
  (`TimeoutError`, `ConnectionError`) — verified via the helper
  function rather than triggering a real network failure.
- A failing command invoked **without** `--json` still writes plain
  text to stderr (back-compat).

## Acceptance Criteria

- `aspec dcr accept DOES-NOT-EXIST --json` exits non-zero and prints a
  JSON object to stdout matching:

  ```json
  {
    "schema": "agentspec.cli_error.v0",
    "error": {
      "type": "FileNotFoundError",
      "message": "...",
      "retryable": false,
      "command": "agentspec dcr"
    }
  }
  ```

- The same command without `--json` exits non-zero with plain
  `agentspec: error: ...` on stderr (current behavior, unchanged).
- `python -m pytest -q -p no:cacheprovider` — green.
- Existing tests unchanged (no shifts in 178 → ≥178).
