# AgentSpec For Codex

This plugin gives Codex the `aspec:*` skills for initializing and continuing
AgentSpec-governed repositories. The plugin is a thin adapter: Codex follows
the packaged skills, but the `aspec` CLI remains the source of truth.

Install or load this directory as the plugin package. It contains only the
Codex plugin manifest, this README, public `skills/`, and non-public
controller/worker/reviewer guidance; it does not include the AgentSpec engine
repository's private `agent/`, `reports/`, `.codex/`, `.claude/`,
`.agentspec/`, or generated design/traceability docs.

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
project status, pick the next ready task pack, create or verify the workflow,
claim or verify the branch/worktree/session lease, follow its allowed paths,
run verification, record review evidence, finish the task, and refresh
roadmap/handoff state. Do not start implementation execution until session
preflight is satisfied.
```

For a new design update:

```text
Use aspec:design-work to process this design update: <path-or-export>.
Import it as a candidate or DCR, diff it against the accepted source, summarize
the impact, and prepare the next task pack. Ask before promoting accepted
source.
```

Codex should report requirement IDs, task pack path, allowed paths,
verification result, review ID, branch/worktree disposition, and
handoff/roadmap status.

## Implementation Order

For implementation work, follow task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish.
Claim or verify an active owner/patcher session lease before implementation execution.
Do not start `aspec run loop`, `aspec run package`, or `aspec run exec` until session preflight is satisfied.
Explicit host-worktree execution is an auditable escape hatch when the workflow or task context pack declares it intentionally.
Every implementation owner/patcher session finishes with a disposition:
`pr`, `merge`, `keep`, or `discard`; use session release for handoff or
abandoned ownership. Cleanup is advisory and requires explicit confirmation
before removing a git worktree or deleting a local branch.

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

### Reviewer profile diagnostics

AgentSpec reviewer profiles are project-local control-plane bindings. A Codex
environment does not need to expose the same dogfood model aliases used by the
AgentSpec engine repository. Use `aspec status --json` or `aspec doctor` to
see which profiles are bound to continuation and terminal quality review,
whether Codex config and credentials can be resolved, and whether model-backed
review is currently available. If a model-backed reviewer is unavailable,
`--reviewer auto` falls back to deterministic review with diagnostics; explicit
`--reviewer model` should fail or reject clearly instead of silently replacing
the configured model with the current host default.

### CLI path

```bash
aspec status
aspec task next
aspec plan <T-id>
aspec session start --task <T-id> --owner <owner> --branch <branch> --worktree <path>
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

Public AgentSpec plugin skills are intentionally limited to the human entry
menu:

- `aspec:project-status`
- `aspec:init-project`
- `aspec:brainstorm`
- `aspec:design-work`
- `aspec:plan-workflow`
- `aspec:continue-work`
- `aspec:review-doc`
- `aspec:finish-work`
- `aspec:outcome-audit`

Lower-level controller procedures such as source intake, compile, task
creation, branch/session start, workflow execution, verification, review-code,
roadmap, and handoff recovery live under `controller/` and are invoked by the
public entrypoints or by the AgentSpec CLI fallback commands listed in
`manifests/skill-manifest.json`.

## Boundaries

The plugin is a thin adapter. It does not fetch Confluence or Jira directly,
store connector credentials, parse sources, diff candidates, promote accepted
snapshots, or replace AgentSpec CLI governance.
