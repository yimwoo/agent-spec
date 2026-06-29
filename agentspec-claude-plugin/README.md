# AgentSpec For Claude Code

This plugin gives Claude Code the `/aspec:*` skills for initializing and
continuing AgentSpec-governed repositories. The plugin is a thin adapter:
Claude Code follows the packaged skills, but the `aspec` CLI remains the source
of truth.

The plugin package contains only the Claude plugin manifest, this README,
public `skills/`, and non-public controller/worker/reviewer guidance; it does
not include the AgentSpec engine repository's private `agent/`, `reports/`,
`.codex/`, `.claude/`, `.agentspec/`, or generated design/traceability docs.

## Install First

Marketplace install inside Claude Code:

```text
/plugin marketplace add yimwoo/agent-spec
/plugin install aspec@agentspec
```

Then make sure the CLI is available:

```bash
python3 -m pip install "git+https://github.com/yimwoo/agent-spec.git"
```

Claude Code exposes plugin skills with the plugin namespace, so
`skills/init-project/SKILL.md` is invoked as `/aspec:init-project`.

## Try This In Claude Code

For a new project:

```text
/aspec:init-project

Initialize this repository. The design source is at docs/source/design.md. Set
up Codex and Claude agent guidance, compile the requirements, report
readiness/open questions, and propose the first task context packs. Do not
start implementation until the task scope and allowed paths are clear.
```

For an existing AgentSpec project:

```text
/aspec:continue-work

Continue this repository. Read AGENTS.md, run project status, pick the next
ready task pack, create or verify the workflow, claim or verify the
branch/worktree/session lease, follow its allowed paths, run verification,
record review evidence, finish the task, and refresh roadmap/handoff state. Do
not start implementation execution until session preflight is satisfied.
```

For a new design update:

```text
/aspec:design-work

Process this design update: <path-or-export>. Import it as a candidate or DCR,
diff it against the accepted source, summarize the impact, and prepare the next
task pack. Ask before promoting accepted source.
```

Claude Code should report requirement IDs, task pack path, allowed paths,
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

## What Claude Code Will Create

The plugin does not copy project state into the user's repository. When Claude
Code initializes a target repo through AgentSpec, the target repo receives the
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

Ask Claude Code to use `/aspec:init-project`.

The skill should identify the target repo, choose greenfield or existing-repo
initialization, run the same `aspec --root "$TARGET" ...` commands, and inspect
the resulting status.

## Continue work in a repository

Use this when the repo already has AgentSpec artifacts and the user wants the
next safe action.

### Reviewer profile diagnostics

AgentSpec reviewer profiles are project-local control-plane bindings. A Claude
Code-only environment can keep using deterministic review without owning Codex
dogfood model aliases. Use `aspec status --json` or `aspec doctor` to see
which profiles are bound to continuation and terminal quality review, whether
local model config and credentials can be resolved, and whether model-backed
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
aspec run package --runner generic --json
aspec run result <run-id> --result-json '{"executor_output":"..."}' --json
```

After session preflight, provider-native execution is preferred: use Claude
`/loop` or a dynamic Claude workflow to complete the scoped task. The
package/result pair is the generic fallback; `aspec run loop` and `aspec run
exec` remain compatibility paths. Do not bypass allowed paths, verification,
review, or finish write-back in either mode.

For candidate external-source updates:

```bash
aspec intake diff <snapshot-id> --baseline accepted --json
aspec intake promote <snapshot-id> --decision accepted --compile --json
```

Promotion remains a human-reviewed action.

### Plugin path

Ask Claude Code to use `/aspec:continue-work`.

Public AgentSpec plugin skills are intentionally limited to the human entry
menu:

- `/aspec:project-status`
- `/aspec:init-project`
- `/aspec:brainstorm`
- `/aspec:design-work`
- `/aspec:plan-workflow`
- `/aspec:continue-work`
- `/aspec:review-doc`
- `/aspec:finish-work`
- `/aspec:outcome-audit`

Lower-level controller procedures such as source intake, compile, task
creation, branch/session start, workflow execution, verification, review-code,
roadmap, and handoff recovery live under `controller/` and are invoked by the
public entrypoints or by the AgentSpec CLI fallback commands listed in
`manifests/skill-manifest.json`.

## Lifecycle hooks

The plugin bundles `hooks/hooks.json` for pre-tool policy and scope checks,
stop verification, and finish-evidence capture. Each handler delegates to
`python3 -m agentspec.cli hook evaluate`; no policy logic is duplicated in the
plugin. Review and trust the hook definition through Claude Code's native hook
and settings controls. An AgentSpec allow decision never auto-approves the
tool call, so Claude sandbox, permissions, and managed policy remain
authoritative. Evidence is written to `agent/hook-evidence/events.jsonl`.

## Boundaries

The plugin is a thin adapter. It does not fetch Confluence or Jira directly,
store connector credentials, or replace AgentSpec CLI governance. It does not
own source parsing, diffing, promotion, or accepted snapshots. It does not ship
an MCP server or independent policy engine; its hooks call implemented
AgentSpec core surfaces.
