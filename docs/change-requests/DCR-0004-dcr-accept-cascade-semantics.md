# DCR-0004: `dcr accept` Cascade Semantics — Per-Requirement Acceptance

| Field | Value |
|---|---|
| Status | accepted |
| Classification | **implement-now** |
| Submitted | 2026-04-28 |
| Submitted by | yimwu (surfaced by Claude pilot agent during T-005 dogfood) |
| Decided by | yimwu |
| Decided on | 2026-04-28 |
| Confidence | high |
| Target milestone | V1 — bundled with T-008 |

## Summary

Change `agentspec dcr accept <id>` so it flips only the **DCR's** status, not
all of its `proposed-pending-acceptance` requirements. Acceptance of a
DCR-derived requirement becomes a separate, deliberate step:
`agentspec requirement accept <R-id>`. Optionally, requirement records gain
an `implementation_complete` flag that a future cascade or status reporter
can rely on.

## Motivation

Surfaced empirically on 2026-04-28 during T-005's dogfood run.

T-005 shipped the `agentspec dcr` CLI and used `dcr accept DCR-0002` to flip
the just-implemented R-125 to `accepted`. The cascade — faithful to R-124's
literal wording ("requirements ... only flip to `accepted` when the DCR is
accepted") — *also* flipped **R-126**, even though R-126's implementation
pack (T-006: drift DCR axis) has not shipped.

Two truths from the same intake disagreed:

- **R-124 (literal):** "Requirements introduced by a DCR are recorded with
  status `proposed-pending-acceptance` and only flip to `accepted` when the
  DCR is accepted." → All R-12X with `originating_dcr=DCR-0002` flip on
  `dcr accept DCR-0002`.
- **DCR-0002 acceptance criteria #7:** "After follow-up packs T-005 (CLI)
  and T-006 (drift) are executed, R-125..R-126 may flip to `accepted`." →
  R-125 flips after T-005, R-126 flips after T-006. Per-pack acceptance.

The operational view (per-pack) is what we actually want. The literal
cascade marks requirements as `accepted` whose code does not yet exist —
a worse state than before, because future contributors will trust the
status field and skip the unimplemented work.

R-126 has been **rolled back** to `proposed-pending-acceptance` pending
this DCR's resolution.

## Proposed Change

1. **Remove the auto-cascade from `agentspec dcr accept`.** That command
   now flips only the DCR's Status row to `accepted` and does not modify
   `requirements.yml`.
2. **Add `agentspec requirement accept <R-id>`** as the canonical way to
   flip a single DCR-derived requirement. It validates that:
   - the requirement exists and is in `proposed-pending-acceptance`
   - its `originating_dcr` (if set) refers to a DCR with status `accepted`
   Then flips its status to `accepted`.
3. **Refine R-124's wording** so the literal text matches the operational
   contract: "Requirements introduced by a DCR are recorded with status
   `proposed-pending-acceptance`. They flip to `accepted` only when (a)
   the originating DCR is `accepted`, AND (b) `agentspec requirement
   accept <R-id>` is invoked — typically because the implementation pack
   for that requirement has shipped and verified."
4. *(Optional, deferrable)* Add `implementation_complete: bool` to the
   requirement schema. `requirement accept` could refuse the flip if this
   flag is False. T-008 may or may not include this — see Q-019.

## Source Section References

Existing `D-*` anchors this change touches:

- `D-11.4` Dogfood Mode — the operational discipline this DCR enforces.
- `D-12.1` CLI Application — adds the `requirement` subcommand.
- `D-18` Domain Model — refines requirement status lifecycle.

## Impact Assessment

### Existing requirements affected

| Req | Type of impact | Action |
|---|---|---|
| `R-124` (DCR-0002) | Literal wording overstates the cascade. | Refine wording when this DCR ships; record the refinement in DCR-0002's history note. |
| `R-125` (DCR-0002) | Already accepted via T-005 cascade. | Stays `accepted` — the cascade was correct *for that requirement* because T-005 had genuinely shipped. |
| `R-126` (DCR-0002) | Was prematurely accepted; rolled back to `proposed-pending-acceptance` by this DCR. | Will flip to `accepted` only when T-006 ships and `agentspec requirement accept R-126` is invoked. |

### Existing task context packs affected

- **T-005** — its `tests/test_dcr_cli.py::test_accept_flips_status_and_cascades_requirements` will need to change when T-008 ships (the cascade behavior changes). T-008's test surface will replace it with separate tests for `dcr accept` (no cascade) and `requirement accept` (single-requirement flip).
- **T-001 / T-002 / T-003 / T-004 / T-006 / T-007** — not affected.

### Source / spec docs needing updates

- `docs/spec/runtime-architecture.md` — once T-008 ships, document the
  separated `dcr accept` / `requirement accept` flow.
- `docs/spec/spec-index.md` — no change.

### Code modules (eventual; T-008's allowed paths)

- `agentspec/dcr.py` — remove cascade from `accept_dcr`.
- `agentspec/cli.py` — add `requirement` subparser with `accept` subcommand.
- `agentspec/requirement.py` (new) — single-requirement accept logic.
- `tests/test_dcr_cli.py` — split the existing cascade test.
- `tests/test_requirement_cli.py` (new) — covers `requirement accept`.

### Open questions raised

| ID | Question |
|---|---|
| `Q-019` | Should requirement records grow an `implementation_complete` flag that `requirement accept` checks (refusing to flip when False)? Pro: prevents accidental claims of completion. Con: extra schema surface, ambiguous who flips it. T-008 may defer this until usage shows whether the manual-only flow is enough. |

Q-018 (filed during T-005) is the originating question; this DCR is its
answer.

## Proposed new requirements

Both recorded with `status: proposed-pending-acceptance`. They flip to
`accepted` after T-008 ships and `agentspec requirement accept R-133` /
`R-134` is invoked.

- `R-133` (P0) — `agentspec dcr accept <id>` flips only the DCR's status to
  `accepted`. It does not modify `requirements.yml`. The DCR's
  Decided-on row is updated to today's date.
- `R-134` (P0) — `agentspec requirement accept <R-id>` flips a single
  requirement from `proposed-pending-acceptance` to `accepted`. It
  validates that the requirement exists, is in `proposed-pending-acceptance`,
  and (if `originating_dcr` is set) the originating DCR is itself
  `accepted`. Refusal cases exit non-zero with a clear error.

## Disposition

**Recommended classification: `implement-now`**, scoped into a new context
pack `T-008-dcr-accept-cascade-fix`.

Rationale:

- The change is bounded: one CLI behavior tweak + one new subcommand +
  small schema clarification. No architectural choice big enough for an
  ADR.
- The two views (literal cascade vs. per-pack acceptance) are already
  authored on the same DCR-0002 page; this DCR picks per-pack as the
  canonical reading and tightens the wording.
- Not blocking: the rollback of R-126 stops the immediate bleed; T-006 and
  T-007 can proceed without T-008 since they don't rely on cascade
  semantics.

Required follow-ups:

- `T-008-dcr-accept-cascade-fix` — to be created when capacity is
  available. **Not** created by this DCR intake.
- Q-019 resolved at T-008 time (or deferred to a future DCR).

## Acceptance Criteria

This DCR is fully addressed when:

1. T-008 ships R-133 and R-134.
2. `tests/test_dcr_cli.py` is split per the impact-assessment plan.
3. R-124's wording is refined in DCR-0002 (or noted as superseded by
   DCR-0004).
4. The next time `agentspec dcr accept <id>` runs on the live workspace,
   no requirement statuses change — only the DCR's status row.
