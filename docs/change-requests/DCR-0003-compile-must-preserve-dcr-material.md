# DCR-0003: `agentspec compile` Must Not Destroy DCR-Originated Artifacts

| Field | Value |
|---|---|
| Status | accepted |
| Classification | **implement-now (safety guard)** with a follow-up question on long-term merge strategy |
| Submitted | 2026-04-28 |
| Submitted by | yimwu (verified by running compile in a temp copy of the repo); drafted by Claude pilot agent |
| Decided by | yimwu |
| Decided on | 2026-04-28 |
| Confidence | high |
| Target milestone | V1 — bundled with `T-003-design-change-management-schema` |

## Summary

`agentspec compile` is currently **regenerative**: it rewrites
`docs/traceability/requirements.yml` and `docs/discovery/open-questions.yml`
from the canonical source (`docs/source/*`) on every run, with no merge
step. It silently drops any artifact that did not originate from a source
section — including all DCR-originated material (R-121..R-130, Q-012..Q-016
in this milestone).

This DCR raises that finding to a first-class behavioral requirement and
folds the fix into `T-003`. Until the safety guard ships, the live workspace
must not be put through `agentspec compile` or every DCR-originated entry
will be lost.

## Motivation

Verified empirically on 2026-04-28 by the project owner running
`agentspec compile` in a temp copy of the repo:

```text
Compiled 8 spec shards, 120 requirements, 10 open questions. Readiness: 100/100.
```

Post-compile temp state:
- `requirements.yml` — 120 entries, ending at `R-120`, all status `accepted`.
- `open-questions.yml` — 10 entries, ending at `Q-010`.

Live workspace (with the DCR-0001 / DCR-0002 intake applied):
- `requirements.yml` — 130 entries, ending at `R-130`, ten of them
  `proposed-pending-acceptance`.
- `open-questions.yml` — 16 entries, ending at `Q-016`.

The **delta** (R-121..R-130, Q-012..Q-016) is exactly the DCR-originated
material. `compile` drops it, exits 0, and emits no warning.

This is a meta-bug for AgentSpec's own dogfood loop: the design-change
protocol that DCR-0002 just established cannot be honored as long as the
compile step silently destroys its outputs.

## Proposed Change

Two requirements, one bounded interim implementation:

1. **Preservation:** `agentspec compile` must preserve any artifact that is
   marked DCR-originated. For requirements: `originating_dcr` is set OR
   `status == "proposed-pending-acceptance"`. For open questions:
   `raised_by` is set to a DCR ID. Preserved entries are merged into the
   regenerated output, not overwritten by absent source coverage.
2. **Loud failure when reconciliation is impossible:** if compile cannot
   reconcile source-derived output with the DCR-originated artifacts (e.g.
   ID collision between a new source-derived requirement and a preserved
   DCR-originated one), it exits non-zero with a structured error listing
   the affected DCRs and artifact IDs. No silent drops, no implicit
   override of human-curated material.

The long-term *merge strategy* — preserve-by-marker, separate-file,
preserve-by-field, or another approach — is left as an open question
(`Q-017`) and may produce a future DCR. The interim safety guard is
deliberately conservative: preserve and refuse-on-conflict.

## Source Section References

Existing `D-*` anchors this change touches:

- `D-12.5` Spec Compiler — the regenerative behavior is implicit in this
  spec section but not made explicit; this DCR forces the merge contract
  into the open.
- `D-11.4` Dogfood Mode — the dogfood loop must be self-consistent.
  Without DCR-0003, ADR-0002's protocol is undermined by the very
  component that emits its outputs.
- `D-18` Domain Model — `proposed-pending-acceptance` is a load-bearing
  status; compile must respect it.
- `D-07` Architectural Principle "Source-backed over summary-backed" —
  *clarified*: source-backed entries co-exist with DCR-backed entries;
  neither destroys the other.

No new design-doc sections are required. The behavior is a clarification
of D-12.5, captured in code and tests.

