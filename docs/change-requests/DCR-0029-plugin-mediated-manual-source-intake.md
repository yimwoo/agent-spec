# DCR-0029: Plugin-mediated manual source intake

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Define the first AgentSpec plugin-source workflow as manual or host-provided
external-source intake. Codex or Claude Code may already have access to
Confluence, Jira, Google Drive, or similar systems through host MCP tools, but
the first AgentSpec plugin slice should not own those connectors, credentials,
or scheduled fetches.

Instead, the plugin accepts content that a human or host integration has already
provided as a local file or equivalent export, attaches source metadata, and
passes it into the existing `aspec intake` candidate flow. AgentSpec remains the
owner of `SpecDocument` normalization, validation, diffing, human-gated
promotion, and repo-local accepted snapshots.

## Source Sections

- `D-03.2`: V2 goal to provide Claude Code and Codex plugins as thin adapters
  over the core CLI and MCP server.
- `D-10.4`: Claude Code plugin surface.
- `D-10.5`: Codex plugin surface.
- `D-20.6`: task/source creation through core AgentSpec tools.
- `D-21.2`: Claude plugin packaging direction.
- `D-22.2`: Codex plugin packaging direction.
- `D-26.1`..`D-26.3`: core before plugins and recommended plugin sequence.

## Motivation

The next productization step is likely a Codex plugin alpha, followed by a
Claude Code plugin. A tempting first plugin scope is "connect AgentSpec to
Confluence/Jira," especially because the agent host may already expose MCP
connectors for those tools.

That coupling is too broad for the first slice:

- Codex and Claude Code can expose MCP tools differently.
- Enterprise connector auth and token storage are sensitive and
  organization-specific.
- A plugin that fetches and promotes remote source changes directly would blur
  the ADR-0006 candidate-first boundary.
- AgentSpec already has a safer intake lane: import candidate, validate, diff,
  review, promote.

The immediate need is a reliable plugin UX that lets an operator bring fresh
external design material into the candidate intake flow without changing the
accepted repo baseline until review.

## Proposed Change

Add a plugin-mediated manual source intake workflow:

```text
human export / host MCP fetch / pasted or downloaded file
  -> plugin records source metadata
  -> plugin calls `aspec intake import ... --as-candidate`
  -> plugin calls or recommends `aspec intake diff`
  -> human reviews candidate diff
  -> human runs `aspec intake promote ...`
```

### Product Rule

The plugin may help fetch, locate, or stage external source content, but it must
not make the plugin or host MCP connector the source of truth. The repo-local
AgentSpec accepted snapshot remains the source used by `aspec compile`.

### Supported First Inputs

The first implementation should support manual or host-provided inputs:

- local Markdown or text export;
- local HTML export;
- local YAML/OpenAPI export;
- local PDF export if PDF intake is available in the current core;
- a file produced by a host MCP call to Confluence/Jira/Drive/etc.;
- pasted content saved to a temporary local file by the operator or plugin.

A remote Confluence/Jira URL may be recorded as metadata, but in this first
slice it is not fetched by AgentSpec itself.

### Required Metadata

When the source represents an external system, the plugin workflow should record
metadata alongside the import request where the core supports it:

```yaml
source_key: payments-design
kind: confluence
source_url: https://confluence.example/wiki/spaces/PAY/pages/12345
external_id: "12345"
external_version: "42"
retrieved_at: "2026-05-01T00:00:00Z"
retrieved_by: host-provided
classification: internal
storage_mode: committed
```

If the current core CLI cannot store every metadata field yet, the first plugin
slice should preserve the content path, `source_key`, `kind`, classification,
storage mode, and content hashes, then report the missing metadata fields as a
follow-up rather than inventing a plugin-only state store.

### Plugin Behavior

The first Codex plugin should provide skills or commands for:

- checking AgentSpec project status;
- importing a provided source file as a candidate;
- validating and diffing the candidate;
- presenting the promote command for human review;
- explaining that connector-managed fetching and scheduled polling are out of
  scope for the first plugin-source workflow.

The plugin should call stable AgentSpec CLI commands and should not implement
its own source parser, diff engine, or promotion logic.

### Implementation Sequence

Implement Codex first, then use the same workflow contract for Claude Code.
This answers `Q-006` for this implementation slice: Codex is first because this
repository can dogfood Codex plugin skills immediately. Claude Code support
should follow once the first plugin packaging and manual-source-intake boundary
are proven.

## Non-Goals

