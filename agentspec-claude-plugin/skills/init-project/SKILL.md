---
name: init-project
description: Initialize AgentSpec in a new repository or add AgentSpec artifacts to an existing repository through the core CLI. Use when the user asks to set up, bootstrap, initialize, or onboard AgentSpec.
---

# Init Project

Call this skill as `/aspec:init-project`.

Use this skill when the user wants to set up AgentSpec in a new repository or
bootstrap AgentSpec artifacts in an existing repository.

## Workflow

1. Confirm the target repository path as `TARGET`.
2. Choose the mode:
   - new repository: `greenfield`
   - existing repository: start with `greenfield` only if the user has a design
     source ready; otherwise run read-only inspection commands first.
3. Initialize AgentSpec and Claude/Codex artifacts:

```bash
aspec --root "$TARGET" init --mode greenfield --targets claude,codex
aspec --root "$TARGET" emit --target claude,codex
aspec --root "$TARGET" status
```

4. If the user has an initial design document, ingest or import it:

```bash
aspec --root "$TARGET" ingest docs/source/design.md
aspec --root "$TARGET" compile
aspec --root "$TARGET" status
```

If `aspec status` reports that readiness is below 60, do not create an
implementation task yet. Enrich the source material or create discovery, spike,
or scaffold tasks. In short: discovery, spike, or scaffold work comes before
normal implementation when the readiness gate is closed.

For changing external design sources, use candidate intake:

```bash
aspec --root "$TARGET" intake import <path> \
  --kind markdown \
  --source-key <source-key> \
  --classification internal \
  --storage-mode committed \
  --as-candidate \
  --json
```

Do not fabricate requirements from thin input. If source material is missing,
report the missing input and recommend discovery or brownfield mapping.
