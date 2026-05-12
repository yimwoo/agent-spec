---
name: review-code
description: Record AgentSpec task-level code review evidence after implementation and verification, before task completion.
---

# Review Code

Controller procedure id: `review-code`. Public entrypoints route here through `manifests/skill-manifest.json`.

Use this skill after implementation and verification, before completing a task
or finalizing a branch.

## Commands

```bash
aspec review code --task <T-id> --verdict ready --summary "No blocking findings."
aspec review code --task <T-id> --verdict needs_changes --summary "<blocking findings>"
```

Review against the task context pack, requirement IDs, outcome gates, allowed
paths, tests, and product-readiness evidence. Record blockers before marking a
task complete.
