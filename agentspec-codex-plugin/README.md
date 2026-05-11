# AgentSpec For Codex

This plugin gives Codex the `aspec:*` skills for initializing and continuing
AgentSpec-governed repositories. The plugin is a thin adapter: Codex follows
the packaged skills, but the `aspec` CLI remains the source of truth.

Install or load this directory as the plugin package. It contains only the
Codex plugin manifest, this README, and the `skills/` tree; it does not include
the AgentSpec engine repository's private `agent/`, `reports/`, `.codex/`,
`.claude/`, `.agentspec/`, or generated design/traceability docs.

## Install First

From the repository root:

```bash
curl -fsSL https://raw.githubusercontent.com/yimwoo/agent-spec/main/install.sh | bash
```

Then install or enable `aspec` in the Codex surface you use:

```text
# Codex CLI
codex
/plugins
```

In the CLI plugin browser, choose the local marketplace, open `aspec`, and
select `Install plugin` or toggle it on. In the Codex app, restart Codex, open
**Plugins > Local Plugins**, and install `aspec`.

Then make sure the AgentSpec CLI is available:

```bash
python3 -m pip install "git+https://github.com/yimwoo/agent-spec.git"
```

For local development, load this plugin directory directly from your checkout
and keep an editable CLI install active:

```bash
pip install -e .
```

## Try This In Codex

For a new project:

```text
Use aspec:init-project to initialize this repository. The design source is at
docs/source/design.md. Set up Codex and Claude agent guidance, compile the
requirements, report readiness/open questions, and propose the first task
context packs. Do not start implementation until the task scope and allowed
paths are clear.
```

For an existing AgentSpec project:

```text
Use aspec:continue-work to continue this repository. Read AGENTS.md, run
project status, pick the next ready task pack, follow its allowed paths, run
verification, record review evidence, finish the task, and refresh
roadmap/handoff state.
```

For a new design update:

```text
Use aspec:manual-source-intake to process this design update: <path-or-export>.
Import it as a candidate or DCR, diff it against the accepted source, summarize
the impact, and prepare the next task pack. Ask before promoting accepted
source.
```

Codex should report requirement IDs, task pack path, allowed paths,
verification result, review ID, and handoff/roadmap status.

## What Codex Will Create

The plugin does not copy project state into the user's repository. When Codex
initializes a target repo through AgentSpec, the target repo receives the
governance files it needs:

```text
your-project/
|-- AGENTS.md
|-- CLAUDE.md
|-- .agentspec/config.yml
|-- .codex/agents/
|-- .claude/agents/
|-- .claude/skills/
|-- agent/context-packs/
|-- agent/roles/
|-- agent/runs/
|-- agent/workflows/
|-- docs/source/
|-- docs/traceability/
`-- reports/
```

Task ledgers, handoff records, review evidence, and `docs/ROADMAP.md` appear
as AgentSpec plans, runs, reviews, and finishes work.

## Initialize a repository

Use this when a repo does not yet have AgentSpec artifacts, or when an existing
repo needs an AgentSpec baseline.

### CLI path

```bash
TARGET=/path/to/repo
aspec --root "$TARGET" init --mode greenfield --targets claude,codex
aspec --root "$TARGET" ingest "$TARGET/docs/source/design.md"
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

Ask Codex to use `aspec:init-project`.

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

Ask Codex to use `aspec:continue-work`.

Use related skills for specific jobs:

- `aspec:project-status`
- `aspec:create-task`
- `aspec:compile-spec`
- `aspec:drift-review`
- `aspec:manual-source-intake`

## Boundaries

The plugin is a thin adapter. It does not fetch Confluence or Jira directly,
store connector credentials, parse sources, diff candidates, promote accepted
snapshots, or replace AgentSpec CLI governance.
