# DCR-0052: Project metrics surface for feedback loops

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Promote the remaining DCR-0022 Item 3 backlog item into an
implementation-ready metrics surface for feedback loops.

AgentSpec already exposes raw status counts, run records, task ledgers, and
Quality GC reports. This change adds a read-only `aspec metrics` surface that
rolls those existing artifacts into durable operational metrics a harness,
dashboard, or quality reviewer can consume without reverse-engineering the
status payload.

## Motivation

DCR-0022 deliberately deferred metrics because the status surface was still
settling. Since then, AgentSpec has shipped run recovery context, task
handoff state, app-build evaluator roles, UI evidence hooks, and Quality GC.
Those pieces make the useful first metrics set clearer:

- completion and ready-work rates for tasks;
- run completion, pause/halt, abort, and verification pass rates;
- policy-flag and reviewer-fallback aggregations;
- DCR/open-decision pressure;
- latest Quality GC grade and cadence.

This closes the last unpromoted DCR-0022 item and gives future background
cleanup or self-tuning loops a stable data surface.

## Proposed Change

- Add `agentspec.metrics` with schema `agentspec.metrics.v0`.
- Add `aspec metrics` with `--json` support and a compact human summary.
- Reuse existing repository artifacts only: project status, run state/events,
  task ledger, DCR metadata, requirements, and `reports/quality/latest.yml`.
- Include derived rates as rounded ratios from existing counts; do not invent
  unavailable data.
- Include cycle-time rollups when run records have both `created_at` and
  `updated_at`.
- Leave report writing out of this slice. The first surface is read-only so
  harnesses can evaluate it before a persistent metrics report format is
  committed.

## Impact Assessment

Affected existing backlog:

- Promotes DCR-0022 Item 3, "Metrics surface for feedback loops."
- Leaves no unpromoted items in DCR-0022 once this ships.

Affected requirements:

- `R-007`: local/CI CLI reliability for automation harnesses.
- `R-035`: dogfood AgentSpec on real repositories.
- `R-128`: supervised run records per-iteration evidence.
- `R-135`: autonomous-mode progress remains auditable and recoverable.
- `R-183`: Quality GC provides recurring project quality state.

New requirement:

- `R-187`: AgentSpec exposes a read-only project metrics surface.

Affected artifacts:

- `agentspec/cli.py`
- `agentspec/metrics.py`
- `agentspec/status.py`
- `tests/test_metrics_cli.py`
- `docs/change-requests/DCR-0022-post-t040-operability-bundle.md`
- `docs/traceability/requirements.yml`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a read-only aggregation over existing durable
artifacts and does not alter run-loop policy, task scheduling, or reviewer
behavior. A later DCR can add persisted metrics reports or automation
thresholds after consumers validate the schema.

## Acceptance Criteria

- `aspec metrics --json` emits schema `agentspec.metrics.v0`.
- The metrics payload includes readiness, requirements, DCRs, tasks, runs,
  verification, policy flags, cycle-time rollups, and latest Quality GC
  summary when available.
- Rates are deterministic and handle empty denominators without division
  errors.
- Human `aspec metrics` output summarizes the most important feedback-loop
  signals.
- DCR-0022 records Item 3 as promoted to this DCR.
- Focused metrics tests and full unittest discovery pass.
