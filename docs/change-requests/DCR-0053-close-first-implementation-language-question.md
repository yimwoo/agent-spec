# DCR-0053: Close first implementation language question

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

Close `Q-002` by recording the now-observed implementation-language decision:
AgentSpec V1's core implementation is Python, delivered as a local-first CLI
package. TypeScript remains a supported target-project language for scanning,
context-pack generation, and plugin-adapter surfaces, but the core engine is
not a split Python/TypeScript architecture.

## Motivation

`Q-002` was useful during initial planning, but the repository has now shipped
80 governed tasks as a Python package with console scripts and a Python module
layout. Keeping the question open makes Quality GC and future sessions treat a
settled implementation fact as unresolved strategy.

The important nuance is that "Python first" applies to the AgentSpec engine
itself, not to repositories AgentSpec can analyze. Brownfield and target
inference work already prevents the engine from assuming every user project is
Python.

## Proposed Change

- Mark `Q-002` answered in `docs/discovery/open-questions.yml`.
- Cite this DCR and `R-188` as the accepted decision evidence.
- Preserve future flexibility for generated plugins, browser/UI harnesses, or
  target-project adapters to use other languages when a separate DCR justifies
  that scope.

## Impact Assessment

Affected open question:

- `Q-002`: "Should the first implementation language be Python, TypeScript, or
  a split architecture?"

New requirement:

- `R-188`: First implementation language question is answered.

Affected artifacts:

- `docs/discovery/open-questions.yml`
- `docs/traceability/requirements.yml`
- `docs/change-requests/DCR-0053-close-first-implementation-language-question.md`

## Disposition

Classification: `implement-now`.

No ADR is required. This is a product/implementation fact already reflected in
the package layout and prior accepted requirements. A future ADR/DCR would be
appropriate only if AgentSpec's core runtime moves to a split architecture.

## Acceptance Criteria

- `Q-002` is marked `answered` with `answered_by: DCR-0053/R-188`.
- Existing impact and source-section metadata for `Q-002` is preserved.
- The requirement ledger records `R-188` with accepted decision evidence after
  task verification.
- No other open question is closed by this task.
- Open-question and requirement ledgers remain parseable.
