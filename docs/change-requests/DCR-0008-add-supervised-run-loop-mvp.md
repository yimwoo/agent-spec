# DCR-0008: Add supervised run loop MVP

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

Add a local `aspec run loop` command that connects the existing task queue
with supervised-run state. The command selects a ready context pack when one
is not supplied, starts or resumes a local run, and records the deterministic
reviewer verdict for an executor output.

This is an orchestration MVP, not a full background scheduler or model-backed
agent runner. It gives a code agent a single command for the next bounded
step and gives the continuation reviewer a structured place to answer
low-risk "continue?" pauses.

## Motivation

The repository now has the three primitive pieces needed for dogfood: profile
configuration, a local supervised-run protocol, and task queue selection.
The remaining gap is an ergonomic loop entry point that lets an agent proceed
through context packs without asking the human to manually glue those commands
together.

## Proposed Change

- Add `aspec run loop` under the supervised-run CLI.
- Let the loop select `aspec task next` when no context pack is supplied.
- Start a run when no existing run state is found.
- Resume an existing run when `--executor-output` is supplied.
- Preserve existing deterministic policy gates: allowed paths, iteration cap,
  completion only after passed verification, and low-risk continuation
  responses.
- Support JSON output so a future model-backed controller can consume the
  result without scraping prose.

## Impact Assessment

- Supports `R-003` by making generated context packs executable through one
  local control-plane command.
- Supports `R-007` by extending the local CLI workflow.
- Supports `R-127` by turning a selected context pack into a bounded
  supervised run.
- Supports `R-129` by creating a reviewer-mediated continuation path for
  low-risk pauses.
- Code surface: `agentspec/run.py`, `agentspec/cli.py`.
- Test surface: supervised run loop unit and CLI tests.

## Disposition

Classification: `implement-now`.

No ADR is required for this MVP because it implements the accepted protocol
shape from ADR-0003 without introducing external orchestration, background
processes, or model invocation.

## Acceptance Criteria

- `aspec run loop` selects the newest ready context pack when none is supplied.
- `aspec run loop <context-pack>` starts a local run for that pack.
- `aspec run loop --run-id <id> --executor-output <text>` resumes the existing
  run and records a reviewer verdict.
- Dogfood continuation prompts can return `auto_continue` through the loop.
- JSON output includes selected task, state, and reviewer verdict when present.
- `python -m unittest discover -s tests -v` passes.
