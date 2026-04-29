# T-038: DCR-0020 Acceptance + Q-026 Model-Backed Quality Reviewer

Type: `implementation`

Originating DCR: `DCR-0020-support-read-only-report-output-for-cross-repo-doctor-and-drift`

## Goal

Two small bookkeeping moves driven by the consolidation pass:

1. Accept DCR-0020 now that T-037 shipped the spike implementation
   with full test coverage and a passing live smoke test.
2. File `Q-026` so the model-backed `quality_reviewer` gap leaves
   "code comment" land and joins the discovery surface as a tracked
   open question. Today the gap is only described in a docstring at
   `agentspec/review.py:243+`; that makes it invisible to anyone
   reading `docs/discovery/open-questions.yml` to plan work.

## Requirements

- `R-126` Drift compliance reporting must reflect the durable state of
  acceptance — flipping DCR-0020's status to `accepted` keeps the
  drift report's DCRs column accurate going forward.
- `R-127` Continuation reviewer + `R-129` quality reviewer profiles
  are the load-bearing requirements behind the open question being
  filed.

## Source Sections

- `D-12.17` Reviewer profiles (motivates Q-026)
- `D-18` Schema surface for open questions and DCRs

## Allowed Paths

- `docs/change-requests/DCR-0020-support-read-only-report-output-for-cross-repo-doctor-and-drift.md`
- `docs/discovery/open-questions.yml`
- `agent/context-packs/T-038-dcr-0020-acceptance-and-quality-reviewer-question.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- Anything outside the allowed paths.
- `agentspec/review.py` — Q-026 captures the gap; it does not
  implement the model-backed branch.

## Tests To Add Or Update

- No code-test changes. The full test suite must still pass
  (`python -m pytest -q -p no:cacheprovider`).
- `aspec compile` must remain idempotent and report the new question.

## Acceptance Criteria

- DCR-0020's `Status` row is `accepted`; `Decided on` is today's date
  (2026-04-28). `aspec dcr list` shows it accepted.
- `docs/discovery/open-questions.yml` has a new `Q-026` entry with:
  - status `open`
  - clear question text describing the gap (deterministic-only
    `quality_reviewer` vs. ADR-0003's "should use a stronger model"
    guidance)
  - `raised_by: "ADR-0003"` and `source_sections: ["D-12.17"]`
  - explicit MVP-acceptance note that the gap is intentional until
    concrete failure cases motivate the model-backed branch
- `python -m pytest -q -p no:cacheprovider` — green.
- `aspec compile` — idempotent on the live repo.
