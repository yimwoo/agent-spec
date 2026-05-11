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
- `aspec review code`
- `aspec task complete`
- `aspec roadmap`
- `aspec roadmap --check --json`
- `aspec finish --dry-run`

## Verification Plan

- `python -m json.tool docs/traceability/requirements.yml`
- `python -m unittest tests/test_lifecycle_skill_gates.py tests/test_status_cli.py -v`
- `git diff --check`
- `aspec roadmap --check --json`
- `aspec status --json`

## Result

The AgentSpec-native lifecycle completed successfully in the isolated worktree:

- `T-099` was created from `R-203` and linked to workflow `W-099`.
- Branch `codex/e2e-agentspec-lifecycle` contains an implementation evidence
  commit before final write-back.
- Requirements JSON validation, targeted lifecycle/status tests, and
  `git diff --check` passed before and after the evidence commit.
- `REVIEW-0044` recorded a ready review verdict for `T-099`.
- `aspec task complete T-099 --test-status passed --review REVIEW-0044`
  updated the task ledger and handoff.
- `aspec roadmap --check --json` reported `docs/ROADMAP.md` current.
- `aspec finish T-099 --dry-run --test-status passed --review REVIEW-0044`
  reported `finishable=true`, `writeback.ready=true`, and no findings.
- Final `aspec status --json` reported `overall=idle`, no ready tasks, and no
  lifecycle warnings.
- A detached clean-checkout probe of the write-back commit reported
  `overall=attention_needed`, `lifecycle=needs_attention`, and one
  `stale_handoff` warning because tracked run count was `1` while committed
  handoff run count was `3`.

## Findings

- Local ignored run state under `agent/runs/*/state.yml` participates in
  `aspec status --json` run counts and handoff projection. Because these files
  are ignored by `.gitignore`, a committed `agent/handoff.yml` can embed counts
  that are fresh in the local worktree but stale in a clean checkout. This is
  reproducible from the E2E commit and is the same class of issue observed in
  the main checkout before the isolated worktree was created.
- `aspec task complete` writes handoff before `aspec roadmap` refreshes the
  roadmap. The selected-task write-back verification is ready after the roadmap
  command, but `handoff.current_state.recommendation` can preserve the
  pre-roadmap recommendation text until another completion refreshes handoff.
