---
name: verify-work
description: Verify AgentSpec implementation work with tests, outcome gates, and recorded evidence before claiming completion.
---

# Verify Work

Call this skill as `aspec:verify-work`.

Use this skill before saying work is complete, fixed, production-ready, or ready
for review.

## Workflow

1. Run the tests and checks named by the task context pack.
2. Inspect product outcome gates:

```bash
aspec outcome --json
aspec status --json
aspec roadmap --check
```

3. Confirm the verification evidence covers the changed behavior, not only the
   files touched.

4. If the work changes user-facing product behavior, include workflow-level or
   browser/API evidence when available.

5. For implementation tasks, confirm write-back state is current: `agent/handoff.yml`
   is updated by completion and `docs/ROADMAP.md` is current or regenerated with
   `aspec roadmap`.

Boundary: this skill does not mark the task complete. Completion still requires
review evidence and the normal `aspec task complete` flow.

## Human-Facing Output

For Codex or Claude Code responses, translate internal AgentSpec checks into
plain evidence labels. Say whether the task tests passed, outcome gates are
ready or blocked, project status is ready or needs attention, and roadmap
freshness passed or needs repair.

Keep raw `aspec ...` command strings internal unless the user asks for commands,
logs, or terminal reproduction steps. Do not list `aspec outcome --json`,
`aspec status --json`, or `aspec roadmap --check` under "Tests / checks run" in
a final human-facing reply.
