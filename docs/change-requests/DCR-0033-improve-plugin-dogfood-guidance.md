# DCR-0033: Improve plugin dogfood guidance

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

Record and fix two end-user guidance gaps found while dogfooding the installed
`aspec:*` Codex plugin skills against a disposable repository:

- after `aspec:init-project`, a small valid design may compile with readiness
  below the implementation gate, so immediate implementation task creation is
  blocked;
- after an initial plain `aspec ingest`, candidate intake diffs only match the
  accepted baseline when the candidate `source_key` matches the accepted source
  id, such as `SRC-0001`.

## Motivation

DCR-0031 and DCR-0032 made this repository dogfood the same installed plugin
skills end users see. The first dogfood pass verified the short `aspec:*`
surface and found that the current plugin docs are correct mechanically but too
thin for common recovery paths.

The plugin should not hide core AgentSpec gates. It should tell users what the
gate means and what command path to use next.

## Proposed Change

- Update `aspec:init-project` guidance to explain readiness scores below 60
  after bootstrap: do not create implementation tasks yet; enrich the source or
  create discovery, spike, or scaffold tasks until `aspec status` reports the
  implementation gate is open.
- Update `aspec:manual-source-intake` guidance to explain source-key selection
  when updating an accepted source created by plain `aspec ingest`: use the
  accepted source id from `docs/source/sources.yml` or `aspec status` evidence
  as the candidate `source_key`, or import the first version through intake from
  the start when a stable external source key is required.
- Update plugin tests so these dogfood lessons stay in the public skill docs.

## Impact Assessment

Affected existing requirements:

- `R-165`: plugin init and continuation docs stay accurate for new and existing
  repositories.
- `R-167`: the guidance remains under the `aspec:*` call surface.

Likely new requirement:

- `R-168`: AgentSpec Codex plugin guidance covers readiness-gate recovery and
  source-key selection for candidate diffs after initial ingest.

Likely affected artifacts:

- `agentspec-codex-plugin/skills/init-project/SKILL.md`
- `agentspec-codex-plugin/skills/manual-source-intake/SKILL.md`
- `tests/test_plugin_source_intake.py`

## Disposition

Classification: `implement-now`.

No ADR is required. This is documentation and skill guidance over existing core
CLI behavior.

## Acceptance Criteria

- `aspec:init-project` skill guidance explains what to do when readiness is
  below 60 after bootstrap.
- `aspec:manual-source-intake` skill guidance explains how to choose
  `source_key` when diffing against an accepted source created by `aspec ingest`.
- Tests assert both guidance points.
- Full test suite passes.
