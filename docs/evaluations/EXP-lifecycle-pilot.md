# EXP-lifecycle-pilot

Status: **partial execution; Codex pair recorded, Claude transport blocked**

This document reports the first observed cells from the controlled Codex and
Claude lifecycle pilot. It is descriptive evidence from one task and one
replicate, not a causal or general AgentSpec performance claim.

## Pinned protocol

- Manifest: `benchmarks/controlled-evals/EXP-lifecycle-pilot/manifest.yml`
- Manifest SHA-256: `54d0c5517ca0553f68a2641f58a77a6877025714ddae0f3956182e5df8deeb83`
- Task SHA-256: `7a3638b7b72e861d4fc74ee6920076610c1b46c4f3ebcdcf31780bf7325ee98b`
- Oracle SHA-256: `42a4742c7b9e4eb61863934908790b6d6594db0389748126c8bfa96d3315bfef`
- Providers: Codex `gpt-5.5`; Claude `claude-opus-4-8`
- Conditions: AgentSpec lifecycle treatment and direct-prompt control
- Replicates: one per provider/condition pair
- Expected cells: 4
- Recorded cells: 2

The fixture's public tests pass before execution and its hidden Unicode oracle
fails, confirming that the task begins unresolved. Workspace preparation is
deterministic and keeps the hidden oracle outside each provider workspace.

## Observed Codex result

Both Codex `gpt-5.5` cells completed the requested implementation. All three
public tests and all three hidden-oracle tests passed in each workspace, with
zero regressions, retries, human interventions, review findings, or escaped
defects.

| Metric | Control | With AgentSpec | AgentSpec - control |
|---|---:|---:|---:|
| Completed | yes | yes | no change |
| Total tokens reported | 236,271 | 1,006,294 | +770,023 |
| Cached input tokens | 207,104 | 905,216 | +698,112 |
| Uncached input + output | 29,167 | 101,078 | +71,911 |
| Duration | 89.648 s | 242.071 s | +152.423 s |
| Actual cost reported | unavailable | unavailable | unavailable |

The AgentSpec cell additionally produced a workflow, claimed and closed a
session lease, recorded ready code-review evidence, completed task write-back,
and reached an idle status with no active session. The control cell produced
the correct source and regression-test changes without lifecycle evidence.

This single pair shows governance overhead but no observed correctness benefit
on this small task. It cannot establish how either condition performs on larger
or failure-prone work.

## Protocol deviations and blocked cells

- The manifest declared a 50,000-token limit, but the provider runner did not
  enforce a token stop. Both Codex cells exceeded the declared total-token
  limit. Their immutable records preserve the observed metrics, but this report
  does not treat the pair as protocol-valid even though its metadata matches.
- Codex CLI did not report actual monetary cost. API list-price estimates are
  not substituted for the user's subscription cost.
- Claude Code authentication was valid, but credential-free connectivity to
  `api.anthropic.com:443` failed and minimal `claude-opus-4-8` probes returned
  no output. Neither Claude evaluation workspace was launched or scored.
- The generated evaluator therefore reports zero valid pairs, two limited
  pairs, and zero invalid pairs: Codex is limited by missing cost data, and
  Claude is limited by missing condition runs.
- Raw transcripts remain in an isolated temporary directory and are not
  committed. Only scored evidence, digests, and non-sensitive blocker facts
  are versioned.

## Required next action

Refresh Claude Code authentication, then run both Claude conditions from fresh
isolated workspaces. As of 2026-07-01 `api.anthropic.com:443` is reachable, but
the active Claude Code login returns HTTP 401 for a minimal pinned-model request.
The follow-up protocol is now published as
`benchmarks/controlled-evals/EXP-lifecycle-pilot/manifest-v2.yml` with SHA-256
`b22aa291b8543f90ca5fbd6050de5e5c663840d507342f6dce271abcd1e79e7d`.
It distinguishes runner-enforced duration/retry limits, Claude's provider
budget, post-run token validity checks, and unavailable Codex monetary cost.
The Codex pin remains `gpt-5.5`: a `gpt-5.6-sol` availability probe was rejected
because that model requires a newer Codex app or CLI than the v2 environment.

Run all four v2 cells from fresh workspaces so each provider pair shares the
same task, model, environment, limits, and oracle. Do not rewrite these v1
observations. Complete T-183 only after all four v2 cells have comparable
evidence and a ready review verdict.