## Impact Assessment

### Existing requirements affected

| Req | Source | Type of impact | Action |
|---|---|---|---|
| `R-008` | D-03 | Validation model now spans the merge contract too. | Extend acceptance criteria after T-003 ships. |
| `R-124` | DCR-0002 | This DCR is the *first real test* of `proposed-pending-acceptance`. | None — DCR-0003 satisfies it operationally. |
| Any req citing `D-12.5` Spec Compiler | various | Compiler gains an explicit merge step. | None now; covered by R-131/R-132. |

### Existing task context packs affected

- **T-003 (this milestone)** — scope expands to include the safety guard.
  Previously, T-003 only required compile to "recognize
  `proposed-pending-acceptance` as a valid status." That is insufficient;
  compile must also **preserve** entries with that status. T-003 is
  amended (allowed paths unchanged; one new test file; acceptance
  criteria expanded).
- **T-001 / T-002** — not affected.

### Source / spec docs needing updates

- `docs/spec/runtime-architecture.md` — once T-003 ships, document the
  compile merge contract explicitly so the spec stops being silent on it.
- `docs/spec/spec-index.md` — no change.

### Code modules

- `agentspec/compile.py` — add merge-aware behavior. Read the existing
  `requirements.yml` and `open-questions.yml`, identify DCR-originated
  entries by the rules above, and merge rather than overwrite.

### Open questions raised

| ID | Question |
|---|---|
| `Q-017` | What is the long-term merge strategy for `agentspec compile`? Candidates: preserve-by-marker section in the same file; separate `proposed-requirements.yml` written by the DCR pipeline; preserve-by-field on every record. The interim safety guard chooses **preserve-by-field** (`originating_dcr` / `proposed-pending-acceptance` / `raised_by`) but a deliberate decision is owed. |

## Proposed new requirements

Both recorded with `status: proposed-pending-acceptance`. They flip to
`accepted` when T-003 ships and verifies them.

- `R-131` (P0) — `agentspec compile` preserves any DCR-originated artifact
  when regenerating from source. Specifically: requirements with
  `originating_dcr` set OR `status == "proposed-pending-acceptance"`, and
  open questions with `raised_by` set to a DCR ID, must survive a compile
  run unchanged.
- `R-132` (P0) — When `agentspec compile` cannot reconcile source-derived
  output with DCR-originated artifacts (e.g. an ID collision), it exits
  non-zero with a structured error listing the affected DCRs and
  artifact IDs.

## Disposition

**Recommended classification: `implement-now` (safety guard, scoped into
the existing T-003 pack).**

Rationale:

- Without this fix, the entire DCR intake we just produced cannot survive
  any future `agentspec compile` run — the project owner has confirmed
  this empirically.
- The fix is bounded: a merge step in one module (`agentspec/compile.py`)
  with a small new test surface. It does not require an ADR.
- The long-term merge strategy is a separate, deliberately deferred
  decision (Q-017); the interim contract is conservative
  (`preserve-by-field`) and explicitly documented.

Required follow-ups:

- T-003 amendment: include R-131 and R-132 in scope (this DCR triggers
  the amendment).
- Resolve Q-017 in a future DCR before any feature relies on a different
  merge strategy.

**Operational guard until T-003 ships:** do not run `agentspec compile`
on the live workspace. The live `requirements.yml` and
`open-questions.yml` already contain the DCR-originated entries; running
compile would erase them.

## Acceptance Criteria

This DCR is fully addressed when:

1. T-003 produces a `tests/test_compile_preserves_dcr_material.py`
   covering the preservation rule and the conflict-error rule.
2. Running `python -m agentspec.cli compile` against a fixture that
   contains DCR-originated requirements and questions emits the same
   set of DCR-originated entries on output.
3. Running `python -m agentspec.cli compile` against a fixture that
   *would* drop a DCR-originated entry exits non-zero with a structured
   error.
4. R-131 and R-132 flip from `proposed-pending-acceptance` to `accepted`.
