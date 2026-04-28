# DCR-0013: Add next executor prompt handoff

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Add a supervised-run handoff command that renders the next executor prompt
from durable run state and reviewer events.

The prompt gives harnesses a stable, machine-readable way to continue a main
code agent after the continuation reviewer returns `auto_continue`, without
requiring a human to copy text out of raw event logs.

## Motivation

The model-backed continuation reviewer can already return structured
`message_to_executor` text, but that response is only printed during
`aspec run resume` and stored as an event. A harness needs a repeatable command
to reconstruct the next instruction after process restarts or between agents.

## Proposed Change

- Add `aspec run prompt <run-id>` with plain-text and `--json` output.
- Build the prompt from the run state, active context pack, allowed paths,
  latest reviewer verdict, latest controller response, iteration budget, and
  verification reminder.
- Keep the command read-only; it must not mutate run state or task ledger.
- Refuse prompt generation for terminal runs (`complete`, `halted`, `aborted`)
  so harnesses do not continue after a stop condition.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by preserving bounded run state and allowed-path context in
  the handoff prompt.
- Supports `R-129` by making reviewer feedback consumable by a next executor
  iteration.
- Code surface: `agentspec/run.py`, `agentspec/cli.py`.
- Test surface: supervised-run prompt tests.

## Disposition

Classification: `implement-now`.

This completes the next small step after DCR-0012: the reviewer can produce a
structured continuation response, and the harness can now retrieve the next
executor instruction from durable state.

## Acceptance Criteria

- `aspec run prompt <run-id>` prints a next executor prompt for a started or
  running run.
- After a reviewer `auto_continue`, the prompt includes the reviewer
  `message_to_executor`.
- `--json` output includes the prompt, context pack, allowed paths, last
  decision, and status.
- Terminal run states refuse continuation prompts.
- `python -m unittest discover -s tests -v` passes.
