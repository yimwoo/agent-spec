# DCR-0020: Support read-only report output for cross-repo doctor and drift

| Field | Value |
|---|---|
| Status | classified |
| Classification | spike |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

During the `agentracing` autonomous dogfood cycle on 2026-04-28,
`aspec doctor` and `aspec drift` were useful control-plane checks but could not
run against the sibling target checkout because both commands attempted to
write reports inside that checkout. The automation sandbox allowed reading the
target repository but not writing there, so the checks failed before producing
diagnostics.

AgentSpec should support a read-only/report-redirect mode for brownfield and
cross-repo analysis, especially when autonomous research mode is using
AgentSpec as the control plane for another repository.

## Motivation

This gap affects the same operating model AgentSpec is designing for:
read-only brownfield assessment, dogfood learning capture, and bounded
autonomous research. A controller repository may be writable while the target
repository is read-only or deliberately protected. In that setup, analysis
commands should still be able to emit diagnostics to stdout, a caller-selected
output directory, or the controller repo's dogfood reports without mutating the
target checkout.

Observed evidence:

- In `/Users/yimwu/Documents/workspace/Apps/agentracing`,
  `aspec doctor` failed with `Operation not permitted:
  '/Users/yimwu/Documents/workspace/Apps/agentracing/reports/doctor/repo-scan.yml'`.
- In the same target repository, `aspec drift` failed with `Operation not
  permitted: '/Users/yimwu/Documents/workspace/Apps/agentracing/reports/drift/latest.md'`.
- `aspec task next` was able to read the target and report `No ready task
  context pack found.`, so the blocker was report persistence rather than
  target discovery.

## Proposed Change

Spike a CLI/reporting contract that lets `doctor` and `drift` run against a
target repository without requiring write access to that target. Candidate
interfaces:

- `--report-dir <path>` to redirect generated report artifacts.
- `--stdout` or `--json` for callers that only need machine-readable output.
- An autonomous/research-mode default that writes dogfood evidence under the
  controller repository when the target is read-only.

The spike should preserve the current default behavior for normal local use,
where writing `reports/doctor/` and `reports/drift/` inside the analyzed repo is
appropriate.

## Impact Assessment

Related requirements:

- `R-005`: Brownfield Doctor mode.
- `R-010`: drift checking against requirements, ADRs, and context packs.
- `R-034`: brownfield assessment must be read-only by default.
- `R-035`: dogfood AgentSpec on real repositories.
- `R-139`: stable dogfood finding capture.
- `R-142`: autonomous empty-queue research mode writes only bounded artifacts.

Likely affected modules:

- `agentspec/doctor.py`: report destination selection and stdout/json mode.
- `agentspec/drift.py`: report destination selection and stdout/json mode.
- `agentspec/cli.py`: common flags and help text.
- `agentspec/run.py`: autonomous/research-mode handling for read-only targets.
- `tests/`: regression coverage for read-only target analysis with redirected
  reports.

## Disposition

Recommendation: keep this DCR as a spike until the desired report interface is
chosen. The smallest implementation should add a shared report-destination
helper and cover both `doctor` and `drift` with tests that run against a
read-only fixture target.

## Acceptance Criteria

- `aspec doctor --report-dir <writable-dir>` can analyze a read-only target and
  writes all report artifacts to the selected directory.
- `aspec drift --report-dir <writable-dir>` can analyze a read-only target and
  writes all report artifacts to the selected directory.
- The default behavior remains unchanged for normal writable repositories.
- The commands return clear errors when neither the default target report path
  nor the caller-selected report path is writable.
- Tests cover read-only target analysis for both commands.
