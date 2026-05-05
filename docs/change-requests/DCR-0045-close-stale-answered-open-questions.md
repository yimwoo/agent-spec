# DCR-0045: Close stale answered open questions

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

Mark stale open-question entries as answered when accepted AgentSpec artifacts
already contain the decision. This is a traceability cleanup only: it does not
change runtime behavior, requirements semantics, or the source snapshots.

## Motivation

Recent dogfood work answered several questions that still appear as open in
`docs/discovery/open-questions.yml`. Leaving these entries open makes the
project look less certain than it is and creates noisy follow-up work for
future agents.

The cleanup should be conservative. Questions stay open when the repository
only has an interim implementation, when the decision is still explicitly
deferred, or when the answer would require a new product decision.

## Proposed Change

- Mark `Q-005` answered by `DCR-0026` / `R-152`: enterprise source bodies are
  not committed by default; storage mode is classification-aware and may be
  pointer-only, local secure cache, or enterprise object store.
- Mark `Q-006` answered by `DCR-0029`: Codex was built first for the first
  plugin slice because this repository can dogfood Codex plugin skills
  immediately.
- Mark `Q-008` answered by `A-002`: the MVP stores structured `.yml`
  artifacts as YAML-compatible JSON to avoid runtime dependencies.
- Mark `Q-016` answered by `DCR-0002` / `R-123`: `defer` is not
  implementation-eligible; downstream context-pack creation is blocked unless
  the DCR is classified `implement-now`, or `needs-adr` with an accepted ADR.
- Mark `Q-023` answered by `DCR-0019` / `R-143`: severity classification is
  hybrid, with deterministic rules first and model-backed review available in
  model/auto reviewer modes.
- Mark `Q-026` answered by `DCR-0043` / `R-178` and `DCR-0044` / `R-179`:
  terminal quality review now has a model-backed test/eval reviewer profile,
  and this repository dogfoods it with `oca/gpt5.3-codex`.

## Impact Assessment

Affected existing artifacts:

- `docs/discovery/open-questions.yml`
- `agent/reviews/REVIEW-0012.yml`
- `agent/task-ledger.yml`
- `docs/traceability/requirements.yml`

Likely new requirement:

- `R-180`: answered open questions cite the accepted artifact that resolved
  them.

Likely task context pack:

- `T-075`: close stale answered open questions.

## Disposition

Classification: `implement-now`.

No ADR is required because this is a ledger cleanup for decisions already made
and accepted elsewhere. Any question without accepted evidence remains open.

## Acceptance Criteria

- `Q-005`, `Q-006`, `Q-008`, `Q-016`, `Q-023`, and `Q-026` have
  `status: answered` with `answered_by` references.
- The original `impact`, `source_sections`, `raised_by`, and hand-curated
  context fields are preserved.
- Questions without accepted decision evidence remain open.
- The open-question and requirement ledgers remain parseable.
