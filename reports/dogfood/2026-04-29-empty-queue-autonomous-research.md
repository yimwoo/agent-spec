# Empty-Queue Autonomous Research

Run: `research-20260429T164324Z`
Date: 2026-04-29

## Question

With `aspec status` idle and `aspec task next` returning no ready task pack,
what is the next legitimate work surface that does not override existing
governance?

## Findings

1. `DCR-0022` is intentionally classified `defer`. Its operability items are
   discoverable and scoped, but downstream context-pack creation is not
   eligible until a human reclassifies an item to `implement-now` or `spike`.
   Item 2, completion atomicity for run state plus ledger, remains the
   smallest real reliability fix if that reclassification happens.

2. `Q-026` already captures the model-backed `quality_reviewer` soft drift.
   The current code in `agentspec/review.py` is deterministic-only by design:
   it requires `test_status=passed` and explicit acceptance evidence. That is
   aligned enough for now because no false-approval or missed-regression case
   has been recorded.

3. The empty-queue fallback is working as governance, not as an implementation
   loophole. Research mode can record findings under `reports/dogfood/`, but
   it should not promote deferred DCR items or turn open questions into code
   without an explicit classification change.

4. Completing this research run briefly wrote a `<research-mode>` entry to
   `agent/task-ledger.yml`, because the generic run-completion path records
   every `complete` verdict as a task completion. That ledger entry was removed
   from the live workspace after discovery. This is a concrete reliability
   finding adjacent to `DCR-0022` item 2: research-mode completion should not
   mutate the task ledger, and implementation-run completion should remain
   atomic between run state and ledger state.

## Recommendation

Do not create a production context pack from this research run.

The next human-sized choices are:

- Reclassify `DCR-0022` item 2 to `implement-now` if reliability hardening is
  the priority. Include the research-mode ledger exclusion in that slice.
- Keep `Q-026` open until a concrete quality-review miss appears.
- Close housekeeping questions such as `Q-008` or `Q-015` separately if the
  goal is governance cleanup rather than feature movement.
