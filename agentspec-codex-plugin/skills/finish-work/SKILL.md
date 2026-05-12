---
name: finish-work
description: Finish AgentSpec work intentionally by linking review evidence, completing the task, and rechecking status and outcomes.
---

# Finish Work

Call this skill as `aspec:finish-work`.

Use this skill when implementation, verification, and code review are complete
and the user wants to close the task or branch.

## Commands

```bash
aspec task complete <T-id> --test-status passed --review <REVIEW-id>
aspec roadmap
aspec status --json
aspec outcome --json
aspec roadmap --check
```

Summarize the completed requirement IDs, tests run, review id, outcome impact,
roadmap status, and any remaining product-readiness blockers. Do not claim
production readiness unless `aspec outcome` says the relevant outcome gates are
ready.

For implementation work, the expected order is task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
If an owner/patcher session was claimed, finish it with an explicit disposition so the branch/worktree state is recoverable.

Disposition meanings:

- `pr`: work is delivered through a pull request; local cleanup waits for merge or closure evidence.
- `merge`: work has been merged into the target branch.
- `keep`: branch/worktree remains intentionally available for follow-up.
- `discard`: branch/worktree can be abandoned because the work is intentionally not delivered.
- `release`: use `aspec session release` for handoff or abandoned ownership; it is not delivery closure.

Cleanup is advisory. `aspec status --json` may report cleanup-eligible
sessions only after task/write-back closure, delivery closure, clean local
resources, and no active owner/patcher lease for the same branch/worktree.
Do not remove a git worktree or delete a local branch without explicit user
confirmation or a later opt-in project policy. Ticket fixes, features,
designs, milestones, and cross-repo AgentSpec work share this finish lifecycle.

## Human-Facing Output

For Codex or Claude Code final replies, keep raw `aspec ...` commands internal
unless the user asks for command-level logs or terminal evidence. Report
verification by purpose and result, for example:

- "Task verification passed."
- "Outcome gates are ready."
- "Roadmap freshness check passed."

Do not include a final "Tests / checks run" section that lists internal
AgentSpec CLI commands such as `aspec outcome --json` or
`aspec roadmap --check`.
