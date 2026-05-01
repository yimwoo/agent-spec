# DCR-0028: Run status recovery context

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Promote DCR-0022 Item 1 into an implementation-ready slice: enrich each
`aspec status --json` run record with enough recovery context for a harness or
operator to triage paused and halted runs without first opening the raw
`events.jsonl` or calling `aspec run inspect`.

The status surface already reports `last_decision`, but not the surrounding
reason, policy flags, verification status, or a copy-pastable per-run recovery
command. This DCR adds those fields while preserving the current top-level
status recommendation.

## Motivation

The DCR-0025 dogfood pass against `agentracing` confirmed redirected run state
works, but the target status output still surfaced a historical halted run with
only `last_decision: pause_for_human`. The missing context is exactly what
DCR-0022 Item 1 captured after the T-040 status review: users can see that a
run needs attention, but not why, what policy flags were involved, whether
tests passed, or which command should be run for that specific record.

As AgentSpec becomes a control-plane API for autonomous loops, dashboards, and
cross-repo dogfood, status records should carry the recovery breadcrumbs
directly.

## Proposed Change

Extend run records produced by `agentspec.status.build_project_status` with:

- `last_review_reason`: reviewer reason string from the latest
  `reviewer_verdict` event, when available.
- `policy_flags`: policy flags from the latest `reviewer_verdict` event,
  defaulting to an empty list.
- `test_status`: latest executor test status, when available.
- `last_event_ref`: a stable pointer to the latest decision event in
  `events.jsonl`.
- `recovery_command`: a command appropriate for the run status, such as
  `aspec run inspect <id>` for halted runs or `aspec run prompt <id>` for
  active runs.

For summary-only runs where raw events are absent, the new fields should be
present with conservative empty/null values and a recovery command based on the
status.

## Impact Assessment

Affected requirements:

- `R-007`: CLI output remains predictable for harnesses.
- `R-128`: run-state evidence becomes easier to consume.
- `R-135`: autonomous/research pauses and halts become easier to recover.

Affected modules:

- `agentspec/status.py`
- `tests/test_status_cli.py`

Related backlog:

- Promotes DCR-0022 Item 1.
- Leaves DCR-0022 Items 3 and 4 deferred.

## Disposition

Classification: `implement-now`.

One implementation pack is enough. No ADR is required because this enriches an
existing JSON status schema with optional recovery fields and does not change
the run protocol or policy decisions.

## Acceptance Criteria

- `aspec status --json` run records include `last_review_reason`,
  `policy_flags`, `test_status`, `last_event_ref`, and `recovery_command`.
- Paused/halted runs expose the latest reviewer reason and policy flags from
  `events.jsonl` when the event log exists.
- Active runs expose a recovery command pointing to `aspec run prompt <id>` or
  the current continuation path.
- Summary-only runs remain visible and use null/empty recovery context rather
  than failing.
- Existing human-readable status output remains backward-compatible.
