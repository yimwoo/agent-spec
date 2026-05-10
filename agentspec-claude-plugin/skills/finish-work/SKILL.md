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
aspec status --json
aspec outcome --json
```

Summarize the completed requirement IDs, tests run, review id, outcome impact,
and any remaining product-readiness blockers. Do not claim production readiness
unless `aspec outcome` says the relevant outcome gates are ready.
