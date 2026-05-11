# DCR-0072: Refresh human-facing README and guide docs

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-11 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-11 |
| Confidence | medium |

## Summary

Refresh the repository's human-facing entrypoints so a first-time reader can
understand what AgentSpec is, install it, run the first workflow, and know where
to go next without reading every generated artifact.

The README should become a concise front door. Deeper operating details should
move into focused guide/index docs that explain the project model, lifecycle,
command map, repository layout, and documentation source-of-truth in plain
language.

## Motivation

AgentSpec has grown from a design compiler into a native lifecycle operating
contract for human + agent software delivery. The current README still reads
like an MVP command transcript and mixes onboarding, agent instructions,
external-source intake, autonomous mode, and control-plane details in one long
page.

This makes the project harder to adopt, especially for humans deciding whether
AgentSpec fits their workflow. It also leaves the maturity profile with no
documentation registry/source-of-truth index.

## Proposed Change

- Rewrite `README.md` as a clean project overview with a short value
  proposition, install path, five-minute quickstart, lifecycle summary,
  repository layout, core commands, and links to focused docs.
- Add a human getting-started guide for people operating AgentSpec in their own
  repositories.
- Add a documentation/design index so readers can find canonical design docs,
  generated specs, DCRs, task packs, reviews, roadmap, and handoff state.
- Keep generated `docs/ROADMAP.md` managed by `aspec roadmap`; do not hand-edit
  generated roadmap content.

## Impact Assessment

- Source sections: `D-03`, `D-05`, `D-10`, `D-18`,
  `agentspec-hotl-integration-without-hotl-names:D-19`.
- New requirement: `R-207`.
- Affected docs: `README.md`, `docs/GETTING_STARTED.md`,
  `docs/designs/README.md`.
- AgentSpec bookkeeping: new task context pack, native workflow, review
  evidence, task ledger, handoff, and generated roadmap refresh.
- Code modules: none.

## Disposition

Accepted for immediate implementation as a documentation-only change.

## Acceptance Criteria

- `README.md` is short enough to scan and gives humans a clear first path:
  install, initialize, ingest, compile, create a task, run/finish work, verify.
- Human guidance explains the project model, when to use DCRs, how to operate
  the lifecycle without relying on external workflow plugins, and what to
  commit.
- A documentation/design index exists at a path recognized by the maturity
  profile as a documentation registry/source-of-truth index.
- The guide cites AgentSpec requirement IDs and links to the deeper artifacts
  needed for implementation, review, roadmap, and handoff.
- Documentation verification passes with JSON validity checks, markdown diff
  checks, AgentSpec maturity/status checks, and roadmap freshness checks.
