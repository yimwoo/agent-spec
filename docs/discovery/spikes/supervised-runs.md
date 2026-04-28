# Spike: Supervised Runs / Agent Reply Loop

Date: 2026-04-28
Originating DCR: `DCR-0001`
Context pack: `T-004`
Related requirements: `R-127`, `R-128`, `R-129`, `R-130`

## Summary

The idea is sound, but the unit should be a supervised run controller rather
than a second agent that blindly says `continue`.

The controller can review the executor agent's latest response, current task
context pack, touched paths, tests, and policy state. When the executor pauses
for a low-risk continuation prompt, the controller sends a scoped continuation
message. When the executor asks for a prioritization, scope, security, or
product decision, the controller pauses for the human.

This matches the existing architecture: context packs remain the work unit
(`D-07`, `D-12.12`), shared state is file-backed (`D-07`, `D-23.6`), and write
automation stays behind policy gates (`D-12.17`, `D-23.4`).

## Dogfood Scenario

Executor reply:

```text
Want me to proceed with T-008, or pick one of the others?
```

If the active run was already started from
`agent/context-packs/T-008-dcr-accept-cascade-fix.md`, the reviewer/controller
may classify this as `auto_continue`. The message should be:

```text
Continue with T-008. Use the T-008 context pack as the active scope, work only
inside its allowed paths, and run its listed verification before reporting
completion.
```

If no active run state names `T-008`, the same executor reply must become
`pause_for_human`, because "pick one of the others" is a prioritization choice.

## Proposed Protocol

The first implementation should be file-backed and local-first:

1. `agentspec run start <context-pack>` creates `agent/runs/<run-id>/`.
2. The executor writes or returns an iteration output.
3. A collector records output, diff summary, tests, and explicit question text.
4. A reviewer/controller model returns a structured verdict.
5. A policy gate upgrades risky verdicts to `pause_for_human` or `halt`.
6. The controller either sends a scoped continuation message to the executor or
   records the pause reason for the human.

The protocol should avoid platform-specific UI automation at first. Codex,
Claude Code, Cursor, and GitHub agents can all be adapted later if the durable
state format works.

## Verdicts

`auto_continue` is allowed when all conditions hold:

- exactly one active context pack is known
- the executor's proposed next step stays inside the pack's allowed paths
- no external credential, network approval, destructive command, or scope
  expansion is requested
- required tests are known or the next step is to run them
- iteration count remains below `max_iterations`

`pause_for_human` is required when:

- the executor asks the human to choose among tasks
- the executor asks for a product or architecture decision not already decided
- the next step changes allowed paths, requirements, DCR status, or ADR status
- the controller confidence is below the configured threshold

`halt` is required when:

- forbidden paths were touched
- a required policy gate fails
- `max_iterations` is exhausted
- the active context pack cannot be found

`complete` is allowed when:

- task acceptance criteria are met
- verification evidence is present
- no blocking reviewer finding remains

## Reviewer Model Choice (`Q-012`)

Use two profiles rather than one default:

- `continuation_reviewer`: cheap/fast model, classifies replies and policy
  state into `auto_continue`, `pause_for_human`, `halt`, or `complete`.
- `quality_reviewer`: stronger model, reviews diffs, tests, and requirement
  coverage before completion.

Both profiles should be configurable per repository and overridable per task
context pack. This supports different model choices without making the
executor and reviewer the same agent.

## Iteration Cap (`Q-013`)

Recommended defaults for ADR discussion:

- small implementation/fix: `max_iterations = 3`
- spike/spec/review task: `max_iterations = 2`
- migration task: no default auto loop until partitioned write scopes exist

The cap should count executor attempts, not reviewer passes.

## Run State Retention (`Q-014`)

Split state:

- commit durable audit metadata such as verdicts, diff hashes, touched paths,
  test command names, and pause reasons
- keep raw model transcripts, long logs, and sensitive terminal output local by
  default

For the MVP, a single local `agent/runs/<run-id>/events.jsonl` is enough. ADR
0003 should decide whether committed summaries move to a separate file such as
`agent/runs/<run-id>/summary.yml`.

## Risks

- A reviewer that says only `continue` can accidentally approve task selection
  or scope expansion.
- Multi-agent continuation can hide accountability unless every decision is
  logged with model profile, confidence, and evidence references.
- UI-driven automation is brittle; the first experiment should use file-backed
  state and adapter boundaries.
- The controller must not accept requirements or DCRs on behalf of the human.

## Recommendation

Proceed with `DCR-0001` as a spike, then draft `ADR-0003` around a file-backed
supervised run protocol. Do not implement `agentspec run` production code until
the ADR is accepted.

The smallest useful dogfood experiment is already represented by:

- `agent/workflows/supervised-run.md`
- `agent/runs/supervised-run-spike/events.jsonl`

This gives AgentSpec a concrete shape for `R-127` through `R-130` without
prematurely flipping those requirements to accepted.
