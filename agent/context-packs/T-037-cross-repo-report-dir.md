# T-037: Cross-Repo Report Dir For Doctor And Drift

Type: `implementation`

Originating DCR: `DCR-0020-support-read-only-report-output-for-cross-repo-doctor-and-drift`

## Goal

Implement the DCR-0020 spike: let `aspec doctor` and `aspec drift` run
against a target repository whose `reports/` tree is not writable
(read-only checkout, sandboxed cross-repo dogfood, etc.) by accepting a
caller-selected destination via `--report-dir <path>`. Default behavior
for normal local use must not change.

## Requirements

- `R-005` Brownfield Doctor mode — `aspec doctor` must remain the
  entrypoint for read-only assessment.
- `R-010` Drift checking against requirements, ADRs, and context packs
  must continue to write a Markdown report.
- `R-034` Brownfield assessment must be read-only by default — the
  target checkout itself stays untouched; only the report destination
  is configurable.
- `R-035` Dogfood AgentSpec on real repositories — this directly
  unblocks the agentracing-style cross-repo loop documented in
  DCR-0020.

## Source Sections

- `D-19` CLI Specification
- `D-23.6` Run state retention (informs the writability error contract)

## Allowed Paths

- `agentspec/doctor.py`
- `agentspec/drift.py`
- `agentspec/cli.py`
- `agentspec/io.py`
- `tests/test_report_dir.py`
- `agent/context-packs/T-037-cross-repo-report-dir.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- Anything outside the allowed paths.
- `docs/change-requests/DCR-0020-*.md` — the DCR stays in its
  `classified/spike` state until the human accepts; this pack ships the
  spike implementation, it does not flip DCR status.

## Tests To Add Or Update

New file `tests/test_report_dir.py` covering:

- `aspec doctor --report-dir <writable-tmp>` writes
  `<writable-tmp>/doctor/repo-scan.yml` and
  `<writable-tmp>/doctor/agent-readiness.md`; the target repo's
  `reports/doctor/` is **not** created.
- `aspec drift --report-dir <writable-tmp>` writes
  `<writable-tmp>/drift/latest.md`; the target repo's
  `reports/drift/` is **not** created.
- Default behavior unchanged: `aspec doctor` (no `--report-dir`)
  still writes to `<root>/reports/doctor/`; same for drift.
- Both commands fail with a clear message when the chosen destination
  (default or `--report-dir`) cannot be written. Use a tempdir made
  read-only via `chmod 0o500` for the negative case; restore
  permissions in the test teardown so the temp tree can be removed.

## Acceptance Criteria

- `aspec doctor --report-dir <writable-dir>` runs against a target
  repository and writes both report artifacts under
  `<writable-dir>/doctor/`. The target's own `reports/doctor/`
  directory is not created or mutated.
- `aspec drift --report-dir <writable-dir>` runs against a target
  repository and writes the drift report under
  `<writable-dir>/drift/`. The target's own `reports/drift/` directory
  is not created or mutated.
- Default behavior is unchanged for normal local use: with no
  `--report-dir`, both commands continue to write to
  `<root>/reports/<command>/`.
- When neither the default destination nor the caller-selected
  destination is writable, both commands raise a clear error before
  doing analysis work. The error message names the path that failed
  the writability check.
- Full test suite green: `python -m pytest -q -p no:cacheprovider`.
- The CLI `--help` for `doctor` and `drift` lists the new
  `--report-dir` flag.