- No AgentSpec-managed Confluence/Jira credentials in this slice.
- No direct AgentSpec remote fetch from Confluence/Jira/Drive.
- No scheduled plugin polling.
- No host-specific MCP tool contract as a required path.
- No plugin-owned source registry or accepted baseline.
- No automatic promotion from external content into `docs/source/`.

## Relationship To Existing Architecture

This DCR relies on the existing candidate-first model:

- ADR-0006 defines `SpecDocument`, candidate snapshots, validation, diff, and
  human-gated promotion.
- ADR-0007 defines the source registry and scheduled drift checks as a later
  registry-backed workflow.
- DCR-0026 and DCR-0027 remain the governing design for core intake and source
  drift.

This DCR narrows the plugin layer: plugins are UX adapters over those core
commands, not connector owners.

## Impact Assessment

Affected existing requirements:

- `R-007`: CLI output and behavior remain local/CI friendly.
- `R-012`: Claude Code and Codex plugins are thin adapters over the core CLI
  and MCP server direction.
- `R-100`: vendor-neutral core remains the primary owner; plugins are adapters.
- `R-147`..`R-154`: candidate intake, promotion, storage policy, and connector
  adapter contracts remain the source intake base.
- `R-155`..`R-158`: source registry and scheduled drift checks remain future
  registry-backed behavior, not a plugin shortcut.

Likely new requirement:

- `R-164`: AgentSpec plugin source intake accepts manual or host-provided
  external-source content, records source metadata where supported, and routes
  the content through `aspec intake` without plugin-owned parsing, diffing, or
  promotion.

Likely affected modules and artifacts:

- `agentspec/emit.py`: optional plugin/skill emission updates.
- `agentspec/cli.py`: only if the core intake CLI needs metadata flags.
- `agentspec/intake.py`: only if source metadata needs first-class persistence.
- `agentspec-codex-plugin/**` or equivalent plugin package.
- `.agents/skills/**` generated or packaged AgentSpec skills.
- `tests/test_emit.py`, `tests/test_intake_candidate.py`, and plugin smoke
  tests.

## Disposition

Classification: `implement-now`.

No ADR is required for this first slice because it does not introduce a new
source-of-truth model, connector auth, scheduled fetch semantics, or promotion
policy. It deliberately uses the ADR-0006 candidate-first intake protocol and
keeps connector-managed fetching out of scope.

If a later change lets AgentSpec manage Confluence/Jira credentials or fetch
remote sources directly, that change should get its own DCR and likely an ADR.

## HOTL Contracts

### Intent Contract

```yaml
intent: Define and implement the first plugin-source workflow as manual or host-provided content routed through core AgentSpec intake.
constraints:
  - Do not add AgentSpec-managed Confluence/Jira credentials.
  - Do not let plugins own parsing, diffing, promotion, or accepted snapshots.
  - Do not require host-specific MCP behavior for the first plugin workflow.
success_criteria:
  - A plugin-facing workflow can import a provided file as an intake candidate.
  - The workflow validates and diffs through core `aspec intake` commands.
  - The human promote gate remains explicit.
  - Missing connector/metadata capabilities are reported as follow-ups.
risk_level: medium
```

### Verification Contract

```yaml
verify_steps:
  - run tests: python -m pytest -q -p no:cacheprovider
  - check: aspec status --json reports the new requirement/task state when implemented.
  - check: plugin smoke tests verify CLI-backed source-intake skill content.
  - confirm: no plugin code writes accepted source/spec artifacts directly.
```

### Governance Contract

```yaml
approval_gates:
  - Human review before promoting any imported candidate.
  - Human review before introducing connector credentials or remote fetch.
rollback:
  - Remove the plugin package/skills and leave core intake artifacts unchanged.
  - Delete unpromoted candidate snapshots if they were created only for testing.
ownership:
  - coordinator owns plugin workflow and governance boundary.
  - security-reviewer owns connector/auth follow-up review.
```

## Acceptance Criteria

- A task context pack can be created for `R-164` after the requirement is
  registered.
- The first plugin-source workflow accepts a local file or host-provided export
  and routes it through `aspec intake import --as-candidate`.
- The workflow can validate and diff the resulting candidate without mutating
  accepted source/spec artifacts.
- The workflow presents, but does not auto-run, the promote command.
- Documentation states that host MCP connector fetching is allowed only as a
  provider of local content for this slice.
- Documentation states that AgentSpec-managed remote connectors and scheduled
  polling are future work.
