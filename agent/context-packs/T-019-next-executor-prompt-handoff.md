# T-019: Next Executor Prompt Handoff

Type: `implementation`
Originating DCR: `DCR-0013-add-next-executor-prompt-handoff`

## Goal

Expose a durable, read-only handoff prompt so a harness can feed reviewer
feedback into the next main-agent iteration.

## Requirements

- `R-007` (P1, accepted) Provide a CLI that can run locally and in CI.
- `R-127` (P2, proposed-pending-acceptance) Bounded supervised run executes
  one context pack with iteration cap and allowed-paths enforcement.
- `R-129` (P2, proposed-pending-acceptance) Reviewer model can produce
  structured feedback consumable by a next iteration.

This task makes reviewer feedback consumable by a next executor prompt. It
does not promote `R-127` or `R-129`.

## Source Sections

- `D-03` Product Goals and Non-Goals
- `D-13.3` Supervised Run Orchestrator
- `D-23.4` Policy Gates
- `D-24` Evaluation and Observability

## Accepted Assumptions

- `A-001` The first AgentSpec release is local-first and CLI-first.
- `A-002` The MVP stores structured `.yml` artifacts as YAML-compatible JSON
  to avoid runtime dependencies.

## Allowed Paths

- `agent/context-packs/T-019-next-executor-prompt-handoff.md`
- `docs/change-requests/DCR-0013-add-next-executor-prompt-handoff.md`
- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_prompt.py`
- `README.md`
- `AGENTS.md`
- `agent/task-ledger.yml`
- `agent/runs/**`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly revised.
- Canonical source snapshots in `docs/source/`.
- Requirement status flips in `docs/traceability/requirements.yml`.
- Secrets, access tokens, or local credential material.

## Tests To Add Or Update

- `tests/test_supervised_run_prompt.py`

## Acceptance Criteria

- `aspec run prompt <run-id>` prints a next executor prompt for started or
  running runs.
- After reviewer `auto_continue`, the prompt includes the reviewer
  `message_to_executor`.
- `--json` output includes prompt, context pack, allowed paths, last decision,
  and status.
- Terminal states (`complete`, `halted`, `aborted`) refuse continuation
  prompts.
- `python -m unittest discover -s tests -v` passes.
