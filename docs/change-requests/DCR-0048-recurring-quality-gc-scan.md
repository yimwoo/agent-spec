# DCR-0048: Recurring Quality GC Scan

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |

## Summary

Add a lightweight quality garbage-collection scan for AgentSpec repositories.

The scan should turn recurring entropy checks into durable report artifacts:
generated agent-context freshness, project invariant status, open-question
load, handoff freshness, and a simple quality grade with recommended follow-up
commands. This gives humans and code agents a small recurring cleanup lane
without letting an autonomous agent rewrite broad areas of the codebase.

## Motivation

Autonomous and semi-autonomous code work tends to repeat existing repository
patterns, including uneven ones. AgentSpec already has `aspec doctor`,
`aspec drift`, project invariants, reviewer profiles, and committed handoff
state, but there is no single recurring quality pass that summarizes entropy
and points to the next cleanup action.

The user wants this to run after a few tasks or after a milestone/phase so
agent-facing docs and project context do not quietly drift stale. Recent dogfood
state shows a concrete example: `aspec doctor` can detect stale generated
agent-context files after task completion, but that signal is not yet surfaced
as a recurring quality report.

## Proposed Change

- Add `aspec quality` as a local recurring quality-GC scan.
- Write structured and markdown reports under `reports/quality/`.
- Include a quality grade derived from mechanical findings.
- Include doctor freshness and project invariant findings.
- Include handoff state and task-count cadence hints so operators can run the
  scan every few completed tasks.
- Add a `quality-gc-reviewer` role to generated role surfaces.
- Keep `reports/quality/latest.yml` and `reports/quality/latest.md` trackable
  so the latest quality grade can travel with the repository.
- Keep this first slice read-only except for report artifacts.

## Impact Assessment

Affected existing artifacts:

- `agentspec/cli.py`
- `agentspec/quality.py`
- `agentspec/paths.py`
- `agentspec/init.py`
- `agentspec/emit.py`
- `.gitignore`
- `tests/test_quality_gc.py`
- `tests/test_init_layout.py`
- `tests/test_cli_workflow.py`
- `docs/traceability/requirements.yml`

Likely new requirement:

- `R-183`: AgentSpec exposes a recurring quality GC scan.

Likely task context pack:

- `T-078`: recurring quality GC scan.

## Disposition

Classification: `implement-now`.

No ADR is required. This is a diagnostic/reporting lane over existing doctor,
status, invariant, and handoff concepts. A later DCR can add automatic task
generation or scheduled automations once the report schema has stabilized.

## Acceptance Criteria

- `aspec quality` writes `reports/quality/latest.yml` and
  `reports/quality/latest.md`.
- The structured report includes schema, generated timestamp, grade, findings,
  project status summary, doctor summary, handoff summary, and cadence hints.
- Stale generated agent context from `aspec doctor` becomes a quality finding
  with recovery command `aspec emit --target claude,codex`.
- Missing `agent/policies/invariants.yml` becomes an informational finding so
  projects can see that golden principles are not configured.
- The CLI supports `--json`, `--report-dir`, and `--task-interval`.
- Init/emit surfaces include a `quality-gc-reviewer` role.
- `.gitignore` keeps the latest quality reports trackable while continuing to
  ignore regenerable report output by default.
- Focused tests and full unittest discovery pass.
