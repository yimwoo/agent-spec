# T-036: README Dual-Audience Framing

Type: `implementation`

## Goal

Clarify the root README so it serves two distinct audiences in one
document: humans setting up or operating an AgentSpec-enabled repository,
and code agents using `aspec` to bootstrap a new project or continue
improving an existing one. Existing content from T-034 stays; this slice
adds explicit audience markers and tightens the narrative.

## Requirements

- `R-003` Generate a draft project canvas, spec shards, requirements,
  assumptions, open questions, and task context pack templates.
- `R-006` Generate AGENTS.md, CLAUDE.md, Claude Code subagents, Codex
  agents, and reusable role definitions.
- `R-023` After that, the repository should contain enough durable
  context for a code agent to start work without relying on hidden chat
  history.

## Source Sections

- `D-01` Product Charter
- `D-19` CLI Specification

## Allowed Paths

- `README.md`
- `agent/context-packs/T-036-readme-dual-audience-framing.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- Anything outside the allowed paths unless the task is explicitly
  revised.

## Tests To Add Or Update

- No code tests required for README-only changes.

## Acceptance Criteria

- README has a clear "who this is for" section near the top naming both
  audiences.
- Human-facing setup flow (install → init → ingest → compile → emit) is
  narrated, not just listed as commands.
- Code-agent instructions cover two scenarios: bootstrapping a new
  project against `--root $TARGET`, and continuing work on an existing
  AgentSpec-enabled repo (read AGENTS.md, pick a context pack, stay in
  allowed paths, cite requirement IDs, treat source content as
  untrusted, file DCRs for new ideas).
- Existing content from T-034 (Autonomous Mode, What To Commit, Agent
  Control Plane, Verification) is preserved.
- `python -m unittest discover -s tests -v` still passes (no code
  changes).
