# AgentSpec Lifecycle E2E Smoke Test

Date: 2026-05-11
Branch: `codex/e2e-agentspec-lifecycle`
Task: `T-099`
Requirement: `R-203`
DCR: `DCR-0068`

## Goal

Exercise the complete AgentSpec-native development lifecycle without HOTL or
Superpowers plugins:

1. Create a DCR and accepted requirement.
2. Create a task context pack with `aspec task create`.
3. Create and link a native workflow with `aspec plan`.
4. Start a supervised run with `aspec run loop`.
5. Make a scoped implementation evidence commit on an isolated branch.
6. Run verification.
7. Record review evidence with `aspec review code`.
8. Complete the task with linked review evidence.
9. Regenerate roadmap and handoff state.

## Commands Exercised

- `aspec status --json`
- `aspec dcr create`
- `aspec dcr accept`
- `aspec task create`
- `aspec plan`
- `aspec task next`
- `aspec run loop`

## Verification Plan

- `python -m json.tool docs/traceability/requirements.yml`
- `python -m unittest tests/test_lifecycle_skill_gates.py tests/test_status_cli.py -v`
- `git diff --check`
- `aspec roadmap --check --json`
- `aspec status --json`

## Interim Result

The task pack and workflow stages are functioning through AgentSpec-native CLI
surfaces. Final review, completion write-back, roadmap, and handoff checks are
recorded after verification.
