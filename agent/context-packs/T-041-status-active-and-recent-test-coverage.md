# T-041: Status Test Coverage — Active And Recent Blocks

Type: `review`

Originating DCR: `DCR-0021-add-project-status-surface`

## Goal

Close the test-coverage gap surfaced by the T-040 review (NOTE 1):
`format_project_status` emits three optional sections for runs —
"Attention Runs:", "Active Runs:", and "Recent Runs:" — but the
existing human-format test only asserts the attention block. The seed
in `test_status_cli.py` already populates an active run and a
summary-only recent run, so the gap is "missing assertions", not
"missing fixture".

Add a focused test that asserts the active and recent blocks render
correctly given the same seed. Keeps the safety net tight as the
human format gets more uses.

## Requirements

- `R-007` Local CLI must remain reliable; status output is part of
  the operator-facing surface.
- `R-128` Run-state and summary projections must be visible to the
  status surface.

## Source Sections

- `D-19` CLI Specification
- `D-24` Evaluation and Observability

## Allowed Paths

- `tests/test_status_cli.py`
- `agent/context-packs/T-041-status-active-and-recent-test-coverage.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- `agentspec/status.py` — no production change. The behaviour is
  already correct; only test coverage is being expanded.
- Anything outside the allowed paths.

## Tests To Add Or Update

- `tests/test_status_cli.py` — add a new test method that asserts the
  "Active Runs:" and "Recent Runs:" headers and the relevant run ids
  appear in the rendered human format. Keep the existing
  attention-focused test intact so each test stays narrowly scoped.

## Acceptance Criteria

- New test method asserts at minimum:
  - the literal string `"Active Runs:"` appears in the human output
  - the active run id (`run-active`) appears in the output
  - the literal string `"Recent Runs:"` appears in the human output
  - the summary-only run id (`run-summary-only`) appears in the
    output (it lives only in the recent block, not in active or
    attention, so its presence proves the recent block rendered)
- `python -m pytest -q -p no:cacheprovider` — green.
- The existing `test_human_status_mentions_next_and_attention_runs`
  test continues to pass unchanged.
