# DCR-0034: Promote DCR-0022 recovery CLI aliases

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

Promote DCR-0022 Item 4 into implementation: add recovery-oriented top-level
CLI aliases that help users continue from the current AgentSpec project state
without remembering the full `run` subcommand set.

The aliases are thin shims over existing behavior. They do not introduce new run
state, new schemas, or new execution semantics.

## Motivation

DCR-0022 captured post-status operability polish. Items 1 and 2 have already
been promoted and shipped via DCR-0028 and DCR-0024. Item 3 remains a metrics
spike candidate. Item 4 is now the clear next low-risk slice: reduce CLI
friction for the common "what do I do next?" path.

The current answer exists in `aspec status` as a recommendation string, but the
operator still has to copy or infer the underlying command.

## Proposed Change

Add top-level aliases:

- `aspec next-action`
- `aspec continue`

Both commands read `build_project_status` and dispatch using existing functions:

- attention run: inspect the first attention-needed run;
- active run: print the next executor prompt for the first active run;
- ready task: start or resume the run loop for the next ready task;
- no action: print the existing status recommendation and exit non-zero.

The command should keep the same prioritization as project status:
attention-needed runs before active runs before ready tasks.

## Impact Assessment

Affected existing requirements:

- `R-007`: CLI ergonomics and local workflow support.
- `R-128`: supervised-run recovery and continuation are easier to discover.
- `R-135`: paused or halted run triage is easier from project status.
- DCR-0022 Item 4: promoted from deferred backlog to implementation.

Likely new requirement:

- `R-169`: AgentSpec exposes top-level recovery aliases that dispatch to the
  current status recommendation without changing underlying run semantics.

Likely affected artifacts:

- `agentspec/cli.py`
- `tests/test_status_cli.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This is an ergonomic CLI alias over existing status and run
behavior.

## Acceptance Criteria

- `aspec next-action` inspects an attention-needed run when one exists.
- `aspec continue` prints the active run prompt when no attention run exists
  and an active run is available.
- `aspec next-action` starts the run loop for the next ready task when no
  attention or active run exists.
- If there is no action, the command prints the existing status recommendation
  and exits non-zero.
- Existing `aspec status`, `aspec task next`, and `aspec run *` behavior remains
  backward-compatible.
