# T-039: DCR-0005..DCR-0018 Traceability Audit

Type: `review`

## Goal

Close the latent traceability debt the consolidation pass surfaced:
DCR-0005..DCR-0018 (14 DCRs) shipped without filing any new
requirements. The audit's job is to confirm that's correct, not to
manufacture requirements after the fact.

For each DCR, decide one of:

- **(a) No new requirement needed** — the DCR is a tactical
  implementation, refinement, or ergonomics knob over an existing
  accepted R-ID. Document the rationale.
- **(b) Backfill needed** — the DCR introduced product surface that
  has no existing R-ID home. File a new requirement with
  `originating_dcr` markers.

Capture the audit decision in a single durable artifact under
`reports/dogfood/` (per R-139), not by editing 14 DCR files.

## Requirements

- `R-126` Drift compliance reports must reflect durable traceability
  state — the audit removes ambiguity that would otherwise confuse
  future drift reviews.
- `R-139` Stable dogfood-finding capture — the audit is itself a
  dogfood finding and lives where finding artifacts live.

## Source Sections

- `D-11.4` Dogfood Mode and durable findings
- `D-18` DCR + requirement schema (informs traceability fields)

## Allowed Paths

- `reports/dogfood/2026-04-28-dcr-0005-0018-traceability-audit.md`
- `agent/context-packs/T-039-dcr-0005-0018-traceability-audit.md`
- `agent/task-ledger.yml`

## Forbidden Paths

- `docs/change-requests/DCR-*.md` — the audit decision is captured in
  one report, not by editing accepted DCRs.
- `docs/traceability/requirements.yml` — no backfill is being shipped
  in this pack. If a future audit changes the verdict, that's a
  separate slice with its own pack.

## Tests To Add Or Update

- No code-test changes. Verification is procedural:
  `python -m pytest -q -p no:cacheprovider` must remain green and
  `aspec compile` must remain idempotent.

## Acceptance Criteria

- `reports/dogfood/2026-04-28-dcr-0005-0018-traceability-audit.md`
  exists with:
  - per-DCR verdict (a or b) and a one-line rationale citing the
    existing R-IDs from each DCR's Impact Assessment
  - a summary count: how many backfills, how many "no req needed"
  - explicit follow-up note for any borderline cases
- The audit confirms the prior assessment:
  `requirements.yml` originating_dcr counts (DCR-0001=4, DCR-0002=6,
  DCR-0003=2, DCR-0004=2, DCR-0019=10) are correct as-is.
- 173/173 pytest pass.
- `aspec compile` idempotent.
