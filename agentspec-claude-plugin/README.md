# aspec Claude Code Plugin

This plugin packages Claude Code skills for AgentSpec workflows while keeping
the core CLI as the source of truth. Users can run the CLI directly or load the
plugin and invoke the matching namespaced skill, such as `/aspec:init-project`.

Install or load this directory as the plugin package. It contains only the
Claude plugin manifest, this README, and the `skills/` tree; it does not
include the AgentSpec engine repository's private `agent/`, `reports/`,
`.codex/`, `.claude/`, `.agentspec/`, or generated design/traceability docs.

## Prompt-first usage

After the plugin is loaded, the human-facing interface is a prompt. Claude Code
uses the packaged `/aspec:*` skills and runs the underlying `aspec --root ...`
commands.

For a new project:

```text
Use AgentSpec to initialize this repository. The design source is at
docs/source/design.md. Set up Codex and Claude agent guidance, compile the
requirements, report readiness/open questions, and propose the first task
context packs.
```

For an existing AgentSpec project:

```text
Use AgentSpec to continue this repository. Read AGENTS.md, run project status,
pick the next ready task pack, follow its allowed paths, verify, review,
finish, and refresh roadmap/handoff state.
```

For a new design update:

```text
Use AgentSpec to process this design update: <path-or-export>. Import it as a
candidate or DCR, diff it against the accepted source, summarize the impact,
and prepare the next task pack. Ask before promoting accepted source.
```

Claude Code should report the requirement IDs, task pack path, allowed paths,
verification result, review ID, and handoff/roadmap status.

## Local development

Validate the plugin:

```bash
claude plugin validate agentspec-claude-plugin
```

Load it for one Claude Code session from this repository:

```bash
claude --plugin-dir ./agentspec-claude-plugin
```

Claude Code exposes plugin skills with the plugin namespace, so
`skills/init-project/SKILL.md` is invoked as `/aspec:init-project`.

## Initialize a repository

Use this when a repo does not yet have AgentSpec artifacts, or when an existing
repo needs an AgentSpec baseline.

### CLI path

```bash
TARGET=/path/to/repo
aspec --root "$TARGET" init --mode greenfield --targets claude,codex
aspec --root "$TARGET" ingest docs/source/design.md
aspec --root "$TARGET" compile
aspec --root "$TARGET" emit --target claude,codex
aspec --root "$TARGET" status
```

For changing external sources, use the intake lane instead of direct ingest:

```bash
aspec --root "$TARGET" intake import ./design-export.md \
  --kind markdown \
  --source-key product-design \
  --classification internal \
  --storage-mode committed \
  --as-candidate \
  --json
```

### Plugin path

Ask Claude Code to use `/aspec:init-project`.

The skill should identify the target repo, choose greenfield or existing-repo
initialization, run the same `aspec --root "$TARGET" ...` commands, and inspect
the resulting status.

## Continue work in a repository

Use this when the repo already has AgentSpec artifacts and the user wants the
next safe action.

### CLI path

```bash
aspec status
aspec task next
aspec run loop
```

For candidate external-source updates:

```bash
aspec intake diff <snapshot-id> --baseline accepted --json
aspec intake promote <snapshot-id> --decision accepted --compile --json
```

Promotion remains a human-reviewed action.

### Plugin path

Ask Claude Code to use `/aspec:continue-work`.

Use related skills for specific jobs:

- `/aspec:project-status`
- `/aspec:create-task`
- `/aspec:compile-spec`
- `/aspec:drift-review`
- `/aspec:manual-source-intake`

## Boundaries

The plugin is a thin adapter. It does not fetch Confluence or Jira directly,
store connector credentials, or replace AgentSpec CLI governance. It does not
own source parsing, diffing, promotion, or accepted snapshots. It also does not
ship MCP, hook, or agent configuration until those entries can call implemented
AgentSpec core surfaces.
