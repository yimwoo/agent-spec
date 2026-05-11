---
name: roadmap
description: Generate or check docs/ROADMAP.md from AgentSpec handoff, task ledger, and traceability artifacts.
---

# Roadmap

Call this skill as `/aspec:roadmap`.

Use this skill when the user asks for a canonical roadmap/status projection or
when finishing work that should refresh generated status artifacts.

## Commands

```bash
aspec roadmap
aspec roadmap --check
```

Do not hand-edit `docs/ROADMAP.md`; regenerate it from the core CLI.
