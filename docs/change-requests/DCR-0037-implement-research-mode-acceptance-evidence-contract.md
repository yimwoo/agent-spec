# DCR-0037: Implement research-mode acceptance evidence contract

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-02 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-02 |
| Confidence | medium |

## Summary

Implement the research-mode acceptance evidence contract designed by DCR-0035.

Research-mode runner results should be able to provide structured completion
evidence so the control plane can distinguish an adequately evidenced research
proposal from an ambiguous completion claim.

## Motivation

DCR-0035 found that research-mode completion currently depends on free-form
executor wording. That is too fragile for autonomous research runs: a result can
write only durable research artifacts and pass verification, yet still halt
because the quality reviewer cannot recognize the evidence.

## Proposed Change

- Extend `agentspec.runner_result.v0` parsing with optional
  `acceptance_evidence`.
- Include a research-mode evidence template in runner packages when the active
  run state is research mode.
- Reject `test_status=passed` research results without valid
  `acceptance_evidence` before mutating run state.
- Thread valid evidence into `resume_run`, reviewer decisions, executor events,
  and quality signoff.
- Keep existing hard limits unchanged: destructive git, credential patterns,
  forbidden paths, and auto-acceptance attempts still halt first.

## Impact Assessment

Affected existing requirements:

- `R-142`: empty-queue autonomous research mode writes bounded durable findings.
- `R-144`: autonomous/research complete requires quality reviewer signoff.
- `R-171`: DCR-0035 spike contract becomes executable.

Likely new requirement:

- `R-172`: Research-mode runner results use structured acceptance evidence for
  deterministic completion.

Likely affected artifacts:

- `agentspec/runner.py`
- `agentspec/run.py`
- `agentspec/review.py`
- `tests/test_runner_package.py`
- `tests/test_research_mode.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This implements the accepted DCR-0035 spike without changing
the supervised-run protocol for non-research runs.

## Acceptance Criteria

- Research-mode runner packages include an `acceptance_evidence` result
  template.
- `aspec run result` rejects passed research results that omit or provide
  invalid `acceptance_evidence`, and run state remains unchanged.
- A research-only proposal with valid evidence can complete even when
  `executor_output` is terse.
- An unclassified research pause without valid completion evidence still logs a
  finding and auto-continues.
- Research-mode hard limits still halt before evidence can approve the run.
