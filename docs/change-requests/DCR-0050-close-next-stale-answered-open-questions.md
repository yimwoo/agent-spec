# DCR-0050: Close next stale answered open questions

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

Mark the next conservative set of stale open-question entries as answered when
the repository already has accepted, durable evidence for the decision.

This is traceability cleanup only. It does not change runtime behavior or
reclassify strategic questions that are still genuinely unresolved.

## Motivation

The Quality GC report still flags 13 open questions. Some are real product or
roadmap questions and should remain open, but a small subset has explicit
accepted evidence:

- `Q-009`: the default readiness gate is 60, reflected in `init_project`,
  task-creation enforcement, and the accepted plugin guidance around readiness
  recovery.
- `Q-015`: DCR IDs are globally sequential and repository-unique, reflected in
  ADR-0002's default policy and the committed DCR README.

Leaving these as open creates avoidable noise for future agents.

## Proposed Change

- Mark `Q-009` answered by `DCR-0033/R-168` and `R-104`: default readiness
  gating is a score threshold of 60 for implementation work.
- Mark `Q-015` answered by `ADR-0002` and `docs/change-requests/README.md`:
  DCR IDs are globally sequential and unique across the repository.
- Preserve each question's existing `impact`, `source_sections`, and
  `raised_by` fields.
- Leave strategic or intentionally deferred questions open.

## Impact Assessment

Affected artifacts:

- `docs/discovery/open-questions.yml`
- `docs/change-requests/DCR-0050-close-next-stale-answered-open-questions.md`
- `docs/traceability/requirements.yml`
- `agent/context-packs/T-080-close-next-stale-answered-open-questions.md`
- `agent/task-ledger.yml`
- `agent/handoff.yml`

New requirement:

- `R-185`: next stale answered open questions cite accepted decision evidence.

## Disposition

Classification: `implement-now`.

No ADR is required. This is metadata cleanup for decisions already captured by
accepted AgentSpec artifacts.

## Acceptance Criteria

- `Q-009` has `status: answered` with an `answered_by` reference to
  `DCR-0033/R-168; R-104`.
- `Q-015` has `status: answered` with an `answered_by` reference to
  `ADR-0002; docs/change-requests/README.md`.
- Existing non-status metadata on both entries is preserved.
- Open questions without accepted decision evidence remain open.
- The open-question and requirement ledgers remain parseable.
