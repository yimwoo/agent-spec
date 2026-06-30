# EXP-lifecycle-pilot

Status: **execution blocked; no provider cells recorded**

This document is a pre-execution record for the first controlled Codex and
Claude lifecycle pilot. It is not an AgentSpec performance result and supports
no AgentSpec-versus-control conclusion.

## Pinned protocol

- Manifest: `benchmarks/controlled-evals/EXP-lifecycle-pilot/manifest.yml`
- Manifest SHA-256: `54d0c5517ca0553f68a2641f58a77a6877025714ddae0f3956182e5df8deeb83`
- Task SHA-256: `7a3638b7b72e861d4fc74ee6920076610c1b46c4f3ebcdcf31780bf7325ee98b`
- Oracle SHA-256: `42a4742c7b9e4eb61863934908790b6d6594db0389748126c8bfa96d3315bfef`
- Providers: Codex `gpt-5.5`; Claude `claude-opus-4-8`
- Conditions: AgentSpec lifecycle treatment and direct-prompt control
- Replicates: one per provider/condition pair
- Expected cells: 4
- Recorded cells: 0

The fixture's public tests pass before execution and its hidden Unicode oracle
fails, confirming that the task begins unresolved. Workspace preparation is
deterministic and keeps the hidden oracle outside each provider workspace.

## Execution boundary

The attempted launch was denied by tenant policy before any cell produced raw
output. The Claude treatment would send repository-derived task, fixture,
AgentSpec plugin, and workspace contents to an external service. That transfer
requires separate explicit user approval after disclosure of the risk. No
workaround was attempted, and the other cells were not treated as completed.

Raw transcripts, when explicitly authorized, remain under an isolated
temporary directory and are not committed. AgentSpec receives only scored run
evidence and provenance after provider execution.

## Current evaluator result

The deterministic evaluator reports two limited provider pairs, zero valid
pairs, and zero invalid pairs because both conditions are missing for Codex and
Claude. It correctly concludes that no comparative claim is supported.

## Required next action

Obtain explicit approval to transmit the pinned task, fixture, AgentSpec
treatment artifacts, and provider prompts to Codex and Claude. Then execute the
four isolated cells, score public tests plus the hidden oracle, record immutable
run evidence, regenerate the comparison, and replace this pre-execution record
with observed results and limitations.
