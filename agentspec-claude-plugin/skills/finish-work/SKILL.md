---
name: finish-work
description: Finish AgentSpec work intentionally by linking review evidence, completing the task, and rechecking status and outcomes.
---

# Finish Work

Call this skill as `/aspec:finish-work`.

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
