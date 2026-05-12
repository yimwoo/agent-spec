---
name: review-doc
description: Review AgentSpec DCRs, designs, source candidates, discovery notes, and workflows through the document-review CLI.
---

# Review Doc

Call this skill as `aspec:review-doc`.

Use this skill when a user asks to review an AgentSpec design artifact before
it becomes implementation authority.

## Commands

```bash
aspec review doc <path> --mode deterministic --json
aspec review doc <path> --verdict ready --reviewer human --summary "<summary>" --json
aspec review doc --check <path> --json
```

Review generated or agent-authored DCRs, design notes, discovery spikes, source
candidates, and workflow plans before accepting, promoting, tasking, or
executing them.

Boundary: this skill records AgentSpec document-review evidence only. Reviewer
personas, rubric details, and model-backed review profiles live in non-public
reviewer package guidance or CLI policy; they are not separate human commands.

